📊 TRADEBOT_ICT — Multi-Timeframe Confluence Trading Engine
🚀 Overview

TRADEBOT_ICT is a modular, rule-based trading intelligence system designed to detect high-probability trading opportunities using ICT concepts, multi-timeframe confluence, and liquidity analysis.

It operates as a manual trading assistant, generating structured trade alerts (via Telegram), tracking trade performance, and dynamically adjusting risk using a Kelly Criterion-based model.

This system is built for precision, discipline, and measurable edge, not signal spam.


🧠 Core Philosophy

The system follows a strict hierarchy:

HTF Bias → LTF Entry → Liquidity Confirmation → Risk Allocation → Execution → Tracking

It only produces signals when:

Market structure aligns across timeframes
Order blocks confirm direction
Liquidity narrative supports the move
Risk conditions are valid


⚙️ Key Features
1️⃣ Signal Engine
Detects ICT-based setups using:
Order Blocks (OB)
Fair Value Gaps (FVG)
Liquidity zones (buy-side / sell-side)
Multi-timeframe analysis:
5m, 30m, 2h, 4h, 1D (configurable)
2️⃣ Multi-Timeframe Confluence
HTF defines bias (1D / 4H / 1M)
LTF confirms entry (5m / 30m)
Signals require:
Minimum multi-TF agreement
HTF + LTF alignment
3️⃣ Liquidity Engine (ICT-based)
Detects:
Equal highs / lows
Resting liquidity zones
Liquidity sweeps
Adds scoring weight based on:
Presence
Directional alignment
Sweep events (higher confidence)
4️⃣ Discipline Engine

Strict filtering rules:

Minimum confluence threshold
Mandatory liquidity presence
HTF + LTF alignment required
Cooldown system:
Per-symbol cooldown
Per-bias cooldown

This prevents:

❌ Overtrading
❌ Signal spam
❌ Low-quality setups
5️⃣ Signal Scoring System

Each timeframe contributes weighted score:

1M > 1D > 4H > 2H > 30m > 5m

Additional boosts:

Liquidity presence
Liquidity sweeps
Narrative alignment
6️⃣ Telegram Alert System
Real-time alerts for valid setups
Structured output:
Pair
Bias (Bullish / Bearish)
Timeframes involved
Entry / SL / TP
Risk (Kelly-adjusted)
Risk-to-reward ratio

Example:

🚨 CONFLUENCE ALERT

Pair: ETHUSDT
Bias: BULLISH
Timeframes: 5m, 30m, 2h, 4h

Score: 101
Risk: 25%

Entry: 2252.42
SL: 2245.82
TP: 2265.62
RR: 1:2
7️⃣ Risk Model (Kelly Criterion)

Dynamic risk sizing based on performance:

f = W - (1-W)/R

Where:

W = win rate
R = reward-to-risk ratio

Features:

Auto-adjusts position size
Max risk cap (default: 25%)
Falls back to safe risk when data is insufficient
8️⃣ Trade Lifecycle Tracking

Every signal becomes a tracked trade:

OPEN → ACTIVE → CLOSED → RESULT (WIN / LOSS)

Stored in:

storage/trades.json

Each trade includes:

Entry / SL / TP
Risk used
Timestamp
Outcome
9️⃣ Trade Resolver (Paper Execution)
Continuously checks price
Determines:
TP hit → WIN
SL hit → LOSS
Closes trades automatically
🔟 Performance Analytics Engine

Tracks:

Total trades
Wins / losses
Win rate
Equity growth
Risk impact
📊 Dashboard (Streamlit)

Live performance dashboard includes:

Total trades
Win rate
Final equity
Net return
Equity growth curve

Helps answer:

Is the system profitable or not? 



project structure


alert_system_strategies/
│
├── alerts/               # Telegram + formatting
├── config/               # Pairs & settings
├── data/                 # Candle fetching
├── engine/               # Evaluator + signal manager
├── strategies/ict/       # OB, FVG, liquidity logic
├── analytics/            # Performance stats
├── storage/              # Trade logs
├── dashboard/            # Streamlit UI
├── utils/                # Logging utilities
├── main.py               # Orchestrator



🔄 Workflow
1. Fetch candles (Binance)
2. Run strategies (OB, FVG, Liquidity)
3. Evaluate confluence
4. Score setup
5. Apply discipline filters
6. Generate signal
7. Send Telegram alert
8. Log trade
9. Track trade outcome
10. Update analytics + dashboard



⚠️ Important Notes
This is a decision-support system, not a guaranteed profit tool
Early performance (few trades) is statistically unreliable
Kelly sizing becomes meaningful only after sufficient data
🧪 Current Capabilities

✔ Multi-timeframe ICT confluence
✔ Liquidity-aware signal filtering
✔ Dynamic risk adjustment (Kelly)
✔ Trade lifecycle automation
✔ Performance tracking
✔ Live dashboard visualization

🚀 Future Roadmap
Advanced analytics (drawdown, expectancy)
Portfolio-level risk management
Multi-symbol concurrent execution
Real exchange execution (optional)
Strategy modular expansion
🎯 Intended Use

This system is built for:

Manual traders seeking structured signals
Developers building trading intelligence tools
Strategy testing and edge validation
Learning ICT + systematic trading
📌 Final Note

This is not just a signal bot —
it is a framework for building and validating trading edge.
