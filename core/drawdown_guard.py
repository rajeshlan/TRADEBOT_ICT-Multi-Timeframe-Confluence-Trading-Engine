from collections import deque


class DrawdownGuard:
    """
    Tracks recent performance and applies
    defensive behavior during drawdowns.
    """

    def __init__(self, max_history=10):
        self.recent_results = deque(maxlen=max_history)

    def register_result(self, pnl):
        self.recent_results.append(pnl)

    def recent_loss_count(self):
        return len([
            x for x in self.recent_results
            if x < 0
        ])

    def total_recent_pnl(self):
        return sum(self.recent_results)

    def should_reduce_risk(self):
        """
        Returns True if bot should become defensive.
        """

        if self.recent_loss_count() >= 4:
            return True

        if self.total_recent_pnl() <= -2.5:
            return True

        return False