import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
import time
import threading
import logging
import datetime
import queue
import pytz
import os

from Database import Database
from datasource import nasdaq
from datasource import yahoofinance
from typing import List, Dict, Set
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.job import Job

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv(override=True)

"""
Collect data through different API
Timezone: UTC
"""

class DataCollector:
    
    db : Database
    proxies: Dict
    scheduler: BackgroundScheduler
    symbols: List
    symbols_set: set
    symbols_len: int
    is_market_open : bool

    #we collect option data with expiry date 60 days ahead of now, reset every day
    option_updater: Job = None
    option_expiry_dates: Dict
    option_expiry_depth : datetime.datetime = datetime.datetime.now(pytz.timezone('US/Eastern')) +  datetime.timedelta(days=60)                 
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

    def __init__(self,
                 db : Database):
        if db == None:
            self.db = Database()
        else:
            self.db = db

        self.scheduler = BackgroundScheduler(timezone=datetime.UTC)

        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        proxy_country = os.getenv("PROXY_COUNTRY")
        proxy_host = os.getenv("PROXY_HOST")
        logger.info(f"Using proxy: {proxy_host}")
        yf.set_config(proxy="PROXY_SERVER")
        self.proxies = {"http" :('http://user-%s-country-%s:%s@%s'%(proxy_username,proxy_country,proxy_password,proxy_host))}

    def connect_and_init(self,
                         empty: bool = False) -> None:
        if self.db.pool == None:
            self.db.connect()
        
        if not empty:
            self.resetter = self.scheduler.add_job(self.reset, 'cron', hour=2)
            self.symbols = self.db.get_symbols()
            self.symbols_set = set(self.symbols)
            self.symbols_len = len(self.symbols)
            self.general_info_curr = 0
            self.curr_earning_date = datetime.date.today() - datetime.timedelta(days=5)
            self.lookahead_earning_date = datetime.date.today() + datetime.timedelta(days=60)
            self.init_option_job_queue()
            self.init_jobs()

    def start(self) -> None :
        logger.info("Starting collector...")
        self.scheduler.start()

        # block
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.stop()

    def stop(self) -> None:
        logger.info("Shutting down...")
        self.scheduler.shutdown()

    def reset(self) -> None:
        logger.info("Resetting...")

        #remove everything
        self.option_queue = None
        self.remove_jobs()

        #re-init
        self.symbols = self.db.get_symbols()
        self.symbols_len = len(self.symbols)
        self.general_info_curr = 0
        self.curr_earning_date = datetime.date.today() - datetime.timedelta(days=5)
        self.lookahead_earning_date = datetime.date.today() + datetime.timedelta(days=60)
        self.option_expiry_depth = datetime.datetime.now(pytz.timezone('US/Eastern')) +  datetime.timedelta(days=60)
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
            logger.info(f"Handling {t.name} for job queue")
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

        # on market pre-open, open and close
        self.on_market_pre_open = self.scheduler.add_job(self.handle_market_pre_open, 'cron', hour=13, minute=15)
        self.on_market_open = self.scheduler.add_job(self.handle_market_open, 'cron', hour=13, minute=31)
        self.on_market_close = self.scheduler.add_job(self.handle_market_close, 'cron', hour=20, minute=1)

        # add option data updater
        if self.check_open() and self.option_updater is None:
             self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)
        
        # add general info updater
        self.general_info_updater = self.scheduler.add_job(self.update_general_info, 'interval', seconds=30)

        #earnings data
        # self.earnings_updater = self.scheduler.add_job(self.update_earnings, 'interval', seconds = 10)

    def remove_jobs(self) -> None:
        logger.info("removing job...")

        if self.on_market_pre_open is not None:
            logger.info("removing pre_open...")
            self.on_market_pre_open.remove()
            self.on_market_pre_open = None

        if self.on_market_open is not None:
            logger.info("removing market open...")
            self.on_market_open.remove()
            self.on_market_open = None

        if self.on_market_close is not None:
            logger.info("removing market close...")
            self.on_market_close.remove()
            self.on_market_close = None

        if self.option_updater is not None:
            logger.info("removing updater...")
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

    def check_open(self) -> bool:
        exchange = mcal.get_calendar("NYSE")
        start = (pd.Timestamp.utcnow() - pd.DateOffset(7)).strftime('%Y-%m-%d')
        end = (pd.Timestamp.utcnow() + pd.DateOffset(7)).strftime('%Y-%m-%d')

        schedule = exchange.schedule(start_date=start, end_date=end)

        self.is_market_open = exchange.is_open_now(schedule)
        
        return self.is_market_open

    def handle_market_pre_open(self) -> None:
        logger.info("Market-pre-open")
        self.check_open()

    def handle_market_open(self) -> None:
        if self.check_open() and self.option_updater is None :

            logger.info("Market-open: Starting option updater")
            self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)

        elif not self.check_open() :
            logger.info(f"Market-open: Market is not open today")
        
    def handle_market_close(self) -> None:
        logger.info("Market-close")
        self.check_open()
  
    """
    The actual methods that do the works
    """
    def update_price(self, 
                     BATCH_SIZE : int = 10) -> None:
        for i in range(0, len(self.symbols), BATCH_SIZE):

            logger.info(f"Handling batch at {i} to {i+BATCH_SIZE}")
            batch = self.symbols[i:i+BATCH_SIZE]
            threads = []
            for i in range(len(batch)):
                symbol = batch[i]
                
                t = threading.Thread(target=self.db.update_price_history_yf, name=symbol ,args=(symbol,))
                threads.append(t)
            
            for t in threads:
                t.start()

            for t in threads:
                t.join()

    def update_price_bulk(self) -> None:
        self.db.update_price_history_bulk_yf(self.symbols)

    def update_option(self, 
                      BATCH_SIZE : int = 10) -> None: 
        if not self.option_queue.empty():

            job_batch : List = []

            for _ in range(BATCH_SIZE):

                job = self.option_queue.get()
                job_batch.append(job)

                if self.is_market_open:
                    self.option_queue.put(job)

                if self.option_queue.empty():
                    break
            
            logger.info(f"Option job batch:{job_batch}")

            try:
                data = yahoofinance.get_option_price_multiple(batch=job_batch,
                                                              range=5,
                                                              proxies=self.proxies)
                self.db.insert_option_data_yf(data=data)

            except Exception as e:
                logger.error(e)
        
        else:
            logger.info("Empty job queue.")

        logger.info(f"Remaining number of job:{self.option_queue.qsize()} ")

    def update_general_info(self) -> None:
        symbol = self.symbols[self.symbols_curr]
        logger.info(f"Updating ticker general info: {symbol}")

        try:
            market_cap = yahoofinance.get_market_cap(symbol=symbol,proxies=self.proxies)
            self.db.update_tickers_overview(symbol=symbol,market_cap=market_cap)

        except Exception as e:
            logger.error(e)

        finally:
            self.symbols_curr = (self.symbols_curr+1)%self.symbols_len

    def update_earnings(self) -> None:
        date_string = self.curr_earning_date.strftime("%Y-%m-%d")

        try:
            data = nasdaq.get_earnings(date=date_string)
            data = [row for row in data if row[1] in self.symbols_set]
            self.db.upsert_earnings(data=data)

        except Exception as e:
            logger.error(e)

        finally:
            self.curr_earning_date += datetime.timedelta(days=1)
            if (self.curr_earning_date > self.lookahead_earning_date):
                self.curr_earning_date = datetime.date.today() - datetime.timedelta(days=5)
