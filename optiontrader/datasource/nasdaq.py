from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException
import logging
import re
from typing import List, Dict

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

earnings_url = 'https://api.nasdaq.com/api/calendar/earnings?date='

time_map = {
    'time-pre-market':'pre',
    'time-after-hours':'after',
    'time-not-supplied':'na'
}


def get_earnings(date: str,
                 proxies: Dict = None
                 ) -> List:

    data = []
    daily_earnings_url = earnings_url + date

    try:
        earnings_r = requests.get(daily_earnings_url, impersonate="chrome", proxies=proxies)
        earnings_r.raise_for_status()
        earnings_data = earnings_r.json()

        if not earnings_data.get('data') or not earnings_data['data'].get('rows'):
            logging.warning(f'No earnings data found for {date}')

        else:
            companies_earn = earnings_data['data']['rows']
            for row in companies_earn:

                fiscalQuarterEnding =  row['fiscalQuarterEnding'].split('/')
                time = time_map[row['time']]
                row_data = (row['symbol'],
                            date,
                            fiscalQuarterEnding[0].lower(),
                            int(fiscalQuarterEnding[1]),
                            _parse_eps(row['eps']) if row.get('eps') else None,
                            _parse_eps(row['epsForecast']) if row.get('epsForecast') else None,
                            time,
                            )

                data.append(row_data)

    except RequestException as e:
        raise e

    return data
    

def _parse_eps(eps_string: str) -> float:

    decimal = '\\d.*\\d'
    negative = '\(.*\)'

    if (re.search('\$',eps_string)):

        decimal = re.search(decimal,eps_string)
        value_string = decimal.group().replace(',','') if decimal else '0'

        if (re.search(negative,eps_string)):
            
            return -float(value_string)
        else: 

            return float(value_string)
    else:

        return None



