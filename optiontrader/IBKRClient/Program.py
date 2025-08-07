"""
Copyright (C) 2024 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable.
"""

import argparse
import datetime
import collections
import inspect

import logging
import time
import os.path

from ibapi import wrapper
from ibapi.client import EClient
from ibapi.utils import longMaxString
from ibapi.utils import iswrapper

# types
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

from ibapi.account_summary_tags import *

from IBKRContract import IBKRContract
from IBKROrder import IBKROrder
# from AvailableAlgoParams import AvailableAlgoParams
from IBKRScannerSubscription import IBKRScannerSubscription
# from FaAllocationSamples import FaAllocationSamples
from IBKRRequest import *
from IBKRExceptions import *
from IBKRAccount import *
from ibapi.scanner import ScanData
from decimal import Decimal
from ibapi.ineligibility_reason import IneligibilityReason

from queue import Queue
from typing import Dict
from threading import Thread, RLock




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
    console.setLevel(logging.INFO)
    logger.addHandler(console)


def printWhenExecuting(fn):
    def fn2(self):
        print("   doing", fn.__name__)
        fn(self)
        print("   done w/", fn.__name__)

    return fn2

def printinstance(inst:Object):
    attrs = vars(inst)
    print(', '.join('{}:{}'.format(key, decimalMaxString(value) if type(value) is Decimal else
                                   floatMaxString(value) if type(value) is float else
                                   intMaxString(value) if type(value) is int else
                                   getEnumTypeName(FundAssetType, value) if type(value) is FundAssetType else
                                   getEnumTypeName(FundDistributionPolicyIndicator, value) if type(value) is FundDistributionPolicyIndicator else  
                                   "{%s}" % "; ".join(map(str, value)) if type(value) is list else  
                                   value) for key, value in attrs.items()))

class Activity(Object):
    def __init__(self, reqMsgId, ansMsgId, ansEndMsgId, reqId):
        self.reqMsdId = reqMsgId
        self.ansMsgId = ansMsgId
        self.ansEndMsgId = ansEndMsgId
        self.reqId = reqId


class RequestMgr(Object):
    def __init__(self):
        # I will keep this simple even if slower for now: only one list of
        # requests finding will be done by linear search
        self.requests = []

    def addReq(self, req):
        self.requests.append(req)

    def receivedMsg(self, msg):
        pass


# ! [socket_declare]
class TestClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        # ! [socket_declare]

        # how many times a method is called to see test coverage
    #     self.clntMeth2callCount = collections.defaultdict(int)
    #     self.clntMeth2reqIdIdx = collections.defaultdict(lambda: -1)
    #     self.reqId2nReq = collections.defaultdict(int)
    #     self.setupDetectReqId()

    # def countReqId(self, methName, fn):
    #     def countReqId_(*args, **kwargs):
    #         self.clntMeth2callCount[methName] += 1
    #         idx = self.clntMeth2reqIdIdx[methName]
    #         if idx >= 0:
    #             sign = -1 if 'cancel' in methName else 1
    #             self.reqId2nReq[sign * args[idx]] += 1
    #         return fn(*args, **kwargs)

    #     return countReqId_

    # def setupDetectReqId(self):

    #     methods = inspect.getmembers(EClient, inspect.isfunction)
    #     for (methName, meth) in methods:
    #         if methName != "send_msg":
    #             # don't screw up the nice automated logging in the send_msg()
    #             self.clntMeth2callCount[methName] = 0
    #             # logging.debug("meth %s", name)
    #             sig = inspect.signature(meth)
    #             for (idx, pnameNparam) in enumerate(sig.parameters.items()):
    #                 (paramName, param) = pnameNparam # @UnusedVariable
    #                 if paramName == "reqId":
    #                     self.clntMeth2reqIdIdx[methName] = idx

    #             setattr(TestClient, methName, self.countReqId(methName, meth))

    #             # print("TestClient.clntMeth2reqIdIdx", self.clntMeth2reqIdIdx)


# ! [ewrapperimpl]
class TestWrapper(wrapper.EWrapper):
    # ! [ewrapperimpl]
    def __init__(self):
        wrapper.EWrapper.__init__(self)

        self.wrapMeth2callCount = collections.defaultdict(int)
        self.wrapMeth2reqIdIdx = collections.defaultdict(lambda: -1)
        self.reqId2nAns = collections.defaultdict(int)
        self.setupDetectWrapperReqId()

    # TODO: see how to factor this out !!

    def countWrapReqId(self, methName, fn):
        def countWrapReqId_(*args, **kwargs):
            self.wrapMeth2callCount[methName] += 1
            idx = self.wrapMeth2reqIdIdx[methName]
            if idx >= 0:
                self.reqId2nAns[args[idx]] += 1
            return fn(*args, **kwargs)

        return countWrapReqId_

    def setupDetectWrapperReqId(self):

        methods = inspect.getmembers(wrapper.EWrapper, inspect.isfunction)
        for (methName, meth) in methods:
            self.wrapMeth2callCount[methName] = 0
            # logging.debug("meth %s", name)
            sig = inspect.signature(meth)
            for (idx, pnameNparam) in enumerate(sig.parameters.items()):
                (paramName, param) = pnameNparam # @UnusedVariable
                # we want to count the errors as 'error' not 'answer'
                if 'error' not in methName and paramName == "reqId":
                    self.wrapMeth2reqIdIdx[methName] = idx

            setattr(TestWrapper, methName, self.countWrapReqId(methName, meth))

            # print("TestClient.wrapMeth2reqIdIdx", self.wrapMeth2reqIdIdx)


# this is here for documentation generation
"""
#! [ereader]
        # You don't need to run this in your code!
        self.reader = reader.EReader(self.conn, self.msg_queue)
        self.reader.start()   # start thread
#! [ereader]
"""

