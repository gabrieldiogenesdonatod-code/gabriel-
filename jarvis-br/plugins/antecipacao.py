"""
Antecipação (3.0): o JARVIS aprende o que você costuma pedir em cada horário e deixa PRONTO antes.

    Você sempre pede o resumo do dia às 8h e a meta de vendas às 9h → às 8h ele já gerou o resumo e
    deixou no painel; às 9h, a meta.

Só antecipa o que é de LEITURA (ver, listar, status, resumo…): nunca abre, apaga, manda mensagem
ou toca música sem você pedir — essas ele só sugere. Aprende com o diário de uso dos últimos 30
dias: um hábito conta quando aparece no mesmo horário em pelo menos 4 dias diferentes.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict

from plugins._lote2 import P, carregar, guardar, rodar

PLUGIN = P("antecipacao", "Anticipation: learns what you usually ask at each hour and prepares read-only results in advance (summary, sales "
           "goal, agenda) before you ask; suggests the rest.",
           "habitos | agora | ligar | desligar",
           "habitos: learned habits by hour. agora: what I would prepare now. ligar/desligar: automatic preparation.", "")

LEITURA = {"listar", "ver", "status", "hoje", "resumo", "total", "proximos", "proximas", "pendentes", "agora", "semana", "vencendo",
           "ultimo", "saldo", "placar", "contagens", "ofensivas", "estante", "lista", "sentir", "prever", "falta", "relatorio", "completo"}
NUNCA = {"antecipacao", "outras_ferramentas", "catalogo", "controle_pc", "whatsapp", "whatsapp_conversas", "app_celular",
         "celular_android", "agendador", "protocolos", "modos", "palavras_secretas"}
MIN_DIAS = 4


def habitos(chamadas: list[dict]) -> dict[int, list[tuple[str, str, int]]]:
    """{hora: [(ferramenta, params json, dias)]} — o que aparece na mesma hora em 4+ dias. Pura."""
    dias = defaultdict(set)
    for c in chamadas:
        if not c.get("ok") or c["ferramenta"] in NUNCA:
            continue
        t = time.localtime(c["ts"])
        dias[(t.tm_hour, c["ferramenta"], c.get("params") or "{}")].add(time.strftime("%Y-%m-%d", t))
    out = defaultdict(list)
    for (h, f, p), ds in dias.items():
        if len(ds) >= MIN_DIAS:
            out[h].append((f, p, len(ds)))
    for h in out:
        out[h].sort(key=lambda x: -x[2])
    return dict(out)


def so_leitura(params_json: str) -> bool:
    try:
        acao = str(json.loads(params_json).get("action") or "")
    except ValueError:
        return False
    return acao.lower() in LEITURA


def _chamadas():
    from core import registro_uso
    return registro_uso.chamadas(desde=time.time() - 30 * 86400)


def passo(player) -> None:
    est = carregar("antecipacao", {"ligado": True, "feitos": {}})
    if not est.get("ligado", True):
        return
    agora, hoje = time.localtime(), time.strftime("%Y-%m-%d")
    est["feitos"] = {k: v for k, v in est.get("feitos", {}).items() if v == hoje}
    hab = habitos(_chamadas()).get(agora.tm_hour, [])
    from core import registro_ferramentas
    from plugins._comum import mostrar
    feitos = 0
    for f, p, dias in hab:
        chave = f"{agora.tm_hour}|{f}|{p}"
        if chave in est["feitos"] or not so_leitura(p) or feitos >= 2:
            continue
        r = str(registro_ferramentas.executar(f, json.loads(p), player))
        mostrar(player, f"JÁ DEIXEI PRONTO — {f.replace('_', ' ').upper()}", r[:3000])
        est["feitos"][chave] = hoje
        feitos += 1
    guardar("antecipacao", est)


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("antecipacao", lambda: passo(player), a_cada_s=600, primeira_em_s=240)


def _go(p, pl):
    a, est = p["action"], carregar("antecipacao", {"ligado": True, "feitos": {}})
    if a in ("ligar", "desligar"):
        est["ligado"] = a == "ligar"
        guardar("antecipacao", est)
        return "Antecipação ligada: vou deixar pronto o que você costuma pedir." if est["ligado"] else "Antecipação desligada."
    hab = habitos(_chamadas())
    if a == "agora":
        h = time.localtime().tm_hour
        itens = hab.get(h, [])
        if not itens:
            return "Nesse horário você não tem um pedido de costume (ainda)."
        return "Nesse horário você costuma pedir: " + "; ".join(
            f"{f} {json.loads(pp).get('action', '')} ({d} dias)" + ("" if so_leitura(pp) else " — só sugiro, não faço sozinho")
            for f, pp, d in itens[:4]) + "."
    if not hab:
        return "Ainda não aprendi hábitos de horário. Preciso que algo se repita na mesma hora em 4 dias diferentes."
    return "\n".join(f"{h:02d}h: " + ", ".join(f"{f} {json.loads(pp).get('action', '')} ({d}x)" for f, pp, d in itens[:3])
                     for h, itens in sorted(hab.items()))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("habitos agora ligar desligar".split(), _go), player, "Antecipação")
