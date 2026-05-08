from core.setup_memory.setup_schema import build_setup_snapshot
from core.setup_memory.setup_logger import register_setup


def register_signal_setup(signal):
    """
    Main orchestration layer for setup memory registration.
    """

    snapshot = build_setup_snapshot(signal)

    register_setup(snapshot)

    return snapshot