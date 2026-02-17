from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("MONGO_URI not set.")
else:
    try:
        client = MongoClient(MONGO_URI)
        db = client["ai_hedge_fund"]
        
        # Check User
        user = db["users"].find_one({"_id": "user_001"})
        print(f"User Balance: {user.get('balance')}")
        print(f"User Portfolio: {user.get('portfolio')}")
        
        # Check Strategies
        strategies = list(db["daily_strategy"].find())
        print(f"Strategies Count: {len(strategies)}")
        if strategies:
            print(f"Latest Strategy Date: {strategies[-1]['date']}")
            print(f"Watchlist Size: {len(strategies[-1].get('watchlist', []))}")
        else:
            print("No strategies found.")
            
    except Exception as e:
        print(f"Error: {e}")
