import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv("/home/paulo/trading-bot/.env")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ─── Helper: chamada com retry ────────────────────────────
def chamar_gemini(prompt, tentativas=3):
    for i in range(tentativas):
        try:
            resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return resp.text
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e) or "overloaded" in str(e):
                espera = 5 * (i + 1)
                print(f"  [Gemini] 503 — retry em {espera}s... ({i+1}/{tentativas})")
                time.sleep(espera)
            else:
                print(f"  [Gemini] Erro: {e}")
                return None
    print("  [Gemini] Falhou após todas tentativas")
    return None

# ─── Filtro 1: Keywords locais (grátis) ───────────────────
KEYWORDS_POR_ATIVO = {
    "btc":        ["bitcoin", "btc", "satoshi", "saylor", "microstrategy", "mstr"],
    "crypto":     ["ethereum", "eth", "solana", "crypto", "cripto", "defi", "altcoin",
                   "token", "blockchain", "stablecoin", "binance", "coinbase"],
    "macro":      ["fed", "fomc", "interest rate", "taxa de juros", "inflation", "inflação",
                   "cpi", "pce", "gdp", "pib", "recession", "recessão",
                   "treasury", "yield", "dollar", "dólar", "dxy", "m2", "liquidity", "liquidez"],
    "politica":   ["trump", "tariff", "tarifa", "trade war", "guerra comercial",
                   "sanction", "sanção", "sancionar", "sec", "regulation", "regulação",
                   "regulamentar", "congress", "congresso", "white house", "casa branca",
                   "election", "eleição", "government", "governo", "legislação", "lei"],
    "commodities":["gold", "ouro", "silver", "prata", "oil", "petróleo", "crude",
                   "wti", "brent", "opec", "natural gas", "gás natural",
                   "wheat", "trigo", "corn", "milho", "xau", "xag",
                   "irã", "iran", "oriente médio", "middle east", "embargo"],
    "risco":      ["hack", "exploit", "liquidat", "crash", "dump", "collapse", "colapso",
                   "bankrupt", "falência", "arrest", "preso", "fraud", "fraude",
                   "ban", "proibição", "emergency", "emergência", "guerra", "war",
                   "ataque", "attack", "míssil", "missile", "embarcações", "naval"],
}

URGENCIA_KEYWORDS = ["breaking", "urgent", "just in", "alert", "flash", "now:", "⚡", "🚨", "🔴"]


def filtro_keyword(texto):
    texto_lower = texto.lower()
    ativos = []
    for ativo, keywords in KEYWORDS_POR_ATIVO.items():
        for kw in keywords:
            if kw in texto_lower:
                if ativo not in ativos:
                    ativos.append(ativo)
                break
    return ativos


def tem_urgencia(texto):
    texto_lower = texto.lower()
    return any(u in texto_lower for u in URGENCIA_KEYWORDS)


# ─── Filtro 2: Gemini sim/não ────────────────────────────
def filtro_relevancia(texto, ativos):
    ativos_str = ", ".join(ativos)
    prompt = f"""Você é um filtro de notícias para trading. Analise esta mensagem:

"{texto[:300]}"

Ativos possivelmente afetados: {ativos_str}

Esta notícia tem impacto IMEDIATO no preço nos próximos 15-60 minutos?
Responda APENAS: sim ou nao"""

    resposta = chamar_gemini(prompt)
    if not resposta:
        return False
    return "sim" in resposta.strip().lower()


# ─── Filtro 3: Gemini análise completa ───────────────────
def analisar_noticia(texto, ativos, tier):
    ativos_str = ", ".join(ativos)
    prompt = f"""Você é um analista de trading. Analise esta notícia:

"{texto[:500]}"

Ativos possivelmente afetados: {ativos_str}
Fonte: Tier {tier} ({"alta" if tier == 1 else "média"} confiabilidade)

Responda APENAS em JSON válido sem nenhum texto antes ou depois:
{{
  "direcao": "<bullish|bearish|neutro>",
  "ativos": ["<lista dos ativos afetados>"],
  "urgencia": <1-5>,
  "duracao": "<imediato|horas|dias>",
  "confianca": "<alta|media|baixa>",
  "resumo": "<1 frase>"
}}"""

    resposta = chamar_gemini(prompt)
    if not resposta:
        return None
    try:
        texto_resp = resposta.strip()
        if "```" in texto_resp:
            texto_resp = texto_resp.split("```")[1].replace("json", "").strip()
        return json.loads(texto_resp)
    except Exception as e:
        print(f"  [classifier] Erro parse JSON: {e}")
        return None


# ─── Pipeline completo ────────────────────────────────────
def classificar(texto, tier=2):
    if not texto or len(texto.strip()) < 10:
        return None

    ativos = filtro_keyword(texto)
    if not ativos:
        return None

    urgente = tem_urgencia(texto)

    # Tier 1 pula filtro 2
    if tier > 1 and not filtro_relevancia(texto, ativos):
        return None

    analise = analisar_noticia(texto, ativos, tier)
    if not analise:
        return None

    return {
        "texto_original": texto[:200],
        "tier": tier,
        "urgente": urgente,
        "ativos": analise.get("ativos", ativos),
        "direcao": analise.get("direcao", "neutro"),
        "urgencia": analise.get("urgencia", 1),
        "duracao": analise.get("duracao", "horas"),
        "confianca": analise.get("confianca", "baixa"),
        "resumo": analise.get("resumo", ""),
    }


if __name__ == "__main__":
    testes = [
        ("🚨 BREAKING: Fed announces emergency rate cut of 50bps", 1),
        ("Good morning everyone! Hope you have a great day", 2),
        ("Bitcoin just broke $80,000 resistance on high volume", 1),
        ("OPEC+ cuts oil production by 1 million barrels per day", 1),
        ("Trump vai sancionar legislação de criptomoedas nos EUA", 1),
    ]

    print("Testando classificador com Gemini Flash + retry...\n")
    for texto, tier in testes:
        print(f"📨 [{tier}] {texto[:60]}")
        resultado = classificar(texto, tier)
        if resultado:
            print(f"   ✅ {resultado['direcao'].upper()} | Ativos: {resultado['ativos']}")
            print(f"   Urgência: {resultado['urgencia']}/5 | Confiança: {resultado['confianca']}")
            print(f"   Resumo: {resultado['resumo']}")
        else:
            print(f"   ⏭️  Descartado")
        print()
