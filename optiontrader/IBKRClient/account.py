import json
import numpy as np
import datetime

from typing import Any, Dict, Set, Tuple, List
from decimal import Decimal

from py_vollib_vectorized.api import get_all_greeks
from optiontrader.IBKRClient.position import IBKRPosition
from optiontrader.util import get_time_to_expiry
from optiontrader.exceptions import ResourceNotAvailableException
from optiontrader.config import config

RISK_FREE_INTEREST_RATE = config.RISK_FREE_INTEREST_RATE
SPY_ANNUAL_DIVIDEND_YIELD = config.SPY_ANNUAL_DIVIDEND_YIELD

ACCOUNT_TAG_MAP= {
    'AccountCode' : ('account_code', str) ,
    'AccountReady' : ('account_ready', bool),
    'AccountType' : ('account_type', str) ,
    'AccuredCash': ('accrued_cash', float) ,
    'AvailableFunds': ('available_funds', float),
    'BuyingPower': ('buying_power', float) ,
    'CashBalance' : ('cash_balance', float),
    'Cushion Value' : ('cushion_value', float),
    'EquityWithLoanValue': ('equity_with_loan_value', float),
    'ExcessLiquidity': ('excess_liquidity', float),
    'FullAvailableFunds' : ('full_available_funds', float),
    'FullExcessLiquidity': ('full_excess_liquidity', float),
    'FullInitMarginReq': ('full_init_margin_req', float),
    'FullMaintMarginReq' : ('full_maint_margin_req', float),
    'FutureOptionValue' : ('future_option_value', float),
    'GrossPositionValue' : ('gross_position_value', float),
    'InitMarginReq' : ('init_margin_req', float),
    'IssuerOptionValue' : ('issuer_option_value', float),
    'MaintMarginReq' : ('maint_margin_req', float),
    'NetLiquidation' : ('net_liquidation', float),
    'OptionMarketValue' : ('option_market_value', float),
    'RealizedPnL' : ('realized_PnL', float),
    'TotalCashBalance' : ('total_cash_balance', float),
    'TotalCashValue' : ('total_cash_value', float),
    'UnrealizedPnL' : ('unrealized_PnL', float)
}

