from strategies.ict.ob import OrderBlockStrategy
from strategies.ict.fvg import FVGStrategy
from strategies.ict.liquidity import LiquidityStrategy

class Evaluator:
    """
    Central hub for processing raw market data through various ICT-based algorithms.
    Combines Order Blocks, Fair Value Gaps, and Liquidity analysis for a holistic market view.
    """
    
    def __init__(self):
        # Initializing the core ICT strategy components
        self.ob = OrderBlockStrategy()
        self.fvg = FVGStrategy()
        self.liquidity = LiquidityStrategy()

    def run(self, symbol, timeframe, candles):
        """
        Runs all initialized strategies on the given candle dataset and aggregates the results.
        
        Args:
            symbol (str): The trading pair (e.g., "BTCUSDT").
            timeframe (str): The chart interval (e.g., "4h").
            candles (list/DataFrame): The raw price data.
            
        Returns:
            dict: Comprehensive analysis results including raw candles for downstream feature engineering.
        """
        # Execute individual strategy detections
        ob_result = self.ob.evaluate(symbol, timeframe, candles)
        fvg_result = self.fvg.detect(candles)
        liq_result = self.liquidity.detect(candles)

        # REPLACED: Now returning 'candles' alongside strategy results
        # This allows the SignalManager's Feature Engine to calculate ATR/Regime.
        return {
            "ob": ob_result,
            "fvg": fvg_result,
            "liquidity": liq_result,
            "candles": candles  # <--- CRITICAL: Exposes data to the Feature Engine
        }