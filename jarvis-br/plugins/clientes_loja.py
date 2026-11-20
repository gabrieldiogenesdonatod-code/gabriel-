"""
Clientes da loja — mini CRM (fork PT-BR 2.17).

    "Jarvis, cadastra a cliente Ana, whats 62 99999-0000, filho de 4 anos, aniversário 12/03"
    "Jarvis, a Ana comprou 120 reais hoje"
    "Jarvis, quem não compra há mais de 60 dias?"       → lista e rascunhos de "saudade" para o WhatsApp
    "Jarvis, quem faz aniversário essa semana?"          (cliente ou criança)
    "Jarvis, o que você sabe da Ana?"

Fica em memory/clientes_loja.json, só no seu PC. Os rascunhos de mensagem você
manda pelo WhatsApp com "manda pra Ana …" (pede confirmação).
"""

from __future__ import annotations

import re

from datetime import date, datetime

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "clientes_loja",
    "brief": "Store customers (CRM): register, log purchases, who stopped buying, birthdays, win-back drafts.",
    "description": (
        "Store customer list. action='cadastrar' with nome and optional whats, aniversario (DD/MM), notas (kids' ages, "
        "sizes, preferences). action='compra' with nome and valor logs a purchase. action='sumidos' (optional dias, "
        "default 60) lists who hasn't bought and drafts friendly win-back messages. action='ritmo' (3.0): customers OUT OF "
        "THEIR OWN buying rhythm (e.g. buys every 2 weeks, gone for 5), with drafts. action='aniversarios' (optional dias "
        "ahead, default 7). action='ver' with nome. action='listar'."
    ),
    "parameters": {"type": "OBJECT", "properties": {
        "action": {"type": "STRING"}, "nome": {"type": "STRING"}, "whats": {"type": "STRING"},
        "aniversario": {"type": "STRING"}, "notas": {"type": "STRING"}, "valor": {"type": "NUMBER"},
        "dias": {"type": "INTEGER"}}, "required": ["action"]},
}

ARQ = MEMORIA / "clientes_loja.json"


