"""
Relatório semanal da loja, falado (fork PT-BR 1.9).

Toda segunda de manhã (na primeira vez que o JARVIS estiver aberto a partir das
8h), ele conta: quanto vendeu na semana, o que mais vendeu, o que está parado
no estoque e qual peça vale divulgar. Também vai no seu WhatsApp, se estiver
conectado.

    "Jarvis, relatório da loja"           (na hora, da última semana)
    "Jarvis, liga/desliga o relatório de segunda"

Usa as vendas e o estoque do Cristal Malhas (memory/cristal_vendas.csv e
cristal_estoque.csv).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

from plugins._comum import MEMORIA, cfg, falar, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "relatorio_loja",
    "brief": "Weekly store report (spoken every Monday morning): sales, best sellers, stuck stock and what to promote.",
    "description": ("Weekly store report from the Cristal Malhas sales and stock: total, best sellers, products with "
                    "stock and no recent sales, and a suggestion of which piece to promote this week. action='agora' "
                    "(report now), 'ligar' / 'desligar' (automatic Monday report), 'status'."),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "agora | ligar | desligar | status"}},
                   "required": []},
}

PLUGIN_SETTINGS = {
    "namespace": "relatorio_loja",
    "title": "Relatório semanal da loja",
    "fields": [
        {"key": "ligado", "label": "Falar o relatório toda segunda de manhã", "type": "toggle", "default": True},
        {"key": "hora", "label": "A partir de que hora (segunda)", "type": "text", "default": "8"},
        {"key": "dias_parado", "label": "Dias sem vender para contar como 'parado'", "type": "text", "default": "21"},
    ],
}

ARQ = MEMORIA / "relatorio_loja.json"
_iniciou = threading.Event()


def _data(v: dict) -> datetime | None:
    try:
        return datetime.strptime(str(v.get("data", ""))[:10], "%Y-%m-%d")
    except ValueError:
        return None


def calcular(vendas: list[dict], estoque: list[dict], hoje: datetime, dias_parado: int = 21) -> dict:
    """Números da semana que passou (pura)."""
    from plugins._dados_br import chave, numero
    inicio = hoje - timedelta(days=7)
    semana = [v for v in vendas if (d := _data(v)) and inicio <= d < hoje + timedelta(days=1)]
    anterior = [v for v in vendas if (d := _data(v)) and inicio - timedelta(days=7) <= d < inicio]
    por_produto: dict = defaultdict(lambda: [None, 0, 0.0])
    for v in semana:
        p = por_produto[chave(v.get("produto", ""))]
        p[0] = p[0] or v.get("produto", "")
        p[1] += int(numero(v.get("quantidade")))
        p[2] += numero(v.get("total"))
    top = sorted(por_produto.values(), key=lambda x: (-x[1], -x[2]))[:5]
    ultima_venda = {}
    for v in vendas:
        d = _data(v)
        if d:
            k = chave(v.get("produto", ""))
            ultima_venda[k] = max(ultima_venda.get(k, d), d)
    parados = []
    for e in estoque:
        qtd = int(numero(e.get("quantidade")))
        if qtd <= 0:
            continue
        ult = ultima_venda.get(chave(e.get("produto", "")))
        dias = (hoje - ult).days if ult else None
        if dias is None or dias >= dias_parado:
            parados.append({"produto": e.get("produto", ""), "quantidade": qtd, "dias": dias})
    parados.sort(key=lambda x: (-(x["dias"] if x["dias"] is not None else 9999), -x["quantidade"]))
    total = sum(numero(v.get("total")) for v in semana)
    total_ant = sum(numero(v.get("total")) for v in anterior)
    sugestao = parados[0]["produto"] if parados else (top[0][0] if top else "")
    return {"vendas": len(semana), "pecas": sum(int(numero(v.get("quantidade"))) for v in semana), "total": total,
            "total_anterior": total_ant, "top": [{"produto": t[0], "pecas": t[1], "total": t[2]} for t in top],
            "parados": parados[:8], "sugestao": sugestao}


def texto(r: dict) -> str:
    from plugins._dados_br import reais
    if not r["vendas"]:
        base = "Na última semana não houve vendas registradas."
    else:
        base = f"Na última semana: {r['vendas']} vendas, {r['pecas']} peças, {reais(r['total'])}"
        if r["total_anterior"]:
            dif = (r["total"] - r["total_anterior"]) / r["total_anterior"] * 100
            base += f" ({'+' if dif >= 0 else ''}{dif:.0f}% sobre a semana anterior)"
        base += f". Mais vendido: {r['top'][0]['produto']} ({r['top'][0]['pecas']})."
    if r["parados"]:
        base += " Parado no estoque: " + ", ".join(
            f"{p['produto']} ({p['quantidade']} un., " + (f"{p['dias']} dias sem vender)" if p["dias"] is not None
                                                          else "nunca vendeu)") for p in r["parados"][:3]) + "."
    if r["sugestao"]:
        base += f" Sugestão para divulgar esta semana: {r['sugestao']}."
    return base


def gerar() -> tuple[dict, str]:
    from plugins._dados_br import ler
    c = cfg("relatorio_loja", PLUGIN_SETTINGS)
    try:
        dias = int(str(c.get("dias_parado") or 21))
    except ValueError:
        dias = 21
    r = calcular(ler("cristal_vendas.csv"), ler("cristal_estoque.csv"), datetime.now(), dias)
    return r, texto(r)


def entregar(player, falado: bool = True) -> str:
    r, t = gerar()
    mostrar(player, "RELATÓRIO SEMANAL DA LOJA", t.replace(". ", ".\n"))
    try:
        from plugins import _whatsapp
        if _whatsapp.rodando():
            _whatsapp.para_donos("🛍️ Relatório da semana\n\n" + t.replace(". ", ".\n"))
    except Exception:
        pass
    if falado:
        falar(player, f"[RELATÓRIO DA LOJA] Bom dia! Conte ao usuário, de forma animada e em até 4 frases: {t} "
                      "Não chame nenhuma ferramenta.")
    return t


def deve_rodar(agora: datetime, ultima_semana: str, hora: int = 8) -> bool:
    """Segunda, depois da hora, uma vez por semana (pura)."""
    semana = f"{agora.isocalendar()[0]}-{agora.isocalendar()[1]}"
    return agora.weekday() == 0 and agora.hour >= hora and ultima_semana != semana


def _laco(player) -> None:
    time.sleep(90)
    while True:
        try:
            c = cfg("relatorio_loja", PLUGIN_SETTINGS)
            agora = datetime.now()
            est = ler_json(ARQ, {}) or {}
            try:
                hora = int(str(c.get("hora") or 8))
            except ValueError:
                hora = 8
            if c.get("ligado", True) and deve_rodar(agora, est.get("semana", ""), hora):
                est["semana"] = f"{agora.isocalendar()[0]}-{agora.isocalendar()[1]}"
                gravar_json(ARQ, est)
                entregar(player)
        except Exception as e:
            print(f"[RelatórioLoja] {e}")
        time.sleep(600)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="relatorio_loja").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "agora").lower()
    try:
        if acao in ("ligar", "desligar"):
            from plugins._comum import salvar_cfg
            salvar_cfg("relatorio_loja", {"ligado": acao == "ligar"})
            return "Relatório de segunda ligado." if acao == "ligar" else "Relatório de segunda desligado."
        if acao == "status":
            c = cfg("relatorio_loja", PLUGIN_SETTINGS)
            return f"Relatório de segunda {'ligado' if c.get('ligado', True) else 'desligado'}, a partir das {c.get('hora', 8)}h."
        return entregar(player, falado=False)
    except Exception as e:
        return f"O relatório falhou: {e}"
