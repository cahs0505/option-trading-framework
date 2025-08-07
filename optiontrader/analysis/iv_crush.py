from optiontrader.Database import Database
import yfinance as yf
import pandas as pd
import argparse
import logging
from dotenv import load_dotenv
import datetime
import numpy as np
from optiontrader.option.Option import *

logging.basicConfig(level=logging.INFO)
load_dotenv(override=True)

parser = argparse.ArgumentParser()
parser.add_argument('-r', action='store_true', help="Use remote database")
parser.add_argument('-p', action='store_true', help="Use proxy")
parser.add_argument('-d', action='store_true', help="Debug mode")
args = parser.parse_args()

yf.set_config(proxy=None)
logging.basicConfig(level=logging.INFO)

db_local  = Database(remote = False, use_proxy = args.p)
db_local.connect()
db_remote = Database(remote = True, use_proxy = args.p)
db_remote.connect()

def get_expiry(symbol):

	all_expiry = db_remote.get_option_expiry_dates_yf(symbol=symbol)
	all_expiry.sort(reverse=True)
	all_expiry = [item.strftime("%Y-%m-%d") for item in all_expiry]

	return all_expiry

def get_earnings(symbol):

	earnings = db_remote.get_earnings(symbol=symbol)
	earnings.sort_values(by=["date"],ascending=False,inplace=True)
	earnings = earnings["date"].to_list()
	earnings = [item.strftime("%Y-%m-%d") for item in earnings]

	return earnings

def get_option_data_and_process(symbol: str, exp: str) -> pd.DataFrame:

	df = db_remote.get_option_data_yf(symbol=symbol,
						columns=["time",
								"expiry",
								"implied_volatility"],
								expiry=exp)
	
	df.drop_duplicates(inplace=True)
	df.drop(df[df.implied_volatility < 0.1].index, inplace=True)
	df = df.groupby(pd.to_datetime(df.index).strftime('%Y-%m-%d'))["implied_volatility"].agg(['last']).reset_index()
	df.set_index("time",inplace=True)
	df.rename(columns={"last": "iv"},inplace=True)

	return df

def earning_is_in_option_duration(earning,df):

	return earning in df.index

def get_pre_and_post_earning_iv(df, earning_date):

	return (df.loc[earning_date]["iv"], df.loc[earning_date:].iloc[1:2]["iv"].values[0])
    
def get_price_history_and_process(symbol):

	stock_price = db_local.get_price_history_yf(symbol=symbol,
                                      columns=["time","close"],
                                      history="5y")
	
	stock_price["log_return"] = np.log(stock_price.close / stock_price.close.shift(1))


	return stock_price

def price_history_l(df, earning_date, expiry_date):
	
	return df.loc[earning_date:expiry_date]



def get_day_differnce(start_date, end_date):
	return (datetime.datetime.strptime(end_date,"%Y-%m-%d") - datetime.datetime.strptime(start_date,"%Y-%m-%d")).days


def compute_sample(symbol,
			   option_data: pd.DataFrame,
			   stock_price_data: pd.DataFrame,
			   earning_date: str,
			   expiry_date: str):
	
	day_diff = get_day_differnce (start_date=earning_date,end_date=expiry_date)

	#calculate iv
	pre_earning_iv = get_pre_and_post_earning_iv(df=option_data, earning_date=earning_date)[0]
	post_earning_iv = get_pre_and_post_earning_iv(df=option_data, earning_date=earning_date)[1]
	iv_change = post_earning_iv - pre_earning_iv

	#calculate vol
	post_earning_vol_annualized = stock_price_data["log_return"].dropna().std() * np.sqrt(252)

	return (symbol, earning_date, expiry_date, day_diff, pre_earning_iv, post_earning_iv, iv_change, post_earning_vol_annualized)

def report(sample):
	print(f"symbol: {sample[0]}")
	print(f"earning date: {sample[1]}")
	print(f"expiry date: {sample[2]}")
	print(f"time difference(day): {sample[3]}")
	print(f"Pre-earning iv: {sample[4]}")
	print(f"Post-earning iv: {sample[5]}")
	print(f"iv change: {sample[6]}")
	print(f"Post earning volatility (annualized): {sample[7]}")

