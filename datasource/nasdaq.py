import requests
import logging
import time
import re
from typing import List 
from requests.exceptions import RequestException

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

earnings_url = 'https://api.nasdaq.com/api/calendar/earnings?date='


def get_earnings(date: str) -> List:

    data = []
    daily_earnings_url = earnings_url + date

    retries = 5
    for attempt in range(retries):

        try:
            earnings_r = requests.get(daily_earnings_url, headers=headers, timeout=15)
            earnings_r.raise_for_status()
            earnings_data = earnings_r.json()

            if not earnings_data.get('data') or not earnings_data['data'].get('rows'):
                logging.warning(f"No earnings data found for {date}")
                

            else:
                companies_earn = earnings_data['data']['rows']
                for row in companies_earn:
        
                    row_data = (date,
                            row["symbol"],
                            _parse_eps(row["eps"]) if row.get("eps") else None,
                            _parse_eps(row["epsForecast"]) if row.get("epsForecast") else None,
                            row["fiscalQuarterEnding"] 
                    )

                    data.append(row_data)

            break
                
        except RequestException as e:
            raise e

    return data
    

def _parse_eps(eps_string: str) -> float:

    decimal = "\\d.*\\d"
    negative = "\(.*\)"

    if (re.search("\$",eps_string)):

        decimal = re.search(decimal,eps_string)
        value_string = decimal.group().replace(",","") if decimal else "0"

        if (re.search(negative,eps_string)):
            
            return -float(value_string)
        else: 

            return float(value_string)
    else:

        return None



