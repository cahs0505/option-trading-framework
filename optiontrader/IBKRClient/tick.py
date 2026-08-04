from typing import Dict
from enum import Enum
from ibapi.contract import Contract

TickTypeArray = [
    "BID_SIZE",
    "BID",
    "ASK",
    "ASK_SIZE",
    "LAST",
    "LAST_SIZE",
    "HIGH",
    "LOW",
    "VOLUME",
    "CLOSE",
    "BID_OPTION_COMPUTATION",
    "ASK_OPTION_COMPUTATION",
    "LAST_OPTION_COMPUTATION",
    "MODEL_OPTION",
    "OPEN",
    "LOW_13_WEEK",
    "HIGH_13_WEEK",
    "LOW_26_WEEK",
    "HIGH_26_WEEK",
    "LOW_52_WEEK",
    "HIGH_52_WEEK",
    "AVG_VOLUME",
    "OPEN_INTEREST",
    "OPTION_HISTORICAL_VOL",
    "OPTION_IMPLIED_VOL",
    "OPTION_BID_EXCH",
    "OPTION_ASK_EXCH",
    "OPTION_CALL_OPEN_INTEREST",
    "OPTION_PUT_OPEN_INTEREST",
    "OPTION_CALL_VOLUME",
    "OPTION_PUT_VOLUME",
    "INDEX_FUTURE_PREMIUM",
    "BID_EXCH",
    "ASK_EXCH",
    "AUCTION_VOLUME",
    "AUCTION_PRICE",
    "AUCTION_IMBALANCE",
    "MARK_PRICE",
    "BID_EFP_COMPUTATION",
    "ASK_EFP_COMPUTATION",
    "LAST_EFP_COMPUTATION",
    "OPEN_EFP_COMPUTATION",
    "HIGH_EFP_COMPUTATION",
    "LOW_EFP_COMPUTATION",
    "CLOSE_EFP_COMPUTATION",
    "LAST_TIMESTAMP",
    "SHORTABLE",
    "FUNDAMENTAL_RATIOS",
    "RT_VOLUME",
    "HALTED",
    "BID_YIELD",
    "ASK_YIELD",
    "LAST_YIELD",
    "CUST_OPTION_COMPUTATION",
    "TRADE_COUNT",
    "TRADE_RATE",
    "VOLUME_RATE",
    "LAST_RTH_TRADE",
    "RT_HISTORICAL_VOL",
    "IB_DIVIDENDS",
    "BOND_FACTOR_MULTIPLIER",
    "REGULATORY_IMBALANCE",
    "NEWS_TICK",
    "SHORT_TERM_VOLUME_3_MIN",
    "SHORT_TERM_VOLUME_5_MIN",
    "SHORT_TERM_VOLUME_10_MIN",
    "DELAYED_BID",
    "DELAYED_ASK",
    "DELAYED_LAST",
    "DELAYED_BID_SIZE",
    "DELAYED_ASK_SIZE",
    "DELAYED_LAST_SIZE",
    "DELAYED_HIGH",
    "DELAYED_LOW",
    "DELAYED_VOLUME",
    "DELAYED_CLOSE",
    "DELAYED_OPEN",
    "RT_TRD_VOLUME",
    "CREDITMAN_MARK_PRICE",
    "CREDITMAN_SLOW_MARK_PRICE",
    "DELAYED_BID_OPTION",
    "DELAYED_ASK_OPTION",
    "DELAYED_LAST_OPTION",
    "DELAYED_MODEL_OPTION",
    "LAST_EXCH",
    "LAST_REG_TIME",
    "FUTURES_OPEN_INTEREST",
    "AVG_OPT_VOLUME",
    "DELAYED_LAST_TIMESTAMP",
    "SHORTABLE_SHARES",
    "DELAYED_HALTED",
    "REUTERS_2_MUTUAL_FUNDS",
    "ETF_NAV_CLOSE",
    "ETF_NAV_PRIOR_CLOSE",
    "ETF_NAV_BID",
    "ETF_NAV_ASK",
    "ETF_NAV_LAST",
    "ETF_FROZEN_NAV_LAST",
    "ETF_NAV_HIGH",
    "ETF_NAV_LOW",
    "SOCIAL_MARKET_ANALYTICS",
    "ESTIMATED_IPO_MIDPOINT",
    "FINAL_IPO_LAST",
    "DELAYED_YIELD_BID",
    "DELAYED_YIELD_ASK",
    "NOT_SET",
]
class MarketDataType(Enum):
    LIVE = 1
    FROZEN = 2
    DELAYED = 3
    DELAYED_FROZEN = 4

