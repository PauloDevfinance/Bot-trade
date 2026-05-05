import time
from web3 import Web3
from .config import POLYGON_RPC

CHAINLINK_BTC_ADDRESS = "0xc907E116054Ad103354f2D350FD2514433D57F6f"

ABI = [{
    "inputs": [],
    "name": "latestRoundData",
    "outputs": [
        {"name": "roundId", "type": "uint80"},
        {"name": "answer", "type": "int256"},
        {"name": "startedAt", "type": "uint256"},
        {"name": "updatedAt", "type": "uint256"},
        {"name": "answeredInRound", "type": "uint80"}
    ],
    "stateMutability": "view",
    "type": "function"
}]

w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
contrato = w3.eth.contract(address=CHAINLINK_BTC_ADDRESS, abi=ABI)

# ─── Cache ───
_cache = {
    "preco": None,
    "atualizado_ha": None,
    "timestamp_local": 0
}
CACHE_TTL = 20  # segundos


def get_chainlink_price():
    global _cache

    agora = time.time()

    # Retorna cache se ainda válido
    if _cache["preco"] and (agora - _cache["timestamp_local"]) < CACHE_TTL:
        return {
            "preco": _cache["preco"],
            "atualizado_ha": _cache["atualizado_ha"],
            "fresco": _cache["atualizado_ha"] < 120,
            "fonte": "cache"
        }

    # Busca novo dado
    try:
        dados = contrato.functions.latestRoundData().call()
        preco = dados[1] / 1e8
        atualizado_em = dados[3]
        segundos_atras = int(agora) - atualizado_em

        _cache = {
            "preco": round(preco, 2),
            "atualizado_ha": segundos_atras,
            "timestamp_local": agora
        }

        return {
            "preco": _cache["preco"],
            "atualizado_ha": segundos_atras,
            "fresco": segundos_atras < 120,
            "fonte": "chainlink"
        }

    except Exception as e:
        print(f"\n[AVISO] Chainlink indisponível: {e}")

        # Retorna cache antigo se existir
        if _cache["preco"]:
            print(f"[AVISO] Usando cache antigo (${_cache['preco']:,.2f})")
            return {
                "preco": _cache["preco"],
                "atualizado_ha": _cache["atualizado_ha"],
                "fresco": False,
                "fonte": "cache_antigo"
            }

        return None


def comparar_com_binance(preco_binance):
    cl = get_chainlink_price()
    if not cl:
        return None

    divergencia = abs(preco_binance - cl["preco"]) / cl["preco"] * 100

    return {
        "binance": preco_binance,
        "chainlink": cl["preco"],
        "divergencia_pct": round(divergencia, 4),
        "seguro_operar": divergencia < 0.3 and cl["fresco"]
    }


def get_price_snapshot():
    from .price_feed import get_btc_price

    binance = get_btc_price()
    cl = get_chainlink_price()

    if not cl:
        return {
            "binance": binance,
            "chainlink": None,
            "divergencia_pct": None,
            "divergencia_usd": None,
            "status": "⚠️ Chainlink indisponível — usando Binance"
        }

    divergencia_pct = ((binance - cl["preco"]) / cl["preco"]) * 100
    divergencia_usd = binance - cl["preco"]

    if abs(divergencia_pct) < 0.1:
        status = "✅ Sincronizados"
    elif abs(divergencia_pct) < 0.3:
        status = "⚠️  Divergência leve"
    else:
        status = "🔴 Divergência alta"

    # Indica se veio do cache
    if cl.get("fonte") == "cache_antigo":
        status += " [cache antigo]"

    return {
        "binance": binance,
        "chainlink": cl["preco"],
        "chainlink_age": cl["atualizado_ha"],
        "divergencia_pct": round(divergencia_pct, 4),
        "divergencia_usd": round(divergencia_usd, 2),
        "status": status
    }


if __name__ == "__main__":
    print("Testando Chainlink com cache...")

    if not w3.is_connected():
        print("❌ Sem conexão com Polygon RPC")
    else:
        print(f"✅ Conectado ao bloco #{w3.eth.block_number}")

        for i in range(3):
            snap = get_price_snapshot()
            print(f"\n[{i+1}] BN: ${snap['binance']:,.2f} | CL: ${snap['chainlink']:,.2f} | {snap['status']}")
            time.sleep(5)
