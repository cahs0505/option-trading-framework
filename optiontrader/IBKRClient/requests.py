from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from ibapi.contract import Contract

class RequestStatus(Enum):
    INIT = 'INIT'               
    PROCESSED = 'PROCESSED'    
    RESPONDED = 'RESPONDED'          
    ERROR = 'ERROR'
    FINISHED = 'FINISHED'
    CANCEL = 'CANCELLED'

class RequestType(Enum):
    MARKET_DATA = auto()
    MARKET_DATA_TYPE = auto()
    OPTION_CHAIN = auto()
    MARKET_DEPTH = auto()
    CONTRACT_DETAIL = auto()
    OPEN_ORDER = auto()
    COMPLETED_ORDERS = auto()
    EXECUTION_DETAILS = auto()
    REAL_TIME_BAR = auto()
    HISTORICAL_DATA = auto()
    ACCOUNT_SUMMARY = auto()
    ACCOUNT_UPDATE = auto()
    PNL = auto()
    PNL_SINGLE = auto()

class BaseRequest(metaclass=ABCMeta):
    id: int
    status: RequestStatus
    type: RequestType
    isSubscription: bool
    error_code: int
    error_msg: str

    @abstractmethod
    def __init__(self):
        self.status = RequestStatus.INIT
        pass

    @abstractmethod
    def __eq__(self, other):
        return self.type == other.type

    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int):
        self.id = id
        return id
    
    def get_status(self) -> RequestStatus:
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
    def set_error(self, error_code: int, error_msg: str):
        self.error_code = error_code
        self.error_msg = error_msg

class MarketDataRequest(BaseRequest):
    
    contract: Contract
    genericTickList: str
    snapshot: bool
    regulatorySnapshot: bool

    def __init__(
        self,
        contract: Contract,
        genericTickList: str = "",
        snapshot: bool = False,
        regulatorySnapshot: bool = False
    ):
        
        self.type = RequestType.MARKET_DATA
        self.isSubscription = True
        self.contract = contract
        self.genericTickList = genericTickList
        self.snapshot = snapshot
        self.regulatorySnapshot = regulatorySnapshot
        
    def __eq__(self, other):
        if isinstance(other, MarketDataRequest):
            these_values = self.contract.secType, self.contract.symbol, self.contract.lastTradeDateOrContractMonth, self.contract.strike, self.contract.right, self.contract.conId
            other_values = other.contract.secType, other.contract.symbol, other.contract.lastTradeDateOrContractMonth, other.contract.strike, other.contract.right, other.contract.conId
            return these_values == other_values
        
        return NotImplemented
        
class MarketDataTypeRequest(BaseRequest):
    
    market_data_type: int

    def __init__(self, market_data_type: int):
        self.type = RequestType.MARKET_DATA_TYPE
        self.isSubscription = False
        self.market_data_type = market_data_type

    def __eq__(self, other):
        if isinstance(other, MarketDataTypeRequest):
            these_values = self.market_data_type
            other_values = other.market_data_type
            return these_values == other_values
        
        return NotImplemented

class OptionChainRequest(BaseRequest):
    
    underlyingSymbol: str
    futFopExchange: str
    underlyingSecType: str
    underlyingConId: int

    def __init__(
        self,
        symbol: str,
        security_type: str,
        conId: int,
        exchange: str = 'SMART'
    ):
        self.type = RequestType.OPTION_CHAIN
        self.isSubscription = True
        self.underlyingSymbol = symbol
        self.futFopExchange = exchange
        self.underlyingSecType = security_type
        self.underlyingConId = conId
        
    def __eq__(self, other):
        if isinstance(other, OptionChainRequest):
            these_values = self.underlyingSymbol, self.futFopExchange, self.underlyingSecType, self.underlyingConId
            other_values = other.underlyingSymbol, other.futFopExchange, other.underlyingSecType, other.underlyingConId
            return these_values == other_values
        
        return NotImplemented
        
class MarketDepthRequest(BaseRequest):
    
    contract: Contract
    numRows: int
    isSmartDepth: bool

    def __init__(
        self,
        contract: Contract,
        numRows: int,
        isSmartDepth: bool
    ):
        self.type = RequestType.MARKET_DEPTH
        self.isSubscription = True
        self.contract = contract
        self.numRows = numRows
        self.isSmartDepth = isSmartDepth

    def __eq__(self, other):
        if isinstance(other, MarketDepthRequest):
            these_values = self.contract.secType, self.contract.symbol, self.contract.currency, self.contract.exchange
            other_values = other.contract.secType, other.contract.symbol, other.contract.currency, other.contract.exchange
            return these_values == other_values
        
        return NotImplemented
        
class ContractDetailRequest(BaseRequest):
    
    contract: Contract

    def __init__(self, contract: Contract):
        self.type = RequestType.CONTRACT_DETAIL
        self.isSubscription = True
        self.contract = contract

    def __eq__(self, other):
        if isinstance(other, ContractDetailRequest):
            these_values = self.contract.secType, self.contract.symbol, self.contract.lastTradeDateOrContractMonth, self.contract.strike, self.contract.right
            other_values = other.contract.secType, other.contract.symbol, other.contract.lastTradeDateOrContractMonth, other.contract.strike, other.contract.right
            return these_values == other_values
        
        return NotImplemented
         
