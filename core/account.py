import os
import time
from dotenv import load_dotenv
from execution.bybit_executor import BybitExecutor

# 1. Initialize Environment
# We load the .env file here so that API keys are available for the executor.
load_dotenv()

# --- 2. THE SINGLETON EXECUTOR ---
# ✅ INITIALIZE ONCE: This is the global executor instance used by the whole bot.
# By importing 'executor' from this file, every other module shares the same connection.
executor = BybitExecutor(
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)

# --- 3. ACCOUNT UTILITIES ---

def get_live_balance():
    """
    Fetches the current USDT wallet balance using the shared global executor.
    
    Returns:
        float: The total USDT balance available in the Unified Trading Account.
        Returns 0.0 if the connection fails or USDT is not found.
    """
    try:
        # Requesting wallet balance for the Unified Account Type
        res = executor.client.get_wallet_balance(accountType="UNIFIED")
        
        # Check if the API call was successful (retCode 0 means success)
        if res and res.get("retCode") == 0:
            # Bybit UTA returns a list of account details; we access the first one
            account_list = res.get("result", {}).get("list", [])
            
            if not account_list:
                print("⚠️ [ACCOUNT] No account list found in balance response.")
                return 0.0

            coins = account_list[0].get("coin", [])
            
            # Loop through coins to find USDT
            for c in coins:
                if c.get("coin") == "USDT":
                    # 'walletBalance' is the total equity including unrealized PnL/Margin
                    balance = float(c.get("walletBalance", 0))
                    return balance
            
            print("⚠️ [ACCOUNT] USDT not found in coin list.")
        else:
            error_msg = res.get("retMsg", "Unknown Error")
            print(f"❌ [API ERROR] Could not fetch balance: {error_msg}")
            
        return 0.0

    except Exception as e:
        # Catch network timeouts or dictionary key errors
        print(f"❌ [CRITICAL] Balance Exception: {e}")
        return 0.0

# --- 4. EXPORT LOGIC ---
# This ensures that when other files do 'from core.account import executor',
# they get the already-configured object.