import streamlit as st
import time
import json
import html

# Standardized event styling, visual encodings, and priority flags
EVENT_STYLES = {
    "PROTECTION_WARNING": {"color": "#ff6d00", "emoji": "🚨"},
    "NEGATIVE_EXPECTANCY_GATE": {"color": "#ff7043", "emoji": "🚫"},
    "SETUP_APPROVED": {"color": "#00ff99", "emoji": "🟢"},
    "SETUP_REJECTED": {"color": "#ff4b4b", "emoji": "🔴"},
    "SCAN_SKIPPED": {"color": "#ffaa00", "emoji": "⏭"},
    "SIGNAL_CREATED": {"color": "#00ccff", "emoji": "⚡"},
    "TRADE_EXECUTED": {"color": "#00e676", "emoji": "🚀"},
    "TRADE_CLOSED": {"color": "#b388ff", "emoji": "📘"},
    "SYSTEM_LIMIT": {"color": "#ff9800", "emoji": "🛑"},
    "EXECUTION_FAILED": {"color": "#ff1744", "emoji": "💥"},
    "CORRELATION_WARNING": {"color": "#ffd54f", "emoji": "⚠️"},
    "SYMBOL_SKIPPED": {"color": "#aaaaaa", "emoji": "⏭️"}
}

# Persistent in-memory storage to track execution cooldowns across reruns
LAST_RENDERED_EVENT = {}

def should_render_event(event_type: str, cooldown: int = 30) -> bool:
    """
    Evaluates whether an event should be rendered based on its cooling window
    to safeguard dashboard performance from high-frequency telemetry spam.
    """
    # Only enforce cooldown filtering on aggressive system status loops
    if event_type not in ["SYSTEM_LIMIT", "SCAN_SKIPPED"]:
        return True

    now = time.time()
    if event_type in LAST_RENDERED_EVENT:
        if now - LAST_RENDERED_EVENT[event_type] < cooldown:
            return False

    LAST_RENDERED_EVENT[event_type] = now
    return True


def render_live_feed(event):
    """
    Renders a structural layout card for a single engine runtime event.
    Guarantees structural validity using deep serialization and character escaping.
    """
    event_type = event.get("event_type", "UNKNOWN")

    # Drop high-frequency spam events if they fall within the cooldown threshold
    if not should_render_event(event_type, cooldown=30):
        return

    style = EVENT_STYLES.get(
        event_type,
        {"color": "#ffffff", "emoji": "📌"}
    )

    color = style["color"]
    emoji = style["emoji"]

    symbol = event.get("symbol", "SYSTEM")
    data = event.get("data", {})
    ts = event.get("timestamp", int(time.time()))

    readable_time = time.strftime(
        "%H:%M:%S",
        time.localtime(ts)
    )

    details = ""

    # Safely convert, serialize, and escape dictionary telemetry values
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, indent=2)

        # Escape brackets and control marks to lock variables within text boundaries
        v = html.escape(str(v))

        details += f"""
        <div style="margin-bottom:4px; font-family: monospace;">
            <span style="color:#9ca3af; font-weight:600;">{k}</span>: 
            <span style="color:#e5e7eb; white-space: pre-wrap;">{v}</span>
        </div>
        """

    html_card = f"""
    <div style="
        background:#111827;
        border-left:4px solid {color};
        padding:14px;
        border-radius:10px;
        margin-bottom:12px;
    ">
        <div style="
            display:flex;
            justify-content:space-between;
            align-items:center;
            margin-bottom:8px;
        ">
            <div style="
                font-weight:bold;
                color:{color};
                font-size:16px;
            ">
                {emoji} {event_type}
            </div>
            <div style="
                font-size:12px;
                opacity:0.7;
                color:white;
            ">
                {readable_time}
            </div>
        </div>

        <div style="
            font-size:18px;
            font-weight:700;
            margin-bottom:8px;
            color:white;
        ">
            {symbol}
        </div>

        <div style="
            font-size:13px;
            line-height:1.6;
            color:#d1d5db;
        ">
            {details}
        </div>
    </div>
    """

    st.markdown(
        html_card,
        unsafe_allow_html=True
    )