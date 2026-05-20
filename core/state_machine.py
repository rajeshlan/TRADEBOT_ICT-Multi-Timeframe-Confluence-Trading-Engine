VALID_STATUS_TRANSITIONS = {
    "PENDING": {"EXECUTING", "ACTIVE", "FAILED", "CANCELLED"},
    "EXECUTING": {"PENDING", "ACTIVE", "FAILED", "CANCELLED"},
    "ACTIVE": {"CLOSED", "FAILED"},
    "FAILED": set(),
    "CANCELLED": set(),
    "CLOSED": set(),
}

VALID_EXECUTION_STATES = {
    "PENDING",
    "EXECUTING",
    "ACTIVE",
    "RETRYING",
    "FAILED",
    "CLOSED",
    "CANCELLED"
}


def transition_trade_status(trade: dict, new_status: str):
    """
    Safely transition trade lifecycle state.
    Prevents illegal state mutations.
    """

    current = trade.get("status", "PENDING")

    if current not in VALID_STATUS_TRANSITIONS:
        raise ValueError(f"Unknown current status: {current}")

    allowed = VALID_STATUS_TRANSITIONS[current]

    if new_status not in allowed:
        raise ValueError(
            f"Illegal transition: {current} -> {new_status}"
        )

    trade["status"] = new_status

    # Auto-sync helper flags
    if new_status == "ACTIVE":
        trade["is_active"] = True

    elif new_status in {"FAILED", "CANCELLED", "CLOSED"}:
        trade["is_active"] = False

    return trade


def set_execution_state(trade: dict, state: str):
    """
    Validates execution_state mutations.
    """

    if state not in VALID_EXECUTION_STATES:
        raise ValueError(f"Invalid execution state: {state}")

    trade["execution_state"] = state
    return trade
