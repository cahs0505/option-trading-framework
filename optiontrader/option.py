import json
import numpy as np
import pandas as pd

import vollib.black_scholes_merton.implied_volatility
import py_vollib_vectorized
from py_vollib_vectorized.api import get_all_greeks
from decimal import Decimal
from typing import Dict, Tuple, List

from optiontrader.constants import SecurityType, OptionRight, OptionStyle
from optiontrader.util import get_time_to_expiry
from optiontrader.config import config
from pysvi import get_model, calibrate_slice, calculate_implied_forward

RISK_FREE_INTEREST_RATE = config.RISK_FREE_INTEREST_RATE
SPY_ANNUAL_DIVIDEND_YIELD = config.SPY_ANNUAL_DIVIDEND_YIELD

class OptionData:
    """
    Dataclass for one option contract, contain bid-ask ticks, last price, greeks
    """
    underlying_security_type: SecurityType
    underlying_quantity: int
    style: OptionStyle

    symbol: str
    underlying_symbol: str
    right: OptionRight
    strike: Decimal
    expiry: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    open_interest: int
   
    #Analytics: Greeks, IV, Gamma Exposure(GEX), etc. 
    #All computed based on mid price
    moneyness: np.float64
    delta: np.float64
    gamma: np.float64
    theta: np.float64
    vega: np.float64
    iv: np.float64
    gex: np.float64

    def __init__(
            self, 
            symbol : str, 
            underlying_symbol: str,
            right: OptionRight, 
            strike: Decimal,
            expiry: str,
            style: OptionStyle = OptionStyle.AMERICAN,
            underlying_security_type: SecurityType = SecurityType.ETF,
            underlying_quantity: int = 100
    ):
        self.underlying_security_type = underlying_security_type
        self.style = style
        self.underlying_quantity = underlying_quantity

        self.symbol = symbol
        self.underlying_symbol = underlying_symbol
        self.right = right
        self.strike = strike
        self.expiry = expiry

        self.bid = None
        self.ask = None
        self.last = None
        self.delta = None
        self.gamma = None
        self.theta = None
        self.vega = None
        self.rho = None
        self.iv = None
        self.gex = 0

    def __repr__(self):
        return f'{self.symbol}({np.round(self.moneyness,decimals=3)})- BID: {self.bid} - ASK: {self.ask} - LAST: {self.last} - IV: {np.round(self.iv, decimals=4)} - DELTA: {np.round(self.delta, decimals=4)} - GAMMA: {np.round(self.gamma, decimals=4)} - THETA: {np.round(self.theta, decimals=4)} - VEGA: {np.round(self.vega, decimals=4)}'
    
    def __str__(self):
        return f'{self.symbol}({np.round(self.moneyness,decimals=3)}) - BID: {self.bid} - ASK: {self.ask} - LAST: {self.last} - IV: {np.round(self.iv, decimals=4)} - DELTA: {np.round(self.delta, decimals=4)} - GAMMA: {np.round(self.gamma, decimals=4)} - THETA: {np.round(self.theta, decimals=4)} - VEGA: {np.round(self.vega, decimals=4)}'
    
    def get_data_tuple(self) -> Tuple:
        return (
                'c' if self.right == OptionRight.CALL else 'p',
                self.strike, 
                (self.bid + self.ask)/2
                )
    
    def update_tick(
            self,
            bid,
            ask,
            last,
            open_interest
    ):
        self.bid = bid if bid != -1 else None
        self.ask = ask if ask != -1 else None
        self.last = last if last != -1 else None
        self.open_interest = open_interest

    def get_mid_price(self):
        if self.bid == 0 and self.ask == 0:
            return self.last
        return (self.bid + self.ask)/2 
    
    def get_greeks(self):
        greeks = {
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho
        }
        return greeks

    def get_moneyness(self, spot):
        if self.right == OptionRight.CALL:
            if self.strike < spot:
                return 'i'
            else:
                return 'o'
        else:
            if self.strike > spot:
                return 'i'
            else:
                return 'o'
    
