import datetime
import logging
import json

from threading import Lock
from decimal import Decimal
from typing import Dict, List, Tuple, Callable, Set

from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.utils import (
    iswrapper,
    floatMaxString,
    intMaxString,
    decimalMaxString,
    setattr_log
)
from ibapi.common import (
    TickerId,
    OrderId,
    SetOfString,
    SetOfFloat,
    TickAttrib
) 
from ibapi.order_condition import (
    ExecutionCondition,
    TimeCondition,
    MarginCondition,
    PriceCondition,
    PercentChangeCondition,
    VolumeCondition
)
from ibapi.contract import (
    DeltaNeutralContract,
    Contract,
    ContractDetails,
)
from ibapi.order import (
    Order
)
from ibapi.order_cancel import (
    OrderCancel
)
from ibapi.order_state import (
    OrderState
)
from ibapi.execution import (
    Execution,
    ExecutionFilter
)
from ibapi.ticktype import (
    TickType
)
from ibapi.tag_value import TagValue
from optiontrader.IBKRClient.order import (
    IBOrder,
    IB_STATUS_MAP
)
from optiontrader.IBKRClient.requests import (
    RequestStatus,
    RequestType,
    BaseRequest
)
from optiontrader.IBKRClient.exceptions import (
    IBDisconnectedException,
    IBAccountNotReadyException,
    OrderNotFoundException
)
from optiontrader.constants import OrderStatus

from optiontrader.IBKRClient.account import IBAccount
from optiontrader.IBKRClient.tick import Tick, TickTypeArray
from optiontrader.logger import logger
from optiontrader.exceptions import ResourceNotAvailableException

#These error codes are not considered real error
EXEMPTED_ERROR_CODE = (
    2104,
    2106,
    2158,
    10167
)

class IBClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)

class IBWrapper(EWrapper):
    def __init__(self):
        EWrapper.__init__(self)

