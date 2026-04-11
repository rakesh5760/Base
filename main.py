import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time
from datetime import datetime, timezone

# Load environment variables from .env file
load_dotenv()

MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "").lower()
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

# Specified Columns per Tab
COLS_NATIVE = ["Transaction Hash", "Action", "Block", "Age", "From", "To", "Amount", "Txn Fee"]
COLS_ERC20 = ["Transaction Hash", "Action", "Block", "Age", "From", "To", "Amount", "Token"]
COLS_NFT = ["Transaction Hash", "Action", "Block", "Age", "From", "To", "Type", "Item"]
COLS_OTHER = ["Source Transaction", "Age", "Source Token", "Destination Token", "Recipient Address", "Protocol"]

def calculate_age(timestamp_str):
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.days > 0: return f"{diff.days}d {diff.seconds // 3600}h ago"
        elif diff.seconds >= 3600: return f"{diff.seconds // 3600}h {(diff.seconds % 3600) // 60}m ago"
        elif diff.seconds >= 60: return f"{diff.seconds // 60}m ago"
        else: return "Just now"
    except: return ""

def export_to_excel(all_data):
    print(f"\n--- Generating Specialized Multi-Sheet Report ---")
    
    native_rows = []
    erc20_rows = []
    nft_rows = []
    other_rows = []

    for tx in all_data:
        timestamp = tx.get("block_timestamp")
        age = calculate_age(timestamp)
        tx_hash = tx.get("hash")
        summary = tx.get("summary")
        category = tx.get("category")
        block = tx.get("block_number")
        base_from = tx.get("from_address")
        base_to = tx.get("to_address")
        fee = tx.get("transaction_fee")
        top_value = tx.get("value_formatted", "0")
        
        # 1. Transactions (Master Log - include EVERY transaction once)
        native_rows.append({
            "Transaction Hash": tx_hash, "Action": summary, "Block": block, "Age": age, 
            "From": base_from, "To": base_to, "Amount": top_value, "Txn Fee": fee
        })

        # 2. Token Transfers (ERC-20)
        if tx.get("erc20_transfers"):
            for move in tx["erc20_transfers"]:
                erc20_rows.append({
                    "Transaction Hash": tx_hash, "Action": summary, "Block": block, "Age": age, 
                    "From": move.get("from_address"), "To": move.get("to_address"), 
                    "Amount": move.get("value_formatted"), 
                    "Token": f"{move.get('token_name')} ({move.get('token_symbol')})"
                })

        # 3. NFT Transfers
        if tx.get("nft_transfers"):
            for move in tx["nft_transfers"]:
                nft_rows.append({
                    "Transaction Hash": tx_hash, "Action": summary, "Block": block, 
                    "Age": age, "From": move.get("from_address"), "To": move.get("to_address"),
                    "Type": move.get("contract_type"), "Item": f"#{move.get('token_id')}"
                })

        # 4. Other Transactions (Specialized Catch-all for interactions)
        if category in ['token swap', 'contract interaction', 'approval', 'mint', 'burn', 'airdrop']:
            source_token = ""
            dest_token = ""
            protocol = "Direct Interaction"
            if "on " in str(summary): protocol = str(summary).split("on ")[-1]
            
            if category == "token swap" and tx.get("erc20_transfers"):
                for t in tx["erc20_transfers"]:
                    if t.get("from_address", "").lower() == WALLET_ADDRESS:
                        source_token = f"{t.get('value_formatted')} {t.get('token_symbol')}"
                    if t.get("to_address", "").lower() == WALLET_ADDRESS:
                        dest_token = f"{t.get('value_formatted')} {t.get('token_symbol')}"

            other_rows.append({
                "Source Transaction": tx_hash, "Age": age, "Source Token": source_token, 
                "Destination Token": dest_token, "Recipient Address": base_to, "Protocol": protocol
            })

    filename = f"specialized_extract_{WALLET_ADDRESS[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        pd.DataFrame(native_rows, columns=COLS_NATIVE).to_excel(writer, index=False, sheet_name="Transactions")
        pd.DataFrame(erc20_rows, columns=COLS_ERC20).to_excel(writer, index=False, sheet_name="Token Transfers (ERC-20)")
        pd.DataFrame(nft_rows, columns=COLS_NFT).to_excel(writer, index=False, sheet_name="NFT Transfers")
        pd.DataFrame(other_rows, columns=COLS_OTHER).to_excel(writer, index=False, sheet_name="Other Transactions")

    print(f"SUCCESS: Specialized workbook saved to {filename}")

def get_transaction_count():
    if not MORALIS_API_KEY: return
    url = f"https://deep-index.moralis.io/api/v2.2/wallets/{WALLET_ADDRESS}/history"
    headers = {"accept": "application/json", "X-API-Key": MORALIS_API_KEY}
    params = {"chain": CHAIN, "from_date": FULL_FROM, "to_date": FULL_TO, "limit": 100}
    
    total_count = 0
    all_results = []
    page_number = 1
    cursor = None
    
    print(f"\n--- Starting Transaction Search ---")
    try:
        while True:
            if cursor: params["cursor"] = cursor
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            transactions = data.get("result", [])
            total_count += len(transactions)
            all_results.extend(transactions)
            print(f"Page {page_number}: Found {len(transactions)} txs. (Total: {total_count})")
            cursor = data.get("cursor")
            if not cursor or (MAX_PAGES > 0 and page_number >= MAX_PAGES): break
            page_number += 1
            time.sleep(0.05)
    except Exception as e: print(f"Error: {e}")

    if 0 < total_count <= EXTRACTION_THRESHOLD:
        export_to_excel(all_results)
    else:
        print(f"Search Finished. Total: {total_count}")

if __name__ == "__main__":
    get_transaction_count()
