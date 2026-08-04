import os
from dataclasses import dataclass

@dataclass
class Config:
    DELTA_MARGIN: int = int(os.getenv('DELTA_MARGIN'))
    HEDGE_FREQ: int = int(os.getenv('HEDGE_FREQ'))
    IC_SHORT_STRIKE_DELTA_TARGET: float = float(os.getenv('IC_SHORT_STRIKE_DELTA_TARGET'))
    IC_LONG_STRIKE_DELTA_TARGET: float = float(os.getenv('IC_LONG_STRIKE_DELTA_TARGET'))
    VRP_THRESHOLD: int = int(os.getenv('VRP_THRESHOLD'))
    RISK_FREE_INTEREST_RATE: float = float(os.getenv('RISK_FREE_INTEREST_RATE'))
    SPY_ANNUAL_DIVIDEND_YIELD: float = float(os.getenv('SPY_ANNUAL_DIVIDEND_YIELD'))

config = Config()