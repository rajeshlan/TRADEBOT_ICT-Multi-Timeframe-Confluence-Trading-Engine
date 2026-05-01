import time
import hashlib

class SetupMemory:
    def __init__(self, cooldown_seconds=3600):
        self.cooldown = cooldown_seconds
        self.memory = {}

    def _generate_id(self, signal):
        key = f"{signal['symbol']}_{signal['bias']}_{round(signal['entry'], 4)}_{round(signal['sl'], 4)}_{round(signal['tp'], 4)}"
        return hashlib.md5(key.encode()).hexdigest()

    def is_duplicate(self, signal):
        setup_id = self._generate_id(signal)
        now = time.time()

        if setup_id in self.memory:
            last_time = self.memory[setup_id]

            if now - last_time < self.cooldown:
                return True  # ❌ duplicate

        self.memory[setup_id] = now
        return False  # ✔ new