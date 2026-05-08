import json
from pathlib import Path

SETUPS_FILE = Path("storage/setup_snapshots.jsonl")


def register_setup(snapshot):
    """
    Append-only setup memory logger.

    JSONL format:
    One setup per line.
    ML-friendly.
    Replay-friendly.
    Streaming-friendly.
    """

    SETUPS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SETUPS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")