Strike = str
Right = str
class OptionChainData:
    """
    Contains all option data for one symbol-expiry pair
    """
    underlying_symbol : str
    expiry: str
    maturity: float 
    dte: int
    options:  Dict[Tuple[str, str], OptionData]
    svi_params : Tuple = None
    
    def __init__(self,
                 underlying_symbol: str,
                 expiry: str):
        self.underlying_symbol = underlying_symbol
        self.expiry = expiry
        self.maturity = get_time_to_expiry(expiry)
        self.dte = get_time_to_expiry(expiry,True)
        self.options = {}
    
    def __repr__(self):
        return ','.join(str(v) for k,v in self.options.items())

    def add_option(self, strike: str, right: str, option_data: OptionData):
        key = (strike, right)
        self.options[key] = option_data
    
    def get_dte(self, as_day: bool = False):
        return get_time_to_expiry(self.expiry, as_day=as_day)
    
    def get_chain_data(self):
        data  = []
        for key, option_data in self.options.items():
            data.append(option_data.get_data_tuple())
        data = np.array(data)
        data = np.transpose(data)
        return data

    def compute_moneyness(self, spot: Decimal) -> None:
        """
        Compute the log-moneyness for each contract
        """
        t = self.maturity

        #Note that We should use forward price instead of spot price here
        F = spot * np.exp((RISK_FREE_INTEREST_RATE - SPY_ANNUAL_DIVIDEND_YIELD) * t)
        
        for k,v in self.options.items():
            v.moneyness = np.log(v.strike / F)

    def compute_iv(self, spot: Decimal):
        """
        Compute the Black-Scholes implied volatility for each contract.
        """
        chain_data = self.get_chain_data()
        t = self.maturity
    
        iv = py_vollib_vectorized.implied_volatility.vectorized_implied_volatility(
            price = chain_data[2],
            S = spot, 
            K = chain_data[1], 
            t = t,
            r = RISK_FREE_INTEREST_RATE, 
            flag = chain_data[0], 
            q = SPY_ANNUAL_DIVIDEND_YIELD,
            model='black_scholes_merton',
            return_as='numpy',
            on_error='ignore')

        chain_data_transpose = np.transpose(chain_data[:2])
        chain_data = list(map(tuple, chain_data_transpose))
        for i in range(len(chain_data)):
            option_key_raw = chain_data[i]
            key = (
                str(option_key_raw[1]),
                str(option_key_raw[0])
            )
            self.options[key].iv = iv[i]

    def get_moneyness_iv_data(self):
        data = []
        T = self.maturity
        for k,v in self.options.items():
            #Only OTM options are used
            if (v.right == OptionRight.CALL and v.moneyness>0) or (v.right == OptionRight.PUT and v.moneyness<0):
                curr = (
                    v.moneyness,
                    v.iv
                )
                data.append(curr)
        data.sort()
        return np.array(data)
    
    def get_atm_iv(self) -> Tuple[np.float64, np.float64]:
        put_atm_moneyness = 1e9
        put_iv = 0
        call_atm_moneyness = 1e9
        call_iv = 0
        for k,v in self.options.items():
            if v.right == OptionRight.CALL and v.moneyness > 0:
                if v.moneyness < call_atm_moneyness:
                    call_atm_moneyness = v.moneyness
                    call_iv = v.iv
            elif v.right == OptionRight.PUT and v.moneyness > 0:
                if v.moneyness < put_atm_moneyness:
                    put_atm_moneyness = v.moneyness
                    put_iv = v.iv
        
        return (call_iv, put_iv)

    def get_full_iv(self) -> Dict[str, List]:
        call = []
        put = []
        for k,v in self.options.items():
            curr = (v.strike,v.iv)
            if v.right == OptionRight.CALL:
                call.append(curr)
            else:
                put.append(curr)
        return {
            'call': call,
            'put': put
        }

    def compute_greeks(self, spot: Decimal, sigma: np.float64) -> None:
        chain_data = self.get_chain_data()
        t = self.maturity
        greeks = get_all_greeks(
            flag = chain_data[0],
            S = spot,
            K = chain_data[1],
            t = t,
            r = RISK_FREE_INTEREST_RATE,
            sigma = sigma,
            q = SPY_ANNUAL_DIVIDEND_YIELD,
            model = 'black_scholes_merton',
        )
        chain_data_transpose = np.transpose(chain_data[:2])
        chain_data = list(map(tuple, chain_data_transpose))
        for i in range(len(chain_data)):
            option_key_raw = chain_data[i]
            key = (
                str(option_key_raw[1]),
                str(option_key_raw[0])
            )
            self.options[key].delta = greeks['delta'][i]
            self.options[key].gamma = greeks['gamma'][i]
            self.options[key].theta = greeks['theta'][i]
            self.options[key].vega = greeks['vega'][i]
            self.options[key].rho = greeks['rho'][i]
            
        return greeks
    
    def compute_gex(self, spot: Decimal) -> None:
        for k,op in self.options.items():
            if op.open_interest == None:
                continue
            op.gex = op.gamma * op.open_interest * 100 * spot * (-1 if op.right == OptionRight.PUT else 1)
        
    def get_net_gex(self) -> np.float64:
        net_gex = 0
        for k,op in self.options.items():
            net_gex += op.gex
        return net_gex

    def _prepare_data_for_svi_fit(self, spot):
        call_put = {}
        right = []
        strike = []
        forward = []
        iv = []
        maturity = self.maturity

        for k,v in self.options.items():
            curr_right = v.right
            curr_strike = v.strike
            curr_price = v.get_mid_price()
            if curr_strike not in call_put:
                call_put[curr_strike] = {}
            if (curr_right == OptionRight.CALL):
                call_put[curr_strike]['c'] = curr_price 
            else:
                call_put[curr_strike]['p'] = curr_price

        for k,v in self.options.items():
            moneyness = v.get_moneyness(spot)
            curr_right = v.right
            curr_strike = v.strike
            curr_price = v.get_mid_price() 
       
            if moneyness == 'o':
                curr_cp = call_put[curr_strike]
                if 'c' in curr_cp and 'p' in curr_cp:
                    right.append(curr_right)
                    strike.append(curr_strike)
                    iv.append(v.iv)
    
                    _spot = pd.Series(spot)
                    _tte = pd.Series(maturity)
                    _strike = pd.Series(curr_strike)
        
                    curr_forward = calculate_implied_forward(
                        spot = _spot,
                        tte = _tte,
                        r = RISK_FREE_INTEREST_RATE,
                        strike = _strike,
                        call_mid = pd.Series(curr_cp['c']),
                        put_mid = pd.Series(curr_cp['p']) 
                    )
                    forward.append(curr_forward[0])     

        df =pd.DataFrame({'strike': strike, 'iv': iv, 'maturity' : maturity, 'implied_forward': forward})
        df['log_moneyness'] = np.log(df['strike']/df['implied_forward'])
        df = df.sort_values(by='strike')

        return df

    def svi_fit(self, spot):
        df = self._prepare_data_for_svi_fit(spot)
        model = get_model('svi')
        params = calibrate_slice(df, model)
        a,b,rho,m,sigma,forward = params.values()
        self.svi_params = (a,b,rho,m,sigma,forward)
        return self.svi_params


    def svi_fit_fi(self):
        """
        Stocastic Volatility Inspired (SVI) model fitting, using the fast iterative algorithm
        For detail, see https://arxiv.org/abs/2301.07830
        """
        data = self.get_moneyness_iv_data()
        N = len(data)
        T = self.maturity

        data[:,1] = (data[:,1]**2) * T
        (x_min,v_min) = min(data,key = lambda x : x[1])

        data = np.transpose(data)
        X = data[0].reshape(N,1)
        V = data[1].reshape(N,1)
        sigma = v_min
        m = x_min
        n = 0
        M = 50
        error_delta = 1e-3
        X_1 = np.ones((N, 1))
        X_2 = X - np.full((N,1), m)
        X_3 = np.sqrt((X - np.full((N,1), m))**2 + (np.full((N,1), sigma))**2)
        Y = np.column_stack((X_1,X_2,X_3))
        beta = np.linalg.inv(np.transpose(Y) @ Y) @ np.transpose(Y) @ V
        L = np.sqrt(np.transpose(V - (Y @ beta)) @ (V - (Y @ beta)))
        a = beta[0]
        b = beta[2]
        rho = beta[1]/beta[2]

        while L > error_delta or n <= M:
            n += 1
            m = x_min + ((rho * (v_min-a))/(b * (1 - rho**2)))
            sigma = (v_min - a) / (b * np.sqrt(1 - rho**2)) 
            X_1 = np.ones((N, 1))
            X_2 = X - np.full((N,1), m)
            X_3 = np.sqrt((X - np.full((N,1), m))**2 + (np.full((N,1), sigma))**2)
            Y = np.column_stack((X_1,X_2,X_3))
            beta = np.linalg.inv(np.transpose(Y) @ Y) @ np.transpose(Y) @ V
            L = np.sqrt(np.transpose(V - (Y @ beta)) @ (V - (Y @ beta)))
            a = beta[0]
            b = beta[2]
            rho = beta[1]/beta[2]

        return (a,b,rho,m,sigma)
    
    def svi(
        self,
        x: np.ndarray,
        a: np.float64,
        b: np.float64,
        rho: np.float64,
        m: np.float64,
        sigma: np.float64
    ):
        return a + b*(rho*(x-m)+np.sqrt((x-m)**2 + sigma**2))

    def construct_iron_condor(self,
                              ic_short_strike_delta_target: float = 0.25,
                              ic_long_strike_delta_target: float = 0.1):

        short_call = None
        short_put = None
        _short_call_delta_diff = 1
        _short_put_delta_diff = 1

        long_call = None
        long_put = None
        _long_call_delta_diff = 1
        _long_put_delta_diff = 1
        
        for k,op in self.options.items():
            if op.right == OptionRight.CALL:
                if abs(op.delta - ic_short_strike_delta_target) < _short_call_delta_diff:
                    _short_call_delta_diff = abs(op.delta - ic_short_strike_delta_target)
                    short_call = k

                if abs(op.delta - ic_long_strike_delta_target) < _long_call_delta_diff:
                    _long_call_delta_diff = abs(op.delta - ic_long_strike_delta_target)
                    long_call = k
            else:
                if abs(abs(op.delta) - ic_short_strike_delta_target) < _short_put_delta_diff:
                    _short_put_delta_diff = abs(abs(op.delta) - ic_short_strike_delta_target)
                    short_put = k

                if abs(abs(op.delta) - ic_long_strike_delta_target) < _long_put_delta_diff:
                    _long_put_delta_diff = abs(abs(op.delta) - ic_long_strike_delta_target)
                    long_put = k


        spread = OptionSpread()
        spread.add_long_leg(self.options[long_call])
        spread.add_long_leg(self.options[long_put])
        spread.add_short_leg(self.options[short_call])
        spread.add_short_leg(self.options[short_put])

        return spread    

