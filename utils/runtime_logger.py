import json
import os
import time

RUNTIME_LOG_PATH = "storage/runtime_events.json"

MAX_EVENTS = 1500


def load_runtime_events():
    if not os.path.exists(RUNTIME_LOG_PATH):
        return []

    try:
        with open(RUNTIME_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_runtime_events(events):
    with open(RUNTIME_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(events[-MAX_EVENTS:], f, indent=2)


def log_runtime_event(event_type, symbol=None, data=None):
    events = load_runtime_events()

    payload = {
        "timestamp": int(time.time()),
        "event_type": event_type,
        "symbol": symbol,
        "data": data or {}
    }

    events.append(payload)

    save_runtime_events(events)