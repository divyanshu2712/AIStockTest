import os
import pymongo
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

def init_db():
    if not MONGO_URI:
        print("MONGO_URI not set.")
        return

    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client["ai_hedge_fund"]
        users_col = db["users"]
        
        # Check if user exists
        if users_col.find_one({"_id": "user_001"}):
            print("User already exists.")
        else:
            user_data = {
                "_id": "user_001",
                "capital": 1000,
                "balance": 1000,
                "settings": { "risk_mode": "AGGRESSIVE", "status": "ACTIVE" },
                "portfolio": [] 
            }
            users_col.insert_one(user_data)
            print("User 'user_001' created with 1000 INR capital.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    init_db()
