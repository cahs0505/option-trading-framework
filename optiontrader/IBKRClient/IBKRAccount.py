from typing import Any, List
from dataclasses import dataclass
from decimal import Decimal

from IBKRPortfolio import IBKRPortfolio
from IBKROrderStatus import IBKROrderStatus
from ibapi.contract import Contract

ACCOUNT_TAG_MAP= {
    "AccountCode" : ("account_code", str) ,
    "AccountReady" : ("account_ready", bool),
    "AccountType" : ("account_type", str) ,
    "AccuredCash": ("accrued_cash", float) ,
    "AvailableFunds": ("available_funds", float),
    "BuyingPower": ("buying_power", float) ,
    "CashBalance" : ("cash_balance", float),
    "Cushion Value" : ("cushion_value", float),
    "EquityWithLoanValue": ("equity_with_loan_value", float),
    "ExcessLiquidity": ("excess_liquidity", float),
    "FullAvailableFunds" : ("full_available_funds", float),
    "FullExcessLiquidity": ("full_excess_liquidity", float),
    "FullInitMarginReq": ("full_init_margin_req", float),
    "FullMaintMarginReq" : ("full_maint_margin_req", float),
    "FutureOptionValue" : ("future_option_value", float),
    "GrossPositionValue" : ("gross_position_value", float),
    "InitMarginReq" : ("init_margin_req", float),
    "IssuerOptionValue" : ("issuer_option_value", float),
    "MaintMarginReq" : ("maint_margin_req", float),
    "NetLiquidation" : ("net_liquidation", float),
    "OptionMarketValue" : ("option_market_value", float),
    "RealizedPnL" : ("realized_PnL", float),
    "TotalCashBalance" : ("total_cash_balance", float),
    "TotalCashValue" : ("total_cash_value", float),
    "UnrealizedPnL" : ("unrealized_PnL", float)
}


class IBKRAccount:

    account_name: str
    currency: str

    account_code: str
    account_ready: bool             ## important!!!
    account_type: str
    accrued_cash: float
    available_funds: float
    buying_power: float
    cash_balance: float
    cushion_value: float
    equity_with_loan_value: float
    excess_liquidity: float
    full_available_funds: float
    full_excess_liquidity: float
    full_init_margin_req: float
    full_maint_margin_req: float
    future_option_value: float
    gross_position_value: float
    init_margin_req: float
    issuer_option_value: float
    maint_margin_req: float
    net_liquidation: float
    option_market_value: float
    realized_PnL: float
    total_cash_balance: float
    total_cash_value: float
    unrealized_PnL: float

    portfolio : dict
    orders: dict

  
    def __init__(self,
                 currency: str = "USD"):
        
        self.currency = currency
        self.account_ready = True
        self.portfolio = {}
        self.orders = {}

    def set_value(self, tag: str, value: Any) -> None:

        if (tag != "AccountReady" and self.account_ready) or tag == "AccountReady":

            if tag in ACCOUNT_TAG_MAP:

                _map = ACCOUNT_TAG_MAP[tag]
                key = _map[0]
                data_type = _map[1]

                if data_type == str:
                    pass
                elif data_type == int:
                    value = int(value)
                    
                elif data_type == float:
                    value = float(value)
                    
                elif data_type == bool:
                    value = value.lower()
                    if value in ["yes","true"]:
                        value = True
                    else:
                        value = False
                setattr(self, key, value)

    def portfolio_exist(self,
                        conId : int) -> bool:
        
        return conId in self.portfolio

    def add_portfolio(self,
                        contract: Contract, 
                        position: Decimal,
                        marketPrice: float, 
                        marketValue: float,
                        averageCost: float, 
                        unrealizedPNL: float,
                        realizedPNL: float, 
                        accountName: str) -> IBKRPortfolio:
        
        if accountName == self.account_name:

            conId = contract.conId
            portfolio = IBKRPortfolio(contract=contract,
                                    position=position,
                                    market_price=marketPrice,
                                    market_value=marketValue,
                                    average_cost=averageCost,
                                    unrealized_PnL=unrealizedPNL,
                                    realized_PnL=realizedPNL
                                    )

            self.portfolio[conId] = portfolio
        
            return self.portfolio[conId]
        

    def update_portfolio(self,                        
                        contract: Contract, 
                        position: Decimal,
                        marketPrice: float, 
                        marketValue: float,
                        averageCost: float, 
                        unrealizedPNL: float,
                        realizedPNL: float, 
                        accountName: str) -> IBKRPortfolio :
        
        if accountName == self.account_name:

            conId = contract.conId
            self.portfolio[conId].set_value(
                contract=contract,
                position=position,
                market_price=marketPrice,
                market_value=marketValue,
                average_cost=averageCost,
                unrealized_PnL=unrealizedPNL,
                realized_PnL=realizedPNL
            )

            return self.portfolio[conId]

    def get_portfolio(self,
                      conId : int) -> IBKRPortfolio:
        
        return self.portfolio[conId]
    


    
    def print_account_summary(self) -> None:
        print(f"Account: {self.account_name}({self.account_ready}) ")
        print(f"Net Liquidation: {self.net_liquidation}")
        print(f"Available Funds:{self.available_funds}")
        print(f"Gross Position: {self.gross_position_value}")
        print(f"Buying Power: {self.buying_power}")
        print(f"Initial Margin: {self.init_margin_req}")
        print(f"Maintenance Margin: {self.maint_margin_req}")

    def print_portfolio(self) -> None:
        for conId, port in self.portfolio.items():
            print(port)


    """
    Order Status
    """
    def order_status_exist(self,
                           perm_id: int):
        
        return perm_id in self.orders
    

    def add_order_status(self,
                         **kwargs) -> None:

        perm_id = kwargs["perm_id"]
        order_status = IBKROrderStatus(**kwargs)
        print(order_status)
        self.orders[perm_id] = order_status

    def update_order_status(self,
                            **kwargs) -> None:
        
        perm_id = kwargs["perm_id"]
        self.orders[perm_id].set_value(**kwargs)
    
    def print_all_orders(self):
        print(self.orders)
        for k,v in self.orders.items():
            print(v)


        
        
        



if __name__ == "__main__":
    acc = IBKRAccount()
    acc.add_order_status(perm_id=1234,
                         order_id=0,
                         action = "LMT")
    print(acc.orders[1234])
    acc.update_order_status(perm_id=1234,
                            contract="MSFT")
    print(acc.orders[1234])
    
    
    
    
  

    
    