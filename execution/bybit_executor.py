import os
import time
import requests
import hmac
import hashlib
import json
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Load environment variables for secure API access
load_dotenv()

class ServerTimeSync:
    """
    Helper utility to calculate and maintain the offset 
    between local system time and Bybit server time.
    """
    def __init__(self, client):
        self.client = client
        self.local_offset = 0
        self.refresh_offset()

    def refresh_offset(self):
        """Calculates the millisecond difference between local and server time."""
        try:
            res = self.client.get_server_time()
            server_time_ms = int(res.get("result", {}).get("timeSecond", 0)) * 1000
            if server_time_ms == 0:
                server_time_ms = int(res.get("time_now", 0)) * 1000 
            
            local_time_ms = int(time.time() * 1000)
            self.local_offset = server_time_ms - local_time_ms
            print(f"⏰ [TIME_SYNC] Clock Offset Detected: {self.local_offset}ms")
        except Exception as e:
            print(f"⚠️ [TIME_SYNC] Diagnostic sync failed: {e}")

    def now(self):
        """Returns the synchronized server time in milliseconds."""
        return int(time.time() * 1000) + self.local_offset

class BybitExecutor:
    """
    Bybit V5 Executor: Custom Signer Mode.
    Uses 'requests' for all private endpoints to ensure timestamp reliability.
    """

    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key or os.getenv("BYBIT_API_KEY")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET")
        self.base_url = "https://api.bybit.com"

        # Pybit kept ONLY for public/diagnostic data
        self.client = HTTP(testnet=False) 
        
        self.time_sync = ServerTimeSync(self.client)
        
        self._last_balance_call = 0
        self._cached_balance = 0.0

        print("✅ Bybit Executor: Full Custom Signer Mode active.")

    def _signed_request(self, method, endpoint, payload=None):
        """
        Generates V5 signatures and executes the request.
        """
        try:
            payload = payload or {}
            timestamp = str(self.time_sync.now())
            recv_window = "30000"

            if method == "GET":
                query_string = "&".join(f"{k}={v}" for k, v in sorted(payload.items()))
                param_str = timestamp + self.api_key + recv_window + query_string
            else:
                payload_json = json.dumps(payload)
                param_str = timestamp + self.api_key + recv_window + payload_json

            signature = hmac.new(
                bytes(self.api_secret, "utf-8"),
                param_str.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()

            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-SIGN-TYPE": "2",
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json"
            }

            url = self.base_url + endpoint

            if method == "GET":
                response = requests.get(url, headers=headers, params=payload, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=10)

            return response.json()

        except Exception as e:
            print(f"❌ Signed Request Error: {e}")
            return None

    def get_balance(self):
        """Fetches the real wallet balance for the Unified account."""
        current_time = time.time()
        if current_time - self._last_balance_call < 5:
            return self._cached_balance

        self._last_balance_call = current_time

        try:
            res = self._signed_request(
                "GET",
                "/v5/account/wallet-balance",
                {"accountType": "UNIFIED"}
            )

            if not res or res.get("retCode") != 0:
                return self._cached_balance

            coins = res["result"]["list"][0]["coin"]
            for c in coins:
                if c["coin"] == "USDT":
                    self._cached_balance = float(c["walletBalance"])
                    return self._cached_balance

            return self._cached_balance
        except Exception as e:
            return self._cached_balance

    def get_positions(self, symbol):
        """Fetch position details for a specific symbol."""
        try:
            return self._signed_request(
                "GET",
                "/v5/position/list",
                {"category": "linear", "symbol": symbol}
            )
        except Exception as e:
            print(f"❌ [FETCH_FAIL] {symbol}: {e}")
            return None

    def get_open_orders(self, symbol=None):
        """
        Fetch currently OPEN exchange orders.
        Used for pending-order reconciliation.
        """
        try:
            payload = {
                "category": "linear"
            }

            if symbol:
                payload["symbol"] = symbol

            return self._signed_request(
                "GET",
                "/v5/order/realtime",
                payload
            )

        except Exception as e:
            print(f"❌ [OPEN_ORDERS_FAIL] {symbol}: {e}")
            return None

    def get_all_positions(self):
        """
        Fetch ALL active linear positions from Bybit.
        Used by dashboard for authoritative exchange state.
        """
        try:
            response = self._signed_request(
                "GET",
                "/v5/position/list",
                {
                    "category": "linear",
                    "settleCoin": "USDT"
                }
            )

            if not response or response.get("retCode") != 0:
                print(f"❌ [POSITIONS_FAIL] {response.get('retMsg') if response else 'No response'}")
                return []

            positions = response.get("result", {}).get("list", [])

            live_positions = [
                p for p in positions
                if float(p.get("size", 0)) > 0
            ]

            return live_positions

        except Exception as e:
            print(f"❌ [ALL_POSITIONS_ERROR] {e}")
            return []

    def place_market_order(self, symbol, side, qty):
        """Executes a market order via the custom signer."""
        if qty <= 0:
            print(f"⚠️ [REJECTED] {symbol} Qty invalid.")
            return None

        try:
            payload = {
                "category": "linear",
                "symbol": symbol,
                "side": side.capitalize(),
                "orderType": "Market",
                "qty": str(qty),
                "timeInForce": "IOC"
            }

            response = self._signed_request("POST", "/v5/order/create", payload)

            if response and response.get("retCode") == 0:
                print(f"🚀 ORDER PLACED: {symbol} {side} {qty}")
            else:
                print(f"❌ ORDER FAILED: {response}")

            return response
        except Exception as e:
            print(f"❌ [ORDER_FAIL] {symbol}: {e}")
            return None 

    def set_trading_stop(self, symbol, stop_loss=None, take_profit=None):
        """
        Sets exchange-native TP/SL on an active position.
        """
        try:
            payload = {
                "category": "linear",
                "symbol": symbol,
                "tpslMode": "Full"
            }

            if stop_loss:
                payload["stopLoss"] = str(stop_loss)

            if take_profit:
                payload["takeProfit"] = str(take_profit)

            response = self._signed_request(
                "POST",
                "/v5/position/trading-stop",
                payload
            )

            if response and response.get("retCode") == 0:
                print(f"✅ TP/SL SET: {symbol}")
            else:
                print(f"❌ TP/SL FAILED: {response}")

            return response

        except Exception as e:
            print(f"❌ [TP_SL_FAIL] {symbol}: {e}")
            return None