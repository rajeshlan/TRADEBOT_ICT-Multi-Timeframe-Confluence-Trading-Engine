import time

class SignalManager:

    def __init__(self):
        # 1️⃣ Trackers for deduplication and timing
        self.last_signals = {}       # { "BTCUSDT_BULLISH": timestamp }
        self.last_signal_time = {}   # { "BTCUSDT": timestamp }
        
        # 🧠 Discipline Config
        self.cooldown = 1800         # 30 mins for same-side bias
        self.cooldown_seconds = 900  # 15 mins total silence for symbol after ANY signal

    def process(self, symbol, results_by_tf):
        """
        🚀 PHASE 6.2 — DISCIPLINE ENGINE (Patch 1: LTF FVG Engine)
        Filters signals by HTF/LTF alignment, mandatory liquidity, and cooldowns.
        LTF now accepts FVG + Liquidity as a valid entry trigger without needing an OB.
        """
        now = time.time()

        # 2️⃣ STEP 2 — COOLDOWN filter (Total Symbol Silence)
        last_symbol_time = self.last_signal_time.get(symbol)
        if last_symbol_time and (now - last_symbol_time < self.cooldown_seconds):
            print(f"[SKIP] {symbol} in system cooldown")
            return None

        # 🔹 Timeframe Weighting
        weights = {
            "1M": 35, "1d": 30, "4h": 25, "2h": 15, "30m": 10, "5m": 5
        }

        score = 0
        tfs_involved = []
        htf_bias = None
        
        # 3️⃣ STEP 3 — State Trackers for Alignment
        valid_timeframes = []
        htf_present = False
        ltf_present = False

        # --- Step 1: Establish HTF Direction ---
        for tf in ["1M", "1d", "4h"]:
            if tf in results_by_tf:
                res = results_by_tf[tf]
                if res and res.get("ob"):
                    htf_bias = res["ob"]["type"]
                    break

        if not htf_bias:
            return None

        bias = "BULLISH" if "BULLISH" in htf_bias else "BEARISH"

        # --- Step 2: Confluence & Scoring ---
        for tf, result in results_by_tf.items():
            if not result: continue

            ob = result.get("ob")
            fvg = result.get("fvg")
            liq = result.get("liquidity")

            # 🧪 Alignment Checks
            has_liq = liq.get("has_liquidity", False) if liq else False
            has_ob = bool(ob and ob.get("type") == htf_bias)
            
            # FVG must align with our established bias
            has_fvg = False
            if fvg and fvg.get("type") and bias in fvg["type"]:
                has_fvg = True

            print(f"[CHECK] {symbol} {tf} ob={has_ob} fvg={has_fvg} liq={has_liq}")

            # 🎯 THE ICT FIX: Valid if aligned OB exists, OR if aligned FVG + Liquidity exists
            if not (has_ob or (has_fvg and has_liq)):
                continue

            # If it reaches here, the timeframe is structurally valid
            score += weights.get(tf, 5)
            tfs_involved.append(tf)
            valid_timeframes.append(tf)

            # Mark HTF/LTF presence
            if tf in ["1M", "1d", "4h"]: htf_present = True
            if tf in ["5m", "30m"]: ltf_present = True

            # --- ⚙️ STEP 5 — LIQUIDITY SCORING ---
            if has_liq:
                score += 5  # Base liquidity presence
                
                if liq.get("swept"):
                    score += 10  # 🔥 BIG BOOST for sweep
                else:
                    # Narrative Check
                    correct_dir = (
                        (bias == "BEARISH" and liq.get("type") == "BUY_SIDE") or 
                        (bias == "BULLISH" and liq.get("type") == "SELL_SIDE")
                    )
                    score += 10 if correct_dir else 3

        # ⚙️ STEP 7 — DEBUG
        print(f"[INFO] {symbol} Score={score} TFs={valid_timeframes} HTF={htf_present} LTF={ltf_present}")

        # 4️⃣ STEP 4 — STRICT FILTERS
        # ❌ Rule 1: Multi-TF Confluence
        if len(valid_timeframes) < 2:
            print(f"[REJECTED] {symbol} Not enough TF confluence")
            return None

        # ❌ Rule 2: HTF Narrative + LTF Entry alignment
        if not (htf_present and ltf_present):
            print(f"[REJECTED] {symbol} Missing HTF/LTF alignment")
            return None

        # ❌ Rule 3: No Liquidity = No Trade
        if not any(results_by_tf[tf].get("liquidity", {}).get("has_liquidity") for tf in tfs_involved):
            print(f"[REJECTED] {symbol} No liquidity confluence")
            return None

        if score < 40: return None

        # --- Same-Bias Cooldown Check ---
        key = f"{symbol}_{bias}"
        if key in self.last_signals and (now - self.last_signals[key] < self.cooldown):
            return None

        # --- Level Extraction (Safeguard added for FVG entries) ---
        # Since an LTF might only have FVG+Liq now, we must find the highest-weighted TF 
        # that actually contains an OB to pull safe Entry/SL parameters.
        best_tf = None
        best_ob = None
        
        # Sort involved TFs by weight descending
        sorted_tfs = sorted(tfs_involved, key=lambda x: weights.get(x, 0), reverse=True)
        
        for tf in sorted_tfs:
            ob_data = results_by_tf[tf].get("ob")
            if ob_data and "entry" in ob_data and "sl" in ob_data:
                best_tf = tf
                best_ob = ob_data
                break

        if not best_ob:
            print(f"[REJECTED] {symbol} No structural OB found for Entry/SL extraction")
            return None

        entry, sl = best_ob.get("entry"), best_ob.get("sl")

        if entry and sl:
            # 6️⃣ STEP 6 — SAVE SIGNAL TIME (Final hurdle passed)
            self.last_signals[key] = now
            self.last_signal_time[symbol] = now

            risk = abs(entry - sl)
            tp = entry - (risk * 2) if bias == "BEARISH" else entry + (risk * 2)

            return {
                "symbol": symbol,
                "bias": bias,
                "timeframes": tfs_involved,
                "score": score,
                "entry": round(entry, 4),
                "sl": round(sl, 4),
                "tp": round(tp, 4),
                "rr": "1:2",
                "details": f"Refined ICT Discipline Engine ({best_tf} Source)"
            }

        return None