def _k(n: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFKD", str(n or "")).encode("ascii", "ignore").decode().lower().split())


def _brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def dias_sem_comprar(c: dict, hoje: date) -> int | None:
    if not c.get("compras"):
        return None
    ultima = max(datetime.strptime(x["data"], "%Y-%m-%d").date() for x in c["compras"])
    return (hoje - ultima).days


def ritmo(c: dict, hoje: date) -> tuple[float, int] | None:
    """Fork PT-BR 3.0: (intervalo típico em dias, dias sem comprar) para quem tem 3+ compras. Pura."""
    datas = sorted({datetime.strptime(x["data"], "%Y-%m-%d").date() for x in c.get("compras", [])})
    if len(datas) < 3:
        return None
    gaps = sorted((b - a).days for a, b in zip(datas, datas[1:]))
    tipico = gaps[len(gaps) // 2] if len(gaps) % 2 else (gaps[len(gaps) // 2 - 1] + gaps[len(gaps) // 2]) / 2
    return float(max(1, tipico)), (hoje - datas[-1]).days


def fora_do_ritmo(c: dict, hoje: date) -> bool:
    r = ritmo(c, hoje)
    return bool(r) and r[1] > max(2 * r[0], r[0] + 10)


def aniversario_em(texto: str, hoje: date, janela: int) -> int | None:
    """Dias até o próximo aniversário 'DD/MM' se cair na janela (pura)."""
    m = re.match(r"(\d{1,2})/(\d{1,2})", str(texto or ""))
    if not m:
        return None
    d, mes = int(m.group(1)), int(m.group(2))
    for ano in (hoje.year, hoje.year + 1):
        try:
            alvo = date(ano, mes, d)
        except ValueError:
            return None
        if alvo >= hoje:
            dif = (alvo - hoje).days
            return dif if dif <= janela else None
    return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    cs = ler_json(ARQ, {}) or {}
    nome = str(p.get("nome") or "").strip()
    k = _k(nome)
    hoje = date.today()
    try:
        if a == "cadastrar":
            if not nome:
                return "Qual o nome da cliente?"
            c = cs.get(k, {"nome": nome, "compras": []})
            for campo in ("whats", "aniversario", "notas"):
                if p.get(campo):
                    c[campo] = (c.get(campo, "") + " | " if campo == "notas" and c.get(campo) else "") + str(p[campo])
            cs[k] = c
            gravar_json(ARQ, cs)
            return f"{nome} cadastrada."
        if a == "compra":
            if k not in cs:
                cs[k] = {"nome": nome, "compras": []}
            v = float(p.get("valor") or 0)
            cs[k]["compras"].append({"data": hoje.isoformat(), "valor": v})
            gravar_json(ARQ, cs)
            total = sum(x["valor"] for x in cs[k]["compras"])
            return f"Anotado: {nome} comprou {_brl(v)}. Ela já gastou {_brl(total)} em {len(cs[k]['compras'])} compra(s)."
        if a == "ver":
            c = cs.get(k) or next((x for kk, x in cs.items() if k and k in kk), None)
            if not c:
                return f"Não tenho {nome} cadastrada."
            d = dias_sem_comprar(c, hoje)
            total = sum(x["valor"] for x in c.get("compras", []))
            return (f"{c['nome']}: whats {c.get('whats', '—')}, aniversário {c.get('aniversario', '—')}, "
                    f"{len(c.get('compras', []))} compra(s), {_brl(total)} no total"
                    + (f", última há {d} dias" if d is not None else "") + f". Notas: {c.get('notas', '—')}.")
        if a == "sumidos":
            lim = int(p.get("dias") or 60)
            sumidos = sorted(((dias_sem_comprar(c, hoje), c) for c in cs.values()
                              if (dias_sem_comprar(c, hoje) or 0) >= lim), key=lambda x: -x[0])
            if not sumidos:
                return f"Ninguém está há mais de {lim} dias sem comprar."
            linhas = [f"{c['nome']} — {d} dias · {c.get('whats', 'sem whats')}\n  \"Oi, {c['nome'].split()[0]}! "
                      f"Saudade de você aqui na Cristal Malhas 💕 Chegaram novidades lindas; quer que eu mande fotos?\""
                      for d, c in sumidos[:30]]
            mostrar(player, "CLIENTES SUMIDOS", "\n".join(linhas))
            return f"{len(sumidos)} cliente(s) sumida(s): " + ", ".join(c["nome"] for _d, c in sumidos[:6]) + \
                ". Os rascunhos de mensagem estão no painel."
        if a == "ritmo":
            fora = sorted(((ritmo(c, hoje), c) for c in cs.values() if fora_do_ritmo(c, hoje)), key=lambda x: -(x[0][1] / x[0][0]))
            if not fora:
                return "Todas as clientes com 3 ou mais compras estão dentro do próprio ritmo."
            linhas = [f"{c['nome']} — costuma comprar a cada {r[0]:.0f} dias, está há {r[1]} · {c.get('whats', 'sem whats')}\n  "
                      f"\"Oi, {c['nome'].split()[0]}! Tudo bem? Separei umas novidades que são a sua cara 💕 Quer ver?\""
                      for r, c in fora[:30]]
            mostrar(player, "CLIENTES FORA DO RITMO", "\n".join(linhas))
            return (f"{len(fora)} cliente(s) fora do próprio ritmo de compra: " + ", ".join(c["nome"] for _r, c in fora[:6]) +
                    ". Os rascunhos estão no painel.")
        if a == "aniversarios":
            jan = int(p.get("dias") or 7)
            achados = []
            for c in cs.values():
                for campo, rot in (("aniversario", ""),):
                    d = aniversario_em(c.get(campo), hoje, jan)
                    if d is not None:
                        achados.append((d, c["nome"]))
                for m in re.finditer(r"(?:anivers[aá]rio|niver)[^0-9]*(\d{1,2}/\d{1,2})", c.get("notas", ""), re.I):
                    d = aniversario_em(m.group(1), hoje, jan)
                    if d is not None:
                        achados.append((d, f"criança da {c['nome']}"))
            if not achados:
                return f"Nenhum aniversário nos próximos {jan} dias."
            return "Aniversários: " + "; ".join(f"{n} {'hoje' if d == 0 else f'em {d} dia(s)'}" for d, n in sorted(achados)) + \
                ". Boa hora para mandar um mimo ou cupom."
        if not cs:
            return "Nenhuma cliente cadastrada ainda."
        ranking = sorted(cs.values(), key=lambda c: -sum(x["valor"] for x in c.get("compras", [])))
        mostrar(player, "CLIENTES", "\n".join(f"{c['nome']:<25} {_brl(sum(x['valor'] for x in c.get('compras', []))):>12}"
                                              f"  {c.get('whats', '')}" for c in ranking))
        return f"{len(cs)} clientes. As que mais compram: " + ", ".join(c["nome"] for c in ranking[:3]) + "."
    except Exception as e:
        return f"Clientes falhou: {e}"


