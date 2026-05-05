import requests
from .config import BINANCE_API

def get_btc_price():
    """Preço atual do BTC na Binance (spot)."""
    r = requests.get(f"{BINANCE_API}/ticker/price", 
                     params={"symbol": "BTCUSDT"}, 
                     timeout=5)
    return float(r.json()["price"])


def get_btc_klines(interval="1m", limit=20):
    """Candles recentes para análise."""
    r = requests.get(f"{BINANCE_API}/klines",
                     params={"symbol": "BTCUSDT", "interval": interval, "limit": limit},
                     timeout=5)
    klines = r.json()
    return [{
        "open_time": k[0],
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5])
    } for k in klines]


def get_price_at_window_open(window_start_ts):
    """Pega o preço de abertura do candle da janela."""
    r = requests.get(f"{BINANCE_API}/klines",
                     params={
                         "symbol": "BTCUSDT",
                         "interval": "1m",
                         "startTime": window_start_ts * 1000,
                         "limit": 1
                     },
                     timeout=5)
    return float(r.json()[0][1])  # open price


if __name__ == "__main__":
    print(f"BTC agora: ${get_btc_price():,.2f}")
    klines = get_btc_klines(limit=5)
    for k in klines:
        print(f"  Close: ${k['close']:,.2f}")