import os
import time
import json
import pymongo
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Clients
groq_client = Groq(api_key=GROQ_API_KEY)
# client = pymongo.MongoClient(MONGO_URI)
# db = client["ai_hedge_fund"]

def get_db_connection():
    if not MONGO_URI:
        return None
    try:
        client = pymongo.MongoClient(MONGO_URI)
        return client["ai_hedge_fund"]
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

def fetch_real_time_data(ticker_symbol):
    """
    Fetches real-time price and calculates RSI.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # We need recent history to calculate RSI (at least 14 periods)
        # Fetching 5 days of 15m or 1h data
        hist = ticker.history(period="5d", interval="15m")
        
        if hist.empty:
            return None
        
        # Calculate RSI (14 period)
        hist.ta.rsi(close='Close', length=14, append=True)
        
        current_price = hist['Close'].iloc[-1]
        current_rsi = hist['RSI_14'].iloc[-1]
        
        return {
            "price": current_price,
            "rsi": current_rsi,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching RT data for {ticker_symbol}: {e}")
        return None

def check_breaking_news(ticker_symbol):
    """
    Fetches latest news and uses Llama 4 (Groq) to check for FATAL news.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        news_list = ticker.news
        
        # Filter news from the last 2 hours (approx, using simple logic)
        # Note: yfinance news doesn't always have exact timestamp in easy format, 
        # but the list is sorted by recency. We'll take the top 3.
        latest_news = news_list[:3] 
        
        if not latest_news:
            return "CLEAR"
            
        news_text = "\n".join([f"- {n.get('title', 'No Title')}" for n in latest_news])
        
        prompt = f"""
        You are a Risk Manager.
        
        Review the following breaking news for {ticker_symbol}:
        {news_text}
        
        Is there any 'FATAL' news? (e.g., Bankruptcy, CEO Fraud, Massive Lawsuit, earnings disaster).
        
        Reply strictly with "FATAL" or "CLEAR".
        """
        
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", # Upgraded to 70B "Maverick" level
        )
        
        decision = completion.choices[0].message.content.strip().upper()
        return "FATAL" if "FATAL" in decision else "CLEAR"
        
    except Exception as e:
        print(f"News Check Error: {e}")
        return "CLEAR" # Default to clear if check fails, or maybe "RISK"

def execute_trade(db, user_id, symbol, action, price, qty, reason):
    """
    Executes a paper trade.
    """
    users_col = db["users"]
    logs_col = db["trade_logs"]
    
    user = users_col.find_one({"_id": user_id})
    if not user:
        print("User not found.")
        return
    
    cost = price * qty
    
    if action == "BUY":
        if user["balance"] >= cost:
            # Deduct Balance
            users_col.update_one({"_id": user_id}, {"$inc": {"balance": -cost}})
            # Add to Holdings
            users_col.update_one(
                {"_id": user_id, "portfolio.symbol": symbol},
                {"$inc": {"portfolio.$.qty": qty}},
                upsert=False
            )
            # If not exists, push new
            users_col.update_one(
                {"_id": user_id, "portfolio.symbol": {"$ne": symbol}},
                {"$push": {"portfolio": {"symbol": symbol, "qty": qty, "avg_price": price}}}
            )
            print(f"Executed BUY: {symbol} @ {price}")
        else:
            print(f"Insufficient funds for {symbol}")
            return

    elif action == "SELL":
        # Check holdings
        holding = next((p for p in user.get("portfolio", []) if p["symbol"] == symbol), None)
        if holding and holding["qty"] >= qty:
            # Add Balance
            users_col.update_one({"_id": user_id}, {"$inc": {"balance": cost}})
            # Reduce Holdings
            users_col.update_one(
                {"_id": user_id, "portfolio.symbol": symbol},
                {"$inc": {"portfolio.$.qty": -qty}}
            )
            # Remove if qty 0 (Optional, but cleaner)
            users_col.update_one(
                {"_id": user_id},
                {"$pull": {"portfolio": {"symbol": symbol, "qty": {"$lte": 0}}}}
            )
            print(f"Executed SELL: {symbol} @ {price} (Profit/Loss realized)")
        else:
            print(f"Cannot SELL {symbol}: Not enough qty.")
            return

    # Log Trade
    log = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": action,
        "price": price,
        "qty": qty,
        "ai_reason": reason
    }
    logs_col.insert_one(log)

