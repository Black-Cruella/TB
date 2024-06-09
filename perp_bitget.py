import ccxt
import pandas as pd
import time
from multiprocessing.pool import ThreadPool as Pool
import numpy as np

class PerpBitget():
    def __init__(self, apiKey=None, secret=None, password=None):
        bitget_auth_object = {
            "apiKey": apiKey,
            "secret": secret,
            "password": password,
            'options': {
            'defaultType': 'swap',
        }
        }
        if bitget_auth_object['secret'] == None:
            self._auth = False
            self._session = ccxt.bitget()
        else:
            self._auth = True
            self._session = ccxt.bitget(bitget_auth_object)
        self.market = self._session.load_markets()

    def authentication_required(fn):
        """Annotation for methods that require auth."""
        def wrapped(self, *args, **kwargs):
            if not self._auth:
                # print("You must be authenticated to use this method", fn)
                raise Exception("You must be authenticated to use this method")
            else:
                return fn(self, *args, **kwargs)
        return wrapped

    def get_last_historical(self, symbol, timeframe, limit):
        result = pd.DataFrame(data=self._session.fetch_ohlcv(
            symbol, timeframe, None, limit=limit))
        result = result.rename(
            columns={0: 'timestamp', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'})
        result = result.set_index(result['timestamp'])
        result.index = pd.to_datetime(result.index, unit='ms')
        del result['timestamp']
        return result

    def get_more_last_historical_async(self, symbol, timeframe, limit):
        max_threads = 4
        pool_size = round(limit/100)  # your "parallelness"

        # define worker function before a Pool is instantiated
        full_result = []
        def worker(i):
            
            try:
                return self._session.fetch_ohlcv(
                symbol, timeframe, round(time.time() * 1000) - (i*1000*60*60), limit=100)
            except Exception as err:
                raise Exception("Error on last historical on " + symbol + ": " + str(err))

        pool = Pool(max_threads)

        full_result = pool.map(worker,range(limit, 0, -100))
        full_result = np.array(full_result).reshape(-1,6)
        result = pd.DataFrame(data=full_result)
        result = result.rename(
            columns={0: 'timestamp', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'})
        result = result.set_index(result['timestamp'])
        result.index = pd.to_datetime(result.index, unit='ms')
        del result['timestamp']
        return result.sort_index()

    def get_bid_ask_price(self, symbol):
        try:
            ticker = self._session.fetchTicker(symbol)
        except BaseException as err:
            raise Exception(err)
        return {"bid":ticker["bid"],"ask":ticker["ask"]}

    def get_min_order_amount(self, symbol):
        return self._session.markets_by_id[symbol]["info"]["minProvideSize"]

    def convert_amount_to_precision(self, symbol, amount):
        return self._session.amount_to_precision(symbol, amount)

    def convert_price_to_precision(self, symbol, price):
        return self._session.price_to_precision(symbol, price)

    @authentication_required
    def place_limit_order(self, symbol, side, amount, price, reduce=False):
        try:
            return self._session.createOrder(
                symbol, 
                'limit', 
                side, 
                self.convert_amount_to_precision(symbol, amount), 
                self.convert_price_to_precision(symbol, price),
                params={"reduceOnly": reduce}
            )
        except BaseException as err:
            raise Exception(err)

    @authentication_required
    def place_limit_stop_loss(self, symbol, side, amount, trigger_price, price, reduce=False):
        
        try:
            return self._session.createOrder(
                symbol, 
                'limit', 
                side, 
                self.convert_amount_to_precision(symbol, amount), 
                self.convert_price_to_precision(symbol, price),
                params = {
                    'stopPrice': self.convert_price_to_precision(symbol, trigger_price),  # your stop price
                    "triggerType": "market_price",
                    "reduceOnly": reduce
                }
            )
        except BaseException as err:
            raise Exception(err)

    @authentication_required
    def place_market_order(self, symbol, side, amount, reduce=False):
        try:
            return self._session.createOrder(
                symbol, 
                'market', 
                side, 
                self.convert_amount_to_precision(symbol, amount),
                None,
                params={"reduceOnly": reduce}
            )
        except BaseException as err:
            raise Exception(err)

    @authentication_required
    def place_market_stop_loss(self, symbol, side, amount, trigger_price, reduce=False):
        
        try:
            return self._session.createOrder(
                symbol, 
                'market', 
                side, 
                self.convert_amount_to_precision(symbol, amount), 
                self.convert_price_to_precision(symbol, trigger_price),
                params = {
                    'stopPrice': self.convert_price_to_precision(symbol, trigger_price),  # your stop price
                    "triggerType": "market_price",
                    "reduceOnly": reduce
                }
            )
        except BaseException as err:
            raise Exception(err)

    @authentication_required
    def place_trailing_stop2(self, symbol, side, amount, trailingTriggerPrice, range_rate, reduce=True):
        """
        Place a trailing stop order to close an existing position.
    
        :param str symbol: Trading pair symbol (e.g., 'BTC/USDT')
        :param str side: Order side ('buy' to close a short, 'sell' to close a long)
        :param float amount: Amount to close
        :param float trailingTriggerPrice: The price at which the trailing stop should be triggered
        :param float range_rate: The trailing percentage
        :param bool reduce: If the order should be reduce-only (default is True)
        :return: Response from the order placement API
        :rtype: dict
        """
        try:
            # Fetch current positions
            positions = self._session.fetch_positions()
            
            # Debug: print the positions to inspect their structure
            print(f"Positions: {positions}")
    
            # Find the position for the given symbol
            position = next((pos for pos in positions if pos['symbol'] == symbol), None)
            
            # Debug: print the position to inspect its structure
            print(f"Position for {symbol}: {position}")
            
            if not position or 'contracts' not in position or float(position['contracts']) < amount:
                raise Exception(f"No sufficient position to close for {symbol}. Required: {amount}, Available: {position['contracts'] if position else 0}")
    
            # Convert amounts and prices to the appropriate precision
            amount_precision = self.convert_amount_to_precision(symbol, amount)
            trailing_trigger_price_precision = self.convert_price_to_precision(symbol, trailingTriggerPrice)
            range_rate_precision = self.convert_price_to_precision(symbol, range_rate)
    
            # Log the converted values
            print(f"Amount (precision): {amount_precision}")
            print(f"Trailing Trigger Price (precision): {trailing_trigger_price_precision}")
            print(f"Range Rate (precision): {range_rate_precision}")
    
            # Prepare the order parameters
            params = {
                'trailingTriggerPrice': trailing_trigger_price_precision,
                'rangeRate': range_rate_precision,
                'triggerType': 'market_price',
                'reduceOnly': reduce  # Ensure the order is to reduce the position
            }
    
            # Log the params
            print(f"Params: {params}")
    
            # Place the trailing stop order
            return self._session.createOrder(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount_precision,
                params=params
            )
        except Exception as err:
            raise Exception(f"An error occurred while placing the trailing stop order: {err}")

    @authentication_required
    def place_trailing_stop(self, symbol, side, amount, trailingTriggerPrice, range_rate, reduce=False):
          try:
            return self._session.createOrder(
                symbol, 
                'market', 
                side, 
                self.convert_amount_to_precision(symbol, amount), 
                self.convert_price_to_precision(symbol, trailingTriggerPrice),
                params = {
                    'trailingPercent': range_rate,  
                    "triggerType": "market_price",
                    "reduceOnly": reduce
                }
            )
        except BaseException as err:
            raise Exception(err)      

    @authentication_required
    def get_balance_of_one_coin(self, coin):
        try:
            allBalance = self._session.fetchBalance()
        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return allBalance['total'][coin]
        except:
            return 0

    @authentication_required
    def get_all_balance(self):
        try:
            allBalance = self._session.fetchBalance()
        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return allBalance
        except:
            return 0

    @authentication_required
    def get_usdt_equity(self):
        try:
            usdt_equity = self._session.fetchBalance()["info"][0]["usdtEquity"]
        except BaseException as err:
            raise Exception("An error occured", err)
        try:
            return usdt_equity
        except:
            return 0

    @authentication_required
    def get_open_order(self, symbol, conditionnal=False):
        try:
            return self._session.fetchOpenOrders(symbol, params={'stop': conditionnal})
        except BaseException as err:
            raise Exception("An error occured", err)

    @authentication_required
    def get_my_orders(self, symbol):
        try:
            return self._session.fetch_orders(symbol)
        except BaseException as err:
            raise Exception("An error occured", err)

    @authentication_required
    def get_open_position(self,symbol=None):
        try:
            positions = self._session.fetchPositions(params = {
                    "productType": "umcbl",
                })
            truePositions = []
            for position in positions:
                if float(position['contracts']) > 0 and (symbol is None or position['symbol'] == symbol):
                    truePositions.append(position)
            return truePositions
        except BaseException as err:
            raise Exception("An error occured in get_open_position", err)

    @authentication_required
    def cancel_order_by_id(self, id, symbol, conditionnal=False):
        try:
            if conditionnal:
                return self._session.cancel_order(id, symbol, params={'stop': True, "planType": "normal_plan"})
            else:
                return self._session.cancel_order(id, symbol)
        except BaseException as err:
            raise Exception("An error occured in cancel_order_by_id", err)
        
    @authentication_required
    def cancel_all_open_order(self):
        try:
            return self._session.cancel_all_orders(
                params = {
                    "marginCoin": "USDT",
                }
            )
        except BaseException as err:
            raise Exception("An error occured in cancel_all_open_order", err)
        
    @authentication_required
    def cancel_order_ids(self, ids=[], symbol=None):
        try:
            return self._session.cancel_orders(
                ids=ids,
                symbol=symbol,
                params = {
                    "marginCoin": "USDT",
                }
            )
        except BaseException as err:
            raise Exception("An error occured in cancel_order_ids", err)

