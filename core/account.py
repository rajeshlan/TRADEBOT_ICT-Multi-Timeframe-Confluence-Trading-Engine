import os
from dotenv import load_dotenv

# 1. Initialize Environment
# Ensures .env variables are available if this module is called standalone.
load_dotenv()

# --- 2. THE SINGLETON EXECUTOR ---
# ✅ IMPORT SHARED INSTANCE: We use the global executor defined in core.executor.
# This ensures we use the same connection and time-sync across the whole bot.
from core.executor import executor

# --- 3. ACCOUNT UTILITIES ---

def get_live_balance():
    """
    Fetches the current USDT wallet balance using the shared global executor.
    
    This function leverages the internal logic of BybitExecutor which handles:
    - Internal clock synchronization (_pre_sync).
    - API response parsing (finding USDT in the Unified account).
    - Throttling (prevents hitting the API more than once every 5 seconds).
    
    Returns:
        float: The total USDT balance. Returns 0.0 or the last cached 
               balance if the API is unreachable.
    """
    try:
        # We simply delegate the work to the executor's optimized method.
        balance = executor.get_balance()
        return balance

    except Exception as e:
        # Catch-all for unexpected local errors to prevent the bot from crashing.
        print(f"❌ [CORE_ACCOUNT] Unexpected Error: {e}")
        return 0.0