class IB(IBWrapper, IBClient):
    """
    Interface for Interactive Broker.
    """
    Order.__setattr__ = setattr_log
    Contract.__setattr__ = setattr_log
    DeltaNeutralContract.__setattr__ = setattr_log
    TagValue.__setattr__ = setattr_log
    TimeCondition.__setattr__ = setattr_log
    ExecutionCondition.__setattr__ = setattr_log
    MarginCondition.__setattr__ = setattr_log
    PriceCondition.__setattr__ = setattr_log
    PercentChangeCondition.__setattr__ = setattr_log
    VolumeCondition.__setattr__ = setattr_log

    logging.getLogger('ibapi').setLevel(logging.ERROR)

    started: bool
    next_valid_order_id : int
    data_ready: bool

    #Request Management
    handled_requests: Dict[int,BaseRequest]
    request_lock: Lock
    nextMarketDataId : int
    nextMarketDataTypeId: int
    nextOptionChainId: int
    nextMarketDepthId : int
    nextContractDetailId: int
    nextRealTimeBarId : int
    nextHistoricalDataId : int
    nextAccountSummaryId : int
    nextAccountUpdateId: int
    nextPnLId : int
    nextPnLSingleId : int

    #Account
    account_data: IBAccount
    account_time: str

    #Contract Details
    contract_details: Dict[int, List[ContractDetails]]

    #Order
    open_orders: Dict[int, IBOrder]
    completed_orders: Dict[int, IBOrder]
    order_lock: Lock
    _order_update_callbacks: Set[Callable]

    #Market Data, Ticks
    market_data_type: int
    ticks: Dict[int, Tick]

    def __init__(self):
        IBWrapper.__init__(self)
        IBClient.__init__(self, wrapper=self)

        self.started = False
        self.next_valid_order_id = None
        self.data_ready = False

        self.handled_requests = {}             
        self.request_lock = Lock()                

        self.nextMarketDataId = 1000
        self.nextMarketDataTypeId = 1100
        self.nextOptionChainId = 1200
        self.nextMarketDepthId = 2000
        self.nextContractDetailId = 2100
        self.nextRealTimeBarId = 3000
        self.nextHistoricalDataId = 4000
        self.nextAccountSummaryId = 9000
        self.nextAccountUpdateId = 9100
        self.nextExecutionDetailId = 10001
        self.nextPnLId = 17000
        self.nextPnLSingleId = 18000

        self.account_data = IBAccount()
        self.account_time = None

        self.contract_details = {}

        self.open_orders = {}
        self.completed_orders = {}
        self.order_lock = Lock()
        self._order_update_callbacks = set()

        self.ticks = {}

    def make_request(self, request: BaseRequest) -> int:
        """
        Make requests to IB (other than placing order) and return request id to user. Requests are handles synchronously.
        """
        if not self.isConnected():
            raise IBDisconnectedException('API is disconnected')
        
        if not self.account_data.account_ready and (request.type != RequestType.ACCOUNT_SUMMARY and request.type != RequestType.ACCOUNT_UPDATE):
            raise IBAccountNotReadyException('Account is not ready')
        
        #If identical request was made, return that id
        for k,v in self.handled_requests.items():
            if v == request:
                return k         
       
        with self.request_lock:

            match request.type:

                case RequestType.MARKET_DATA:
                    reqId = self.nextMarketDataId
                    self.reqMktData(reqId, 
                                    request.contract,
                                    request.genericTickList,
                                    request.snapshot,
                                    request.regulatorySnapshot,
                                    [])
                    self.ticks[reqId] = Tick(reqId,request.contract)
                    self.nextMarketDataId += 1

                case RequestType.MARKET_DATA_TYPE:
                    reqId = self.nextMarketDataTypeId
                    self.reqMarketDataType(marketDataType=request.market_data_type)
                    self.nextMarketDataTypeId += 1
                
                case RequestType.OPTION_CHAIN:
                    reqId = self.nextOptionChainId
                    self.reqSecDefOptParams(reqId,
                                            request.underlyingSymbol,
                                            request.futFopExchange,
                                            request.underlyingSecType,
                                            request.underlyingConId)
                    self.nextOptionChainId += 1

                case RequestType.MARKET_DEPTH:
                    reqId = self.nextMarketDepthId
                    self.reqMktDepth(reqId=reqId, 
                                        contract=request.contract,
                                        numRows=request.numRows,
                                        isSmartDepth=request.isSmartDepth,
                                        mktDepthOptions=[])
                    self.nextMarketDepthId += 1

                case RequestType.CONTRACT_DETAIL:
                    reqId = self.nextContractDetailId
                    self.reqContractDetails(reqId,request.contract)
                    self.contract_details[reqId] = []
                    self.nextContractDetailId += 1

                case RequestType.REAL_TIME_BAR:
                    reqId = self.nextRealTimeBarId
                    self.reqRealTimeBars(reqId=reqId,
                                            contract=request.contract,
                                            barSize=request.barSize,
                                            whatToShow=request.whatToShow,                         
                                            useRTH=request.useRTH,
                                            realTimeBarsOptions=[])
                    self.nextRealTimeBarId += 1

                case RequestType.HISTORICAL_DATA:
                    reqId = self.nextHistoricalDataId
                    self.reqHistoricalData(
                        reqId=reqId,
                        contract=request.contract,
                        endDateTime=request.endDateTime,
                        durationStr=request.durationStr,
                        barSizeSetting=request.barSizeSetting,
                        whatToShow=request.whatToShow,
                        useRTH=request.useRTH,
                        formatDate=request.formatDate,
                        keepUpToDate=request.keepUpToDate,
                        chartOptions=[]
                    )
                    self.nextHistoricalDataId += 1

                case RequestType.ACCOUNT_SUMMARY:
                    reqId = self.nextAccountSummaryId           
                    self.reqAccountSummary(reqId,request.groupName,request.tags)
                    self.nextAccountSummaryId += 1

                case RequestType.ACCOUNT_UPDATE:
                    reqId = self.nextAccountUpdateId
                    self.reqAccountUpdates(subscribe=request.subscribe,
                                            acctCode=request.acctCode)
                    self.nextAccountUpdateId += 1

                case RequestType.OPEN_ORDER:
                    reqId = -1
                    self.reqAllOpenOrders()

                case RequestType.COMPLETED_ORDERS:
                    reqId = -1
                    self.reqCompletedOrders(False)
                
                case RequestType.EXECUTION_DETAILS:
                    reqId = self.nextExecutionDetailId
                    self.reqExecutions(reqId, ExecutionFilter())
                    self.nextExecutionDetailId +=1

                case RequestType.PNL:
                    reqId = self.nextPnLId
                    self.reqPnL(reqId,request.account,request.modelCode)
                    self.nextPnLId += 1

                case RequestType.PNL_SINGLE:
                    reqId = self.nextPnLSingleId
                    self.reqPnLSingle(reqId=reqId,
                                        account=request.account,
                                        modelCode="",
                                        conid=request.conId)
                    self.nextPnLSingleId += 1
                
        if request.isSubscription:
            request.set_status(RequestStatus.PROCESSED)
            self.handled_requests[reqId] = request

        return reqId
    
    def is_connected(self) -> bool:
        """
        Check connection to IB TWS 
        """
        return self.isConnected()
    
    def get_account(self) -> IBAccount:
        """
        Get account data object
        """
        return self.account_data
    
    def get_account_summary_json(self) -> str:
        """
        Get account data as JSON
        """
        return self.account_data.get_account_summary_json()
    
    def get_portfolio(self) -> Dict:
        """
        Get portfolio data
        """
        return self.account_data.get_portfolio()
    
    def get_portfolio_json(self) -> str:
        """
        Get portfolio data as JSON
        """
        return self.account_data.get_portfolio_json()
    
    def get_position_greeks(self) -> Tuple:
        """
        Get net position greeks
        """
        try:
            return self.account_data.get_net_greeks()
        except ResourceNotAvailableException:
            raise
    
    def get_open_orders(self) -> Dict[int, IBOrder]:
        """
        Get open orders data
        """
        return self.open_orders
    
    def get_open_orders_json(self) -> str:
        """
        Get open orders data as JSON
        """
        response = {}
        for k,v in self.open_orders.items():
            response[k] = v.get_order_summary_json()

        return json.dumps(response)  

    def get_completed_orders(self) -> Dict[int, IBOrder]:
        """
        Get completed orders data
        """
        return self.completed_orders    
    
    def add_order_update_callback(self, callback: Callable) -> None:
        """
        Subscribe to order update
        """
        self._order_update_callbacks.add(callback)

    def place_order(self, order: IBOrder) -> int:
        """
        Place order
        """
        if not self.isConnected():
            raise IBDisconnectedException('API is disconnected')
        
        with self.order_lock:
            self.next_valid_order_id += 1
            order_id = self.next_valid_order_id
            self.placeOrder(order_id,
                            order.contract,
                            order.order)
            self.reqIds(-1)
            self.open_orders[order_id] = order
            
        return order_id
    
    def get_order_data(self, order_id: int) -> IBOrder:
        """
        Get order data object by order id 
        """
        if order_id not in self.open_orders:
            raise OrderNotFoundException(f'order_id {order_id} cannot be found.')
        return self.open_orders[order_id]
    
    def get_order_data_json(self, order_id: int) -> str:
        """
        Get order data as JSON
        """
        if order_id not in self.open_orders:
            raise OrderNotFoundException(f'order_id {order_id} cannot be found.')
        return self.open_orders[order_id].get_order_summary_json()
    
    def get_order_status(self, order_id: int) -> OrderStatus:
        """
        Get order status
        """
        if order_id not in self.open_orders:
            raise OrderNotFoundException(f'order_id {order_id} cannot be found.')
        return self.open_orders[order_id].status

    def cancel_order(self, order_id:int) -> None:
        """
        Cancel order
        """
        if not self.isConnected():
            raise IBDisconnectedException('API is disconnected')
        self.cancelOrder(order_id, OrderCancel())

    def get_ticks(self, req_id: int) -> Tick:
        """
        Get ticks data 
        """
        try:
            return self.ticks[req_id]
        except KeyError:
            logger.error('Request ID not found')
            raise

    def get_ticks_json(self, req_ids: List[int]) -> Dict:
        """
        Get subscribed ticks by request id
        """
        response = {}
        for req_id in req_ids:
            try:
                req = self.handled_requests[req_id]
            except KeyError:
                response[req_id] = {'status': 'ERROR',
                                    'message': 'request were never made'}
       
            if req.status == RequestStatus.INIT or req.status == RequestStatus.PROCESSED:
                response[req_id] = {'status': req.status.value,
                                    'message': 'no response yet'}

            elif (req.status == RequestStatus.ERROR and req.error_code != 10167):
                response[req_id] = {'status': req.status.value,
                                    'message': req.error_msg}
        
            else:
                data = self.ticks[req_id].get_bid_ask()
                data['status'] = req.status.value
                response[req_id] = data

        return response
    
    def _handle_error(
        self,
        reqId: TickerId, 
        errorCode: int, 
        errorString: str, 
        msg: str,
        advancedOrderRejectJson = ""
    ) -> None:
        """
        Error handler
        """
        if reqId in self.handled_requests:
            if reqId != -1 and errorCode not in EXEMPTED_ERROR_CODE:
                self.handled_requests[reqId].set_status(RequestStatus.ERROR)
                self.handled_requests[reqId].set_error(errorCode,errorString)
                logger.error(msg)

        elif reqId in self.open_orders:
            if errorCode == 202:
                self.open_orders.pop(reqId,None)
            elif errorCode == 399:
                self.open_orders[reqId].add_status('Submitted')
            else:
                self.open_orders[reqId].add_status('Inactive')
            logger.error(msg)

        else:
            logger.error(msg)

    #Methods below are for callbacks for receiving and handling data from IB
    @iswrapper
    def connectAck(self) -> None:
        logger.info('TWS API connected')

    @iswrapper
    def connectionClosed(self) -> None:
        logger.info('TWS API connection Lost')

    @iswrapper
    def nextValidId(self, orderId: int) -> None:
        super().nextValidId(orderId)
        self.next_valid_order_id = orderId
        logger.info(f"Next Valid Order Id: {orderId}")

    @iswrapper
    def currentTime(self, time:int) -> None:
        super().currentTime(time)
        logger.debug("CurrentTime:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d-%H:%M:%S"))

    @iswrapper
    def error(
        self, 
        reqId: TickerId, 
        errorCode: int, 
        errorString: str, 
        advancedOrderRejectJson = ""
    ) -> None:
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)

        if advancedOrderRejectJson:
            msg = f"Error Id:{reqId} Code:{errorCode} Msg:{errorString} AdvancedOrderRejectJson:{advancedOrderRejectJson}"
        else:
            msg = f"Error Id:{reqId} Code:{errorCode} Msg:{errorString}"

        #Error code 2104, 2106 and 2158 are confirmation of market data farm connection, not actual errors
        if errorCode == 2104 or errorCode == 2106 or errorCode == 2158:
            self.data_ready = True
            logger.info(msg)

        else:
            self._handle_error(reqId = reqId,
                               errorCode = errorCode,
                               errorString = errorString,
                               msg = msg,
                               advancedOrderRejectJson = advancedOrderRejectJson)
            
    @iswrapper
    def winError(self, text: str, lastError: int) -> None:
        super().winError(text, lastError)

    @iswrapper
    def managedAccounts(self, accountsList: str) -> None:
        super().managedAccounts(accountsList)

        self.account = accountsList.split(",")[0]
        self.account_data.account_name = accountsList.split(",")[0]
        
    @iswrapper
    def accountSummary(
        self, 
        reqId: int, 
        account: str, 
        tag: str, 
        value: str,
        currency: str
    ) -> None:
        super().accountSummary(reqId, account, tag, value, currency)
        logger.debug(f'AccountSummary. ReqId:{reqId} Account:{account} Tag:{tag} Value:{value} Currency:{currency}')

        if (currency == '' or currency == self.account_data.currency) and account == self.account_data.account_name:
            self.account_data.set_value(tag = tag, 
                                        value = value)
            
    @iswrapper
    def pnl(
        self, 
        reqId: int, 
        dailyPnL: float,
        unrealizedPnL: float, 
        realizedPnL: float
    ) -> None:
        super().pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)
        logger.debug(f'pnl. RequestId:{reqId} DailyPnL:{dailyPnL} unrealizedPnL:{unrealizedPnL} realizedPnL:{realizedPnL}')

        kwargs = {
            "unrealizedPNL":unrealizedPnL,
            "realizedPNL":realizedPnL,
            "dailyPnL": dailyPnL
        }

        self.account_data.update_account_summary(**kwargs)

    @iswrapper
    def accountSummaryEnd(
        self, 
        reqId: int
    ) -> None:
        super().accountSummaryEnd(reqId)
        logger.debug(f'AccountSummaryEnd. ReqId:{reqId}')

        self.handled_requests.get(reqId).set_status(RequestStatus.FINISHED)

    @iswrapper
    def updateAccountValue(
        self, 
        key: str, 
        val: str, 
        currency: str,
        accountName: str
    ) -> None:    
        super().updateAccountValue(key, val, currency, accountName)
        logger.debug(f'UpdateAccountValue. Key:{key} Value:{val} Currency:{currency} AccountName:{accountName}')

        if (currency == '' or currency == self.account_data.currency) and accountName == self.account_data.account_name:
            self.account_data.set_value(tag = key,
                                        value = val)

    @iswrapper
    def updateAccountTime(self, timeStamp: str) -> None:
        super().updateAccountTime(timeStamp)
        logger.debug(f'UpdateAccountTime. Time:{timeStamp}')

        self.account_data.account_time = timeStamp

    @iswrapper
    def updatePortfolio(
        self, 
        contract: Contract, 
        position: Decimal,
        marketPrice: float, 
        marketValue: float,
        averageCost: float, 
        unrealizedPNL: float,
        realizedPNL: float,
        accountName: str
    ) -> None:
        super().updatePortfolio(contract, position, marketPrice, marketValue,
                                averageCost, unrealizedPNL, realizedPNL, accountName)
        logger.debug(f'UpdatePortfolio. Symbol:{contract.symbol} SecType: {contract.secIdType} Exchanges: {contract.exchange} Position: {decimalMaxString(position)} MarketPrice: {floatMaxString(marketPrice)} MarketValue:{floatMaxString(marketValue)} AverageCost:{floatMaxString(averageCost)} UnrealizedPnL:{floatMaxString(unrealizedPNL)} RealizedPnL: {floatMaxString(realizedPNL)} AccountName: {accountName}')

        if position == 0:
            pass

        conId = contract.conId

        data = {
            'contract' : contract,
            'position' : position,
            'market_price' : marketPrice,
            'market_value' : marketValue,
            'average_cost' : averageCost,
            'unrealized_PnL' : unrealizedPNL,
            'realized_PnL' : realizedPNL,
        }

        if self.account_data.position_exist(conId = conId):

            self.account_data.update_position(account_name = accountName, 
                                              conId = conId, 
                                              data = data)
        else:
            self.account_data.add_position(account_name = accountName, 
                                           data = data)

    @iswrapper
    def position(
        self, 
        account: str, 
        contract: Contract, 
        position: Decimal,
        avgCost: float
    ) -> None:
        super().position(account, contract, position, avgCost)
        logger.debug(f'Position. Account:{account} Symbol:{contract.symbol} SecType:{contract.secType} Currency:{contract.currency} Posistion: {decimalMaxString(position)} Avg Cost: {floatMaxString(avgCost)}')

    @iswrapper
    def positionEnd(self) -> None:
        super().positionEnd()
        logger.debug('PositionEnd')

    @iswrapper
    def positionMulti(
        self, 
        reqId: int, 
        account: str, 
        modelCode: str,
        contract: Contract, 
        pos: Decimal, 
        avgCost: float
        ) -> None:
        super().positionMulti(reqId, account, modelCode, contract, pos, avgCost)
        logger.debug(f'PositionMulti. RequestedId:{reqId} Account:{account} ModelCode:{modelCode} Symbol:{contract.symbol} SecType:{contract.secType} Currency:{contract.currency} Position:{decimalMaxString(pos)} AvgCost:{floatMaxString(avgCost)}')

    @iswrapper
    def positionMultiEnd(self, reqId: int):
        super().positionMultiEnd(reqId)
        logger.debug(f'PositionMultiEnd. RequestId:{reqId}')

    @iswrapper
    def pnlSingle(
        self,
        reqId: int,
        pos: Decimal,
        dailyPnL: float,
        unrealizedPnL: float,
        realizedPnL: float,
        value: float
    ) -> None:
        super().pnlSingle(reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value)
        logger.debug(f'pnlSingle. ReqId:{reqId} Position:{decimalMaxString(pos)} DailyPnL:{floatMaxString(dailyPnL)} UnrealizedPnL:{floatMaxString(unrealizedPnL)} RealizedPnL:{floatMaxString(realizedPnL)} Value:{floatMaxString(value)}')

    @iswrapper
    def openOrder(
        self, 
        orderId: OrderId, 
        contract: Contract, 
        order: Order,
        orderState: OrderState
    ) -> None:          
        super().openOrder(orderId, contract, order, orderState)
        logger.debug(f'OpenOrder. orderId: {orderId} orderstatus:{orderState.status} contract:{contract} order:{order} orderState:{orderState}' )

        if orderId not in self.open_orders:
            order_data:IBOrder = IBOrder()
            for callback in self._order_update_callbacks:
                order_data.subscribe(callback)
            self.open_orders[orderId] = order_data
        else:
            order_data = self.open_orders[orderId]
        order_data.order_id = order.permId
        order_data.status = IB_STATUS_MAP.get(orderState.status)
        order_data.order = order
        order_data.contract = contract
        order_data.order_state = orderState
        order_data.notify(broker_order_id = order_data.order_id ,
                          security_type = order_data.contract.secType,
                          status = str(order_data.status),
                          filled = order_data.filled,
                          average_price = order_data.avg_fill_price)

    @iswrapper
    def openOrderEnd(self) -> None:
        super().openOrderEnd()
        logger.debug('OpenOrderEnd')

    @iswrapper
    def orderStatus(
        self, 
        orderId: OrderId, 
        status: str, 
        filled: Decimal,
        remaining: Decimal, 
        avgFillPrice: float, 
        permId: int,
        parentId: int, 
        lastFillPrice: float, 
        clientId: int,
        whyHeld: str, 
        mktCapPrice: float
    ) -> None:
        super().orderStatus(orderId, status, filled, remaining,
                            avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
        logger.debug(f'OrderStatus. OrderId:{orderId} Status:{status} Filled:{decimalMaxString(filled)} Remaining:{decimalMaxString(remaining)} AvgFillPrice:{floatMaxString(avgFillPrice)} PermId:{intMaxString(permId)} ParentId:{intMaxString(parentId)} LastFillPrice:{floatMaxString(lastFillPrice)} ClientId: {intMaxString(clientId)} WhyHeld:{whyHeld} MkrCapPrice:{floatMaxString(mktCapPrice)}')
        
        if orderId not in self.open_orders:
            order_data:IBOrder = IBOrder()
            for callback in self._order_update_callbacks:
                order_data.subscribe(callback)
            self.open_orders[orderId] = order_data
        else:
            order_data = self.open_orders[orderId]

        order_data.order_id = permId
        order_data.status = IB_STATUS_MAP.get(status)
        order_data.filled = filled
        order_data.remaining = remaining
        order_data.avg_fill_price = avgFillPrice
        order_data.perm_id = permId
        order_data.parent_id = parentId
        order_data.last_fill_price = lastFillPrice
        order_data.client_id = clientId
        order_data.why_held = whyHeld
        order_data.market_cap_price = mktCapPrice
        order_data.notify(broker_order_id = order_data.order_id ,
                          security_type = order_data.contract.secType,
                          status = str(order_data.status),
                          filled = order_data.filled,
                          average_price = order_data.avg_fill_price,)

    @iswrapper
    def completedOrder(self, contract: Contract, order: Order, orderState: OrderState) -> None:
        super().completedOrder(contract, order, orderState)
        logger.debug(f'CompletedOrder. Contract:{contract} order:{order} orderState{orderState}')

        order_id = order.permId
        if order_id in self.open_orders:
            self.open_orders.pop(order_id)
        if order_id not in self.completed_orders:
            order_data: IBOrder = IBOrder()
            for callback in self._order_update_callbacks:
                order_data.subscribe(callback)
            self.completed_orders[order_id] = order_data
        else:
            order_data = self.completed_orders[order_id]

        order_data.order_id = order_id
        order_data.order = order
        order_data.contract = contract
        order_data.status = IB_STATUS_MAP.get(orderState.status)
        order_data.filled = order.filledQuantity
        order_data.remaining = 0
        order_data.perm_id = order_id
        order_data.parent_id = order.parentId
        order_data.notify(broker_order_id = order_data.order_id ,
                          security_type = order_data.contract.secType,
                          status = str(order_data.status),
                          filled = order_data.filled)

    @iswrapper
    def completedOrdersEnd(self) -> None: 
        super().completedOrdersEnd()
        logger.debug("CompletedOrdersEnd")
        
    @iswrapper
    def execDetails(
        self, 
        reqId: int, 
        contract: Contract, 
        execution: Execution
        ) -> None:
        super().execDetails(reqId, contract, execution)
        logger.debug(f'ExecDetails. ReqId:{reqId} Contract:{contract} Execution:{execution}')
        
        order_id = execution.permId
        if order_id not in self.completed_orders:
            order_data: IBOrder = IBOrder()
            for callback in self._order_update_callbacks:
                order_data.subscribe(callback)
            self.completed_orders[order_id] = order_data
        else:
            order_data = self.completed_orders[order_id]

        order_data.contract = contract
        order_data.add_execution(execution.execId,execution)
        order_data.avg_fill_price = execution.avgPrice
        order_data.notify(broker_order_id = execution.permId,
                          security_type = contract.secType,
                          average_price = order_data.avg_fill_price)

    @iswrapper
    def execDetailsEnd(self, reqId: int) -> None:
        super().execDetailsEnd(reqId)
        logger.debug(f'ExecDetailsEnd:{reqId}')

    @iswrapper
    def contractDetails(self, reqId: int, contractDetails: ContractDetails) -> None:
        super().contractDetails(reqId, contractDetails)
        logger.debug(f'Contract Details: {contractDetails}')

        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)
        self.contract_details[reqId].append(contractDetails)

        con_id = contractDetails.contract.conId
        if con_id != 0:
            for order_id, order_data in self.open_orders.items():
                if order_data.contract.conId == con_id:
                    order_data.contract.symbol = contractDetails.contract.symbol
                    order_data.contract.lastTradeDateOrContractMonth = contractDetails.contract.lastTradeDateOrContractMonth
                    order_data.contract.strike = contractDetails.contract.strike
                    order_data.contract.right = contractDetails.contract.right
                    order_data.contract.localSymbol = contractDetails.contract.localSymbol
                    break

    @iswrapper
    def contractDetailsEnd(self, reqId: int) -> None:
        super().contractDetailsEnd(reqId)
        logger.debug(f'ContractDetailsEnd. ReqId:{reqId}')

        self.handled_requests.get(reqId).set_status(RequestStatus.FINISHED)

    @iswrapper
    def securityDefinitionOptionParameter(
        self, 
        reqId: int, 
        exchange: str, 
        underlyingConId: int, 
        tradingClass: str, 
        multiplier: str, 
        expirations: SetOfString, 
        strikes: SetOfFloat
    ) -> None:
        super().securityDefinitionOptionParameter(reqId, exchange, underlyingConId, tradingClass, multiplier, expirations, strikes)
        logger.debug("SecurityDefinitionOptionParameter.", "ReqId:", reqId, "Exchange:", exchange, "Underlying conId:", underlyingConId, "TradingClass:", tradingClass, "Multiplier:", multiplier, "Expirations:", expirations, "Strikes:", strikes)

        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)

    @iswrapper
    def marketDataType(self, reqId: TickerId, marketDataType: int) -> None:
        super().marketDataType(reqId, marketDataType)
        logger.info(f'Market Data Type. ReqId:{reqId} Type:{marketDataType}')
        print(f'Market Data Type. ReqId:{reqId} Type:{marketDataType}')

        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)
        if reqId in self.ticks:
            self.ticks[reqId].data_type = marketDataType

    @iswrapper
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib) -> None:
        super().tickPrice(reqId, tickType, price, attrib)
        logger.debug(f'TickPrice. reqId:{reqId} tickType:{tickType} price: {floatMaxString(price)} attrib:{attrib}')
        print(f'TickPrice. reqId:{reqId} tickType:{tickType} price: {floatMaxString(price)} attrib:{attrib}')

        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)
        if not reqId in self.ticks:
            req = self.handled_requests[reqId]
            contract = req.contract
            tick = Tick(tickerId=reqId, contract=contract)
            self.ticks[reqId] = tick

        tickTypeString = TickTypeArray[tickType]
        setattr(self.ticks[reqId],tickTypeString,price)

    @iswrapper
    def tickSize(self, reqId: TickerId, tickType: TickType, size: Decimal) -> None:
        super().tickSize(reqId, tickType, size)
        logger.debug(f'TickPrice. reqId:{reqId} tickType:{tickType} price:{decimalMaxString(size)}')
        
        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)
        if not reqId in self.ticks:
            req = self.handled_requests[reqId]
            contract = req.contract
            tick = Tick(tickerId=reqId, contract=contract)
            self.ticks[reqId] = tick
        else:
            tickTypeString = TickTypeArray[tickType]
            setattr(self.ticks[reqId],tickTypeString,str(size))

    @iswrapper
    def tickGeneric(self,reqId: TickerId, tickType: TickType, value: float) -> None:
        super().tickGeneric(reqId, tickType, value)
        logger.debug(f'TickGeneric. reqId:{reqId} tickType:{tickType} value:{floatMaxString(value)}')
        
        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)
        if not reqId in self.ticks:
            req = self.handled_requests[reqId]
            contract = req.contract
            tick = Tick(tickerId=reqId, contract=contract)
            self.ticks[reqId] = tick
        else:
            tickTypeString = TickTypeArray[tickType]
            setattr(self.ticks[reqId],tickTypeString,value)         

    @iswrapper
    def tickString(self, reqId: TickerId, tickType: TickType, value: str) -> None:
        super().tickString(reqId, tickType, value)
        logger.debug(f'reqId:{reqId} tickType:{tickType} value:{value}')
        
        self.handled_requests.get(reqId).set_status(RequestStatus.RESPONDED)
        if not reqId in self.ticks:
            req = self.handled_requests[reqId]
            contract = req.contract
            tick = Tick(tickerId=reqId, contract=contract)
            self.ticks[reqId] = tick
        else:
            tickTypeString = TickTypeArray[tickType]
            setattr(self.ticks[reqId],tickTypeString,value)         