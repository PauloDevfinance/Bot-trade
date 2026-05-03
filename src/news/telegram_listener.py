# telegram_listener.py
import asyncio
from telethon import TelegramClient, events

# ====== CONFIG ======
api_id = 38728772
api_hash = "edf8d787702b400416786a13dccc07bc"
session_name = "sessao"

USUARIO_ID = 1927840529

# ====== FILTRO DE GRUPOS ======
TIER_1 = {
    -1001556054753: "Watcher Guru",
    -1001653515977: "Crypto Pro Updates",
}

TIER_2 = {
    -1001484262071: "Análise Gráfica BTC/Altcoins",
}

GRUPOS_PERMITIDOS = {**TIER_1, **TIER_2}

def get_tier(chat_id):
    if chat_id in TIER_1:
        return 1
    if chat_id in TIER_2:
        return 2
    return None

# ====== INIT ======
client = TelegramClient(session_name, api_id, api_hash)

print("✅ Iniciando cliente Telegram...")
print(f"✅ Monitorando {len(GRUPOS_PERMITIDOS)} grupos:")
for gid, nome in GRUPOS_PERMITIDOS.items():
    tier = get_tier(gid)
    print(f"   [Tier {tier}] {nome} ({gid})")

# ====== HANDLER ======
@client.on(events.NewMessage)
async def handler(event):
    if event.chat_id not in GRUPOS_PERMITIDOS:
        return

    sender = await event.get_sender()

    tier = get_tier(event.chat_id)
    nome_chat = GRUPOS_PERMITIDOS[event.chat_id]
    texto = (event.raw_text or "").strip()
    horario = event.date.strftime("%d/%m/%Y %H:%M:%S")

    nome = sender.first_name if sender and sender.first_name else "Desconhecido"
    username = f"@{sender.username}" if sender and sender.username else ""

    # Comando de parada
    if texto.lower() == "parar" and sender and sender.id == USUARIO_ID:
        print(" Encerrando por comando autorizado...")
        await client.disconnect()
        return

    # Ignora mensagens sem texto
    if not texto:
        return

    prioridade = " ALTA" if tier == 1 else " MÉDIA"

    print(f"""
{'='*50}
{prioridade} | Tier {tier} | {nome_chat}
👤 De: {nome} {username}
🕒 Hora: {horario} UTC
💬 Mensagem: {texto}
{'='*50}
""")

# ====== MAIN ======
async def main():
    await client.start()
    print(" Conectado. Aguardando mensagens...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())