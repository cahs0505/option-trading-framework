from optiontrader.datacollector import DataCollector
from optiontrader.database import Database
from optiontrader.logger import logger
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-r', action='store_true', help="Use remote database")
parser.add_argument('-p', action='store_true', help="Use proxy")
args = parser.parse_args()

if __name__ == '__main__':
    
    db = Database(remote = args.r, use_proxy = args.p)
    scraper = DataCollector(db=db,blocking=True)

    try:
        db.connect()
        symbols = ['SPY','QQQ','NVDA','TSLA','MSFT','PLTR','AAPL','META','AMZN',]
        scraper.connect_and_init(symbols)
        scraper.start()

    except (KeyboardInterrupt, SystemExit):
        logger("Disconnecting")
        scraper.stop()
        db.disconnect()
