import pandas_market_calendars as mcal
import json
import datetime
import pika
import uuid
import numpy as np
import os

from flask import Flask, request, jsonify
from flask_cors import CORS
from curl_cffi.requests.exceptions import HTTPError
from pika import PlainCredentials
from optiontrader.database import Database
from optiontrader.util import validate_date
from optiontrader.datasource  import yahoofinance
from optiontrader.constants import (
    SecurityType,
    OrderType
)
from optiontrader.exceptions import (
    DBConnectionException
)
from optiontrader.rpc import RPCMessage, RPCRequestType
from optiontrader.logging_config import setup_logging

setup_logging(log_level="INFO")

RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_PORT = os.getenv('RABBITMQ_PORT')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')
RABBITMQ_USER= os.getenv('RABBITMQ_USER')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST')



class RPCClient(object):

        def __init__(self):

            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host= RABBITMQ_HOST,
                                                                                port = RABBITMQ_PORT,
                                                                                virtual_host = RABBITMQ_VHOST,
                                                                                credentials=PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)))
            self.channel = self.connection.channel()
            result = self.channel.queue_declare(queue='', exclusive=True)
            self.callback_queue = result.method.queue

            self.channel.basic_consume(
                queue=self.callback_queue,
                on_message_callback=self.on_response,
                auto_ack=True)

            self.response = None
            self.corr_id = None

        def on_response(self, ch, method, props, body):
            if self.corr_id == props.correlation_id:
                self.response = body

        def call(self, message):
            self.response = None
            self.corr_id = str(uuid.uuid4())
            self.channel.basic_publish(
                exchange='',
                routing_key=RABBITMQ_QUEUE,
                properties=pika.BasicProperties(
                    reply_to=self.callback_queue,
                    correlation_id=self.corr_id,
                    delivery_mode=pika.DeliveryMode.Transient
                ),
                body=message)
            while self.response is None:
                self.connection.process_data_events(time_limit=None)
            
            self.connection.close()
            return self.response
        
class APIError(Exception):
    status_code: int
    message: str

