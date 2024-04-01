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

try:
    with open('stop_loss_triggered.txt', 'r') as file:
        stop_loss_triggered = file.read() == 'True'
except FileNotFoundError:
    stop_loss_triggered = False
print("Stop_loss_triggered is:", stop_loss_triggered)

def open_long(row):
    global stop_loss_triggered
    if stop_loss_triggered:
        if row['buy_signal']:
            return True
        else:
            return False
    else:
        if row['sell_signal']:
            return True
        else:
            return False

def close_long(row):
    global stop_loss_triggered
    if row['STOP LOSS']:
        if row['sell_signal']:
            stop_loss_triggered = True
            return True
        else:
            return False
    if stop_loss_triggered:    
        if row['sell_signal'] or row['close_signal']:
            stop_loss_triggered = False
            return True
        else:
            return False
    else:
        # Logique normale sans le stop loss
        if row['buy_signal'] or row['close_signal']:
            return True
        else:
            return False

def open_short(row):
    global stop_loss_triggered
    if stop_loss_triggered:
        if row['sell_signal']:
            return True
        else:
            return False
    else:
        if row['buy_signal']:
            return True
        else:
            return False

def close_short(row):
    global stop_loss_triggered
    if row['STOP LOSS']:
        if row['buy_signal']:
            stop_loss_triggered = True
            return True
        else:
            return False
    if stop_loss_triggered:
        if row['buy_signal'] or row['close_signal']:
            stop_loss_triggered = False
            return True
        else:
            return False
    else:
        # Logique normale sans le stop loss
        if row['sell_signal'] or row['close_signal']:
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
#df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
#df.at[df.index[0], 'ha_open'] = df.at[df.index[0], 'close']
#for i in range(1, len(df)):
#    df.at[df.index[i], 'ha_open'] = (df.at[df.index[i - 1], 'ha_open'] + df.at[df.index[i - 1], 'ha_close']) / 2
#    df.at[df.index[i], 'ha_high'] = max(df.at[df.index[i], 'high'], df.at[df.index[i], 'ha_open'], df.at[df.index[i], 'ha_close'])
#    df.at[df.index[i], 'ha_low'] = min(df.at[df.index[i], 'low'], df.at[df.index[i], 'ha_open'], df.at[df.index[i], 'ha_close'])

