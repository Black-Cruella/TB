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
timeframe = "1m"
leverage = 0.99

print(f"--- {pair} {timeframe} Leverage x {leverage} ---")

type = ["long", "short"]

def open_long(row):
    if row['buy_signal'] and row['signal'] == 'GO':
        return True
    else:
        return False

def close_long(row):
    if row['close_long'] or row['close_signal'] or row['SL_long']:
        return True
    else:
        return False

def open_short(row):
    if row['sell_signal'] and row['signal'] == 'GO':
        return True
    else:
        return False

def close_short(row):
    if row['close_short'] or row['close_signal'] or row['SL_short']:
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

# Calculer les superTrend
ST_length = 21
ST_multiplier = 1.5
superTrend1 = pda.supertrend(df['high'], df['low'], df['close'], length=ST_length, multiplier=ST_multiplier)
df['SUPER_TREND1'] = superTrend1['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
df['SUPER_TREND_DIRECTION1'] = superTrend1['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

ST_length = 30
ST_multiplier = 3.0
superTrend2 = pda.supertrend(df['high'], df['low'], df['close'], length=ST_length, multiplier=ST_multiplier)
df['SUPER_TREND2'] = superTrend2['SUPERT_'+str(ST_length)+"_"+str(ST_multiplier)]
df['SUPER_TREND_DIRECTION2'] = superTrend2['SUPERTd_'+str(ST_length)+"_"+str(ST_multiplier)]

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

def calculate_macd(df, short_window=12, long_window=26, signal_window=9):
    # Calculer les moyennes mobiles exponentielles (EMA)
    short_ema = df['close'].ewm(span=short_window, min_periods=1, adjust=False).mean()
    long_ema = df['close'].ewm(span=long_window, min_periods=1, adjust=False).mean()
    
    # Calculer la différence entre les deux EMA pour obtenir le MACD
    macd = short_ema - long_ema
    
    # Calculer la ligne de signal (EMA du MACD)
    signal_line = macd.ewm(span=signal_window, min_periods=1, adjust=False).mean()
    
    # Calculer l'histogramme MACD (différence entre le MACD et sa ligne de signal)
    macd_histogram = macd - signal_line
    
    return macd, signal_line, macd_histogram

macd, _, _ = calculate_macd(df)
df['MACD'] = macd

def MACD_direction(macd_values):
    macd_direction = [0]  # Initialise la liste de direction de EMA avec une valeur arbitraire, car la première direction n'est pas définie
    for i in range(1, len(macd_values)):
        if macd_values[i] > macd_values[i-1]:
            macd_direction.append(1)
        elif macd_values[i] < macd_values[i-1]:
            macd_direction.append(-1)
        else:
            macd_direction.append(0)  # Si les valeurs sont égales, on peut mettre 0 ou une autre valeur qui indique qu'il n'y a pas de changement
    return macd_direction

df['MACD_direction'] = MACD_direction(macd)

df['buy_signal'] = (df['SUPER_TREND_DIRECTION2'] == 1) & (df['EMA_direction'] == 1) & (df['MACD_direction'] == 1)
df['close_long'] = (df['SUPER_TREND_DIRECTION1'] == -1) & (df['SUPER_TREND_DIRECTION2'] == -1)

df['sell_signal'] = (df['SUPER_TREND_DIRECTION2'] == -1) & (df['EMA_direction'] == -1) & (df['MACD_direction'] == -1)
df['close_short'] = (df['SUPER_TREND_DIRECTION1'] == 1) & (df['SUPER_TREND_DIRECTION2'] == 1)

df['prev_ST1'] = df['SUPER_TREND_DIRECTION1'].shift(1)
df['prev_ST1_2'] = df['SUPER_TREND_DIRECTION1'].shift(2)

position = None  # Initialiser la position à None
def calculate_position(row):
    global position  # Utiliser la variable de position globale

    if row['sell_signal']:  # Si le sell signal est déclenché
        position = 'short'  # Changer la position à short
        return position

    elif row['buy_signal']:  # Si le buy signal est déclenché
        if position == 'short':  # Si la position précédente était short
            position = 'long'  # Changer la position à long
        return position

    else:
        return position  # Retourner la position actuelle
df['position'] = df.apply(calculate_position, axis=1)


prev_position = None  # Initialiser la position précédente à None
def calculate_signal(row):
    global prev_position  # Utiliser la variable de position précédente globale

    if row['position'] != prev_position:  # Si la position actuelle est différente de la position précédente
        prev_position = row['position']  # Mettre à jour la position précédente
        return 'GO'  # Retourner 'GO' pour indiquer un changement de position

    elif ((row['position'] == 'long' and row['buy_signal'] and row['prev_ST1_2'] == -1 and row['prev_ST1'] == -1 and row['SUPER_TREND_DIRECTION1'] == 1) or
        (row['position'] == 'long' and row['buy_signal'] and row['prev_ST1_2'] == -1 and row['prev_ST1'] == 1 and row['SUPER_TREND_DIRECTION1'] == 1)):
        return 'GO'

    elif ((row['position'] == 'short' and row['sell_signal'] and row['prev_ST1_2'] == 1 and row['prev_ST1'] == 1 and row['SUPER_TREND_DIRECTION1'] == -1) or 
        (row['position'] == 'short' and row['sell_signal'] and row['prev_ST1_2'] == 1 and row['prev_ST1'] == -1 and row['SUPER_TREND_DIRECTION1'] == -1): 
        return 'GO'  # Retourner 'GO'
    
    else:
        return 'WAIT'  # Sinon, retourner 'WAIT'
        
df['signal'] = df.apply(calculate_signal, axis=1)

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

# Ajouter le Open Price
if len(positions_data) == 0:
    df['entry_price'] = 0
else:
    position_info = positions_data[0]
    entry_price = position_info['entryPrice']
    df['entry_price'] = entry_price

usd_balance = float(bitget.get_usdt_equity())
print("USD balance :", round(usd_balance, 2), "$")

percentage_difference = ((df['EMA_5'] - df['entry_price']) / df['entry_price']) * 100
df['0.2_P'] = (percentage_difference > 0.2).astype(int)
df.loc[df['side'] == 'short', '0.2_P'] = (percentage_difference < -0.2).astype(int)
df['0.3_P'] = (percentage_difference > 0.3).astype(int)
df.loc[df['side'] == 'short', '0.3_P'] = (percentage_difference < -0.3).astype(int)
df['0.4_P'] = (percentage_difference > 0.4).astype(int)
df.loc[df['side'] == 'short', '0.4_P'] = (percentage_difference < -0.4).astype(int)
df['0.5_P'] = (percentage_difference > 0.5).astype(int)
df.loc[df['side'] == 'short', '0.5_P'] = (percentage_difference < -0.5).astype(int)
df['0.6_P'] = (percentage_difference > 0.6).astype(int)
df.loc[df['side'] == 'short', '0.6_P'] = (percentage_difference < -0.6).astype(int)
df['0.7_P'] = (percentage_difference > 0.7).astype(int)
df.loc[df['side'] == 'short', '0.7_P'] = (percentage_difference < -0.7).astype(int)
df['0.8_P'] = (percentage_difference > 0.8).astype(int)
df.loc[df['side'] == 'short', '0.8_P'] = (percentage_difference < -0.8).astype(int)
df['0.9_P'] = (percentage_difference > 0.9).astype(int)
df.loc[df['side'] == 'short', '0.9_P'] = (percentage_difference < -0.9).astype(int)
df['1_P'] = (percentage_difference > 1).astype(int)
df.loc[df['side'] == 'short', '1_P'] = (percentage_difference < -1).astype(int)
df['TOTAL_P'] = df[['0.2_P', '0.3_P', '0.4_P', '0.5_P', '0.6_P', '0.7_P', '0.8_P', '0.9_P', '1_P']].sum(axis=1)
df['close_signal'] = (df['TOTAL_P'].shift(1) > df['TOTAL_P'])

df['SL_long'] = (df['EMA_direction'] == -1) & (df['MACD_direction'] == -1) & (df['close'] < df['entry_price'])
df['SL_short'] = (df['EMA_direction'] == 1) & (df['MACD_direction'] == 1) & (df['close'] > df['entry_price'])

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


