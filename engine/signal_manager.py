import time

class SignalManager:
    """
    Manages the lifecycle of trading signals, applying ICT-based discipline 
    and multi-timeframe confluence filtering.
    """

    def __init__(self):
        # 1️⃣ TRACKERS: Prevents over-trading and protects against "signal spam"
        self.last_signals = {}       # Key: "SYMBOL_BIAS" -> Value: timestamp
        self.last_signal_time = {}   # Key: "SYMBOL" -> Value: timestamp
        
        # 🧠 DISCIPLINE CONFIG
        # Cooldown prevents taking multiple trades in the same direction too quickly
        self.cooldown = 1800         # 30 mins for same-side bias
        # Total silence ensures the bot waits after any signal before looking again
        self.cooldown_seconds = 900  # 15 mins total silence for symbol after ANY signal

    def process(self, symbol, results_by_tf):
        """
        🚀 PHASE 6.3 — DISCIPLINE ENGINE (Risk Filter Edition)
        Filters raw technical data into actionable trading signals.
        """
        now = time.time()

        # 2️⃣ STEP 1: COOLDOWN FILTER
        # Check if the symbol is currently in a "rest period"
        last_symbol_time = self.last_signal_time.get(symbol)
        if last_symbol_time and (now - last_symbol_time < self.cooldown_seconds):
            print(f"[SKIP] {symbol} in system cooldown")
            return None

        # 🔹 TIMEFRAME WEIGHTING
        # Higher weights are given to Higher Timeframes (HTF) for narrative strength
        weights = {
            "1M": 35, "1d": 30, "4h": 25, "2h": 15, "30m": 10, "5m": 5
        }

        score = 0
        valid_timeframes = []
        htf_present = False
        ltf_present = False
        htf_bias = None

        # --- STEP 2: ESTABLISH HTF BIAS ---
        # We look for an Order Block (OB) on the Daily or 4H to set the narrative
        for tf in ["1M", "1d", "4h"]:
            if tf in results_by_tf:
                res = results_by_tf[tf]
                if res and res.get("ob"):
                    htf_bias = res["ob"]["type"]
                    break

        if not htf_bias:
            return None

        # Determine if we are looking for BUYS or SELLS
        bias = "BULLISH" if "BULLISH" in htf_bias else "BEARISH"

        # --- STEP 3: CONFLUENCE & SCORING ---
        for tf, result in results_by_tf.items():
            if not result: continue

            ob = result.get("ob")
            fvg = result.get("fvg")
            liq = result.get("liquidity")

            # 🧪 ALIGNMENT CHECKS
            has_liq = liq.get("has_liquidity", False) if liq else False
            has_ob = bool(ob and ob.get("type") == htf_bias)
            
            # Fair Value Gap (FVG) alignment check
            has_fvg = False
            if fvg and fvg.get("type") and bias in fvg["type"]:
                has_fvg = True

            # 🎯 ICT VALIDATION: A timeframe is valid if it has an aligned OB, 
            # OR an aligned FVG paired with Liquidity.
            if not (has_ob or (has_fvg and has_liq)):
                continue

            # Add weight and track involved timeframes
            score += weights.get(tf, 5)
            valid_timeframes.append(tf)

            # Mark HTF vs LTF (Lower Timeframe) presence
            if tf in ["1M", "1d", "4h"]: htf_present = True
            if tf in ["5m", "30m"]: ltf_present = True

            # --- ⚙️ LIQUIDITY SCORING ---
            if has_liq:
                score += 5  # Base liquidity presence
                if liq.get("swept"):
                    score += 10 # Sweep confirmation (Pro-Trend)
                else:
                    # Check if the liquidity is "Narrative Correct" (e.g. Sell-side liq for a Bullish bias)
                    correct_dir = (
                        (bias == "BEARISH" and liq.get("type") == "BUY_SIDE") or 
                        (bias == "BULLISH" and liq.get("type") == "SELL_SIDE")
                    )
                    score += 10 if correct_dir else 3

        # --- STEP 4: TUNED FILTERS (MODERATE RIGOR) ---
        # 💡 Lowered requirements to increase trade frequency
        if len(valid_timeframes) < 1:
            return None

        if not (htf_present and ltf_present):
            print(f"[REJECTED] {symbol} Missing HTF/LTF alignment")
            return None

        # Ensure at least one timeframe has a liquidity confluence
        if not any(results_by_tf[tf].get("liquidity", {}).get("has_liquidity") for tf in valid_timeframes):
            print(f"[REJECTED] {symbol} No liquidity confluence")
            return None

        # 💡 Lowered Score Threshold (40 -> 25)
        if score < 25: 
            return None

        # Same-Bias Cooldown: Prevent multiple trades in the same direction
        key = f"{symbol}_{bias}"
        if key in self.last_signals and (now - self.last_signals[key] < self.cooldown):
            return None

        # --- STEP 5: LEVEL EXTRACTION ---
        best_tf, best_ob = None, None
        sorted_tfs = sorted(valid_timeframes, key=lambda x: weights.get(x, 0), reverse=True)
        
        for tf in sorted_tfs:
            ob_data = results_by_tf[tf].get("ob")
            if ob_data and "entry" in ob_data and "sl" in ob_data:
                best_tf = tf
                best_ob = ob_data
                break

        if not best_ob:
            return None

        entry, sl = best_ob.get("entry"), best_ob.get("sl")

        if entry and sl:
            # 🔴 RISK DISTANCE FILTER
            # 💡 Increased tolerance (3% -> 5%)
            risk_pct = abs(entry - sl) / entry * 100
            if risk_pct > 5:
                print(f"[REJECTED] {symbol} Risk too wide: {risk_pct:.2f}%")
                return None

            # Finalize tracking
            self.last_signals[key] = now
            self.last_signal_time[symbol] = now

            # Calculate Target (Standard 1:2 Reward to Risk)
            risk_amount = abs(entry - sl)
            tp = entry - (risk_amount * 2) if bias == "BEARISH" else entry + (risk_amount * 2)

            # 🔥 FIX: Normalize score and rename key for dashboard clarity
            final_confluence_score = min(score, 100)

            return {
                "symbol": symbol,
                "bias": bias,
                "timeframes": valid_timeframes,
                "confluence_score": final_confluence_score,
                "entry": round(entry, 4),
                "sl": round(sl, 4),
                "tp": round(tp, 4),
                "rr": "1:2",
                "risk_pct_distance": round(risk_pct, 2),
                "details": f"Refined ICT Discipline Engine ({best_tf} Source)"
            }

        return None