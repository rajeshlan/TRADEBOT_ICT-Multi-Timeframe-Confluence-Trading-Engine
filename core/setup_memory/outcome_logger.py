import json
from pathlib import Path

OUTCOMES_FILE = Path("storage/setup_outcomes.jsonl")


def append_outcome_event(event: dict):
    """
    Append-only lifecycle event logger.

    Every lifecycle mutation becomes:
    - execution event
    - telemetry event
    - closure event

    This creates a replayable event stream.
    """

    OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTCOMES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")