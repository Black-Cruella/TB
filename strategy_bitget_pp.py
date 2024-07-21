import sys
sys.path.append("./TBPP")
import ccxt
import ta
import pandas as pd
import pandas_ta as pda 
from perp_bitget import PerpBitget
from custom_indicators import get_n_columns
from datetime import datetime
import time
import json
import numpy as np

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- Start Execution Time :", current_time, "---")

f = open(
    "./TBPP/secret.json",
)
secret = json.load(f)
f.close()

account_to_select = "bitget_exemple"
production = True

pair = "AVAX/USDT:USDT"
timeframe = "30m"
leverage = 0.99

print(f"--- {pair} {timeframe} Leverage x {leverage} ---")

bitget = PerpBitget(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    password=secret[account_to_select]["password"],
)

# Get data
df = bitget.get_last_historical(pair, timeframe, 900)

def calculate_pivots(prices_high, prices_low, depth):
    pivots_high = [np.nan] * len(prices_high)
    pivots_low = [np.nan] * len(prices_low)
    for i in range(depth, len(prices_high) - depth):
        if prices_high.iloc[i] == max(prices_high.iloc[i - depth:i + depth + 1]):
            pivots_high[i] = prices_high.iloc[i]
        if prices_low.iloc[i] == min(prices_low.iloc[i - depth:i + depth + 1]):
            pivots_low[i] = prices_low.iloc[i]
    return pivots_high, pivots_low

def calc_dev(base_price, price):
    return 100 * (price - base_price) / base_price

def calculate_zigzag(prices_high, prices_low, volumes, dev_threshold, depth, timestamps):
    highs, lows = calculate_pivots(prices_high, prices_low, depth)

    zigzag = []
    last_pivot = None
    cumulative_volume = 0

    for i in range(len(prices_high)):
        if not np.isnan(highs[i]):
            dev = calc_dev(last_pivot, highs[i]) if last_pivot is not None else np.inf
            if last_pivot is None or dev >= dev_threshold:
                zigzag.append((timestamps[i], highs[i], cumulative_volume))
                last_pivot = highs[i]
                cumulative_volume = 0
        elif not np.isnan(lows[i]):
            dev = calc_dev(last_pivot, lows[i]) if last_pivot is not None else np.inf
            if last_pivot is None or dev <= -dev_threshold:
                #zigzag.append((timestamps[i], lows[i], cumulative_volume))
                last_pivot = lows[i]
                cumulative_volume = 0
        cumulative_volume += volumes.iloc[i]

    zigzag_df = pd.DataFrame(zigzag, columns=['timestamp', 'price', 'cumulative_volume'])
    zigzag_df.set_index('timestamp', inplace=True)

    return zigzag_df

# Example usage with a DataFrame `df`
def add_pivots_and_zigzag_to_df(df, dev_threshold, depth):
    prices_high = df['high']
    prices_low = df['low']
    volumes = df['volume']
    timestamps = df.index

    pivots_high, pivots_low = calculate_pivots(prices_high, prices_low, depth)
    df['pivot_high'] = pivots_high
    df['pivot_low'] = pivots_low

    zigzag_df = calculate_zigzag(prices_high, prices_low, volumes, dev_threshold, depth, timestamps)

    df = pd.merge(df, zigzag_df, left_index=True, right_index=True, how='left')
    df.drop(columns=['cumulative_volume'], inplace=True)
    df['pivot_high'] = df['pivot_high'].fillna(method='ffill')
    df['pivot_low'] = df['pivot_low'].fillna(method='ffill')
    df['price'] = df['price'].fillna(method='ffill')
    # Add new columns if needed
    df['last_zigzag_price'] = zigzag_df['price'].shift(1)
    df['last_zigzag_price'] = df['last_zigzag_price'].fillna(method='ffill')
    
    return df, zigzag_df

df, zigzag_df = add_pivots_and_zigzag_to_df(df, dev_threshold=0.5, depth=12)

positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["markPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["markPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

open_orders = bitget.get_open_order(pair)
order = [
    {"side": d["side"], "size": d["info"]["size"], "Id": d["id"], "market_price":d["info"]["price"]}
    for d in open_orders if d["symbol"] == pair]
print("Ordres ouverts :", order)

TS_open_orders = bitget.get_TS_open_order(pair)
TS_order = [
    {"side": d["side"], "size": d["size"], "Id": d["orderId"], "trigger_price": d["triggerPrice"]}
    for d in TS_open_orders if d["symbol"] == pair]
print("Trailings ouverts :", TS_order)

last_zigzag_price = df.iloc[-1]['last_zigzag_price']
for ord in open_orders:
    if float(ord['price']) == last_zigzag_price:
        order_id = ord['id']
        bitget.cancel_open_order(pair, order_id)

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")

row = df.iloc[-13]
    
num_orders_open = len(open_orders)
num_TS_orders_open = len(TS_open_orders)
print(num_TS_orders_open)
num_position_open = len(position)
if num_orders_open < 1 and num_position_open < 1:
    zigzag_price = row['price']
    long_quantity_in_usd = usd_balance * leverage
    long_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, long_quantity_in_usd / zigzag_price))))
    exchange_long_quantity = long_quantity * zigzag_price
    print(f"Place Limit Long Market Order: {long_quantity} {pair[:-5]} at the price of {zigzag_price}$ ~{round(exchange_long_quantity, 2)}$")
    if production:
        bitget.place_limit_order(pair, 'buy', long_quantity, zigzag_price, reduce=False)

# Ajouter le Open Price
if len(positions_data) == 0:
    df['entry_price'] = None
else:
    position_info = positions_data[0]
    entry_price = position_info['entryPrice']
    df['entry_price'] = entry_price

if num_TS_orders_open < 1 and num_position_open == 1:
    long_quantity_in_usd = usd_balance * leverage
    long_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, long_quantity_in_usd / entry_price))))

    trailing_stop_price = entry_price * 1.001
    rounded_price = round(trailing_stop_price, 3)
    trailingPercent = 0.2  # 1% de suivi
    print(f"Place Short Trailing Stop Order at {rounded_price}$ with range rate {trailingPercent}")
    bitget.place_trailing_stop('AVAXUSDT', 'sell', long_quantity, rounded_price, trailingPercent)

    stop_loss_price = entry_price * 0.998  # 1% au-dessus du prix de vente
    print(f"Place Short Stop Loss Order at {stop_loss_price}$")
    bitget.place_market_stop_loss(pair, 'sell', long_quantity, stop_loss_price, reduce=True)



    
#    elif row['direction'] == 'GO SHORT':
#        short_market_price = float(df.iloc[-1]["close"])
#        short_quantity_in_usd = usd_balance * leverage
#        short_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, short_quantity_in_usd / zigzag_price))))
#        exchange_short_quantity = short_quantity * zigzag_price
#        print(f"Place Open Short Market Order: {short_quantity} {pair[:-5]} at the price of {zigzag_price}$ ~{round(exchange_short_quantity, 2)}$")
#        if production:
#            bitget.place_limit_order(pair, 'sell', short_quantity, zigzag_price, reduce=False)

print(zigzag_df)
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
print(df.tail(10))

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
