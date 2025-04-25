from enum import Enum

class Asset(Enum):
    STOCK = 0
    CRYPTO = 1

class Position(Enum):
    SHORT = 0
    LONG = 1

class OptionSpread(Enum):
    STRADDLE = 0
    STRANGLE = 1

class DataSource(Enum):
    LOCAL = 0
    REMOTE = 1
    YFINANCE = 2

class Exchange(Enum):
    NYSE = "NYSE"