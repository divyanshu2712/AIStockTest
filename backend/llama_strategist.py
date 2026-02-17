import os
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
import pymongo
from groq import Groq
import yfinance as yf
from data_engine import ALL_MARKET_TICKERS, fetch_stock_data

# Load environment variables
load_dotenv()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Initialize Clients
client = Groq(api_key=GROQ_API_KEY)

# DB Connection
mongo_client = None
if MONGO_URI:
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI)
        print("Connected to MongoDB.")
    except Exception as e:
        print(f"MongoDB Connection Failed: {e}")

def fetch_portfolio(user_id="user_001"):
    """
    Fetches the user's current holdings and settings.
    """
    if not mongo_client:
        return {}, {}
    
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
        
        settings = user.get("settings", {}) if user else {}
        return portfolio, settings
    except Exception as e:
        print(f"Error fetching portfolio: {e}")
        return {}, {}

def analyze_with_llama(stock_data, holding=None, user_settings=None):
    """
    Sends data to Llama 3 (via Groq) for analysis.
    """
    
    # User Preferences Context
    risk_profile = user_settings.get("risk_profile", "Balanced") if user_settings else "Balanced"
    investment_period = user_settings.get("investment_period", "1 Month") if user_settings else "1 Month"
    expected_return = float(user_settings.get("expected_return", 15)) if user_settings else 15.0

    # Dynamic Strategy Instructions based on User/Return
    strategy_instruction = ""
    if expected_return >= 50:
        strategy_instruction = """
        **WARNING: AGGRESSIVE RETURN TARGET (>50%)**
        - You MUST identify High Beta / High Momentum stocks.
        - Prioritize Volatility and Breakouts over Stability.
        - ACCEPT higher risk. Look for "Multiplier" setups.
        """
    elif expected_return >= 20:
        strategy_instruction = """
        **GROWTH STRATEGY (20-50%)**
        - Look for strong fundamentals + upward price momentum.
        - Balance growth with reasonable valuation.
        """
    else:
        strategy_instruction = """
        **CONSERVATIVE / STEADY GROWTH (<20%)**
        - Prioritize Capital Preservation and steady uptrends.
        - Avoid high volatility. Look for Blue Chips.
        """

    # Portfolio Context
    holding_context = ""
    if holding:
        holding_context = f"""
        **PORTFOLIO CONTEXT**: 
        You currently HOLD {holding['qty']} shares. Avg Price: ₹{holding['avg_price']}.
        Current Price: ₹{stock_data['fundamentals']['current_price']}.
        Analyze if we should SELL (Take Profit/Stop Loss) or HOLD/BUY more.
        """
    else:
        holding_context = "**PORTFOLIO CONTEXT**: You do NOT own this stock."

    prompt = f"""
    You are 'Llama 4 Maverick', the Chief Investment Officer.
    
    **User Strategy Profile**:
    - Risk Tolerance: {risk_profile}
    - Time Horizon: {investment_period}
    - **Target Return**: {expected_return}%
    
    {strategy_instruction}
    
    {holding_context}
    
    **Analyze {stock_data['fundamentals']['symbol']}**:
    1. **Fundamentals**: P/E: {stock_data['fundamentals']['pe_ratio']}, Sector: {stock_data['fundamentals']['sector']}
    2. **News**: {json.dumps(stock_data['news'])}
    3. **Price Data (Last 1 Month)**:
    {stock_data['history_1mo']}
    
    **Objective**: 
    Provide a trading decision (BUY, SELL, WAIT) primarily based on the **User Strategy** above.
    
    **Output Format (JSON ONLY)**:
    {{
        "symbol": "{stock_data['fundamentals']['symbol']}",
        "decision": "BUY" or "SELL" or "WAIT" or "AVOID",
        "reasoning": "Brief explanation focused on the strategy (e.g., 'Matches aggressive growth target').",
        "sentiment_score": "Positive/Negative/Neutral"
    }}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial analyst AI. Output valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.3, # Increased slightly for creative strategy matching
            max_tokens=350,
            response_format={"type": "json_object"} 
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"   > Groq API Error: {e}")
        return None

def save_to_mongodb(strategy_data):
    if not mongo_client:
        return

    try:
        db = mongo_client["ai_hedge_fund"]
        collection = db["daily_strategy"]
        query = {"date": strategy_data["date"]}
        update = {"$set": strategy_data}
        result = collection.update_one(query, update, upsert=True)
        print(f"Strategy saved for {strategy_data['date']}.")
    except Exception as e:
        print(f"MongoDB Write Error: {e}")

if __name__ == "__main__":
    print("--- Llama 4 Maverick: Market Strategist (Nifty 50) ---")
    
    portfolio, settings = fetch_portfolio("user_001")
    watchlist = []
    
    # --- MARKET SCREENING PHASE ---
    print(f"\n[PHASE 1] Screening {len(ALL_MARKET_TICKERS)} stocks for high potential...")
    
    shortlisted_tickers = []
    
    # 1. Technical Screen (Simulated fast scan)
    # In a real app, we'd use a bulk downloader or database.
    # Here we check Volume and Price change to filter "Active" stocks.
    
    # Limit scan to save time, BUT shuffle first to avoid "Alphabetical Bias"
    # This ensures we get a random sample of the market every time.
    import random
    random.shuffle(ALL_MARKET_TICKERS)
    
    scan_limit = 50 
    
    # --- CRITICAL: Always analyze current holdings for Exit Signals ---
    current_holdings = list(portfolio.keys())
    # Add holdings to the shortlist first
    shortlisted_tickers = current_holdings.copy()
    print(f"  > Added {len(current_holdings)} portfolio stocks for Exit Analysis: {current_holdings}")
    
    print(f"  > Scanning Random {scan_limit} of {len(ALL_MARKET_TICKERS)} tickers (Advanced TA)...")

    for ticker in ALL_MARKET_TICKERS[:scan_limit]:
        try:
            # Fetch 3 months for 50-day SMA
            t = yf.Ticker(ticker)
            hist = t.history(period="3mo")
            
            if len(hist) > 50:
                # --- Advanced Technical Indicators ---
                
                # 1. RSI (14)
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                
                # 2. SMA (50) - Trend
                sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
                current_price = hist['Close'].iloc[-1]
                
                # 3. Volume Spike (vs 20-day Avg)
                avg_vol = hist['Volume'].rolling(window=20).mean().iloc[-1]
                current_vol = hist['Volume'].iloc[-1]
                vol_spike = current_vol > (1.5 * avg_vol)
                
                # --- Screening Criteria ---
                reason = []
                
                # A. Portfolio Hold (Always Check)
                if ticker in portfolio:
                    reason.append("Existing Holding")
                
                # B. Oversold Dip (RSI < 30)
                elif rsi < 30:
                    reason.append(f"Oversold (RSI {rsi:.1f})")
                    
                # C. Momentum Breakout (Price > SMA50 AND Vol Spike)
                elif current_price > sma_50 and vol_spike:
                    reason.append(f"Momentum Breakout (Vol Spike, >SMA50)")
                    
                # D. Strong Uptrend (Price > SMA50 AND RSI 50-70)
                elif current_price > sma_50 and 50 < rsi < 70:
                    reason.append(f"Strong Uptrend (RSI {rsi:.1f})")
                
                if reason:
                    shortlisted_tickers.append(ticker)
                    print(f"  > Found Candidate: {ticker} | Matches: {', '.join(reason)}")
                    
        except Exception as e:
            # print(f"Error screening {ticker}: {e}")
            continue
            
    print(f"\n[PHASE 2] AI Deep Analysis on {len(shortlisted_tickers)} Candidates...")
    
    for ticker in shortlisted_tickers:
        print(f"\nAnalyzing {ticker}...")
        data = fetch_stock_data(ticker)
        
        if data:
            holding = portfolio.get(ticker)
            analysis_json = analyze_with_llama(data, holding, settings)
            
            if analysis_json:
                try:
                    analysis = json.loads(analysis_json)
                    print(f"  > Decision: {analysis['decision']} | {analysis['reasoning']}")
                    if analysis['decision'] in ["BUY", "SELL"]:
                        watchlist.append(analysis)
                except:
                    print("  > JSON Parse Error")
            
            # Groq Rate Limit handling
            time.sleep(2) 
            
    # Save Strategy
    today_date = datetime.now().strftime('%Y-%m-%d')
    strategy = {
        "date": today_date,
        "watchlist": watchlist,
        "generated_at": datetime.now().isoformat()
    }
    
    save_to_mongodb(strategy)
    print("\n--- Strategy Generation Complete ---")
