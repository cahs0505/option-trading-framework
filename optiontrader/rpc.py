import json
import time
import datetime
import os
from decimal import Decimal
from enum import StrEnum
from dataclasses import dataclass
from typing import Dict, List, Tuple
from pika import (
    BlockingConnection,
    ConnectionParameters,
    BasicProperties,
    DeliveryMode,
    PlainCredentials
)
from pika.channel import Channel
from pika.spec import Basic, BasicProperties
from pika.exceptions import ChannelClosed, ChannelWrongStateError, ConnectionWrongStateError

from optiontrader.IBKRClient.ib import IB
from optiontrader.database import Database
from optiontrader.IBKRClient.contracts import IBContract
from optiontrader.IBKRClient.requests import (
    RequestStatus,
    ContractDetailRequest,
    MarketDataRequest
)
from optiontrader.IBKRClient.exceptions import IBDisconnectedException, IBOrderExcepton
from optiontrader.constants import (
    SecurityType,
    OptionSpread,
    OrderType,
    OptionRight,
    Action,
    Broker
)
from optiontrader.logger import logger
from optiontrader.screener import Screener
from optiontrader.forecast import ForecastEngine
from optiontrader.order_management import OrderManager
from optiontrader.orders import (EquityOrder, SpreadOrder, OptionLeg)
SPREAD_TYPE_MAP = {
    'IRON_CONDOR': OptionSpread.IRON_CONDOR
} 
ORDER_TYPE_MAP = {
    'LMT' : OrderType.LIMIT,
    'MKT' : OrderType.MARKET,
    'MID' : OrderType.MID
}

SECURITY_TYPE_MAP = {
    'OPTION_SPREAD' : SecurityType.OPTION_SPREAD,
    'STOCK': SecurityType.STOCK,
    'ETF': SecurityType.ETF
}
OPTION_RIGHT_MAP = {
    'CALL' : OptionRight.CALL,
    'PUT': OptionRight.PUT
}
ACTION_MAP = {
    'BUY' : Action.BUY,
    'SELL' : Action.SELL
}

class RPCRequestType(StrEnum):
    ACCOUNT = 'ACCOUNT'
    ACCOUNT_VALUES = 'ACCOUNT_VALUES'
    PORTFOLIO = 'PORTFOLIO'
    OPEN_ORDERS = 'OPEN_ORDERS'
    COMPLETED_ORDERS = 'COMPLETED_ORDERS'
    OPTION_CHAIN = 'OPTION_CHAIN'
    TICKS = 'TICKS'
    ORDER = 'ORDER'
    CANCEL_ORDER = 'CANCEL_ORDER'
    PROFITABLE_SPREADS = 'PROFITABLE_SPREADS'
    TERM_STRUCTURE = 'TERM_STRUCTURE'
    GEX = 'GEX'
    VOLATILITY_FORECAST = 'VOLATILITY_FORECAST'
    VOLATILITY_HISTORY = 'VOLATILITY_HISTORY'
    VOLATILITY_SURFACE = 'VOLATILITY_SURFACE'
    OPTION_CHAIN_IV = 'OPTION_CHAIN_IV'


ib_disconnected_response = json.dumps({
    'error': 'IB Disconnected',
})
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_PORT = os.getenv('RABBITMQ_PORT')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE')
RABBITMQ_USER= os.getenv('RABBITMQ_USER')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS')
RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST')

@dataclass
class RPCMessage:
     
    request_type : RPCRequestType
    request_body: Dict

    def to_json(self):
        data = self.__dict__
        json_string = json.dumps(data)
        return json_string
    
