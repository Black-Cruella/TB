import sys
sys.path.append("./TB")
import ccxt
import ta
from perp_bitget import PerpBitget
import pandas_ta as pda 
import pandas as pd
from datetime import datetime
import time
import json

account_to_select = "bitget_exemple"
production = True

pair = "AVAX/USDT:USDT"
leverage = 1
type=["long", "short"]
src="close"

f = open(
    "./TB/secret.json",
)
secret = json.load(f)
f.close()


bitget = PerpBitget(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    password=secret[account_to_select]["password"],
)

candles = bitget.get_last_historical(pair, "5m", 100)
df = pd.DataFrame(candles)

# Calculer les bougies Heikin Ashi
ha_df = pd.DataFrame(index=df.index, columns=['open', 'high', 'low', 'close'])

ha_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
ha_df['close_original'] = df['close']

ha_df.at[ha_df.index[0], 'open'] = df.at[df.index[0], 'close']

for i in range(1, len(df)):
    ha_df.at[df.index[i], 'open'] = (ha_df.at[df.index[i - 1], 'open'] + ha_df.at[df.index[i - 1], 'close']) / 2
    ha_df.at[df.index[i], 'high'] = max(df.at[df.index[i], 'high'], ha_df.at[df.index[i], 'open'], ha_df.at[df.index[i], 'close'])
    ha_df.at[df.index[i], 'low'] = min(df.at[df.index[i], 'low'], ha_df.at[df.index[i], 'open'], ha_df.at[df.index[i], 'close'])

ST_length = 21
ST_multiplier = 1.0
superTrend = pda.supertrend(ha_df['high'], ha_df['low'], ha_df['close'], length=ST_length, multiplier=ST_multiplier)
ha_df['SUPER_TREND1'] = superTrend['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
ha_df['SUPER_TREND_DIRECTION1'] = superTrend['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

ST_length = 14
ST_multiplier = 2.0
superTrend = pda.supertrend(ha_df['high'], ha_df['low'], ha_df['close'], length=ST_length, multiplier=ST_multiplier)
ha_df['SUPER_TREND2'] = superTrend['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
ha_df['SUPER_TREND_DIRECTION2'] = superTrend['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

# Calculate buy signals
ha_df['buy_signal'] = (ha_df['SUPER_TREND_DIRECTION1'] == 1) & (ha_df['SUPER_TREND_DIRECTION2'] == 1)

# Calculate sell signals
ha_df['sell_signal'] = (ha_df['SUPER_TREND_DIRECTION1'] == -1) & (ha_df['SUPER_TREND_DIRECTION2'] == -1)

usd_balance = float(bitget.get_usdt_equity())
usd_balance = usd_balance * leverage
print(f"Balance: {round(usd_balance, 2)} $", )

pd.set_option('display.max_rows', None)
print(ha_df)

# Récupération des positions ouvertes
positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["marketPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["marketPrice"]), "entry_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

row = df.iloc[-2]

if len(position) > 0:
    position = position[0]
    print(f"Current position : {position}")
    if position["side"] == "long" and row['sell_signal']:
        close_long_market_price = float(df.iloc[-1]["close"])
        close_long_quantity = float(bitget.convert_amount_to_precision(pair, position["size"]))
        exchange_close_long_quantity = close_long_quantity * close_long_market_price
        print(
            f"Place Close Long Market Order: {close_long_quantity} {pair[:-5]} at the price of {close_long_market_price}$ ~{round(exchange_close_long_quantity, 2)}$")
        if True:  # Set to True to place orders (e.g., production)
            bitget.place_market_order(pair, "sell", close_long_quantity, reduce=True)

    elif position["side"] == "short" and row['buy_signal']:
        close_short_market_price = float(df.iloc[-1]["close"])
        close_short_quantity = float(bitget.convert_amount_to_precision(pair, position["size"]))
        exchange_close_short_quantity = close_short_quantity * close_short_market_price
        print(
            f"Place Close Short Market Order: {close_short_quantity} {pair[:-5]} at the price of {close_short_market_price}$ ~{round(exchange_close_short_quantity, 2)}$")
        if True:  # Set to True to place orders (e.g., production)
            bitget.place_market_order(pair, "buy", close_short_quantity, reduce=True)

else:
    print("No active position")
    if row['buy_signal']:
        long_market_price = float(df.iloc[-1]["close"])
        long_quantity_in_usd = usd_balance * leverage
        long_quantity = float(
            bitget.convert_amount_to_precision(pair, float(
                bitget.convert_amount_to_precision(pair, long_quantity_in_usd / long_market_price)
            )))
        exchange_long_quantity = long_quantity * long_market_price
        print(
            f"Place Open Long Market Order: {long_quantity} {pair[:-5]} at the price of {long_market_price}$ ~{round(exchange_long_quantity, 2)}$")
        if True:  # Set to True to place orders (e.g., production)
            bitget.place_market_order(pair, "buy", long_quantity, reduce=False)

    elif row['sell_signal']:
        short_market_price = float(df.iloc[-1]["close"])
        short_quantity_in_usd = usd_balance * leverage
        short_quantity = float(
            bitget.convert_amount_to_precision(pair, float(
                bitget.convert_amount_to_precision(pair, short_quantity_in_usd / short_market_price)
            )))
        exchange_short_quantity = short_quantity * short_market_price
        print(
            f"Place Open Short Market Order: {short_quantity} {pair[:-5]} at the price of {short_market_price}$ ~{round(exchange_short_quantity, 2)}$")
        if True:  # Set to True to place orders (e.g., production)
            bitget.place_market_order(pair, "sell", short_quantity, reduce=False)

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
