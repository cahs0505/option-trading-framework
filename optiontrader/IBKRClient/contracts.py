from ibapi.contract import * 
from typing import List

class IBContract:
    """
    Provide static methods for creating IB Contract. Mainly used for submitting orders
    """
    @staticmethod
    def Index(
        symbol: str,
        exchange : str = "SMART",
        currency : str = "USD"
    ) -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "IND"
        contract.currency = currency
        contract.exchange = exchange

        return contract

    @staticmethod
    def Commodity(
        symbol: str,
        exchange : str = "SMART",
        currency : str = "USD"
    ) -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "CMDTY"
        contract.exchange = exchange
        contract.currency = currency

        return contract
    
    @staticmethod
    def USStock(
        symbol : str, 
        exchange : str = "SMART",
        currency : str = "USD"
    ) -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = currency
        contract.exchange = exchange

        return contract
    
    @staticmethod
    def USStockWithPrimaryExch(
        symbol : str,          
        primaryExchange: str,
        exchange : str = "SMART",
        currency : str = "USD"
    ) -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = currency
        contract.exchange = exchange
        contract.primaryExchange = primaryExchange

        return contract
            
    @staticmethod
    def USStockAtSmart(symbol : str) -> Contract:
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "SMART"

        return contract
    
    @staticmethod
    def EuropeanStock(
        symbol : str, 
        primaryExchange: str,
        exchange : str = "SMART",
        currency : str = "EUR"
        ) -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = exchange
        contract.exchange = currency
        contract.primaryExchange = primaryExchange
        return contract


    @staticmethod
    def etf(
        symbol: str,
        exchange: str = "SMART",
        currency: str = "USD"
        ) -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = currency
        contract.exchange = exchange

        return contract
    
    @staticmethod
    def USOptionContract(
        symbol: str,
        expiry: str,
        strike: int,
        right: str,
        exchange: str = "SMART",
        currency: str = "USD",
        multiplier: str = "100"
        ) -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency
        contract.lastTradeDateOrContractMonth = expiry
        contract.strike = strike
        contract.right = right
        contract.multiplier = multiplier

        return contract

    @staticmethod
    def OptionWithTradingClass(
        symbol: str,
        expiry: str,
        exchange: str,
        strike: int,
        right: str,
        tradingClass: str, 
        currency: str = "USD",
        multiplier: str = "100"
        ) -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency
        contract.lastTradeDateOrContractMonth = expiry
        contract.strike = strike
        contract.right = right
        contract.multiplier = multiplier
        contract.tradingClass = tradingClass

        return contract

    @staticmethod
    def OptionWithLocalSymbol(
        localSymbol: str,
        exchange : str = "CBOE",
        currency:str = "USD"
        ) -> Contract:

        contract = Contract()
        contract.localSymbol = localSymbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency

        return contract

    @staticmethod
    def OptionForQuery(
        symbol: str,
        exchange: str = "SMART",
        currency: str = "USD"
        ) -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency

        return contract

    @staticmethod
    def OptionComboContract(
        symbol: str,
        legs: List,
        exchange : str = "SMART",
        currency : str = "USD"
        ) -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "BAG"
        contract.currency = currency
        contract.exchange = exchange

        contract.comboLegs = []
        for leg in legs:
            curr_leg = ComboLeg()
            curr_leg.conId = leg['con_id']
            curr_leg.ratio = leg['quantity']
            curr_leg.action = leg['action']
            curr_leg.exchange = exchange
            contract.comboLegs.append(curr_leg)
            
        return contract

    @staticmethod
    def ByConId(
        secType: str,
        conId: int,
        exchange: str = "SMART"
        ) -> Contract:

        contract = Contract()
        contract.secType = secType
        contract.conId = conId
        contract.exchange = exchange
        
        return contract