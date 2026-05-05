import time
from datetime import datetime

from .config import PAPER_TRADING, ENTRY_TIME_BEFORE_CLOSE
from .market_finder import get_current_window
from .price_feed import get_btc_price, get_price_at_window_open
from .chainlink_feed import get_chainlink_price, get_price_snapshot
from .polymarket_client import buscar_mercado_15min, extrair_info_mercado
from .signal_engine import calcular_sinal
from .paper_trader import PaperTrader


def rodar_bot():
    print("=" * 60)
    print("  BTC 15-MIN TRADING BOT")
    print(f"  Mode: {'📝 PAPER' if PAPER_TRADING else '🔴 LIVE'}")
    print(f"  Iniciado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 60)

    trader = PaperTrader()
    trade_pendente = None
    janela_analisada = None
    janela_resolvida = None

    try:
        while True:
            window = get_current_window()
            restante = window["seconds_remaining"]
            slug_atual = window["slug"]

            # ─── FASE 1: Aguardando ───
            if restante > ENTRY_TIME_BEFORE_CLOSE and trade_pendente is None:
                snap = get_price_snapshot()
                if snap["chainlink"]:
                    linha = (
                        f"\r⏳ Resta: {restante:>4}s | "
                        f"BN: ${snap['binance']:>10,.2f} | "
                        f"CL: ${snap['chainlink']:>10,.2f} ({snap['chainlink_age']:>3}s) | "
                        f"Δ: {snap['divergencia_pct']:>+7.4f}% {snap['status']}   "
                    )
                else:
                    linha = f"\r⏳ Resta: {restante:>4}s | BN: ${snap['binance']:>10,.2f} | CL: indisponível   "
                print(linha, end="", flush=True)
                time.sleep(10)
                continue

            # ─── FASE 2: Análise (1x por janela) ───
            if (restante <= ENTRY_TIME_BEFORE_CLOSE
                    and trade_pendente is None
                    and janela_analisada != slug_atual):

                janela_analisada = slug_atual

                # Snapshot completo antes de analisar
                snap = get_price_snapshot()

                print(f"\n\n{'─'*60}")
                print(f"🔍 ANALISANDO | {slug_atual} | Resta: {restante}s")
                print(f"\n   📊 Preços:")
                print(f"      Binance:    ${snap['binance']:,.2f}")
                if snap["chainlink"]:
                    print(f"      Chainlink:  ${snap['chainlink']:,.2f} (atualizado há {snap['chainlink_age']}s)")
                    print(f"      Divergência: {snap['divergencia_pct']:+.4f}% (${snap['divergencia_usd']:+.2f}) {snap['status']}")

                mercado = buscar_mercado_15min(slug_atual)
                info = extrair_info_mercado(mercado) if mercado else None

                if info and info["outcomes"]:
                    outcomes = info["outcomes"]
                    print(f"\n   🎯 Mercado: {info['question']}")
                    for k, v in outcomes.items():
                        print(f"      {k.upper()}: ${v:.4f}")
                else:
                    preco_ab = get_price_at_window_open(window["start_ts"])
                    preco_at = get_btc_price()
                    delta_pct = (preco_at - preco_ab) / preco_ab
                    prob_up = max(0.1, min(0.9, 0.5 + (delta_pct * 10)))
                    outcomes = {"up": round(prob_up, 4), "down": round(1 - prob_up, 4)}
                    print(f"\n   ⚠️  Mercado não encontrado — usando estimativa")

                sinal = calcular_sinal(window["start_ts"], outcomes)

                print(f"\n   📈 Sinal:")
                print(f"      BTC abertura: ${sinal['preco_abertura']:,.2f}")
                print(f"      BTC agora:    ${sinal['preco_atual']:,.2f} [{sinal.get('fonte', '?')}]")
                print(f"      Delta:        {sinal.get('delta_pct', 0):+.4f}%")
                print(f"      Ação:         {sinal['acao']}")
                print(f"      Razão:        {sinal['razao']}")

                if sinal["acao"].startswith("BUY"):
                    trade_pendente = trader.registrar_entrada(sinal, slug_atual)
                    trade_pendente["window_start_ts"] = window["start_ts"]
                else:
                    print(f"\n   ⏭️  Skip")

                print(f"{'─'*60}\n")

            # ─── FASE 3: Resolução via Chainlink ───
            if (trade_pendente is not None
                    and slug_atual != trade_pendente["window_slug"]
                    and janela_resolvida != trade_pendente["window_slug"]):

                janela_resolvida = trade_pendente["window_slug"]
                print(f"\n⏰ Janela fechou — verificando resultado...")
                time.sleep(8)

                preco_abertura = get_price_at_window_open(trade_pendente["window_start_ts"])

                cl = get_chainlink_price()
                binance_final = get_btc_price()

                if cl and cl["fresco"]:
                    preco_final = cl["preco"]
                    fonte_resolucao = f"Chainlink ({cl['atualizado_ha']}s)"
                else:
                    preco_final = binance_final
                    fonte_resolucao = "Binance (fallback)"

                btc_subiu = preco_final > preco_abertura
                direcao_trade = trade_pendente["direcao"]
                venceu = (direcao_trade == "up" and btc_subiu) or \
                         (direcao_trade == "down" and not btc_subiu)

                print(f"   BTC abertura:  ${preco_abertura:,.2f}")
                print(f"   BTC final CL:  ${cl['preco']:,.2f}" if cl else "   CL: indisponível")
                print(f"   BTC final BN:  ${binance_final:,.2f}")
                print(f"   Resolução por: {fonte_resolucao}")
                print(f"   BTC subiu:     {'Sim ↑' if btc_subiu else 'Não ↓'}")
                print(f"   Trade:         {direcao_trade.upper()}")

                trader.registrar_resultado(trade_pendente, venceu)
                trade_pendente = None

                total = trader.wins + trader.losses
                if total > 0 and total % 5 == 0:
                    trader.resumo()

                print(f"\n⏳ Aguardando próxima janela...\n")

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\n🛑 Bot parado pelo usuário")
        trader.resumo()


if __name__ == "__main__":
    rodar_bot()
