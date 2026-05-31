import time
import os

# FEATURE ENGINE & SCHEMA IMPORTS
from core.setup_memory.feature_engine import build_features
from core.trade_schema import normalize_trade_schema
from core.market_regime_engine import classify_market_regime
from core.market_context import get_market_context
from core.signal_quality import (
    assess_signal_quality,
    classify_archetype,
    expected_value_assessment,
)
from core.ids import build_decision_id, build_setup_id

# UPGRADE 7: IMPORT SETUP GRADER
from core.setup_grader import grade_trade_setup

# SYSTEM STATE & SESSION IMPORTS
from core.system_state import drawdown_guard
from core.session_engine import get_current_session

# STEP 1 — ADD CORRELATION & STORAGE IMPORTS
from core.correlation_engine import correlated_positions_count
from storage.trade_logger import load_active_trades, load_closed_trades
from analytics.research import empirical_prior_for

# STEP 2 — ADD RUNTIME LOGGER IMPORT
from utils.runtime_logger import log_runtime_event

# 🚀 STEP 1 (UPGRADE) — IMPORT THE NEW RISK ENGINE
from risk.adaptive_risk import (
    compute_atr,
    build_adaptive_stop,
    volatility_is_tradeable,
)

class SignalManager:
    """
    Manages the lifecycle of trading signals, applying ICT-based discipline,
    adaptive market-regime logic, session intelligence, and correlation awareness.
    """

    def __init__(self):
        # TRACKERS: Prevents over-trading and protects against "signal spam"
        self.last_signals = {}       # Key: "SYMBOL_BIAS" -> Value: timestamp
        self.last_signal_time = {}   # Key: "SYMBOL" -> Value: timestamp
        
        # DISCIPLINE CONFIG
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

        # STEP 2: COOLDOWN FILTER
        last_symbol_time = self.last_signal_time.get(symbol)
        if last_symbol_time and (now - last_symbol_time < self.cooldown_seconds):
            print(f"[SKIP] {symbol} in system cooldown")
            
            # LOG COOLDOWN EVENT
            log_runtime_event(
                event_type="SCAN_SKIPPED",
                symbol=symbol,
                data={"reason": "COOLDOWN"}
            )
            return None

        # TIMEFRAME WEIGHTING
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
            
            # LOG CORRELATION WARNING
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

        # 🚀 STEPS 2 & 3 (UPGRADE) — VOLATILITY ENGINE & ADAPTIVE STOP OVERRIDE
        entry = best_ob.get("entry")
        structure_sl = best_ob.get("sl")

        if entry and structure_sl:

            # ---------------------------------------------------------
            # 🚀 VOLATILITY ENGINE
            # ---------------------------------------------------------
            execution_tf_candles = (
                candles_by_tf.get("5m")
                or candles_by_tf.get("30m")
                or []
            )

            atr = compute_atr(execution_tf_candles, period=14)

            # Reject dead/compressed volatility environments
            if not volatility_is_tradeable(
                atr=atr,
                entry=entry,
                minimum_atr_pct=0.003
            ):
                log_runtime_event(
                    event_type="SETUP_REJECTED",
                    symbol=symbol,
                    data={
                        "reason": "LOW_VOLATILITY_ENVIRONMENT",
                        "atr": atr,
                        "entry": entry,
                        "market_regime": market_regime,
                    }
                )
                return None

            # ---------------------------------------------------------
            # 🚀 ADAPTIVE STOP ENGINE
            # ---------------------------------------------------------
            adaptive_stop = build_adaptive_stop(
                bias=bias,
                entry=entry,
                structure_sl=structure_sl,
                atr=atr,
                atr_multiplier=1.5,
                liquidity_buffer_pct=0.0015
            )

            sl = adaptive_stop["adaptive_sl"]
            risk_amount = adaptive_stop["stop_distance"]
            risk_pct = (risk_amount / entry) * 100

            # Reject absurdly wide invalidations
            if risk_pct > 6:
                return None

            # Reject ultra-tight noise stops
            if risk_pct < 0.25:
                log_runtime_event(
                    event_type="SETUP_REJECTED",
                    symbol=symbol,
                    data={
                        "reason": "STOP_TOO_TIGHT",
                        "risk_pct": risk_pct,
                        "atr": atr,
                    }
                )
                return None

            rr_ratio = 2.0 
            if market_regime == "TRENDING": rr_ratio = 2.8
            elif market_regime == "RANGING": rr_ratio = 1.6
            elif market_regime == "VOLATILE": rr_ratio = 1.8
            elif market_regime == "COMPRESSED": rr_ratio = 1.4

            risk_amount = abs(entry - sl)
            tp = entry + (risk_amount * rr_ratio) if bias == "BULLISH" else entry - (risk_amount * rr_ratio)

            market_context = get_market_context(symbol)
            
            # STEP 4: ADDED VOLATILITY METADATA SELECTION
            preliminary_signal = {
                "symbol": symbol,
                "bias": bias,
                "timeframes": valid_timeframes,
                "confluence_score": min(score, 100),
                "market_regime": market_regime,
                "session": current_session,
                "correlated_exposure": correlated_count,
                "entry": round(entry, 4),
                "sl": round(sl, 4),
                "tp": round(tp, 4),
                "rr_ratio": rr_ratio,
                "risk_pct_distance": round(risk_pct, 2),
                "atr": round(atr, 6),
                "atr_buffer": adaptive_stop["atr_buffer"],
                "liquidity_buffer": adaptive_stop["liquidity_buffer"],
                "structural_sl": round(structure_sl, 6),
                "adaptive_sl": round(sl, 6),
            }
            preliminary_signal["archetype"] = classify_archetype(
                preliminary_signal,
                results_by_tf,
                candles_by_tf,
            )
            preliminary_signal.update({
                "funding_rate": market_context.get("funding_rate"),
                "spread_bps": market_context.get("spread_bps"),
                "book_imbalance": market_context.get("book_imbalance"),
                "open_interest_change_pct": market_context.get("open_interest_change_pct"),
            })

            quality = assess_signal_quality(
                preliminary_signal,
                results_by_tf,
                candles_by_tf,
                market_context,
            )
            score = max(0, min(score + quality["score_delta"], 100))
            preliminary_signal["confluence_score"] = score
            preliminary_signal.update(quality)

            if quality["hard_reject"]:
                log_runtime_event(
                    event_type="SETUP_REJECTED",
                    symbol=symbol,
                    data={
                        "reason": "QUALITY_HARD_REJECT",
                        "quality_reasons": quality["reject_reasons"],
                        "score": score,
                        "market_regime": market_regime,
                        "session": current_session,
                        "bias": bias,
                    }
                )
                return None

            empirical = empirical_prior_for(preliminary_signal, load_closed_trades())
            expectancy = expected_value_assessment(
                preliminary_signal,
                quality,
                empirical,
                box=expectancy if 'expectancy' in locals() else None # Safeguard schema structure
            ) if False else expected_value_assessment(preliminary_signal, quality, empirical)
            
            preliminary_signal.update(expectancy)

            if not expectancy["approved"]:
                log_runtime_event(
                    event_type="SETUP_REJECTED",
                    symbol=symbol,
                    data={
                        "reason": "NEGATIVE_EXPECTANCY_GATE",
                        "archetype": preliminary_signal.get("archetype"),
                        "expected_value_r": expectancy["expected_value_r"],
                        "approval_threshold_r": expectancy["approval_threshold_r"],
                        "win_probability": expectancy["win_probability"],
                        "score": score,
                        "quality_reasons": quality["reject_reasons"],
                    }
                )
                return None

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
                
                # LOG GRADE REJECTION
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

            # DEBUG LOGGING
            print(
                f"🏆 {symbol} | "
                f"SESSION={current_session} | "
                f"🔗 CORR_COUNT={correlated_count} | "
                f"GRADE={setup_grade} | "
                f"SCORE={score} | "
                f"EV_R={expectancy['expected_value_r']}"
            )

            preliminary_signal["setup_grade"] = setup_grade
            preliminary_signal["setup_id"] = build_setup_id(preliminary_signal)
            preliminary_signal["decision_id"] = build_decision_id(preliminary_signal)

            # LOG SETUP APPROVAL
            log_runtime_event(
                event_type="SETUP_APPROVED",
                symbol=symbol,
                data={
                    "setup_id": preliminary_signal["setup_id"],
                    "decision_id": preliminary_signal["decision_id"],
                    "grade": setup_grade,
                    "score": score,
                    "session": current_session,
                    "market_regime": market_regime,
                    "bias": bias,
                    "timeframes": valid_timeframes,
                    "correlated_exposure": correlated_count,
                    "archetype": preliminary_signal.get("archetype"),
                    "expected_value_r": expectancy["expected_value_r"],
                    "win_probability": expectancy["win_probability"],
                    "quality_reasons": quality["reject_reasons"],
                }
            )

            # STEP 5: TP computation stays identical, adapting perfectly to structural shifts
            risk_amount = abs(entry - sl)
            tp = entry + (risk_amount * rr_ratio) if bias == "BULLISH" else entry - (risk_amount * rr_ratio)

            # --- STEP 7: ENRICH SIGNAL ---
            preliminary_signal.update({
                "rr": f"1:{rr_ratio}",
                "quality_reasons": quality["reject_reasons"],
                "details": (
                    f"Institutional Exposure Engine ({best_tf} Source) | "
                    f"{preliminary_signal.get('archetype')} | "
                    f"EV_R={expectancy['expected_value_r']}"
                ),
            })
            signal = normalize_trade_schema(preliminary_signal)

            try:
                enriched = build_features(signal, results_by_tf, candles_by_tf)
                if enriched: signal.update(enriched)
            except Exception as e:
                print(f"[FEATURE_ERROR] {symbol}: {e}")

            self.last_signals[key] = now
            self.last_signal_time[symbol] = now
            return signal

        return None