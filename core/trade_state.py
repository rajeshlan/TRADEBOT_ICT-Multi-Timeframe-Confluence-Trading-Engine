import time

class TradeStateManager:
    def __init__(self):
        self.active_symbols = set()

    def is_symbol_active(self, symbol):
        return symbol in self.active_symbols

    def open_trade(self, symbol):
        self.active_symbols.add(symbol)
        print(f"[STATE] Locked {symbol}")

    def close_trade(self, symbol):
        if symbol in self.active_symbols:
            self.active_symbols.remove(symbol)
            print(f"[STATE] Released {symbol}")