import pandas as pd
import numpy as np


def log_return(data: pd.DataFrame):

    data["log_return"] = np.log(data.close / data.close.shift(1))

    return data
    

def volatility(data: pd.DataFrame,
                window: int):
    
    data["volatility"] = data["log_return"].rolling(window=window).std() * np.sqrt(252)

    return data

