import os
import time
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Load environment variables for secure API access
load_dotenv()

class BybitExecutor:
    """
    Bybit V5 Executor: Production-Grade Hard Sync Version.
    Calculates and applies a time offset to the internal pybit engine
    to ensure local clock drift never causes signature rejections.
    """

    def __init__(self, api_key=None, api_secret=None):
        # 1. Credentials Setup
        self.api_key = api_key or os.getenv("BYBIT_API_KEY")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET")

        # 2. Client Initialization
        # recv_window=20000 provides a 20-second safety buffer
        self.client = HTTP(
            testnet=False,
            api_key=self.api_key,
            api_secret=self.api_secret,
            recv_window=20000,
            force_retry=True,
            retry_codes={10002, 10001}
        )

        # 3. Initial Hard Sync
        self.sync_time()
        print("✅ Bybit Executor: Hard Sync Mode initialized.")

    def sync_time(self):
        """
        Calculates the millisecond difference between local time and Bybit time.
        Injects the offset directly into the pybit HTTP client.
        """
        try:
            res = self.client.get_server_time()
            # Convert server timeSecond to milliseconds
            server_ts = int(res["result"]["timeSecond"]) * 1000
            local_ts = int(time.time() * 1000)

            # Calculate drift
            offset = server_ts - local_ts

            # 🔥 CRITICAL: Update the pybit internal engine offset
            self.client._timestamp_offset = offset

            print(f"🕒 HARD SYNC | Offset: {offset} ms | Server Time matched.")
        except Exception as e:
            print(f"❌ Sync failed: {e}")

    def get_balance(self):
        """
        Retrieves USDT balance with a JIT time sync.
        """
        try:
            self.sync_time()  # Sync right before the call
            res = self.client.get_wallet_balance(accountType="UNIFIED")

            if res.get("retCode") != 0:
                print(f"❌ Balance API Error: {res.get('retMsg')}")
                return 0.0

            coins = res["result"]["list"][0]["coin"]
            for c in coins:
                if c["coin"] == "USDT":
                    return float(c["walletBalance"])

            return 0.0
        except Exception as e:
            print(f"❌ Balance Exception: {e}")
            return 0.0

    def place_market_order(self, symbol, side, qty):
        """
        Places a Market Order with a JIT time sync for maximum reliability.
        """
        formatted_side = "Buy" if side.upper() == "BUY" else "Sell"

        try:
            self.sync_time()  # 🔥 Force sync before placing order
            
            response = self.client.place_order(
                category="linear",
                symbol=symbol,
                side=formatted_side,
                orderType="Market",
                qty=str(qty),
                timeInForce="IOC"
            )
            return response
            
        except Exception as e:
            print(f"❌ [ORDER_FAIL] {symbol}: {e}")
            return None

    def get_positions(self, symbol):
        """
        Retrieves active positions using the current synced offset.
        """
        try:
            self.sync_time()
            return self.client.get_positions(
                category="linear",
                symbol=symbol
            )
        except Exception as e:
            print(f"❌ [FETCH_FAIL] {symbol}: {e}")
            return None