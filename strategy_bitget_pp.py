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

#Indicators
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

def calculate_zigzag(prices_high, prices_low, volumes, dev_threshold, depth):
    highs, lows = calculate_pivots(prices_high, prices_low, depth)

    zigzag = []
    last_pivot = None
    cumulative_volume = 0

    for i in range(len(prices_high)):
        if not np.isnan(highs[i]):
            dev = calc_dev(last_pivot, highs[i]) if last_pivot is not None else np.inf
            if last_pivot is None or dev >= dev_threshold:
                zigzag.append((i, highs[i], cumulative_volume))
                last_pivot = highs[i]
                cumulative_volume = 0
        elif not np.isnan(lows[i]):
            dev = calc_dev(last_pivot, lows[i]) if last_pivot is not None else np.inf
            if last_pivot is None or dev <= -dev_threshold:
                zigzag.append((i, lows[i], cumulative_volume))
                last_pivot = lows[i]
                cumulative_volume = 0
        cumulative_volume += volumes.iloc[i]

    return zigzag

# Calculate zigzag pivots and cumulative volume
dev_threshold = 2.0  # en pourcentage
depth = 5  # en nombre de barres

# Assuming you have 'high' and 'low' columns in your DataFrame 'df'
prices_high = df['high']
prices_low = df['low']
volumes = df['volume']

zigzag = calculate_zigzag(prices_high, prices_low, volumes, dev_threshold, depth)

# Initialize lists to store zigzag points
zigzag_x = []
zigzag_y = []

# Record zigzag points with their timestamps and prices
for i, (idx, price, cum_volume) in enumerate(zigzag):
    zigzag_x.append(df.index[idx])
    zigzag_y.append(price)

# Create a DataFrame to store zigzag points (optional)
zigzag_df = pd.DataFrame({'timestamp': zigzag_x, 'price': zigzag_y})

# Display or use zigzag_df as needed in your backtest
print(zigzag_df)


# Create arrays to store zigzag values
zigzag_prices = [np.nan] * len(df)
zigzag_volumes = [np.nan] * len(df)

# Populate zigzag values in the DataFrame
for i, price, volume in zigzag:
    zigzag_prices[i] = price
    zigzag_volumes[i] = volume

# Add zigzag columns to DataFrame
df['zigzag_price'] = zigzag_prices
#df['zigzag_volume'] = zigzag_volumes

df['zigzag_price'] = df['zigzag_price'].fillna(method='ffill')
df['prev_zigzag'] = df['zigzag_price'].shift(1)
df['prev_zigzag'] = df['prev_zigzag'].where(df['zigzag_price'] != df['prev_zigzag'])
df['prev_zigzag'] = df['prev_zigzag'].fillna(method='ffill')



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