if __name__ == "__main__":
    print("--- Llama 4 Maverick: Context-Aware Trader ---")
    
    db = get_db_connection()
    if db is None:
        print("No DB Connection. Exiting.")
        exit()
        
    # 1. Load Daily Strategy
    today_str = datetime.now().strftime("%Y-%m-%d")
    strategy = db["daily_strategy"].find_one({"date": today_str})
    
    # --- CHECK INVESTMENT PERIOD ---
    user = db["users"].find_one({"_id": "user_001"})
    settings = user.get("settings", {})
    start_date_str = settings.get("start_date")
    period_str = settings.get("investment_period", "1 Month")
    
    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        
        # Robust parser for "X Unit(s)" (e.g., "6 Months", "2 Weeks")
        try:
            import re
            match = re.search(r"(\d+)", period_str)
            qty = int(match.group(1)) if match else 1
            
            multiplier = 1 # Default to Days
            if "Year" in period_str: multiplier = 365
            elif "Month" in period_str: multiplier = 30
            elif "Week" in period_str: multiplier = 7
            
            days_limit = qty * multiplier
            
        except Exception as e:
            print(f"Error parsing period '{period_str}': {e}")
            days_limit = 30 # Default safety
        
        elapsed = datetime.now() - start_date
        if elapsed.days >= days_limit:
            print(f"!!! INVESTMENT PERIOD ENDED ({period_str} | {days_limit} days) !!!")
            print(f"Elapsed: {elapsed.days} days. Trading HALTED.")
            print("Please reset your settings or start a new period to continue.")
            exit()
        else:
            print(f"Investment Day: {elapsed.days + 1}/{days_limit} ({period_str})")

    if not strategy:
        print(f"No strategy found for {today_str}. Run llama_strategist.py first.")
        # Fallback or exit
        # for demo purposes, let's assume we have a watchlist or exit
        exit()
        
    watchlist = strategy.get("watchlist", [])
    print(f"Loaded Watchlist: {[item['symbol'] for item in watchlist]}")
    
    # 2. Iterate and Trade
    for item in watchlist:
        symbol = item["symbol"]
        gemini_reason = item["reasoning"]
        
        print(f"\nChecking {symbol}...")
        
        # Real-time Data
        rt_data = fetch_real_time_data(symbol)
        if not rt_data:
            print("  > No data.")
            continue
            
        rsi = rt_data["rsi"]
        price = rt_data["price"]
        print(f"  > Price: {price}, RSI: {rsi:.2f}")
        
        # Logic: Buy if Gemini said BUY AND RSI is favorable
        # Logic: Sell if Gemini said SELL
        
        decision = item.get("decision", "BUY") 
        
        if decision == "SELL":
             print(f"  >>> LLAMA SIGNAL: SELL ({gemini_reason})")
             # Execute SELL immediately (or check RSI for 'overbought' confirmation if desired)
             qty = 5 # Default sell qty, should be dynamic
             execute_trade(db, "user_001", symbol, "SELL", price, qty, f"Llama Take Profit: {gemini_reason[:20]}...")

        elif decision == "BUY":
            # Dynamic RSI Threshold based on User Risk
            rsi_limit = 40 # Default Conservative
            if settings.get("risk_profile") == "Aggressive":
                rsi_limit = 70 # Buy momentum
            elif settings.get("risk_profile") == "Balanced":
                rsi_limit = 55
            
            # Check RSI
            if rsi < rsi_limit: 
                print(f"  > Technical Setup VALID (RSI {rsi:.1f} < {rsi_limit}).")
                
                # News Check
                news_status = check_breaking_news(symbol)
                print(f"  > News Status: {news_status}")
                
                if news_status == "CLEAR":
                    print("  >>> TRIGGERING BUY!")
                    
                    # Dynamic Quantity Calculation
                    # Invest up to 20% of balance per trade, or at least 1 share
                    # But if balance is small (like 1000), maybe invest 50% or 100% for testing?
                    # Let's use 25% of *remaining* balance per trade to diversify slightly
                    
                    user_balance = user.get("balance", 0)
                    allocatable_amount = user_balance * 0.95 # Keep 5% buffer
                    
                    # If this is the only trade, we might want to use more.
                    # For now, let's max out at 1 share minimum.
                    
                    target_investment = allocatable_amount / 3 # Target 3 stocks approx
                    if target_investment < price:
                         target_investment = allocatable_amount # Try to buy at least one using full balance if needed
                    
                    qty = int(target_investment // price)
                    
                    if qty > 0:
                        execute_trade(db, "user_001", symbol, "BUY", price, qty, f"Llama: {gemini_reason[:20]}... | RSI: {rsi:.1f}")
                    else:
                        print(f"  > Insufficient balance to buy 1 share (Price: {price}, Bal: {user_balance})")
                else:
                    print("  > Trade BLOCKED by negative news.")
            else:
                print(f"  > RSI too high ({rsi:.1f} >= {rsi_limit}). Waiting for dip.")
    
    print("\nTrading cycle complete.")
