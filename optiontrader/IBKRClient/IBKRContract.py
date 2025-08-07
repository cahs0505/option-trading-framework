"""
Copyright (C) 2024 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable.
"""

from ibapi.contract import * # @UnusedWildImport


class IBKRContract:


    @staticmethod
    def Index(symbol: str,
              exchange : str = "SMART",
              currency : str = "USD") -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "IND"
        contract.currency = currency
        contract.exchange = exchange

        return contract

    @staticmethod
    def Commodity(symbol: str,
                  exchange : str = "SMART",
                  currency : str = "USD") -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "CMDTY"
        contract.exchange = exchange
        contract.currency = currency

        return contract
    

    @staticmethod
    def USStock(symbol : str, 
                exchange : str = "SMART",
                currency : str = "USD") -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = currency
        contract.exchange = exchange

        return contract
    


    @staticmethod
    def USStockWithPrimaryExch(symbol : str, 
                               primaryExchange: str,
                               exchange : str = "SMART",
                               currency : str = "USD") -> Contract:

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
    def EuropeanStock(symbol : str, 
                      primaryExchange: str,
                      exchange : str = "SMART",
                      currency : str = "EUR") -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = exchange
        contract.exchange = currency
        contract.primaryExchange = primaryExchange
        return contract


    @staticmethod
    def etf(symbol: str,
            exchange: str = "SMART",
            currency: str = "USD") -> Contract:
        
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.currency = currency
        contract.exchange = exchange

        return contract
    
    @staticmethod
    def CryptoContract(symbol: str,
                       exchange: str = "PAXOS",
                       currency: str = "USD") -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "CRYPTO"
        contract.currency = currency
        contract.exchange = exchange

        return contract

    
    """
        US Option
        Example:
        symol = "GOOG"
        expiry = "20190504"
        strike = 1120
        right = "C"
    """
    @staticmethod
    def USOptionContract(symbol: str,
                         expiry: str,
                         strike: int,
                         right: str,
                         exchange: str = "SMART",
                         currency: str = "USD",
                         multiplier: str = "100") -> Contract:
        
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


    """ Option contracts require far more information since there are many 
    contracts having the exact same attributes such as symbol, currency, 
    strike, etc. This can be overcome by adding more details such as the 
    trading class"""

    @staticmethod
    def OptionWithTradingClass(symbol: str,
                                expiry: str,
                                exchange: str,
                                strike: int,
                                right: str,
                                tradingClass: str, 
                                currency: str = "USD",
                                multiplier: str = "100") -> Contract:

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


    """ 
    Using the contract's own symbol (localSymbol) can greatly simplify a
    contract description

    Watch out for the spaces within the local symbol!
    Example : "P BMW  20221216 72 M"
    """
    @staticmethod
    def OptionWithLocalSymbol(localSymbol: str,
                              exchange : str = "SMART",
                              currency:str = "USD"
                              ) -> Contract:

        contract = Contract()
        contract.localSymbol = localSymbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency

        return contract





    """ Ambiguous contracts are great to use with reqContractDetails. This way
    you can query the whole option chain for an underlying. Bear in mind that
    there are pacing mechanisms in place which will delay any further responses
    from the TWS to prevent abuse. """

    @staticmethod
    def OptionForQuery(symbol: str,
                       exchange: str = "SMART",
                       currency: str = "USD") -> Contract:

        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = exchange
        contract.currency = currency

        return contract


    @staticmethod
    def OptionComboContract() -> Contract:

        contract = Contract()
        contract.symbol = "DBK"
        contract.secType = "BAG"
        contract.currency = "EUR"
        contract.exchange = "EUREX"

        leg1 = ComboLeg()
        leg1.conId = 577164786 #DBK Jun21'24 2 CALL @EUREX
        leg1.ratio = 1
        leg1.action = "BUY"
        leg1.exchange = "EUREX"

        leg2 = ComboLeg()
        leg2.conId = 577164767 #DBK Dec15'23 2 CALL @EUREX
        leg2.ratio = 1
        leg2.action = "SELL"
        leg2.exchange = "EUREX"

        contract.comboLegs = []
        contract.comboLegs.append(leg1)
        contract.comboLegs.append(leg2)

        return contract



    """ CBOE Volatility Index Future combo contract """

    @staticmethod
    def FutureComboContract() -> Contract:
        #! [bagfutcontract]
        contract = Contract()
        contract.symbol = "VIX"
        contract.secType = "BAG"
        contract.currency = "USD"
        contract.exchange = "CFE"

        leg1 = ComboLeg()
        leg1.conId = 326501438 # VIX FUT 201903
        leg1.ratio = 1
        leg1.action = "BUY"
        leg1.exchange = "CFE"

        leg2 = ComboLeg()
        leg2.conId = 323072528 # VIX FUT 2019049
        leg2.ratio = 1
        leg2.action = "SELL"
        leg2.exchange = "CFE"

        contract.comboLegs = []
        contract.comboLegs.append(leg1)
        contract.comboLegs.append(leg2)
        #! [bagfutcontract]
        return contract
    

    """ 
    It is also possible to define contracts based on their ISIN (IBKR STK sample). 
        secIdType = "ISIN"
        secId = "US45841N1072"
        exchange = "SMART"
        currency = "USD"
        secType = "STK"
    """

    @staticmethod
    def ByISIN(secIdType: str,
               secId: str,
               secType: str,
               exchange: str = "SMART",
               currency: str = "USD") -> Contract:

        contract = Contract()
        contract.secIdType = secIdType
        contract.secId = secId
        contract.exchange = exchange
        contract.currency = currency
        contract.secType = secType
        return contract


    """ Or their conId (EUR.uSD sample).
    Note: passing a contract containing the conId can cause problems if one of 
    the other provided attributes does not match 100% with what is in IB's 
    database. This is particularly important for contracts such as Bonds which 
    may change their description from one day to another.
    If the conId is provided, it is best not to give too much information as
    in the example below. 

        secType = "CASH"
        conId = 12087792
        exchange = "IDEALPRO"
    """

    @staticmethod
    def ByConId(secType: str,
                conId: int,
                exchange: str = "SMART") -> Contract:

        contract = Contract()
        contract.secType = secType
        contract.conId = conId
        contract.exchange = exchange
        
        return contract

    @staticmethod
    def ByFIGI(secId: str,
               exchange: str = "SMART") -> Contract:

        contract = Contract()
        contract.secIdType = "FIGI"
        contract.secId = secId
        contract.exchange = exchange

        return contract
        
    @staticmethod
    def ByIssuerId(isssuerId: str) -> Contract:

        contract = Contract()
        contract.issuerId = isssuerId

        return contract


    @staticmethod
    def NewsFeedForQuery() -> Contract:
        #! [newsfeedforquery]
        contract = Contract()
        contract.secType = "NEWS"
        contract.exchange = "BRFG" #Briefing Trader
        #! [newsfeedforquery]
        return contract


    @staticmethod
    def BTbroadtapeNewsFeed() -> Contract:
        #! [newscontractbt]
        contract = Contract()
        contract.symbol  = "BRF:BRF_ALL"
        contract.secType = "NEWS"
        contract.exchange = "BRF"
        #! [newscontractbt]
        return contract


    @staticmethod
    def BZbroadtapeNewsFeed() -> Contract:
        #! [newscontractbz]
        contract = Contract()
        contract.symbol = "BZ:BZ_ALL"
        contract.secType = "NEWS"
        contract.exchange = "BZ"
        #! [newscontractbz]
        return contract


    @staticmethod
    def FLYbroadtapeNewsFeed() -> Contract:
        #! [newscontractfly]
        contract = Contract()
        contract.symbol  = "FLY:FLY_ALL"
        contract.secType = "NEWS"
        contract.exchange = "FLY"
        #! [newscontractfly]
        return contract



def Test():
    from ibapi.utils import ExerciseStaticMethods
    ExerciseStaticMethods(IBKRContract)


if "__main__" == __name__:
    Test()

