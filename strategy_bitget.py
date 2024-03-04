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



# Afficher le DataFrame des bougies Heikin Ashi
print(ha_df)
