from decimal import Decimal
from typing import Dict, Callable, Set

from ibapi.order import Order
from ibapi.contract import Contract
from ibapi.order_state import OrderState
from ibapi.commission_report import CommissionReport
from ibapi.execution import Execution

from optiontrader.constants import OrderStatus

IB_STATUS_MAP: dict[str, OrderStatus] = {
    'ApiPending': OrderStatus.SUBMITTING,
    'PendingSubmit': OrderStatus.SUBMITTING,
    'PreSubmitted': OrderStatus.SUBMITTED,
    'Submitted': OrderStatus.SUBMITTED,
    'ApiCancelled': OrderStatus.CANCELLED,
    'Cancelled': OrderStatus.CANCELLED,
    'Filled': OrderStatus.FILLED,
    'Inactive': OrderStatus.REJECTED
}

class IBOrder:
    """
    Wrapper around the Order, Contract, Order State, and Execution Details.
    Also act as the interface for submitting order
    """
    order_id: int = None
    status: OrderStatus = OrderStatus.INIT
    filled: Decimal = None
    remaining: Decimal = None
    avg_fill_price: float = None
    perm_id: int = None
    parent_id: int = None
    last_fill_price: float = None 
    client_id: int = None
    why_held: str = None
    market_cap_price: float = None

    order: Order = None
    contract: Contract = None
    order_state: OrderState = None
    commission_report: Dict[int,CommissionReport] = {}
    executions: Dict[int,Execution] = {}

    _subscribers:  Set[Callable] 

    def __init__(self):
        self.status = OrderStatus.INIT
        self._subscribers = set()

    def __str__(self):
        return f'Order ID {self.order_id} - Status: {self.status}, Filled: {self.filled}, Remaining: {self.remaining} Contract:{self.contract}'
    
    def __repr__(self):
        return f'Order ID {self.order_id} - Status: {self.status}, Filled: {self.filled}, Remaining: {self.remaining} Contract:{self.contract}'

    def add_status(self, status: str) -> None:
        self.status = IB_STATUS_MAP[status]

    def add_execution(self, exec_id: int, execution: Execution) -> None:
        self.executions[exec_id] = execution

    def add_commission_report(self,exec_id: int, commission_report: CommissionReport) -> None:
        self.commission_report[exec_id] = commission_report

    def get_order_summary(self) -> Dict:
        data = {
            'order_id' : self.order_id,
            'security_type': self.contract.secType,
            'symbol': self.contract.symbol,
            'order_type': self.order.orderType,            
            'action': self.order.action,
            'quantity': self.order.totalQuantity,
            'status': self.status,
            'filled': self.filled,
            'remaining': self.remaining,
            'avg_fill_price': self.avg_fill_price,
        }

        return data
    
    def get_order_summary_json(self) -> str:
        data = self.get_order_summary()
        for k,v in data.items():
            data[k] = str(v)
        return data
    
    def subscribe(self, callback: Callable) -> None:
        self._subscribers.add(callback)

    def unsubscribe(self, callback: Callable) -> None:
        self._subscribers.discard(callback)

    def notify(self, **kwargs) -> None:
        for callback in self._subscribers:
            callback(**kwargs)  