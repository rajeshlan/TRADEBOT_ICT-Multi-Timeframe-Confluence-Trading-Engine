class BaseStrategy:
    def evaluate(self, symbol, timeframe, candles):
        raise NotImplementedError