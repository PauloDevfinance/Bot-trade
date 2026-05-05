import os
from dotenv import load_dotenv

load_dotenv("/home/paulo/trading-bot/.env")

# Polymarket
POLYGON_RPC = os.getenv("POLYGON_RPC")
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

# Binance (preço de referência)
BINANCE_API = "https://api.binance.com/api/v3"


# Trading
WINDOW_SECONDS = 900  # 15 minutos
ENTRY_TIME_BEFORE_CLOSE = 120  # T-120s (2 min antes do fim)
EXECUTION_TIME_BEFORE_CLOSE = 90  # T-90s executa

# Risco
PAPER_TRADING = True
CAPITAL_USD = 100
MAX_POSITION_PCT = 0.05
MIN_FILL_PRICE = 0.30  # abaixo disso mercado muito incerto
MAX_FILL_PRICE = 0.70
MIN_DELTA_PCT = 0.05  # BTC precisa ter andado pelo menos 0.05%  # acima disso sem margem suficiente

# Logging
LOG_FILE = "/home/paulo/trading-bot/logs/btc_15min.log"
TRADES_FILE = "/home/paulo/trading-bot/logs/trades.csv"