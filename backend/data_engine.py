import yfinance as yf
import pandas as pd
import json
import requests
import io

# Fallback List (Nifty 100)
HARDCODED_NIFTY_100 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "INFY.NS", "LICI.NS",
    "ITC.NS", "HINDUNILVR.NS", "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "KOTAKBANK.NS", "TITAN.NS", "ONGC.NS", "TATAMOTORS.NS", "NTPC.NS", "AXISBANK.NS",
    "ADANIPORTS.NS", "ULTRACEMCO.NS", "WIPRO.NS", "M&M.NS", "JSWSTEEL.NS", "BAJAJFINSV.NS", "BAJAJ-AUTO.NS",
    "LTIM.NS", "TATASTEEL.NS", "COALINDIA.NS", "SIEMENS.NS", "SBILIFE.NS", "GRASIM.NS", "POWERGRID.NS",
    "TECHM.NS", "HDFCLIFE.NS", "BRITANNIA.NS", "INDUSINDBANK.NS", "CIPLA.NS", "TATACONSUM.NS", "BPCL.NS",
    "NESTLEIND.NS", "DRREDDY.NS", "EICHERMOT.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "HINDALCO.NS", "TATACONSUM.NS",
    "ASIANPAINT.NS", "DMART.NS", "GICRE.NS", "IOC.NS", "IRFC.NS", "JIOFIN.NS", "L&T.NS", "VBL.NS", "ZOMATO.NS",
    "BEL.NS", "TRENT.NS", "CHOLAFIN.NS", "TVSMOTOR.NS", "DLF.NS", "HAL.NS", "BANKBARODA.NS", "INDIGO.NS",
    "PFC.NS", "RECLTD.NS", "HAVELLS.NS", "GAIL.NS", "SHRIRAMFIN.NS", "ABB.NS", "ICICIPRULI.NS", "CANBK.NS",
    "PNB.NS", "JINDALSTEL.NS", "VARROC.NS", "PAGEIND.NS", "BOSCHLTD.NS", "HONAUT.NS", "PIDILITIND.NS",
    "GODREJCP.NS", "BERGEPAINT.NS", "MOTHERSON.NS", "MRF.NS", "NAUKRI.NS", "POLYCAB.NS", "SRF.NS",
    "TATAELXSI.NS", "ALKEM.NS", "AUBANK.NS", "AUROPHARMA.NS", "BALKRISIND.NS", "BANDHANBNK.NS", "BHARATFORG.NS"
]

def get_all_nse_tickers():
    """
    Fetches the list of all active equity symbols from NSE website.
    Returns a list of symbols with '.NS' appended.
    Falls back to HARDCODED_NIFTY_100 if download fails.
    """
    try:
        # NSE Equity List URL
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print("Fetching full ticker list from NSE...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse CSV
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        
        # Extract SYMBOL column and append .NS
        if 'SYMBOL' in df.columns:
            tickers = [f"{sym}.NS" for sym in df['SYMBOL'].tolist()]
            print(f"Successfully fetched {len(tickers)} tickers from NSE.")
            return tickers
        else:
            print("CSV format changed, column 'SYMBOL' not found.")
            return HARDCODED_NIFTY_100
            
    except Exception as e:
        print(f"Failed to fetch from NSE: {e}. Using fallback list.")
        return HARDCODED_NIFTY_100

# Expose the function result (or the function itself)
ALL_MARKET_TICKERS = get_all_nse_tickers()

def fetch_stock_data(ticker_symbol):
    """
    Fetches 1-month and 1-week OHLC data, fundamental info, and news for a specific stock.
    Return None if data is incomplete or empty.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # 1. Price History
        # We need enough data for TA. 1mo is good for daily, 5d for short term.
        hist = ticker.history(period="1mo")
        
        if hist.empty:
            return None

        # 2. Fundamentals (Handle missing keys gracefully)
        info = ticker.info
        fundamentals = {
            "symbol": ticker_symbol,
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "debt_to_equity": info.get("debtToEquity"),
            "profit_margins": info.get("profitMargins"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "long_business_summary": info.get("longBusinessSummary") 
        }
        
        # 3. News
        news_list = ticker.news
        recent_news = []
        if news_list:
            for n in news_list[:3]: # Limit to top 3 to save tokens
                recent_news.append({
                    "title": n.get("title"),
                    "publisher": n.get("publisher"),
                })
        
        return {
            "history_1mo": hist.to_csv(),
            "fundamentals": fundamentals,
            "news": recent_news
        }

    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None
