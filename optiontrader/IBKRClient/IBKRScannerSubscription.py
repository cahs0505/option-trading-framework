"""
Copyright (C) 2019 Interactive Brokers LLC. All rights reserved. This code is subject to the terms
 and conditions of the IB API Non-Commercial License or the IB API Commercial License, as applicable.
"""


from ibapi.object_implem import Object 
from ibapi.scanner import ScannerSubscription


class IBKRScannerSubscription(Object):

    @staticmethod
    def HotUSStkByVolume() -> ScannerSubscription:
        #! [hotusvolume]
        #Hot US stocks by volume
        scanSub = ScannerSubscription()
        scanSub.instrument = "STK"
        scanSub.locationCode = "STK.US.MAJOR"
        scanSub.scanCode = "HOT_BY_VOLUME"
        #! [hotusvolume]
        return scanSub

    @staticmethod
    def TopPercentGainersIbis() -> ScannerSubscription:
        #! [toppercentgaineribis]
        # Top % gainers at IBIS
        scanSub = ScannerSubscription()
        scanSub.instrument = "STOCK.EU"
        scanSub.locationCode = "STK.EU.IBIS"
        scanSub.scanCode = "TOP_PERC_GAIN"
        #! [toppercentgaineribis]
        return scanSub

    @staticmethod
    def MostActiveFutEurex() -> ScannerSubscription:
        #! [mostactivefuteurex]
        # Most active futures at EUREX
        scanSub = ScannerSubscription()
        scanSub.instrument = "FUT.EU"
        scanSub.locationCode = "FUT.EU.EUREX"
        scanSub.scanCode = "MOST_ACTIVE"
        #! [mostactivefuteurex]
        return scanSub

    @staticmethod
    def HighOptVolumePCRatioUSIndexes() -> ScannerSubscription:
        #! [highoptvolume]
        # High option volume P/C ratio US indexes
        scanSub = ScannerSubscription()
        scanSub.instrument = "IND.US"
        scanSub.locationCode = "IND.US"
        scanSub.scanCode = "HIGH_OPT_VOLUME_PUT_CALL_RATIO"
        #! [highoptvolume]
        return scanSub

    @staticmethod
    def ComplexOrdersAndTrades() -> ScannerSubscription:
        #! [combolatesttrade]
        # High option volume P/C ratio US indexes
        scanSub = ScannerSubscription()
        scanSub.instrument = "NATCOMB"
        scanSub.locationCode = "NATCOMB.OPT.US"
        scanSub.scanCode = "COMBO_LATEST_TRADE"
        #! [combolatesttrade]
        return scanSub

def Test():
    print(IBKRScannerSubscription.HotUSStkByVolume())
    print(IBKRScannerSubscription.TopPercentGainersIbis())
    print(IBKRScannerSubscription.MostActiveFutSoffex())
    print(IBKRScannerSubscription.HighOptVolumePCRatioUSIndexes())
    
 
if "__main__" == __name__:
    Test()
 
