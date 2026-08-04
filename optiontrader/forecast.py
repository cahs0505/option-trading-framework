import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from typing import Dict
from datetime import datetime, timedelta, UTC
from optiontrader.datasource.yahoofinance import get_price_history
from optiontrader.database import Database
from optiontrader.mathtools import volatility_p
from optiontrader.logger import logger
from sklearn.linear_model import LinearRegression

Horizon = int
class ForecastEngine:
    """
    Volatility forecast engine.
    Used the Heterogeneous Autoregressive (HAR) model
    """
    
    db: Database
    models: Dict[Horizon, LinearRegression]
    forecasts: Dict[Horizon, float]
    train_look_back: int = 3000
    symbol = 'SPY'

    def __init__(self, db:Database):
        self.db = db
        self.models = {}
        self.forecasts = {}

    def HAR_train(self, horizon: Horizon = 1):
        train_period = self.train_look_back
        price = self._get_price_data('SPY', history = train_period)
        v = volatility_p(price)

        df = pd.DataFrame({'v_t+1': v})
        df['v_t'] = df['v_t+1']
        df['v_week_t'] = df['v_t'].rolling(window = 5).mean()
        df['v_month_t'] = df['v_t'].rolling(window = 22).mean()
        df['v_t+1'] = df['v_t+1'].shift(-1)
        df.dropna(inplace=True)

        predictors = [
            'v_t',
            'v_week_t',
            'v_month_t'
        ]
        if horizon > 1:
            df = df.groupby(np.arange(len(df)) // horizon).mean()

        X = df[predictors].to_numpy()
        y = df['v_t+1'].to_numpy()
        y_train_mean = np.mean(y)
        ols_model = LinearRegression().fit(X=X,y=y)
        
        y_fit = ols_model.predict(X)
        for j in range(len(y_fit)):
            if y_fit[j] < 0:
                y_fit[j] = y_train_mean

        wls_weights = np.reciprocal(np.array(y_fit))
        wls_model = LinearRegression().fit(X=X,y=y,sample_weight=wls_weights)

        self.models[horizon] = wls_model

        return wls_model

    def HAR_forecast(self, horizon: Horizon= 1):
        price = self._get_price_data('SPY', history = 50)
        v = volatility_p(price)

        df = pd.DataFrame({'v_t+1': v})
        df['v_t'] = df['v_t+1']
        df['v_week_t'] = df['v_t'].rolling(window = 5).mean()
        df['v_month_t'] = df['v_t'].rolling(window = 22).mean()
        df['v_t+1'] = df['v_t+1'].shift(-1)

        if horizon > 1:
            df = df.groupby(np.arange(len(df)) // horizon).mean()

        df = df.iloc[-1]
        predictors = [
            'v_t',
            'v_week_t',
            'v_month_t',
        ]

        X = df[predictors].to_numpy().reshape(1,-1)
        y = self.models[horizon].predict(X)[0]

        self.forecasts[horizon] = y
        
        return y
    
    def naive_forecast(self, horizon: Horizon= 1):
        price = self._get_price_data(symbol = self.symbol, history = 50)
        v = volatility_p(price)
        if horizon > 1:
            v = v.groupby(np.arange(len(v)) // horizon).mean()
        return v.iloc[-1]
        
    def get_forecast(self, horizon: Horizon = 1):
        try:
            if horizon in self.forecasts:
                return self.forecasts[horizon]
            elif horizon in self.models:
                return self.HAR_forecast(horizon)
            else :
                self.HAR_train(horizon)
                return self.HAR_forecast(horizon)
        except Exception as e:
            logger.error('forecast engine encountering unexpected error, using naive forecast')
            return self.naive_forecast(horizon)
        
    def get_volatility_history(self, symbol: str = 'SPY', history: int = 1):
        price = self._get_price_data(symbol = symbol, history = history * 365)
        v = volatility_p(price)
        return v
    
    def _get_price_data(self, symbol:str, history:int = 1):
        now = datetime.now(UTC)
        today = str(now.date())

        yf_df = get_price_history(symbol, start_date = str(now.date() - timedelta(days = 1) * history))
        yf_df.index = yf_df.index.date
        yf_df.drop(columns=['dividends','splits','Capital Gains','symbol'], inplace=True)

        #Patch Yfinance data with our data
        exchange = mcal.get_calendar('NYSE')
        cal = exchange.schedule(start_date = str(now.date() - timedelta(days = 7)), end_date = today)
        cal = cal[cal.index <= today]
        closest_date = str(cal.index[-1].date())

        if now < cal.loc[closest_date].market_open:
            last = cal.index[-2].date()
        elif now > cal.loc[closest_date].market_open and now < cal.loc[closest_date].market_close:
            last = cal.index[-2].date()
        else:
            last = cal.index[-1].date()

        if last in yf_df.index and not np.isnan(yf_df.loc[last]['close']): 
            return yf_df
        else:
            yf_df.drop(index=last,inplace=True)
            data = self.db.get_ohlc_5min_yf('SPY')
            df = pd.DataFrame(data, columns=['time','open','high','low','close','volume'])
            df = df.set_index('time', drop=True)
            df =  df.resample('D').agg(
                {'open': 'first',   
                    'high': 'max',    
                    'low': 'min',     
                    'close': 'last',  
                    'volume': 'sum'    
                }).dropna()
            df.index = df.index.date
            df = df.apply(pd.to_numeric)
            row_to_patch = df.loc[[last]]
            df_patched = pd.concat([yf_df,row_to_patch],axis=0)

            return df_patched