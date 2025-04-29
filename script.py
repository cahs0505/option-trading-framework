from DataCollector import DataCollector
from Database import Database
import argparse
import logging

logging.basicConfig(level=logging.INFO)

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