# ! [socket_init]
class TestApp(TestWrapper, TestClient):

    nKeybInt: int
    started: bool
    nextValidOrderId : int
    permId2ord: Dict
    reqId2nErr: collections.defaultdict
    globalCancelOnly: bool
    simplePlaceOid: int

    requestQueue: Queue
    orderQueue: Queue

    handledRequests: Dict
    requestLock: RLock

    handledOrders: Dict

    responses: Dict

    requestHandler: Thread
    orderHandler: Thread

    nextMarketDataId : int
    nextMarketDepthId : int
    nextRealTimeBarId : int
    nextHistoricalDataId : int
    nextAccountSummaryId : int
    nextPnLId : int
    
    account_: IBKRAccount


    def __init__(self):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)
        # ! [socket_init]
        self.nKeybInt = 0
        self.started = False
        self.nextValidOrderId = None
        self.permId2ord = {}
        self.reqId2nErr = collections.defaultdict(int)
        self.globalCancelOnly = False
        self.simplePlaceOid = None

        self.handledRequests = {}          #Dict of reqID : Request
        self.requestLock = RLock()
        self.responses = {}                 #Dict of reqID : Response

        self.orderQueue = Queue()               #store incoming order   
        self.handledOrders = {}          #Dict of orderID : Order

        self.orderHandler = None

        self.nextMarketDataId = 1000
        self.nextMarketDepthId = 2000
        self.nextRealTimeBarId = 3000
        self.nextHistoricalDataId = 4000
        self.nextAccountSummaryId = 9000
        self.nextAccountUpdateId = 9100
        self.nextPnLId = 17000

        self.account = IBKRAccount()

    """
    Make request and return request id to user
    (to be refactored)
    """
    def make_request(self, request: BaseRequest) -> int:

        if not self.isConnected():
            raise DisconnectedException("API is disconnected")
        
        if not self.account.account_ready and (request.type != RequestType.ACCOUNT_SUMMARY and request.type != RequestType.ACCOUNT_UPDATE):
            raise AccountNotReadyException("Account is not ready")
        
        ##If idential request was made, return that id
        for k,v in self.handledRequests.items():
            if v == request:
                return k         
       
        with self.requestLock:

            match request.type:

                case RequestType.MARKET_DATA:
                    
                    reqId : int = self.nextMarketDataId
           
                    self.reqMktData(reqId=reqId, 
                                    contract=request.contract,
                                    genericTickList=request.genericTickList,
                                    snapshot=request.snapshot,
                                    regulatorySnapshot=request.regulatorySnapshot,
                                    mktDataOptions=[])
            
                    self.nextMarketDataId += 1

                case RequestType.MARKET_DEPTH:

                    reqId : int = self.nextMarketDepthId

                    self.reqMktDepth(reqId=reqId, 
                                     contract=request.contract,
                                     numRows=request.numRows,
                                     isSmartDepth=request.isSmartDepth,
                                     mktDepthOptions=[])
                    
                    self.nextMarketDepthId += 1

                case RequestType.REAL_TIME_BAR:

                    reqId : int = self.nextRealTimeBarId

                    self.reqRealTimeBars(reqId=reqId,
                                         contract=request.contract,
                                         barSize=request.barSize,
                                         whatToShow=request.whatToShow,                         
                                         useRTH=request.useRTH,
                                         realTimeBarsOptions=[])
                    
                    self.nextRealTimeBarId += 1

                case RequestType.HISTORICAL_DATA:

                    reqId : int = self.nextHistoricalDataId

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
                    
                    reqId: int = self.nextAccountSummaryId
              
                    self.reqAccountSummary(reqId=reqId,
                                           groupName=request.groupName,
                                           tags=request.tags)
                    
                    self.nextAccountSummaryId += 1

                case RequestType.ACCOUNT_UPDATE:
                    
                    reqId: int = self.nextAccountUpdateId

                    self.reqAccountUpdates(subscribe=request.subscribe,
                                           acctCode=request.acctCode)
                    
                    self.nextAccountUpdateId += 1

                case RequestType.OPEN_ORDER:
                    reqId: int = 0
                    self.reqAllOpenOrders()
                    
                case RequestType.PNL:
                    reqId: int = self.nextPnLId

                    self.reqPnL(reqId=reqId, 
                                account=request.account, 
                                modelCode=request.account)
                    
                    self.nextPnLId += 1

                
            if request.isSubscription:
                request.set_status(RequestStatus.PROCESSED)
                self.handledRequests[reqId] = request

            return reqId
                

                
        
    def _handleOrder(self):
        pass



    def dumpTestCoverageSituation(self):
        for clntMeth in sorted(self.clntMeth2callCount.keys()):
            logging.debug("ClntMeth: %-30s %6d" % (clntMeth,
                                                   self.clntMeth2callCount[clntMeth]))

        for wrapMeth in sorted(self.wrapMeth2callCount.keys()):
            logging.debug("WrapMeth: %-30s %6d" % (wrapMeth,
                                                   self.wrapMeth2callCount[wrapMeth]))

    def dumpReqAnsErrSituation(self):
        logging.debug("%s\t%s\t%s\t%s" % ("ReqId", "#Req", "#Ans", "#Err"))
        for reqId in sorted(self.reqId2nReq.keys()):
            nReq = self.reqId2nReq.get(reqId, 0)
            nAns = self.reqId2nAns.get(reqId, 0)
            nErr = self.reqId2nErr.get(reqId, 0)
            logging.debug("%d\t%d\t%s\t%d" % (reqId, nReq, nAns, nErr))

    @iswrapper
    # ! [connectack]
    def connectAck(self):
        if self.asynchronous:
            self.startApi()

    # ! [connectack]

    @iswrapper
    # ! [nextvalidid]
    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)

        logging.debug("setting nextValidOrderId: %d", orderId)
        self.nextValidOrderId = orderId
        logging.info("NextValidId:", orderId)
    # ! [nextvalidid]

        # we can start now
        if hasattr(self.account, 'account_name'):
            self.start()

    def start(self):
        if self.started:
            return

        self.started = True

        if self.globalCancelOnly:
            logging.info("Executing GlobalCancel only")
            self.reqGlobalCancel()
        else:
            logging.info("Executing requests")

            acc_sum = AccountSummaryRequest("All",AccountSummaryTags.AllTags)
            acc_update = AccountUpdateRequest(subscribe=True, acctCode=self.account.account_name)
            
            self.make_request(acc_sum)
            self.make_request(acc_update)
            
            
            #self.marketDataTypeOperations()
            #self.tickDataOperations_req()
            #self.historicalDataOperations_req()

            #self.reqGlobalCancel()
            
            
            #self.tickOptionComputations_req()
            #self.marketDepthOperations_req()
            #self.realTimeBarsOperations_req()
            
            #self.optionsOperations_req()
            #self.marketScannersOperations_req()
            #self.fundamentalsOperations_req()
            #self.bulletinsOperations_req()
            #self.contractOperations()
            #self.newsOperations_req()
            #self.miscelaneousOperations()
            #self.linkingOperations()
            #self.financialAdvisorOperations()
            #self.orderOperations_req()
            #self.orderOperations_cancel()
            #self.rerouteCFDOperations()
            #self.marketRuleOperations()
            #self.pnlOperations_req()
            #self.histogramOperations_req()
            #self.continuousFuturesOperations_req()
            #self.historicalTicksOperations()
            #self.tickByTickOperations_req()
            #self.whatIfOrderOperations()
            #self.wshCalendarOperations()
            # self.rfqOperations()
            
            logging.info("Executing requests ... finished")

    def keyboardInterrupt(self):
        self.nKeybInt += 1
        if self.nKeybInt == 1:
            self.stop()
        else:
            print("Finishing test")
            self.done = True

    def stop(self):
        logging.info("Executing cancels")

        self.accountOperations_cancel()


        #self.orderOperations_cancel()
        
        #self.tickDataOperations_cancel()
        #self.tickOptionComputations_cancel()
        #self.marketDepthOperations_cancel()
        #self.realTimeBarsOperations_cancel()
        #self.historicalDataOperations_cancel()
        #self.optionsOperations_cancel()
        #self.marketScanners_cancel()
        #self.fundamentalsOperations_cancel()
        #self.bulletinsOperations_cancel()
        #self.newsOperations_cancel()
        #self.pnlOperations_cancel()
        #self.histogramOperations_cancel()
        #self.continuousFuturesOperations_cancel()
        #self.tickByTickOperations_cancel()
        print("Executing cancels ... finished")
        print("Disconnecting...")
  

    def nextOrderId(self):
        oid = self.nextValidOrderId
        self.nextValidOrderId += 1
        return oid


    """
    Receiving error
    """
    @iswrapper
    # ! [error]
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson = ""):
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)
        if advancedOrderRejectJson:
            print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString, "AdvancedOrderRejectJson:", advancedOrderRejectJson)
        else:
            print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString)

    # ! [error] self.reqId2nErr[reqId] += 1


    @iswrapper
    def winError(self, text: str, lastError: int):
        super().winError(text, lastError)

    """
    Receiving order information 
    """
    @iswrapper
    # ! [openorder]
    def openOrder(self, 
                  orderId: OrderId, 
                  contract: Contract, 
                  order: Order,
                  orderState: OrderState):
        super().openOrder(orderId, contract, order, orderState)

        logging.debug("OpenOrder. PermId:", intMaxString(order.permId), "ClientId:", intMaxString(order.clientId), " OrderId:", intMaxString(orderId), 
              "Account:", order.account, "Symbol:", contract.symbol, "SecType:", contract.secType,
              "Exchange:", contract.exchange, "Action:", order.action, "OrderType:", order.orderType,
              "TotalQty:", decimalMaxString(order.totalQuantity), "CashQty:", floatMaxString(order.cashQty), 
              "LmtPrice:", floatMaxString(order.lmtPrice), "AuxPrice:", floatMaxString(order.auxPrice), "Status:", orderState.status,
              "MinTradeQty:", intMaxString(order.minTradeQty), "MinCompeteSize:", intMaxString(order.minCompeteSize),
              "competeAgainstBestOffset:", "UpToMid" if order.competeAgainstBestOffset == COMPETE_AGAINST_BEST_OFFSET_UP_TO_MID else floatMaxString(order.competeAgainstBestOffset),
              "MidOffsetAtWhole:", floatMaxString(order.midOffsetAtWhole),"MidOffsetAtHalf:" ,floatMaxString(order.midOffsetAtHalf),
              "FAGroup:", order.faGroup, "FAMethod:", order.faMethod, "CustomerAccount:", order.customerAccount, "ProfessionalCustomer:", order.professionalCustomer, 
              "BondAccruedInterest:", order.bondAccruedInterest)

        order.contract = contract
        self.permId2ord[order.permId] = order

        if not self.account.order_status_exist(perm_id=order.permId):
     
            self.account.add_order_status(order_id = orderId,
                                          perm_id = order.permId,
                                          contract = contract,
                                          action =order.action,
                                          order_type = order.orderType,
                                          total_quantity = order.totalQuantity,
                                          cash_quantity = order.cashQty,
                                          limit_price = order.lmtPrice,
                                          aux_price = order.auxPrice,
                                          status = orderState.status
                                          )
        else:
          
            self.account.update_order_status(order_id = orderId,
                                          perm_id = order.permId,
                                          contract = contract,
                                          action =order.action,
                                          order_type = order.orderType,
                                          total_quantity = order.totalQuantity,
                                          cash_quantity = order.cashQty,
                                          limit_price = order.lmtPrice,
                                          aux_price = order.auxPrice,
                                          status = orderState.status)
        
        
    # ! [openorder]

    @iswrapper
    # ! [openorderend]
    def openOrderEnd(self):
        super().openOrderEnd()
        logging.info("OpenOrderEnd")

        logging.debug("Received %d openOrders", len(self.permId2ord))
    # ! [openorderend]

    @iswrapper
    # ! [orderstatus]
    def orderStatus(self, 
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
                    mktCapPrice: float):
        
        super().orderStatus(orderId, status, filled, remaining,
                            avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)
        logging.debug("OrderStatus. Id:", orderId, "Status:", status, "Filled:", decimalMaxString(filled),
              "Remaining:", decimalMaxString(remaining), "AvgFillPrice:", floatMaxString(avgFillPrice),
              "PermId:", intMaxString(permId), "ParentId:", intMaxString(parentId), "LastFillPrice:",
              floatMaxString(lastFillPrice), "ClientId:", intMaxString(clientId), "WhyHeld:",
              whyHeld, "MktCapPrice:", floatMaxString(mktCapPrice))
        
        if not self.account.order_status_exist(perm_id=permId):

            self.account.add_order_status(order_id = orderId,
                                          perm_id = permId,
                                          status = status,
                                          filled = filled,
                                          remaining = remaining,
                                          avg_fill_price = avgFillPrice,
                                          last_fill_price = lastFillPrice)
        else:
     
            self.account.update_order_status(order_id = orderId,
                                          perm_id = permId,
                                          status = status,
                                          filled = filled,
                                          remaining = remaining,
                                          avg_fill_price = avgFillPrice,
                                          last_fill_price = lastFillPrice)
    # ! [orderstatus]


    """
    Receiving account information
    """
    @iswrapper
    # ! [managedaccounts]
    def managedAccounts(self, accountsList: str):
        super().managedAccounts(accountsList)
        logging.info("Account list:", accountsList)
        # ! [managedaccounts]

        self.account.account_name = accountsList.split(",")[0]
        
        if self.nextValidOrderId is not None:
            self.start()

    @iswrapper
    # ! [accountsummary]
    def accountSummary(self, 
                       reqId: int, 
                       account: str, 
                       tag: str, 
                       value: str,
                       currency: str) -> None:
        
        super().accountSummary(reqId, account, tag, value, currency)
        logging.debug("AccountSummary. ReqId:", reqId, "Account:", account,
              "Tag: ", tag, "Value:", value, "Currency:", currency)

        if (currency == "" or currency == self.account.currency) and account == self.account.account_name:
            self.account.set_value(tag=tag,value=value)
        
    # ! [accountsummary]

    @iswrapper
    # ! [accountsummaryend]
    def accountSummaryEnd(self, 
                          reqId: int) -> None:
        
        super().accountSummaryEnd(reqId)
        logging.debug("AccountSummaryEnd. ReqId:", reqId)
    # ! [accountsummaryend]

    @iswrapper
    # ! [updateaccountvalue]
    def updateAccountValue(self, 
                           key: str, 
                           val: str, 
                           currency: str,
                           accountName: str) -> None:
        
        super().updateAccountValue(key, val, currency, accountName)

        logging.debug("UpdateAccountValue. Key:", key, "Value:", val,
              "Currency:", currency, "AccountName:", accountName)

        if (currency == "" or currency == self.account.currency) and accountName == self.account.account_name:
            self.account.set_value(tag=key,value=val)
    # ! [updateaccountvalue]

    @iswrapper
    # ! [updateaccounttime]
    def updateAccountTime(self, 
                          timeStamp: str) -> None:
        super().updateAccountTime(timeStamp)
        logging.info("UpdateAccountTime. Time:", timeStamp)
    # ! [updateaccounttime]

    @iswrapper
    # ! [accountdownloadend]
    def accountDownloadEnd(self, 
                           accountName: str) -> None:
        super().accountDownloadEnd(accountName)
        logging.info("AccountDownloadEnd. Account:", accountName)
    # ! [accountdownloadend]

    """
    Receiving portfolio
    """
    @iswrapper
    # ! [updateportfolio]
    def updatePortfolio(self, 
                        contract: Contract, 
                        position: Decimal,
                        marketPrice: float, 
                        marketValue: float,
                        averageCost: float, 
                        unrealizedPNL: float,
                        realizedPNL: float, 
                        accountName: str) -> None:
        
        super().updatePortfolio(contract, position, marketPrice, marketValue,
                                averageCost, unrealizedPNL, realizedPNL, accountName)
        conId = contract.conId

        if self.account.portfolio_exist(conId=conId):

            self.account.update_portfolio(contract=contract,
                                          position=position,
                                          marketPrice=marketPrice,
                                          marketValue=marketValue,
                                          averageCost=averageCost,
                                          unrealizedPNL=unrealizedPNL,
                                          realizedPNL=realizedPNL,
                                          accountName=accountName)
        else:
            self.account.add_portfolio(contract=contract,
                                        position=position,
                                        marketPrice=marketPrice,
                                        marketValue=marketValue,
                                        averageCost=averageCost,
                                        unrealizedPNL=unrealizedPNL,
                                        realizedPNL=realizedPNL,
                                        accountName=accountName)

    # ! [updateportfolio]


    
    """
    Receiving position information
    """
    @iswrapper
    # ! [position]
    def position(self, 
                 account: str, 
                 contract: Contract, 
                 position: Decimal,
                 avgCost: float) -> None:
        super().position(account, contract, position, avgCost)
        print("Position.", "Account:", account, "Symbol:", contract.symbol, "SecType:",
              contract.secType, "Currency:", contract.currency,
              "Position:", decimalMaxString(position), "Avg cost:", floatMaxString(avgCost))
    # ! [position]

    @iswrapper
    # ! [positionend]
    def positionEnd(self):
        super().positionEnd()
        print("PositionEnd")
    # ! [positionend]



    """
    Receiving PnL information
    """

    @iswrapper
    # ! [pnl]
    def pnl(self, reqId: int, dailyPnL: float,
            unrealizedPnL: float, realizedPnL: float):
        super().pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)
        print("Daily PnL. ReqId:", reqId, "DailyPnL:", floatMaxString(dailyPnL),
              "UnrealizedPnL:", floatMaxString(unrealizedPnL), "RealizedPnL:", floatMaxString(realizedPnL))
    # ! [pnl]

    @iswrapper
    # ! [pnlsingle]
    def pnlSingle(self, reqId: int, pos: Decimal, dailyPnL: float,
                  unrealizedPnL: float, realizedPnL: float, value: float):
        super().pnlSingle(reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value)
        print("Daily PnL Single. ReqId:", reqId, "Position:", decimalMaxString(pos),
              "DailyPnL:", floatMaxString(dailyPnL), "UnrealizedPnL:", floatMaxString(unrealizedPnL),
              "RealizedPnL:", floatMaxString(realizedPnL), "Value:", floatMaxString(value))
    # ! [pnlsingle]

    

    """
    Receiving market data
    """

    @iswrapper
    # ! [marketdatatype]
    def marketDataType(self, reqId: TickerId, marketDataType: int):
        super().marketDataType(reqId, marketDataType)
        print("MarketDataType. ReqId:", reqId, "Type:", marketDataType)
    # ! [marketdatatype]

    
    @iswrapper
    # ! [tickprice]
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float,
                  attrib: TickAttrib):
        super().tickPrice(reqId, tickType, price, attrib)
        print("TickPrice. TickerId:", reqId, "tickType:", tickType,
              "Price:", floatMaxString(price), "CanAutoExecute:", attrib.canAutoExecute,
              "PastLimit:", attrib.pastLimit, end=' ')
        if tickType == TickTypeEnum.BID or tickType == TickTypeEnum.ASK:
            print("PreOpen:", attrib.preOpen)
        else:
            print()
    # ! [tickprice]

    @iswrapper
    # ! [ticksize]
    def tickSize(self, reqId: TickerId, tickType: TickType, size: Decimal):
        super().tickSize(reqId, tickType, size)
        print("TickSize. TickerId:", reqId, "TickType:", tickType, "Size: ", decimalMaxString(size))
    # ! [ticksize]

    @iswrapper
    # ! [tickgeneric]
    def tickGeneric(self, reqId: TickerId, tickType: TickType, value: float):
        super().tickGeneric(reqId, tickType, value)
        print("TickGeneric. TickerId:", reqId, "TickType:", tickType, "Value:", floatMaxString(value))
    # ! [tickgeneric]

    @iswrapper
    # ! [tickstring]
    def tickString(self, reqId: TickerId, tickType: TickType, value: str):
        super().tickString(reqId, tickType, value)
        print("TickString. TickerId:", reqId, "Type:", tickType, "Value:", value)
    # ! [tickstring]

    @iswrapper
    # ! [ticksnapshotend]
    def tickSnapshotEnd(self, reqId: int):
        super().tickSnapshotEnd(reqId)
        print("TickSnapshotEnd. TickerId:", reqId)
    # ! [ticksnapshotend]

    @iswrapper
    # ! [rerouteMktDataReq]
    def rerouteMktDataReq(self, reqId: int, conId: int, exchange: str):
        super().rerouteMktDataReq(reqId, conId, exchange)
        print("Re-route market data request. ReqId:", reqId, "ConId:", conId, "Exchange:", exchange)
    # ! [rerouteMktDataReq]

    @iswrapper
    # ! [marketRule]
    def marketRule(self, marketRuleId: int, priceIncrements: ListOfPriceIncrements):
        super().marketRule(marketRuleId, priceIncrements)
        print("Market Rule ID: ", marketRuleId)
        for priceIncrement in priceIncrements:
            print("Price Increment.", priceIncrement)
    # ! [marketRule]


    @iswrapper
    # ! [orderbound]
    def orderBound(self, orderId: int, apiClientId: int, apiOrderId: int):
        super().orderBound(orderId, apiClientId, apiOrderId)
        print("OrderBound.", "OrderId:", intMaxString(orderId), "ApiClientId:", intMaxString(apiClientId), "ApiOrderId:", intMaxString(apiOrderId))
    # ! [orderbound]

    @iswrapper
    # ! [tickbytickalllast]
    def tickByTickAllLast(self, reqId: int, tickType: int, time: int, price: float,
                          size: Decimal, tickAtrribLast: TickAttribLast, exchange: str,
                          specialConditions: str):
        super().tickByTickAllLast(reqId, tickType, time, price, size, tickAtrribLast,
                                  exchange, specialConditions)
        if tickType == 1:
            print("Last.", end='')
        else:
            print("AllLast.", end='')
        print(" ReqId:", reqId,
              "Time:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d-%H:%M:%S"),
              "Price:", floatMaxString(price), "Size:", decimalMaxString(size), "Exch:" , exchange,
              "Spec Cond:", specialConditions, "PastLimit:", tickAtrribLast.pastLimit, "Unreported:", tickAtrribLast.unreported)
    # ! [tickbytickalllast]

    @iswrapper
    # ! [tickbytickbidask]
    def tickByTickBidAsk(self, reqId: int, time: int, bidPrice: float, askPrice: float,
                         bidSize: Decimal, askSize: Decimal, tickAttribBidAsk: TickAttribBidAsk):
        super().tickByTickBidAsk(reqId, time, bidPrice, askPrice, bidSize,
                                 askSize, tickAttribBidAsk)
        print("BidAsk. ReqId:", reqId,
              "Time:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d-%H:%M:%S"),
              "BidPrice:", floatMaxString(bidPrice), "AskPrice:", floatMaxString(askPrice), "BidSize:", decimalMaxString(bidSize),
              "AskSize:", decimalMaxString(askSize), "BidPastLow:", tickAttribBidAsk.bidPastLow, "AskPastHigh:", tickAttribBidAsk.askPastHigh)
    # ! [tickbytickbidask]

    # ! [tickbytickmidpoint]
    @iswrapper
    def tickByTickMidPoint(self, reqId: int, time: int, midPoint: float):
        super().tickByTickMidPoint(reqId, time, midPoint)
        print("Midpoint. ReqId:", reqId,
              "Time:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d-%H:%M:%S"),
              "MidPoint:", floatMaxString(midPoint))
    # ! [tickbytickmidpoint]

    @iswrapper
    # ! [updatemktdepth]
    def updateMktDepth(self, reqId: TickerId, position: int, operation: int,
                       side: int, price: float, size: Decimal):
        super().updateMktDepth(reqId, position, operation, side, price, size)
        print("UpdateMarketDepth. ReqId:", reqId, "Position:", position, "Operation:",
              operation, "Side:", side, "Price:", floatMaxString(price), "Size:", decimalMaxString(size))
    # ! [updatemktdepth]

    @iswrapper
    # ! [updatemktdepthl2]
    def updateMktDepthL2(self, reqId: TickerId, position: int, marketMaker: str,
                         operation: int, side: int, price: float, size: Decimal, isSmartDepth: bool):
        super().updateMktDepthL2(reqId, position, marketMaker, operation, side,
                                 price, size, isSmartDepth)
        print("UpdateMarketDepthL2. ReqId:", reqId, "Position:", position, "MarketMaker:", marketMaker, "Operation:",
              operation, "Side:", side, "Price:", floatMaxString(price), "Size:", decimalMaxString(size), "isSmartDepth:", isSmartDepth)

    # ! [updatemktdepthl2]

    @iswrapper
    # ! [rerouteMktDepthReq]
    def rerouteMktDepthReq(self, reqId: int, conId: int, exchange: str):
        super().rerouteMktDataReq(reqId, conId, exchange)
        print("Re-route market depth request. ReqId:", reqId, "ConId:", conId, "Exchange:", exchange)
    # ! [rerouteMktDepthReq]

    @iswrapper
    # ! [realtimebar]
    def realtimeBar(self, reqId: TickerId, time:int, open_: float, high: float, low: float, close: float,
                        volume: Decimal, wap: Decimal, count: int):
        super().realtimeBar(reqId, time, open_, high, low, close, volume, wap, count)
        print("RealTimeBar. TickerId:", reqId, RealTimeBar(time, -1, open_, high, low, close, volume, wap, count))
    # ! [realtimebar]



    """
    Receiving Historical Data
    """
    @iswrapper
    # ! [headTimestamp]
    def headTimestamp(self, reqId:int, headTimestamp:str):
        print("HeadTimestamp. ReqId:", reqId, "HeadTimeStamp:", headTimestamp)
    # ! [headTimestamp]

    @iswrapper
    # ! [histogramData]
    def histogramData(self, reqId:int, items:HistogramDataList):
        print("HistogramData. ReqId:", reqId, "HistogramDataList:", "[%s]" % "; ".join(map(str, items)))
    # ! [histogramData]

    @iswrapper
    # ! [historicaldata]
    def historicalData(self, reqId:int, bar: BarData):
        print("HistoricalData. ReqId:", reqId, "BarData.", bar)
    # ! [historicaldata]

    @iswrapper
    # ! [historicaldataend]
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        super().historicalDataEnd(reqId, start, end)
        print("HistoricalDataEnd. ReqId:", reqId, "from", start, "to", end)
    # ! [historicaldataend]

    @iswrapper
    # ! [historicalDataUpdate]
    def historicalDataUpdate(self, reqId: int, bar: BarData):
        print("HistoricalDataUpdate. ReqId:", reqId, "BarData.", bar)
    # ! [historicalDataUpdate]

    @iswrapper
    # ! [historicalticks]
    def historicalTicks(self, reqId: int, ticks: ListOfHistoricalTick, done: bool):
        for tick in ticks:
            print("HistoricalTick. ReqId:", reqId, tick)
    # ! [historicalticks]

    @iswrapper
    # ! [historicalticksbidask]
    def historicalTicksBidAsk(self, reqId: int, ticks: ListOfHistoricalTickBidAsk,
                              done: bool):
        for tick in ticks:
            print("HistoricalTickBidAsk. ReqId:", reqId, tick)
    # ! [historicalticksbidask]

    @iswrapper
    # ! [historicaltickslast]
    def historicalTicksLast(self, reqId: int, ticks: ListOfHistoricalTickLast,
                            done: bool):
        for tick in ticks:
            print("HistoricalTickLast. ReqId:", reqId, tick)
    # ! [historicaltickslast]


    """
    Receiving: Unused
    """


    @iswrapper
    # ! [positionmulti]
    def positionMulti(self, reqId: int, account: str, modelCode: str,
                      contract: Contract, pos: Decimal, avgCost: float):
        super().positionMulti(reqId, account, modelCode, contract, pos, avgCost)
        print("PositionMulti. RequestId:", reqId, "Account:", account,
              "ModelCode:", modelCode, "Symbol:", contract.symbol, "SecType:",
              contract.secType, "Currency:", contract.currency, ",Position:",
              decimalMaxString(pos), "AvgCost:", floatMaxString(avgCost))
    # ! [positionmulti]

    @iswrapper
    # ! [positionmultiend]
    def positionMultiEnd(self, reqId: int):
        super().positionMultiEnd(reqId)
        print("PositionMultiEnd. RequestId:", reqId)
    # ! [positionmultiend]

    @iswrapper
    # ! [accountupdatemulti]
    def accountUpdateMulti(self, reqId: int, account: str, modelCode: str,
                           key: str, value: str, currency: str):
        super().accountUpdateMulti(reqId, account, modelCode, key, value,
                                   currency)
        print("AccountUpdateMulti. RequestId:", reqId, "Account:", account,
              "ModelCode:", modelCode, "Key:", key, "Value:", value,
              "Currency:", currency)
    # ! [accountupdatemulti]

    @iswrapper
    # ! [accountupdatemultiend]
    def accountUpdateMultiEnd(self, reqId: int):
        super().accountUpdateMultiEnd(reqId)
        print("AccountUpdateMultiEnd. RequestId:", reqId)
    # ! [accountupdatemultiend]

    @iswrapper
    # ! [familyCodes]
    def familyCodes(self, familyCodes: ListOfFamilyCode):
        super().familyCodes(familyCodes)
        print("Family Codes:")
        for familyCode in familyCodes:
            print("FamilyCode.", familyCode)
    # ! [familyCodes]

    @iswrapper
    # ! [securityDefinitionOptionParameter]
    def securityDefinitionOptionParameter(self, reqId: int, exchange: str,
                                          underlyingConId: int, tradingClass: str, multiplier: str,
                                          expirations: SetOfString, strikes: SetOfFloat):
        super().securityDefinitionOptionParameter(reqId, exchange,
                                                  underlyingConId, tradingClass, multiplier, expirations, strikes)
        print("SecurityDefinitionOptionParameter.",
              "ReqId:", reqId, "Exchange:", exchange, "Underlying conId:", intMaxString(underlyingConId), "TradingClass:", tradingClass, "Multiplier:", multiplier,
              "Expirations:", expirations, "Strikes:", str(strikes))
    # ! [securityDefinitionOptionParameter]

    @iswrapper
    # ! [securityDefinitionOptionParameterEnd]
    def securityDefinitionOptionParameterEnd(self, reqId: int):
        super().securityDefinitionOptionParameterEnd(reqId)
        print("SecurityDefinitionOptionParameterEnd. ReqId:", reqId)
    # ! [securityDefinitionOptionParameterEnd]

    @iswrapper
    # ! [tickoptioncomputation]
    def tickOptionComputation(self, reqId: TickerId, tickType: TickType, tickAttrib: int,
                              impliedVol: float, delta: float, optPrice: float, pvDividend: float,
                              gamma: float, vega: float, theta: float, undPrice: float):
        super().tickOptionComputation(reqId, tickType, tickAttrib, impliedVol, delta,
                                      optPrice, pvDividend, gamma, vega, theta, undPrice)
        print("TickOptionComputation. TickerId:", reqId, "TickType:", tickType,
              "TickAttrib:", intMaxString(tickAttrib),
              "ImpliedVolatility:", floatMaxString(impliedVol), "Delta:", floatMaxString(delta), "OptionPrice:",
              floatMaxString(optPrice), "pvDividend:", floatMaxString(pvDividend), "Gamma: ", floatMaxString(gamma), "Vega:", floatMaxString(vega),
              "Theta:", floatMaxString(theta), "UnderlyingPrice:", floatMaxString(undPrice))

    # ! [tickoptioncomputation]

    @iswrapper
    #! [tickNews]
    def tickNews(self, tickerId: int, timeStamp: int, providerCode: str,
                 articleId: str, headline: str, extraData: str):
        print("TickNews. TickerId:", tickerId, "TimeStamp:", intMaxString(timeStamp),
              "ProviderCode:", providerCode, "ArticleId:", articleId,
              "Headline:", headline, "ExtraData:", extraData)
    #! [tickNews]

    @iswrapper
    #! [historicalNews]
    def historicalNews(self, reqId: int, time: str, providerCode: str,
                       articleId: str, headline: str):
        print("HistoricalNews. ReqId:", reqId, "Time:", time,
              "ProviderCode:", providerCode, "ArticleId:", articleId,
              "Headline:", headline)
    #! [historicalNews]

    @iswrapper
    #! [historicalNewsEnd]
    def historicalNewsEnd(self, reqId:int, hasMore:bool):
        print("HistoricalNewsEnd. ReqId:", reqId, "HasMore:", hasMore)
    #! [historicalNewsEnd]

    @iswrapper
    #! [newsProviders]
    def newsProviders(self, newsProviders: ListOfNewsProviders):
        print("NewsProviders: ")
        for provider in newsProviders:
            print("NewsProvider.", provider)
    #! [newsProviders]

    @iswrapper
    #! [newsArticle]
    def newsArticle(self, reqId: int, articleType: int, articleText: str):
        print("NewsArticle. ReqId:", reqId, "ArticleType:", articleType,
              "ArticleText:", articleText)
    #! [newsArticle]

    @iswrapper
    # ! [contractdetails]
    def contractDetails(self, reqId: int, contractDetails: ContractDetails):
        super().contractDetails(reqId, contractDetails)
        printinstance(contractDetails)
    # ! [contractdetails]

    @iswrapper
    # ! [bondcontractdetails]
    def bondContractDetails(self, reqId: int, contractDetails: ContractDetails):
        super().bondContractDetails(reqId, contractDetails)
        printinstance(contractDetails)
    # ! [bondcontractdetails]

    @iswrapper
    # ! [contractdetailsend]
    def contractDetailsEnd(self, reqId: int):
        super().contractDetailsEnd(reqId)
        print("ContractDetailsEnd. ReqId:", reqId)
    # ! [contractdetailsend]

    @iswrapper
    # ! [symbolSamples]
    def symbolSamples(self, reqId: int,
                      contractDescriptions: ListOfContractDescription):
        super().symbolSamples(reqId, contractDescriptions)
        print("Symbol Samples. Request Id: ", reqId)

        for contractDescription in contractDescriptions:
            derivSecTypes = ""
            for derivSecType in contractDescription.derivativeSecTypes:
                derivSecTypes += " "
                derivSecTypes += derivSecType
            print("Contract: conId:%s, symbol:%s, secType:%s primExchange:%s, "
                  "currency:%s, derivativeSecTypes:%s, description:%s, issuerId:%s" % (
                contractDescription.contract.conId,
                contractDescription.contract.symbol,
                contractDescription.contract.secType,
                contractDescription.contract.primaryExchange,
                contractDescription.contract.currency, derivSecTypes,
                contractDescription.contract.description,
                contractDescription.contract.issuerId))
    # ! [symbolSamples]
    @iswrapper
    # ! [scannerparameters]
    def scannerParameters(self, xml: str):
        super().scannerParameters(xml)
        open('log/scanner.xml', 'w').write(xml)
        print("ScannerParameters received.")
    # ! [scannerparameters]

    @iswrapper
    # ! [scannerdata]
    def scannerData(self, reqId: int, rank: int, contractDetails: ContractDetails,
                    distance: str, benchmark: str, projection: str, legsStr: str):
        super().scannerData(reqId, rank, contractDetails, distance, benchmark,
                            projection, legsStr)
