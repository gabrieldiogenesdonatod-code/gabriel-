"""Trocas e devoluções da loja (2.18): registra, controla prazo e lembra o direito de arrependimento (compra online)."""
from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import Colecao, P, hoje, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("trocas_loja", "Store exchanges/returns: register with purchase date, deadline check (store policy days; 7-day online regret), pending list.",
           "registrar | prazo | resolver | pendentes",
           "registrar: cliente, peca, motivo, data (purchase dd/mm), online (sim|nao). prazo: data, online -> can still exchange? "
           "resolver: cliente. Store policy days in dias (default 30).",
           "cliente peca motivo data online dias")

T = Colecao("trocas")


def dentro_prazo(compra: date, ref: date, dias: int, online: bool) -> tuple[bool, date]:
    limite = compra + timedelta(7 if online else dias)
    return ref <= limite, limite


def _go(p, pl):
    a = str(p.get("action")).lower()
    online = str(p.get("online") or "").lower().startswith("s")
    dias = int(p.get("dias") or 30)
    if a == "prazo":
        ok, lim = dentro_prazo(ler_data(p.get("data")), date.today(), dias, online)
        base = "arrependimento (7 dias, compra online)" if online else f"política da loja ({dias} dias)"
        return f"{'Ainda dá' if ok else 'Passou do prazo'}: limite {lim:%d/%m/%Y} pela {base}. Defeito tem regra própria (30/90 dias)."
    if a == "registrar":
        T.por(p.get("cliente"), {"peca": p.get("peca"), "motivo": p.get("motivo"), "data": hoje(), "ok": False})
        return f"Troca de {p.get('cliente')} registrada."
    if a == "resolver":
        return "Resolvida." if T.tirar(p.get("cliente")) else "Não achei."
    return "\n".join(f"{t['nome']}: {t['peca']} ({t['motivo']}) desde {t['data']}" for t in T.tudo().values()) or "Sem trocas pendentes."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("registrar prazo resolver pendentes".split(), _go), player, "Trocas")