# Calculer les superTrend
ST_length = 21
ST_multiplier = 1.5
superTrend1 = pda.supertrend(df['high'], df['low'], df['close'], length=ST_length, multiplier=ST_multiplier)
df['SUPER_TREND1'] = superTrend1['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
df['SUPER_TREND_DIRECTION1'] = superTrend1['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

def calculate_ema5(data, alpha):
    ema_values = [data.iloc[0]]  # La première valeur de l'EMA est simplement la première valeur de la série
    for i in range(1, len(data)):
        ema = alpha * data.iloc[i] + (1 - alpha) * ema_values[-1]
        ema_values.append(ema)
    return ema_values
alpha = 2 / (5 + 1)  # Calcul du facteur de lissage
df['EMA_5'] = calculate_ema5(df['close'], alpha)

def calculate_ema_direction(ema_values):
    ema_direction = [0]  # Initialise la liste de direction de EMA avec une valeur arbitraire, car la première direction n'est pas définie
    for i in range(1, len(ema_values)):
        if ema_values[i] > ema_values[i-1]:
            ema_direction.append(1)
        elif ema_values[i] < ema_values[i-1]:
            ema_direction.append(-1)
        else:
            ema_direction.append(0)  # Si les valeurs sont égales, on peut mettre 0 ou une autre valeur qui indique qu'il n'y a pas de changement
    return ema_direction

df['EMA_direction'] = calculate_ema_direction(df['EMA_5'])

#ST_length = 14
#ST_multiplier = 2.0
#superTrend2 = pda.supertrend(df['ha_high'], df['ha_low'], df['ha_close'], length=ST_length, multiplier=ST_multiplier)
#df['SUPER_TREND2'] = superTrend2['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
#df['SUPER_TREND_DIRECTION2'] = superTrend2['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

# Calculer les signaux d'achat
df['buy_signal'] = (df['SUPER_TREND_DIRECTION1'] == 1) & (df['EMA_direction'] == 1)

# Calculer les signaux de vente
df['sell_signal'] = (df['SUPER_TREND_DIRECTION1'] == -1) & (df['EMA_direction'] == -1)


# Calculer la EMA2
def calculate_ema2(data, alpha):
    ema_values = [data.iloc[0]]  # La première valeur de l'EMA est simplement la première valeur de la série
    for i in range(1, len(data)):
        ema = alpha * data.iloc[i] + (1 - alpha) * ema_values[-1]
        ema_values.append(ema)
    return ema_values
alpha = 2 / (2 + 1)  # Calcul du facteur de lissage

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")

positions_data = bitget.get_open_position()
position = [
    {"side": d["side"], "size": float(d["contracts"]) * float(d["contractSize"]), "market_price":d["info"]["marketPrice"], "usd_size": float(d["contracts"]) * float(d["contractSize"]) * float(d["info"]["marketPrice"]), "open_price": d["entryPrice"]}
    for d in positions_data if d["symbol"] == pair]

# Ajouter la position
if len(positions_data) == 0:
    df['side'] = None
else :
    current_position = positions_data[0]
    side = current_position['side']
    df['side'] = side

df['EMA_2'] = calculate_ema2(df['close'], alpha)

# Ajouter le Open Price
if len(positions_data) == 0:
    df['entry_price'] = None
else:
    position_info = positions_data[0]
    entry_price = position_info['entryPrice']
    df['entry_price'] = entry_price

percentage_difference = ((df['EMA_2'] - df['entry_price']) / df['entry_price']) * 100
df['1_P'] = (percentage_difference > 1).astype(int)
df.loc[df['side'] == 'short', '1_P'] = (percentage_difference < -1).astype(int)
df['2_P'] = (percentage_difference > 2).astype(int)
df.loc[df['side'] == 'short', '2_P'] = (percentage_difference < -2).astype(int)
df['3_P'] = (percentage_difference > 3).astype(int)
df.loc[df['side'] == 'short', '3_P'] = (percentage_difference < -3).astype(int)
df['4_P'] = (percentage_difference > 4).astype(int)
df.loc[df['side'] == 'short', '4_P'] = (percentage_difference < -4).astype(int)
df['5_P'] = (percentage_difference > 5).astype(int)
df.loc[df['side'] == 'short', '5_P'] = (percentage_difference < -5).astype(int)
df['6_P'] = (percentage_difference > 6).astype(int)
df.loc[df['side'] == 'short', '6_P'] = (percentage_difference < -6).astype(int)
df['7_P'] = (percentage_difference > 7).astype(int)
df.loc[df['side'] == 'short', '7_P'] = (percentage_difference < -7).astype(int)
df['8_P'] = (percentage_difference > 8).astype(int)
df.loc[df['side'] == 'short', '8_P'] = (percentage_difference < -8).astype(int)
df['9_P'] = (percentage_difference > 9).astype(int)
df.loc[df['side'] == 'short', '9_P'] = (percentage_difference < -9).astype(int)
df['10_P'] = (percentage_difference > 10).astype(int)
df.loc[df['side'] == 'short', '10_P'] = (percentage_difference < -10).astype(int)
df['TOTAL_P'] = df[['1_P', '2_P', '3_P', '4_P', '5_P', '6_P', '7_P', '8_P', '9_P', '10_P']].sum(axis=1)
df['close_signal'] = (df['TOTAL_P'].shift(1) > df['TOTAL_P'])

df['1.5_SL'] = (percentage_difference < -0.8).astype(int)
df.loc[df['side'] == 'short', '1.5_SL'] = (percentage_difference > 0.8).astype(int)
df['STOP LOSS'] = df['1.5_SL'] == 1


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
        if production:
            stop_loss_price = long_market_price * 1.005  # 1% sous le prix d'achat
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
            stop_loss_price = short_market_price * 0.995  # 1% au-dessus du prix de vente
            print(f"Place Short Stop Loss Order at {stop_loss_price}$")
            bitget.place_market_stop_loss(pair, 'buy', short_quantity, stop_loss_price, reduce=True)

with open('stop_loss_triggered.txt', 'w') as file:
    file.write(str(stop_loss_triggered))

now = datetime.now()
current_time = now.strftime("%d/%m/%Y %H:%M:%S")
print("--- End Execution Time :", current_time, "---")


