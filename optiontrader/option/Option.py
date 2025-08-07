from datetime import datetime
import yfinance as yf
import numpy as np
from optiontrader.Constants import Asset, Position, OptionRight
from decimal import Decimal

AMERICAN = "American"
EUROPEAN = "European" 

"""
Represent long/short position of a single option contract
All computations ignore transaction cost, slippage, etc.
"""
class Option:

    underlying_asset: Asset
    underlying_quantity: int
    style: str

    symbol: str
    right: OptionRight
    position: Position
    strike: Decimal
    expiration: datetime
    premium: Decimal
    
    def __init__(self, 
                 symbol : str, 
                 right: OptionRight, 
                 position: Position,
                 strike: Decimal,
                 expiration: datetime,
                 premium: Decimal):
        
        self.underlying_asset = Asset.STOCK
        self.underlying_quantity = 100
        self.style = AMERICAN

        self.symbol = symbol
        self.right = right
        self.position = position
        self.strike = strike
        self.expiration = expiration
        self.premium = premium

    def initial_debit_or_credit(self) -> Decimal:

        if(self.position == Position.LONG):
            return -self.premium * self.underlying_quantity
        else:
            return self.premium * self.underlying_quantity
        
    """
    Return the stock price of breakeven point
    """
    def break_even(self) -> Decimal:

        if(self.right == OptionRight.CALL):
            return self.strike + self.premium
        else:
            return self.strike - self.premium

    """
    Given stock price at expiry, calculate payout (ignore premium)
    """
    def payout_at_expiry(self,
                         stock_price: Decimal) -> Decimal:

        if(self.position == Position.LONG):
            if(self.right == OptionRight.CALL):
                return max(0,stock_price - self.strike) * self.underlying_quantity
            else:
                return max(0,self.strike - stock_price) * self.underlying_quantity
        
        else:
            if(self.right == OptionRight.CALL):
                return min(0,self.strike - stock_price) * self.underlying_quantity
            else:
                return min(0,stock_price - self.strike) * self.underlying_quantity
    
    """
    Given stock price at expiry, calculate PnL (including premium)
    """
    def pnl_at_expiry(self,
                      stock_price: Decimal) -> Decimal:
        
        if(self.position == Position.LONG):
            return self.payout_at_expiry(stock_price=stock_price) - self.premium * self.underlying_quantity
        
        else:
            return self.payout_at_expiry(stock_price=stock_price) + self.premium * self.underlying_quantity
        
        