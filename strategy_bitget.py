import sys
sys.path.append("./TB")
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
    "./TB/secret.json",
)
secret = json.load(f)
f.close()

account_to_select = "bitget_exemple"
production = True

pair = "AVAX/USDT:USDT"
timeframe = "5m"
leverage = 0.99

print(f"--- {pair} {timeframe} Leverage x {leverage} ---")

type = ["long", "short"]



def open_long(row):
    if (
        row['buy_signal']
    ):
        return True
    else:
        return False

def close_long(row):
    if (row['sell_signal']):
        return True
    else:
        return False

def open_short(row):
    if (
        row['sell_signal']      
    ):
        return True
    else:
        return False

def close_short(row):
    if (row['buy_signal']):
        
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

# Populate indicator
# Calculer les bougies Heikin Ashi
df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
df['ha_close_original'] = df['close']

df.at[df.index[0], 'ha_open'] = df.at[df.index[0], 'close']

for i in range(1, len(df)):
    df.at[df.index[i], 'ha_open'] = (df.at[df.index[i - 1], 'ha_open'] + df.at[df.index[i - 1], 'ha_close']) / 2
    df.at[df.index[i], 'ha_high'] = max(df.at[df.index[i], 'high'], df.at[df.index[i], 'ha_open'], df.at[df.index[i], 'ha_close'])
    df.at[df.index[i], 'ha_low'] = min(df.at[df.index[i], 'low'], df.at[df.index[i], 'ha_open'], df.at[df.index[i], 'ha_close'])

# Calculer les superTrend
ST_length = 21
ST_multiplier = 1.0
superTrend1 = pda.supertrend(df['ha_high'], df['ha_low'], df['ha_close'], length=ST_length, multiplier=ST_multiplier)
df['SUPER_TREND1'] = superTrend1['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
df['SUPER_TREND_DIRECTION1'] = superTrend1['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

ST_length = 14
ST_multiplier = 2.0
superTrend2 = pda.supertrend(df['ha_high'], df['ha_low'], df['ha_close'], length=ST_length, multiplier=ST_multiplier)
df['SUPER_TREND2'] = superTrend2['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
df['SUPER_TREND_DIRECTION2'] = superTrend2['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

# Calculer les signaux d'achat
df['buy_signal'] = (df['SUPER_TREND_DIRECTION1'] == 1) & (df['SUPER_TREND_DIRECTION2'] == 1)

# Calculer les signaux de vente
df['sell_signal'] = (df['SUPER_TREND_DIRECTION1'] == -1) & (df['SUPER_TREND_DIRECTION2'] == -1)

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")
print(df)

positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["marketPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["marketPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

row = df.iloc[-2]

current_plan_orders = perp_bitget.get_current_plan_orders(pair)

# Ou pour récupérer les ordres TPSL pour un type de produit spécifique
# current_plan_orders = perp_bitget.get_current_plan_orders(productType="votreTypeDeProduit")

print(current_plan_orders)

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
        if production:
            stop_loss_price = long_market_price * 0.995  # 0.5% sous le prix d'achat
            print(f"Place Long Stop Loss Order at {stop_loss_price}$")
            bitget.place_market_stop_loss(pair, 'sell', long_quantity, stop_loss_price, reduce=True)

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
        if production:
            stop_loss_price = short_market_price * 1.005  # 0.5% au-dessus du prix de vente
            print(f"Place Short Stop Loss Order at {stop_loss_price}$")
            bitget.place_market_stop_loss(pair, 'buy', short_quantity, stop_loss_price, reduce=True)


now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
