import pandas as pd
import numpy as np
import random
import vollib.black_scholes_merton.implied_volatility
import vollib.black_scholes_merton.greeks.numerical
import vollib.black_scholes_merton
import py_vollib_vectorized

from numpy.typing import NDArray
from typing import Dict, List, Tuple
from optiontrader.util import get_time_to_expiry
from optiontrader.config import config
from optiontrader.constants import (
    YEARLY_TRADING_DAYS
)

RISK_FREE_INTEREST_RATE = config.RISK_FREE_INTEREST_RATE
SPY_ANNUAL_DIVIDEND_YIELD = config.SPY_ANNUAL_DIVIDEND_YIELD

def log_return(data: pd.DataFrame) -> pd.DataFrame:

    data['log_return'] = np.log(data.close / data.close.shift(1))
    data.dropna(inplace=True)
    
    return data

def volatility_cc(data: pd.DataFrame,
                  window: int) -> pd.Series:
    """
    Close-to-close volatility estimator
    """
    log_return = np.log(data.close / data.close.shift(1))
    v = log_return.rolling(window=window).std() * np.sqrt(YEARLY_TRADING_DAYS)

    return v

def volatility_p(data: pd.DataFrame,
                 window: int = 1) -> pd.Series:
    """
    Parkinson volatility
    """

    _ = (np.log(data.high / data.low) ** 2)
    _ = _.rolling(window=window).sum()
    _ = _ / (4 * np.log(2))
    _ = np.sqrt(_)
    v = _ * np.sqrt(YEARLY_TRADING_DAYS) / np.sqrt(window)

    return v

def volatility_gk(data: pd.DataFrame) -> pd.Series:
    """
    Garman-Klass volatility
    """
    v = np.sqrt(0.5 * np.log(data.high / data.low) ** 2 - (2*np.log(2) -1) * np.log(data.close/data.open)**2) * np.sqrt(YEARLY_TRADING_DAYS)

    return v

def volatility_rs(data: pd.DataFrame) -> pd.Series:
    """
    Rogers-Satchell volatility estimator
    """
    v = (np.log(data.high/data.open) * np.log(data.high/data.close) + np.log(data.low/data.open) * np.log(data.low/data.close)) * np.sqrt(YEARLY_TRADING_DAYS)

    return v

def volatility_rb(data: pd.DataFrame) -> pd.Series:
    """
    A simple average of the parkinson, garman-klass and rogers-satchell
    """
    v = (volatility_p(data) + volatility_gk(data) + volatility_rs(data)) / 3

    return v

def volatility_yz(data: pd.DataFrame,
                  window : int = 2) -> pd.Series:
    """
    Yang-Zhang volatility estimator
    """
    
    data['sigma_rs_squared'] = np.log(data.high/data.open) * np.log(data.high/data.close) + np.log(data.low/data.open) * np.log(data.low/data.close)
    data['sigma_rs_squared'] = data['sigma_rs_squared'].rolling(window=window).mean()

    data['log_overnight'] = np.log(data['open']/data['close'].shift(1))
    data['sigma_overnight'] = data['log_overnight'].rolling(window=window).std()

    data['log_open_to_close'] = np.log(data['close']/data['open'])
    data['sigma_open_to_close'] = data['log_open_to_close'].rolling(window=window).std() 

    k = 0.34 / (1.34 + (window+1)/(window-1))

    data['volatility'] = np.sqrt(data['sigma_overnight']**2 + k * data['sigma_open_to_close']**2 +(1-k)*data['sigma_rs_squared']) * np.sqrt(YEARLY_TRADING_DAYS)
    data.dropna(inplace=True, subset=['volatility'])

    return data['volatility']

def box_cox_transformation(data: pd.Series | NDArray,
                           power: int = 0) -> pd.Series | NDArray:
    """
    Box-Cox transformation
    """
    if(power == 0):
        return np.log(data)
    else:
        return (((data ** power) - 1) / power)
    
def q_like(forcast_data: pd.Series | NDArray,
           test_data: pd.Series | NDArray) -> pd.Series | NDArray:
    """
    Quasi-likelihood
    """
    
    ratio = forcast_data / test_data
    
    return np.mean(ratio - np.log(ratio) - 1)

