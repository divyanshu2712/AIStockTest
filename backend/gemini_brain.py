import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import pymongo
from google import genai
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MONGO_URI = os.getenv("MONGO_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Clients
client = genai.Client(api_key=GEMINI_API_KEY)

# DB Connection (Global)
mongo_client = None
if MONGO_URI:
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI)
        print("Connected to MongoDB.")
    except Exception as e:
        print(f"MongoDB Connection Failed: {e}")

def fetch_portfolio(user_id="user_001"):
    """
    Fetches the user's current holdings to provide context to the AI.
    """
    if not mongo_client:
        return {}
    
    try:
        db = mongo_client["ai_hedge_fund"]
        user = db["users"].find_one({"_id": user_id})
        portfolio = {}
        if user and "portfolio" in user:
            for item in user["portfolio"]:
                portfolio[item["symbol"]] = {
                    "qty": item["qty"],
                    "avg_price": item.get("avg_price", 0)
                }
        return portfolio
    except Exception as e:
        print(f"Error fetching portfolio: {e}")
        return {}

def fetch_stock_data(ticker_symbol):
    """
    Fetches 1-month and 1-week OHLC data, fundamental info, and news for a specific stock.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # 1. Price History (1 Month for daily trend, 1 Week for short term)
        hist_1mo = ticker.history(period="1mo")
        hist_1wk = ticker.history(period="5d") # 1 week (5 trading days)
        
        # 2. Fundamentals
        info = ticker.info
        fundamentals = {
            "symbol": ticker_symbol,
            "current_price": info.get("currentPrice"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "debt_to_equity": info.get("debtToEquity"),
            "profit_margins": info.get("profitMargins"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "long_business_summary": info.get("longBusinessSummary") # Company Background
        }
        
        # 3. News (Specific to the company)
        news_list = ticker.news
        recent_news = []
        if news_list:
            for n in news_list[:5]: # Top 5 news items
                recent_news.append({
                    "title": n.get("title"),
                    "publisher": n.get("publisher"),
                    "link": n.get("link"),
                    "relatedTickers": n.get("relatedTickers")
                })
        
        return {
            "history_1mo": hist_1mo.to_csv(),
            "history_1wk": hist_1wk.to_csv(),
            "fundamentals": fundamentals,
            "news": recent_news
        }

    except Exception as e:
        print(f"Error fetching data for {ticker_symbol}: {e}")
        return None


def analyze_with_gemini(stock_data, holding=None):
    """
    Sends data to Gemini 1.5 Flash for analysis (Complete Version).
    """
    
    # Context string about holdings
    holding_context = ""
    if holding:
        holding_context = f"""
        **PORTFOLIO CONTEXT**: 
        You currently HOLD {holding['qty']} shares of this stock.
        Your Average Buy Price was ₹{holding['avg_price']}.
        Current Price is roughly ₹{stock_data['fundamentals']['current_price']}.
        
        Determine if you should SELL to take profit (if profitable) or cut losses, 
        or HOLD for more gains, or BUY more.
        """
    else:
        holding_context = "**PORTFOLIO CONTEXT**: You do NOT own this stock. Consider primarily BUY or WAIT."

    # 1. DEFINE THE PROMPT (This was missing before)
    prompt = f"""
    You are the Chief Investment Officer (CIO) of an AI Hedge Fund.
    
    **Context**: All monetary values are in Indian Rupees (₹).
    {holding_context}
    
    Analyze the following data for {stock_data['fundamentals']['symbol']} to determine the action.
    
    1. **Company Background**: {stock_data['fundamentals']['long_business_summary']}
    2. **Fundamentals**:
       - P/E Ratio: {stock_data['fundamentals']['pe_ratio']}
       - Debt-to-Equity: {stock_data['fundamentals']['debt_to_equity']}
       - Profit Margins: {stock_data['fundamentals']['profit_margins']}
    3. **Price History (1 Month CSV)**:
    {stock_data['history_1mo']}
    
    4. **Recent News**:
    {json.dumps(stock_data['news'], indent=2)}
    
    **Task**:
    - Analyze the price trend (Uptrend/Downtrend/Base).
    - Evaluate fundamentals (Healthy/Overvalued/Risky).
    - Assess news sentiment (Positive/Negative/Neutral).
    - DECIDE: BUY, SELL, WAIT, or AVOID.
    
    **Output Format (JSON strictly)**:
    {{
        "symbol": "{stock_data['fundamentals']['symbol']}",
        "decision": "BUY" or "SELL" or "WAIT" or "AVOID",
        "reasoning": "Concise explanation. If SELLING, mention profit/loss logic.",
        "technical_trend": "Uptrend" or "Downtrend" or "Consolidation",
        "fundamental_health": "Strong" or "Weak" or "Mixed",
        "sentiment_score": "Positive" or "Negative" or "Neutral"
    }}
    """
    
    # 2. SELECT MODEL
    # Confirmed working model from list_models.py
    model_name = "gemini-3-flash-preview"
    
    print(f"   > Sending request to {model_name}...") 

    # 3. CALL API WITH RETRY LOGIC
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json' 
                }
                
            )
            return response.text

        except Exception as e:
            print(f"   > CRITICAL ERROR (Attempt {attempt+1}): {e}")
            
            # If Rate Limit, wait longer
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("   > Rate limit hit. Sleeping 20s...")
                time.sleep(20)
                continue
            
            # If other error, stop trying
            return None

    return None


def save_to_mongodb(strategy_data):
    """
    Saves the daily strategy to MongoDB.
    """
    if not MONGO_URI:
        print("MONGO_URI not set. Skipping DB write.")
        print(json.dumps(strategy_data, indent=2))
        return

    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client["ai_hedge_fund"]
        collection = db["daily_strategy"]
        
        # Check if strategy already exists for today
        query = {"date": strategy_data["date"]}
        update = {"$set": strategy_data}
        
        result = collection.update_one(query, update, upsert=True)
        print(f"Strategy saved to MongoDB using URI: {MONGO_URI[:10]}... (Upserted: {result.upserted_id is not None})")
        client.close()
    except Exception as e:
        print(f"MongoDB Error: {e}")

import time

if __name__ == "__main__":
    print("--- Gemini 2.0 Pro: Daily Review Strategy ---")
    
    # Target Watchlist (Indian Market Simulated)
    tickers = ["RELIANCE.NS", "TATAPOWER.NS", "HDFCBANK.NS", "INFY.NS", "TCS.NS", "ADANIENT.NS", "BHARTIARTL.NS", "ICICIBANK.NS", "SBIN.NS"] 
    
    # Fetch User Portfolio
    portfolio = fetch_portfolio("user_001")
    if portfolio:
        print(f"Loaded Portfolio: {len(portfolio)} items.")
    
    watchlist = []
    
    for ticker in tickers:
        print(f"\nProcessing {ticker}...")
        data = fetch_stock_data(ticker)
        
        if data:
            # 1. Quick Filter: Only analyze if data is valid
            print(f"  > Data fetched. Fundamentals: P/E={data['fundamentals'].get('pe_ratio')}")
            
            # 2. ASK GEMINI
            # Check if we hold this stock
            holding = portfolio.get(ticker)
            
            print("  > Asking Gemini...")
            analysis_json_str = analyze_with_gemini(data, holding)
            
            # Rate Limit Delay (Aggressive for free tier)
            print("  > Waiting 30s to respect API rate limits...")
            time.sleep(30)
            
            if analysis_json_str:
                try:
                    # Clean the response (remove markdown code blocks if present)
                    clean_json = analysis_json_str.replace("```json", "").replace("```", "").strip()
                    analysis = json.loads(clean_json)
                    
                    if analysis.get("decision") == "BUY":
                        print(f"  >>> GEMINI SAYS BUY: {analysis.get('reasoning')}")
                        watchlist.append(analysis)
                    elif analysis.get("decision") == "SELL":
                        print(f"  >>> GEMINI SAYS SELL: {analysis.get('reasoning')}")
                        watchlist.append(analysis) # Add to strategy so Trader can execute
                    else:
                        print(f"  > Gemini says {analysis.get('decision')}: {analysis.get('reasoning')}")
                except json.JSONDecodeError:
                    print(f"  > Error parsing Gemini response: {analysis_json_str[:50]}...")
            else:
                 print("  > Gemini returned no response.")
        else:
            print("  > Failed to fetch data.")

    # Save Daily Strategy
    if watchlist:
        daily_strategy = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "market_mood": "NEUTRAL", # TODO: Implement broad market analysis (e.g., Nifty 50 trend)
            "watchlist": watchlist
        }
        
        print(f"\nGeneratin final strategy for {len(watchlist)} stocks...")
        save_to_mongodb(daily_strategy)
    else:
        print("\nNo stocks selected for today's watchlist.")