def run_test():

	symbols = db_remote.get_symbols()
	symbols = ['NVDA', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'META', 'AVGO', 'TSM', 'BRK-B', 'TSLA', 'JPM', 'WMT', 'V', 'LLY', 'ORCL', 'SPY', 'NFLX', 'MA', 'XOM', 'COST', 'PG', 'JNJ', 'HD', 'BAC', 'SAP', 'ABBV', 'PLTR', 'NVO', 'ASML', 'KO', 'UNH', 'PM', 'CSCO', 'TMUS', 'WFC', 'IBM', 'GE', 'CRM', 'BABA', 'CVX', 'NVS', 'ABT', 'MS', 'AXP', 'TM', 'LIN', 'AMD', 'DIS', 'GS', 'QQQ', 'INTU', 'NOW', 'AZN', 'HSBC', 'SHEL', 'MCD', 'T', 'MRK', 'TXN', 'UBER', 'HDB', 'ISRG', 'RTX', 'ACN', 'BX', 'CAT', 'RY', 'BKNG', 'PEP', 'VZ', 'QCOM', 'BLK', 'SCHW', 'C', 'ARM', 'EADSY', 'BA', 'SPGI', 'TMO', 'ADBE', 'AMGN', 'MUFG', 'HON', 'BSX', 'SONY', 'PGR', 'AMAT', 'NEE', 'SHOP', 'SYK', 'UL', 'SPOT', 'PDD', 'DHR', 'PFE', 'ETN', 'COF', 'UNP', 'GEV', 'DE', 'TJX', 'GILD', 'TTE', 'MU', 'PANW', 'CMCSA', 'BUD', 'BHP', 'TD', 'ANET', 'KKR', 'CRWD', 'LOW', 'MELI', 'SAN', 'LRCX', 'ADP', 'KLAC', 'ADI', 'IBN', 'APH', 'AIQUY', 'SNY', 'COP', 'VRTX', 'APP', 'CB', 'MDT', 'MSTR', 'NKE', 'RTNTF', 'UBS', 'CFRUY', 'LMT', 'SBUX', 'MMC', 'BTI', 'ICE', 'AMT', 'BNPQY', 'DASH', 'SO', 'MO', 'PLD', 'WELL', 'CME', 'BN', 'SMFG', 'INTC', 'IBKR', 'ENB', 'CEG', 'TT', 'RELX', 'FI', 'BMY', 'RIO', 'PH', 'BAM', 'WM', 'DUK', 'MCO', 'RCL', 'COIN', 'HCA', 'TRI', 'BBVA', 'MCK', 'MDLZ', 'CDNS', 'SHW', 'CTAS', 'SE', 'UPS', 'RACE', 'TOELY', 'TDG', 'CI', 'CVS', 'SNPS', 'SCCO', 'DELL', 'NTES', 'ABNB', 'HOOD', 'APO', 'MMM', 'BMO', 'AJG', 'FTNT', 'BP', 'PBR', 'GLD', 'INFY', 'GD', 'EMR', 'ELV', 'ORLY', 'PNC', 'ECL', 'GSK', 'EQIX', 'CMG', 'MAR', 'AON', 'ATLKY', 'BAESY', 'ITW', 'CP', 'RSG', 'CL', 'USB', 'PYPL', 'SNOW', 'HWM', 'NOC', 'WMB', 'MSI', 'ZTS', 'ITUB', 'MFG', 'NGG', 'RBLX', 'JCI', 'BNS', 'EPD', 'ADSK', 'CNQ', 'CM', 'EOG', 'ING', 'CNI', 'NEM', 'NET', 'BK', 'EQNR', 'FCX', 'NU', 'VST', 'HLT', 'APD', 'CARR', 'MRVL', 'BCS', 'WDAY', 'CRH', 'KMI', 'CSX', 'SHECY', 'AZO', 'SPG', 'CAIXY', 'LYG', 'AXON', 'ET', 'ROP', 'MNST', 'IAU', 'AEM', 'TRV', 'TFC', 'GBTC', 'ANZGY', 'DLR', 'NSC', 'REGN', 'NXPI', 'DEO', 'ARES', 'FDX', 'CRARY', 'CODYY', 'MBGYY', 'COR', 'PWR', 'CHTR', 'DB', 'AFL', 'TEAM', 'AEP', 'CPNG', 'AMX', 'MFC', 'NWG', 'MET', 'MPC', 'ATEYY', 'DDOG', 'LNG', 'PAYX', 'CTVA', 'ALL', 'PTCAY', 'MPLX', 'O', 'PSA', 'PSX', 'AMP', 'NDAQ', 'TEL', 'URI', 'OKE', 'PCAR', 'GM', 'BDX', 'GWW', 'DFS', 'TRP', 'E', 'GLNCY', 'FLUT', 'FAST', 'ZS', 'SRE', 'VRT', 'D', 'SLB', 'AIG', 'TAK', 'LHX', 'CTA-PA', 'CPRT', 'TGT', 'SU', 'XLF', 'F', 'WCN', 'VEEV', 'JD', 'KR', 'HLN', 'KDP', 'CMI', 'MSCI', 'GLW', 'VLO', 'FICO', 'EW', 'CCI', 'FERG', 'HES', 'CCEP', 'IDXX', 'TTWO', 'KMB', 'VALE', 'EXC', 'ALC', 'ALNY', 'OXY', 'ROST', 'FIS', 'CBRE', 'VRSK', 'AME', 'YUM', 'WPM', 'IMO', 'GRMN', 'HMC', 'FANG', 'BSBR', 'CVNA', 'CCL', 'DHI', 'PEG', 'KVUE', 'ANYYY', 'SVNDY', 'FRFHF', 'CTSH', 'MCHP', 'CAH', 'XEL', 'OTIS', 'BKR', 'HEI', 'ROK', 'EA', 'TCOM', 'ABEV', 'PRU', 'NTDTY', 'FER', 'WTKWY', 'RMD', 'TRGP', 'DNZOY', 'SYY', 'SLF', 'CUK', 'WAB', 'FMX', 'TTD', 'ETR', 'TLGPY', 'OLCLY', 'DIA', 'MPWR', 'DKILY', 'ODFL', 'ED', 'BRO', 'HSY', 'HIG', 'VICI', 'CHT', 'EBAY', 'VMC', 'IR', 'GEHC', 'CSGP', 'LYV', 'GWLIF', 'A', 'LVS', 'EXR', 'MLM', 'NVZMY', 'ACGL', 'WEC', 'DAL', 'ARGX', 'EQT', 'WIT', 'DXCM', 'MTB', 'EFX', 'GOLD', 'ANSS', 'RJF', 'MDY', 'XYL', 'PUK', 'FNV', 'CCJ', 'EL', 'NUE', 'STX', 'KHC', 'STT', 'DSCSY', 'KB', 'QSR', 'NRG', 'DD', 'IT', 'LPLA', 'RYAAY', 'PCG', 'WTW', 'STZ', 'TW', 'BBD', 'TME', 'OWL', 'TEF', 'BIDU', 'WDS', 'STLA', 'IRM', 'LULU', 'NTR', 'HUBS', 'STM', 'SMCI', 'RDDT', 'FITB', 'TSCO', 'HUM', 'AVB', 'GIS', 'KEYS', 'ERIC', 'BR', 'IQV', 'VTR', 'LEN', 'RKT', 'SYM', 'HPE', 'NOK', 'WBD', 'K', 'MRAAY', 'SMPNY', 'FCNCA', 'DTE', 'ROL', 'PPERY', 'AWK', 'CQP', 'WRB', 'PUBGY', 'UAL', 'VRSN', 'PPG', 'OEZVY', 'LI', 'XLV', 'SYF', 'IP', 'XLY', 'ADM', 'BNTX', 'VOD', 'EQR', 'AEE', 'DOV', 'IX', 'YAHOY', 'FUJIY', 'DRI', 'VLTO', 'CVE', 'UI', 'NTRS', 'HBAN', 'TYL', 'MKL', 'GDDY', 'FANUY', 'TOST', 'SBAC', 'MTD', 'DG', 'MT', 'PPL', 'TPL', 'EJPRY', 'TU', 'VIK', 'EME', 'HPQ', 'TDY', 'JBL', 'CHD', 'FOXA', 'CHKP', 'CBOE', 'ATO', 'PINS', 'CDW', 'CPAY', 'FTS', 'ZM', 'GIB', 'ES', 'ON', 'BDORY', 'AU', 'CNP', 'STE', 'CINF', 'WDC', 'FE', 'DIDIY', 'ASX', 'PHG', 'SHG', 'EXPE', 'AFRM', 'RF', 'NVR', 'IOT', 'HUBB', 'NTRA', 'GFS', 'AMCR', 'TROW', 'LH', 'PHM', 'CJPRY', 'PBA', 'GFI', 'NTAP', 'ULTA', 'LII', 'DVN', 'WSM', 'DLTR', 'PODD', 'LDOS', 'BEKE', 'PTC', 'CMS', 'BCE', 'AER', 'WAT', 'CFG', 'SSNC', 'NTNX', 'TECK', 'KOF', 'RPRX', 'TSN', 'TS', 'SGSOY', 'DKNG', 'KEY', 'EIX', 'MKC', 'DOW', 'CG', 'GRAB', 'CYBR', 'INVH', 'GPN', 'LYB', 'FSLR', 'STLD', 'DGX', 'CRBG', 'UMC', 'RBA', 'ESS', 'IFF', 'TEVA', 'BIIB', 'KGC', 'LUV', 'GWRE', 'L', 'FLEX', 'CTRA', 'CASY', 'NMR', 'VIV', 'WY', 'FIX', 'KKPNY', 'GEN', 'EC', 'TPG', 'TRMB', 'EDPFY', 'TPR', 'NI', 'PSTG', 'INSM', 'ZBH', 'HAL', 'WSO', 'CW', 'IHG', 'TWLO', 'PKG', 'PFG', 'USFD', 'ERIE', 'OMVKY', 'MAA', 'BAP', 'FTV', 'TRU', 'DUOL', 'GFL', 'ONON', 'NWSA', 'GPC', 'RCI', 'NNGRY', 'PNR', 'RYAN', 'BOUYY', 'BEP', 'PKX', 'ZG', 'OKTA', 'KEP', 'MDB', 'FFIV', 'CSL', 'RS', 'SUI', 'EBR', 'CNH', 'CHWY', 'YUMC', 'FUTU', 'RL', 'DT', 'FDS', 'EQH', 'SNA', 'TLK', 'BSY', 'HRL', 'KSPI', 'FMS', 'CNC', 'DKS', 'ZBRA', 'BALL', 'XLE', 'EXPD', 'EVRG', 'WST', 'DOCU', 'ILMN', 'J', 'THC', 'FNF', 'BAX', 'SFM', 'DECK', 'LNT', 'MNDY', 'APTV', 'BIP', 'BG', 'RIVN', 'BURL', 'XPO', 'ARCC', 'MBLY', 'SNAP', 'DPZ', 'SBS', 'VDMCY', 'CLX', 'UDR', 'CF', 'WMG', 'JBSAY', 'ACM', 'BCH', 'BBY', 'JBHT', 'SN', 'WWD', 'AMH', 'EWBC', 'ALAB', 'TER', 'WES', 'TXT', 'GGG', 'SGIOY', 'FTI', 'OMC', 'KIM', 'COO', 'RPM', 'TKO', 'BJ', 'UNM', 'HOLX', 'WLMIY', 'EG', 'AVY', 'ZTO', 'ALGN', 'APG', 'ULS', 'COHR', 'H', 'BLDR', 'MAS', 'PFGC', 'WPC', 'JBAXY', 'LOGI', 'IEX', 'SOLV', 'MTZ', 'BAH', 'EMRAF', 'BF-B', 'JNPR', 'ARE', 'UTHR', 'INCY', 'GLPI', 'SNN', 'JKHY', 'MORN', 'ENTG', 'BEN', 'RGA', 'BWXT', 'PAYC', 'PAA', 'MOH', 'HLI', 'ROKU', 'REG', 'YPF', 'NBIX', 'ALLE', 'LAMR', 'RDY', 'ITT', 'ALLY', 'DOC', 'YMM', 'GMAB', 'STN', 'NDSN', 'TXRH', 'CCK', 'CLH', 'JHX', 'ELS', 'X', 'MMYT', 'JLL', 'ACI', 'CNA', 'OC', 'NVT', 'CART', 'CNM', 'CPT', 'BXP', 'MANH', 'RTO', 'PAG', 'LECO', 'CELH', 'EHC', 'BSAC', 'RVTY', 'ICLR', 'UHS', 'SUZ', 'RGLD', 'SWKS', 'MOS', 'NLY', 'MRNA', 'FTAI', 'JEF', 'MGA', 'RNR', 'RKUNY', 'SCI', 'RDEIY', 'CHRW', 'PAC', 'SEIC', 'AR', 'TOL', 'SNX', 'AEG', 'SLV', 'HST', 'POOL', 'AKAM', 'PR', 'UHAL', 'SF', 'ARMK', 'CR', 'SJM', 'KNSL', 'WYNN', 'BMRN', 'SWK', 'VTRS', 'OHI', 'PCOR', 'PPC', 'OUKPY', 'PNW', 'SSMXY', 'DVA', 'NICE', 'CACI', 'AFG', 'ATR', 'KMX', 'FN', 'GME', 'CX', 'QGEN', 'UUGRY', 'XP', 'WLK', 'OVV', 'EPAM', 'WTRG', 'DOX', 'SQM', 'COKE', 'MGM', 'HTHT', 'TKHVY', 'EXAS', 'RRX', 'CAG', 'CAVA', 'TAP', 'LKQ', 'BLD', 'CUBE', 'WBA', 'BPYPP', 'HII', 'UWMC', 'AIZ', 'DSEEY', 'PSO', 'KAIKY', 'AOS', 'TTEK', 'PTBRY', 'SKX', 'ASR', 'AVTR', 'ORI', 'IPG', 'HSIC', 'CPB', 'NYT', 'MEDP', 'WMS', 'ESTC', 'EMN', 'WIX', 'WING', 'CSXXY', 'BDNNY', 'REXR', 'ALV', 'GNRC', 'BIRK', 'USO', 'DSGX', 'CFLT', 'FND', 'EBCOY', 'KIKOY', 'VFS', 'APPF', 'EDU', 'LNW', 'MUSA', 'TECH', 'FRT', 'DINO', 'DCI', 'QRVO', 'SIRI', 'AES', 'HESM', 'GMED', 'PSN', 'ALB', 'TFII', 'WPP', 'SAIA', 'CRL', 'NIO', 'IDKOY', 'OLED', 'CHDN', 'BZ', 'INFA', 'LW', 'ELF', 'TTC', 'APA', 'MKSI', 'BBWI', 'CHE', 'CE', 'LEGN', 'BRKR', 'FBIN', 'TREX', 'SPXSY', 'CZR', 'KBR', 'CHRD', 'CROX', 'ENPH', 'AMKR', 'TFX', 'LB', 'ONTO', 'COTY', 'ANF', 'PCVX', 'WFRD', 'ZI', 'VIVHY', 'SRPT']
	print("all symbol:")
	print(symbols)
	data= []

	for symbol in symbols:

		print(f"Testing {symbol}")
		all_expiry = get_expiry(symbol=symbol)
		earnings = get_earnings(symbol=symbol)

		price_history = get_price_history_and_process(symbol=symbol)


		##iterate all earning date
		for earning in earnings:
			
			earning_success = False

			#iterate all expiry dates
			for exp in all_expiry:
			

				option_data = get_option_data_and_process(symbol=symbol, exp=exp)


				if (earning_is_in_option_duration(earning=earning,df=option_data)):
			
					try:
						print(f"Testing earning: {earning} - Expiry: {exp}")
						price_this_period = price_history.loc[earning:exp]
						sample_data = compute_sample(
							symbol=symbol,
							option_data=option_data, 
							stock_price_data=price_this_period,
							earning_date=earning,
							expiry_date=exp)
						data.append(sample_data)
		
				
						earning_success = True
				
					except Exception as e:
						print(e)


			if not earning_success:
				break
				

	data = pd.DataFrame(data,columns=["symbol",'earning_date', 'expirt_date', 'time_difference', 'pre_earning_iv','post_earning_iv','iv_change','post_earning_vol' ])
	data.to_csv('iv_crush.csv', index=False) 
			
# run_test()
o1 = Option(symbol="TSLA",                  
            right=OptionRight.CALL,         
            position=Position.LONG,
            strike = Decimal('80'),
            expiration=None,
            premium=Decimal('20.4')
            )

db_local.disconnect()
db_remote.disconnect()



