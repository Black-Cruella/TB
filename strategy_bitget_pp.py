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
RT_df = bitget.get_last_historical(pair, "1m", 60)

try:
    with open('./TBPP/hp_status.txt', 'r') as file:
        hp_status = file.read().strip()
        if hp_status == 'used':
            print("HP Status is: used, waiting for new point")
        else:
            print("HP Status is: unused, waiting for execution")
except FileNotFoundError:
    hp_status = 'unused'
    print("Status file not found. Status is: unused, waiting for execution")
except Exception as e:
    print(f"An error occurred: {e}")
    hp_status = 'unused'

try:
    with open('./TBPP/lp_status.txt', 'r') as file:
        lp_status = file.read().strip()
        if lp_status == 'used':
            print("LP Status is: used, waiting for new point")
        else:
            print("LP Status is: unused, waiting for execution")
except FileNotFoundError:
    lp_status = 'unused'
    print("Status file not found. Status is: unused, waiting for execution")
except Exception as e:
    print(f"An error occurred: {e}")
    lp_status = 'unused'


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
                zigzag.append((timestamps[i], highs[i], cumulative_volume, 'high'))
                last_pivot = highs[i]
                cumulative_volume = 0
        elif not np.isnan(lows[i]):
            dev = calc_dev(last_pivot, lows[i]) if last_pivot is not None else np.inf
            if last_pivot is None or dev <= -dev_threshold:
                zigzag.append((timestamps[i], lows[i], cumulative_volume, 'low'))
                last_pivot = lows[i]
                cumulative_volume = 0
        cumulative_volume += volumes.iloc[i]

    zigzag_df = pd.DataFrame(zigzag, columns=['timestamp', 'price', 'cumulative_volume', 'H/L'])
    zigzag_df.set_index('timestamp', inplace=True)

    return zigzag_df

# Example usage with a DataFrame `df`
def add_pivots_and_zigzag_to_df(df, dev_threshold, depth):
    prices_high = df['high']
    prices_low = df['low']
    volumes = df['volume']
    timestamps = df.index

    zigzag_df = calculate_zigzag(prices_high, prices_low, volumes, dev_threshold, depth, timestamps)
    hp_df = zigzag_df[zigzag_df['H/L'] == 'high'].drop(columns=['H/L'])
    lp_df = zigzag_df[zigzag_df['H/L'] == 'low'].drop(columns=['H/L'])
    df = pd.merge(df, zigzag_df, left_index=True, right_index=True, how='left')
    df.drop(columns=['cumulative_volume'], inplace=True)
    df.drop(columns=['H/L'], inplace=True)
    df['price'] = df['price'].fillna(method='ffill')
    # Add new columns if needed
    df['last_zigzag_price'] = zigzag_df['price'].shift(1)
    df['last_zigzag_price'] = df['last_zigzag_price'].fillna(method='ffill')
    
    return df, zigzag_df, hp_df, lp_df

def add_signal_column(df):
    df['signal'] = 'WAITING'
    for i in range(1, len(df)):
        if df.loc[df.index[i], 'price'] != df.loc[df.index[i-1], 'price']:
            df.loc[df.index[i], 'signal'] = 'NEW POINT'
    return df

df, zigzag_df, hp_df, lp_df = add_pivots_and_zigzag_to_df(df, dev_threshold=0.5, depth=12)
df = add_signal_column(df)


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
if TS_open_orders is not None and 'data' in TS_open_orders:
    TS_orders_data = TS_open_orders['data'].get('entrustedList', [])
    if TS_orders_data is None:
        TS_orders_data = []
else:
    TS_orders_data = []

TS_order = [
    {"side": d["side"], "size": d["size"], "Id": d["orderId"], "trigger_price": d["triggerPrice"]}
    for d in TS_orders_data
]
TS_order_Id = [d["orderId"] for d in TS_orders_data]
print("Trailing ouvert :", TS_order)

last_zigzag_price = df.iloc[-1]['last_zigzag_price']
for ord in open_orders:
    if float(ord['price']) == last_zigzag_price:
        order_id = ord['id']
        bitget.cancel_open_order(pair, order_id)

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")

row = df.iloc[-13]
if row["signal"] == "NEW POINT":
    if row['price'] == hp_df.iloc[-1]['price']:
        hp_status = 'unused'
    if row['price'] == lp_df.iloc[-1]['price']:
        lp_status = 'unused'

num_orders_open = len(open_orders)
num_TS_orders_open = len(TS_order)
num_position_open = len(position)

#Annuler les Trailings
if num_position_open < 1:
    for ts_order_id in TS_order_Id:
        bitget.cancel_TS_open_order('AVAXUSDT', ts_order_id)
        print(f"Trailing stop order {ts_order_id} canceled due to main position closure.")

