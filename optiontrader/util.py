import datetime
import pandas_market_calendars as mcal
import pandas as pd
from optiontrader.constants import *

def validate_date(date_text):
    """
    All date should be in ISO 8601 format (YYYY-MM-DD)
    """
    try:
        datetime.date.fromisoformat(date_text)
    except ValueError:
        raise ValueError(f"Incorrect data format : {date_text}, should be YYYY-MM-DD")
    
def get_time_to_expiry(expiry: str, as_day: bool = False):
    """
    Get number of trading days until market close of expiry date
    """
    exchange = mcal.get_calendar('NYSE')
    now = datetime.datetime.now(datetime.UTC)
    today = now.date().strftime('%Y-%m-%d')
    schedule = exchange.schedule(start_date=today, end_date=expiry)
    if(today in schedule.index):
        trading_days_remaining = len(schedule.index) - 1
        if(now < schedule.loc[today]['market_open']):
            time_to_maturity = (trading_days_remaining + 1)
        elif(now > schedule.loc[today]['market_open'] and now < schedule.loc[today]['market_close']):
            time_remaining_today = ((schedule.loc[today]['market_close'] - now).seconds/3600) / TRADING_HOURS_PER_DAY
            time_to_maturity = (time_remaining_today + trading_days_remaining)
        else:
            time_to_maturity = trading_days_remaining
    else:
        trading_days_remaining = len(schedule.index)
        time_to_maturity = trading_days_remaining

    if not as_day:
        return time_to_maturity / YEARLY_TRADING_DAYS
    else:
        return int(time_to_maturity)

def is_market_open():
    exchange = mcal.get_calendar("NYSE")
