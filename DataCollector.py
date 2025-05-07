import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
import time
import threading
import logging
import datetime
import queue
import pytz

from Database import Database
from typing import List, Dict
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.job import Job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCollector:
    
    db : Database
    scheduler: BackgroundScheduler
    symbols: List
    is_market_open : bool

    option_expiry_dates: Dict
    option_expiry_depth : datetime.datetime = datetime.datetime.now(pytz.timezone('US/Eastern')) +  datetime.timedelta(days=60)                 
    option_queue : queue.Queue
    symbols_curr : int = 0
    exp_curr : int = 0

    price_updater: Job = None 
    option_updater: Job = None
    on_market_pre_open: Job = None
    on_market_open: Job = None 
    on_market_close: Job = None 


    def __init__(self,
                 db : Database):
        
        if db == None:
            self.db = Database()
        else:
            self.db = db

        self.scheduler = BackgroundScheduler(timezone=datetime.UTC)

    def connect_and_init(self) -> None:

        if self.db.pool == None:
            self.db.connect()
        
        self.symbols = self.db.get_symbols()
        self.init_option_job_queue()

    def init_option_job_queue(self) -> None:

        self.option_queue = queue.Queue()

        threads = []

        for symbol in self.symbols:
            t = threading.Thread(target=self._put_job_queue, args=(symbol,))
            threads.append(t)
       
        for t in threads:
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


    def start(self) -> None :

        #every day after market close
        # self.price_updater = self.scheduler.add_job(self.update_price_bulk, 'cron', hour=20, minute=15)


        # on market pre-open, open and close
        self.on_market_pre_open = self.scheduler.add_job(self.handle_market_pre_open, 'cron', hour=13, minute=15)
        self.on_market_open = self.scheduler.add_job(self.handle_market_open, 'cron', hour=13, minute=31)
        self.on_market_close = self.scheduler.add_job(self.handle_market_close, 'cron', hour=20, minute=1)

        # add option updater
        if self.check_open():
             self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)

        self.scheduler.start()

        # block
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
            self.db.disconnect()
        
    def shutdown(self) -> None:
        self.db.disconnect()

    def get_expiration_dates(self, 
                             depth : int = 3) -> List:
        
        ticker = yf.Ticker("MSFT",proxy=self.db.proxies)
        exp = ticker.options    

        self.option_expiry_depth = depth
        self.option_expiry_dates = exp[0:depth]

        return self.option_expiry_dates

    
    def check_open(self) -> bool:
        
        exchange = mcal.get_calendar("NYSE")
        start = (pd.Timestamp.utcnow() - pd.DateOffset(7)).strftime('%Y-%m-%d')
        end = (pd.Timestamp.utcnow() + pd.DateOffset(7)).strftime('%Y-%m-%d')

        schedule = exchange.schedule(start_date=start, end_date=end)

        self.is_market_open = exchange.is_open_now(schedule)
        
        return self.is_market_open

    def handle_market_pre_open(self) -> None:

        self.init_option_job_queue()
        self.check_open()

    def handle_market_open(self) -> None:

        if self.check_open() and self.option_updater is None :

            logger.info(f"Starting option updater")
            self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)

        elif not self.check_open() :
            logger.info(f"Market is not open today")
        
    def handle_market_close(self) -> None:

        self.check_open()
  
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

            self.db.insert_option_price_bulk_yf(job_batch)
        
        else:
            logger.info("Empty job queue.")

    def update_overview(self,
                        BATCH_SIZE : int = 10) -> None:
        
        for i in range(0, len(self.symbols), BATCH_SIZE):

            logger.info(f"Handling batch at {i} to {i+BATCH_SIZE}")
            batch = self.symbols[i:i+BATCH_SIZE]
            threads = []
            for i in range(len(batch)):
                symbol = batch[i]
                
                t = threading.Thread(target=self.db.update_tickers_overview, name=symbol ,args=(symbol,))
                threads.append(t)
            
            for t in threads:
                t.start()

            for t in threads:
                t.join()
