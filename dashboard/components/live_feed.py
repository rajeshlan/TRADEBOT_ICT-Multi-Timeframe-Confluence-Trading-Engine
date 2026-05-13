import streamlit as st
import time


EVENT_STYLES = {
    "SETUP_APPROVED": {
        "color": "#00ff99",
        "emoji": "🟢"
    },
    "SETUP_REJECTED": {
        "color": "#ff4b4b",
        "emoji": "🔴"
    },
    "SCAN_SKIPPED": {
        "color": "#ffaa00",
        "emoji": "⏳"
    },
    "SIGNAL_CREATED": {
        "color": "#00ccff",
        "emoji": "⚡"
    },
    "TRADE_EXECUTED": {
        "color": "#00e676",
        "emoji": "🚀"
    },
    "TRADE_CLOSED": {
        "color": "#b388ff",
        "emoji": "🏁"
    },
    "SYSTEM_LIMIT": {
        "color": "#ff9800",
        "emoji": "🛑"
    },
    "EXECUTION_FAILED": {
        "color": "#ff1744",
        "emoji": "💥"
    },
    "CORRELATION_WARNING": {
        "color": "#ffd54f",
        "emoji": "⚠️"
    }
}


def render_live_feed(event):

    event_type = event.get("event_type", "UNKNOWN")

    style = EVENT_STYLES.get(
        event_type,
        {
            "color": "#ffffff",
            "emoji": "📌"
        }
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

    for k, v in data.items():
        details += f"<b>{k}</b>: {v}<br>"

    html = f"""
    <div class="feed-card"
         style="border-left: 4px solid {color};">

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
            ">
                {readable_time}
            </div>

        </div>

        <div style="
            font-size:18px;
            font-weight:700;
            margin-bottom:8px;
        ">
            {symbol}
        </div>

        <div style="
            font-size:13px;
            line-height:1.5;
            opacity:0.92;
        ">
            {details}
        </div>

    </div>
    """

    st.markdown(
        html,
        unsafe_allow_html=True
    )