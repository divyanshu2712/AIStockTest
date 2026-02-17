from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key not found.")
else:
    client = genai.Client(api_key=api_key)
    model_id = "gemini-3-flash-preview"
    
    print(f"Testing model: {model_id}...")
    try:
        response = client.models.generate_content(
            model=model_id,
            contents="Explain how AI works in one sentence."
        )
        print("Success!")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
