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
timeframe = "1m"
leverage = 0.99

print(f"--- {pair} {timeframe} Leverage x {leverage} ---")

bitget = PerpBitget(
    apiKey=secret[account_to_select]["apiKey"],
    secret=secret[account_to_select]["secret"],
    password=secret[account_to_select]["password"],
)

# Get data
df = bitget.get_last_historical(pair, timeframe, 100)

def pivot_points_high_low(df, left, right, percent_threshold=2.0):
    # Calcul des potential pivots highs
    highs = df['high'].rolling(window=left + right + 1, center=True).max()
    pivot_high_mask = (df['high'] == highs) & (df['high'].shift(left) != highs)

    # Calcul des potential pivots lows
    lows = df['low'].rolling(window=left + right + 1, center=True).min()
    pivot_low_mask = (df['low'] == lows) & (df['low'].shift(left) != lows)

    percent_threshold /= 100.0  # Convertir en décimal pour le calcul

    last_pivot_high = None
    last_pivot_low = None

    # Créer des listes pour stocker les valeurs des pivots validés
    pivot_high_values = [np.nan] * len(df)
    pivot_low_values = [np.nan] * len(df)

    for i in range(len(df)):
        if pivot_high_mask[i]:
            if last_pivot_low is None or (df['high'][i] >= last_pivot_low * (1 + percent_threshold)):
                pivot_high_values[i] = df['high'][i]
                last_pivot_high = df['high'][i]
        if pivot_low_mask[i]:
            if last_pivot_high is None or (df['low'][i] <= last_pivot_high * (1 - percent_threshold)):
                pivot_low_values[i] = df['low'][i]
                last_pivot_low = df['low'][i]

    df['pivot_high_value'] = pivot_high_values
    df['pivot_low_value'] = pivot_low_values

    return df['pivot_high_value'], df['pivot_low_value']

df['pivot_high_value'], df['pivot_low_value'] = pivot_points_high_low(df, left=5, right=5, percent_threshold=2.0)

positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["markPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["markPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")

row = df.iloc[-2]

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
print(df.tail(150))

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")
