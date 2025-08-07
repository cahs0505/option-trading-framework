from optiontrader.DataCollector import DataCollector
from optiontrader.Database import Database
import argparse
import logging


logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument('-r', action='store_true', help="Use remote database")
parser.add_argument('-p', action='store_true', help="Use proxy")
parser.add_argument('-d', action='store_true', help="Debug mode")
args = parser.parse_args()

if args.d:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    db = Database(remote = args.r, use_proxy = args.p)
    scraper = DataCollector(db)
    scraper.connect_and_init()
    print(scraper.db.get_symbols())
    scraper.start()
