import unittest

from core.ids import build_order_intent_id, build_setup_id
from core.trade_schema import normalize_trade_schema


class TradeIdentityTests(unittest.TestCase):
    def test_order_intent_is_stable_and_exchange_safe(self):
        trade = {
            "trade_uuid": "abc-123",
            "symbol": "BTCUSDT",
            "bias": "BULLISH",
            "entry": 100,
            "sl": 95,
            "tp": 112,
        }
        first = build_order_intent_id(trade)
        second = build_order_intent_id(trade)
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 36)

    def test_schema_preserves_signal_identity(self):
        setup_id = build_setup_id(
            {
                "symbol": "ETHUSDT",
                "bias": "BEARISH",
                "entry": 2000,
                "sl": 2040,
                "tp": 1900,
                "timeframes": ["5m", "30m"],
            }
        )
        trade = normalize_trade_schema(
            {
                "setup_id": setup_id,
                "decision_id": "decision_x",
                "archetype": "SWEEP_REVERSAL",
            }
        )
        self.assertEqual(trade["setup_id"], setup_id)
        self.assertEqual(trade["decision_id"], "decision_x")
        self.assertEqual(trade["archetype"], "SWEEP_REVERSAL")


if __name__ == "__main__":
    unittest.main()