def get_PnL(leg: Dict,
            curr_price: float) -> float:
    
    if(leg['position'] > 0):
        if(leg['right'] =='c' or leg['right'] == 'call'):
            if(curr_price <= leg['strike']):
                return -leg['position'] * leg['price'] * 100
            else:
                return leg['position'] * (curr_price - leg['strike'] - leg['price']) * 100
        else:
            if(curr_price >= leg['strike']):
                return -leg['position'] * leg['price'] * 100
            else: 
                return leg['position'] * (leg['strike'] - curr_price - leg['price']) * 100
    else:
        if(leg['right'] == 'c' or leg['right'] == 'call'):
            if(curr_price <= leg['strike']):
                return -leg['position'] * leg['price'] * 100
            else:
                return leg['position'] * (curr_price - leg['strike'] - leg['price']) * 100
        else:
            if(curr_price >= leg['strike']):
                return -leg['position'] * leg['price'] * 100
            else:
                return leg['position'] * (leg['strike'] - curr_price - leg['price']) * 100

def get_total_PnL(legs, price) -> float:
    total_pnl = 0
    for i in range(len(legs)):
        total_pnl += get_PnL(legs[i],price)
    return total_pnl


def GBM_monte_carlo(mu:float, 
                    sigma:float, 
                    S0:float, 
                    steps:int, 
                    dt: float = 1/252, 
                    M=10000) -> np.ndarray:
    """
    Simulate Geometric Brownian Motion with Monte Carlo Method, primarily used by BSM
        mu: drift
        sigma: variance
        S0: initial val
        steps: number of steps
        M: number of simulation 
    """    
    np.random.seed(int(random.randrange(1,10000)))
    St1 = np.exp(
        (mu - 0.5 * sigma ** 2 ) * dt
        + sigma * np.random.normal(0, np.sqrt(dt), size=(steps, M))
    )
    result = S0 * np.cumprod(St1, axis=0)
    result = np.insert(result,0,np.full(M,S0), axis=0)

    return result

def BSM_ev_monte_carlo(legs: List,
                       sigma: float, 
                       initial_price: float, 
                       expiry: str, 
                       dt: float = 1/252,
                       steps: int = None,
                       riskfree_rate: float = RISK_FREE_INTEREST_RATE,
                       M:int = 10000) -> float:

    if steps is None:
        years = get_time_to_expiry(expiry)
        total_steps = round(YEARLY_TRADING_DAYS * years)
        if (total_steps == 0):
            total_steps = 1
    else: 
        total_steps = steps


    final_prices = GBM_monte_carlo(
        mu = riskfree_rate,
        sigma = sigma,
        S0 = initial_price,
        steps = total_steps,
        dt = dt,
        M = M
    )[-1]

    freq, bin_edges = np.histogram(final_prices, bins=100)
    returns = (bin_edges[1:] + bin_edges[:-1]) / 2

    for i in range(len(returns)):
        returns[i] = get_total_PnL(legs,returns[i])

    return returns, freq

def BSM_greeks(leg: Dict, 
               volatility: float,
               curr_price: float, 
               expiry: str,
               riskfree_rate: float = RISK_FREE_INTEREST_RATE,
               dividend: float = 0
               ) -> Tuple:

    greeks = (
        py_vollib_vectorized.vectorized_delta(
            flag = leg['right'],
            S = curr_price,
            K = leg['strike'],
            t = get_time_to_expiry(expiry=expiry),
            r = riskfree_rate,
            sigma = volatility,
            q = dividend,
            model='black_scholes_merton',
            return_as= 'numpy'
        )[0],
        py_vollib_vectorized.vectorized_gamma(
            flag = leg['right'],
            S = curr_price,
            K = leg['strike'],
            t = get_time_to_expiry(expiry=expiry),
            r = riskfree_rate,
            sigma = volatility,
            q = dividend,
            model='black_scholes_merton',
            return_as= 'numpy'                  
        )[0],
        py_vollib_vectorized.vectorized_theta(
            flag = leg['right'],
            S = curr_price,
            K = leg['strike'],
            t = get_time_to_expiry(expiry=expiry),
            r = riskfree_rate,
            sigma = volatility,
            q = dividend,
            model='black_scholes_merton',
            return_as= 'numpy'    
        )[0],
        py_vollib_vectorized.vectorized_vega(
            flag = leg['right'],
            S = curr_price,
            K = leg['strike'],
            t = get_time_to_expiry(expiry=expiry),
            r = riskfree_rate,
            sigma = volatility,
            q = dividend,
            model='black_scholes_merton',
            return_as= 'numpy'     
        )[0]
    )

    return tuple(x * leg['position'] for x in greeks)