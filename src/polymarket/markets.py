import requests
import json
from datetime import datetime, timezone

def buscar_mercados(limit=1000, volume_minimo=10000):
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit,
        "order": "volume",
        "ascending": "false"
    }

    resposta = requests.get(url, params=params)
    dados = resposta.json()
    mercados_filtrados = []

    for mercado in dados:
        volume = float(mercado.get('volume', 0) or 0)
        if volume < volume_minimo:
            continue

        try:
            outcomes = json.loads(mercado.get('outcomePrices', '[]'))
            outcomes_labels = json.loads(mercado.get('outcomes', '[]'))
        except:
            outcomes = []
            outcomes_labels = []

        probabilidades = {}
        for label, price in zip(outcomes_labels, outcomes):
            probabilidades[label] = round(float(price) * 100, 2)

        mercados_filtrados.append({
            "question": mercado.get('question'),
            "volume": volume,
            "end_date": mercado.get('endDate', '')[:10],
            "probabilidades": probabilidades
        })

    return mercados_filtrados

def exibir_mercados(mercados):
    print("=== Mercados Ativos no Polymarket ===\n")
    for m in mercados:
        print(f"Pergunta:   {m['question']}")
        print(f"Volume:     ${m['volume']:,.2f}")
        print(f"Encerra em: {m['end_date']}")
        for outcome, prob in m['probabilidades'].items():
            print(f"  {outcome}: {prob}%")
        print("-" * 60)

if __name__ == "__main__":
    mercados = buscar_mercados()
    exibir_mercados(mercados)