#        print("ScannerData. ReqId:", reqId, "Rank:", rank, "Symbol:", contractDetails.contract.symbol,
#              "SecType:", contractDetails.contract.secType,
#              "Currency:", contractDetails.contract.currency,
#              "Distance:", distance, "Benchmark:", benchmark,
#              "Projection:", projection, "Legs String:", legsStr)
        print("ScannerData. ReqId:", reqId, ScanData(contractDetails.contract, rank, distance, benchmark, projection, legsStr))
    # ! [scannerdata]

    @iswrapper
    # ! [scannerdataend]
    def scannerDataEnd(self, reqId: int):
        super().scannerDataEnd(reqId)
        print("ScannerDataEnd. ReqId:", reqId)
        # ! [scannerdataend]

    @iswrapper
    # ! [smartcomponents]
    def smartComponents(self, reqId:int, smartComponentMap:SmartComponentMap):
        super().smartComponents(reqId, smartComponentMap)
        print("SmartComponents:")
        for smartComponent in smartComponentMap:
            print("SmartComponent.", smartComponent)
    # ! [smartcomponents]

    @iswrapper
    # ! [tickReqParams]
    def tickReqParams(self, tickerId:int, minTick:float,
                      bboExchange:str, snapshotPermissions:int):
        super().tickReqParams(tickerId, minTick, bboExchange, snapshotPermissions)
        print("TickReqParams. TickerId:", tickerId, "MinTick:", floatMaxString(minTick),
              "BboExchange:", bboExchange, "SnapshotPermissions:", intMaxString(snapshotPermissions))
    # ! [tickReqParams]

    @iswrapper
    # ! [mktDepthExchanges]
    def mktDepthExchanges(self, depthMktDataDescriptions:ListOfDepthExchanges):
        super().mktDepthExchanges(depthMktDataDescriptions)
        print("MktDepthExchanges:")
        for desc in depthMktDataDescriptions:
            print("DepthMktDataDescription.", desc)
    # ! [mktDepthExchanges]

    @iswrapper
    # ! [fundamentaldata]
    def fundamentalData(self, reqId: TickerId, data: str):
        super().fundamentalData(reqId, data)
        print("FundamentalData. ReqId:", reqId, "Data:", data)
    # ! [fundamentaldata]

    @iswrapper
    # ! [updatenewsbulletin]
    def updateNewsBulletin(self, msgId: int, msgType: int, newsMessage: str,
                           originExch: str):
        super().updateNewsBulletin(msgId, msgType, newsMessage, originExch)
        print("News Bulletins. MsgId:", msgId, "Type:", msgType, "Message:", newsMessage,
              "Exchange of Origin: ", originExch)
        # ! [updatenewsbulletin]

    @iswrapper
    # ! [receivefa]
    def receiveFA(self, faData: FaDataType, cxml: str):
        super().receiveFA(faData, cxml)
        print("Receiving FA: ", faData)
        open('log/fa.xml', 'w').write(cxml)
    # ! [receivefa]

    @iswrapper
    # ! [softDollarTiers]
    def softDollarTiers(self, reqId: int, tiers: list):
        super().softDollarTiers(reqId, tiers)
        print("SoftDollarTiers. ReqId:", reqId)
        for tier in tiers:
            print("SoftDollarTier.", tier)
    # ! [softDollarTiers]


    @iswrapper
    # ! [displaygrouplist]
    def displayGroupList(self, reqId: int, groups: str):
        super().displayGroupList(reqId, groups)
        print("DisplayGroupList. ReqId:", reqId, "Groups", groups)
    # ! [displaygrouplist]

    @iswrapper
    # ! [displaygroupupdated]
    def displayGroupUpdated(self, reqId: int, contractInfo: str):
        super().displayGroupUpdated(reqId, contractInfo)
        print("DisplayGroupUpdated. ReqId:", reqId, "ContractInfo:", contractInfo)
    # ! [displaygroupupdated]

    @iswrapper
    # ! [execdetails]
    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        super().execDetails(reqId, contract, execution)
        print("ExecDetails. ReqId:", reqId, "Symbol:", contract.symbol, "SecType:", contract.secType, "Currency:", contract.currency, execution)
    # ! [execdetails]

    @iswrapper
    # ! [execdetailsend]
    def execDetailsEnd(self, reqId: int):
        super().execDetailsEnd(reqId)
        print("ExecDetailsEnd. ReqId:", reqId)
    # ! [execdetailsend]

    @iswrapper
    # ! [commissionreport]
    def commissionReport(self, commissionReport: CommissionReport):
        super().commissionReport(commissionReport)
        print("CommissionReport.", commissionReport)
    # ! [commissionreport]

    @iswrapper
    # ! [currenttime]
    def currentTime(self, time:int):
        super().currentTime(time)
        print("CurrentTime:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d-%H:%M:%S"))
    # ! [currenttime]

    @iswrapper
    # ! [completedorder]
    def completedOrder(self, contract: Contract, order: Order,
                  orderState: OrderState):
        super().completedOrder(contract, order, orderState)
        print("CompletedOrder. PermId:", intMaxString(order.permId), "ParentPermId:", longMaxString(order.parentPermId), "Account:", order.account, 
              "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:", contract.exchange, 
              "Action:", order.action, "OrderType:", order.orderType, "TotalQty:", decimalMaxString(order.totalQuantity), 
              "CashQty:", floatMaxString(order.cashQty), "FilledQty:", decimalMaxString(order.filledQuantity), 
              "LmtPrice:", floatMaxString(order.lmtPrice), "AuxPrice:", floatMaxString(order.auxPrice), "Status:", orderState.status,
              "Completed time:", orderState.completedTime, "Completed Status:" + orderState.completedStatus,
              "MinTradeQty:", intMaxString(order.minTradeQty), "MinCompeteSize:", intMaxString(order.minCompeteSize),
              "competeAgainstBestOffset:", "UpToMid" if order.competeAgainstBestOffset == COMPETE_AGAINST_BEST_OFFSET_UP_TO_MID else floatMaxString(order.competeAgainstBestOffset),
              "MidOffsetAtWhole:", floatMaxString(order.midOffsetAtWhole),"MidOffsetAtHalf:" ,floatMaxString(order.midOffsetAtHalf), "CustomerAccount:", order.customerAccount,
              "ProfessionalCustomer:", order.professionalCustomer)
    # ! [completedorder]

    @iswrapper
    # ! [completedordersend]
    def completedOrdersEnd(self):
        super().completedOrdersEnd()
        print("CompletedOrdersEnd")
    # ! [completedordersend]

    @iswrapper
    # ! [replacefaend]
    def replaceFAEnd(self, reqId: int, text: str):
        super().replaceFAEnd(reqId, text)
        print("ReplaceFAEnd.", "ReqId:", reqId, "Text:", text)
    # ! [replacefaend]

    @iswrapper
    # ! [wshmetadata]
    def wshMetaData(self, reqId: int, dataJson: str):
        super().wshMetaData(reqId, dataJson)
        print("WshMetaData.", "ReqId:", reqId, "Data JSON:", dataJson)
    # ! [wshmetadata]

    @iswrapper
    # ! [wsheventdata]
    def wshEventData(self, reqId: int, dataJson: str):
        super().wshEventData(reqId, dataJson)
        print("WshEventData.", "ReqId:", reqId, "Data JSON:", dataJson)
    # ! [wsheventdata]

    @iswrapper
    # ! [historicalschedule]
    def historicalSchedule(self, reqId: int, startDateTime: str, endDateTime: str, timeZone: str, sessions: ListOfHistoricalSessions):
        super().historicalSchedule(reqId, startDateTime, endDateTime, timeZone, sessions)
        print("HistoricalSchedule. ReqId:", reqId, "Start:", startDateTime, "End:", endDateTime, "TimeZone:", timeZone)

        for session in sessions:
            print("\tSession. Start:", session.startDateTime, "End:", session.endDateTime, "Ref Date:", session.refDate)
    # ! [historicalschedule]

    @iswrapper
    # ! [userinfo]
    def userInfo(self, reqId: int, whiteBrandingId: str):
        super().userInfo(reqId, whiteBrandingId)
        print("UserInfo.", "ReqId:", reqId, "WhiteBrandingId:", whiteBrandingId)
    # ! [userinfo]


    """
    Cancelling Request
    """

    @printWhenExecuting
    def accountOperations_cancel(self):
        
        
        # ! [cancelaaccountsummary]
        for id,req in self.handledRequests.items():
            if req.type == RequestType.ACCOUNT_SUMMARY:
                print(f"Unsubscribing {id}: Account Summary")
                self.cancelAccountSummary(id)
        # ! [cancelaaccountsummary]

        # ! [cancelaaccountupdates]
        for id,req in self.handledRequests.items():
            if req.type == RequestType.ACCOUNT_UPDATE:
                print(f"Unsubscribing {id}: Account Update")
                self.reqAccountUpdates(False, self.account.account_name)
        # ! [cancelaaccountupdates]





    @printWhenExecuting
    def marketDataTypeOperations(self):
        # ! [reqmarketdatatype]
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        self.reqMarketDataType(MarketDataTypeEnum.DELAYED)
        # ! [reqmarketdatatype]

    @printWhenExecuting
    def tickDataOperations_req(self):
        self.reqMarketDataType(MarketDataTypeEnum.DELAYED_FROZEN)
        
        # Requesting real time market data

        # ! [reqmktdata]
        self.reqMktData(1000, IBKRContract.USStockAtSmart(), "", False, False, [])
        # ! [reqmktdata]

        # ! [reqmktdata_genticks]
        # Requesting RTVolume (Time & Sales) and shortable generic ticks
        self.reqMktData(1004, IBKRContract.USStockAtSmart(), "233,236", False, False, [])
        # ! [reqmktdata_genticks]

        # ! [reqmktdata_contractnews]
        # Without the API news subscription this will generate an "invalid tick type" error
        self.reqMktData(1005, IBKRContract.USStockAtSmart(), "mdoff,292:BRFG", False, False, [])
        self.reqMktData(1006, IBKRContract.USStockAtSmart(), "mdoff,292:BRFG+DJNL", False, False, [])
        self.reqMktData(1007, IBKRContract.USStockAtSmart(), "mdoff,292:BRFUPDN", False, False, [])
        self.reqMktData(1008, IBKRContract.USStockAtSmart(), "mdoff,292:DJ-RT", False, False, [])
        # ! [reqmktdata_contractnews]


        # ! [reqmktdata_broadtapenews]
        self.reqMktData(1009, IBKRContract.BTbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        self.reqMktData(1010, IBKRContract.BZbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        self.reqMktData(1011, IBKRContract.FLYbroadtapeNewsFeed(), "mdoff,292", False, False, [])
        # ! [reqmktdata_broadtapenews]

        # ! [reqoptiondatagenticks]
        # Requesting data for an option contract will return the greek values
        self.reqMktData(1013, IBKRContract.OptionWithLocalSymbol(), "", False, False, [])        
        # ! [reqoptiondatagenticks]

        # ! [reqavgoptvolume]
        self.reqMktData(1017, IBKRContract.USStockAtSmart(), "mdoff,105", False, False, [])
        # ! [reqavgoptvolume]
        
        # ! [reqsmartcomponents]
        # Requests description of map of single letter exchange codes to full exchange names
        self.reqSmartComponents(1018, "a6")
        # ! [reqsmartcomponents]
        
        # ! [reqetfticks]
        self.reqMktData(1019, IBKRContract.etf(), "mdoff,577,623,614", False, False, [])
        # ! [reqetfticks]

    @printWhenExecuting
    def tickDataOperations_cancel(self):
        # Canceling the market data subscription
        # ! [cancelmktdata]
        self.cancelMktData(1000)
        self.cancelMktData(1001)
        # ! [cancelmktdata]

        self.cancelMktData(1004)
        
        self.cancelMktData(1005)
        self.cancelMktData(1006)
        self.cancelMktData(1007)
        self.cancelMktData(1008)
        
        self.cancelMktData(1009)
        self.cancelMktData(1010)
        self.cancelMktData(1011)
        self.cancelMktData(1012)
        
        self.cancelMktData(1013)
        self.cancelMktData(1014)
        
        self.cancelMktData(1015)
        
        self.cancelMktData(1016)
        
        self.cancelMktData(1017)

        self.cancelMktData(1019)
        self.cancelMktData(1020)
        self.cancelMktData(1021)

    @printWhenExecuting
    def tickOptionComputations_req(self):
        self.reqMarketDataType(MarketDataTypeEnum.DELAYED_FROZEN)
        # Requesting options computations
        # ! [reqoptioncomputations]
        self.reqMktData(1000, IBKRContract.OptionWithLocalSymbol(), "", False, False, [])
        # ! [reqoptioncomputations]

    @printWhenExecuting
    def tickOptionComputations_cancel(self):
        # Canceling options computations
        # ! [canceloptioncomputations]
        self.cancelMktData(1000)
        # ! [canceloptioncomputations]

    @printWhenExecuting
    def tickByTickOperations_req(self):
        # Requesting tick-by-tick data (only refresh)
        # ! [reqtickbytick]
        self.reqTickByTickData(19001, IBKRContract.EuropeanStock2(), "Last", 0, True)
        self.reqTickByTickData(19002, IBKRContract.EuropeanStock2(), "AllLast", 0, False)
        self.reqTickByTickData(19003, IBKRContract.EuropeanStock2(), "BidAsk", 0, True)
        self.reqTickByTickData(19004, IBKRContract.EurGbpFx(), "MidPoint", 0, False)
        # ! [reqtickbytick]

        # Requesting tick-by-tick data (refresh + historicalticks)
        # ! [reqtickbytickwithhist]
        self.reqTickByTickData(19005, IBKRContract.EuropeanStock2(), "Last", 10, False)
        self.reqTickByTickData(19006, IBKRContract.EuropeanStock2(), "AllLast", 10, False)
        self.reqTickByTickData(19007, IBKRContract.EuropeanStock2(), "BidAsk", 10, False)
        self.reqTickByTickData(19008, IBKRContract.EurGbpFx(), "MidPoint", 10, True)
        # ! [reqtickbytickwithhist]

    @printWhenExecuting
    def tickByTickOperations_cancel(self):
        # ! [canceltickbytick]
        self.cancelTickByTickData(19001)
        self.cancelTickByTickData(19002)
        self.cancelTickByTickData(19003)
        self.cancelTickByTickData(19004)
        # ! [canceltickbytick]

        # ! [canceltickbytickwithhist]
        self.cancelTickByTickData(19005)
        self.cancelTickByTickData(19006)
        self.cancelTickByTickData(19007)
        self.cancelTickByTickData(19008)
        # ! [canceltickbytickwithhist]
        
 

    @printWhenExecuting
    def marketDepthOperations_req(self):
        # Requesting the Deep Book
        # ! [reqmarketdepth]
        self.reqMktDepth(2001, IBKRContract.EurGbpFx(), 5, False, [])
        # ! [reqmarketdepth]

        # ! [reqmarketdepth]
        self.reqMktDepth(2002, IBKRContract.EuropeanStock(), 5, True, [])
        # ! [reqmarketdepth]

        # Request list of exchanges sending market depth to UpdateMktDepthL2()
        # ! [reqMktDepthExchanges]
        self.reqMktDepthExchanges()
        # ! [reqMktDepthExchanges]

    @printWhenExecuting
    def marketDepthOperations_cancel(self):
        # Canceling the Deep Book request
        # ! [cancelmktdepth]
        self.cancelMktDepth(2001, False)
        self.cancelMktDepth(2002, True)
        # ! [cancelmktdepth]



    @printWhenExecuting
    def realTimeBarsOperations_req(self):
        # Requesting real time bars
        # ! [reqrealtimebars]
        self.reqRealTimeBars(3001, IBKRContract.EurGbpFx(), 5, "MIDPOINT", True, [])
        # ! [reqrealtimebars]



    @printWhenExecuting
    def realTimeBarsOperations_cancel(self):
        # Canceling real time bars
        # ! [cancelrealtimebars]
        self.cancelRealTimeBars(3001)
        # ! [cancelrealtimebars]

    @printWhenExecuting
    def historicalDataOperations_req(self):
        # Requesting historical data
        # ! [reqHeadTimeStamp]
        self.reqHeadTimeStamp(4101, IBKRContract.USStockAtSmart(), "TRADES", 0, 1)
        # ! [reqHeadTimeStamp]

        # ! [reqhistoricaldata]
        queryTime = (datetime.datetime.today() - datetime.timedelta(days=180)).strftime("%Y%m%d-%H:%M:%S")
        self.reqHistoricalData(4102, IBKRContract.EurGbpFx(), queryTime,
                               "1 M", "1 day", "MIDPOINT", 1, 1, False, [])
        self.reqHistoricalData(4103, IBKRContract.EuropeanStock(), queryTime,
                               "10 D", "1 min", "TRADES", 1, 1, False, [])
        self.reqHistoricalData(4104, IBKRContract.EurGbpFx(), "",
                               "1 M", "1 day", "MIDPOINT", 1, 1, True, [])
        self.reqHistoricalData(4103, IBKRContract.USStockAtSmart(), queryTime,
                               "1 M", "1 day", "SCHEDULE", 1, 1, False, [])
        # ! [reqhistoricaldata]

    @printWhenExecuting
    def historicalDataOperations_cancel(self):
        # ! [cancelHeadTimestamp]
        self.cancelHeadTimeStamp(4101)
        # ! [cancelHeadTimestamp]
        
        # Canceling historical data requests
        # ! [cancelhistoricaldata]
        self.cancelHistoricalData(4102)
        self.cancelHistoricalData(4103)
        self.cancelHistoricalData(4104)
        # ! [cancelhistoricaldata]

    @printWhenExecuting
    def historicalTicksOperations(self):
        # ! [reqhistoricalticks]
        self.reqHistoricalTicks(18001, IBKRContract.USStockAtSmart(),
                                "20170712 21:39:33 US/Eastern", "", 10, "TRADES", 1, True, [])
        self.reqHistoricalTicks(18002, IBKRContract.USStockAtSmart(),
                                "20170712 21:39:33 US/Eastern", "", 10, "BID_ASK", 1, True, [])
        self.reqHistoricalTicks(18003, IBKRContract.USStockAtSmart(),
                                "20170712 21:39:33 US/Eastern", "", 10, "MIDPOINT", 1, True, [])
        # ! [reqhistoricalticks]


    @printWhenExecuting
    def optionsOperations_req(self):
        # ! [reqsecdefoptparams]
        self.reqSecDefOptParams(0, "IBM", "", "STK", 8314)
        # ! [reqsecdefoptparams]

        # Calculating implied volatility
        # ! [calculateimpliedvolatility]
        self.calculateImpliedVolatility(5001, IBKRContract.OptionWithLocalSymbol(), 0.5, 55, [])
        # ! [calculateimpliedvolatility]

        # Calculating option's price
        # ! [calculateoptionprice]
        self.calculateOptionPrice(5002, IBKRContract.OptionWithLocalSymbol(), 0.6, 55, [])
        # ! [calculateoptionprice]

        # Exercising options
        # ! [exercise_options]
        self.exerciseOptions(5003, IBKRContract.OptionWithTradingClass(), 1,
                             1, self.account, 1, "20231018-12:00:00", "CustAcct", True)
        # ! [exercise_options]

    @printWhenExecuting
    def optionsOperations_cancel(self):
        # Canceling implied volatility
        self.cancelCalculateImpliedVolatility(5001)
        # Canceling option's price calculation
        self.cancelCalculateOptionPrice(5002)




    @printWhenExecuting
    def contractOperations(self):
        # ! [reqcontractdetails]
        self.reqContractDetails(210, IBKRContract.OptionForQuery())
        self.reqContractDetails(211, IBKRContract.EurGbpFx())
        self.reqContractDetails(212, IBKRContract.Bond())
        self.reqContractDetails(213, IBKRContract.FuturesOnOptions())
        self.reqContractDetails(214, IBKRContract.SimpleFuture())
        self.reqContractDetails(215, IBKRContract.USStockAtSmart())
        self.reqContractDetails(216, IBKRContract.CryptoContract())
        self.reqContractDetails(217, IBKRContract.ByIssuerId())
        self.reqContractDetails(219, IBKRContract.FundContract())
        self.reqContractDetails(220, IBKRContract.USStock())
        self.reqContractDetails(221, IBKRContract.USStockAtSmart())
        # ! [reqcontractdetails]

        # ! [reqmatchingsymbols]
        self.reqMatchingSymbols(218, "IBM")
        # ! [reqmatchingsymbols]

    @printWhenExecuting
    def newsOperations_req(self):
        # Requesting news ticks
        # ! [reqNewsTicks]
        self.reqMktData(10001, IBKRContract.USStockAtSmart(), "mdoff,292", False, False, [])
        # ! [reqNewsTicks]

        # Returns list of subscribed news providers
        # ! [reqNewsProviders]
        self.reqNewsProviders()
        # ! [reqNewsProviders]

        # Returns body of news article given article ID
        # ! [reqNewsArticle]
        self.reqNewsArticle(10002,"BRFG", "BRFG$04fb9da2", [])
        # ! [reqNewsArticle]

        # Returns list of historical news headlines with IDs
        # ! [reqHistoricalNews]
        self.reqHistoricalNews(10003, 8314, "BRFG", "", "", 10, [])
        # ! [reqHistoricalNews]

        # ! [reqcontractdetailsnews]
        self.reqContractDetails(10004, IBKRContract.NewsFeedForQuery())
        # ! [reqcontractdetailsnews]

    @printWhenExecuting
    def newsOperations_cancel(self):
        # Canceling news ticks
        # ! [cancelNewsTicks]
        self.cancelMktData(10001)
        # ! [cancelNewsTicks]


    @printWhenExecuting
    def marketScannersOperations_req(self):
        # Requesting list of valid scanner parameters which can be used in TWS
        # ! [reqscannerparameters]
        self.reqScannerParameters()
        # ! [reqscannerparameters]

        # Triggering a scanner subscription
        # ! [reqscannersubscription]
        self.reqScannerSubscription(7001, IBKRScannerSubscription.HighOptVolumePCRatioUSIndexes(), [], [])

        # Generic Filters
        tagvalues = []
        tagvalues.append(TagValue("usdMarketCapAbove", "10000"))
        tagvalues.append(TagValue("optVolumeAbove", "1000"))
        tagvalues.append(TagValue("avgVolumeAbove", "10000"))

        self.reqScannerSubscription(7002, IBKRScannerSubscription.HotUSStkByVolume(), [], tagvalues) # requires TWS v973+
        # ! [reqscannersubscription]

        # ! [reqcomplexscanner]
        AAPLConIDTag = [TagValue("underConID", "265598")]
        self.reqScannerSubscription(7003, IBKRScannerSubscription.ComplexOrdersAndTrades(), [], AAPLConIDTag) # requires TWS v975+
        
        # ! [reqcomplexscanner]


    @printWhenExecuting
    def marketScanners_cancel(self):
        # Canceling the scanner subscription
        # ! [cancelscannersubscription]
        self.cancelScannerSubscription(7001)
        self.cancelScannerSubscription(7002)
        self.cancelScannerSubscription(7003)
        # ! [cancelscannersubscription]



    @printWhenExecuting
    def fundamentalsOperations_req(self):
        # Requesting Fundamentals
        # ! [reqfundamentaldata]
        self.reqFundamentalData(8001, IBKRContract.USStock(), "ReportsFinSummary", [])
        # ! [reqfundamentaldata]
        
        # ! [fundamentalexamples]
        self.reqFundamentalData(8002, IBKRContract.USStock(), "ReportSnapshot", []) # for company overview
        self.reqFundamentalData(8003, IBKRContract.USStock(), "ReportRatios", []) # for financial ratios
        self.reqFundamentalData(8004, IBKRContract.USStock(), "ReportsFinStatements", []) # for financial statements
        self.reqFundamentalData(8005, IBKRContract.USStock(), "RESC", []) # for analyst estimates
        self.reqFundamentalData(8006, IBKRContract.USStock(), "CalendarReport", []) # for company calendar
        # ! [fundamentalexamples]

    @printWhenExecuting
    def fundamentalsOperations_cancel(self):
        # Canceling fundamentalsOperations_req request
        # ! [cancelfundamentaldata]
        self.cancelFundamentalData(8001)
        # ! [cancelfundamentaldata]

        # ! [cancelfundamentalexamples]
        self.cancelFundamentalData(8002)
        self.cancelFundamentalData(8003)
        self.cancelFundamentalData(8004)
        self.cancelFundamentalData(8005)
        self.cancelFundamentalData(8006)
        # ! [cancelfundamentalexamples]


    @printWhenExecuting
    def bulletinsOperations_req(self):
        # Requesting Interactive Broker's news bulletinsOperations_req
        # ! [reqnewsbulletins]
        self.reqNewsBulletins(True)
        # ! [reqnewsbulletins]

    @printWhenExecuting
    def bulletinsOperations_cancel(self):
        # Canceling IB's news bulletinsOperations_req
        # ! [cancelnewsbulletins]
        self.cancelNewsBulletins()
        # ! [cancelnewsbulletins]




    def ocaSample(self):
        # OCA ORDER
        # ! [ocasubmit]
        ocaOrders = [IBKROrder.LimitOrder("BUY", 1, 10), IBKROrder.LimitOrder("BUY", 1, 11),
                     IBKROrder.LimitOrder("BUY", 1, 12)]
        IBKROrder.OneCancelsAll("TestOCA_" + str(self.nextValidOrderId), ocaOrders, 2)
        for o in ocaOrders:
            self.placeOrder(self.nextOrderId(), IBKRContract.USStockAtSmart(), o)
            # ! [ocasubmit]

    def conditionSamples(self):
        # ! [order_conditioning_activate]
        mkt = IBKROrder.MarketOrder("BUY", 100)
        # Order will become active if conditioning criteria is met
        mkt.conditions.append(
            IBKROrder.PriceCondition(PriceCondition.TriggerMethodEnum.Default,
                                        208813720, "SMART", 600, False, False))
        mkt.conditions.append(IBKROrder.ExecutionCondition("EUR.USD", "CASH", "IDEALPRO", True))
        mkt.conditions.append(IBKROrder.MarginCondition(30, True, False))
        mkt.conditions.append(IBKROrder.PercentageChangeCondition(15.0, 208813720, "SMART", True, True))
        mkt.conditions.append(IBKROrder.TimeCondition("20160118 23:59:59 US/Eastern", True, False))
        mkt.conditions.append(IBKROrder.VolumeCondition(208813720, "SMART", False, 100, True))
        self.placeOrder(self.nextOrderId(), IBKRContract.EuropeanStock(), mkt)
        # ! [order_conditioning_activate]

        # Conditions can make the order active or cancel it. Only LMT orders can be conditionally canceled.
        # ! [order_conditioning_cancel]
        lmt = IBKROrder.LimitOrder("BUY", 100, 20)
        # The active order will be cancelled if conditioning criteria is met
        lmt.conditionsCancelOrder = True
        lmt.conditions.append(
            IBKROrder.PriceCondition(PriceCondition.TriggerMethodEnum.Last,
                                        208813720, "SMART", 600, False, False))
        self.placeOrder(self.nextOrderId(), IBKRContract.EuropeanStock(), lmt)
        # ! [order_conditioning_cancel]

    def bracketSample(self):
        # BRACKET ORDER
        # ! [bracketsubmit]
        bracket = IBKROrder.BracketOrder(self.nextOrderId(), "BUY", 100, 30, 40, 20)
        for o in bracket:
            self.placeOrder(o.orderId, IBKRContract.EuropeanStock(), o)
            self.nextOrderId()  # need to advance this we'll skip one extra oid, it's fine
            # ! [bracketsubmit]

    def hedgeSample(self):
        # F Hedge order
        # ! [hedgesubmit]
        # Parent order on a contract which currency differs from your base currency
        parent = IBKROrder.LimitOrder("BUY", 100, 10)
        parent.orderId = self.nextOrderId()
        parent.transmit = False
        # Hedge on the currency conversion
        hedge = IBKROrder.MarketFHedge(parent.orderId, "BUY")
        # Place the parent first...
        self.placeOrder(parent.orderId, IBKRContract.EuropeanStock(), parent)
        # Then the hedge order
        self.placeOrder(self.nextOrderId(), IBKRContract.EurGbpFx(), hedge)
        # ! [hedgesubmit]





    def wshCalendarOperations(self):
        # ! [reqmetadata]
        self.reqWshMetaData(1100)
        # ! [reqmetadata]

        # ! [reqeventdata]
        wshEventData1 = WshEventData()
        wshEventData1.conId = 8314
        wshEventData1.startDate = "20220511"
        wshEventData1.totalLimit = 5
        self.reqWshEventData(1101, wshEventData1)
        # ! [reqeventdata]

        # ! [reqeventdata]
        wshEventData2 = WshEventData()
        wshEventData2.filter = "{\"watchlist\":[\"8314\"]}"
        wshEventData2.fillWatchlist = False
        wshEventData2.fillPortfolio = False
        wshEventData2.fillCompetitors = False
        wshEventData2.endDate = "20220512"
        self.reqWshEventData(1102, wshEventData2)
        # ! [reqeventdata]



    @printWhenExecuting
    def miscelaneousOperations(self):
        # Request TWS' current time
        self.reqCurrentTime()
        # Setting TWS logging level
        self.setServerLogLevel(1)

    @printWhenExecuting
    def linkingOperations(self):
        # ! [querydisplaygroups]
        self.queryDisplayGroups(19001)
        # ! [querydisplaygroups]

        # ! [subscribetogroupevents]
        self.subscribeToGroupEvents(19002, 1)
        # ! [subscribetogroupevents]

        # ! [updatedisplaygroup]
        self.updateDisplayGroup(19002, "8314@SMART")
        # ! [updatedisplaygroup]

        # ! [subscribefromgroupevents]
        self.unsubscribeFromGroupEvents(19002)
        # ! [subscribefromgroupevents]


    @printWhenExecuting
    def whatIfOrderOperations(self):
    # ! [whatiflimitorder]
        whatIfOrder = IBKROrder.LimitOrder("BUY", 100, 20)
        whatIfOrder.whatIf = True
        self.placeOrder(self.nextOrderId(), IBKRContract.BondWithCusip(), whatIfOrder)
    # ! [whatiflimitorder]
        time.sleep(2)

    @printWhenExecuting
    def orderOperations_req(self):
        # Requesting the next valid id
        # ! [reqids]
        # The parameter is always ignored.
        self.reqIds(-1)
        # ! [reqids]

        # Requesting all open orders
        # ! [reqallopenorders]
        self.reqAllOpenOrders()
        # ! [reqallopenorders]

        # Taking over orders to be submitted via TWS
        # ! [reqautoopenorders]
        self.reqAutoOpenOrders(True)
        # ! [reqautoopenorders]

        # Requesting this API client's orders
        # ! [reqopenorders]
        self.reqOpenOrders()
        # ! [reqopenorders]

        # Placing/modifying an order - remember to ALWAYS increment the
        # nextValidId after placing an order so it can be used for the next one!
        # Note if there are multiple clients connected to an account, the
        # order ID must also be greater than all order IDs returned for orders
        # to orderStatus and openOrder to this client.

        # ! [order_submission]
        self.simplePlaceOid = self.nextOrderId()
        self.placeOrder(self.simplePlaceOid, IBKRContract.USStock(),
                        IBKROrder.LimitOrder("SELL", 1, 50))
        # ! [order_submission]

        # ! [faorderoneaccount]
        faOrderOneAccount = IBKROrder.MarketOrder("BUY", 100)
        # Specify the Account Number directly
        faOrderOneAccount.account = "DU119915"
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(), faOrderOneAccount)
        # ! [faorderoneaccount]

        # ! [faordergroup]
        faOrderGroup = IBKROrder.LimitOrder("BUY", 200, 10)
        faOrderGroup.faGroup = "MyTestGroup1"
        faOrderGroup.faMethod = "AvailableEquity"
        self.placeOrder(self.nextOrderId(), IBKRContract.USStockAtSmart(), faOrderGroup)
        # ! [faordergroup]

        # ! [faorderuserdefinedgroup]
        faOrderUserDefinedGroup = IBKROrder.LimitOrder("BUY", 200, 10)
        faOrderUserDefinedGroup.faGroup = "MyTestProfile1"
        self.placeOrder(self.nextOrderId(), IBKRContract.USStockAtSmart(), faOrderUserDefinedGroup)
        # ! [faorderuserdefinedgroup]

        # ! [modelorder]
        modelOrder = IBKROrder.LimitOrder("BUY", 200, 100)
        modelOrder.account = "DF12345"
        modelOrder.modelCode = "Technology" # model for tech stocks first created in TWS
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(), modelOrder)
        # ! [modelorder]

        self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtBOX(),
                        IBKROrder.Block("BUY", 50, 20))
        self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtBOX(),
                         IBKROrder.BoxTop("SELL", 10))
        self.placeOrder(self.nextOrderId(), IBKRContract.FutureComboContract(),
                         IBKROrder.ComboLimitOrder("SELL", 1, 1, False))
        self.placeOrder(self.nextOrderId(), IBKRContract.StockComboContract(),
                          IBKROrder.ComboMarketOrder("BUY", 1, True))
        self.placeOrder(self.nextOrderId(), IBKRContract.OptionComboContract(),
                          IBKROrder.ComboMarketOrder("BUY", 1, False))
        self.placeOrder(self.nextOrderId(), IBKRContract.StockComboContract(),
                          IBKROrder.LimitOrderForComboWithLegPrices("BUY", 1, [10, 5], True))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                         IBKROrder.Discretionary("SELL", 1, 45, 0.5))
        self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtBOX(),
                          IBKROrder.LimitIfTouched("BUY", 1, 30, 34))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.LimitOnClose("SELL", 1, 34))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.LimitOnOpen("BUY", 1, 35))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.MarketIfTouched("BUY", 1, 30))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                         IBKROrder.MarketOnClose("SELL", 1))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.MarketOnOpen("BUY", 1))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.MarketOrder("SELL", 1))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.MarketToLimit("BUY", 1))
        self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtIse(),
                          IBKROrder.MidpointMatch("BUY", 1))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.MarketToLimit("BUY", 1))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.Stop("SELL", 1, 34.4))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.StopLimit("BUY", 1, 35, 33))
        self.placeOrder(self.nextOrderId(), IBKRContract.SimpleFuture(),
                          IBKROrder.StopWithProtection("SELL", 1, 45))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.SweepToFill("BUY", 1, 35))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.TrailingStop("SELL", 1, 0.5, 30))
        self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
                          IBKROrder.TrailingStopLimit("BUY", 1, 2, 5, 50))
        self.placeOrder(self.nextOrderId(), IBKRContract.USOptionContract(),
                         IBKROrder.Volatility("SELL", 1, 5, 2))

        self.bracketSample()

        self.conditionSamples()

        self.hedgeSample()

        # NOTE: the following orders are not supported for Paper Trading
        # self.placeOrder(self.nextOrderId(), IBKRContract.USStock(), IBKROrder.AtAuction("BUY", 100, 30.0))
        # self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtBOX(), IBKROrder.AuctionLimit("SELL", 10, 30.0, 2))
        # self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtBOX(), IBKROrder.AuctionPeggedToStock("BUY", 10, 30, 0.5))
        # self.placeOrder(self.nextOrderId(), IBKRContract.OptionAtBOX(), IBKROrder.AuctionRelative("SELL", 10, 0.6))
        # self.placeOrder(self.nextOrderId(), IBKRContract.SimpleFuture(), IBKROrder.MarketWithProtection("BUY", 1))
        # self.placeOrder(self.nextOrderId(), IBKRContract.USStock(), IBKROrder.PassiveRelative("BUY", 1, 0.5))

        # 208813720 (GOOG)
        # self.placeOrder(self.nextOrderId(), IBKRContract.USStock(),
        #    IBKROrder.PeggedToBenchmark("SELL", 100, 33, True, 0.1, 1, 208813720, "ARCA", 750, 650, 800))

        # STOP ADJUSTABLE ORDERS
        # Order stpParent = IBKROrder.Stop("SELL", 100, 30)
        # stpParent.OrderId = self.nextOrderId()
        # self.placeOrder(stpParent.OrderId, IBKRContract.EuropeanStock(), stpParent)
        # self.placeOrder(self.nextOrderId(), IBKRContract.EuropeanStock(), IBKROrder.AttachAdjustableToStop(stpParent, 35, 32, 33))
        # self.placeOrder(self.nextOrderId(), IBKRContract.EuropeanStock(), IBKROrder.AttachAdjustableToStopLimit(stpParent, 35, 33, 32, 33))
        # self.placeOrder(self.nextOrderId(), IBKRContract.EuropeanStock(), IBKROrder.AttachAdjustableToTrail(stpParent, 35, 32, 32, 1, 0))

        # Order lmtParent = IBKROrder.LimitOrder("BUY", 100, 30)
        # lmtParent.OrderId = self.nextOrderId()
        # self.placeOrder(lmtParent.OrderId, IBKRContract.EuropeanStock(), lmtParent)
        # Attached TRAIL adjusted can only be attached to LMT parent orders.
        # self.placeOrder(self.nextOrderId(), IBKRContract.EuropeanStock(), IBKROrder.AttachAdjustableToTrailAmount(lmtParent, 34, 32, 33, 0.008))
        self.algoSamples()
        
        self.ocaSample()

        # Request the day's executions
        # ! [reqexecutions]
        self.reqExecutions(10001, ExecutionFilter())
        # ! [reqexecutions]
        
        # Requesting completed orders
        # ! [reqcompletedorders]
        self.reqCompletedOrders(False)
        # ! [reqcompletedorders]
        
        # Placing crypto order
        # ! [cryptoplaceorder]
        self.placeOrder(self.nextOrderId(), IBKRContract.CryptoContract(), IBKROrder.LimitOrder("BUY", Decimal("0.00001234"), 3370))
        # ! [cryptoplaceorder]
        

        # Placing limit order with manual order time
        # ! [place_order_with_manual_order_time]
        self.placeOrder(self.nextOrderId(), IBKRContract.USStockAtSmart(), IBKROrder.LimitOrderWithManualOrderTime("BUY", Decimal("100"), 111.11, "20220314-13:00:00"))
        # ! [place_order_with_manual_order_time]

        # Placing peg best up to mid order
        # ! [place_peg_best_up_to_mid_order]
        self.placeOrder(self.nextOrderId(), IBKRContract.IBKRATSContract(), IBKROrder.PegBestUpToMidOrder("BUY", Decimal("100"), 111.11, 100, 200, 0.02, 0.025))
        # ! [place_peg_best_up_to_mid_order]

        # Placing peg best order
        # ! [place_peg_best_order]
        self.placeOrder(self.nextOrderId(), IBKRContract.IBKRATSContract(), IBKROrder.PegBestOrder("BUY", Decimal("100"), 111.11, 100, 200, 0.03))
        # ! [place_peg_best_order]

        # Placing peg mid order
        # ! [place_peg_mid_order]
        self.placeOrder(self.nextOrderId(), IBKRContract.IBKRATSContract(), IBKROrder.PegMidOrder("BUY", Decimal("100"), 111.11, 100, 0.02, 0.025))
        # ! [place_peg_mid_order]

        # Placing limit order with customer accounte
        # ! [place_order_with_customer_account]
        self.placeOrder(self.nextOrderId(), IBKRContract.USStockAtSmart(), IBKROrder.LimitOrderWithCustomerAccount("BUY", Decimal("100"), 111.11, "CustAcct"))
        # ! [place_order_with_customer_account]

    def orderOperations_cancel(self):
        if self.simplePlaceOid is not None:
            # ! [cancelorder]
            self.cancelOrder(self.simplePlaceOid, IBKROrder.CancelOrderEmpty())
            # ! [cancelorder]
            
        # Cancel all orders for all accounts
        # ! [reqglobalcancel]
        self.reqGlobalCancel()
        # ! [reqglobalcancel]
         
        # Cancel limit order with manual order cancel time
        if self.simplePlaceOid is not None:
            # ! [cancel_order_with_manual_order_time]
            self.cancelOrder(self.simplePlaceOid, IBKROrder.CancelOrderWithManualTime("20240614-00:00:10"))
            # ! [cancel_order_with_manual_order_time]

    def rerouteCFDOperations(self):
        # ! [reqmktdatacfd]
        self.reqMktData(16001, IBKRContract.USStockCFD(), "", False, False, [])
        self.reqMktData(16002, IBKRContract.EuropeanStockCFD(), "", False, False, [])
        self.reqMktData(16003, IBKRContract.CashCFD(), "", False, False, [])
        # ! [reqmktdatacfd]

        # ! [reqmktdepthcfd]
        self.reqMktDepth(16004, IBKRContract.USStockCFD(), 10, False, [])
        self.reqMktDepth(16005, IBKRContract.EuropeanStockCFD(), 10, False, [])
        self.reqMktDepth(16006, IBKRContract.CashCFD(), 10, False, [])
        # ! [reqmktdepthcfd]

    def marketRuleOperations(self):
        self.reqContractDetails(17001, IBKRContract.USStock())
        self.reqContractDetails(17002, IBKRContract.Bond())

        # ! [reqmarketrule]
        self.reqMarketRule(26)
        self.reqMarketRule(239)
        # ! [reqmarketrule]
        
    def ibkratsSample(self):
        # ! [ibkratssubmit]
        ibkratsOrder = IBKROrder.LimitIBKRATS("BUY", 100, 330)
        self.placeOrder(self.nextOrderId(), IBKRContract.IBKRATSContract(), ibkratsOrder)
        # ! [ibkratssubmit]

    @printWhenExecuting
    def rfqOperations(self):
        # ! [rfq_submission]
        self.simplePlaceOid = self.nextOrderId()
        self.placeOrder(self.simplePlaceOid, IBKRContract.BondWithCusip(), IBKROrder.RfqEmpty())
        # ! [rfq_submission]

        time.sleep(5)

        if self.simplePlaceOid is not None:
            # ! [rfq_cancel]
            self.cancelOrder(self.simplePlaceOid, IBKROrder.RfqCancel())
            # ! [rfq_cancel]

        time.sleep(1)

        # ! [rfq_submission]
        self.placeOrder(self.nextOrderId(), IBKRContract.BondWithCusip(), IBKROrder.Rfq())
        # ! [rfq_submission]

