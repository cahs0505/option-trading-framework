from ibapi.contract import *
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class IBKROrderStatus:

    perm_id : int 
    order_id : int = None
    contract : Contract = None
    action: str = ""
    order_type: str = ""
    total_quantity: Decimal = None
    cash_quantity: float = None
    limit_price: float = None
    aux_price: float = None
    status: str = ""
    filled: Decimal = None
    remaining: Decimal = None
    avg_fill_price: float = None
    last_fill_price: float = None


    def set_value(self,
                  **kwargs):
        
        for k,v in kwargs.items():
            setattr(self,k,v)


