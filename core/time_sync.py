import time

class TimeSync:
    def __init__(self, client):
        self.client = client
        self.offset = 0
        self.last_sync = 0

    def sync(self):
        try:
            res = self.client.get_server_time()
            server_time = int(res["time"])
            local_time = int(time.time() * 1000)

            self.offset = server_time - local_time
            self.last_sync = time.time()

            print(f"🕒 AUTO SYNC | Offset: {self.offset} ms")

        except Exception as e:
            print(f"❌ Time sync failed: {e}")

    def now(self):
        # refresh every 30 sec
        if time.time() - self.last_sync > 30:
            self.sync()

        return int(time.time() * 1000) + self.offset