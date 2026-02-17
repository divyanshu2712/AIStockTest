from flask import Flask, jsonify, request
from flask_cors import CORS
import pymongo
import os
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

MONGO_URI = os.getenv("MONGO_URI")

def get_db():
    if not MONGO_URI:
        return None
    try:
        client = pymongo.MongoClient(MONGO_URI)
        return client["ai_hedge_fund"]
    except Exception as e:
        print(f"DB Error: {e}")
        return None

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    if db is None:
        return jsonify({"error": "DB not connected"}), 500
    
    user = db["users"].find_one({"_id": "user_001"})
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    # Calculate Portfolio Value & Enrich Holdings with Live Data
    portfolio_value = 0
    holdings = user.get("portfolio", [])
    enriched_holdings = []

    for h in holdings:
        qty = h.get("qty", 0)
        avg_price = h.get("avg_price", 0)
        
        try:
            # Fetch real-time price
            ticker = yf.Ticker(h["symbol"])
            current_price = ticker.fast_info.last_price
            
            # Calculate Value & PnL
            market_value = qty * current_price
            portfolio_value += market_value
            
            # Add live data to holding object for UI
            h_copy = h.copy()
            h_copy["current_price"] = current_price
            h_copy["market_value"] = market_value
            h_copy["pnl"] = market_value - (qty * avg_price)
            h_copy["pnl_percent"] = ((current_price - avg_price) / avg_price) * 100 if avg_price > 0 else 0
            enriched_holdings.append(h_copy)
            
        except Exception as e:
             # Fallback to cost basis
             # print(f"Price fetch failed for {h['symbol']}: {e}")
             val = qty * avg_price
             portfolio_value += val
             h_copy = h.copy()
             h_copy["current_price"] = avg_price
             enriched_holdings.append(h_copy)
    
    total_equity = user.get("balance", 0) + portfolio_value
    
    return jsonify({
        "balance": user.get("balance"),
        "capital": user.get("capital"), # Initial capital
        "portfolio_value": portfolio_value,
        "total_equity": total_equity,
        "settings": user.get("settings", {}), # Return full settings
        "holdings_count": len(enriched_holdings),
        "portfolio": enriched_holdings # Return enriched list
    })

@app.route('/api/trades', methods=['GET'])
def get_trades():
    db = get_db()
    if db is None:
        return jsonify({"error": "DB not connected"}), 500
        
    trades = list(db["trade_logs"].find().sort("timestamp", -1).limit(50))
    for t in trades:
        t["_id"] = str(t["_id"]) # Convert ObjectId to string
        
    return jsonify(trades)

@app.route('/api/toggle_status', methods=['POST'])
def toggle_status():
    db = get_db()
    if db is None:
        return jsonify({"error": "DB not connected"}), 500
    
    user = db["users"].find_one({"_id": "user_001"})
    current_status = user.get("settings", {}).get("status", "ACTIVE")
    new_status = "PAUSED" if current_status == "ACTIVE" else "ACTIVE"
    
    db["users"].update_one(
        {"_id": "user_001"},
        {"$set": {"settings.status": new_status}}
    )
    
    return jsonify({"status": new_status})
@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    db = get_db()
    if db is None:
        return jsonify({"error": "DB not connected"}), 500
    
    data = request.json
    # Expected: { "balance": 10000, "expected_return": 15, "period": "1 Month" }
    
    update_data = {}
    if "balance" in data:
        update_data["balance"] = float(data["balance"])
        update_data["capital"] = float(data["balance"]) # Reset capital basis
        update_data["portfolio"] = [] # Clear portfolio
        db["trade_logs"].delete_many({}) # Clear history
    
    if "expected_return" in data or "period" in data:
        settings_update = {}
        if "expected_return" in data: settings_update["settings.expected_return"] = data["expected_return"]
        if "period" in data: settings_update["settings.investment_period"] = data["period"]
        if "risk" in data: settings_update["settings.risk_profile"] = data["risk"]
        
        # Reset Start Date on new strategy
        from datetime import datetime
        settings_update["settings.start_date"] = datetime.now().isoformat()
        
        db["users"].update_one({"_id": "user_001"}, {"$set": settings_update})

    if update_data:
        # If Balance reset, also reset start date
        from datetime import datetime
        update_data["settings.start_date"] = datetime.now().isoformat()
        db["users"].update_one({"_id": "user_001"}, {"$set": update_data})
        
    return jsonify({"message": "Settings updated"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
