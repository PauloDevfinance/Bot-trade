from .price_feed import get_btc_price, get_price_at_window_open
from .chainlink_feed import get_chainlink_price, comparar_com_binance
from .config import MAX_FILL_PRICE

MIN_DELTA_PCT = 0.05

def calcular_confianca(delta_pct_abs, token_price):
    if delta_pct_abs > 0.40:
        conf_delta = "alta"
    elif delta_pct_abs > 0.15:
        conf_delta = "media"
    elif delta_pct_abs > MIN_DELTA_PCT:
        conf_delta = "baixa"
    else:
        return "skip"

    if token_price < 0.45:
        return conf_delta
    elif token_price <= 0.70:
        return conf_delta
    else:
        if conf_delta == "alta":
            return "media"
        else:
            return "baixa"


def calcular_sinal(window_start_ts, outcomes):
    # Preço de abertura via Binance (histórico)
    preco_abertura = get_price_at_window_open(window_start_ts)

    # Preço atual: usa Chainlink se disponível, senão Binance
    cl = get_chainlink_price()
    preco_atual_binance = get_btc_price()

    if cl and cl["fresco"]:
        preco_atual = cl["preco"]
        fonte = "Chainlink"

        # Verifica divergência
        comp = comparar_com_binance(preco_atual_binance)
        if comp and not comp["seguro_operar"]:
            return {
                "acao": "SKIP",
                "razao": f"Divergência alta Binance/Chainlink ({comp['divergencia_pct']:.3f}%) — aguarda sincronizar",
                "preco_abertura": round(preco_abertura, 2),
                "preco_atual": round(preco_atual, 2),
                "delta": 0,
                "delta_pct": 0
            }
    else:
        preco_atual = preco_atual_binance
        fonte = "Binance (fallback)"

    delta = preco_atual - preco_abertura
    delta_pct = (delta / preco_abertura) * 100
    delta_pct_abs = abs(delta_pct)

    direcao = "up" if delta > 0 else "down" if delta < 0 else None

    if direcao is None or delta_pct_abs < MIN_DELTA_PCT:
        return {
            "acao": "SKIP",
            "razao": f"Delta muito fraco ({delta_pct:.4f}%) — sem sinal",
            "delta": round(delta, 2),
            "delta_pct": round(delta_pct, 4),
            "preco_abertura": round(preco_abertura, 2),
            "preco_atual": round(preco_atual, 2),
            "fonte": fonte
        }

    token_price = outcomes.get(direcao, 0.5)

    if token_price > MAX_FILL_PRICE:
        return {
            "acao": "SKIP",
            "razao": f"Token {direcao.upper()} muito caro (${token_price:.4f}) — sem margem",
            "direcao": direcao,
            "delta": round(delta, 2),
            "delta_pct": round(delta_pct, 4),
            "token_price": token_price,
            "preco_abertura": round(preco_abertura, 2),
            "preco_atual": round(preco_atual, 2),
            "fonte": fonte
        }

    confianca = calcular_confianca(delta_pct_abs, token_price)

    if confianca == "skip":
        return {
            "acao": "SKIP",
            "razao": f"Delta fraco com token caro — sem edge",
            "direcao": direcao,
            "delta": round(delta, 2),
            "delta_pct": round(delta_pct, 4),
            "token_price": token_price,
            "preco_abertura": round(preco_abertura, 2),
            "preco_atual": round(preco_atual, 2),
            "fonte": fonte
        }

    lucro_potencial = round(1 - token_price, 4)
    roi = round((lucro_potencial / token_price) * 100, 1)

    return {
        "acao": f"BUY {direcao.upper()}",
        "direcao": direcao,
        "token_price": token_price,
        "delta": round(delta, 2),
        "delta_pct": round(delta_pct, 4),
        "confianca": confianca,
        "preco_abertura": round(preco_abertura, 2),
        "preco_atual": round(preco_atual, 2),
        "lucro_potencial": lucro_potencial,
        "roi_pct": roi,
        "fonte": fonte,
        "razao": (
            f"BTC {'subiu' if delta > 0 else 'caiu'} {abs(delta_pct):.3f}% [{fonte}] | "
            f"Token {direcao.upper()} a ${token_price:.4f} | ROI potencial: {roi}%"
        )
    }
