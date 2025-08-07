import yfinance as yf
import psycopg2
import psycopg2.pool
import os
import pandas as pd
import numpy as np
import pandas_market_calendars as mcal
import logging
import threading

from psycopg2.extras import execute_values
from dotenv import load_dotenv
from typing import List, Dict
from optiontrader.Constants import DataSource
from optiontrader.util import validate_date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv(override=True)

"""
PostgreSQL with TimescaleDB extension
"""
class Database:

    ##Basic database config
    database_name : str
    user_name: str
    password: str
    source: DataSource
    pool: psycopg2.pool.ThreadedConnectionPool
    remote: bool
    use_proxy: bool

    #Timezone information
    nyse: mcal.market_calendar.MarketCalendar

    #Proxies
    proxies : Dict

    def __init__(self, 
                 remote : bool = False,
                 use_proxy: bool = False):
        
        if remote:
            self.database_name = os.getenv("DATABASE_NAME")
            self.user_name = os.getenv("DATABASE_USER")
            self.password = os.getenv("DATABASE_PASSWORD")
            self.host = os.getenv("DATABASE_HOST")
            self.port = os.getenv("DATABASE_PORT")
        else:
            self.database_name = os.getenv("DATABASE_NAME_LOCAL")
            self.user_name = os.getenv("DATABASE_USER_LOCAL")
            self.password = os.getenv("DATABASE_PASSWORD_LOCAL")
            self.host = os.getenv("DATABASE_HOST_LOCAL")
            self.port = os.getenv("DATABASE_PORT_LOCAL")

        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        proxy_country = os.getenv("PROXY_COUNTRY")
        proxy_host = os.getenv("PROXY_HOST")

        self.remote = remote
        self.use_proxy = use_proxy
        self.source = DataSource.LOCAL
        self.pool = None
    
        self.nyse = mcal.get_calendar('NYSE')

        if self.use_proxy:
            logger.info(f"Using proxy: {proxy_host}")
            yf.set_config(proxy="PROXY_SERVER")
            self.proxies = {"http" :('http://user-%s-country-%s:%s@%s'%(proxy_username,proxy_country,proxy_password,proxy_host))}
        else:
            logger.info("Use without proxy")
            self.proxies = None
        
    def connect(self) -> None:
        logger.info(f"Connecting...")
        logger.info(f"Host: {self.host}")
        logger.info(f"Database: {self.database_name}")
        logger.info(f"Port: {self.port}")
        logger.info(f"Username: {self.user_name}")
        self.pool = psycopg2.pool.ThreadedConnectionPool(minconn=10, 
                                                        maxconn=10,
                                                        user=self.user_name,
                                                        password=self.password,
                                                        database=self.database_name,
                                                        host = self.host,
                                                        port = self.port)
        
    def disconnect(self) -> None:
        logger.info(f"Disconnecting from {self.database_name}") 
        self.pool.closeall()
        self.pool = None

    def set_source(self, 
                   source: DataSource) -> None:
        self.source = source

    """
    YFinance
    """
    #OHLCV data using YFinance
    def create_price_table_yf(self) -> None:
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            sql = f"""
                        CREATE TABLE price_yf (
                        time TIMESTAMPTZ NOT NULL,
                        symbol TEXT NOT NULL,
                        open REAL,
                        close REAL,
                        high REAL,
                        low REAL,
                        volume INTEGER
                        );
                   """

            cur.execute(sql)
            cur.execute("SELECT create_hypertable('price_yf', 'time', 'symbol');")
            conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error for: {e}")
            
        finally:
            cur.close()
            self.pool.putconn(conn)


    def create_price_history_yf(self,
                            symbol: str) -> None:
        
        logger.info(f"Creating price history: {symbol}")

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
            return
        
        try:
            sql = f"SELECT EXISTS(SELECT 1 FROM price_yf WHERE symbol='{symbol}')"
            cur.execute(sql)
            data = cur.fetchone()
            
            if(data[0]):
                logger.info(f"Price history already exists: {symbol}")
                
            else:
                ticker = yf.Ticker(symbol,proxy=self.proxies)

                df = ticker.history('max')

                if df.empty:
                    logger.error(f"Fetch failed, empty data: {symbol}")
                    return
                    # raise ApiError(f"Fetch failed, empty data: {symbol}")
                
                df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume" :"volume", "Dividends" : "dividends", "Stock Splits": "splits"},inplace=True)
                df['symbol'] = symbol
                df.index = (df.index+ pd.DateOffset(hours=16)).tz_convert("UTC")

                data = list(df[['open','high','low','close','volume','symbol']].itertuples(index=True, name=None))

                TABLE = "price_yf"
                COLUMNS = ["time", "open", "high", "low", "close", "volume","symbol"]
                sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

                execute_values(cur, sql, data)  
                conn.commit()
                logger.info(f"Price history created: {symbol}")

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error for {symbol}: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)
        

    def get_price_history_yf(self,
                        symbol: str,
                        columns: List,
                        history: str = None
                        ) -> pd.DataFrame:
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
            return

        try:
            sql = f"SELECT {','.join(columns)} FROM price_yf WHERE symbol = %s AND TIME>=NOW() - INTERVAL %s ORDER BY time;"
            cur.execute(sql,(symbol,history))
            data = cur.fetchall()
            df = pd.DataFrame(data, columns=columns)        
            df.set_index("time", inplace=True)
            df.drop_duplicates(inplace=True)
            df.index = pd.to_datetime(df.index, utc=True)
            return df

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error for {symbol}: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)

    def get_latest_date_price_history_yf(self) -> str:

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            ##This should be re-implemented 
            sql = f"SELECT time FROM price_yf WHERE symbol = 'AAPL' AND time >= NOW() - INTERVAL '3 months' ORDER BY time DESC LIMIT 1;"
            cur.execute(sql)
            data = cur.fetchall()
            return data
        
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")

        finally:
            self.pool.putconn(conn)
            
    
    def update_price_history_yf(self,
                             symbol: str) -> None:
        
        logger.info(f"Updating price history: {symbol}")

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            logger.debug(f"Checking last row: {symbol}")
            sql = f"SELECT time FROM price_yf WHERE symbol = %s AND time >= NOW() - INTERVAL '100 days' ORDER BY time DESC LIMIT 1;"
            cur.execute(sql,(symbol,))
            data = cur.fetchall()
            logger.debug(data)
            if len(data) == 0:
                self.create_price_history_yf(symbol)
                return
            
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
            self.pool.putconn(conn)
            return 

        try:
            last = pd.Timestamp(data[0][0]).tz_convert("UTC")
            last_string = last.strftime("%Y-%m-%d")

            logger.debug(f"Last row: {symbol} - {last_string}")

            now = pd.Timestamp.utcnow()
            now_string = now.strftime("%Y-%m-%d")

            ######to extend to all exchange######
            range = self.nyse.schedule(start_date=last_string, end_date=now_string)

            #drop first row (which is last row in db)
            if(len(range) == 1):
                logger.info(f"Price history already updated: {symbol}")
                return
            range = range.iloc[1:]

            #drop last row if not yet market close
            if(now < range.iloc[-1].market_close):
                if(len(range) == 1):
                    logger.info(f"Price history already updated: {symbol}")
                    return
                else:
                    range = range[:-1]
            

            ##add one day to to_string because how yfinance work (end date is not included)
            from_string = range.market_close.iloc[0].strftime("%Y-%m-%d")
            to_string = (range.market_close.iloc[-1]+ pd.DateOffset(1)).strftime("%Y-%m-%d")
    
            if not range.empty: 

                logger.debug(f"Fetching for: {symbol}")
                ticker = yf.Ticker(symbol,proxy=self.proxies)
                df = ticker.history(interval="1d", start=from_string, end=to_string)
                
                if df.empty:
                    logger.error(f"Fetch failed, empty data: {symbol}")
                    return

                df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume" :"volume", "Dividends" : "dividends", "Stock Splits": "splits"},inplace=True)
                df['symbol'] = symbol
                df.index = (df.index+ pd.DateOffset(hours=16)).tz_convert("UTC")
    
                
                if not df.empty: 
                    data = list(df[['open','high','low','close','volume','symbol']].itertuples(index=True, name=None))

                    TABLE = "price_yf"
                    COLUMNS = ["time", "open", "high", "low", "close", "volume", "symbol"]
                    sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

                    execute_values(cur, sql, data)  
                    conn.commit()
            
            else:
                logger.info(f"Price history already updated: {symbol}")

            logger.info(f"Price history updated: {symbol}")

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error for {symbol}: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)
        

    def update_price_history_bulk_yf(self,
                                     symbols : List) -> None:

        logger.info(f"Updating price : {symbols} ")
        number = len(symbols)

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            logger.debug(f"Checking last row")

            ##This should be re-implemented (keep a meta-table for last update)
            sql = f"SELECT time FROM price_yf WHERE symbol = 'AAPL' AND time >= NOW() - INTERVAL '3 months' ORDER BY time DESC LIMIT 1;"
            cur.execute(sql)
            data = cur.fetchall()
            
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
            self.pool.putconn(conn)
            return 

        try:
            last = pd.Timestamp(data[0][0]).tz_convert("UTC")
            last_string = last.strftime("%Y-%m-%d")

            logger.debug(f"Last row:{last_string}")

            now = pd.Timestamp.utcnow()
            now_string = now.strftime("%Y-%m-%d")

            ######to extend to all exchange######
            range = self.nyse.schedule(start_date=last_string, end_date=now_string)

            #drop first row (which is last row in db)
            if(len(range) == 1):
                logger.info(f"Price history already updated")
                return
            range = range.iloc[1:]

            #drop last row if not yet market close
            if(now < range.iloc[-1].market_close):
                if(len(range) == 1):
                    logger.info(f"Price history already updated")
                    return
                else:
                    range = range[:-1]
            

            ##add one day to to_string because how yfinance work (end date is not included)
            from_string = range.market_close.iloc[0].strftime("%Y-%m-%d")
            to_string = (range.market_close.iloc[-1]+ pd.DateOffset(1)).strftime("%Y-%m-%d")
            
            data = []

            if not range.empty: 
                logger.debug(f"Fetching for: {number}")
                df = yf.download(symbols, period='3mo',start=from_string,end=to_string,proxy=self.proxies)
                df = df[~(df.index < from_string)]
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
                        except ValueError as e:
                            logger.error(f"{symbol} does not exist")
                        except Exception as e:
                            logger.error(f"{symbol}: unexpected error")
                        finally:
                            continue
                
                    TABLE = "price_yf"
                    COLUMNS = ["time", "open", "high", "low", "close", "volume", "symbol"]
                    sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

                    execute_values(cur, sql, data)  
                    conn.commit()
                        
            else:
                logger.info(f"Price history already updated ({number})")

            logger.info(f"Price history updated ({number})")

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error for {symbols}: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)


    #overview of all tickers
    def create_tickers_overview(self,
                                df: pd.DataFrame) -> None:
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            if not df.empty:
                data = list(df[["symbol","market_cap","industry","sector","asset_type"]].itertuples(index=False, name=None))

                TABLE = "ticker"
                COLUMNS = ["symbol", "market_cap", "industry", "sector", "asset_type"]
                sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

                execute_values(cur, sql, data)
                conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)

    def get_tickers_overview(self) -> pd.DataFrame:

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
    
            sql = f"SELECT * FROM ticker"
            cur.execute(sql)
            data = cur.fetchall()
            df = pd.DataFrame(data)
            return df 

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)
    
    def update_tickers_overview(self,
                               symbol : str,
                               market_cap: str) -> None:
        
        logger.info(f"Updating ticker overview: {symbol}")
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            ticker = yf.Ticker(symbol,proxy=self.proxies)
            market_cap = ticker.info["marketCap"]
            sql = """
                    UPDATE ticker 
                    SET market_cap = %(market_cap)s
                    WHERE symbol = %(symbol)s;
                """
            value = {
                "market_cap" : market_cap,
                "symbol" : symbol,
            }
            cur.execute(sql,value)
            conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    def get_sec_filing(self,
                       symbol: str) -> List:
        
        logger.info(f"Getting sec filing: {symbol}")

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            sql = "SELECT date FROM sec_filing WHERE symbol = %(symbol)s ORDER BY date DESC;"
            value = {
                "symbol": symbol,
            }
            cur.execute(sql,value)
            data = cur.fetchall()
            data = list(map(lambda tuple : tuple[0],data))
      
            return data

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    def update_sec_filing(self,
                       symbol: str) -> None:
       
        logger.info(f"Updating sec filing info: {symbol}")

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            TABLE = "sec_filing"
            COLUMNS = ["symbol","type","date"]            
            sql = f"SELECT * FROM {TABLE} WHERE symbol = %(symbol)s ORDER BY date DESC LIMIT 1;"
            value = {
                "symbol" : symbol,
            }
            cur.execute(sql,value)
            last_row = cur.fetchone()

            if last_row != None:
                
                last_date = last_row[2]

                ticker = yf.Ticker(symbol,proxy=self.proxies)
                data = list(filter(lambda d : (d["type"] == "10-Q" and d["date"]>last_date),ticker.sec_filings))

                if len(data)>0:
                    data_all = []
                    for d in data:
                        data_all.append((symbol,"10Q",d["date"]))
                    
                    sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

                    cur.execute(sql,data_all)
                    conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)

    def add_ticker(self, symbol : str) -> None:

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            ticker = yf.Ticker(symbol,proxy=self.proxies)

            TABLE = "ticker"
            COLUMNS = ["symbol",
                       "market_cap",
                       "asset_type",
                       "industry",
                       "sector"]
            
            data=[(symbol,
                   ticker.info['marketCap'] if 'marketCap' in ticker.info else None,
                   ticker.info['quoteType'] if 'quoteType' in ticker.info else None,
                   ticker.info['industry'] if 'industry' in ticker.info else None,
                   ticker.info['sector'] if 'sector' in ticker.info else None,
                   )]
                  
            sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

            execute_values(cur, sql, data)
            conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    def remove_ticker(self, symbol : str) -> None:
        pass

    def get_symbols(self) -> List:

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            sql = f"SELECT * FROM ticker ORDER BY market_cap DESC"
            cur.execute(sql)
            data = [r[0] for r in cur.fetchall()]

            return data 

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    #option data
    def create_option_table_yf(self) -> None:

        try:

            conn = self.pool.getconn()
            cur = conn.cursor()
            
            sql = f"""CREATE TABLE option_yf (
                        time_of_snapshot TIMESTAMPTZ NOT NULL,
                        time TIMESTAMPTZ NOT NULL,
                        contract TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        strike REAL NOT NULL,
                        expiry DATE NOT NULL,
                        call_put CHAR(1) NOT NULL,
                        last_price REAL,
                        bid REAL,
                        ask REAL,
                        volume INTEGER,
                        open_interest INTEGER,
                        moneyness CHAR(1)
                        implied_volatility REAL,
                    );
            """

            cur.execute(sql)
            cur.execute("SELECT create_hypertable('option_yf', 'time', 'symbol', number_partitions => 4);")
            conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    def insert_option_data_yf(self,
                              data: List) -> None:
        
        logger.info(f"Inserting  option data (size:{len(data)})")

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            TABLE = "option_yf"
            COLUMNS = ["time_of_snapshot",
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
                       "implied_volatility"]
            
            sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""
            execute_values(cur, sql, data)
            conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
         
        finally:
            cur.close()
            self.pool.putconn(conn)
        
    def get_option_data_yf(self,
                           symbol: str,
                           columns: List = ["time",
                                        "contract",
                                        "strike",
                                        "expiry",
                                        "call_put",
                                        "last_price",
                                        "volume",
                                        "open_interest",
                                        "moneyness",
                                        "bid",
                                        "ask",
                                        "implied_volatility",
                                        "time_of_snapshot"
                                        ],
                           expiry: str = None,
                           atm_only : bool = True) -> pd.DataFrame:
        
        logger.debug(f"Getting option data: {symbol}")
  
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            
            TABLE = "option_yf"
            
            sql = f"""
                SELECT DISTINCT {','.join(columns)} FROM {TABLE} WHERE 
                {"expiry = %s AND" if expiry is not None else ""}
                symbol = %s AND 
                {"moneyness = 'a' AND" if atm_only is True else ""}
                call_put = 'c' 
                ORDER BY time;
            """

            cur.execute(sql,(expiry,symbol))
            conn.commit()
            
            data = cur.fetchall()

            df = pd.DataFrame(data, columns=columns)        
            df.set_index("time", inplace=True)
            df.index = pd.to_datetime(df.index, utc=True)
            df.drop_duplicates(inplace=True)

            return df

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    def get_option_expiry_dates_yf(self,
                                   symbol: str) -> pd.DataFrame:
        
        logger.info(f"Getting option expiry: {symbol}")
  
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            
            TABLE = "option_yf"
            
            sql = f"""
                SELECT DISTINCT expiry FROM {TABLE} WHERE 
                symbol = %s AND 
                moneyness = 'a' AND 
                call_put = 'c' 
            """

            cur.execute(sql,(symbol,))
            conn.commit()
            
            data = cur.fetchall()
            data = list(map(lambda data : data[0],data))

            return data

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)

    """
    Polygon API
    """

    """
    Nasdaq API
    """
    def create_earnings(self) -> None:

        try:

            conn = self.pool.getconn()
            cur = conn.cursor()
            
            sql = """
                        CREATE TABLE earnings_nasdaq (
                        symbol TEXT NOT NULL REFERENCES ticker(symbol),
                        date DATE NOT NULL,
                        fiscal_quarter_ending CHAR(8) NOT NULL,
                        eps NUMERIC(6,2),
                        eps_forecast NUMERIC(6,2),
                        PRIMARY KEY (symbol, date)
                        );

                """

            cur.execute(sql)
            conn.commit()

        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")

        finally:
            cur.close()
            self.pool.putconn(conn)

    def get_earnings(self,
                     symbol: str = None) -> pd.DataFrame:
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            TABLE = "earnings_nasdaq"

            COLUMNS = [ "symbol",
                        "date",
                        "fiscal_quarter_ending",
                        "eps", 
                        "eps_forecast"]
            
            sql = f"""
                SELECT * FROM {TABLE} 
                WHERE 
                symbol = %s;
                """
            cur.execute(sql,(symbol,))
            conn.commit()

            data = cur.fetchall()
            df = pd.DataFrame(data,columns=COLUMNS)
            return df 
        
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)
    
    def upsert_earnings(self,
                        data: List) -> None:
        
        if len(data) == 0:
            return
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            TABLE = "earnings_nasdaq"
            COLUMNS = [ "date",
                        "symbol",
                        "eps", 
                        "eps_forecast",
                        "fiscal_quarter_ending"]
            
            sql =  f"""
                    INSERT INTO {TABLE} ({','.join(COLUMNS)}) 
                    VALUES %s
                    ON CONFLICT (date,symbol,fiscal_quarter_ending) DO UPDATE 
                    SET (eps,eps_forecast) = (EXCLUDED.eps, EXCLUDED.eps_forecast);
                    """
            
            execute_values(cur,sql,data)
            conn.commit()
            
        except psycopg2.Error as e:
            logger.error(f"Psycopg2 error: {e}")
        
        finally:
            cur.close()
            self.pool.putconn(conn)