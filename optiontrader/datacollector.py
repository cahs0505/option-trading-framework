import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
import time
import threading
import datetime
import queue
import pytz
import os

from optiontrader.database import Database
from optiontrader.datasource import nasdaq,yahoofinance
from optiontrader.logger import logger
from typing import List, Dict
from apscheduler.schedulers.background import BaseScheduler,BackgroundScheduler, BlockingScheduler
from apscheduler.job import Job

from dotenv import load_dotenv

load_dotenv(override=True)

class DataCollector:
    """
    Collect data through different API
    """
    db : Database
    proxies: Dict
    scheduler: BaseScheduler
    symbols: List
    symbols_set: set
    symbols_len: int
    is_market_open : bool
    exchange: mcal.MarketCalendar
    exchange_schedule: pd.DataFrame

    #we collect option data with expiry date 60 days ahead of now, reset every day
    option_updater: Job = None
    option_expiry_dates: Dict
    option_expiry_depth : datetime.datetime = datetime.datetime.now(pytz.timezone('US/Eastern')) +  datetime.timedelta(days = 365)                 
    option_queue : queue.Queue
    symbols_curr : int = 0
    exp_curr : int = 0

    #Utility job
    resetter: Job = None 
    on_market_pre_open: Job = None
    on_market_open: Job = None 
    on_market_close: Job = None 

    #Update general information 
    general_info_updater: Job = None
    general_info_curr: int = 0

    #We update earning information in this date range, reset every day
    earnings_updater: Job = None
    curr_earning_date: datetime.date = None
    lookahead_earning_date: datetime.date = None

    ohlhc_5m_job : Job = None

    def __init__(self,
                 db : Database,
                 blocking = False):
        
        if db == None:
            self.db = Database()
        else:
            self.db = db

        if blocking:
            self.scheduler = BlockingScheduler(timezone=pytz.timezone('US/Eastern'))
        else:
            self.scheduler = BackgroundScheduler(timezone=pytz.timezone('US/Eastern'))

        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        proxy_country = os.getenv("PROXY_COUNTRY")
        proxy_host = os.getenv("PROXY_HOST")
        logger.info(f"Using proxy: {proxy_host}")
        yf.set_config(proxy="PROXY_SERVER")
        self.proxies = {"http" :('http://user-%s-country-%s:%s@%s'%(proxy_username,proxy_country,proxy_password,proxy_host))}

    def connect_and_init(self,
                         symbols: List = None,
                         empty: bool = False) -> None:
        if self.db.pool == None:
            self.db.connect()

        if not empty:
            if symbols == None:
                self.symbols = self.db.get_symbols()
            else:
                self.symbols = symbols

        self.resetter = self.scheduler.add_job(self.reset, 'cron', hour=6)
        self.symbols_set = set(self.symbols)
        self.symbols_len = len(self.symbols)
        self.general_info_curr = 0
        self.curr_earning_date = datetime.date.today() - datetime.timedelta(days=5)
        self.lookahead_earning_date = datetime.date.today() + datetime.timedelta(days=60)

        self.exchange = mcal.get_calendar("NYSE")
        start = (datetime.date.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        end = (datetime.date.today() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        self.exchange_schedule = self.exchange.schedule(start_date=start, end_date=end)

        self.init_option_job_queue()
        self.init_jobs()

    def start(self) -> None :
        logger.info("Starting collector...")
        self.scheduler.start()

    def stop(self) -> None:
        logger.info("Shutting down...")
        if self.scheduler.running:
            self.scheduler.shutdown()

    def reset(self) -> None:
        logger.info("Resetting...")

        #remove everything
        self.option_queue = None
        self.remove_jobs()

        #re-init
        self.general_info_curr = 0
        self.curr_earning_date = datetime.date.today() - datetime.timedelta(days=10)
        self.lookahead_earning_date = datetime.date.today() + datetime.timedelta(days=60)
        self.option_expiry_depth = datetime.datetime.now(pytz.timezone('US/Eastern')) + datetime.timedelta(days=365)
        self.exchange = mcal.get_calendar('NYSE')
        start = (datetime.date.today() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        end = (datetime.date.today() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        self.schedule = self.exchange.schedule(start_date=start, end_date=end)
        self.init_option_job_queue()
        self.init_jobs()

    def init_option_job_queue(self) -> None:

        logger.info("Initing option job queue...")
        self.option_queue = queue.Queue()

        threads = []

        for symbol in self.symbols:
            t = threading.Thread(target=self._put_job_queue, args=(symbol,), name=symbol)
            threads.append(t)
       
        ## prevent rate-limiting, to be re-do
        for t in threads:
            time.sleep(0.5)
            t.start()

        for t in threads:
            t.join()

    def _put_job_queue(self, 
                       symbol: str) -> None:
        try:
            ticker = yf.Ticker(symbol,proxy=self.db.proxies)
            exp = ticker.options
        
            for e_str in exp:
                
                try:
                    e = datetime.datetime.strptime(e_str,"%Y-%m-%d").replace(tzinfo=pytz.timezone('US/Eastern'))
                    if e < self.option_expiry_depth:
                        logger.info(f"Putting {symbol} - {e_str} to job queue")
                        self.option_queue.put((symbol,e_str))
                    else:
                        break
                    
                except Exception as e:
                    logger.error(f"{symbol}: {e}")
                    continue

        except Exception as e:
                logger.error(f"{symbol}: {e}")

    def init_jobs(self) -> None:
        logger.info("initing jobs...")

        # on market open 
        self.on_market_open = self.scheduler.add_job(self.handle_market_open, 'cron', hour=9, minute=31)

        #ohlc_5m
        logger.info("Add job: ohlc_5m_yf ")
        self.ohlhc_5m_job = self.scheduler.add_job(self.update_ohlcv_5m_yf, 'interval', minutes = 1)

        # add option data updater
        logger.info(f"Open?: {self.check_open()}")
        if self.check_open() and self.option_updater is None:
             logger.info("Add job: option data updater")
             self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)
        
        # add general info updater
        logger.info("Add job: general info updater")
        self.general_info_updater = self.scheduler.add_job(self.update_general_info, 'interval', seconds=30)

        #earnings data
        logger.info("Add job: earning data ")
        self.earnings_updater = self.scheduler.add_job(self.update_earnings, 'interval', minutes = 2)

    def remove_jobs(self) -> None:
        logger.info("removing job...")

        if self.on_market_open is not None:
            logger.info("removing market open...")
            self.on_market_open.remove()
            self.on_market_open = None

        if self.option_updater is not None:
            logger.info("removing option updater...")
            self.option_updater.remove()
            self.option_updater = None

        if self.general_info_updater is not None:
            logger.info("removing general info updater...")
            self.general_info_updater.remove()
            self.general_info_updater = None

        if self.earnings_updater is not None:
            logger.info("removing earnings updater...")
            self.earnings_updater.remove()
            self.earnings_updater = None

        if self.ohlhc_5m_job is not None:
            logger.info("removing ohlhc_5m job...")
            self.ohlhc_5m_job.remove()
            self.ohlhc_5m_job = None

    def check_open(self) -> bool:
        self.is_market_open = self.exchange.is_open_now(self.exchange_schedule)
        return self.is_market_open

    def log_config(self) -> None:
        logger.info(f"Number of symbols: {self.symbols_len}")
        logger.info(f"Lookahead date for earning: {self.lookahead_earning_date}")
        logger.info(f"Option expiry depth: {self.option_expiry_depth}")

    def handle_market_open(self) -> None:
        if self.check_open() and self.option_updater is None :

            logger.info("Market-open: Starting option updater")
            self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)

        elif not self.check_open() :
            logger.info(f"Market-open: Market is not open today")
  
    def update_ohlcv_5m_yf(self) -> None:
        try:
            today = str(datetime.datetime.now(datetime.UTC).date())
            data = yahoofinance.get_price_history_multiple(
                self.symbols,
                history = None,
                start_date = today,
                end_date = None,
                interval = '5m'
            )
            self.db.update_ohlc_5min_yf(data)
        except Exception as e:
            logger.error(f'OHLCV_5m job encounter enexpected error: {e}')

    def update_option(self, 
                      BATCH_SIZE : int = 10) -> None: 
        if not self.option_queue.empty():

            job_batch : List = []

            for _ in range(BATCH_SIZE):

                job = self.option_queue.get()
                job_batch.append(job)

                if self.check_open():
                    self.option_queue.put(job)

                if self.option_queue.empty():
                    break
            
            logger.info(f"Option job batch:{job_batch}")

            try:
                data = yahoofinance.get_option_price_multiple(batch=job_batch,
                                                              range=20)
                self.db.insert_option_data_yf(data=data)

            except Exception as e:
                logger.error(f'Option updating job encounter enexpected error: {e}')
        
        else:
            logger.info("Empty job queue.")

        logger.info(f"Remaining number of job:{self.option_queue.qsize()} ")

    def update_general_info(self) -> None:
        symbol = self.symbols[self.symbols_curr]
        logger.info(f"Updating ticker general info: {symbol}")

        try:
            market_cap = yahoofinance.get_market_cap(symbol=symbol)
            self.db.update_tickers_overview(symbol=symbol,market_cap=market_cap)

        except Exception as e:
            logger.error(e)

        finally:
            self.symbols_curr = (self.symbols_curr+1)%self.symbols_len

    def update_earnings(self) -> None:
        date_string = self.curr_earning_date.strftime("%Y-%m-%d")
        logger.info(f"Getting earnings info at: {date_string}")
        try:
            data = nasdaq.get_earnings(date=date_string)
    
            data = [row for row in data if row[0] in self.symbols_set]

            self.db.upsert_earnings(data=data)

        except Exception as e:
            logger.error(e)

        finally:
            self.curr_earning_date += datetime.timedelta(days=1)
            if (self.curr_earning_date > self.lookahead_earning_date):
                self.curr_earning_date = datetime.date.today() - datetime.timedelta(days=5)