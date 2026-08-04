import numpy as np
import json
import pandas_market_calendars as mcal

from typing import Dict, List
from datetime import datetime, timedelta, date, UTC
from threading import Event

from optiontrader.option import OptionChainData, OptionData, OptionSpread
from optiontrader.logger import logger
from optiontrader.config import config
from optiontrader.constants import OptionRight
from optiontrader.datasource import yahoofinance
from optiontrader.util import get_time_to_expiry
from optiontrader.forecast import ForecastEngine
from optiontrader.mathtools import BSM_ev_monte_carlo, volatility_p
from optiontrader.constants import OptionSpread
from optiontrader.database import Database

IC_SHORT_STRIKE_DELTA_TARGET = config.IC_SHORT_STRIKE_DELTA_TARGET 
IC_LONG_STRIKE_DELTA_TARGET  = config.IC_LONG_STRIKE_DELTA_TARGET 
VRP_THRESHOLD = config.VRP_THRESHOLD
 
class Screener:
    """
    Screen and suggest profitable option spreads using our volatility forecast
    """
    shut_down_flag = Event
    
    symbol: str = 'SPY'
    expiries: List[str]

    option_chains: Dict[str,OptionChainData]
    profitable_spreads: List[Dict]
    
    def __init__(self,
                 db: Database,
                 forecast_engine: ForecastEngine):

        self.db = db
        self.forecast_engine = forecast_engine
        self.expiries = yahoofinance.get_option_expiry(self.symbol)[:16]
        self.option_chains = {}
        self.contract_detail_requests = {}
        self.ticks_requests = {}
        self.profitable_spreads = []
        self.exchange = mcal.get_calendar('NYSE')
        start = (date.today() - timedelta(days=7)).strftime('%Y-%m-%d')
        end = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        self.exchange_schedule = self.exchange.schedule(start_date=start, end_date=end)

        self.shut_down_flag = Event()

    # def init_all_chains(self):
    #     for exp in self.expiries:
    #         self.add_option_chain(exp)
            
            
    def run(self):
        """
        Main loop
        """
        # self.init_all_chains()

        if self.exchange.is_open_now(self.exchange_schedule):
            _ = []
            for exp in self.expiries:
                self.add_option_chain(exp)
                _.append((self.symbol,exp))
            data = yahoofinance.get_option_price_multiple(batch=_,range=20)
            self._process_yf_data(data)
        else:
            for exp in self.expiries:
                data = self.db.get_option_chain_latest_snapshot(symbol = 'SPY',
                                                                expiry = exp,
                                                                columns = [
                                                                    'call_put',
                                                                    'strike',
                                                                    'bid',
                                                                    'ask',
                                                                    'last_price',
                                                                    'open_interest'
                                                                ])
                if len(data) == 0:
                    break
                self.add_option_chain(exp)
                self._process_db_data(symbol = 'SPY', 
                                      expiry = exp,
                                      data = data)


        start_date = datetime.today() - timedelta(days=252)
        price_history = yahoofinance.get_price_history(symbol=self.symbol, start_date=start_date, end_date=None)
        price_history.index = price_history.index.normalize()
        rv = volatility_p(price_history)

        while not self.shut_down_flag.wait(timeout=30):

            #Fetch Option Data
            if self.exchange.is_open_now(self.exchange_schedule):
                data = yahoofinance.get_option_price_multiple(batch=_,range=20)
                self._process_yf_data(data)

            profitable_spreads = []
            #Process option data
            for i in range(len(self.expiries)):
            
                expiry = self.expiries[i]

                if expiry not in self.option_chains:
                    continue

                if datetime.strptime(expiry,'%Y-%m-%d').date() < datetime.now(UTC).date():
                    continue
                
                dte = get_time_to_expiry(expiry, as_day=True)

                curr_chain = self.option_chains[expiry]
                curr_price = yahoofinance.get_spot_price(self.symbol)['close']

                #Past RV
                past_rv = rv.iloc[-dte:].mean()

                #Train and forecast RV
                rv_forecast = self.forecast_engine.get_forecast(horizon = dte)

                #Compute analytics
                curr_chain.compute_moneyness(curr_price)
                curr_chain.compute_iv(curr_price)
                curr_chain.compute_greeks(curr_price, rv_forecast)
                curr_chain.compute_gex(curr_price)
           
                #Fit volatility surface
                try:
                    curr_chain.svi_fit(curr_price)

                except Exception as e:
                    logger.error(e.with_traceback(None))

                #Volatility Risk Premium
                call_atm_iv, put_atm_iv = curr_chain.get_atm_iv()
                call_vrp = (call_atm_iv - rv_forecast) * 100
                put_vrp = (put_atm_iv - rv_forecast) *  100

                #Premium is high, sell IC
                if call_vrp > VRP_THRESHOLD and put_vrp > VRP_THRESHOLD:
                    ic = curr_chain.construct_iron_condor(
                        ic_short_strike_delta_target = IC_SHORT_STRIKE_DELTA_TARGET,
                        ic_long_strike_delta_target= IC_LONG_STRIKE_DELTA_TARGET)
                    spread_type = OptionSpread.IRON_CONDOR
                    premium = ic.get_premium()

                    #Monte Carlo Simulation 
                    returns, freq = BSM_ev_monte_carlo(legs = ic.get_spread_data(), sigma = rv_forecast, initial_price = curr_price, expiry = expiry)
                    ev = np.sum(returns * freq) / np.sum(freq)

                    #greeks
                    greeks = ic.get_greeks()

                else: 
                    ic = None
                    ev = None
                    premium = None

                #Push trade
                if ic!= None and ev > 0:
                    spreads_data = {
                        'spread': ic,
                        'spread_type': spread_type,
                        'symbol': curr_chain.underlying_symbol,
                        'expiry': expiry,
                        'dte': curr_chain.get_dte(as_day=True),
                        'past_rv': past_rv,
                        'forecast_rv': rv_forecast,
                        'call_vrp': call_vrp,
                        'put_vrp': put_vrp,
                        'premium': premium,
                        'monte_carlo_ev': ev,
                        'greeks': greeks
                    }
                    profitable_spreads.append(spreads_data)
            
                
                logger.info(f'--------SPY {expiry}-------')
                logger.info(f'DTE: {dte}')
                logger.info(f'GEX: {curr_chain.get_net_gex():.4f}')
                logger.info(f'Past RV: {past_rv:.4f}')
                logger.info(f'RV forecast: {rv_forecast:.4f}')
                logger.info(f'Call VRP: {call_vrp:.2f}')
                logger.info(f'Put VRP: {put_vrp:.2f}')
                logger.info(f'IC Premium: {premium if premium is not None else None}')
                logger.info(f'Monte Carlo ev: {ev if ev is not None else None}')
                if ic is not None:
                    logger.info(f'delta:{greeks["delta"]:.4f} gamma:{greeks["gamma"]:.4f} theta:{greeks["theta"]:.4f} rho:{greeks["rho"]:.4f}')
                logger.info(f'----------------------------')

            self.profitable_spreads = profitable_spreads

        if self.shut_down_flag.is_set():
            logger.info('Screener stopped')

    def add_option_chain(self, expiry: str) -> None:
        if expiry not in self.option_chains:
            option_chain = OptionChainData(self.symbol,expiry)
            self.option_chains[expiry] = option_chain

    def get_term_structure(self) -> List:
        term_structure = []
        for k,op_chain in self.option_chains.items():
            call_atm_iv, put_atm_iv = op_chain.get_atm_iv()
            curr = {
                'DTE': op_chain.get_dte(as_day=True),
                'call_atm_iv': call_atm_iv,
                'put_atm_iv': put_atm_iv
            }
            term_structure.append(curr)
        return term_structure

    def get_gex(self) -> List:
        gex = []
        for k,op_chain in self.option_chains.items():
            curr = {
                'DTE': op_chain.get_dte(as_day=True),
                'net_gex': op_chain.get_net_gex()
            }
            gex.append(curr)
        return gex
    
    def get_profitable_spread(self):
        return self.profitable_spreads
    
    def get_profitable_spread_json(self):

        data = []
        for spread in self.profitable_spreads:
            spread_data = {}
            spread_data['spread'] = spread['spread'].get_spread_data()
            spread_data['spread_type'] = spread['spread_type']
            spread_data['symbol'] = spread['symbol']
            spread_data['expiry'] = spread['expiry']
            spread_data['dte'] = spread['dte']
            spread_data['past_rv'] = spread['past_rv']
            spread_data['forecast_rv'] = spread['forecast_rv']
            spread_data['call_vrp'] = spread['call_vrp']
            spread_data['put_vrp'] = spread['put_vrp']
            spread_data['premium'] = spread['premium']
            spread_data['monte_carlo_ev'] = spread['monte_carlo_ev']
            spread_data['greeks'] = spread['greeks']
            data.append(spread_data)

        return json.dumps(data)

    def get_volatility_surface(self):
        params = []
        iv = []
        tenors = []
        maturity = []
        moneyness_start = -0.25
        curr = moneyness_start
        moneyness_step_size = 0.0125
        moneyness_steps = 40
        moneyness = []
        for i in range(moneyness_steps):
            moneyness.append(curr)
            curr += moneyness_step_size
        
        for exp, option_chain in self.option_chains.items():
            if option_chain.svi_params is not None:
                (a,b,rho,m,sigma,forward) =  option_chain.svi_params
                k = np.array(moneyness)
                w = a + b * (rho * (k - m) + np.sqrt((k-m)**2 + sigma**2))
                curr_iv = np.sqrt(w/option_chain.maturity)
                iv.append(curr_iv.tolist())
                tenors.append(option_chain.expiry)
                maturity.append(option_chain.maturity)
                params.append(option_chain.svi_params)

        return {"moneyness_start": moneyness_start,
                "moneyness_step_size": moneyness_step_size,
                "moneyness_steps": moneyness_steps,
                "tenors": tenors,
                "maturity" : maturity,
                "iv": iv,
                "params":params}

    def get_raw_iv(self, expiry: str):
        return self.option_chains[expiry].get_full_iv()

    def _process_yf_data(self, data: List):
        
        for option_data in data:

            expiry = option_data[5]
            symbol = option_data[2]
            strike = option_data[4]
            right  = option_data[6]
            
            key = (str(strike),right)

            if key not in self.option_chains[expiry].options:
                op_data = OptionData(symbol = symbol,
                                     underlying_symbol = self.symbol,
                                     right = OptionRight.CALL if right == 'c' else OptionRight.PUT,
                                     strike = strike,
                                     expiry = expiry)
                
                self.option_chains[expiry].add_option(strike = str(strike),
                                                      right = right,
                                                      option_data = op_data)             
            last = option_data[7]
            bid = option_data[8]
            ask = option_data[9]
            oi = option_data[11]
            self.option_chains[expiry].options[key].update_tick(bid = bid,
                                                                ask = ask,
                                                                last = last,
                                                                open_interest = oi)

    def _process_db_data(self, symbol :str, expiry: str, data: List):

        for option_data in data:
            right, strike, bid , ask, last, oi = option_data
            key = (str(strike),right)
            if key not in self.option_chains[expiry].options:
                op_data = OptionData(symbol = symbol,
                                     underlying_symbol = self.symbol,
                                     right = OptionRight.CALL if right == 'c' else OptionRight.PUT,
                                     strike = strike,
                                     expiry = expiry)
                
                self.option_chains[expiry].add_option(strike = str(strike),
                                                      right = right,
                                                      option_data = op_data)   
                
                self.option_chains[expiry].options[key].update_tick(bid = bid,
                                                                    ask = ask,
                                                                    last = last,
                                                                    open_interest = oi)