import pandas as pd
import yfinance as yf
import numpy as np
import threading
import logging

from typing import List, Dict, Tuple
from datetime import datetime, UTC
from curl_cffi.requests.exceptions import HTTPError
from optiontrader.util import validate_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YFinanceError(Exception):
    def __init__(self, message):
        super().__init__()
        self.message = message

def get_spot_price(symbol):
    try:
        df = get_price_history(symbol=symbol,interval='5m')
        df['timestamp'] = df.index.astype('int64') // 10**9
        data = df.iloc[-1][['timestamp','close']].to_dict()
    except YFinanceError:
        raise 

    return data

def get_price_history(symbol: str,
                      start_date: str = None,
                      end_date: str = None,
                      interval: str = "1d",
                      proxies: Dict  = None,
                      ) -> pd.DataFrame:
    """
    Single Ticker Price Histroy
    """
    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(interval=interval, start=start_date, end=end_date)
    except HTTPError:
        raise YFinanceError('Possibly invalid symbol/interval/start date/end date') 

    df.rename(columns={'Open': 'open', 
                       'High': 'high', 
                       'Low': 'low', 
                       'Close': 'close', 
                       'Volume' :'volume', 
                       'Dividends' : 'dividends', 
                       'Stock Splits': 'splits'},
                       inplace=True)
    df['symbol'] = symbol
    if df.empty:
        raise YFinanceError('No Price data found')
    df.index = df.index.tz_convert('UTC')

    return df
    
def get_price_history_multiple(symbols: List,
                               history: str = None,
                               start_date: str = None,
                               end_date: str = None,
                               interval: str = "1d") -> List[Tuple]:
    """
    Multiple Tickers Price History
    """
    try:
        data = []
        df = yf.download(
            symbols,
            period = history,
            start = start_date,
            end = end_date,
            interval = interval)

        if not df.empty:
            df = df[~(df.index < start_date)]
            df.dropna(axis=1,inplace=True)
            df.columns = df.columns.remove_unused_levels().set_levels(['close','high','low','open','volume'],level=0)
            for symbol in symbols:
                curr_df = df.xs(symbol, level='Ticker', axis=1)
                curr_df['symbol'] = symbol
                curr_data = list(curr_df[['symbol','open','high','low','close','volume',]].itertuples(index=True, name=None))
                data += curr_data

    except Exception as e:
        logger.error(f'yahoofinance encountered enexpected error when getting price history:{e}')
        raise

    return data

def get_option_expiry(symbol: str,
                      proxies: Dict = None) -> tuple:
    """
    All expiration dates for a symbol 
    """
    ticker = yf.Ticker(symbol)
    option = ticker.options

    return option

def get_option_price(symbol: str,
                    expiry: str, 
                    range: int = 5,
                    join: bool = False
                    ) -> List:
    """
    Single Ticker Option Price
    """

    try:
        ticker = yf.Ticker(symbol)
        option = ticker.option_chain(expiry)
        
    except ValueError:
        raise

    if join:
        data = option.calls.set_index("strike").join(option.puts.set_index("strike"),
                                                    on = "strike",
                                                    how = "inner",
                                                    lsuffix = "_calls",
                                                    rsuffix = "_puts")
    else:
        data = _process_option_data(option=option, expiry=expiry, symbol=symbol, range=range)

    return data

def get_option_price_multiple(batch: List[Tuple[str,str]], 
                              range: int = 5) -> List:
    """
    Multiple Tickers Option Price 
    (Multi-threaded implementation)
    batch should be a list of symbol-expiry pair : [("TSLA",2025-06-01), ("NVDA",2025-06-07),...]
    """
    data_all = []
    threads = []

    for job in batch:
        symbol = job[0]
        expiry = job[1]
        t = threading.Thread(target=_download_and_process, args=(data_all,symbol,expiry,range))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    return data_all

def _download_and_process(data_all : List, 
                          symbol : str, 
                          expiry : str, 
                          range : int) -> None:
    """
    Download and process raw option data 
    """ 
    ticker = yf.Ticker(symbol)
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
    time_of_snapshot = datetime.now(UTC)
    
    calls = option.calls
    puts = option.puts

    if not calls.empty:
        calls["call_put"] = 'c'
        if not calls[calls.inTheMoney == True].empty:
            
            atm_idx = calls [calls.inTheMoney == True].iloc[-1:].index[0]
            calls['moneyness'] = calls.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
            calls.at[atm_idx, 'moneyness'] = 'a'

            if not range == None:
                start_index = (atm_idx-range) if (atm_idx-range)>0 else 0
                end_index = (atm_idx+range) if (atm_idx+range) < len(calls) else  len(calls)-1

                calls = calls.iloc[start_index : end_index]
        else:
            calls['moneyness'] = calls.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
            if not range == None:
                calls = calls.iloc[:range]

    
    if not puts.empty:
        puts["call_put"] = 'p'
        if not puts[puts.inTheMoney == True].empty:

            atm_idx = puts [puts.inTheMoney == True].iloc[:1].index[0]
            puts['moneyness'] = puts.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
            puts.at[atm_idx, 'moneyness'] = 'a'

            if not range == None:
                start_index = (atm_idx-range) if (atm_idx-range)>0 else 0
                end_index = (atm_idx+range) if (atm_idx+range) < len(puts) else  len(puts)-1

                puts = puts.iloc[start_index : end_index]
        else:
            puts['moneyness'] = puts.apply(lambda row :  'i' if row.inTheMoney else 'o' , axis=1)
            atm_idx = puts.iloc[-1:].index[0]
            if not range == None:
                puts = puts.iloc[-range:]

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
def get_market_cap(symbol: str) -> int:

    ticker = yf.Ticker(symbol)
    market_cap = ticker.info["marketCap"]
    
    return market_cap