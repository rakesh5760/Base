import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time
from datetime import datetime

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

FULL_FROM = f"{FROM_DATE}T{FROM_TIME}{UTC_OFFSET}" if FROM_DATE else None
FULL_TO = f"{TO_DATE}T{TO_TIME}{UTC_OFFSET}" if TO_DATE else None

MAX_PAGES = int(os.getenv("MAX_PAGES", 20))
EXTRACTION_THRESHOLD = int(os.getenv("EXTRACTION_THRESHOLD", 500))

def export_to_excel(all_data):
    print(f"\n--- Starting Data Extraction to Excel ---")
    
    master_transactions = []
    erc20_data = []
    nft_data = []
    other_data = []

    for tx in all_data:
        timestamp = tx.get("block_timestamp")
        tx_hash = tx.get("hash")
        summary = tx.get("summary")
        category = tx.get("category")
        from_addr = tx.get("from_address")
        to_addr = tx.get("to_address")
        
        # 1. Transactions (Master List - one row per hash)
        master_transactions.append({
            "Timestamp": timestamp,
            "Hash": tx_hash,
            "From": from_addr,
            "To": to_addr,
            "Category": category,
            "Summary": summary
        })

        # 2. Token Transfers (ERC-20)
        if tx.get("erc20_transfers"):
            for move in tx["erc20_transfers"]:
                erc20_data.append({
                    "Timestamp": timestamp,
                    "Hash": tx_hash,
                    "From": move.get("from_address"),
                    "To": move.get("to_address"),
                    "Token": move.get("token_name"),
                    "Symbol": move.get("token_symbol"),
                    "Value": move.get("value_decimal"),
                    "Summary": summary
                })

        # 3. NFT Transfers
        if tx.get("nft_transfers"):
            for move in tx["nft_transfers"]:
                nft_data.append({
                    "Timestamp": timestamp,
                    "Hash": tx_hash,
                    "From": move.get("from_address"),
                    "To": move.get("to_address"),
                    "Collection": move.get("token_name"),
                    "Token ID": move.get("token_id"),
                    "Summary": summary
                })

        # 4. Other Transactions (Filter based on special categories)
        special_categories = ['contract interaction', 'approval', 'token swap', 'mint', 'burn']
        if any(cat in str(category).lower() for cat in special_categories):
            other_data.append({
                "Timestamp": timestamp,
                "Hash": tx_hash,
                "Type": category,
                "Summary": summary
            })

    # Save to Excel
    filename = f"extract_{WALLET_ADDRESS[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        pd.DataFrame(master_transactions).to_writer_sheet(writer, "Transactions")
        pd.DataFrame(erc20_data).to_writer_sheet(writer, "Token Transfers (ERC-20)")
        pd.DataFrame(nft_data).to_writer_sheet(writer, "NFT Transfers")
        pd.DataFrame(other_data).to_writer_sheet(writer, "Other Transactions")

    print(f"SUCCESS: Data saved to {filename}")

def to_writer_sheet(df, writer, sheet_name):
    if df.empty:
        pd.DataFrame({"Info": ["No data found in this category"]}).to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        df.to_excel(writer, sheet_name=sheet_name, index=False)

pd.DataFrame.to_writer_sheet = to_writer_sheet

def get_transaction_count():
    if not MORALIS_API_KEY or "YOUR_API_KEY" in MORALIS_API_KEY:
        print("Error: MORALIS_API_KEY not correctly set")
        return

    url = f"https://deep-index.moralis.io/api/v2.2/wallets/{WALLET_ADDRESS}/history"
    headers = {"accept": "application/json", "X-API-Key": MORALIS_API_KEY}
    params = {"chain": CHAIN, "from_date": FULL_FROM, "to_date": FULL_TO, "limit": 100, "order": "DESC"}
    
    total_count = 0
    all_results = []
    page_number = 1
    cursor = None
    
    print(f"--- Starting Transaction Search ---")
    print(f"Address: {WALLET_ADDRESS}")
    print(f"Range:   {FULL_FROM} to {FULL_TO}")
    print("---------------------------------")

    try:
        while True:
            if cursor: params["cursor"] = cursor
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            transactions = data.get("result", [])
            total_count += len(transactions)
            all_results.extend(transactions)
            
            print(f"Page {page_number}: Found {len(transactions)} txs. (Total: {total_count})")
            
            cursor = data.get("cursor")
            if not cursor or (MAX_PAGES > 0 and page_number >= MAX_PAGES):
                break
            page_number += 1
            time.sleep(0.05)
            
    except Exception as e:
        print(f"Error: {e}")

    print("---------------------------------")
    print(f"Search Completed! Total: {total_count}")

    if total_count > 0 and total_count <= EXTRACTION_THRESHOLD:
        export_to_excel(all_results)
    elif total_count > EXTRACTION_THRESHOLD:
        print(f"NOTE: Count ({total_count}) exceeds Extraction Threshold ({EXTRACTION_THRESHOLD}). No Excel file generated.")

if __name__ == "__main__":
    get_transaction_count()
