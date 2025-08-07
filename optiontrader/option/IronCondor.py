from optiontrader.Constants import Position
from optiontrader.option.Option import Option
from typing import Tuple
from decimal import Decimal

"""
Represent long/short position of a single iron condor spread
All computations ignore transaction cost, slippage, etc.
"""
class IronCondor:
    
    leg1: Option
    leg2: Option
    leg3: Option
    leg4: Option
    position: Position

    def __init__(self,
                 position: Position,
                 leg1: Option,
                 leg2: Option,
                 leg3: Option,
                 leg4: Option):
        
        self.leg1 = leg1
        self.leg2 = leg2
        self.leg3 = leg3
        self.leg4 = leg4
        self.position = position
        
    def initial_debit_or_credit(self) -> Decimal:

        return self.leg1.initial_debit_or_credit()+self.leg2.initial_debit_or_credit()+self.leg3.initial_debit_or_credit()+self.leg4.initial_debit_or_credit()
    
    def total_premium(self) -> Decimal:

        return -self.leg1.premium + self.leg2.premium + self.leg3.premium - self.leg4.premium
    
    """
    Pair of stock price for breakeven at expiry 
    """
    def break_even_threshold(self) -> Tuple[Decimal, Decimal]:

        low_break_even = self.total_premium() - self.leg1.strike + self.leg2.strike + self.leg3.strike
        high_break_even = -self.total_premium() + self.leg1.strike

        return (low_break_even,high_break_even)

    """
    Pair of stock price for max profit at expiry
    """
    def max_profit_threshold(self) -> Tuple[Decimal, Decimal]:

        return (self.leg2.strike, self.leg3.strike)
    
    """
    Pair of stock price for max loss at expiry
    """
    def max_loss_threshold(self) -> Tuple[Decimal, Decimal]:

        return (self.leg1.strike, self.leg4.strike)

    """
    Given stock price at expiry, return payout
    """
    def payout_at_expiry(self,
                         stock_price: float) -> Decimal:
        
        return self.leg1.payout_at_expiry(stock_price=stock_price)+self.leg2.payout_at_expiry(stock_price=stock_price)+self.leg3.payout_at_expiry(stock_price=stock_price)+self.leg4.payout_at_expiry(stock_price=stock_price)
    
    """
    Given stock price at expiry, return PnL
    """
    def pnl_at_expiry(self,
                      stock_price: float) -> Decimal:
        
        return self.leg1.pnl_at_expiry(stock_price=stock_price)+self.leg2.pnl_at_expiry(stock_price=stock_price)+self.leg3.pnl_at_expiry(stock_price=stock_price)+self.leg4.pnl_at_expiry(stock_price=stock_price)


    def delta(self):
        pass

    def gamma(self):
        pass

    def theta(self):
        pass

    def vega(self):
        pass
    
    




