class LiquidityStrategy:
    """
    Refined ICT Liquidity Engine (Phase 6.1).
    Detects high-probability liquidity zones using strict Equal High/Low 
    matching and Sweep detection.
    """

    def detect(self, candles):
        """
        Analyzes 20 candles for Buy-side or Sell-side liquidity.
        Returns:
            {
                "has_liquidity": bool,
                "type": "BUY_SIDE" | "SELL_SIDE" | None,
                "swept": bool
            }
        """
        if len(candles) < 20:
            return {
                "has_liquidity": False,
                "type": None,
                "swept": False
            }

        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]

        lookback = 20
        # Strict threshold: 0.0003 (0.03%) to ensure institutional relevance
        threshold = 0.0003

        equal_highs = False
        equal_lows = False
        sweep = False
        liq_type = None

        # --- 1️⃣ Equal Highs Detection (Engineered Buy-side) ---
        count_eqh = 0
        # Slice for lookback range excluding the last candle
        for i in range(len(highs) - lookback, len(highs) - 2):
            diff = abs(highs[i] - highs[i+1]) / highs[i]
            if diff < threshold:
                count_eqh += 1

        # Require at least 2 candle-to-candle matches (3+ candles forming a ceiling)
        if count_eqh >= 2:
            equal_highs = True

        # --- 2️⃣ Equal Lows Detection (Engineered Sell-side) ---
        count_eql = 0
        for i in range(len(lows) - lookback, len(lows) - 2):
            diff = abs(lows[i] - lows[i+1]) / lows[i]
            if diff < threshold:
                count_eql += 1

        if count_eql >= 2:
            equal_lows = True

        # --- 3️⃣ Sweep Detection ---
        last_high = highs[-1]
        last_low = lows[-1]

        # Calculate range extremes excluding the trigger candle
        prev_max = max(highs[-lookback:-1])
        prev_min = min(lows[-lookback:-1])

        if last_high > prev_max:
            sweep = True
            liq_type = "BUY_SIDE"

        elif last_low < prev_min:
            sweep = True
            liq_type = "SELL_SIDE"

        # --- 4️⃣ Consolidation & Type Mapping ---
        # Note: If a sweep is active, that becomes the primary signal type
        if not sweep:
            if equal_highs:
                liq_type = "BUY_SIDE"
            elif equal_lows:
                liq_type = "SELL_SIDE"

        return {
            "has_liquidity": equal_highs or equal_lows or sweep,
            "type": liq_type,
            "swept": sweep
        }