import json
import os
import time
import subprocess
from datetime import datetime

OUTPUT_FILE = "/home/paulo/trading-bot/logs/macro_context.json"
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def salvar_contexto(regime, preco, probas):
    ctx = {
        "timestamp": datetime.utcnow().isoformat(),
        "regime_atual": regime,
        "preco_btc": preco,
        "probabilidades": probas,
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(ctx, f, indent=2)
    print(f"[macro] Contexto salvo: {regime} | BTC ${preco:,.0f}")
    return ctx

def ler_contexto():
    """Qualquer bot chama isso para saber o regime atual."""
    try:
        with open(OUTPUT_FILE, "r") as f:
            return json.load(f)
    except:
        return None

if __name__ == "__main__":
    print("Pipeline macro rodando a cada 1h...")
    while True:
        try:
            print(f"\n[{datetime.utcnow().strftime('%H:%M')}] Rodando pipeline...")
            # Importa e roda o pipeline
            import sys
            sys.path.insert(0, "/home/paulo/trading-bot")
            # Roda pipeline em subprocess pra não conflitar com imports
            result = subprocess.run(
                ["python", "-c", """
import sys
sys.path.insert(0, '/home/paulo/trading-bot')
from src.pipeline import *
ctx = {
    'regime': regime_atual,
    'preco': float(preco_atual),
    'probas': {str(c): float(p) for c, p in zip(classes, probas[0])}
}
import json
print('CONTEXT:' + json.dumps(ctx))
"""],
                capture_output=True, text=True, timeout=120
            )
            # Pega a linha com o contexto
            for line in result.stdout.split('\n'):
                if line.startswith('CONTEXT:'):
                    ctx = json.loads(line.replace('CONTEXT:', ''))
                    salvar_contexto(ctx['regime'], ctx['preco'], ctx['probas'])
                    break
        except Exception as e:
            print(f"[macro] Erro: {e}")

        print(f"Próxima atualização em 1h...")
        time.sleep(3600)
