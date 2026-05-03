import anthropic
import requests
import json
import os
import re
from dotenv import load_dotenv
import time
from datetime import date
import yfinance as yf





load_dotenv(dotenv_path="/home/paulo/trading-bot/.env")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def match_keyword(texto, keywords):
    """
    Faz match mais seguro:
    - palavras simples: usa regex com borda de palavra
    - expressões com espaço: usa busca direta
    """
    texto = (texto or "").lower()

    for k in keywords:
        k = k.lower().strip()
        if " " in k:
            if k in texto:
                return True
        else:
            if re.search(rf"\b{re.escape(k)}\b", texto):
                return True
    return False


def buscar_mercados_raw(limit=1000):
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit,
        "order": "volume",
        "ascending": "false"
    }

    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Erro na API: {resp.status_code}")

    return resp.json()




def preparar_mercados(mercados, categorias_escolhidas, volume_minimo=100000, top_n=15):
    categorias = {
        "crypto": [
            "bitcoin", "btc", "ethereum", "eth", "solana", "bnb",
            "crypto market", "cryptocurrency", "defi", "blockchain", "stablecoin"
        ],
        "macro": [
            "inflation", "fed", "interest", "economy", "rate", "m2", "liquidity",
            "cpi", "pce", "gdp", "recession"
        ],
        "politica": [
            "election", "president", "senate", "government", "congress", "white house", "recession", "tariff", "jobs", "yield", "payroll", "Uneployment", "treasury",
            "trade"
        ],
        "tech": [
            "ai", "openai", "google", "meta", "model", "llm", "artificial intelligence"
        ],
        "clima": [
            "weather", "temperature", "rainfall", "precipitation", "hurricane",
            "snowfall", "forecast", "celsius", "fahrenheit"
        ]
    }

    # blacklist opcional para remover mercados que você já sabe que dão falso positivo
    blacklist = [
        "microstrategy sells",
        "saylor sells",
    ]

    keywords = []
    for cat in categorias_escolhidas:
        keywords.extend(categorias.get(cat, []))

    filtrados = []

    for m in mercados:
        pergunta = (m.get("question") or "").lower()
        descricao = (m.get("description") or "").lower()
        texto = f"{pergunta} {descricao}"

        # blacklist primeiro
        if any(b in texto for b in blacklist):
            continue

        # filtro por categoria
        if not match_keyword(texto, keywords):
            continue

        # filtro por volume
        try:
            volume = float(m.get("volume") or 0)
        except Exception as e:
            print(f"[ERRO volume] {e}")
            continue

        if volume < volume_minimo:
            continue

        filtrados.append({
            "question": m.get("question"),
            "volume": round(volume, 2),
            "end_date": (m.get("endDate") or "")[:10],
            "description": (m.get("description") or "")[:300],
            "outcomes": m.get("outcomes"),
            "probabilidades": m.get("outcomePrices"),
        })

    filtrados.sort(key=lambda x: x["volume"], reverse=True)
    return filtrados[:top_n]












