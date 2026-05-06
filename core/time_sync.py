import time


class TimeSync:
    def __init__(self, client):
        self.client = client

        self.server_epoch_ms = 0
        self.monotonic_base = 0

        self.last_sync = 0

        self.sync()

    def sync(self):
        try:
            res = self.client.get_server_time()

            # Bybit server time
            self.server_epoch_ms = int(res["time"])

            # Stable local monotonic clock
            self.monotonic_base = time.monotonic()

            self.last_sync = time.time()

            print(
                f"🕒 AUTO SYNC | "
                f"Server Epoch: {self.server_epoch_ms}"
            )

        except Exception as e:
            print(f"❌ Time sync failed: {e}")

    def now(self):
        # Refresh every 30 sec
        if time.time() - self.last_sync > 30:
            self.sync()

        elapsed_ms = int(
            (time.monotonic() - self.monotonic_base) * 1000
        )

        return self.server_epoch_ms + elapsed_ms