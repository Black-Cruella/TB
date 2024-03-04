import sys
sys.path.append("./TB")
from perp_bitget import PerpBitget
import pandas_ta as pda 
import pandas as pd
import json

account_to_select = "bitget_exemple"
production = True

pair = "AVAX/USDT"
leverage = 1

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

pd.set_option('display.max_rows', None)
print(ha_df)

# Récupération des positions ouvertes
positions_data = bitget.get_open_position(pair)
position = [
    {"side": d["side"], "size": float(d["volume"]), "entry_price": d["entry_price"]}
    for d in positions_data if d["symbol"] == pair]

# Boucle principale pour exécuter la stratégie de trading
for i, row in ha_df.iterrows():
    # Si une position est ouverte, vérifier les conditions de clôture
    if position:
        position = position[0]  # Sélection de la première position

        # Si la position est longue et les conditions de clôture longue sont remplies
        if position["side"] == "long" and row['sell_signal']:
            print(f"Sell signal at index {i}, closing the long position")
            bitget.place_market_order(pair, 'sell', position['size'])
            position = None

        # Si la position est courte et les conditions de clôture courte sont remplies
        elif position["side"] == "short" and row['buy_signal']:
            print(f"Buy signal at index {i}, closing the short position")
            bitget.place_market_order(pair, 'buy', position['size'])
            position = None

    # Si aucune position n'est ouverte, vérifier les conditions d'ouverture
    else:
        # Si les conditions d'ouverture longue sont remplies
        if row['buy_signal']:
            print(f"Buy signal at index {i}, opening a long position")
            order_size = balance 
            bitget.place_market_order(pair, 'buy', order_size)
            position = {'type': 'long', 'size': order_size}
            print(f"Opened a long position with size: {order_size}")

            # Placement du stop-loss pour la position longue
            stop_loss_price = row['close'] * 0.995  # 0.5% sous le prix d'achat
            bitget.place_limit_stop_loss(pair, 'sell', order_size, stop_loss_price, stop_loss_price, reduce=True)
            print(f"Stop loss placed for long position at {stop_loss_price}")

        # Si les conditions d'ouverture courte sont remplies
        elif row['sell_signal']:
            print(f"Sell signal at index {i}, opening a short position")
            order_size = balance 
            bitget.place_market_order(pair, 'sell', order_size)
            position = {'type': 'short', 'size': order_size}
            print(f"Opened a short position with size: {order_size}")

            # Placement du stop-loss pour la position courte
            stop_loss_price = row['close'] * 1.005  # 0.5% au-dessus du prix de vente
            bitget.place_limit_stop_loss(pair, 'buy', order_size, stop_loss_price, stop_loss_price, reduce=True)
            print(f"Stop loss placed for short position at {stop_loss_price}")

# Vérification des positions restantes
if position:
    print("Remaining position:", position)
else:
    print("No active position")
