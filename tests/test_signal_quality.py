import unittest

from core.signal_quality import (
    assess_signal_quality,
    classify_archetype,
    expected_value_assessment,
)


def make_candles(direction=1, count=40, noisy=False):
    candles = []
    price = 100.0
    for index in range(count):
        step = direction * 0.4
        if noisy:
            step = 0.4 if index % 2 == 0 else -0.38
        open_ = price
        close = price + step
        high = max(open_, close) + 0.1
        low = min(open_, close) - 0.1
        candles.append(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 100 + index,
            }
        )
        price = close
    return candles


class SignalQualityTests(unittest.TestCase):
    def test_classifies_sweep_fvg_reversal(self):
        signal = {"bias": "BULLISH", "market_regime": "TRENDING"}
        results = {
            "5m": {
                "liquidity": {"swept": True, "type": "SELL_SIDE"},
                "fvg": {"type": "BULLISH"},
            }
        }
        archetype = classify_archetype(signal, results, {"5m": make_candles()})
        self.assertEqual(archetype, "SWEEP_FVG_REVERSAL")

    def test_chop_gets_penalized(self):
        signal = {"bias": "BULLISH", "correlated_exposure": 0}
        quality = assess_signal_quality(
            signal,
            {},
            {"5m": make_candles(noisy=True)},
            {"spread_bps": 1, "funding_rate": 0, "book_imbalance": 0},
        )
        self.assertLess(quality["score_delta"], 0)
        self.assertGreaterEqual(quality["chop_score"], 0.5)

    def test_expected_value_gate_approves_strong_setup(self):
        signal = {"confluence_score": 90, "rr_ratio": 2.8, "correlated_exposure": 0}
        quality = {
            "trend_quality": 0.8,
            "reclaim_speed": 0.8,
            "chop_score": 0.1,
            "squeeze_risk": 0,
            "cascade_risk": 0,
            "liquidity_vacuum": False,
        }
        result = expected_value_assessment(signal, quality)
        self.assertTrue(result["approved"])
        self.assertGreater(result["expected_value_r"], result["approval_threshold_r"])


if __name__ == "__main__":
    unittest.main()
