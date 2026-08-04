from enum import StrEnum

class SecurityType(StrEnum):
    STOCK = 'STK'
    OPTION = 'OPT'
    ETF = 'ETF'
    OPTION_SPREAD = 'OPTION_SPREAD'

class OrderType(StrEnum):
    LIMIT = 'LMT'
    MARKET = 'MKT'
    MID = 'MIDPRICE'

class Action(StrEnum):
    BUY = 'BUY'
    SELL = 'SELL'

class OptionRight(StrEnum):
    CALL = 'CALL'
    PUT = 'PUT'

class OptionStyle(StrEnum):
    AMERICAN = 'AMERICAN'
    EUROPEAN = 'EUROPEAN'

class OptionSpread(StrEnum):
    STRADDLE = 'STRADDLE'
    STRANGLE = 'STRANGLE'
    IRON_CONDOR = 'IRON_CONDOR'
    
class DataSource(StrEnum):
    LOCAL = 'LOCAL'
    REMOTE = 'REMOTE'
    YFINANCE = 'YFINANCE'
    IBKR = 'IBKR'

class Broker(StrEnum):
    IBKR = 'IBKR'
    
class Exchange(StrEnum):
    NYSE = 'NYSE'

class OrderStatus(StrEnum):
    INIT = 'Initiated'
    SUBMITTING = 'Submmiting'           
    SUBMITTED = 'Submitted'                 
    PARTIALLY_FILLED = 'Partilly Filled'
    FILLED = 'Filled'
    CANCELLED = 'Cancelled'
    REJECTED = 'Rejected'

YEARLY_TRADING_DAYS = 252
TRADING_HOURS_PER_DAY = 6.5
TRADING_MINUTES_PER_DAY = 390