class RPCServer:
    """
    RPC Server, using pika and RabbitMQ.
    Used to communiate with flask server 
    """
    ib: IB
    db: Database
    screener: Screener
    forecast_engine: ForecastEngine
    oms: OrderManager
    connection: BlockingConnection
    host: str
    queue_name: str
    exchange: str
    active: bool

    def __init__(self, ib: IB, db: Database, screener: Screener, forecast_engine: ForecastEngine, oms: OrderManager):
        self.host = RABBITMQ_HOST
        self.queue_name = RABBITMQ_QUEUE
        self.exchange = ''
        self.ib = ib
        self.db = db
        self.forecast_engine = forecast_engine
        self.oms = oms
        self.screener = screener
        self.connection = BlockingConnection(ConnectionParameters(host= RABBITMQ_HOST,
                                                                  port = RABBITMQ_PORT,
                                                                #   virtual_host = RABBITMQ_VHOST,
                                                                  credentials=PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True, arguments={'x-queue-type': 'quorum'})
        
    def on_request(self, 
                   ch: Channel, 
                   method: Basic.Deliver, 
                   props: BasicProperties, 
                   body: bytes):

        if not self.ib.is_connected():
            response = ib_disconnected_response
        
        else:
            req = json.loads(body)
            req = RPCMessage(**req)
            match req.request_type:
                case RPCRequestType.ACCOUNT:
                    response = self.handle_account_request()
                case RPCRequestType.ACCOUNT_VALUES:
                    response = self.handle_account_values_request()
                case RPCRequestType.PORTFOLIO:
                    response = self.handle_portfolio_request()
                case RPCRequestType.OPEN_ORDERS:
                    response = self.handle_open_orders_request()
                case RPCRequestType.COMPLETED_ORDERS:
                    response = self.handle_completed_orders_request()                
                case RPCRequestType.OPTION_CHAIN:
                    response = self.handle_option_chain_request(req.request_body)
                case RPCRequestType.TICKS:
                    response = self.handle_ticks_request(req.request_body)
                case RPCRequestType.ORDER:
                    response = self.handle_order_request(req.request_body)
                case RPCRequestType.CANCEL_ORDER:
                    response = self.handle_cancel_order_request(req.request_body)
                case RPCRequestType.PROFITABLE_SPREADS:
                    response = self.handle_profitable_spreads_request()
                case RPCRequestType.TERM_STRUCTURE:
                    response = self.handle_term_structure_request()
                case RPCRequestType.GEX:
                    response = self.handle_gex_request()
                case RPCRequestType.VOLATILITY_FORECAST:
                    response = self.handle_volatility_forecast_request(req.request_body)
                case RPCRequestType.VOLATILITY_HISTORY:
                    response = self.handle_volatility_history_request(req.request_body) 
                case RPCRequestType.VOLATILITY_SURFACE:
                    response = self.handle_volatility_surface_request()
                case RPCRequestType.OPTION_CHAIN_IV:
                    response = self.handle_option_chain_iv_request(req.request_body)

        ch.basic_publish(
            exchange = self.exchange,
            routing_key = props.reply_to,
            properties = BasicProperties(
                correlation_id = props.correlation_id,
                delivery_mode = DeliveryMode.Transient
            ),
            body = response
        )
        ch.basic_ack(delivery_tag = method.delivery_tag)

    def close(self):
        try:
            self.channel.stop_consuming()
            self.channel.close()
            self.connection.close()
        except (ChannelWrongStateError, ConnectionWrongStateError):
            logger.error('Unexpected error when shutting down RPC server') 

    def handle_account_request(self) -> str:
        """
        Account request handler
        """
        if not self.ib.is_connected():
            return ib_disconnected_response
            
        data = self.ib.account_data.get_account_summary_json()

        return data
    def handle_account_values_request(self) -> str:
        """
        Account values request handler
        """
        try:

            raw_data : List[Tuple[datetime.datetime, Decimal]] = self.db.get_ib_account_records(columns = ['time','net_liquidation'])
            data = []
            for time, acc_val in raw_data:
                data.append([
                    int(time.timestamp()),
                    str(acc_val)
                ])
      
            return json.dumps(data)
        except Exception as e:
            return json.dumps({
                'error': e
            })
    
    def handle_portfolio_request(self) -> str:
        """
        Portfolio request handler
        """
        if not self.ib.is_connected():
            return ib_disconnected_response
        
        data = self.ib.account_data.get_portfolio_json()
  
        return data
    
    def handle_open_orders_request(self) -> str:
        """
        Open order request handler
        """
        if not self.ib.is_connected():
            return ib_disconnected_response
                
        data = self.oms.get_open_orders()
        response_data = []
        for id,order in data.items():
            response_data.append(order.get_data_dict(stringify=True))

        response_json = json.dumps(response_data)
        return response_json
    
    def handle_completed_orders_request(self) -> str:
        """
        Completed order request handler
        """
        if not self.ib.is_connected():
            return ib_disconnected_response
                
        data = self.oms.get_completed_orders()
        response_data = []
        for id,order in data.items():
            response_data.append(order.get_data_dict(stringify=True))
        
        response_json = json.dumps(response_data)
        return response_json    
    
    def handle_option_chain_request(self, request_body) -> str:
        """
        IB Option chain request handler
        """
        symbol = request_body['symbol']
        expiry = request_body['expiry']

        if symbol is None or expiry is None:

            response = {
                'error': 'Bad Request',
                'message': 'Symbol or Expiry unprovided',
                'status': 500
            }

            return json.dumps(response)
        
        expiry = expiry.replace('-','')
        contract = IBContract.OptionForQuery(symbol)
        contract.lastTradeDateOrContractMonth = expiry
        contract_req = ContractDetailRequest(contract)

        try:
            req_id = self.ib.make_request(contract_req)

        except IBDisconnectedException:
            return ib_disconnected_response


        while self.ib.handled_requests[req_id].status != RequestStatus.RESPONDED and self.ib.handled_requests[req_id].status != RequestStatus.FINISHED and self.ib.handled_requests[req_id].status != RequestStatus.ERROR:
            time.sleep(0.1)
            continue

        if self.ib.handled_requests[req_id].status == RequestStatus.ERROR:

            response = {
                'error': 'Bad Request',
                'message': f'{self.ib.handled_requests[req_id].error_msg}',
                'status': 500
            }
            return json.dumps(response)

        data = []
        for _con_detail in self.ib.contract_details[req_id]:
            curr = (_con_detail.contract.conId,
                    _con_detail.contract.strike,
                    _con_detail.contract.right)
            data.append(curr)

        return json.dumps(data)

    def handle_ticks_request(self, request_body):
        """
        IB live ticks request handler
        """
        security_type = SecurityType(request_body['security_type'])
        symbol = request_body['symbol']
     
        if security_type == SecurityType.OPTION_SPREAD:
            req_ids = []
            legs = request_body['legs']
            for leg in legs:
                contract = IBContract.OptionWithTradingClass(
                    symbol = symbol,
                    expiry = leg['expiry'].replace('-',''),
                    exchange = 'SMART',
                    strike = int(leg['strike']),
                    right = leg['right'],
                    tradingClass = symbol
                )
                tick_request = MarketDataRequest(contract)
                req_id = self.ib.make_request(tick_request)
                req_ids.append(req_id)
                time.sleep(0.5)

            ticks_data = self.ib.get_ticks_json(req_ids)

            i = 0
            total_bid = 0
            total_ask = 0
            total_last = 0
            bid_valid = True
            ask_valid = True
            last_valid = True
            for req_id, tick in ticks_data.items():
                status = RequestStatus(tick['status'])
                if status == RequestStatus.INIT or status == RequestStatus.PROCESSED:
                    response = {
                        'data' : 'pending'
                    }
                    return json.dumps(response)
                elif status == RequestStatus.ERROR:
                    response = {
                        'data' : 'error'
                    }
                    return json.dumps(response)
                else:
                    data_type = tick['data_type']
                    bid = tick['bid']
                    ask = tick['ask']
                    last = tick['last']

                    if bid == '' :
                        bid_valid = False
                    if ask == '':
                        ask_valid = False
                    if last == '':
                        last_valid = False

                    leg = legs[i]
                    leg_action = Action[leg['action']]
                    leg_quantity = int(leg['quantity'])
                    if leg_action == Action.BUY:
                        if bid_valid :
                            total_bid += bid * leg_quantity
                        else:
                            total_bid = ''
                        if ask_valid:
                            total_ask += ask * leg_quantity
                        else:
                            total_ask = ''
                        if last_valid:
                            total_last += last * leg_quantity
                        else:
                            total_last = ''
                    elif leg_action == Action.SELL:
                        if bid_valid :
                            total_bid -= bid * leg_quantity
                        else:
                            total_bid = ''
                        if ask_valid:
                            total_ask -= ask * leg_quantity
                        else:
                            total_ask = ''
                        if last_valid:
                            total_last -= last * leg_quantity
                        else:
                            total_last = ''
                i += 1

            response = {
                'data_type': data_type,
                'bid' : total_bid,
                'ask' : total_ask,
                'last': total_last,
            }
            
            return json.dumps(response)


    def handle_order_request(self, request_body):
        """
        Order handler
        """
        if not self.ib.is_connected:
            return ib_disconnected_response 
        
        #parse parameters
        security_type = SecurityType(request_body['security_type'])
        symbol = request_body['symbol']
        order_type = OrderType(request_body['order_type'])
        action = Action(request_body['action'])
        quantity = int(request_body['quantity'])
        if 'price' in request_body:
            limit_price = request_body['price']
        else:
            limit_price = None

        #construct order
        if security_type == SecurityType.STOCK or security_type == SecurityType.ETF:
            order = EquityOrder(
                broker = Broker.IBKR,
                security_type = security_type,
                order_type = order_type,
                action = action,
                quantity = quantity,
                limit_price = limit_price,
                symbol = symbol
            )

        elif security_type == SecurityType.OPTION_SPREAD:
            spread_type =  OptionSpread(request_body['spread_type'])
            legs = request_body['legs']
            legs_data = []
            for leg in legs:
                curr_leg = OptionLeg(
                    Action(leg['action']),
                    int(leg['quantity']),
                    Decimal(leg['strike']),
                    OptionRight(leg['right']),
                    leg['expiry']
                )
                legs_data.append(curr_leg)

            order = SpreadOrder( 
                broker = Broker.IBKR,
                security_type = security_type,
                order_type = order_type,
                action = action,
                quantity = quantity,
                limit_price = limit_price,
                spread_type = spread_type,
                expiry = legs_data[0].expiry,
                underlying_symbol = symbol,
                legs = legs_data
            )

        #submit order
        try:
            order = self.oms.place_order(order)
            response_json = order.get_data_json()
            return response_json

        except IBOrderExcepton :
            response_data = {
                'error': 'Order is rejected by IB'
            }
        except IBDisconnectedException:
            response_data = {
                'error': 'IB is disconnected, could not submit order'
            }
        except Exception as e:
            response_data = {
                'error': f'Unexpected error: {e}'
            }

        return json.dumps(response_data)
    
    def handle_cancel_order_request(self, request_body):
        """
        Cancel Order handler
        """
        if not self.ib.is_connected:
            return ib_disconnected_response
        
        broker_order_id = request_body['broker_order_id']
        security_type = request_body['security_type']

        try:
            broker_order_id = self.oms.cancel_order(broker_order_id = int(broker_order_id),
                                                    security_type = SecurityType(security_type))
            response_data = {
                'broker_order_id' : broker_order_id

            }
        except IBDisconnectedException:
            response_data = {
                'error': 'IB is disconnected, could not submit order'
            }
        except IBOrderExcepton:
            response_data = {
                'error': 'IB Order ID not found'
            }
        except Exception as e:
            response_data = {
                'error': f'Unexpected error: {e}'
            }

        return json.dumps(response_data)

    def handle_profitable_spreads_request(self):
        response_json = self.screener.get_profitable_spread_json()
        return response_json
    
    def handle_term_structure_request(self):
        term_structure_data = self.screener.get_term_structure()
        response_json = json.dumps(term_structure_data)
        return response_json

    def handle_gex_request(self):
        gex_data = self.screener.get_gex()
        response_json = json.dumps(gex_data)
        return response_json    
    
    def handle_volatility_forecast_request(self, request_body):
        horizon = int(request_body['horizon'])
        data = self.forecast_engine.get_forecast(horizon)
        response_data = {
            'forecast': data
        }
        response_json = json.dumps(response_data)
        return response_json
    
    def handle_volatility_history_request(self, request_body):
        symbol = request_body['symbol']
        history = int(request_body['history'])
        v = self.forecast_engine.get_volatility_history(
            symbol = symbol,
            history = history
        )
        raw_data : List[List[datetime.date, float]]= list(v.items())
        response_data = []
        for data in raw_data:
            response_data.append([
                str(data[0]),
                data[1]
            ])
        response_json = json.dumps(response_data)
        return response_json
    
    def handle_volatility_surface_request(self):
        response_data = self.screener.get_volatility_surface()
        response_json = json.dumps(response_data)
        return response_json

    def handle_option_chain_iv_request(self, request_body):
        expiry = request_body['expiry']
        if expiry not in self.screener.option_chains:
            response = {
                'error': f'Expiry {expiry} not found.'
            }
            return json.dumps(response)
        response_data = self.screener.get_raw_iv(expiry)
        response_json = json.dumps(response_data)
        return response_json
        
    def start(self):
        """
        Start the RPC server
        """
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.on_request)
        try:
            self.channel.start_consuming()
        except ChannelClosed:
            self.active = False
            logger.error('Channel is closed unexpectedly')
