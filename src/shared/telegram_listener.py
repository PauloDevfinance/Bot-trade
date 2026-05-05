import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from dotenv import load_dotenv
from .news_classifier import classificar

load_dotenv("/home/paulo/trading-bot/.env")

# ====== CONFIG ======
api_id = 38728772
api_hash = "edf8d787702b400416786a13dccc07bc"
session_name = "/home/paulo/trading-bot/sessao"
MEU_ID = 1927840529

# ====== GRUPOS ======
TIER_1 = {
    -1001556054753: "Watcher Guru",
    -1001653515977: "Crypto Pro Updates",
}
TIER_2 = {
    -1001484262071: "Análise Gráfica BTC/Altcoins",
}
TESTE = {
    MEU_ID: "TESTE - Paulo"  # 🔧 suas mensagens pra você mesmo
}
GRUPOS_PERMITIDOS = {**TIER_1, **TIER_2, **TESTE}

# ====== SIGNAL BUS ======
SIGNAL_FILE = "/home/paulo/trading-bot/logs/news_signals.json"
os.makedirs(os.path.dirname(SIGNAL_FILE), exist_ok=True)

def publicar_sinal(sinal):
    sinais = []
    if os.path.exists(SIGNAL_FILE):
        try:
            with open(SIGNAL_FILE, "r") as f:
                sinais = json.load(f)
        except:
            sinais = []
    sinal["timestamp"] = datetime.utcnow().isoformat()
    sinais.append(sinal)
    sinais = sinais[-100:]
    with open(SIGNAL_FILE, "w") as f:
        json.dump(sinais, f, indent=2, ensure_ascii=False)

# ====== STATS ======
stats = {"total": 0, "filtro1": 0, "publicados": 0}

def get_tier(chat_id):
    if chat_id in TIER_1: return 1
    if chat_id in TIER_2: return 2
    if chat_id in TESTE: return 1  # trata como tier 1
    return None

# ====== INIT ======
client = TelegramClient(session_name, api_id, api_hash)

@client.on(events.NewMessage)
async def handler(event):
    if event.chat_id not in GRUPOS_PERMITIDOS:
        return

    texto = (event.raw_text or "").strip()
    if not texto:
        return

    tier = get_tier(event.chat_id)
    nome_chat = GRUPOS_PERMITIDOS[event.chat_id]
    stats["total"] += 1

    print(f"\n{'='*60}")
    print(f"📨 MENSAGEM RECEBIDA [{nome_chat}]")
    print(f"Texto: {texto[:100]}")
    print(f"{'='*60}")

    loop = asyncio.get_event_loop()
    sinal = await loop.run_in_executor(None, classificar, texto, tier)

    if sinal:
        stats["publicados"] += 1
        publicar_sinal(sinal)
        print(f"✅ CLASSIFICADO:")
        print(f"   Direção:   {sinal['direcao'].upper()}")
        print(f"   Ativos:    {sinal['ativos']}")
        print(f"   Urgência:  {sinal['urgencia']}/5")
        print(f"   Confiança: {sinal['confianca']}")
        print(f"   Resumo:    {sinal['resumo']}")
    else:
        stats["filtro1"] += 1
        print(f"⏭️  DESCARTADO (sem keywords ou irrelevante)")
    
    print(f"{'='*60}\n")

    if stats["total"] % 20 == 0:
        taxa = stats["publicados"] / stats["total"] * 100
        print(f"\n📊 STATS: {stats['total']} msgs | {stats['publicados']} sinais ({taxa:.1f}%)\n")

async def main_with_reconnect():
    tentativas = 0
    while True:
        try:
            await client.start()
            print("=" * 60)
            print("✅ TELEGRAM LISTENER ATIVO")
            print(f"✅ Monitorando {len(GRUPOS_PERMITIDOS)} fontes")
            print(f"✅ Teste: mande uma msg pra 'Mensagens Salvas'")
            print("=" * 60)
            tentativas = 0
            await client.run_until_disconnected()
        except Exception as e:
            tentativas += 1
            espera = min(60, 5 * tentativas)
            print(f"⚠️  Desconectado: {e}")
            print(f"Reconectando em {espera}s... (tentativa {tentativas})")
            await asyncio.sleep(espera)

if __name__ == "__main__":
    asyncio.run(main_with_reconnect())
