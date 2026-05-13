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

# ✅ STEP 1 — ADD EXECUTION CONTEXT IMPORT
from core.execution_context import execution_context

class ServerTimeSync:
    """
    Utility to sync local clock with Bybit server time to avoid 
    timestamp errors during signed requests.
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
            print(f"⏰ [TIME_SYNC] Offset: {self.local_offset}ms")
        except Exception as e:
            print(f"⚠️ [TIME_SYNC] Failed: {e}")

    def now(self):
        """Returns the synchronized server time in milliseconds."""
        return int(time.time() * 1000) + self.local_offset

class BybitExecutor:
    """
    Bybit V5 Executor: Custom Signer Mode.
    Handles authentication and private endpoints with safety gating for LIVE mode.
    """

    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key or os.getenv("BYBIT_API_KEY")
        self.api_secret = api_secret or os.getenv("BYBIT_API_SECRET")
        self.base_url = "https://api.bybit.com"

        # Public client used only for diagnostic data (server time)
        self.client = HTTP(testnet=False) 
        self.time_sync = ServerTimeSync(self.client)
        
        self._last_balance_call = 0
        self._cached_balance = 0.0

        print("✅ Bybit Executor: Full Custom Signer Mode active.")

    def _signed_request(self, method, endpoint, payload=None):
        """
        Generates V5 signatures and executes the request via 'requests'.
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

    def get_positions(self, symbol=None):
        """Fetches raw positions. If symbol is None, returns all linear positions."""
        try:
            payload = {
                "category": "linear",
                "settleCoin": "USDT"
            }
            if symbol:
                payload["symbol"] = symbol

            response = self._signed_request("GET", "/v5/position/list", payload)
            return response if response else {}
            
        except Exception as e:
            print(f"❌ GET POSITIONS FAIL [{symbol if symbol else 'ALL'}]: {e}")
            return {}

    def get_all_positions(self):
        """
        Returns ONLY active open positions as a clean, standardized list.
        """
        try:
            MIN_POSITION_SIZE = 0.0001
            
            response = self.get_positions()
            raw_positions = response.get("result", {}).get("list", [])
            
            clean_positions = []

            for pos in raw_positions:
                try:
                    size = abs(float(pos.get("size", 0)))
                    if size > MIN_POSITION_SIZE:
                        unrealized = float(pos.get("unrealisedPnl", 0))
                        
                        clean_positions.append({
                            "symbol": pos.get("symbol"),
                            "side": pos.get("side"),
                            "size": size,
                            "avgPrice": float(pos.get("avgPrice", 0)),
                            "markPrice": float(pos.get("markPrice", 0)),
                            "liqPrice": pos.get("liqPrice"),
                            "unrealisedPnl": unrealized,
                            "positionValue": float(pos.get("positionValue", 0)),
                            "takeProfit": pos.get("takeProfit"),
                            "stopLoss": pos.get("stopLoss"),
                            "leverage": pos.get("leverage"),
                            "raw": pos
                        })
                except Exception as inner_e:
                    print(f"⚠️ POSITION PARSE FAIL: {inner_e}")

            return clean_positions
        except Exception as e:
            print(f"❌ [GET_ALL_POSITIONS_FAIL] {e}")
            return []

    def get_balance(self):
        """Fetches the real-time USDT Equity for the Unified account."""
        try:
            response = self._signed_request(
                "GET", 
                "/v5/account/wallet-balance", 
                {"accountType": "UNIFIED"}
            )
            if not response or response.get("retCode") != 0:
                return 0.0

            accounts = response.get("result", {}).get("list", [])
            if not accounts:
                return 0.0

            coins = accounts[0].get("coin", [])
            for coin in coins:
                if coin.get("coin") == "USDT":
                    return float(coin.get("equity", coin.get("walletBalance", 0)))
            return 0.0
        except Exception as e:
            print(f"❌ [BALANCE_FAIL] {e}")
            return 0.0

    def get_open_orders(self, symbol=None):
        """Fetches currently active orders (Limit, TP, SL)."""
        try:
            payload = {
                "category": "linear",
                "settleCoin": "USDT" 
            }
            if symbol:
                payload["symbol"] = symbol

            response = self._signed_request("GET", "/v5/order/realtime", payload)
            
            if not response or response.get("retCode") != 0:
                return []
                
            return response if response else {}
        except Exception as e:
            print(f"❌ [OPEN_ORDERS_FAIL] {e}")
            return []

    def place_market_order(self, symbol, side, qty):
        """
        Executes a market order.
        ✅ STEP 2 — BLOCK LIVE EXECUTION OUTSIDE LIVE MODE
        """
        if not execution_context.is_live():
            print(f"🛑 BLOCKED: Non-live mode execution attempted for {symbol}")
            return {
                "retCode": -1,
                "retMsg": "EXECUTION_BLOCKED_NON_LIVE_MODE"
            }

        try:
            payload = {
                "category": "linear",
                "symbol": symbol,
                "side": side.capitalize(),
                "orderType": "Market",
                "qty": str(qty),
                "timeInForce": "IOC"
            }
            return self._signed_request("POST", "/v5/order/create", payload)
        except Exception as e:
            print(f"❌ [ORDER_FAIL] {symbol}: {e}")
            return None 

    def set_trading_stop(self, symbol, stop_loss=None, take_profit=None):
        """
        Sets exchange-native TP/SL on an active position.
        ✅ STEP 3 — BLOCK TP/SL MUTATION OUTSIDE LIVE MODE
        """
        if not execution_context.is_live():
            print(f"🛑 BLOCKED: TP/SL mutation outside LIVE mode for {symbol}")
            return {
                "retCode": -1,
                "retMsg": "TP_SL_BLOCKED_NON_LIVE_MODE"
            }

        try:
            payload = {"category": "linear", "symbol": symbol, "tpslMode": "Full"}
            if stop_loss: payload["stopLoss"] = str(stop_loss)
            if take_profit: payload["takeProfit"] = str(take_profit)

            return self._signed_request("POST", "/v5/position/trading-stop", payload)
        except Exception as e:
            print(f"❌ [TP_SL_FAIL] {symbol}: {e}")
            return None