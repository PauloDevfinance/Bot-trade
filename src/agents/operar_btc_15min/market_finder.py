import time
from src.agents.operar_btc_15min.config import WINDOW_SECONDS
def get_current_window():
    """Retorna timestamp de início da janela ativa e quanto falta pro fim."""
    now = int(time.time())
    window_start = now - (now % WINDOW_SECONDS)
    window_end = window_start + WINDOW_SECONDS
    seconds_remaining = window_end - now
    
    return {
        "start_ts": window_start,
        "end_ts": window_end,
        "seconds_remaining": seconds_remaining,
        "slug": f"btc-updown-15m-{window_start}"
    }


def time_until_next_window():
    """Segundos até a próxima janela começar."""
    now = int(time.time())
    return WINDOW_SECONDS - (now % WINDOW_SECONDS)


if __name__ == "__main__":
    w = get_current_window()
    print(f"Janela ativa: {w['slug']}")
    print(f"Termina em: {w['seconds_remaining']}s")