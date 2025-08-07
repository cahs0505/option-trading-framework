from ibapi.contract import *
from decimal import Decimal
from dataclasses import dataclass

PORTFOLIO_MAP= {
    "contract" : "contract",
    "position" : "position",
    "marketPrice" : "market_price",
    "marketValue" : "market_value",
    "averageCost" : "average_cost",
    "unrealizedPNL" : "unrealized_PnL",
    "realizedPNL" : "realized_PnL",
}

"""
Represent the position of ONE ibkr contract
"""
@dataclass
class IBKRPortfolio:

    contract : Contract
    position : Decimal
    market_price: float
    market_value: float
    average_cost: float
    unrealized_PnL: float
    realized_PnL: float

    def __repr__(self):
        return(f"Symbol: {self.contract.symbol} Security Type: {self.contract.secType} Market Price: {self.market_price} Market Value: {self.market_value} Average Cost: {self.average_cost} Unrealized PnL: {self.unrealized_PnL} Realized PnL: {self.realized_PnL}")

    def set_value(self,
                contract: Contract, 
                position: Decimal,
                market_price: float, 
                market_value: float,
                average_cost: float, 
                unrealized_PnL: float,
                realized_PnL: float):
        
        self.contract = contract
        self.position = position
        self.market_price = market_price
        self.market_value = market_value
        self.average_cost = average_cost
        self.unrealized_PnL = unrealized_PnL
        self.realized_PnL = realized_PnL
        

        