class RealTimeBarRequest(BaseRequest):
    
    contract: Contract
    barSize: int
    whatToShow: str
    useRTH: bool
 
    def __init__(
        self,
        contract: Contract,
        barSize: int,
        whatToShow: str,
        useRTH: bool
    ):
        self.type = RequestType.REAL_TIME_BAR
        self.isSubscription = True
        self.contract = contract
        self.barSize = barSize
        self.whatToShow = whatToShow
        self.useRTH = useRTH
        
    def __eq__(self, other):
        if isinstance(other, RealTimeBarRequest):
            these_values = self.contract.secType, self.contract.symbol, self.contract.currency, self.contract.exchange, self.barSize, self.whatToShow, self.useRTH
            other_values = other.contract.secType, other.contract.symbol, other.contract.currency, other.contract.exchange, other.barSize, other.whatToShow, other.useRTH
            return these_values == other_values
        
        return NotImplemented
 
class HistoricalDataRequest(BaseRequest):
    
    contract: Contract
    endDateTime: str
    durationStr: str
    barSizeSetting: str
    whatToShow: str
    useRTH: int
    formatDate: int
    keepUpToDate: bool

    def __init__(
        self,
        contract: Contract,
        endDateTime: str,
        durationStr: str,
        barSizeSetting: str,
        whatToShow: str,
        useRTH: int,
        formatDate: int,
        keepUpToDate: bool
    ):
        self.type = RequestType.HISTORICAL_DATA
        self.isSubscription = True
        self.contract = contract
        self.endDateTime = endDateTime
        self.durationStr = durationStr
        self.barSizeSetting =barSizeSetting
        self.whatToShow = whatToShow
        self.useRTH = useRTH
        self.formatDate = formatDate
        self.keepUpToDate = keepUpToDate

    def __eq__(self, other):
        if isinstance(other, HistoricalDataRequest):
            these_values = self.contract.secType, 
            self.contract.symbol, 
            self.contract.currency, 
            self.contract.exchange, 
            self.endDateTime,
            self.durationStr,
            self.whatToShow,
            self.useRTH,
            self.formatDate,
            self.keepUpToDate

            other_values = other.contract.secType, 
            other.contract.symbol, 
            other.contract.currency, 
            other.contract.exchange,
            other.endDateTime,
            other.durationStr,
            other.whatToShow,
            other.useRTH,
            other.formatDate,
            other.keepUpToDate

            return these_values == other_values
        
        return NotImplemented     
        
class AccountSummaryRequest(BaseRequest):
    
    groupName: str
    tags: str

    def __init__(self, groupName: str, tags: str):
        self.type = RequestType.ACCOUNT_SUMMARY
        self.isSubscription = True
        self.groupName = groupName
        self.tags = tags
        
    def __eq__(self, other):
        if isinstance(other, AccountSummaryRequest):
            these_values = self.groupName, self.tags
            other_values = other.groupName, other.tags
            return these_values == other_values
        
        return NotImplemented
        
class AccountUpdateRequest(BaseRequest):
    
    subscribe: bool
    acctCode: str

    def __init__(self,subscribe: bool, acctCode: str):
        self.type = RequestType.ACCOUNT_UPDATE
        self.isSubscription = True
        self.subscribe = subscribe
        self.acctCode = acctCode
        
    def __eq__(self, other):

        if isinstance(other, AccountUpdateRequest):
            these_values = self.subscribe, self.acctCode
            other_values = other.subscribe, other.acctCode
            return these_values == other_values
        
        return NotImplemented
    
class AccountOpenOrderRequest(BaseRequest):

    def __init__(self):
        self.type = RequestType.OPEN_ORDER
        self.isSubscription = False

    def __eq__(self, other) -> bool:

        if isinstance(other, AccountOpenOrderRequest):
            return super().__eq__(other) 
        
        return NotImplemented
    
class AccountCompletedOrderRequest(BaseRequest):

    def __init__(self):
        self.type = RequestType.COMPLETED_ORDERS
        self.isSubscription = False

    def __eq__(self, other) -> bool:

        if isinstance(other, AccountCompletedOrderRequest):
            return super().__eq__(other) 
        
        return NotImplemented
    
class ExecutionDetailRequest(BaseRequest):

    def __init__(self):
        self.type = RequestType.EXECUTION_DETAILS
        self.isSubscription = False

    def __eq__(self, other) -> bool:

        if isinstance(other, ExecutionDetailRequest):
            return super().__eq__(other) 
        
        return NotImplemented
    
class PnLRequest(BaseRequest):
    
    account: str
    modelCode: str

    def __init__(self, account: str, modelCode: str):
        
        self.type = RequestType.PNL
        self.isSubscription = True
        self.account = account
        self.modelCode = modelCode
        
    def __eq__(self, other):

        if isinstance(other, PnLRequest):
            these_values = self.account, self.modelCode
            other_values = other.account, other.modelCode
            return these_values == other_values
        
        return NotImplemented
            
class PnLSingleRequest(BaseRequest):
    
    account: str
    modelCode: str
    conId: int

    def __init__(self, account: str, modelCode: str, conId: int):
        
        self.type = RequestType.PNL_SINGLE
        self.isSubscription = True
        self.conId = conId
        self.account = account
        self.modelCode = modelCode
        
    def __eq__(self, other):

        if isinstance(other, PnLSingleRequest):
            these_values = self.account, self.modelCode, self.conId
            other_values = other.account, other.modelCode, other.conId
            return these_values == other_values
        
        return NotImplemented