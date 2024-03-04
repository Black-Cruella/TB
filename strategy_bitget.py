import sys
sys.path.append("./live_tools")
import ccxt
import ta
from perp_bitget import PerpBitget
import pandas_ta as pda 
import pandas as pd
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


balance = float(bitget.get_usdt_equity())
balance = balance * leverage
print(f"Balance: {round(balance, 2)} $", )

print(ha_df)

position = None

for i, row in ha_df.iterrows():
    row = ha_df.iloc[-2]  # Récupération des données de l'avant-dernière bougie
    # Check for a buy signal and if not already in a position
    if row['buy_signal'] and position is None:
        print(f"Buy signal at index {i}")
        order_size = balance 
        bitget.place_market_order('AVAX/USDT', 'buy', order_size)
        position = {'type': 'buy', 'size': order_size}
        print(f"Opened a long position with size: {order_size}")

    # Check for a sell signal and if currently in a long position
    elif row['sell_signal'] and position is not None and position['type'] == 'buy':
        print(f"Sell signal at index {i}")
        bitget.place_market_order('AVAX/USDT', 'sell', position['size'])
        position = None
        print("Closed the long position")

    # Check for a sell signal and if not already in a position
    elif row['sell_signal'] and position is None:
        print(f"Sell signal at index {i}")
        order_size = balance 
        bitget.place_market_order('AVAX/USDT', 'sell', order_size)
        position = {'type': 'sell', 'size': order_size}
        print(f"Opened a short position with size: {order_size}")

    # Check for a buy signal and if currently in a short position
    elif row['buy_signal'] and position is not None and position['type'] == 'sell':
        print(f"Buy signal at index {i}")
        bitget.place_market_order('AVAX/USDT', 'buy', position['size'])
        position = None
        print("Closed the short position")


# Afficher le DataFrame des bougies Heikin Ashi

