class ExecutionContext:
    """
    Controls runtime execution mode.

    Modes:
        LIVE
        REPLAY
        PAPER
    """

    VALID_MODES = {
        "LIVE",
        "REPLAY",
        "PAPER"
    }

    def __init__(self):
        self.mode = "LIVE"

    def set_mode(self, mode):
        if mode not in self.VALID_MODES:
            raise ValueError(f"Invalid mode: {mode}")

        self.mode = mode

    def is_live(self):
        return self.mode == "LIVE"

    def is_replay(self):
        return self.mode == "REPLAY"

    def is_paper(self):
        return self.mode == "PAPER"


execution_context = ExecutionContext()