class Tick:

    tickerId: int
    data_type: MarketDataType
    error_code: int = None

    symbol: str
    secType: str
    exchange: str
    currency: str
    expiry: str
    strike: str
    right: str
    multiplier: int
    tradingClass:str

    BID_SIZE : str = None
    BID : float = None
    ASK : float = None
    ASK_SIZE : str = None
    LAST : float = None
    LAST_SIZE : str = None
    HIGH : float = None
    LOW : float = None
    VOLUME : str = None
    CLOSE : float = None
    BID_OPTION_COMPUTATION : float = None
    ASK_OPTION_COMPUTATION : float = None
    LAST_OPTION_COMPUTATION : float = None
    MODEL_OPTION : float = None
    OPEN : float = None
    LOW_13_WEEK : float = None
    HIGH_13_WEEK : float = None
    LOW_26_WEEK : float = None
    HIGH_26_WEEK : float = None
    LOW_52_WEEK : float = None
    HIGH_52_WEEK : float = None
    AVG_VOLUME : str = None
    OPEN_INTEREST : str = None
    OPTION_HISTORICAL_VOL : float = None
    OPTION_IMPLIED_VOL : float = None
    OPTION_BID_EXCH : str = None
    OPTION_ASK_EXCH : str = None
    OPTION_CALL_OPEN_INTEREST : str = None
    OPTION_PUT_OPEN_INTEREST : str = None
    OPTION_CALL_VOLUME : str = None
    OPTION_PUT_VOLUME : str = None
    INDEX_FUTURE_PREMIUM : float = None
    BID_EXCH : str = None
    ASK_EXCH : str = None
    AUCTION_VOLUME : str = None
    AUCTION_PRICE : float = None
    AUCTION_IMBALANCE : str = None
    MARK_PRICE : float = None
    BID_EFP_COMPUTATION : float = None
    ASK_EFP_COMPUTATION : float = None
    LAST_EFP_COMPUTATION : float = None
    OPEN_EFP_COMPUTATION : float = None
    HIGH_EFP_COMPUTATION : float = None
    LOW_EFP_COMPUTATION : float = None
    CLOSE_EFP_COMPUTATION : float = None
    LAST_TIMESTAMP : str = None
    SHORTABLE : float = None
    FUNDAMENTAL_RATIOS : float = None
    RT_VOLUME : float = None
    HALTED : float = None
    BID_YIELD : float = None
    ASK_YIELD : float = None
    LAST_YIELD : float = None
    CUST_OPTION_COMPUTATION : float = None
    TRADE_COUNT : float = None
    TRADE_RATE : float = None
    VOLUME_RATE : float = None
    LAST_RTH_TRADE : float = None
    RT_HISTORICAL_VOL : float = None
    IB_DIVIDENDS : str = None
    BOND_FACTOR_MULTIPLIER : float = None
    REGULATORY_IMBALANCE : str = None
    NEWS_TICK : str = None
    SHORT_TERM_VOLUME_3_MIN : str = None
    SHORT_TERM_VOLUME_5_MIN : str = None
    SHORT_TERM_VOLUME_10_MIN : str = None
    DELAYED_BID : float = None
    DELAYED_ASK : float = None
    DELAYED_LAST : float = None
    DELAYED_BID_SIZE : str = None
    DELAYED_ASK_SIZE : str = None
    DELAYED_LAST_SIZE : str = None
    DELAYED_HIGH : float = None
    DELAYED_LOW : float = None
    DELAYED_VOLUME : str = None
    DELAYED_CLOSE : float = None
    DELAYED_OPEN : float = None
    RT_TRD_VOLUME : str = None
    CREDITMAN_MARK_PRICE : float = None
    CREDITMAN_SLOW_MARK_PRICE : float = None
    DELAYED_BID_OPTION : float = None
    DELAYED_ASK_OPTION : float = None
    DELAYED_LAST_OPTION : float = None
    DELAYED_MODEL_OPTION : float = None
    LAST_EXCH : str = None
    LAST_REG_TIME : str = None
    FUTURES_OPEN_INTEREST : str = None
    AVG_OPT_VOLUME : str = None
    DELAYED_LAST_TIMESTAMP : str = None
    SHORTABLE_SHARES : str = None
    DELAYED_HALTED : float = None
    REUTERS_2_MUTUAL_FUNDS : float = None
    ETF_NAV_CLOSE : float = None
    ETF_NAV_PRIOR_CLOSE : float = None
    ETF_NAV_BID : float = None
    ETF_NAV_ASK : float = None
    ETF_NAV_LAST : float = None
    ETF_FROZEN_NAV_LAST : float = None
    ETF_NAV_HIGH : float = None
    ETF_NAV_LOW : float = None
    SOCIAL_MARKET_ANALYTICS : float = None
    ESTIMATED_IPO_MIDPOINT : float = None
    FINAL_IPO_LAST : float = None
    DELAYED_YIELD_BID : float = None
    DELAYED_YIELD_ASK : float = None

    def __init__(
        self,
        tickerId: int,
        contract: Contract
    ):
        self.tickerId = tickerId
        self.data_type = MarketDataType.LIVE
        self.symbol = contract.symbol
        self.secType = contract.secType
        self.exchange = contract.exchange
        self.currency = contract.currency
        self.expiry = contract.lastTradeDateOrContractMonth
        self.strike = contract.strike
        self.right = contract.right
        self.multiplier = contract.multiplier 
        self.tradingClass = contract.tradingClass

    def get_bid_ask(self) -> Dict:


        if self.data_type == MarketDataType.LIVE:
            data = {
                'data_type': self.data_type,
                'bid': self.BID if self.BID is not None and self.BID != -1 else '',
                'ask': self.ASK if self.ASK is not None and self.ASK != -1 else '',
                'last': self.LAST if self.LAST is not None and self.LAST != -1 else '',
                'close' : self.CLOSE if self.CLOSE is not None and self.CLOSE != -1 else ''
            }
        else:
            data = {
                'data_type': self.data_type,
                'bid': self.DELAYED_BID if self.DELAYED_BID is not None and self.DELAYED_BID != -1 else '',
                'ask': self.DELAYED_ASK if self.DELAYED_ASK is not None and self.DELAYED_ASK != -1 else '',
                'last': self.DELAYED_LAST if self.DELAYED_LAST is not None and self.DELAYED_LAST != -1 else '',
                'close' : self.DELAYED_CLOSE if self.DELAYED_CLOSE is not None and self.DELAYED_CLOSE != -1 else ''
            }

        return data 