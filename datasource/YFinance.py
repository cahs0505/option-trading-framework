import pandas as pd
from typing import List, Dict

"""
Single Ticker Price Histroy
"""
def get_price_history(symbol: str,
                        history: str = None,
                        start_date: str = None,
                        end_date: str = None,
                        proxies: Dict  = None
                        ) -> pd.DataFrame:
    pass

"""
Multiple Tickers Price History
"""
def get_price_history_multiple(symbols: List,
                                  history: str = None,
                                  start_date: str = None,
                                  end_date: str = None,
                                  proxies: Dict  = None
                                  ) -> pd.DataFrame:
    pass

"""
Single Ticker Option Price
"""
def get_option_price(symbol: str,
                    expiry: str, 
                    range: int = 5,
                    proxies: Dict  = None
                    ) -> pd.DataFrame:
    pass


"""
Multiple Tickers Option Price 
(Multi-threaded)
"""
def get_option_price_multiple(symbols: List,
                            expiry: str, 
                            range: int = 5,
                            proxies: Dict = None
                            ) -> pd.DataFrame:
    pass


"""
Sec Filing
"""
def get_sec_filing(symbol: str) -> pd.DataFrame:
    pass

