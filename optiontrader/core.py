import datetime
import signal
import time
import os

from threading import Thread, Event
from ibapi.account_summary_tags import AccountSummaryTags

from optiontrader.database import Database
from optiontrader.IBKRClient.ib import IB
from optiontrader.logger import logger
from optiontrader.IBKRClient.requests import (
    AccountSummaryRequest,
    AccountUpdateRequest,
    PnLRequest,
    AccountOpenOrderRequest,
    AccountCompletedOrderRequest,
    ExecutionDetailRequest,
)
from optiontrader.deltahedge import DeltaHedgeEngine
from optiontrader.forecast import ForecastEngine
from optiontrader.rpc import RPCServer
from optiontrader.screener import Screener
from optiontrader.order_management import OrderManager
from optiontrader.util import get_time_to_expiry
from optiontrader.datasource.yahoofinance import get_spot_price
from optiontrader.exceptions import ResourceNotAvailableException

class Core:
    """
    Main instance of the trading bot. It launches and control thread for every modules.
    """
    db: Database
    ib: IB
    oms: OrderManager
    forecast_engine: ForecastEngine
    hedge_engine: DeltaHedgeEngine
    screener: Screener
    rbc_server: RPCServer
    
    active: bool
    shut_down_flag: Event

    def __init__(self):

        self.shut_down_flag = Event()
        self.db = Database(remote = True, use_proxy = False)
        self.ib = IB()
        self.oms = OrderManager(ib = self.ib, db = self.db)
        self.forecast_engine = ForecastEngine(db = self.db)
        self.hedge_engine = DeltaHedgeEngine(ib = self.ib, oms = self.oms, forecast_engine = self.forecast_engine)
        self.screener = Screener(db = self.db, forecast_engine = self.forecast_engine)
        self.rbc_server = RPCServer(ib = self.ib, db = self.db, screener = self.screener, forecast_engine = self.forecast_engine, oms = self.oms)
        signal.signal(signal.SIGINT, self.graceful_shutdown)
        signal.signal(signal.SIGTERM, self.graceful_shutdown)

    def connect(self) -> None:
        """
        Connect to broker and database
        """
        self.db.connect()
        self.connect_ib()

    def connect_ib(self) -> None:
        self.ib.setConnectOptions('+PACEAPI')
        while not self.ib.isConnected() and not self.shut_down_flag.wait(timeout=5):
            logger.info('Attempting to connect ib')
            self.ib.connect(os.environ.get('IB_HOST'), 
                            int(os.environ.get('IB_PORT')), 
                            0)
        logger.info('IB connected and inited')

    def graceful_shutdown(self, signum, frame):
        """
        Shut down gracefully by handling signals
        """
        logger.info(f"\n[!] Signal {signum} received. Cleaning up resources...")
        self.shutdown()

    def shutdown(self) -> None:
        """
        Shut down and clean up resources
        """
        logger.info('Shutting down core...')
        self.shut_down_flag.set()
        self.hedge_engine.shut_down_flag.set()
        self.screener.shut_down_flag.set()
        self.ib.disconnect()
        self.db.disconnect()
        self.rbc_server.close()
        logger.info('Everything stopped')

    def start(self) -> None:
        """
        Start every module 
        """
        self.ib_thread = Thread(target=self.ib.run)
        self.ib_thread.start()

        self.main_loop_t = Thread(target=self.main_loop)
        self.main_loop_t.start()

        self.init_ib_t = Thread(target=self.init_ib)
        self.init_ib_t.start()
        
        self.hedge_engine_t = Thread(target=self.hedge_engine.run)
        self.hedge_engine_t.start()

        self.screener_t = Thread(target=self.screener.run)
        self.screener_t.start()

        self.rbc_server_t = Thread(target=self.rbc_server.start)
        self.rbc_server_t.start()

        self.forecast_engine.get_forecast()

    def init_ib(self):
        while True:
            time.sleep(0.1)
            if self.ib.is_connected():
                    try:
                        self.ib.reqMarketDataType(3)
                        self.ib.make_request(AccountSummaryRequest(groupName='All',tags=AccountSummaryTags.AllTags))
                        self.ib.make_request(AccountUpdateRequest(subscribe=True, acctCode='DU6734746'))
                        self.ib.make_request(PnLRequest('DU6734746',''))
                        break
                    except Exception as e:
                        continue
                
    def compute_position_greeks(self):
        """
        Compute the greeks for current position
        """
        position_expiries = self.ib.account_data.get_option_expiries()
        sigma_forecasts = {}
        for exp in position_expiries:
            dte = get_time_to_expiry(exp,as_day=True)
            sigma_forecasts[exp] = self.forecast_engine.get_forecast(dte)
        spot = get_spot_price('SPY')['close']
        self.ib.account_data.compute_option_position_greeks(spot = spot, sigmas=sigma_forecasts)

    
    def save_account_data(self) -> None:
        """
        Save account data to db
        """
        try:
            account = self.ib.get_account()
            data = (
                datetime.datetime.now(datetime.UTC).date(),
                account.net_liquidation,
                account.available_funds,
                account.gross_position_value,
                account.unrealized_PnL,
                account.realized_PnL,
                account.daily_PnL
            )
            self.db.add_ib_account_record(data)
        except Exception as e:
            logger.error(f'Unexpected error when saving account data: {e}')

    def log_account(self) -> None:
        """
        Log account detail
        """
        account_data = self.ib.get_account_summary_json()
        logger.info(account_data)

    def log_position(self) -> None:
        """
        Log position
        """
        logger.info('Positions and Greeks:')
        for position in self.ib.account_data.get_portfolio().values():
            logger.info(position)
        try:
            delta, gamma, theta, vega, rho = self.ib.get_position_greeks()
            logger.info(f'delta: {delta:.2f} gamma: {gamma:.2f} theta: {theta:.2f} vega: {vega:.2f} rho: {rho:.2f}')
        except ResourceNotAvailableException:
            pass
        
    def log_orders(self) -> None:
        """
        Log open and completed orders
        """
        logger.info('Open Orders:')
        for id, order in self.oms.get_open_orders().items():
            logger.info(order)

        logger.info('Completed Orders:')
        for order in self.ib.get_completed_orders().values():
            logger.info(order)

    def main_loop(self) -> None:
        """
        Main loop at the core level
        """
        while not self.shut_down_flag.wait(timeout=5):
            try:
                if self.ib.is_connected():
                    self.ib.make_request(AccountCompletedOrderRequest())
                    self.ib.make_request(AccountOpenOrderRequest())
                    self.ib.make_request(ExecutionDetailRequest())
                    self.save_account_data()
                    self.compute_position_greeks()
                    self.log_position()
                    self.log_account()
                    self.log_orders()
                   
                else:
                    logger.error('IB disconnected')
                    self.active = False
                    logger.info('Attempting to reconnect...')
                    self.connect_ib()

            except Exception as e:
                logger.error(f'Unexpected error in main loop: {e.with_traceback(None)}')