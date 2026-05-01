from strategies.base_strategy import BaseStrategy
from strategies.ict.structure import MarketStructure

class OrderBlockStrategy(BaseStrategy):
    """
    Upgraded ICT Order Block Strategy.
    Filters for OBs that are confirmed by a recent Break of Structure (BOS)
    and uses logically validated structural swings for high-precision SL placement.
    """

    def __init__(self):
        # Initialize MarketStructure to handle trend alignment and swing detection
        self.structure = MarketStructure()

    def get_recent_swing(self, candles, direction, entry):
        """
        Retrieves the most recent structural point to use as a Stop Loss,
        ensuring it is logically positioned relative to the entry level.
        """
        highs, lows = self.structure.get_swings(candles)

        if direction == "BEARISH" and highs:
            # Pick the most recent swing HIGH that is strictly above the entry
            for i in range(len(highs) - 1, -1, -1):
                if highs[i][1] > entry:
                    return highs[i][1]

        if direction == "BULLISH" and lows:
            # Pick the most recent swing LOW that is strictly below the entry
            for i in range(len(lows) - 1, -1, -1):
                if lows[i][1] < entry:
                    return lows[i][1]

        return None

    def evaluate(self, symbol, timeframe, candles):
        # Ensure we have enough data to calculate structure and OB
        if len(candles) < 20:
            return None

        # 1. Trend Alignment: Detect recent Break of Structure (BOS)
        bos = self.structure.detect_bos(candles)

        # If no clear trend structure is detected, we skip the trade
        if not bos:
            return None

        last = candles[-1]

        # 2. Scan for the Order Block (The last opposing candle before the move)
        # Lookback range: from 5 bars ago to 15 bars ago
        for i in range(len(candles) - 5, len(candles) - 15, -1):
            c = candles[i]
            candle_range = c["high"] - c["low"]

            # 🔹 BULLISH OB Logic
            if bos == "BULLISH" and c["close"] < c["open"]:
                move = last["close"] - c["high"]

                # Requirement: Explosive move
                if move > candle_range * 1.5:
                    entry_level = c["low"]
                    sl = self.get_recent_swing(candles, bos, entry_level)
                    return {
                        "type": "BULLISH_OB",
                        "bos": bos,
                        "entry": entry_level,
                        "sl": sl if sl else (entry_level - candle_range), # Fallback if no valid swing found
                        "strength": round(move, 2)
                    }

            # 🔹 BEARISH OB Logic
            if bos == "BEARISH" and c["close"] > c["open"]:
                move = c["low"] - last["close"]

                # Requirement: Explosive move down
                if move > candle_range * 1.5:
                    entry_level = c["high"]
                    sl = self.get_recent_swing(candles, bos, entry_level)
                    return {
                        "type": "BEARISH_OB",
                        "bos": bos,
                        "entry": entry_level,
                        "sl": sl if sl else (entry_level + candle_range), # Fallback if no valid swing found
                        "strength": round(abs(move), 2)
                    }

        return None