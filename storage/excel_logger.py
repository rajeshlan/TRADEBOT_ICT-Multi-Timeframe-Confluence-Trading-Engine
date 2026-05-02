import pandas as pd
from pathlib import Path

FILE = Path("storage/trade_history.xlsx")

def append_trade_to_excel(trade: dict):
    """
    Appends a closed trade to the Excel master ledger.
    Includes duplicate protection for safe resolver retries.
    """
    df_new = pd.DataFrame([trade])

    if FILE.exists():
        df_existing = pd.read_excel(FILE)
        df = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df = df_new

    # 👉 Prevents duplicate writes if the resolver retries
    df.drop_duplicates(subset=["id"], inplace=True)

    FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(FILE, index=False)