class BadRequestError(APIError):
    status_code = 400
    def __init__(self, message, status_code=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code

def create_app(name) -> Flask:

    app = Flask(name)

    CORS(app,resources=r'/api/*')
    CORS(app,resources=r'/streams/*')
    
    @app.errorhandler(BadRequestError)
    def handle_invalid_usage(error):
        response = jsonify({"message": error.message, "status": error.status_code})
        return response, error.status_code

    @app.route('/api', methods=['GET'])
    def hello_world():

        return 'hello world'

    @app.route('/api/price/last', methods=['GET'])
    def get_last_price():

        symbol = request.args.get('symbol')
    
        if symbol == None:
            raise BadRequestError('symbol must be provided')
        
        symbol = symbol.upper()

        try:
            df = yahoofinance.get_price_history(symbol=symbol,interval='5m')
            df['timestamp'] = df.index.astype('int64') // 10**9
            data = df.iloc[-1][['timestamp','close']].to_dict()
    
        except HTTPError:
            raise BadRequestError('Yfinance error, possibly invalid symbol')
        except ValueError:
            raise BadRequestError('Yfinance error, possibly invalid interval/date')
        
        return jsonify(data), 200
    
    @app.route('/api/option_expiry', methods=['GET'])
    def get_option_expiry():
        """
        Get list of expiry dates
        """
        symbol = request.args.get('symbol')

        if symbol == None:
            raise BadRequestError('Missing symbol')
        
        option_expiry = yahoofinance.get_option_expiry(symbol=symbol)
        data = list(option_expiry)

        return data, 200
    
    @app.route('/api/option_chain', methods=['GET'])
    def get_option_chain():
        """
        Get option chain from Yahoo Finance
        """
        symbol = request.args.get('symbol')
        expiry = request.args.get('expiry')

        if symbol == None or expiry == None:
            raise BadRequestError('Missing symbol and/or expiry')

        try:
            validate_date(expiry)
        except ValueError:
            raise BadRequestError('Expiry is in wrong format (YYYY-MM-DD)')
        
        try:
            df = yahoofinance.get_option_price(symbol = symbol,
                                               expiry = expiry,
                                               range = 10,
                                               join = True)

        except ValueError:
            raise BadRequestError('Wrong symbol/expiry')

        result = df.to_json(orient='table', date_format='iso', date_unit='s')
        data = json.loads(result)
        
        return data

    @app.route('/api/volatility/historical', methods=['GET'])
    def get_historical_volatility():
        """
        Get historical volatility for a symbol
        """
        symbol = request.args.get('symbol')
        history = request.args.get('history')
       
        request_body = {
            'symbol' : symbol,
            'history' : history
        }

        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.VOLATILITY_HISTORY,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response

    
    @app.route('/api/volatility/forecast', methods=['GET'])
    def get_volatility_forecast():
        """
        Get volatility forecast for a symbol
        """
        horizon = request.args.get('horizon')
        if horizon == None:
            raise BadRequestError('Horizon must be provided')
        
        request_body = {'horizon':horizon}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.VOLATILITY_FORECAST,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response
    
    # @app.route('/api/analysis/bsm_iv', methods=['POST'])
    # def BSM_iv():
    #     """
    #     Compute IV based on BSM
    #     Input: OptionLegs[], current price
    #     """
    #     data = request.get_json()

    #     s = data['curr_price']
    #     result = []
    #     for leg in data['legs']:
    #         price = leg['price']
    #         k = leg['strike']
    #         t = get_time_to_expiry(leg['expiry'])
    #         r = RISK_FREE_INTEREST_RATE
    #         flag = [leg['right']]
    #         iv = py_vollib.black_scholes_merton.implied_volatility.implied_volatility(price, s, k, t, r, flag, q=0, return_as='numpy')[0]
    #         result.append(iv)

    #     return result
    

    # @app.route('/api/analysis/bsm_ev_monte_carlo', methods=['POST'])
    # def BSM_ev_monte_carlo():
    #     """
    #     Compute EV of option spreads by simulating BSM with Monte Carlo method
    #     Input: OptionLegs[], current price, expected volatility
    #     """
    #     data = request.get_json()

    #     curr = data['curr_price']
    #     expiry = data['expiry']
    #     legs = data['legs']
    #     volatility = data['volatility']
    #     steps = data['steps'] if 'steps' in data else None

    #     ev = mathtools.BSM_ev_monte_carlo(legs=legs,
    #                                  volatility=volatility,
    #                                  initial_price=curr,
    #                                  expiry=expiry,
    #                                  steps=steps)

    #     result = str(ev)
    #     return result

    # @app.route('/api/analysis/bsm_greeks', methods=['POST'])
    # def BSM_greeks():

    #     data = request.get_json()
    #     curr_price = data['curr_price']
    #     expiry = data['expiry']
    #     legs = data['legs']
    #     volatility = data['volatility']
        
    #     greeks = []

    #     for leg in legs:
    #         if leg['right'] == 'call' or leg['right'] == 'Call' or leg['right'] == 'c':
    #             leg['right'] = 'c'
    #         else:
    #             leg['right'] = 'p'
            
    #         greek_curr = mathtools.BSM_greeks(leg =  leg,
    #                                       volatility = volatility,
    #                                       curr_price = curr_price,
    #                                       expiry = expiry)
    #         greeks.append(greek_curr)
        
 
    #     return greeks

    @app.route('/api/ib/account', methods=['GET'])
    def ib_get_account_info():

        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.ACCOUNT,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response
    
    @app.route('/api/ib/account_values', methods=['GET'])
    def ib_get_account_values():

        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.ACCOUNT_VALUES,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response
            
    
    @app.route('/api/ib/portfolio', methods=['GET'])
    def ib_get_portifolio():

        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.PORTFOLIO,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response
    
    @app.route('/api/ib/open_orders', methods=['GET'])
    def ib_get_open_orders():

        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.OPEN_ORDERS,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)        
    
        return response
    
    @app.route('/api/ib/completed_orders', methods=['GET'])
    def ib_get_completed_orders():

        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.COMPLETED_ORDERS,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)        
    
        return response    
    
    @app.route('/api/ib/option_chain' , methods=['GET'])
    def ib_get_option_chain():

        symbol = request.args.get('symbol')
        expiry = request.args.get('expiry')

        if symbol == None or expiry == None:
            raise BadRequestError('Symbol and Expiry must be provided')
        
        try:
            validate_date(expiry)
        except ValueError:
            raise BadRequestError('Expiry is in wrong format (YYYY-MM-DD)')
        
        request_body = {
            'symbol': symbol,
            'expiry': expiry
        }

        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.OPTION_CHAIN,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response

    @app.route('/api/ib/ticks', methods=['GET'])
    def ib_get_ticks():
        request_data = request.get_json()
        if 'security_type' not in request_data:
            raise BadRequestError('Security_type must be provided')

        security_type = request_data['security_type']

        if security_type == SecurityType.OPTION_SPREAD:
            if 'legs' not in request_data:
                raise BadRequestError('legs must be provided for option')
            
            legs = request_data['legs']
            symbol = request_data['symbol']
            request_body = {
                'security_type': security_type,
                'symbol': symbol,
                'legs': legs
            }

        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.TICKS,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response
    
    @app.route('/api/ib/order', methods=['POST'])
    def ib_place_order():

        request_data = request.get_json()
        if 'security_type' not in request_data or 'order_type' not in request_data or 'action' not in request_data or 'quantity' not in request_data:
            raise BadRequestError('At least 1 is missing from: security_type, order_type, action, quantity')
        
        security_type = request_data['security_type']
        order_type = request_data['order_type']
        if order_type == OrderType.LIMIT:
            if 'price' not in request_data:
                raise BadRequestError('Price must be provided for limit order')
            price = request_data['price']
            
        if security_type == SecurityType.STOCK or security_type == SecurityType.ETF:
            if 'symbol' not in request_data:
                raise BadRequestError('symbol is missing')
            symbol = request_data['symbol']
            action = request_data['action']
            quantity = request_data['quantity']
            request_body = {
                'symbol': symbol,
                'action': action,
                'security_type': security_type,
                'order_type': order_type,
                'quantity': quantity
            }

        elif security_type == SecurityType.OPTION:
            if 'con_id' not in request_data:
               raise BadRequestError('con_id must be provided for option')
            con_id = request_data['con_id']
            request_body = {
                'con_id': con_id,
                'action': action,
                'security_type': security_type,
                'order_type': order_type,
                'quantity': quantity
            }

        elif security_type == SecurityType.OPTION_SPREAD:
            if 'legs' not in request_data:
                raise BadRequestError('legs must be provided for option')
            
            legs = request_data['legs']
            symbol = request_data['symbol']
            spread_type= request_data['spread_type']
            action = request_data['action']
            quantity = request_data['quantity']
            request_body = {
                'symbol': symbol,
                'security_type': security_type,
                'spread_type': spread_type,
                'order_type': order_type,
                'action': action,
                'quantity': quantity,
                'legs': legs
            }

        if order_type == OrderType.LIMIT:
            request_body['price'] = price

        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.ORDER,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        if 'error' in response:
            raise BadRequestError(response['error'])
        
        return response
    
    @app.route('/api/ib/cancel_order', methods=['POST'])
    def ib_cancel_order():

        request_data = request.get_json()
        if 'broker_order_id' not in request_data or 'security_type' not in request_data: 
            raise BadRequestError('Broker Order ID and Security Type must be provided')
        
        request_body = {
            'broker_order_id': request_data['broker_order_id'],
            'security_type': request_data['security_type'],
        }

        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.CANCEL_ORDER,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        if 'error' in response:
            raise BadRequestError(response['error'])
        
        return response
        
    @app.route('/api/screener/profitable_spreads', methods=['GET'])
    def get_profitable_spreads():
        """
        Get profitable spreads and related data from screener
        """
        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.PROFITABLE_SPREADS,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response

    @app.route('/api/screener/term_structure', methods=['GET'])
    def get_term_structure():
        """
        Get term structure
        """
        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.TERM_STRUCTURE,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response
    
    @app.route('/api/screener/net_gex', methods=['GET'])
    def get_net_gex():
        """
        Get net Gamma Exposure
        """
        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.GEX,request_body)
        data = client.call(rpc_request.to_json())
        response = json.loads(data)

        return response

    @app.route('/api/screener/volatility_surface', methods=['GET'])
    def get_volatility_surface():
        """
        Get volatility surface
        """
        request_body = {}
        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.VOLATILITY_SURFACE,request_body)
        response_data = client.call(rpc_request.to_json())
        response = json.loads(response_data)
        iv = response['iv']
        iv = np.round(iv,decimals=4).tolist()
        response['iv'] = iv

        return response

    @app.route('/api/screener/option_chain_iv', methods=['GET'])
    def get_option_chain_iv():
        """
        Get raw iv for a option chain
        """
        expiry = request.args.get('expiry')
        if expiry is None: 
            raise BadRequestError('Expiry must be provided')
        
        request_body = {
            'expiry': expiry
        }

        client = RPCClient()
        rpc_request = RPCMessage(RPCRequestType.OPTION_CHAIN_IV,request_body)
        response_data = client.call(rpc_request.to_json())
        response = json.loads(response_data)
        
        return response
    
    @app.route('/api/util/market_schedule', methods=['GET'])
    def get_market_schedule():
        exchange = mcal.get_calendar('NYSE')
        schedule = exchange.schedule(start_date=datetime.date.today()-datetime.timedelta(days=10), end_date=datetime.date.today()+datetime.timedelta(days=10))
        schedule['market_open_unix'] =schedule['market_open'].dt.tz_convert('UTC').astype('int64') // 10**6
        schedule['market_close_unix'] =schedule['market_close'].dt.tz_convert('UTC').astype('int64') // 10**6
        data = schedule[['market_open_unix','market_close_unix']].values.tolist()

        return data

    return app