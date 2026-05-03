import requests
import time

def buscar_atividade_wallet(wallet, start_ts, end_ts):
    sessao = requests.Session()
    registros = []
    offset = 0

    MAX_PAGINAS = 10   # 🔥 proteção contra travamento (50*500 = 25k eventos)
    tentativas_max = 3

    for pagina in range(MAX_PAGINAS):
        params = {
            "user": wallet,
            "start": start_ts,
            "end": end_ts,
            "limit": 500,
            "offset": offset,
        }

        sucesso = False

        for tentativa in range(tentativas_max):
            try:
                r = sessao.get(BASE_URL, params=params, timeout=10)
                r.raise_for_status()
                dados = r.json()
                sucesso = True
                break

            except requests.exceptions.Timeout:
                print(f"[Timeout] wallet={wallet} tentativa {tentativa+1}")
                time.sleep(1)

            except Exception as e:
                print(f"[Erro] {e}")
                time.sleep(1)

        if not sucesso:
            print(f"[ABORTADO] wallet {wallet}")
            break

        if not dados:
            break

        registros.extend(dados)

        print(f"wallet={wallet[:6]}... | página {pagina+1} | total={len(registros)}")

        if len(dados) < 500:
            break

        offset += 500
        time.sleep(0.2)

    return registros