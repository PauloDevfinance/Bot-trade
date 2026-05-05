import csv
import os
from datetime import datetime
from .config import CAPITAL_USD, MAX_POSITION_PCT, TRADES_FILE


class PaperTrader:
    def __init__(self):
        self.capital = CAPITAL_USD
        self.trades = []
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0

        # Cria diretório de logs se não existir
        os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)

        # Cria CSV com headers se não existir
        if not os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "window_slug", "direcao", "token_price",
                    "size_usd", "delta_pct", "confianca",
                    "resultado", "pnl", "capital_apos"
                ])

    def calcular_size(self, confianca):
        """Position sizing baseado em confiança."""
        multiplier = {
            "alta": 1.0,
            "media": 0.6,
            "baixa": 0.3
        }.get(confianca, 0.3)

        size = self.capital * MAX_POSITION_PCT * multiplier
        return round(size, 2)

    def registrar_entrada(self, sinal, window_slug):
        """Registra uma entrada de trade (paper)."""
        size = self.calcular_size(sinal.get("confianca", "baixa"))

        trade = {
            "timestamp": datetime.utcnow().isoformat(),
            "window_slug": window_slug,
            "direcao": sinal["direcao"],
            "token_price": sinal["token_price"],
            "size_usd": size,
            "delta_pct": sinal["delta_pct"],
            "confianca": sinal.get("confianca", "?"),
            "shares": round(size / sinal["token_price"], 4),
            "resultado": None,
            "pnl": None
        }

        self.trades.append(trade)
        print(f"  📝 PAPER TRADE: {sinal['acao']}")
        print(f"     Size: ${size:.2f} | Shares: {trade['shares']:.2f}")
        print(f"     Fill: ${sinal['token_price']:.4f}")

        return trade

    def registrar_resultado(self, trade, venceu):
        """Registra o resultado após resolução do mercado."""
        if venceu:
            # Ganha $1 por share - custo
            pnl = trade["shares"] * 1.0 - trade["size_usd"]
            self.wins += 1
        else:
            # Perde tudo
            pnl = -trade["size_usd"]
            self.losses += 1

        trade["resultado"] = "WIN" if venceu else "LOSS"
        trade["pnl"] = round(pnl, 2)
        self.capital += pnl
        self.total_pnl += pnl

        # Salva no CSV
        with open(TRADES_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                trade["timestamp"], trade["window_slug"],
                trade["direcao"], trade["token_price"],
                trade["size_usd"], trade["delta_pct"],
                trade["confianca"], trade["resultado"],
                trade["pnl"], round(self.capital, 2)
            ])

        emoji = "✅" if venceu else "❌"
        print(f"  {emoji} {trade['resultado']}: PnL ${pnl:+.2f} | Capital: ${self.capital:.2f}")

        return pnl

    def resumo(self):
        """Imprime resumo da sessão."""
        total = self.wins + self.losses
        wr = (self.wins / total * 100) if total > 0 else 0

        print(f"\n{'='*50}")
        print(f"RESUMO PAPER TRADING")
        print(f"{'='*50}")
        print(f"Trades:   {total}")
        print(f"Wins:     {self.wins} | Losses: {self.losses}")
        print(f"Win Rate: {wr:.1f}%")
        print(f"PnL:      ${self.total_pnl:+.2f}")
        print(f"Capital:  ${self.capital:.2f}")
        print(f"{'='*50}")


if __name__ == "__main__":
    pt = PaperTrader()

    # Simula um trade
    sinal_teste = {
        "acao": "BUY UP",
        "direcao": "up",
        "token_price": 0.55,
        "delta_pct": 0.15,
        "confianca": "media"
    }

    trade = pt.registrar_entrada(sinal_teste, "btc-updown-15m-teste")
    pt.registrar_resultado(trade, venceu=True)
    pt.resumo()
