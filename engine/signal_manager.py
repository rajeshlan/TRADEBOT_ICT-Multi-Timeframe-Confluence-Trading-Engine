import time
import os

# FEATURE ENGINE & SCHEMA IMPORTS
from core.setup_memory.feature_engine import build_features
from core.trade_schema import normalize_trade_schema
from core.market_regime_engine import classify_market_regime

# ✅ UPGRADE 7: IMPORT SETUP GRADER
from core.setup_grader import grade_trade_setup

# ✅ SYSTEM STATE & SESSION IMPORTS
from core.system_state import drawdown_guard
from core.session_engine import get_current_session

# ✅ STEP 1 — ADD CORRELATION & STORAGE IMPORTS
from core.correlation_engine import correlated_positions_count
from storage.trade_logger import load_active_trades

# ✅ STEP 2 — ADD RUNTIME LOGGER IMPORT
from utils.runtime_logger import log_runtime_event

class SignalManager:
    """
    Manages the lifecycle of trading signals, applying ICT-based discipline,
    adaptive market-regime logic, session intelligence, and correlation awareness.
    """

    def __init__(self):
        # 1️⃣ TRACKERS: Prevents over-trading and protects against "signal spam"
        self.last_signals = {}       # Key: "SYMBOL_BIAS" -> Value: timestamp
        self.last_signal_time = {}   # Key: "SYMBOL" -> Value: timestamp
        
        # 🧠 DISCIPLINE CONFIG
        self.cooldown = 1800         # 30 mins for same-side bias
        self.cooldown_seconds = 900  # 15 mins total silence for symbol after ANY signal

    def process(self, symbol, results_by_tf):
        """
        🚀 PHASE 9.0 — OBSERVABILITY & AUDIT LOGGING
        Evaluates signals and logs decision events for post-trade analysis.
        """
        now = time.time()

        # STEP 1: BUILD CANDLE REGISTRY
        candles_by_tf = {}
        for tf, result in results_by_tf.items():
            if result and result.get("candles"):
                candles_by_tf[tf] = result["candles"]

        # 2️⃣ STEP 2: COOLDOWN FILTER
        last_symbol_time = self.last_signal_time.get(symbol)
        if last_symbol_time and (now - last_symbol_time < self.cooldown_seconds):
            print(f"[SKIP] {symbol} in system cooldown")
            
            # ✅ LOG COOLDOWN EVENT
            log_runtime_event(
                event_type="SCAN_SKIPPED",
                symbol=symbol,
                data={"reason": "COOLDOWN"}
            )
            return None

        # 🔹 TIMEFRAME WEIGHTING
        weights = {"1M": 35, "1d": 30, "4h": 25, "2h": 15, "30m": 10, "5m": 5}

        score = 0
        valid_timeframes = []
        htf_present = False
        ltf_present = False
        htf_bias = None

        # --- STEP 3: ESTABLISH HTF BIAS ---
        for tf in ["1M", "1d", "4h"]:
            if tf in results_by_tf:
                res = results_by_tf[tf]
                if res and res.get("ob"):
                    htf_bias = res["ob"]["type"]
                    break

        if not htf_bias:
            return None

        bias = "BULLISH" if "BULLISH" in htf_bias else "BEARISH"

        # ---------------------------------------------------------
        # 🚀 MARKET REGIME CLASSIFICATION
        # ---------------------------------------------------------
        lower_tf_candles = candles_by_tf.get("30m", [])
        market_regime = "UNKNOWN"
        
        if lower_tf_candles:
            market_regime = classify_market_regime(lower_tf_candles)
            
            # ADAPTIVE SCORING MODIFIERS
            if market_regime == "RANGING": score -= 10
            elif market_regime == "COMPRESSED": score -= 15
            elif market_regime == "TRENDING": score += 8
            elif market_regime == "VOLATILE": score -= 5

        # ---------------------------------------------------------
        # ✅ SESSION-BASED SCORING
        # ---------------------------------------------------------
        current_session = get_current_session()

        if current_session == "NEW_YORK": score += 10
        elif current_session == "LONDON": score += 6
        elif current_session == "ASIA": score -= 4
        elif current_session == "DEAD": score -= 12

        # ---------------------------------------------------------
        # ✅ CORRELATION EXPOSURE LOGIC
        # ---------------------------------------------------------
        active_trades = load_active_trades() or []
        correlated_count = correlated_positions_count(symbol, active_trades)

        if correlated_count >= 2:
            print(f"⚠️ CORRELATED EXPOSURE HIGH: {symbol} (Count: {correlated_count})")
            
            # ✅ LOG CORRELATION WARNING
            log_runtime_event(
                event_type="CORRELATION_WARNING",
                symbol=symbol,
                data={"correlated_count": correlated_count}
            )
            score -= 15
        elif correlated_count == 1:
            score -= 6

        # --- STEP 4: CONFLUENCE & SCORING ---
        for tf, result in results_by_tf.items():
            if not result: continue

            ob = result.get("ob")
            fvg = result.get("fvg")
            liq = result.get("liquidity")

            has_liq = liq.get("has_liquidity", False) if liq else False
            has_ob = bool(ob and ob.get("type") == htf_bias)
            
            has_fvg = False
            if fvg and fvg.get("type") and bias in fvg["type"]:
                has_fvg = True

            if not (has_ob or (has_fvg and has_liq)):
                continue

            score += weights.get(tf, 5)
            valid_timeframes.append(tf)

            if tf in ["1M", "1d", "4h"]: htf_present = True
            if tf in ["5m", "30m"]: ltf_present = True

            if has_liq:
                score += 5
                if liq.get("swept"):
                    score += 10 
                else:
                    correct_dir = (
                        (bias == "BEARISH" and liq.get("type") == "BUY_SIDE") or 
                        (bias == "BULLISH" and liq.get("type") == "SELL_SIDE")
                    )
                    score += 10 if correct_dir else 3

        # ✅ DEFENSIVE FILTER
        if drawdown_guard.should_reduce_risk():
            print("⚠️ DEFENSIVE MODE ACTIVE: Applying -12 confluence penalty.")
            score -= 12 

        # --- STEP 5: VALIDATION FILTERS ---
        if len(valid_timeframes) < 1 or not (htf_present and ltf_present):
            return None

        if score < 25: 
            return None

        key = f"{symbol}_{bias}"
        if key in self.last_signals and (now - self.last_signals[key] < self.cooldown):
            return None

        # --- STEP 6: LEVEL EXTRACTION & ADAPTIVE RR LOGIC ---
        best_ob = None
        sorted_tfs = sorted(valid_timeframes, key=lambda x: weights.get(x, 0), reverse=True)
        
        for tf in sorted_tfs:
            ob_data = results_by_tf[tf].get("ob")
            if ob_data and "entry" in ob_data and "sl" in ob_data:
                best_tf = tf
                best_ob = ob_data
                break

        if not best_ob:
            return None

        entry = best_ob.get("entry")
        sl = best_ob.get("sl")

        if entry and sl:
            risk_pct = abs(entry - sl) / entry * 100
            if risk_pct > 5: return None

            rr_ratio = 2.0 
            if market_regime == "TRENDING": rr_ratio = 2.8
            elif market_regime == "RANGING": rr_ratio = 1.6
            elif market_regime == "VOLATILE": rr_ratio = 1.8
            elif market_regime == "COMPRESSED": rr_ratio = 1.4

            # ---------------------------------------------------------
            # ✅ SETUP GRADING & FILTERING
            # ---------------------------------------------------------
            setup_grade = grade_trade_setup(
                score=score,
                market_regime=market_regime,
                rr_ratio=rr_ratio
            )

            if setup_grade == "C":
                print(f"[REJECTED] {symbol} Grade too weak: C")
                
                # ✅ LOG GRADE REJECTION
                log_runtime_event(
                    event_type="SETUP_REJECTED",
                    symbol=symbol,
                    data={
                        "reason": "GRADE_C",
                        "grade": setup_grade,
                        "score": score,
                        "market_regime": market_regime,
                        "session": current_session
                    }
                )
                return None

            # ✅ STEP 6 — DEBUG LOGGING
            print(
                f"🏆 {symbol} | "
                f"SESSION={current_session} | "
                f"🔗 CORR_COUNT={correlated_count} | "
                f"GRADE={setup_grade} | "
                f"SCORE={score}"
            )

            # ✅ LOG SETUP APPROVAL
            log_runtime_event(
                event_type="SETUP_APPROVED",
                symbol=symbol,
                data={
                    "grade": setup_grade,
                    "score": score,
                    "session": current_session,
                    "market_regime": market_regime,
                    "bias": bias,
                    "timeframes": valid_timeframes,
                    "correlated_exposure": correlated_count
                }
            )

            risk_amount = abs(entry - sl)
            tp = entry + (risk_amount * rr_ratio) if bias == "BULLISH" else entry - (risk_amount * rr_ratio)

            # --- STEP 7: ENRICH SIGNAL ---
            signal = normalize_trade_schema({
                "symbol": symbol, "bias": bias, "timeframes": valid_timeframes,
                "confluence_score": min(score, 100), "market_regime": market_regime,
                "setup_grade": setup_grade, "session": current_session,
                "correlated_exposure": correlated_count, "entry": round(entry, 4),
                "sl": round(sl, 4), "tp": round(tp, 4), "rr_ratio": rr_ratio,
                "rr": f"1:{rr_ratio}", "risk_pct_distance": round(risk_pct, 2),
                "details": f"Institutional Exposure Engine ({best_tf} Source)"
            })

            try:
                enriched = build_features(signal, results_by_tf, candles_by_tf)
                if enriched: signal.update(enriched)
            except Exception as e:
                print(f"[FEATURE_ERROR] {symbol}: {e}")

            self.last_signals[key] = now
            self.last_signal_time[symbol] = now
            return signal

        return None