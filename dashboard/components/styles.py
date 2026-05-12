def load_css():
    """
    Returns the global CSS injection string for the Streamlit dashboard.
    Contains theme colors, layout structures, and interactive effects.
    """
    return """
    <style>

    html, body, [class*="css"] {
        background-color: #0b1220;
        color: #f8fafc;
    }

    .metric-card {
        background: rgba(15,23,42,0.88);
        border: 1px solid rgba(0,255,170,0.08);
        border-radius: 18px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 0 18px rgba(0,255,170,0.06);
    }

    .metric-title {
        font-size: 12px;
        opacity: 0.7;
        margin-bottom: 5px;
    }

    .metric-value {
        font-size: 28px;
        font-weight: 700;
    }

    .green {
        color: #00ffa3;
        font-weight: bold;
    }

    .red {
        color: #ff4d6d;
        font-weight: bold;
    }

    .feed-card {
        background: rgba(255,255,255,0.03);
        border-left: 4px solid #00ffa3;
        padding: 12px;
        border-radius: 12px;
        margin-bottom: 10px;
    }

    .risk-box {
        background: rgba(255,255,0,0.08);
        padding: 14px;
        border-radius: 12px;
        margin-top: 10px;
    }

    /* --- NEW UPGRADED CLASSES --- */

    .small-text {
        font-size: 12px;
        opacity: 0.7;
    }

    .glow {
        transition: all 0.2s ease;
    }

    .glow:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 24px rgba(0,255,170,0.12);
    }

    </style>
    """