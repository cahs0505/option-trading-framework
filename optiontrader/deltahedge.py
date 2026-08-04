import numpy as np

from threading import Event
from typing import Dict

from optiontrader.logger import logger
from optiontrader.config import config
from optiontrader.constants import Action,OrderType,Broker,SecurityType
from optiontrader.IBKRClient.ib import IB
from optiontrader.IBKRClient.exceptions import IBAccountNotReadyException, IBDisconnectedException
from optiontrader.forecast import ForecastEngine
from optiontrader.order_management import OrderManager, EquityOrder
from optiontrader.exceptions import ResourceNotAvailableException

DELTA_MARGIN = config.DELTA_MARGIN
HEDGE_FREQ = config.HEDGE_FREQ

class DeltaHedgeEngine:
    """
    Compute position delta, and dynamically hedge the position
    """
    symbol = 'SPY'
    ib: IB
    oms: OrderManager
    forecast_engine: ForecastEngine
    shut_down_flag: Event

    def __init__(self, ib: IB, oms: OrderManager, forecast_engine: ForecastEngine):
        self.ib = ib
        self.oms = oms
        self.forecast_engine = forecast_engine
        self.shut_down_flag = Event()

    def run(self):
        """
        Main loop of the hedge engine
        """
        while not self.shut_down_flag.wait(timeout=HEDGE_FREQ):
            try:
                position_delta = self.ib.get_position_greeks()[0]
                order_delta = self.get_order_delta()
                net_delta = position_delta + order_delta
                logger.info(f'Position Delta: {position_delta}')
                logger.info(f'Order_delta: {order_delta}')
                logger.info(f'Net Delta:{net_delta}')
                self.hedge(net_delta)
            except IBDisconnectedException:
                logger.error('IB disconnected, cannot hedge')
            except ResourceNotAvailableException:
                logger.error('Postion greeks not available, continue')
            except Exception as e:
                logger.error(f'Unexpected error in hedge main loop :{e.with_traceback(None)}')

        if self.shut_down_flag.is_set():
            logger.info('Hedge engine stopped')
    
    def get_order_delta(self) -> Dict[str, float]:
        """
        Compute the delta for unfilled orders
        """
        total_delta = 0
        for k,v in self.ib.get_open_orders().items():
            if v.remaining != 0:
                action = 1 if v.order.action == 'BUY' else -1   
                if v.contract.secType == 'STK':
                    total_delta += np.float64(v.remaining) * action

                #delta for unfilled option order is not considered
                elif v.contract.secType == 'BAG' or v.contract.secType == 'OPT':
                    continue

        return total_delta       
    
    def get_net_delta(self, position_delta: Dict, order_delta: Dict) -> Dict[str, float]:
        """
        Get the net delta
        """
        data = dict(position_delta)
        for k,v in order_delta.items():
            if k in data:
                data[k] += order_delta[k]
            else:
                data[k] = order_delta[k]

        return data

    def hedge(self, net_delta) -> None:
        """
        Hedge the position
        """
        if np.abs(net_delta) >= DELTA_MARGIN:
            if net_delta < 0:
                action = Action.BUY
            else:
                action = Action.SELL
            quantity = int(np.abs(net_delta))
            order = EquityOrder(
                broker = Broker.IBKR,
                security_type = SecurityType.ETF,
                order_type = OrderType.MID,
                action = action,
                quantity = quantity,
                limit_price = None,
                symbol = self.symbol 
            )
            try:
                logger.info(f'Hedging: {action} {self.symbol} {quantity}')
                self.oms.place_order(order)
            except (IBDisconnectedException, IBAccountNotReadyException):
                logger.error('IB is disconnected, hedge order is not placed')
            except Exception as e:
                logger.error(f'Unexpected error encountered when hedging: {e}')