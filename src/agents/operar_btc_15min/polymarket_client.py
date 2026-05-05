import requests
from .config import GAMMA_HOST, CLOB_HOST


def buscar_mercado_15min(slug):
    """Busca o mercado ativo pelo slug na Gamma API."""
    url = f"{GAMMA_HOST}/markets"
    params = {
        "slug": slug,
        "limit": 1
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data and len(data) > 0:
            return data[0]
    except Exception as e:
        print(f"[ERRO] Busca por slug falhou: {e}")

    # Fallback: busca por keyword
    try:
        params = {
            "active": "true",
            "closed": "false",
            "limit": 20,
            "order": "startDate",
            "ascending": "false"
        }
        r = requests.get(url, params=params, timeout=10)
        mercados = r.json()

        for m in mercados:
            q = (m.get("question") or "").lower()
            if "btc" in q and ("15" in q or "fifteen" in q) and ("up" in q or "down" in q):
                return m
    except Exception as e:
        print(f"[ERRO] Busca fallback falhou: {e}")

    return None


def extrair_info_mercado(mercado):
    """Extrai dados relevantes do mercado."""
    if not mercado:
        return None

    import json

    outcomes = mercado.get("outcomes", [])
    prices = mercado.get("outcomePrices", [])

    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    if isinstance(prices, str):
        prices = json.loads(prices)

    info = {
        "question": mercado.get("question"),
        "condition_id": mercado.get("conditionId"),
        "market_slug": mercado.get("slug"),
        "end_date": mercado.get("endDate"),
        "active": mercado.get("active"),
        "outcomes": {},
        "volume": float(mercado.get("volume") or 0),
    }

    for label, price in zip(outcomes, prices):
        info["outcomes"][str(label).lower()] = round(float(price), 4)

    return info


def buscar_orderbook(token_id):
    """Busca orderbook do CLOB para um token específico."""
    url = f"{CLOB_HOST}/book"
    params = {"token_id": token_id}
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[ERRO] Orderbook: {e}")
        return None


if __name__ == "__main__":
    from .market_finder import get_current_window

    window = get_current_window()
    print(f"Janela: {window['slug']}")
    print(f"Termina em: {window['seconds_remaining']}s\n")

    mercado = buscar_mercado_15min(window["slug"])

    if mercado:
        info = extrair_info_mercado(mercado)
        print(f"Mercado: {info['question']}")
        print(f"Volume: ${info['volume']:,.0f}")
        for outcome, price in info["outcomes"].items():
            print(f"  {outcome.upper()}: ${price}")
    else:
        print("Nenhum mercado 15min encontrado.")
        print("(Pode ser que a Polymarket não tenha mercado ativo agora)")
