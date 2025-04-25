import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
import time
import threading
import logging
import datetime
import queue
import argparse

from Database import Database
from typing import List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.job import Job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCollector:
    
    db : Database
    scheduler: BackgroundScheduler
    symbols: List
    is_market_open : bool

    option_expiry_dates: List
    option_expiry_depth : int
    option_queue : queue.Queue
    symbols_curr : int = 0
    exp_curr : int = 0


    job_manager : Job = None 
    price_updater: Job = None 
    on_market_open: Job = None 
    on_market_close: Job = None 


    def __init__(self,
                 db : Database):
        
        if db == None:
            self.db = Database()
        else:
            self.db = db

        self.scheduler = BackgroundScheduler(timezone=datetime.UTC)
        self.option_queue = queue.Queue()

    def connect_and_init(self) -> None:

        if self.db.pool == None:
            self.db.connect()
        
        self.symbols = self.db.get_symbols()
        self.option_expiry_dates = self.get_expiration_dates()

        for exp in self.option_expiry_dates:
            for symbol in self.symbols:
                job = (symbol,exp)
                self.option_queue.put(job)

     
    def start(self) -> None :

        #every day after market close
        # self.price_updater = self.scheduler.add_job(self.update_price_bulk, 'cron', hour=20, minute=15)

        # on market open and on market close
        self.on_market_open = self.scheduler.add_job(self.handle_market_open, 'cron', hour=13, minute=1)
        self.on_market_close = self.scheduler.add_job(self.handle_market_close, 'cron', hour=20, minute=30)

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

    def get_expiration_dates(self, 
                             depth : int = 3) -> List:
        
        ticker = yf.Ticker("MSFT",proxy=self.db.proxies)
        exp = ticker.options    

        self.option_expiry_depth = depth
        self.option_expiry_dates = exp[0:depth]

        return self.option_expiry_dates

    
    def check_open(self) -> bool:
        
        exchange = mcal.get_calendar("NYSE")
        start = (pd.Timestamp.utcnow() - pd.DateOffset(1)).strftime('%Y-%m-%d')
        end = (pd.Timestamp.utcnow() + pd.DateOffset(1)).strftime('%Y-%m-%d')
        schedule = exchange.schedule(start_date=start, end_date=end)

        self.is_market_open = exchange.is_open_now(schedule)
        
        return self.is_market_open

    
    def handle_market_open(self):

        if self.check_open() and self.option_updater is None :

            logger.info(f"Starting option updater")
            self.option_updater = self.scheduler.add_job(self.update_option, 'interval', seconds=15)
        
    def handle_market_close(self):

        if not self.check_open() and self.option_updater is not None:

            logger.info(f"Shutting down option updater")
            self.option_updater.remove()
            self.option_updater = None
  
    def update_price(self, 
                     BATCH_SIZE : int = 10):
        
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

    def update_price_bulk(self):
        self.db.update_price_history_bulk_yf(self.symbols)

            
    def update_option(self, 
                      BATCH_SIZE : int = 5) -> None: 
    
        batch = self.symbols[self.symbols_curr : self.symbols_curr + BATCH_SIZE]
        expiry = self.option_expiry_dates[self.exp_curr]

        self.db.insert_option_price_yf(batch,expiry)

        self.symbols_curr += BATCH_SIZE
        if self.symbols_curr >= len(self.symbols):
            self.symbols_curr = 0
            self.exp_curr = (self.exp_curr + 1) % len(self.option_expiry_dates)

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
        


        


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-r', action='store_true')
    parser.add_argument('-p', action='store_true')
    args = parser.parse_args()
    
    db = Database(remote = args.r,
                  use_proxy = args.p)
    
    dc = DataCollector(db)
    dc.connect_and_init()
    print(dc.db.get_symbols())
    dc.start()
