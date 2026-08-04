import uuid
import json
from optiontrader.constants import OrderStatus,OptionSpread, Action, OrderType, Broker, OptionRight, SecurityType
from decimal import Decimal
from dataclasses import dataclass
from typing import List
from datetime import datetime, UTC

class BaseOrder:
    """
    Base order object submitted to the order manager
    """
    order_id: uuid 
    time: datetime
    broker_order_id: int
    status: OrderStatus
    broker: Broker
    security_type: SecurityType
    order_type: OrderType
    action: Action
    quantity: int
    filled: int
    limit_price: Decimal
    average_price: Decimal
    def __init__(self,
                 broker: Broker,
                 security_type: SecurityType,
                 order_type: OrderType,
                 action: Action,
                 quantity: int,
                 limit_price: Decimal = None):
        self.order_id = uuid.uuid4()
        self.time = datetime.now(UTC)
        self.status = OrderStatus.INIT
        self.broker = broker
        self.security_type = security_type
        self.order_type = order_type
        self.action = action
        self.quantity = quantity
        self.filled = 0
        self.limit_price = limit_price
        self.average_price = None

    def __str__(self):
        return f'OrderID {self.order_id} BrokerID: {self.broker_order_id } - Status: {self.status}'
    
    def __repr__(self):
        return f'OrderID {self.order_id} BrokerID: {self.broker_order_id } - Status: {self.status}'

    def set_status(self, status: OrderStatus):
        self.status = status

    def set_broker_order_id(self, broker_order_id:int):
        self.broker_order_id = broker_order_id

    def set_average_price(self, average_price: Decimal):
        self.average_price = average_price
    
    def get_data_dict(self, stringify:bool = False):
        pass

@dataclass
class OptionLeg:
    action: Action
    quantity: int
    strike: Decimal
    right: OptionRight
    expiry: str
class SpreadOrder(BaseOrder):
    """
    Option Spread Order
    """
    spread_type: OptionSpread
    expiry: str
    underlying_symbol: str
    legs: List[OptionLeg]

    def __init__(self,
                 broker: Broker,
                 security_type: SecurityType,
                 order_type: OrderType,
                 action: Action,
                 quantity: int,
                 limit_price: Decimal,
                 spread_type: OptionSpread,
                 expiry: str,
                 underlying_symbol: str,
                 legs: List[OptionLeg]):
        
        super().__init__(
            broker = broker,
            security_type = security_type,
            order_type = order_type,
            action = action,
            quantity = quantity,
            limit_price = limit_price
        )
        self.spread_type = spread_type
        self.expiry = expiry
        self.underlying_symbol = underlying_symbol
        self.legs = legs

    def get_data_dict(self, stringify:bool = False):
        data = {}
        columns = [
            'order_id',
            'time',
            'status',
            'broker',
            'broker_order_id',
            'order_type',
            'security_type',
            'spread_type',
            'expiry',
            'underlying_symbol',
            'quantity',
            'filled',
            'action',
            'limit_price',
            'average_price'
        ]
        for col in columns:
            val = getattr(self,col)
            if val is not None:
                data[col] = str(val) if stringify else val
        return data
    
    def get_data_json(self):
        data = {
            'order_id': str(self.order_id),
            'time': str(self.time),
            'status': self.status.value,
            'broker': self.broker.value,
            'broker_order_id': self.broker_order_id,
            'order_type': self.order_type.value,
            'security_type': self.security_type.value,
            'spread_type': self.spread_type.value,
            'underlying_symbol': self.underlying_symbol,
            'quantity': self.quantity,
            'filled': self.filled,
            'action': self.action.value,
            'limit_price': str(self.limit_price),
            'average_price': str(self.average_price)
        }
        return json.dumps(data)
    
    def get_legs_data(self):
        data = []
        for leg in self.legs:
            data.append({
                'expiry': leg.expiry,
                'strike': leg.strike,
                'option_right': 'C' if leg.right == OptionRight.CALL else 'P',
                'action': leg.action.value,
                'quantity': leg.quantity
            })
        return data
    
class EquityOrder(BaseOrder):
    """
    Equity Orders: Stocks, ETF, etc.
    """
    symbol: str

    def __init__(self,
                 broker: Broker,
                 security_type: SecurityType,
                 order_type: OrderType,
                 action: Action,
                 quantity: int,
                 limit_price: Decimal,
                 symbol: str):
        
        super().__init__(
            broker = broker,
            security_type = security_type,
            order_type = order_type,
            action = action,
            quantity = quantity,
            limit_price = limit_price
        )
        self.symbol = symbol

    def get_data_dict(self, stringify:bool = False):
        data = {}
        columns = [
            'order_id',
            'time',
            'status',
            'broker',
            'broker_order_id',
            'order_type',
            'security_type',
            'symbol',
            'quantity',
            'filled',
            'action',
            'limit_price',
            'average_price'
        ]
        for col in columns:
            val = getattr(self,col)
            if val is not None:
                data[col] = str(val) if stringify else val
        return data

    def get_data_json(self):
        data = {
            'order_id': str(self.order_id),
            'time': str(self.time),
            'status': self.status.value,
            'broker': self.broker.value,
            'broker_order_id': self.broker_order_id,
            'security_type': self.security_type.value,
            'order_type': self.order_type.value,
            'symbol' : self.symbol,
            'quantity': self.quantity,
            'filled': self.filled,
            'action': self.action.value,
            'limit_price': str(self.limit_price),
            'average_price': str(self.average_price)
        }
        return json.dumps(data)