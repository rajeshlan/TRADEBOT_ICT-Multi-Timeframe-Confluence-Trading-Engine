class MarketStructure:

    def get_swings(self, candles):
        highs = []
        lows = []

        for i in range(2, len(candles) - 2):
            c = candles[i]

            if c["high"] > candles[i-1]["high"] and c["high"] > candles[i+1]["high"]:
                highs.append((i, c["high"]))

            if c["low"] < candles[i-1]["low"] and c["low"] < candles[i+1]["low"]:
                lows.append((i, c["low"]))

        return highs, lows

    def detect_bos(self, candles):
        highs, lows = self.get_swings(candles)

        if len(highs) < 2 or len(lows) < 2:
            return None

        last_high = highs[-1][1]
        prev_high = highs[-2][1]

        last_low = lows[-1][1]
        prev_low = lows[-2][1]

        # Bullish BOS
        if last_high > prev_high:
            return "BULLISH"

        # Bearish BOS
        if last_low < prev_low:
            return "BEARISH"

        return None