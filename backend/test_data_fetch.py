import yfinance as yf

def test_fetch(ticker_symbol):
    print(f"--- Testing {ticker_symbol} ---")
    ticker = yf.Ticker(ticker_symbol)
    
    # 1. History
    try:
        hist = ticker.history(period="1mo")
        print(f"History (Last 5 days):\n{hist.tail()}")
    except Exception as e:
        print(f"History Error: {e}")

    # 2. Info keys
    try:
        info = ticker.info
        print(f"Info Keys: {list(info.keys())[:5]}") # Print first 5 keys
        print(f"Current Price: {info.get('currentPrice')}")
    except Exception as e:
        print(f"Info Error: {e}")

if __name__ == "__main__":
    test_fetch("AAPL") 
    test_fetch("RELIANCE.NS")
