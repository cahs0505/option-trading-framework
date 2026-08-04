import uuid
import time
from datetime import datetime
from optiontrader.constants import OrderStatus, OrderType, OptionRight, SecurityType
from optiontrader.IBKRClient.ib import IB
from optiontrader.IBKRClient.contracts import IBContract
from optiontrader.IBKRClient.order import IBOrder
from optiontrader.IBKRClient.requests import ContractDetailRequest, RequestStatus
from optiontrader.IBKRClient.exceptions import *
from optiontrader.database import Database
from optiontrader.logger import logger
from optiontrader.orders import (BaseOrder, EquityOrder, SpreadOrder)
from decimal import Decimal
from optiontrader.option import OptionData
from ibapi.order import Order
from typing import Dict, Tuple

class OrderManager():
    """
    All orders are submitted through the order managers.
    Handles the interfacing with Broker. Also write order data to db
    """

    ib:IB
    db:Database
    orders: Dict[uuid.UUID, BaseOrder]

    def __init__(self, ib:IB, db:Database):
        self.ib = ib
        self.ib.add_order_update_callback(self.update_order_data)
        self.db = db
        self.orders = {}

    def place_order(self, order: BaseOrder):
        try:
            #Construct IB Order structure
            if isinstance(order,EquityOrder):
                ib_contract = self._generate_ib_equity_order(order)
            elif isinstance(order,SpreadOrder):
                ib_contract = self._generate_ib_spread_contract(order)
            ib_order = self._generate_ib_order(order)
            order_data = IBOrder()
            order_data.contract = ib_contract
            order_data.order = ib_order

            #Submit to IB and get the status
            broker_client_id = self.ib.place_order(order_data)
            ib_order_data = self.ib.get_order_data(broker_client_id)
            order_status = ib_order_data.status
            broker_order_id = ib_order_data.perm_id
            while order_status == OrderStatus.INIT or broker_order_id == 0:
                time.sleep(0.1)
                order_status = self.ib.get_order_status(broker_client_id)
                broker_order_id = ib_order_data.order.permId
            if order_status == OrderStatus.REJECTED:
                raise IBOrderExcepton('Order is rejected by IB')
            else:
                order.set_status(order_status)

            #Save the sucessful Order
            logger.info('Order successfully submitted.')
            order.broker_order_id = broker_order_id
            self.orders[order.order_id] = order
            if isinstance(order,EquityOrder):
                self.db.add_equity_order(order)
            elif isinstance(order,SpreadOrder):
                self.db.add_spread_order(order)
            return order
        
        except IBDisconnectedException:
            logger.error('IB is disconnected, cannot submit order')
            raise
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            raise        

    def cancel_order(self, broker_order_id: int, security_type: SecurityType):
        try:
            ib_open_orders = self.ib.get_open_orders()
            order_id = None
            for client_id, order_data in ib_open_orders.items():
                if order_data.order_id == broker_order_id:
                    order_id = client_id 
                    break
            if order_id == None:
                raise IBOrderExcepton('Order ID Not Found')
            
            self.ib.cancel_order(client_id)

            if security_type == SecurityType.OPTION_SPREAD:
                self.db.update_spread_order(broker_order_id = broker_order_id, status = str(OrderStatus.CANCELLED))
            else:
                self.db.update_equity_order(broker_order_id = broker_order_id, status = str(OrderStatus.CANCELLED))
            return broker_order_id
            
        except IBDisconnectedException:
            logger.error('IB is disconnected, cannot cancel')
            raise
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            raise
    
    def update_order_data(self, **kwargs):
        if not kwargs:
            return
        try:
            security_type = kwargs.pop('security_type')            
            if security_type == 'BAG':
                self.db.update_spread_order(**kwargs)
            else:
                self.db.update_equity_order(**kwargs)

        except IBDisconnectedException:
            logger.error('IB is disconnected, cannot update')
            raise
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            raise

    def get_open_orders(self) -> Dict[uuid.UUID, BaseOrder]:
        try:
            data = {}
            
            #get order records from db
            equity_orders = self.db.get_open_equity_orders()
            spread_orders = self.db.get_open_spread_orders()
  
            #validate data with ib 
            ib_open_orders = self.ib.get_open_orders()
            for id,order in equity_orders.items():
                broker_id = order.broker_order_id
                for ib_id,ib_order in ib_open_orders.items():
                    if broker_id == ib_order.order_id:
                        data[id] = order

            for id,order in spread_orders.items():
                broker_id = order.broker_order_id
                for ib_id,ib_order in ib_open_orders.items():
                    if broker_id == ib_order.order_id:
                        data[id] = order

            return data
        except IBDisconnectedException:
            logger.error('IB is disconnected, cannot update')
            raise
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            raise

    def get_completed_orders(self) -> Dict[uuid.UUID, BaseOrder]:
        try:
            equity_orders = self.db.get_completed_equity_orders()
            spread_orders = self.db.get_completed_spread_orders()
            return equity_orders | spread_orders
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            raise     
        
    def _generate_local_symbol(
        underlying_symbol: str,
        expiry: str,
        strike: Decimal,
        right: OptionRight
        ) -> str:
        _exp_obj = datetime.strptime(expiry, "%Y-%m-%d")
        _exp = datetime.strftime(_exp_obj, '%y%m%d')
        _right =  'C' if right == OptionRight.CALL else 'P'
        _strike = str(strike*1000).split('.')[0]
        return f'{underlying_symbol}   {_exp}{_right}00{_strike}'

    def _generate_ib_spread_contract(self, spread_order:SpreadOrder):

        try:
            req_id = self._subscribe_con_id_request(spread_order)
        except IBDisconnectedException:
            raise
        
        con_id_dict = {}
        for leg in spread_order.legs:
            curr_key = (leg.right , leg.strike)
            con_id_dict[curr_key] = -1

        success = False
        n = len(con_id_dict)

        while not success:
            self._get_con_id(req_id,con_id_dict)
            success_count = 0
            for k,v in con_id_dict.items():
                if v != -1:
                    success_count+=1
            if success_count == n:
                success = True
            time.sleep(0.1)

        legs_data = []
        for leg in spread_order.legs:
            _key = (leg.right , leg.strike)
            _con_id = con_id_dict[_key]
            _action = leg.action.value
            _quantity = leg.quantity
            legs_data.append({
                'con_id':_con_id,
                'action': _action,
                'quantity': _quantity
            })

        ib_contract = IBContract.OptionComboContract(
            symbol = spread_order.underlying_symbol,
            legs = legs_data
        )

        return ib_contract
    
    def _generate_ib_equity_order(self, equity_order: EquityOrder):
        sec_type = equity_order.security_type
        symbol = equity_order.symbol
        if sec_type == SecurityType.STOCK:
            ib_contract = IBContract.USStock(symbol)
        elif sec_type == SecurityType.ETF:
            ib_contract = IBContract.etf(symbol)
        return ib_contract
    
    def _generate_ib_order(self, base_order: BaseOrder):

        match base_order.order_type:
            case OrderType.LIMIT:
                order = Order()
                order.action = base_order.action.value
                order.orderType = OrderType.LIMIT
                order.totalQuantity = int(base_order.quantity)
                price = base_order.limit_price
                order.lmtPrice = price
            case OrderType.MARKET:
                order = Order()
                order.action = base_order.action.value
                order.orderType = OrderType.MARKET
                order.totalQuantity = int(base_order.quantity)
            case OrderType.MID:
                order = Order()
                order.action = base_order.action.value
                order.orderType = OrderType.MID
                order.totalQuantity = int(base_order.quantity)

        return order

    def _subscribe_con_id_request(self, spread_order: SpreadOrder):
        underlying = spread_order.underlying_symbol
        expiry = spread_order.legs[0].expiry
        expiry = expiry.replace('-','')
        contract = IBContract.OptionForQuery(underlying)
        contract.lastTradeDateOrContractMonth = expiry
        contract_req = ContractDetailRequest(contract)

        try:
            req_id = self.ib.make_request(contract_req)
        except IBDisconnectedException:
            raise

        return req_id
    
    def _get_con_id(self, 
                    req_id:int, 
                    con_id_dict: Dict[Tuple ,OptionData]):

        while self.ib.handled_requests[req_id].status != RequestStatus.RESPONDED and self.ib.handled_requests[req_id].status != RequestStatus.FINISHED and self.ib.handled_requests[req_id].status != RequestStatus.ERROR:
            continue

        for _con_detail in self.ib.contract_details[req_id]:
            curr_key = (OptionRight.CALL if _con_detail.contract.right == 'C' else OptionRight.PUT ,
                         Decimal(_con_detail.contract.strike))
            if curr_key in con_id_dict:
                con_id_dict[curr_key] = _con_detail.contract.conId

        return con_id_dict