def analisar_mercado_com_claude(mercado, contexto_btc=None):
    prob_yes, prob_no, _ = extrair_probs(mercado)
    prob_mercado = prob_yes if prob_yes is not None else 50

    contexto_extra = f"\nContexto atual:\n{contexto_btc}" if contexto_btc else ""

    prompt = f"""Você é um trader quantitativo especializado em mercados de predição. Data de hoje: {date.today().strftime('%d/%m/%Y')}
    Sua tarefa é estimar a probabilidade real do evento acontecer.

{contexto_extra}

MERCADO:
Pergunta: {mercado['question']}
Volume: ${mercado['volume']:,.0f}
Encerra: {mercado['end_date']}
Probabilidade YES no mercado: {prob_mercado}%
Descrição: {mercado['description']}

Responda APENAS em JSON válido sem nenhum texto antes ou depois:
{{
  "probabilidade_estimada": <0-100>,
  "confianca": "<alta|media|baixa>",
  "razao": "<2 frases>"
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    texto = response.content[0].text.strip()
    print(f"  [DEBUG] Resposta Claude: {texto[:200]}")

    try:
        if "```" in texto:
            texto = texto.split("```")[1].replace("json", "").strip()
        return json.loads(texto)
    except Exception as e:
        print(f"  [DEBUG] Erro parse JSON: {e}")
        return {"erro": texto}






def extrair_probs(mercado):
    try:
        outcomes = mercado.get("outcomes")
        probs = mercado.get("probabilidades")

        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)

        if isinstance(probs, str):
            probs = json.loads(probs)

        if not outcomes or not probs:
            return None, None, None

        mapa = {}
        for label, p in zip(outcomes, probs):
            mapa[str(label).lower()] = round(float(p) * 100, 1)

        prob_yes = mapa.get("yes")
        prob_no = mapa.get("no")

        return prob_yes, prob_no, mapa

    except Exception as e:
        print(f"[DEBUG] erro em extrair_probs: {e}")
        return None, None, None
    





def rodar_agente_polymarket(contexto_btc=None, categorias_teste=None, volume_minimo=100000, top_n=10, categoria="macro"):
    if categorias_teste is None:
        categorias_teste = [categoria]

    print("Buscando mercados do Polymarket...")
    mercados = buscar_mercados_raw(limit=1000)
    print(f"Encontrados {len(mercados)} mercados brutos\n")

    mercados_filtrados = preparar_mercados(
        mercados=mercados,
        categorias_escolhidas=categorias_teste,
        volume_minimo=volume_minimo,
        top_n=top_n
    )

    print(f"Após filtro {categorias_teste}: {len(mercados_filtrados)} mercados\n")

    oportunidades = []

    for m in mercados_filtrados:
        pergunta = (m["question"] or "").lower()

        if match_keyword(pergunta, ["btc", "bitcoin", "crypto", "ethereum"]):
            contexto = contexto_btc
        else:
            contexto = None

        analise = analisar_mercado_com_claude(m, contexto)

        if "erro" in analise:
            continue

        prob_yes, prob_no, _ = extrair_probs(m)
        prob_mercado = prob_yes

        try:
            prob_modelo = float(analise.get("probabilidade_estimada", 50))
        except Exception as e:
            print(f"  ❌ Erro lendo probabilidade_estimada: {e}")
            continue

        edge_raw = prob_modelo - (prob_mercado if prob_mercado is not None else 50)
        edge_abs = abs(edge_raw)

        confianca = analise.get("confianca", "baixa")
        razao = analise.get("razao", "")
        decisao = "comprar_sim" if edge_raw > 0 else "comprar_nao" if edge_raw < 0 else "neutro"

        print(f"Mercado: {m['question'][:70]}")
        print(f"  YES:     {prob_yes}% | NO: {prob_no}%")
        print(f"  Modelo:  {prob_modelo}%")
        print(f"  Edge:    {edge_raw:.1f}%")
        print(f"  Ação:    {'BUY YES' if decisao == 'comprar_sim' else 'BUY NO' if decisao == 'comprar_nao' else 'HOLD'}")
        print(f"  Conf:    {confianca}")

        if edge_abs > 40:
            print("  ❌ Ignorado: edge irrealista (>40%)")
            print("-" * 70)
            continue

        if not (
            edge_abs >= 12
            and edge_abs <= 35
            and decisao in ["comprar_sim", "comprar_nao"]
            and (
                confianca == "alta"
                or (confianca == "media" and edge_abs >= 20)
            )
        ):
            print("  ❌ Ignorado: não passou nos critérios (edge/confiança)")
            print("-" * 70)
            continue

        if prob_modelo < 0 or prob_modelo > 100:
            print("  ❌ Ignorado: probabilidade inválida")
            print("-" * 70)
            continue

        print("  ✅ OPORTUNIDADE DETECTADA")
        print(f"  Razão: {razao}")
        print("-" * 70)

        oportunidades.append({
            "mercado": m["question"],
            "volume": m["volume"],
            "decisao": decisao,
            "acao": "BUY YES" if decisao == "comprar_sim" else "BUY NO" if decisao == "comprar_nao" else "HOLD",
            "edge": edge_raw,
            "edge_abs": edge_abs,
            "confianca": confianca,
            "prob_mercado": prob_mercado,
            "prob_no": prob_no,
            "prob_modelo": prob_modelo,
            "razao": razao
        })

        
        time.sleep(0.5)

    print(f"\n{'='*70}")
    print(f"OPORTUNIDADES ENCONTRADAS: {len(oportunidades)}")
    print(f"{'='*70}")

    for op in oportunidades:
        print(f"\n{'='*60}")
        print(f"Mercado: {op['mercado'][:70]}")
        print(f"YES: {op['prob_mercado']}% | NO: {op['prob_no']}%")
        print(f"Modelo: {op['prob_modelo']}%")
        print(f"Edge: {op['edge']:.1f}%")
        print(f"Ação: {op['acao']}")
        print(f"Conf: {op['confianca']}")
        print(f"Razão: {op['razao']}")

    return oportunidades








def gerar_contexto_btc():
    try:
        
        btc = yf.download("BTC-USD", period="30d", interval="1d", progress=False)
        btc.columns = [c[0] if isinstance(c, tuple) else c for c in btc.columns]
        
        preco = float(btc["Close"].iloc[-1])
        retorno_7d = float((btc["Close"].iloc[-1] / btc["Close"].iloc[-7] - 1) * 100)
        retorno_30d = float((btc["Close"].iloc[-1] / btc["Close"].iloc[0] - 1) * 100)

        fg_url = "https://api.alternative.me/fng/?limit=1&format=json"
        fg = requests.get(fg_url).json()
        fear_greed = int(fg["data"][0]["value"])
        fg_label = fg["data"][0]["value_classification"]

        return f"""Contexto de mercado atual:
- BTC preço: ${preco:,.0f}
- BTC retorno 7 dias: {retorno_7d:.1f}%
- BTC retorno 30 dias: {retorno_30d:.1f}%
- Regime HMM: Lateral (50.5% chance de continuar, 34.2% de virar Bull)
- Fear & Greed: {fear_greed} ({fg_label})
- Fed Rate: 4.33% sem cortes previstos
- Contexto macro: guerra comercial EUA/China, tarifas Trump, incerteza geopolítica"""
    except Exception as e:
        print(f"Erro ao gerar contexto: {e}")
        return "Contexto BTC: mercado lateral, incerteza macro alta"

if __name__ == "__main__":
    contexto = gerar_contexto_btc()
    print("Contexto gerado:")
    print(contexto)
    print()
    rodar_agente_polymarket(contexto_btc=contexto, categoria="politica")
    # categorias --> crypto, macro, politica, tech, clima