class IBAccount:
    """
    Class for Interactive Broker Account
    """
    account_name: str = None
    account_ready: bool = False
    account_time: str = None
    account_code: str = None
    account_type: str = None
    accrued_cash: float  = None
    available_funds: float = None
    buying_power: float = None
    cash_balance: float = None
    currency: str ='USD'
    cushion_value: float = None
    daily_PnL: float = None
    equity_with_loan_value: float = None
    excess_liquidity: float = None
    full_available_funds: float = None
    full_excess_liquidity: float = None
    full_init_margin_req: float = None
    full_maint_margin_req: float = None
    future_option_value: float = None
    gross_position_value: float = None
    init_margin_req: float = None
    issuer_option_value: float = None
    maint_margin_req: float = None
    net_liquidation: float = None
    option_market_value: float = None
    realized_PnL: float = None
    total_cash_balance: float = None
    total_cash_value: float = None
    unrealized_PnL: float = None

    portfolio : Dict[str, IBKRPosition] = {}
    orders: Dict = {}

    def __init__(self, currency: str = 'USD'): 
        self.currency = currency
        self.account_ready = True
        self.portfolio = {}
        self.orders = {}

    def set_value(self, tag: str, value: Any) -> None:
        if (tag != 'AccountReady' and self.account_ready) or tag == 'AccountReady':
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
                    if value in ['yes','true']:
                        value = True
                    else:
                        value = False
                setattr(self, key, value)
                
    def position_exist(self, conId : int) -> bool:
        return conId in self.portfolio

    def add_position(self, account_name: str, data: Dict) -> IBKRPosition:
        if account_name == self.account_name:

            conId = data['contract'].conId
            position = IBKRPosition(data)

            self.portfolio[conId] = position
        
            return self.portfolio[conId]
        
    def update_position(self, account_name: str, conId: int, data: Dict) -> IBKRPosition :
        if account_name == self.account_name:
            
            self.portfolio[conId].set_value(data)

            return self.portfolio[conId]
        
    def get_net_greeks(self) -> Tuple:
        delta = 0
        gamma = 0
        theta = 0
        vega = 0
        rho = 0
        for k,pos in self.portfolio.items():
            if pos.contract.secType == 'OPT':
                if pos.delta is None or pos.gamma is None or pos.theta is None or pos.vega is None or pos.rho is None:
                    raise ResourceNotAvailableException('Position greeks not available')
                delta += pos.delta
                gamma += pos.gamma
                theta += pos.theta
                vega += pos.vega
                rho += pos.rho
            else:
                delta += float(pos.position)

        return (delta,gamma,theta,vega,rho)

    def get_option_expiries(self) -> Set[str]:
        exp = set()
        for k,v in self.portfolio.items():
            if v.contract.secType == 'OPT':
                exp.add(v.contract.lastTradeDateOrContractMonth)
        return exp
    
    def _get_option_exp_right_strike(self) -> List[Tuple]:
        data = set()
        for k,position in self.portfolio.items():
            if position.contract.secType == 'OPT':
                curr = (position.contract.lastTradeDateOrContractMonth,
                        position.contract.right.lower(),
                        position.contract.strike)
                
                data.add(curr)
        return list(data)

    def compute_option_position_greeks(self, spot: Decimal, sigmas: Dict[str,float]) -> None:
        #Prepare data for vectorized computatiom
        dte_list = []
        right_list = []
        strike_list = []
        sigma_list = []
 
        exp_right_strike = self._get_option_exp_right_strike()

        for contract in exp_right_strike:
            exp,right,strike = contract
            sigma = sigmas[exp]
            dte_list.append(get_time_to_expiry(exp))
            right_list.append(right)
            strike_list.append(strike)
            sigma_list.append(sigma)

        dte_list = np.array(dte_list)
        right_list = np.array(right_list)
        strike_list = np.array(strike_list)
        sigma_list = np.array(sigma_list)
        N = len(dte_list)

        #Compute greeks
        greeks = get_all_greeks(
            flag = right_list,
            S = spot,
            K = strike_list,
            t = dte_list,
            r = RISK_FREE_INTEREST_RATE,
            sigma = sigma_list,
            q = SPY_ANNUAL_DIVIDEND_YIELD,
            model = 'black_scholes_merton',
            return_as = 'dict'
        )

        greeks_data: Dict[Tuple,Tuple] = {}
        for i in range(N):
            key = exp_right_strike[i]
            curr_greeks = (
                greeks['delta'][i],
                greeks['gamma'][i],
                greeks['theta'][i],
                greeks['vega'][i],
                greeks['rho'][i]
            )
            greeks_data[key] = curr_greeks

        #Boardcast back to self.portfolio
        for k,pos in self.portfolio.items():
            if pos.contract.secType == 'OPT':
                curr_key = (pos.contract.lastTradeDateOrContractMonth,
                            pos.contract.right.lower(),
                            pos.contract.strike)
                if curr_key in greeks_data:
                    curr_greeks = greeks_data[curr_key]
                    pos.delta = float(pos.position) * curr_greeks[0] * 100
                    pos.gamma = float(pos.position) * curr_greeks[1] * 100
                    pos.theta = float(pos.position) * curr_greeks[2] * 100
                    pos.vega = float(pos.position) * curr_greeks[3] * 100
                    pos.rho = float(pos.position) * curr_greeks[4] * 100
 
                    
    def get_portfolio(self) -> Dict:
        return {k:v for k,v in self.portfolio.items() if v.position != 0}
    
    def get_portfolio_json(self) -> str:
        data = {}
        for conId, item in self.portfolio.items():
            
            if item.contract.secType == 'STK':
                data[conId] = {
                    'security_type': item.contract.secType,
                    'symbol' : item.contract.symbol,
                    'position' : str(item.position),
                    'market_price': item.market_price,
                    'market_value': item.market_value,
                    'average_cost': item.average_cost if item.position > 0 else item.average_cost *-1,
                    'unrealized_PnL': item.unrealized_PnL,
                    'realized_PnL': item.realized_PnL
                }

            elif item.contract.secType == 'OPT':
                expiry = datetime.datetime.strptime(item.contract.lastTradeDateOrContractMonth,'%Y%m%d')
                expiry = datetime.datetime.strftime(expiry,'%Y-%m-%d')
                data[conId] = {
                    'security_type': item.contract.secType,
                    'symbol' : item.contract.localSymbol,
                    'underlying': item.contract.symbol,
                    'expiry': expiry,
                    'dte': get_time_to_expiry(expiry,True),
                    'right': item.contract.right,
                    'strike': item.contract.strike,
                    'position' : str(item.position),
                    'market_price': item.market_price,
                    'market_value': item.market_value,
                    'average_cost': item.average_cost if item.position > 0 else item.average_cost *-1,
                    'unrealized_PnL': item.unrealized_PnL,
                    'realized_PnL': item.realized_PnL,
                    'implied_volatility': item.implied_volatility if hasattr(item,'implied_volatility') else '',
                    'delta': item.delta if hasattr(item,'delta') else '',
                    'gamma': item.gamma if hasattr(item,'gamma') else '',
                    'vega': item.vega if hasattr(item,'vega') else '',
                    'theta': item.theta if hasattr(item,'theta') else '',
                    'rho': item.rho if hasattr(item,'theta') else '',
                }
        return json.dumps(data)

    def update_account_summary(self, unrealizedPNL: float, realizedPNL: float, dailyPnL: float) -> None:
        self.unrealized_PnL = unrealizedPNL
        self.realized_PnL = realizedPNL
        self.daily_PnL = dailyPnL

    def get_account_summary(self) -> Dict:
        delta, gamma, theta, vega, rho = self.get_net_greeks()
        data = {
            'account_name' : self.account_name,
            'net_liquidation' : self.net_liquidation,
            'available_funds' : self.available_funds,
            'gross_position' : self.gross_position_value,
            'buying_power' : self.buying_power,
            'initial_margin' : self.init_margin_req,
            'maintenance_margin' : self.maint_margin_req,
            'unrealized_PnL' : self.unrealized_PnL,
            'realized_PnL': self.realized_PnL,
            'daily_PnL' : 0 if self.daily_PnL is None else self.daily_PnL,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }

        return data
    
    def get_account_summary_json(self) -> str:
        return json.dumps(self.get_account_summary())