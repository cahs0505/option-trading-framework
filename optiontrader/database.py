import yfinance as yf
import psycopg2
import psycopg2.pool
import psycopg2.errorcodes
import psycopg2.extensions

import os
import pandas as pd
import pandas_market_calendars as mcal
import datetime
import uuid
import functools

from psycopg2.extras import execute_values, register_uuid
from psycopg2 import sql
from dotenv import load_dotenv
from typing import List, Dict, Tuple
from decimal import Decimal
from optiontrader.constants import DataSource, SecurityType, OrderType, OptionSpread, Action, OrderStatus, OptionRight, Broker
from optiontrader.logger import logger
from optiontrader.exceptions import (
    DBConnectionException
)
from optiontrader.orders import (SpreadOrder, EquityOrder, OptionLeg)

load_dotenv(override=True)

CONNECTION_EXCEPTIONS = (
    psycopg2.errorcodes.CONNECTION_DOES_NOT_EXIST, 
    psycopg2.errorcodes.CONNECTION_EXCEPTION, 
    psycopg2.errorcodes.SQLCLIENT_UNABLE_TO_ESTABLISH_SQLCONNECTION,
    psycopg2.errorcodes.SQLCLIENT_UNABLE_TO_ESTABLISH_SQLCONNECTION
)

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
        register_uuid()
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
        self.pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, 
                                                        maxconn=10,
                                                        user=self.user_name,
                                                        password=self.password,
                                                        database=self.database_name,
                                                        host = self.host,
                                                        port = self.port)
        
    def disconnect(self) -> None:
        logger.info(f"Disconnecting from {self.database_name}") 
        self.pool.closeall()

    def with_cursor(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.pool == None:
                raise DBConnectionException('DB not connnected')
            conn = self.pool.getconn()
            try:
                with conn.cursor() as cursor:
                    result = func(self, cursor, *args, **kwargs)
                    
                conn.commit()
                return result
            
            except psycopg2.OperationalError as e:
                if e.pgcode in CONNECTION_EXCEPTIONS:
                    logger.error(f'Database connection error: {e.pgerror}')
                    raise DBConnectionException(e.pgerror)
                else:
                    logger.error(f'Database unexpected error: {e.pgerror}')
                    conn.rollback()
                    raise

            except Exception as e:
                logger.error(f'Database unexpected error: {e}')
                conn.rollback()
                raise

            finally:
                self.pool.putconn(conn)

        return wrapper


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

        except psycopg2.OperationalError as e:

            if e.pgcode in CONNECTION_EXCEPTIONS:
                logger.error(f'Database connection error: {e.pgerror}')
                raise DBConnectionException(e.pgerror)
            else:
                logger.error(f'Database unexpected error: {e.pgerror}')
                raise
                
        except psycopg2.Error as e:
            logger.error(f'Database unexpected error: {e.pgerror}')
            raise

        finally:
            cur.close()
            self.pool.putconn(conn)

    def get_latest_date_price_history_yf(self) -> str:

        if self.pool == None:
            raise DBConnectionException('DB not connnected')

        try:
            conn = self.pool.getconn()
            cur = conn.cursor()

            ##This should be re-implemented 
            sql = f"SELECT time FROM price_yf WHERE symbol = 'AAPL' AND time >= NOW() - INTERVAL '3 months' ORDER BY time DESC LIMIT 1;"
            cur.execute(sql)
            data = cur.fetchall()
            return data
        
        except psycopg2.OperationalError as e:

            if e.pgcode in CONNECTION_EXCEPTIONS:
                logger.error(f'Database connection error: {e.pgerror}')
                raise DBConnectionException(e.pgerror)
            else:
                logger.error(f'Database unexpected error: {e.pgerror}')
                raise
                
        except psycopg2.Error as e:
            logger.error(f'Database unexpected error: {e.pgerror}')
            raise

        finally:
            cur.close()
            self.pool.putconn(conn)
            
    @with_cursor
    def get_ohlc_5min_yf(self, cursor: psycopg2.extensions.cursor, symbol: str, history: int = 1 ):

        TABLE = 'ohlcv_5m_yf'
        query = sql.SQL("SELECT time,open,high,low,close,volume FROM {} WHERE symbol = %s;").format(
          sql.Identifier(TABLE), 
        )
        cursor.execute(query, (symbol,))
        data = cursor.fetchall()

        return data

    @with_cursor
    def update_ohlc_5min_yf(self, cursor: psycopg2.extensions.cursor, data: List[Tuple]) -> None:
    
        query = """
                INSERT INTO ohlcv_5m_yf (time,symbol,open,high,low,close,volume)
                VALUES %s
                ON CONFLICT (time, symbol)
                DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume;
                """
        execute_values(cursor, query, data)

    @with_cursor
    def create_tickers_overview(self, cursor: psycopg2.extensions.cursor, df: pd.DataFrame) -> None:
        
        if not df.empty:
            data = list(df[["symbol","market_cap","industry","sector","asset_type"]].itertuples(index=False, name=None))

            TABLE = "ticker"
            COLUMNS = ["symbol", "market_cap", "industry", "sector", "asset_type"]
            sql = f"""INSERT INTO {TABLE} ({','.join(COLUMNS)})VALUES %s;"""

            execute_values(cursor, sql, data)

    @with_cursor
    def get_tickers_overview(self, cursor: psycopg2.extensions.cursor) -> pd.DataFrame:

        sql = f"SELECT * FROM ticker"
        cursor.execute(sql)
        data = cursor.fetchall()
        df = pd.DataFrame(data)
        return df 

    @with_cursor
    def update_tickers_overview(self, cursor: psycopg2.extensions.cursor, symbol : str, market_cap: int) -> None:
        sql = """
                UPDATE ticker 
                SET market_cap = %(market_cap)s
                WHERE symbol = %(symbol)s;
                """
        value = {
            "market_cap" : market_cap,
            "symbol" : symbol,
        }
        cursor.execute(sql,value)

    @with_cursor
    def add_ticker(self, cursor: psycopg2.extensions.cursor, symbol : str) -> None:

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

        execute_values(cursor, sql, data)

    @with_cursor
    def get_symbols(self, cursor: psycopg2.extensions.cursor) -> List:
        sql = f"SELECT * FROM ticker ORDER BY market_cap DESC"
        cursor.execute(sql)
        data = [r[0] for r in cursor.fetchall()]

        return data 

    @with_cursor
    def create_option_table_yf(self, cursor: psycopg2.extensions.cursor) -> None:
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
        cursor.execute(sql)
        cursor.execute("SELECT create_hypertable('option_yf', 'time', 'symbol', number_partitions => 4);")

    @with_cursor
    def insert_option_data_yf(self,
                              cursor: psycopg2.extensions.cursor,
                              data: List) -> None:

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
        execute_values(cursor, sql, data)

    @with_cursor
    def get_option_data_yf(self,
                           cursor: psycopg2.extensions.cursor,
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
            
        TABLE = "option_yf"

        sql = f"""
            SELECT DISTINCT {','.join(columns)} FROM {TABLE} WHERE 
            symbol = %s AND 
            {"moneyness = 'a' AND" if atm_only is True else ""}
            {f"expiry = '{expiry}' AND" if expiry is not None else ""}
            call_put = 'c' 
            ORDER BY time;
        """

        cursor.execute(sql,(symbol,))            
        data = cursor.fetchall()

        df = pd.DataFrame(data, columns=columns)        
        df.set_index("time", inplace=True)
        df.index = pd.to_datetime(df.index, utc=True)
        df.drop_duplicates(inplace=True)

        return df

    @with_cursor
    def get_option_chain_latest_snapshot(self,
                                         cursor: psycopg2.extensions.cursor,
                                         symbol: str,
                                         expiry: str,
                                         columns: List
                                         ):

        TABLE = 'option_yf'
        query = sql.SQL(
            "SELECT {cols} FROM {table}" \
            "WHERE symbol = {symbol} and " \
            "expiry = {expiry} and " \
            "time_of_snapshot = "
                "(SELECT MAX(time_of_snapshot) " \
                "FROM {table} " \
                "WHERE symbol = {symbol} and " \
                "expiry = {expiry});"
                ).format(
                    cols = sql.SQL(', ').join(map(sql.Identifier, columns)),
                    table = sql.Identifier(TABLE),
                    symbol = sql.Literal(symbol),
                    expiry = sql.Literal(expiry)
                )
        
        cursor.execute(query)
        data = cursor.fetchall()

        return data
    
    @with_cursor
    def get_option_expiry_dates_yf(self,
                                   cursor: psycopg2.extensions.cursor,
                                   symbol: str) -> List:
            
        TABLE = 'option_yf'
        query = sql.SQL(
            "SELECT DISTINCT expiry FROM {table}" \
            "WHERE symbol = {symbol} and " \
            "moneyness = 'a' AND " \
            "call_put = 'c"
            ).format(
                table = sql.Identifier(TABLE),
                symbol = sql.Literal(symbol))
        
        cursor.execute(query)
        data = cursor.fetchall()
        data = list(map(lambda data : data[0],data))

        return data
    
    @with_cursor
    def get_earnings(self,
                     cursor: psycopg2.extensions.cursor,
                     symbol: str,
                     include_future: bool = True
                     ) -> pd.DataFrame:
    
        TABLE = 'earnings_nasdaq'
        COLUMNS = ['symbol',
                    'date',
                    'quarter',
                    'year',
                    'eps', 
                    'eps_forecast',
                    'time']
        
        if not include_future:
            sql = f"""
                    SELECT {','.join(COLUMNS)}
                    FROM {TABLE} 
                    WHERE symbol = %s 
                    AND date <= '{datetime.date.today().strftime('%Y-%m-%d')}';
                    """
        else:
            sql = f"""
                    SELECT {','.join(COLUMNS)}
                    FROM {TABLE} 
                    WHERE symbol = %s;
                    """
        cursor.execute(sql,(symbol,))

        data = cursor.fetchall()
        df = pd.DataFrame(data,columns=COLUMNS)
        df['date'] = pd.to_datetime(df['date'],utc=True)
        df.set_index("date",inplace=True)
        df.drop(columns=['symbol'],inplace=True)
        
        return df 

    @with_cursor
    def get_future_earnings(self,
                            cursor: psycopg2.extensions.cursor,
                            time_period: str = "1 MONTH"):

        COLUMNS = ['symbol',
                    'date',
                    'time']

        sql = f"""
                SELECT ticker.symbol,e.date,e.time  
                FROM earnings_nasdaq e INNER JOIN (SELECT symbol, market_cap FROM ticker ORDER BY market_cap DESC LIMIT 100) AS ticker  
                ON e.symbol = ticker.symbol 
                WHERE date >= NOW() - INTERVAL '1 DAY' AND date <= NOW() + INTERVAL '{time_period}' 
                ORDER BY date 
                """
        
        cursor.execute(sql)
        data = cursor.fetchall()
        df = pd.DataFrame(data,columns=COLUMNS)
        df['date'] = pd.to_datetime(df['date'],utc=True)
        df.set_index("date",inplace=True)
        
        return df 

    @with_cursor
    def upsert_earnings(self,
                        cursor: psycopg2.extensions.cursor,
                        data: List) -> None:
        
        if len(data) == 0:
            return
        
        TABLE = 'earnings_nasdaq'
        COLUMNS = ['symbol',
                    'date',
                    'quarter',
                    'year',
                    'eps', 
                    'eps_forecast',
                    'time']
        
        sql =  f"""
                INSERT INTO {TABLE} ({','.join(COLUMNS)}) 
                VALUES %s
                ON CONFLICT (symbol, quarter, year) DO UPDATE 
                SET (time,date,eps,eps_forecast) = (EXCLUDED.time,EXCLUDED.date,EXCLUDED.eps,EXCLUDED.eps_forecast);
                """
        
        execute_values(cursor,sql,data)
  
    @with_cursor
    def add_ib_account_record(self, cursor: psycopg2.extensions.cursor, account_data: Tuple):
        COLUMNS = [
            'time',
            'net_liquidation',
            'available_funds',
            'gross_position',
            'unrealized_pnl',
            'realized_pnl',
            'daily_pnl'
        ]
        sql = f"""
            INSERT INTO account 
            ({','.join(COLUMNS)})
            VALUES (
            %s, 
            %s,
            %s, 
            %s, 
            %s, 
            %s, 
            %s
            ) 
            ON CONFLICT (time)
            DO UPDATE SET 
                net_liquidation = EXCLUDED.net_liquidation,
                available_funds = EXCLUDED.available_funds,
                gross_position = EXCLUDED.gross_position,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                realized_pnl = EXCLUDED.realized_pnl,
                daily_pnl = EXCLUDED.daily_pnl
            """
        cursor.execute(sql, account_data)

    @with_cursor
    def get_ib_account_records(self, cursor: psycopg2.extensions.cursor, columns: List):

        TABLE = 'account'
        col_identifiers = [sql.Identifier(col) for col in columns]
        table_identifier = sql.Identifier(TABLE)
        query = sql.SQL("SELECT {} FROM {} WHERE net_liquidation IS NOT NULL ORDER BY time").format(
                sql.SQL(', ').join(col_identifiers),
                table_identifier
                )
    
        cursor.execute(query)
        account_data = cursor.fetchall()

        return account_data
        
    @with_cursor
    def get_open_equity_orders(self, cursor: psycopg2.extensions.cursor) -> Dict[uuid.UUID, SpreadOrder]:
        def _process_equity_orders_data(data : List[Tuple]) -> Dict[uuid.UUID, SpreadOrder]:
            equity_orders = {}
            for order_data in data:
                order_id, broker_order_id, time, status, broker, order_type, security_type, symbol, quantity, action, average_price, limit_price, filled = order_data
                order = EquityOrder(
                    broker = Broker(broker),
                    security_type = SecurityType(security_type),
                    order_type = OrderType(order_type),
                    action = Action(action),
                    quantity = quantity,
                    limit_price = limit_price,
                    symbol = symbol
                )
                order.order_id = order_id
                order.broker_order_id = broker_order_id
                order.time = time
                order.status = OrderStatus(status)
                order.average_price = average_price
                order.filled = filled
                equity_orders[order_id] = order
            
            return equity_orders
    
        sql = f"""
                SELECT 
                order_id,
                broker_order_id,
                time,
                status,
                broker,
                order_type,
                security_type,
                symbol,
                quantity,
                action,
                average_price,
                limit_price,
                filled
                FROM equity_order
                WHERE status = 'Submitted'; 
                """
        
        cursor.execute(sql)
        order_data = cursor.fetchall()
        orders = _process_equity_orders_data(order_data)

        return orders
    
    @with_cursor
    def get_open_spread_orders(self, cursor: psycopg2.extensions.cursor) -> Dict[uuid.UUID, SpreadOrder]:
        def _process_spread_orders_data(data : List[Tuple]) -> Dict[uuid.UUID, SpreadOrder]:
            spread_orders = {}
            for order_data in data:
                order_id, broker_order_id, time, status, broker, order_type, spread_type, underlying_symbol, spread_order_quantity, spread_order_action, average_price, limit_price, strike, expiry, option_right, leg_action, leg_quantiy, filled = order_data
             
                if order_id not in spread_orders:
                    order = SpreadOrder(
                        broker = Broker(broker),
                        security_type = SecurityType.OPTION_SPREAD,
                        order_type = OrderType(order_type),
                        action = Action(spread_order_action),
                        quantity = spread_order_quantity,
                        limit_price = limit_price,
                        spread_type = OptionSpread(spread_type),
                        expiry = expiry,
                        underlying_symbol = underlying_symbol,
                        legs = [])
                    order.order_id = order_id
                    order.broker_order_id = broker_order_id
                    order.time = time
                    order.status = OrderStatus(status)
                    order.average_price = average_price
                    order.filled = filled
                    spread_orders[order_id] = order
              
                leg = OptionLeg(
                    action = Action(leg_action),
                    quantity = leg_quantiy,
                    strike = strike,
                    right = OptionRight.CALL if option_right == 'CALL' else OptionRight.PUT,
                    expiry= expiry.strftime('%Y-%m-%d')
                )
                order.legs.append(leg)
            
            return spread_orders
            
        sql = f"""
                SELECT 
                spread_order.order_id,
                broker_order_id,
                time,
                status,
                broker,
                order_type,
                spread_type,
                underlying_symbol,
                spread_order.quantity,
                spread_order.action,
                average_price,
                limit_price,
                strike,
                expiry,
                option_right,
                spread_order_legs.action,
                spread_order_legs.quantity,
                filled
                FROM spread_order JOIN spread_order_legs
                ON spread_order.order_id = spread_order_legs.order_id
                WHERE status = 'Submitted'; 
                """
            
        cursor.execute(sql)
        data = cursor.fetchall()
        orders = _process_spread_orders_data(data)

        return orders
                        
    @with_cursor
    def add_equity_order(self, cursor: psycopg2.extensions.cursor, order: EquityOrder):
        TABLE = 'equity_order'
        order_data = order.get_data_dict(stringify=True)
        columns = order_data.keys()
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(TABLE),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder(col) for col in columns)
        )
        
        cursor.execute(query, order_data)

    @with_cursor
    def add_spread_order(self, cursor: psycopg2.extensions.cursor, order: SpreadOrder):
        order_id = order.order_id
        SPREAD_ORDER_TABLE = 'spread_order'
        SPREAD_ORDER_COLUMNS = ['order_id',
                                'time',
                                'status',
                                'broker',
                                'broker_order_id',
                                'order_type',
                                'spread_type',
                                'underlying_symbol',
                                'quantity',
                                'filled',
                                'action',
                                'limit_price',
                                'average_price']
        spread_data = order.get_data_dict(stringify=True)

        spread_data = {k : spread_data[k] for k in SPREAD_ORDER_COLUMNS if k in spread_data}
        legs = order.get_legs_data()
        columns = spread_data.keys()
        spread_sql = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(SPREAD_ORDER_TABLE),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder(col) for col in columns)
        )
        
        SPREAD_ORDER_LEGS_TABLE = 'spread_order_legs'
        SPREAD_ORDER_LEGS_COLUMNS = ['order_id',
                                     'strike',
                                     'expiry',
                                     'option_right',
                                     'action',
                                     'quantity']
        
        legs_data = []
        for leg in legs:
            curr = []
            curr.append(order_id)
            for i in range(1,len(SPREAD_ORDER_LEGS_COLUMNS)):
                col = SPREAD_ORDER_LEGS_COLUMNS[i]
                curr.append(leg[col])
            legs_data.append(tuple(curr))
    
        legs_sql = f"""
                INSERT INTO {SPREAD_ORDER_LEGS_TABLE} 
                ({','.join(SPREAD_ORDER_LEGS_COLUMNS)})
                VALUES %s;
                """
    
        cursor.execute(spread_sql, spread_data)
        execute_values(cursor, legs_sql, legs_data)

    @with_cursor
    def update_equity_order(self, cursor: psycopg2.extensions.cursor, broker_order_id: int, **kwargs):
 
        set_clauses = []
        for column_name in kwargs.keys():
            clause = sql.SQL("{} = {}").format(
                sql.Identifier(column_name), 
                sql.Placeholder(column_name)
            )
            set_clauses.append(clause)

        set_string = sql.SQL(', ').join(set_clauses)

        TABLE = 'equity_order'
        query = sql.SQL("UPDATE {table} SET {set_items} WHERE broker_order_id = %(broker_order_id)s;").format(
            table = sql.Identifier(TABLE),
            set_items = set_string,
            broker_order_id = sql.Literal(broker_order_id)
        )
    
        query_params = {**kwargs, 'broker_order_id': broker_order_id}
        cursor.execute(query, query_params)

    @with_cursor
    def update_spread_order(self, cursor: psycopg2.extensions.cursor, broker_order_id: int, **kwargs):
 
        set_clauses = []
        for column_name in kwargs.keys():
            clause = sql.SQL("{} = {}").format(
                sql.Identifier(column_name), 
                sql.Placeholder(column_name)
            )
            set_clauses.append(clause)

        set_string = sql.SQL(', ').join(set_clauses)

        TABLE = 'spread_order'
        query = sql.SQL("UPDATE {table} SET {set_items} WHERE broker_order_id = %(broker_order_id)s;").format(
            table = sql.Identifier(TABLE),
            set_items = set_string,
            broker_order_id = sql.Literal(broker_order_id)
        )
    
        query_params = {**kwargs, 'broker_order_id': broker_order_id}
        cursor.execute(query, query_params)   

    @with_cursor
    def get_completed_spread_orders(self, cursor: psycopg2.extensions.cursor):
        def _process_spread_orders_data(data : List[Tuple]) -> Dict[uuid.UUID, SpreadOrder]:
            spread_orders = {}
            for order_data in data:
                order_id, broker_order_id, time, status, broker, order_type, spread_type, underlying_symbol, spread_order_quantity, spread_order_action, average_price, limit_price, strike, expiry, option_right, leg_action, leg_quantiy, filled = order_data
             
                if order_id not in spread_orders:
                    order = SpreadOrder(
                        broker = Broker(broker),
                        security_type = SecurityType.OPTION_SPREAD,
                        order_type = OrderType(order_type),
                        action = Action(spread_order_action),
                        quantity = spread_order_quantity,
                        limit_price = limit_price,
                        spread_type = OptionSpread(spread_type),
                        expiry = expiry,
                        underlying_symbol = underlying_symbol,
                        legs = [])
                    order.order_id = order_id
                    order.broker_order_id = broker_order_id
                    order.time = time
                    order.status = OrderStatus(status)
                    order.average_price = average_price
                    order.filled = filled
                    spread_orders[order_id] = order
              
                leg = OptionLeg(
                    action = Action(leg_action),
                    quantity = leg_quantiy,
                    strike = strike,
                    right = OptionRight.CALL if option_right == 'CALL' else OptionRight.PUT,
                    expiry= expiry.strftime('%Y-%m-%d')
                )
                order.legs.append(leg)
            
            return spread_orders
            
        sql = f"""
                SELECT 
                spread_order.order_id,
                broker_order_id,
                time,
                status,
                broker,
                order_type,
                spread_type,
                underlying_symbol,
                spread_order.quantity,
                spread_order.action,
                average_price,
                limit_price,
                strike,
                expiry,
                option_right,
                spread_order_legs.action,
                spread_order_legs.quantity,
                filled
                FROM spread_order JOIN spread_order_legs
                ON spread_order.order_id = spread_order_legs.order_id
                WHERE status = 'Filled'
                ORDER BY time DESC
                ; 
                """
            
        cursor.execute(sql)
        data = cursor.fetchall()
        orders = _process_spread_orders_data(data)

        return orders
    
    @with_cursor
    def get_completed_equity_orders(self, cursor: psycopg2.extensions.cursor):
        def _process_equity_orders_data(data : List[Tuple]) -> Dict[uuid.UUID, SpreadOrder]:
            equity_orders = {}
            for order_data in data:
                order_id, broker_order_id, time, status, broker, order_type, security_type, symbol, quantity, action, average_price, limit_price, filled = order_data
                order = EquityOrder(
                    broker = Broker(broker),
                    security_type = SecurityType(security_type),
                    order_type = OrderType(order_type),
                    action = Action(action),
                    quantity = quantity,
                    limit_price = limit_price,
                    symbol = symbol
                )
                order.order_id = order_id
                order.broker_order_id = broker_order_id
                order.time = time
                order.status = OrderStatus(status)
                order.average_price = average_price
                order.filled = filled
                equity_orders[order_id] = order
            
            return equity_orders
    
        sql = f"""
                SELECT 
                order_id,
                broker_order_id,
                time,
                status,
                broker,
                order_type,
                security_type,
                symbol,
                quantity,
                action,
                average_price,
                limit_price,
                filled
                FROM equity_order
                WHERE status = 'Filled'
                ORDER BY time DESC
                ; 
                """
        
        cursor.execute(sql)
        order_data = cursor.fetchall()
        orders = _process_equity_orders_data(order_data)

        return orders
     