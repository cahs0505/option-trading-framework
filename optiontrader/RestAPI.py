from flask import Flask, request
from flask_cors import CORS
from optiontrader.Database import Database
import optiontrader.mathtool as mathtool
import pandas as pd


from json import loads
from datetime import datetime

app = Flask(__name__)

db_remote = Database(remote=True, use_proxy=True)
db_local = Database(remote=False, use_proxy=True)
db_remote.connect()
db_local.connect()

CORS(app,resources=r'/api/*')

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/api/volatility/<symbol>", methods=['GET'])
def get_volatility(symbol):

    history = request.args.get("history")
    window = int(request.args.get("window"))

    df = db_local.get_price_history_yf(symbol=symbol,
                                    columns=["time","close"],
                                    history=history)
    
    df = mathtool.log_return(df)
    df = mathtool.volatility(df,window=window)

    df.drop(columns=["close","log_return"],axis=1,inplace=True)
    df.dropna(inplace=True)
  
    result = df.to_json(orient="table")
    data = loads(result)

    return data

@app.route("/api/implied_volatility/<symbol>", methods=['GET'])
def get_implied_volatility(symbol):

    expiry = request.args.get("expiry")

    df = db_remote.get_option_data_yf(symbol=symbol,
                                    columns=["time","expiry","implied_volatility"],
                                    atm_only=True)
    
    df.drop_duplicates(inplace=True)
    df.drop(df[df.implied_volatility < 0.1].index, inplace=True)
    expiry_date = datetime.strptime(expiry,"%Y-%m-%d").date()
    df = df.loc[df["expiry"] == expiry_date]
    df = df.groupby(pd.to_datetime(df.index).strftime('%Y-%m-%d'))["implied_volatility"].agg(['last']).reset_index()
    df.set_index("time",inplace=True)
    df.rename(columns={"last": "iv"},inplace=True)

    iv = df["iv"]
    result = iv.to_json(orient="split")
    data = loads(result)

    return data

@app.route("/api/earning_dates/<symbol>", methods=['GET'])
def get_earning_dates(symbol):

    data = db_remote.get_sec_filing(symbol=symbol)
    data = {"data":data}

    return data

    
@app.route("/api/analysis/iv_crush", methods=['GET'])
def get_analysis_iv_crush():

    time_diff = request.args.get("time_diff")
    df = pd.read_csv("analysis/result/out.csv")

    ##drop outliers
    df.drop([1329],inplace=True)

    df["iv_minus_vol"] = df.pre_earning_iv - df.post_earning_vol

    if time_diff is not None:
        time_diff = int(request.args.get("time_diff"))
        df = df.loc[df.time_difference <= time_diff]
    
    result = df.to_json(orient="table")
    
    data = loads(result)
    data["statistics"] = {"mean_iv_minus_vol" : df["iv_minus_vol"].mean(),
                          "variance_iv_minus_vol" : df["iv_minus_vol"].var(),
                          "mean_iv_change": df["iv_change"].mean(),
                          "variance_iv_change": df["iv_change"].var(),
                          }
    

    return data



if __name__ == '__main__':
    app.run()