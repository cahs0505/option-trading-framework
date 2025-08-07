from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from ibapi.contract import *

"""
ID Scheme consistant with IB official examples
"""

class RequestStatus(Enum):

    INIT = auto()               #initiated
    PROCESSED = auto()          #Sent to IBKR
    RESPONDED = auto()          #Recevied response to IBKR
    CANCEL = auto()             #cancelled by client

class RequestType(Enum):
    MARKET_DATA = auto()
    MARKET_DEPTH = auto()
    OPEN_ORDER = auto()
    REAL_TIME_BAR = auto()
    HISTORICAL_DATA = auto()
    ACCOUNT_SUMMARY = auto()
    ACCOUNT_UPDATE = auto()
    PNL = auto()

class BaseRequest(metaclass=ABCMeta):

    id: int
    status: RequestStatus
    type: RequestType
    isSubscription: bool

    @abstractmethod
    def __init__(self):
        self.status = RequestStatus.INIT
        pass

    @abstractmethod
    def __eq__(self, other):
        return self.type == other.type

    @abstractmethod
    def get_id(self):
        return self.id
    
    @abstractmethod
    def set_id(self, id:int):
        self.id = id
        return id
    
    @abstractmethod
    def get_status(self):
        return self.status
    
    @abstractmethod
    def set_status(self, status:RequestStatus):
        self.status = status
        return status

"""
id: 1000, 1001, 1002...
"""
class MarketDataRequest(BaseRequest):
    
    contract: Contract
    genericTickList: str
    snapshot: bool
    regulatorySnapshot: bool


    def __init__(self,
                contract: Contract,
                genericTickList: str,
                snapshot: bool,
                regulatorySnapshot: bool):
        
        self.type = RequestType.MARKET_DATA
        self.isSubscription = True

        self.contract = contract
        self.genericTickList = genericTickList
        self.snapshot = snapshot
        self.regulatorySnapshot = regulatorySnapshot
        

    def __eq__(self, other):

        contract_equal = (self.contract.secType == other.contract.secType) and (self.contract.symbol == other.contract.symbol) and (self.contract.currency == other.contract.currency) and (self.contract.exchange == other.contract.exchange)
        
        return super().__eq__(other) and contract_equal and (self.genericTickList == other.genericTickList) and (self.snapshot == other.snapshot) and (self.regulatorySnapshot == other.regulatorySnapshot )
     
        

    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
"""
id: 2000, 2001, 2002...
"""
class MarketDepthRequest(BaseRequest):
    
    contract: Contract
    numRows: int
    isSmartDepth: bool

    def __init__(self,
                contract: Contract,
                numRows: int,
                isSmartDepth: bool):
        
        self.type = RequestType.MARKET_DEPTH
        self.isSubscription = True

        self.contract = contract
        self.numRows = numRows
        self.isSmartDepth = isSmartDepth
        

    def __eq__(self, other):

        contract_equal = (self.contract.secType == other.contract.secType) and (self.contract.symbol == other.contract.symbol) and (self.contract.currency == other.contract.currency) and (self.contract.exchange == other.contract.exchange)
        
        return super.__eq__(other) and contract_equal and (self.numRows == other.numRows) and (self.isSmartDepth == other.isSmartDepth)
     
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
"""
id: 3000, 3001, 3002...
"""
class RealTimeBarRequest(BaseRequest):
    
    contract: Contract
    barSize: int
    whatToShow: str
    useRTH: bool
 

    def __init__(self,
                contract: Contract,
                barSize: int,
                whatToShow: str,
                useRTH: bool):

        self.type = RequestType.REAL_TIME_BAR
        self.isSubscription = True

        self.contract = contract
        self.barSize = barSize
        self.whatToShow = whatToShow
        self.useRTH = useRTH
        

    def __eq__(self, other):

        contract_equal = (self.contract.secType == other.contract.secType) and (self.contract.symbol == other.contract.symbol) and (self.contract.currency == other.contract.currency) and (self.contract.exchange == other.contract.exchange)
        
        return super.__eq__(other) and contract_equal and (self.barSize == other.barSize) and (self.whatToShow == other.whatToShow) and (self.useRTH == other.useRTH)
     
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
"""
id: 4100, 4101, 4102...
"""
class HistoricalDataRequest(BaseRequest):
    
    contract: Contract
    endDateTime: str
    durationStr: str
    barSizeSetting: str
    whatToShow: str
    useRTH: int
    formatDate: int
    keepUpToDate: bool


    def __init__(self,
                contract: Contract,
                endDateTime: str,
                durationStr: str,
                barSizeSetting: str,
                whatToShow: str,
                useRTH: int,
                formatDate: int,
                keepUpToDate: bool):
        
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

        contract_equal = (self.contract.secType == other.contract.secType) and (self.contract.symbol == other.contract.symbol) and (self.contract.currency == other.contract.currency) and (self.contract.exchange == other.contract.exchange)
        
        return super.__eq__(other) and contract_equal and (self.endDateTime == other.endDateTime) and (self.durationStr == other.durationStr) and (self.barSizeSetting == other.barSizeSetting) and (self.whatToShow == other.whatToShow) and (self.useRTH == other.useRTH) and (self.formatDate == other.formatDate) and (self.keepUpToDate == other.keepUpToDate)
     
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
"""
id: 9000, 9001, 9002...
"""
class AccountSummaryRequest(BaseRequest):
    
    groupName: str
    tags: str

    def __init__(self,
                groupName: str,
                tags: str):
        
        self.type = RequestType.ACCOUNT_SUMMARY
        self.isSubscription = True

        self.groupName = groupName
        self.tags = tags
        
    def __eq__(self, other):

        return super().__eq__(other) and self.groupName == other.groupName and self.tags == other.tags
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status


"""
id: 9100, 9101, 9102...
"""
class AccountUpdateRequest(BaseRequest):
    
    subscribe: bool
    acctCode: str

    def __init__(self,
                subscribe: bool, 
                acctCode: str):
        
        self.type = RequestType.ACCOUNT_UPDATE
        self.isSubscription = True

        self.subscribe = subscribe
        self.acctCode = acctCode
        
    def __eq__(self, other):

        return super().__eq__(other) and self.subscribe == other.subscribe and self.acctCode == other.acctCode
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
"""
id: 9200 
"""
class AccountOpenOrderRequest(BaseRequest):

    def __init__(self):
        self.type = RequestType.OPEN_ORDER
        self.isSubscription = False

    def __eq__(self, other) -> bool:
        return True
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    

    
"""
id: 17000, 17001, 17002...
"""
class PnLRequest(BaseRequest):
    
    account: str
    modelCode: str

    def __init__(self,
                account: str, 
                modelCode: str):
        
        self.type = RequestType.PNL
        self.isSubscription = False

        self.account = account
        self.modelCode = modelCode
        
    def __eq__(self, other):
        
        return super.__eq__(other) and self.account == other.account and self.modelCode == other.modelCode
        
    def get_id(self) -> int:
        return self.id
    
    def set_id(self, id:int) -> int:
        self.id = id
        return id
    
    def get_status(self):
        return self.status
    
    def set_status(self, status:RequestStatus):
        self.status = status
        return status
    
if __name__ == "__main__":
    req1 = AccountSummaryRequest("aLL","aaa")
    req2 = AccountUpdateRequest(True, "BBB")
    req3 = AccountUpdateRequest(True, "BBB")
    req4 = AccountUpdateRequest(False,"BBB")

    print(req1==req2)
    print(req2==req3)
    print(req3==req4)
