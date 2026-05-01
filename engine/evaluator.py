from strategies.ict.ob import OrderBlockStrategy
from strategies.ict.fvg import FVGStrategy
from strategies.ict.liquidity import LiquidityStrategy

class Evaluator:
    """
    Central hub for processing raw market data through various ICT-based algorithms.
    Combines Order Blocks, Fair Value Gaps, and Liquidity analysis for a holistic market view.
    """
    
    def __init__(self):
        self.ob = OrderBlockStrategy()
        self.fvg = FVGStrategy()
        self.liquidity = LiquidityStrategy()

    def run(self, symbol, timeframe, candles):
        """
        Runs all initialized strategies on the given candle dataset and aggregates the results.
        """
        ob_result = self.ob.evaluate(symbol, timeframe, candles)
        fvg_result = self.fvg.detect(candles)
        liq_result = self.liquidity.detect(candles)

        return {
            "ob": ob_result,
            "fvg": fvg_result,
            "liquidity": liq_result
        }