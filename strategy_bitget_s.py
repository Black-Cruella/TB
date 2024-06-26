import sys
sys.path.append("./TBWOTP")
import ccxt
import ta
import pandas as pd
import pandas_ta as pda 
from perp_bitget import PerpBitget
from custom_indicators import get_n_columns
from datetime import datetime
import time
import json

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- Start Execution Time :", current_time, "---")

f = open(
    "./TBWOTP/secret.json",
)
secret = json.load(f)
f.close()

account_to_select = "bitget_exemple"
production = True

pair = "AVAX/USDT:USDT"
timeframe = "1m"
leverage = 0.99

print(f"--- {pair} {timeframe} Leverage x {leverage} ---")

type = ["long", "short"]

def open_long(row):
    if row['buy_signal'] or row['close_short_signal']:
        return True
    else:
        return False

def close_long(row):
    if row['close_long']:
        return True
    else:
        return False

def open_short(row):
    if row['sell_signal'] or row['close_long_signal']:
        return True
    else:
        return False

def close_short(row):
    if row['close_short']:
        return True
    else:
        return False


bitget = PerpBitget(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    password=secret[account_to_select]["password"],
)

# Get data
df = bitget.get_last_historical(pair, timeframe, 100)

df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

df['buy_signal'] = (df['rsi'].shift(1) < 30) & (df['rsi'] > 30)
df['close_long'] = (df['rsi'].shift(1) > 70) & (df['rsi'] < 70)
df['sell_signal'] = (df['rsi'].shift(1) > 70) & (df['rsi'] < 70)
df['close_short'] = (df['rsi'].shift(1) < 30) & (df['rsi'] > 30)
df['close_short_signal'] = df['close_short'].shift(1)
df['close_long_signal'] = df['close_long'].shift(1)

positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["marketPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["marketPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")

row = df.iloc[-2]

pd.set_option('display.max_columns', None)
print(df.tail(5))

if len(position) > 0:
    position = position[0]
    print(f"Current position : {position}")
    if position["side"] == "long" and close_long(row):
        close_long_market_price = float(df.iloc[-1]["close"])
        close_long_quantity = float(
            bitget.convert_amount_to_precision(pair, position["size"])
        )
        exchange_close_long_quantity = close_long_quantity * close_long_market_price
        print(
            f"Place Close Long Market Order: {close_long_quantity} {pair[:-5]} at the price of {close_long_market_price}$ ~{round(exchange_close_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", close_long_quantity, reduce=True)
           
    elif position["side"] == "short" and close_short(row):
        close_short_market_price = float(df.iloc[-1]["close"])
        close_short_quantity = float(
            bitget.convert_amount_to_precision(pair, position["size"])
        )
        exchange_close_short_quantity = close_short_quantity * close_short_market_price
        print(
            f"Place Close Short Market Order: {close_short_quantity} {pair[:-5]} at the price of {close_short_market_price}$ ~{round(exchange_close_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", close_short_quantity, reduce=True)
        
        

else:
    print("No active position")
    if open_long(row) and "long" in type:
        long_market_price = float(df.iloc[-1]["close"])
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, long_quantity_in_usd / long_market_price)
        )))
        exchange_long_quantity = long_quantity * long_market_price
        print(
            f"Place Open Long Market Order: {long_quantity} {pair[:-5]} at the price of {long_market_price}$ ~{round(exchange_long_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "buy", long_quantity, reduce=False)
        #if production:
        #    stop_loss_price = long_market_price * 1.002  # 1% sous le prix d'achat
        #    print(f"Place Long Stop Loss Order at {stop_loss_price}$")
        #    bitget.place_market_stop_loss(pair, 'sell', long_quantity, stop_loss_price, reduce=True)

    elif open_short(row) and "short" in type:
        short_market_price = float(df.iloc[-1]["close"])
        short_quantity_in_usd = usd_balance * leverage
        short_quantity = float(bitget.convert_amount_to_precision(pair, float(
            bitget.convert_amount_to_precision(pair, short_quantity_in_usd / short_market_price)
        )))
        exchange_short_quantity = short_quantity * short_market_price
        print(
            f"Place Open Short Market Order: {short_quantity} {pair[:-5]} at the price of {short_market_price}$ ~{round(exchange_short_quantity, 2)}$"
        )
        if production:
            bitget.place_market_order(pair, "sell", short_quantity, reduce=False)
        #if production:
        #    stop_loss_price = short_market_price * 0.998  # 1% au-dessus du prix de vente
        #    print(f"Place Short Stop Loss Order at {stop_loss_price}$")
        #    bitget.place_market_stop_loss(pair, 'buy', short_quantity, stop_loss_price, reduce=True)

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
