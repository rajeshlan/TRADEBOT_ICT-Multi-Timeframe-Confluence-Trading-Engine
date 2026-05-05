import os
from dotenv import load_dotenv
from execution.bybit_executor import BybitExecutor

# Load environment variables from .env
load_dotenv()

# ✅ SINGLETON INSTANCE
# This object is created once and shared across the entire system.
executor = BybitExecutor(
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)

print("✅ System Core: Shared Bybit Executor Initialized.")