# Ajouter le Open Price
if len(positions_data) == 0:
    df['entry_price'] = None
else:
    position_info = positions_data[0]
    entry_price = position_info['entryPrice']
    df['entry_price'] = entry_price

if len(positions_data) == 0:
    df['side'] = None
    side = 'close'
else :
    position_info = positions_data[0]
    side = position_info['side']
    df['side'] = side


if num_orders_open < 1 and num_position_open < 1 and hp_status == 'unused':
    zigzag_price = hp_df.iloc[-1]['price']
    RT_high = RT_df.iloc[-2]['high'] + 0.05
    RT_low = RT_df.iloc[-2]['low'] - 0.05
    
    if RT_low <= zigzag_price <= RT_high:
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, long_quantity_in_usd / zigzag_price))))
        exchange_long_quantity = long_quantity * zigzag_price
        print(f"Place Limit Long Market Order: {long_quantity} {pair[:-5]} at the price of {zigzag_price}$ ~{round(exchange_long_quantity, 2)}$")
        if production:
            bitget.place_limit_order(pair, 'buy', long_quantity, zigzag_price, reduce=False)
            hp_status = 'used'
    else:
        print(f"Zigzag High price {zigzag_price}$ is not within the range of RT_df high {RT_high}$ and low {RT_low}$.")
    
    #Ouvrir le TS et SL
if side == "long":
    if num_TS_orders_open < 1 and num_position_open == 1:
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, long_quantity_in_usd / entry_price))))
        
        trailing_stop_price = entry_price * 1.001
        rounded_price = round(trailing_stop_price, 3)
        trailingPercent = 0.25  # 1% de suivi
        print(f"Place Short Trailing Stop Order at {rounded_price}$ with range rate {trailingPercent}")
        bitget.place_trailing_stop('AVAXUSDT', 'sell', long_quantity, rounded_price, trailingPercent)
        
        stop_loss_price = entry_price * 0.998  # 1% au-dessus du prix de vente
        SL_rounded_price = round(stop_loss_price, 3)
        print(f"Place Short Stop Loss Order at {SL_rounded_price}$")
        bitget.place_market_stop_loss('AVAXUSDT', 'buy', long_quantity, SL_rounded_price, reduce=True)


if num_orders_open < 1 and num_position_open < 1 and lp_status == 'unused':
        zigzag_price = lp_df.iloc[-1]['price']
        RT_high = RT_df.iloc[-2]['high'] + 0.05
        RT_low = RT_df.iloc[-2]['low'] - 0.05
        
        if RT_low <= zigzag_price <= RT_high:
            short_quantity_in_usd = usd_balance * leverage
            short_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, short_quantity_in_usd / zigzag_price))))
            exchange_short_quantity = short_quantity * zigzag_price
            print(f"Place Limit short Market Order: {short_quantity} {pair[:-5]} at the price of {zigzag_price}$ ~{round(exchange_short_quantity, 2)}$")
            if production:
                bitget.place_limit_order(pair, 'sell', short_quantity, zigzag_price, reduce=False)
                lp_status = 'used'
        else:
            print(f"Zigzag Low price {zigzag_price}$ is not within the range of RT_df high {RT_high}$ and low {RT_low}$.")
        
if side == "short":
    if num_TS_orders_open < 1 and num_position_open == 1:
        short_quantity_in_usd = usd_balance * leverage
        short_quantity = float(bitget.convert_amount_to_precision(pair, float(bitget.convert_amount_to_precision(pair, short_quantity_in_usd / entry_price))))
        
        trailing_stop_price = entry_price * 0.999
        rounded_price = round(trailing_stop_price, 3)
        trailingPercent = 0.25  # 1% de suivi
        print(f"Place long Trailing Stop Order at {rounded_price}$ with range rate {trailingPercent}")
        bitget.place_trailing_stop('AVAXUSDT', 'buy', short_quantity, rounded_price, trailingPercent)
        
        stop_loss_price = entry_price * 1.002  # 1% au-dessus du prix de vente
        SL_rounded_price = round(stop_loss_price, 3)
        print(f"Place long Stop Loss Order at {SL_rounded_price}$")
        bitget.place_market_stop_loss('AVAXUSDT', 'sell', short_quantity, SL_rounded_price, reduce=True)


print(hp_df.tail(10))
print(lp_df.tail(10))
print(df.tail(10))
print(RT_df.tail(10))

with open('./TBPP/hp_status.txt', 'w') as file:
    file.write(str(hp_status))

with open('./TBPP/lp_status.txt', 'w') as file:
    file.write(str(lp_status))


now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
