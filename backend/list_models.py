from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key not found.")
else:
    # FIX 1: Assign the client to a variable
    client = genai.Client(api_key=api_key)
    
    try:
        print("Listing available models...")
        
        print("Iterating models...")
        for m in client.models.list():
            # Check if generateContent is supported (if attribute exists)
            methods = getattr(m, 'supported_generation_methods', [])
            if methods and 'generateContent' in methods:
                 print(f"- {m.name}")
            elif not methods:
                 # Fallback if attribute missing but it's a model
                 print(f"- {m.name} (Attributes unavailable)")

    except Exception as e:
        print(f"Error listing models: {e}")