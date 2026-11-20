"""
Caderneta de fiado (fork PT-BR 2.17).

    "Jarvis, a Maria levou 150 reais fiado"
    "Jarvis, a Maria pagou 50 do fiado"
    "Jarvis, quem me deve?"            "Jarvis, quanto a Maria deve?"
    "Jarvis, cobra a Maria"            → rascunho de cobrança educada (você manda pelo WhatsApp)

Cada movimento fica com data em memory/fiado.json. Quem passa de 30 dias sem
pagar aparece primeiro.
"""

from __future__ import annotations

from datetime import date, datetime

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "fiado",
    "brief": "Store credit book: who owes what, partial payments, polite collection message drafts.",
    "description": (
        "Credit book (fiado). action='anotar' with nome and valor (a purchase on credit). action='pagou' with nome and "
        "valor. action='quem_deve' lists debts (oldest first). action='saldo' with nome. action='cobrar' with nome drafts "
        "a polite collection message."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "nome": {"type": "STRING"},
                                                    "valor": {"type": "NUMBER"}}, "required": ["action"]},
}

ARQ = MEMORIA / "fiado.json"


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def saldo(movs: list[dict]) -> float:
    return round(sum(m["valor"] if m["tipo"] == "compra" else -m["valor"] for m in movs), 2)


def dias_devendo(movs: list[dict], hoje: date) -> int:
    """Desde a compra mais antiga ainda não coberta pelos pagamentos (pura)."""
    pago = sum(m["valor"] for m in movs if m["tipo"] == "pagamento")
    for m in sorted((m for m in movs if m["tipo"] == "compra"), key=lambda m: m["data"]):
        if pago >= m["valor"]:
            pago -= m["valor"]
            continue
        return (hoje - datetime.strptime(m["data"], "%Y-%m-%d").date()).days
    return 0


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "quem_deve").lower()
    d = ler_json(ARQ, {}) or {}
    nome = str(p.get("nome") or "").strip()
    k = nome.lower()
    hoje = date.today()
    try:
        if a in ("anotar", "pagou"):
            v = float(p.get("valor") or 0)
            if not nome or v <= 0:
                return "Diga o nome e o valor."
            pessoa = d.setdefault(k, {"nome": nome, "movs": []})
            pessoa["movs"].append({"data": hoje.isoformat(), "tipo": "compra" if a == "anotar" else "pagamento", "valor": v})
            gravar_json(ARQ, d)
            s = saldo(pessoa["movs"])
            return f"Anotado. {nome} agora deve {_brl(s)}." if s > 0 else f"Anotado. {nome} está quite" + \
                (f" (sobrou crédito de {_brl(-s)})." if s < 0 else ".")
        if a == "saldo":
            pessoa = d.get(k)
            return f"{nome} deve {_brl(saldo(pessoa['movs']))}." if pessoa else f"{nome} não tem fiado."
        if a == "cobrar":
            pessoa = d.get(k)
            if not pessoa or saldo(pessoa["movs"]) <= 0:
                return f"{nome} não deve nada."
            texto = (f"Oi, {pessoa['nome'].split()[0]}, tudo bem? 😊 Passando só pra lembrar do valor de "
                     f"{_brl(saldo(pessoa['movs']))} das peças da Cristal Malhas. Pode ser no Pix, quando ficar bom pra "
                     "você. Obrigada!")
            mostrar(player, f"COBRANÇA — {pessoa['nome']}", texto)
            return f"Rascunho pronto no painel: \"{texto}\". Quer que eu mande no WhatsApp dela?"
        devendo = [(dias_devendo(x["movs"], hoje), saldo(x["movs"]), x["nome"]) for x in d.values() if saldo(x["movs"]) > 0]
        if not devendo:
            return "Ninguém está devendo."
        devendo.sort(reverse=True)
        total = sum(s for _d, s, _n in devendo)
        mostrar(player, "FIADO", "\n".join(f"{n:<22} {_brl(s):>12}   há {dd} dias" for dd, s, n in devendo))
        return f"{len(devendo)} pessoa(s) devem {_brl(total)} no total. Mais antigo: {devendo[0][2]}, " \
               f"{_brl(devendo[0][1])} há {devendo[0][0]} dias."
    except Exception as e:
        return f"O fiado falhou: {e}"
