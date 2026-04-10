import os
import requests
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
CHAIN = os.getenv("CHAIN", "base")
UTC_OFFSET = os.getenv("UTC_OFFSET", "Z")

# Combine Date and Time with Offset
FROM_DATE = os.getenv("FROM_DATE")
FROM_TIME = os.getenv("FROM_TIME", "00:00:00")
TO_DATE = os.getenv("TO_DATE")
TO_TIME = os.getenv("TO_TIME", "23:59:59")

# Create full timestamp strings (ISO 8601)
# Example: 2024-01-01T12:00:00+05:30
FULL_FROM = f"{FROM_DATE}T{FROM_TIME}{UTC_OFFSET}" if FROM_DATE else None
FULL_TO = f"{TO_DATE}T{TO_TIME}{UTC_OFFSET}" if TO_DATE else None

# Safety limit
MAX_PAGES = int(os.getenv("MAX_PAGES", 20))

def get_transaction_count():
    if not MORALIS_API_KEY or "YOUR_API_KEY" in MORALIS_API_KEY:
        print("Error: MORALIS_API_KEY not correctly set in .env")
        return

    if not WALLET_ADDRESS or "0x000" in WALLET_ADDRESS:
        print("Error: WALLET_ADDRESS not set in .env")
        return

    url = f"https://deep-index.moralis.io/api/v2.2/wallets/{WALLET_ADDRESS}/history"
    
    headers = {
        "accept": "application/json",
        "X-API-Key": MORALIS_API_KEY
    }
    
    params = {
        "chain": CHAIN,
        "from_date": FULL_FROM,
        "to_date": FULL_TO,
        "limit": 100,
        "order": "DESC"
    }
    
    total_count = 0
    page_number = 1
    cursor = None
    
    print(f"--- Starting Transaction Count ---")
    print(f"Address: {WALLET_ADDRESS}")
    print(f"Start:   {FULL_FROM}")
    print(f"End:     {FULL_TO}")
    print(f"Chain:   {CHAIN}")
    print(f"Offset:  {UTC_OFFSET}")
    print("---------------------------------")

    try:
        while True:
            if cursor:
                params["cursor"] = cursor
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            transactions = data.get("result", [])
            count_on_page = len(transactions)
            total_count += count_on_page
            
            print(f"Page {page_number}: Found {count_on_page} transactions. (Total: {total_count})")
            
            cursor = data.get("cursor")
            
            # Stop if no more pages
            if not cursor:
                break
            
            # Stop if we hit user-defined page limit
            if MAX_PAGES > 0 and page_number >= MAX_PAGES:
                print(f"--- Reached MAX_PAGES limit ({MAX_PAGES}) ---")
                break
                
            page_number += 1
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"Error: {e}")

    print("---------------------------------")
    print(f"COMPLETED!")
    print(f"Final Count for your local range: {total_count} transactions.")
    print(f"Total API Calls: {page_number}")

if __name__ == "__main__":
    get_transaction_count()
