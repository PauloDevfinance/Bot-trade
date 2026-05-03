import requests
import pandas as pd

base = "https://data-api.polymarket.com/v1/leaderboard"

limit = 20
max_offset = 1000

rows = []

for offset in range(0, max_offset, limit):
    params = {
        "category": "OVERALL",
        "timePeriod": "ALL",
        "orderBy": "PNL",
        "limit": limit,
        "offset": offset
    }

    r = requests.get(base, params=params)
    data = r.json()

    if not data:
        break

    rows.extend(data)

df = pd.DataFrame(rows).drop_duplicates(subset=["proxyWallet"])
df["proxyWallet"].to_csv("wallets.txt", index=False, header=False)
print("Total coletado:", len(df))
print(df.head())