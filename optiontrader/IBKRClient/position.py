from ibapi.contract import Contract
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict

POSITION_MAP= {
    "contract" : "contract",
    "position" : "position",
    "marketPrice" : "market_price",
    "marketValue" : "market_value",
    "averageCost" : "average_cost",
    "unrealizedPNL" : "unrealized_PnL",
    "realizedPNL" : "realized_PnL",
}

@dataclass
class IBKRPosition:
    """
    Represent the position of 1 contract
    """
    contract : Contract
    position : Decimal
    market_price: float
    market_value: float
    average_cost: float
    unrealized_PnL: float
    realized_PnL: float

    #Greeks if underlying contract is an option
    last_price: float
    implied_volatility: float
    delta: float = None 
    gamma: float = None
    vega: float = None
    theta: float = None
    rho: float = None
    
    def __init__(self, data: Dict):
        for k,v in data.items():
            setattr(self,k , v)

    def __str__(self):
        return ",".join(
                    (
                        "symbol: " + str(self.contract.localSymbol),
                        "security type: " + str(self.contract.secType),
                        "position: " + str(self.position),
                        "market price: " + str(self.market_price),
                        "market value: " + str(self.market_value),
                        "average cost: " + str(self.average_cost),
                        "unrealized PnL: " + str(self.unrealized_PnL),
                        "realized PnL: " + str(self.realized_PnL),
                    )
                )
    
    def __repr__(self):
        return ",".join(
                    (
                        "symbol: " + str(self.contract.localSymbol),
                        "security type: " + str(self.contract.secType),
                        "position: " + str(self.position),
                        "market price: " + str(self.market_price),
                        "market value: " + str(self.market_value),
                        "average cost: " + str(self.average_cost),
                        "unrealized PnL: " + str(self.unrealized_PnL),
                        "realized PnL: " + str(self.realized_PnL),
                    )
                )

    def set_value(self, data: Dict) -> None:
        for k,v in data.items():
            setattr(self, k, v)