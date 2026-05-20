import json
import os
import time

from core.ids import new_event_id

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
    data = data or {}

    payload = {
        "event_id": new_event_id("evt"),
        "timestamp": int(time.time()),
        "event_type": event_type,
        "symbol": symbol,
        "setup_id": data.get("setup_id"),
        "decision_id": data.get("decision_id"),
        "order_intent_id": data.get("order_intent_id"),
        "trade_uuid": data.get("trade_uuid"),
        "data": data
    }

    events.append(payload)

    save_runtime_events(events)
