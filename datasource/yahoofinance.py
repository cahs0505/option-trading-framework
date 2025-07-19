import pandas as pd
from typing import List, Dict, Tuple
import yfinance as yf
import numpy as np
import threading
import logging
from util import validate_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_price_history(symbol: str,
                        history: str = None,
                        start_date: str = None,
                        end_date: str = None,
                        proxies: Dict  = None
                        ) -> pd.DataFrame:
    """
    Single Ticker Price Histroy
    """
    ticker = yf.Ticker(symbol,proxy=proxies)
    df = ticker.history(interval="1d", start=start_date, end=end_date)
    df.rename(columns={"Open": "open", 
                       "High": "high", 
                       "Low": "low", 
                       "Close": "close", 
                       "Volume" :"volume", 
                       "Dividends" : "dividends", 
                       "Stock Splits": "splits"},
                       inplace=True)
    df['symbol'] = symbol
    df.index = (df.index+ pd.DateOffset(hours=16)).tz_convert("UTC")

    return df
    
def get_price_history_multiple(symbols: List,
                               history: str = None,
                               start_date: str = None,
                               end_date: str = None,
                               proxies: Dict  = None
                               ) -> pd.DataFrame:
    """
    Multiple Tickers Price History
    """

    validate_date(start_date)
    validate_date(end_date)
    data = []
    df = yf.download(symbols, period=history,start=start_date,end=end_date,proxy=proxies)
    df = df[~(df.index < start_date)]
    df.dropna(axis=1,inplace=True)
    df.columns = df.columns.remove_unused_levels().set_levels(['close','high','low','open','volume'],level=0)
    df.index = (df.index+ pd.DateOffset(hours=20)).tz_localize("UTC")

    if not df.empty:    

        for symbol in symbols:

            try:
                curr_df = df.xs(symbol, level='Ticker', axis=1)
                curr_df["symbol"] = symbol
                curr_data = list(curr_df[['open','high','low','close','volume','symbol']].itertuples(index=True, name=None))
                data += curr_data

                ##error handling to be implemented
            except ValueError:
                logger.error(f"{symbol} does not exist")
            except Exception:
                logger.error(f"{symbol}: Unexpected error")
            finally:
                continue

    return data

def get_option_price(symbol: str,
                    expiry: str, 
                    range: int = 5,
                    proxies: Dict  = None
                    ) -> pd.DataFrame:
    """
    Single Ticker Option Price
    """

    ticker = yf.Ticker(symbol,proxy=proxies)
    option = ticker.option_chain(expiry)
    data = _process_option_data(option=option, expiry=expiry, symbol=symbol, range=range)

    return data

def get_option_price_multiple(batch: List[Tuple[str,str]], 
                              range: int = 5,
                              proxies: Dict = None
                              ) -> pd.DataFrame:
    """
    Multiple Tickers Option Price 
    (Multi-threaded implementation)
    batch should be a list of symbol-expiry pair : [("TSLA","2025-06-01), ("NVDA","2025-06-07),...]
    """
    data_all = []
    threads = []

    for job in batch:
        symbol = job[0]
        expiry = job[1]
        t = threading.Thread(target=_download_and_process, args=(data_all,symbol,expiry,range,proxies))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    return data_all

def _download_and_process(data_all : List, 
                          symbol : str, 
                          expiry : str, 
                          range : int,
                          proxies: Dict = None) -> None:
    """
    Download and process raw option data 
    """ 
    ticker = yf.Ticker(symbol,proxy=proxies)
    option = ticker.option_chain(expiry)
    data = _process_option_data(option=option, expiry=expiry, symbol=symbol, range=range)
    data_all += data

def _process_option_data(option: pd.DataFrame,
                         symbol: str,
                         expiry: str,
                         range: int) -> List:
    """
    Process raw option data from yfinance
    """            
    time_of_snapshot = pd.Timestamp.utcnow()
    calls = option.calls
    calls["call_put"] = 'c'
    if not calls[calls.inTheMoney == True].empty:
        
        atm_idx = calls [calls.inTheMoney == True].iloc[-1:].index[0]
        calls['moneyness'] = calls.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
        calls.at[atm_idx, 'moneyness'] = 'a'

        start_index = (atm_idx-range) if (atm_idx-range)>0 else 0
        end_index = (atm_idx+range) if (atm_idx+range) < len(calls) else  len(calls)-1

        calls = calls.iloc[start_index : end_index]
    else:
        calls['moneyness'] = calls.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
        calls = calls.iloc[:range]

    puts = option.puts
    puts["call_put"] = 'p'
    if not puts[puts.inTheMoney == True].empty:

        atm_idx = puts [puts.inTheMoney == True].iloc[:1].index[0]
        puts['moneyness'] = puts.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
        puts.at[atm_idx, 'moneyness'] = 'a'

        start_index = (atm_idx-range) if (atm_idx-range)>0 else 0
        end_index = (atm_idx+range) if (atm_idx+range) < len(puts) else  len(puts)-1

        puts = puts.iloc[start_index : end_index]
    else:
        puts['moneyness'] = puts.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
        atm_idx = puts.iloc[-1:].index[0]
        puts = puts.iloc[-range: ]

    df = pd.concat([calls,puts])

    df.rename(columns={"contractSymbol": "contract", 
                        "lastTradeDate": "time", 
                        "lastPrice": "last_price", 
                        "openInterest": 
                        "open_interest", 
                        "impliedVolatility": "implied_volatility"}
                        ,inplace=True)

    df.drop(columns=['change','percentChange','inTheMoney','contractSize','currency'],inplace=True)
    df["symbol"] = symbol
    df["expiry"] = expiry
    df["time_of_snapshot"] = time_of_snapshot
    df = df.replace({np.nan: None})

    data = list(df[["time_of_snapshot",
                    "time",
                    "contract",
                    "symbol",
                    "strike",
                    "expiry",
                    "call_put",
                    "last_price",
                    "bid",
                    "ask",
                    "volume",
                    "open_interest",
                    "moneyness",
                    "implied_volatility"]]
                    .itertuples(index=False, name=None))  

    return data

"""
General Info
"""
def get_market_cap(symbol: str,
                   proxies: Dict = None) -> int:

    ticker = yf.Ticker(symbol,proxy=proxies)
    market_cap = ticker.info["marketCap"]
    
    return market_cap

