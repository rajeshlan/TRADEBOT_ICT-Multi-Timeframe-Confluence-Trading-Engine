class FVGStrategy:

    def detect(self, candles):
        if len(candles) < 3:
            return None

        fvg_zones = []

        for i in range(2, len(candles)):
            c1 = candles[i-2]
            c2 = candles[i-1]
            c3 = candles[i]

            # Bullish FVG
            if c1["high"] < c3["low"]:
                fvg_zones.append({
                    "type": "BULLISH",
                    "low": c1["high"],
                    "high": c3["low"]
                })

            # Bearish FVG
            if c1["low"] > c3["high"]:
                fvg_zones.append({
                    "type": "BEARISH",
                    "high": c1["low"],
                    "low": c3["high"]
                })

        return fvg_zones[-1] if fvg_zones else None