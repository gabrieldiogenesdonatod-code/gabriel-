"""
Controle de gastos por voz — plugin do J.A.R.V.I.S BR.

    "Jarvis, gastei 40 reais no almoço"        → registra (categoria: alimentação)
    "Jarvis, quanto eu gastei esse mês?"       → total e divisão por categoria
    "Jarvis, apaga o último gasto"             → desfaz o último registro
    "Jarvis, exporta meus gastos pro Excel"    → cria uma planilha .xlsx do mês

Os gastos ficam em `memory/gastos.csv` (abre no Excel) e só no seu computador.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from plugins._dados_br import DATA_DIR, acrescentar, escrever, ler, numero, reais

PLUGIN = {
    "name": "gastos",
    "description": (
        "Personal expense tracker. action='registrar' when the user says they "
        "spent / paid money ('gastei 40 no almoço', 'paguei 120 de luz'): pass "
        "valor (number in reais), descricao and categoria — choose one of "
        "alimentacao, transporte, casa, contas, loja, lazer, saude, compras, "
        "outros. action='resumo' for how much was spent (mes: 'atual', 'passado' "
        "or YYYY-MM). action='apagar_ultimo' to undo the last entry. "
        "action='exportar' to create an Excel file of a month. "
        "Store sales and stock belong to cristal_malhas, not here."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "registrar | resumo | apagar_ultimo | exportar"},
            "valor": {"type": "NUMBER", "description": "Amount in reais"},
            "descricao": {"type": "STRING", "description": "What it was"},
            "categoria": {"type": "STRING", "description": "Category, see description"},
            "mes": {"type": "STRING", "description": "atual | passado | YYYY-MM"},
        },
        "required": ["action"],
    },
}

_ARQ = "gastos.csv"
_CAMPOS = ["data", "valor", "categoria", "descricao"]
_CATEGORIAS = {"alimentacao", "transporte", "casa", "contas", "loja", "lazer",
               "saude", "compras", "outros"}
_BONITO = {"alimentacao": "alimentação", "saude": "saúde"}


def _mes_alvo(mes: str) -> str:
    m = (mes or "atual").strip().lower()
    hoje = datetime.now()
    if m.startswith("passad") or m == "anterior":
        ano, mm = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
        return f"{ano}-{mm:02d}"
    if len(m) == 7 and m[4] == "-":
        return m
    return hoje.strftime("%Y-%m")


def _do_mes(mes: str) -> tuple[str, list[dict]]:
    alvo = _mes_alvo(mes)
    return alvo, [g for g in ler(_ARQ) if g.get("data", "").startswith(alvo)]


def _registrar(p: dict) -> str:
    valor = numero(p.get("valor"))
    if valor <= 0:
        return "Quanto foi o gasto?"
    cat = str(p.get("categoria") or "outros").strip().lower()
    cat = cat.replace("ç", "c").replace("ã", "a").replace("ú", "u")
    if cat not in _CATEGORIAS:
        cat = "outros"
    desc = str(p.get("descricao") or "").strip() or cat
    acrescentar(_ARQ, _CAMPOS, {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "valor": f"{valor:.2f}".replace(".", ","), "categoria": cat, "descricao": desc,
    })
    _alvo, mes = _do_mes("atual")
    total = sum(numero(g["valor"]) for g in mes)
    return (f"Anotado: {reais(valor)} em {desc} ({_BONITO.get(cat, cat)}). "
            f"Total do mês: {reais(total)}.")


def _resumo(mes: str, player) -> str:
    alvo, gastos = _do_mes(mes)
    if not gastos:
        return f"Nenhum gasto registrado em {alvo}."
    por_cat: dict[str, float] = defaultdict(float)
    for g in gastos:
        por_cat[g["categoria"]] += numero(g["valor"])
    total = sum(por_cat.values())
    ordem = sorted(por_cat.items(), key=lambda kv: -kv[1])
    if player is not None:
        try:
            linhas = [f"{_BONITO.get(c, c):<14} {reais(v):>14}  {v / total:5.0%}"
                      for c, v in ordem]
            linhas += ["", f"{'TOTAL':<14} {reais(total):>14}", "",
                       *(f"{g['data']}  {reais(numero(g['valor']))}  {g['descricao']}"
                         for g in gastos[-15:])]
            player.show_content(f"GASTOS {alvo}", "\n".join(linhas))
        except Exception:
            pass
    top = ", ".join(f"{_BONITO.get(c, c)} {reais(v)}" for c, v in ordem[:3])
    n = len(gastos)
    return (f"Em {alvo} você gastou {reais(total)} em {n} "
            f"{'registro' if n == 1 else 'registros'}. Maiores: {top}.")


def _apagar_ultimo() -> str:
    gastos = ler(_ARQ)
    if not gastos:
        return "Não há gastos para apagar."
    ultimo = gastos.pop()
    escrever(_ARQ, _CAMPOS, gastos)
    return f"Apaguei o último gasto: {reais(numero(ultimo['valor']))} em {ultimo['descricao']}."


def _exportar(mes: str) -> str:
    alvo, gastos = _do_mes(mes)
    if not gastos:
        return f"Nenhum gasto em {alvo} para exportar."
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        return "Para exportar preciso do openpyxl: pip install openpyxl"
    wb = Workbook()
    ws = wb.active
    ws.title = alvo
    ws.append(["Data", "Valor (R$)", "Categoria", "Descrição"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for g in gastos:
        ws.append([g["data"], numero(g["valor"]),
                   _BONITO.get(g["categoria"], g["categoria"]), g["descricao"]])
    fim = ws.max_row
    ws.append([])
    ws.append(["TOTAL", f"=SUM(B2:B{fim})"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=2):
        for c in row:
            c.number_format = '"R$" #,##0.00'
    for col, w in zip("ABCD", (18, 14, 16, 40)):
        ws.column_dimensions[col].width = w
    path = DATA_DIR / f"gastos_{alvo}.xlsx"
    wb.save(path)
    return f"Planilha criada em {path}."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    action = str(p.get("action", "")).strip().lower()
    try:
        if action == "registrar":
            return _registrar(p)
        if action == "resumo":
            return _resumo(str(p.get("mes") or ""), player)
        if action in ("apagar_ultimo", "desfazer"):
            return _apagar_ultimo()
        if action == "exportar":
            return _exportar(str(p.get("mes") or ""))
        return "Ação desconhecida. Use registrar, resumo, apagar_ultimo ou exportar."
    except Exception as e:
        return f"O controle de gastos falhou: {e}"
