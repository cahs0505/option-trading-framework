import logging
import time
import os
import argparse
import datetime
from threading import Thread

from ibapi.common import * # @UnusedWildImport
from ibapi.order_condition import * # @UnusedWildImport
from ibapi.contract import * # @UnusedWildImport
from ibapi.order import * # @UnusedWildImport
from ibapi.order_state import * # @UnusedWildImport
from ibapi.execution import Execution
from ibapi.execution import ExecutionFilter
from ibapi.commission_report import CommissionReport
from ibapi.ticktype import * # @UnusedWildImport
from ibapi.tag_value import TagValue
from IBKRContract import IBKRContract
from IBKRRequest import *

from Program import TestApp


def SetupLogger():
    if not os.path.exists("log"):
        os.makedirs("log")

    time.strftime("pyibapi.%Y%m%d_%H%M%S.log")

    recfmt = '(%(threadName)s) %(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s'

    timefmt = '%y%m%d_%H:%M:%S'

    # logging.basicConfig( level=logging.DEBUG,
    #                    format=recfmt, datefmt=timefmt)
    logging.basicConfig(filename=time.strftime("log/pyibapi.%y%m%d_%H%M%S.log"),
                        filemode="w",
                        level=logging.INFO,
                        format=recfmt, datefmt=timefmt)
    logger = logging.getLogger()
    console = logging.StreamHandler()
    console.setLevel(logging.ERROR)
    logger.addHandler(console)

SetupLogger()
logging.debug("now is %s", datetime.datetime.now())
logging.getLogger().setLevel(logging.ERROR)

cmdLineParser = argparse.ArgumentParser("api tests")
# cmdLineParser.add_option("-c", action="store_True", dest="use_cache", default = False, help = "use the cache")
# cmdLineParser.add_option("-f", action="store", type="string", dest="file", default="", help="the input file")
cmdLineParser.add_argument("-p", "--port", action="store", type=int,
                            dest="port", default=7497, help="The TCP port to use")
cmdLineParser.add_argument("-C", "--global-cancel", action="store_true",
                            dest="global_cancel", default=False,
                            help="whether to trigger a globalCancel req")
args = cmdLineParser.parse_args()
print("Using args", args)
logging.debug("Using args %s", args)
# print(args)


# enable logging when member vars are assigned
from ibapi import utils
Order.__setattr__ = utils.setattr_log
Contract.__setattr__ = utils.setattr_log
DeltaNeutralContract.__setattr__ = utils.setattr_log
TagValue.__setattr__ = utils.setattr_log
TimeCondition.__setattr__ = utils.setattr_log
ExecutionCondition.__setattr__ = utils.setattr_log
MarginCondition.__setattr__ = utils.setattr_log
PriceCondition.__setattr__ = utils.setattr_log
PercentChangeCondition.__setattr__ = utils.setattr_log
VolumeCondition.__setattr__ = utils.setattr_log

# from inspect import signature as sig
# import code code.interact(local=dict(globals(), **locals()))
# sys.exit(1)

# tc = TestClient(None)
# tc.reqMktData(1101, IBKRContract.USStockAtSmart(), "", False, None)
# print(tc.reqId2nReq)
# sys.exit(1)



try:
    app = TestApp()

    def client(app:TestApp):
        print("Start client thread")

        while True:

            time.sleep(30)
            try:
                if app.isConnected():
                    app.make_request(AccountOpenOrderRequest())
                    app.account.print_account_summary()
                    app.account.print_portfolio()
                    app.account.print_all_orders()
            except Exception as e:
                print(e)

    def market_data(app:TestApp):
        time.sleep(60)
        print("requesting market data")

    
        contract  = IBKRContract.USStockAtSmart(symbol="TSLA")
        req1 = MarketDataRequest(contract=contract,
                                 genericTickList="",
                                 snapshot=False,
                                 regulatorySnapshot=False)
        

        try:
            if app.isConnected():
                app.reqMarketDataType(1)
                time.sleep(30)
                app.make_request(request=req1)

        except Exception as e:
                print(e)

    if args.global_cancel:
        app.globalCancelOnly = True
    # ! [connect]
    app.setConnectOptions("+PACEAPI")
    print("Waiting for IBC/TWS to initialize...")

    host = "127.0.0.1"
    port = 7497
    while not app.isConnected():

        try:
            print(f"Attempting to connect: {host}:{port}")

            app.connect(host, port, clientId=0)
            time.sleep(10)
        except Exception as e:
            print(f"Unexpected error: {e}")
            continue
            

    # ! [connect]
    print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                    app.twsConnectionTime()))


    # ! [clientrun]
    
    main_running_thread = Thread(target=app.run)
    main_running_thread.start()
    client_thread = Thread(target=client,args=(app,))
    client_thread.start()

    data_thread = Thread(target=market_data,args=(app,))
    data_thread.start()

    # req1 = AccountSummaryRequest("All",AccountSummaryTags.AllTags)
    # app.make_request(req1)

    main_running_thread.join()

    # ! [clientrun]

except:
    print("interrupteddd1")
    
finally:
    print("interrupteddd2")
    app.stop()
    app.disconnect()
    # app.dumpTestCoverageSituation()
    # app.dumpReqAnsErrSituation()