class OptionSpread():
    """
    Dataclass for one option spread
    """
    short_legs: List[OptionData]
    long_legs: List[OptionData]

    def __init__(self):
        self.short_legs = []
        self.long_legs = []

    def __str__(self):
        return self.get_spread_data_json()

    def __repr__(self):
        return self.get_spread_data_json()

    def __dict__(self):
        return self.get_spread_data_json()

    def add_long_leg(self, leg: OptionData):
        self.long_legs.append(leg)

    def add_short_leg(self, leg: OptionData):
        self.short_legs.append(leg)

    def get_spread_data(self):
        data = []
        for leg in self.short_legs:
            price = leg.get_mid_price() 
            if price == 0 :
                price = leg.last
            curr = {
                'position': -1,
                'right': 'c' if leg.right == OptionRight.CALL else 'p',
                'strike': leg.strike,
                'price': price
            }
            data.append(curr)
        for leg in self.long_legs:
            price = leg.get_mid_price() 
            if price == 0 :
                price = leg.last
            curr = {
                'position': 1,
                'right': 'c' if leg.right == OptionRight.CALL else 'p',
                'strike': leg.strike,
                'price': price
            }
            data.append(curr)
        return data
    
    def get_spread_data_json(self):
        return json.dumps(self.get_spread_data())

    def get_premium(self) -> float:
        premium = 0
        for leg in self.short_legs:
            price = leg.get_mid_price() 
            if price == 0 :
                price = leg.last
            
            premium += price
        for leg in self.long_legs:
            price = leg.get_mid_price() 
            if price == 0 :
                price = leg.last
            premium -= price
        return premium * 100
    
    def get_greeks(self) -> Dict:
        greeks = {
            'delta': 0,
            'gamma': 0,
            'theta': 0,
            'vega': 0,
            'rho': 0
        }
        for leg in self.short_legs:
            leg_greek = leg.get_greeks()
            greeks['delta'] -= leg_greek['delta']
            greeks['gamma'] -= leg_greek['gamma']
            greeks['theta'] -= leg_greek['theta']
            greeks['vega'] -= leg_greek['vega']
            greeks['rho'] -= leg_greek['rho']

        for leg in self.long_legs:
            leg_greek = leg.get_greeks()
            greeks['delta'] += leg_greek['delta']
            greeks['gamma'] += leg_greek['gamma']
            greeks['theta'] += leg_greek['theta']
            greeks['vega'] += leg_greek['vega']
            greeks['rho'] += leg_greek['rho']

        return greeks