"""
Linha do tempo do mês — retrospectiva (fork PT-BR 1.6).

"Jarvis, o que eu fiz em outubro?" — junta TUDO que ficou registrado no
período: horas no PC por atividade e por projeto, commits, tarefas concluídas,
conquistas, jogos, alertas importantes, aniversários e cápsulas do tempo — e
conta como uma retrospectiva (com a IA, em texto corrido).

    "Jarvis, o que eu fiz em outubro?"         "Jarvis, retrospectiva do mês passado"
    "Jarvis, resumo da semana passada"         "Jarvis, o que eu fiz em 2026?"
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, ler_json, mostrar

PLUGIN = {
    "name": "retrospectiva",
    "brief": "Retrospective of a month/week/year: hours by activity and project, commits, tasks, achievements, games, events.",
    "description": (
        "Retrospective timeline of a period: periodo = month name ('outubro', 'outubro de 2026'), 'mês passado', "
        "'este mês', 'semana passada', a year ('2026') or 'ano'. Gathers PC hours by activity and project, commits, "
        "finished tasks, achievements, games, important events and tells it as a story."
    ),
    "parameters": {"type": "OBJECT", "properties": {"periodo": {"type": "STRING"}}, "required": []},
}

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def intervalo(texto: str, hoje: date | None = None) -> tuple[datetime, datetime, str]:
    """'outubro' → (1/10, 1/11, 'em outubro de 2026'); mês futuro = do ano passado (pura)."""
    hoje = hoje or date.today()
    t = _dobrar(texto or "este mes")

    def mes(ano, m):
        ini = datetime(ano, m, 1)
        fim = datetime(ano + (m == 12), m % 12 + 1, 1)
        return ini, fim, f"em {MESES[m - 1].replace('marco', 'março')} de {ano}"
    for i, nome in enumerate(MESES, 1):
        if nome in t or nome[:3] == t.strip()[:3] and len(t.strip()) <= 4:
            ano = re.search(r"(20\d\d)", t)
            a = int(ano.group(1)) if ano else (hoje.year if i <= hoje.month else hoje.year - 1)
            return mes(a, i)
    if "mes passado" in t:
        m = hoje.month - 1 or 12
        return mes(hoje.year if hoje.month > 1 else hoje.year - 1, m)
    if "semana passada" in t:
        ini = datetime.combine(hoje - timedelta(days=hoje.weekday() + 7), datetime.min.time())
        return ini, ini + timedelta(days=7), "na semana passada"
    if "semana" in t:
        ini = datetime.combine(hoje - timedelta(days=hoje.weekday()), datetime.min.time())
        return ini, datetime.combine(hoje + timedelta(days=1), datetime.min.time()), "nesta semana"
    ano = re.search(r"(20\d\d)", t)
    if ano or t.strip() in ("ano", "este ano", "esse ano"):
        a = int(ano.group(1)) if ano else hoje.year
        return datetime(a, 1, 1), datetime(a + 1, 1, 1), f"em {a}"
    return mes(hoje.year, hoje.month)[:2] + ("neste mês",)


def coletar(ini: datetime, fim: datetime) -> dict:
    desde, ate = ini.timestamp(), min(fim.timestamp(), datetime.now().timestamp())
    d: dict = {}
    try:
        from plugins.linha_do_tempo import resumo
        r = resumo(desde, ate)
        d["horas"] = r["ativo_s"] / 3600
        d["atividades"] = [(k, v / 3600) for k, v in r["atividades"][:8]]
        d["projetos"] = [(k, v / 3600) for k, v in r["projetos"][:6]]
    except Exception:
        pass
    try:
        from plugins import _projetos
        commits = []
        for repo in _projetos.repos():
            commits += [(repo.name, c) for c in _projetos.commits(repo, desde) if c["ts"] < ate]
        d["commits"] = len(commits)
        d["commits_por_repo"] = {}
        for nome, _c in commits:
            d["commits_por_repo"][nome] = d["commits_por_repo"].get(nome, 0) + 1
        d["mensagens_commit"] = [c["msg"] for _n, c in sorted(commits, key=lambda x: -x[1]["ts"])[:12]]
    except Exception:
        pass
    try:
        from plugins import prioridades
        d["tarefas"] = [t["titulo"] if "titulo" in t else t.get("nome", "") for t in prioridades.carregar()["tarefas"]
                        if t.get("concluida") and ini.isoformat() <= t["concluida"] < fim.isoformat()]
    except Exception:
        pass
    g = ler_json(MEMORIA / "gamificacao.json", {}) or {}
    d["xp"] = sum(h["xp"] for h in g.get("historico", []) if desde <= h["ts"] < ate)
    from plugins.gamificacao import CONQUISTAS
    nomes = {cid: nome for cid, nome, _t in CONQUISTAS}
    d["conquistas"] = [nomes.get(cid, cid) for cid, ts in (g.get("conquistas") or {}).items() if desde <= ts < ate]
    jogos = {}
    for s in ler_json(MEMORIA / "jogos.json", []) or []:
        if desde <= s["inicio"] < ate:
            jogos[s["jogo"]] = jogos.get(s["jogo"], 0) + (s["fim"] - s["inicio"]) / 3600
    d["jogos"] = sorted(jogos.items(), key=lambda x: -x[1])[:5]
    try:
        from plugins import _monitor_db
        d["eventos"] = [e["mensagem"] for e in _monitor_db.eventos(desde, 500)
                        if e["ts"] < ate and e.get("tipo") in ("seguranca", "alerta")][:8]
    except Exception:
        pass
    return d


def texto(d: dict, rotulo: str) -> list[str]:
    linhas = [f"RETROSPECTIVA {rotulo.upper()}", ""]
    if d.get("horas"):
        linhas.append(f"{d['horas']:.0f} h de PC. Atividades: " + ", ".join(f"{k} {v:.0f}h" for k, v in d.get("atividades", [])))
    if d.get("projetos"):
        linhas.append("Projetos: " + ", ".join(f"{k} {v:.0f}h" for k, v in d["projetos"]))
    if d.get("commits"):
        linhas.append(f"{d['commits']} commits: " + ", ".join(f"{k} ({v})" for k, v in d["commits_por_repo"].items()))
    if d.get("tarefas"):
        linhas.append(f"{len(d['tarefas'])} tarefas concluídas: " + "; ".join(d["tarefas"][:10]))
    if d.get("xp"):
        linhas.append(f"+{d['xp']} XP" + (f"; conquistas: {', '.join(d['conquistas'])}" if d.get("conquistas") else ""))
    if d.get("jogos"):
        linhas.append("Jogos: " + ", ".join(f"{k} {v:.0f}h" for k, v in d["jogos"]))
    if d.get("eventos"):
        linhas += ["Eventos importantes:"] + [f"  • {e}" for e in d["eventos"]]
    return linhas


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        ini, fim, rotulo = intervalo(str((parameters or {}).get("periodo") or ""))
        d = coletar(ini, fim)
        linhas = texto(d, rotulo)
        if len(linhas) <= 2:
            return f"Não tenho registros {rotulo} (a linha do tempo só existe a partir de quando o JARVIS ficou aberto)."
        from plugins import _ia
        historia = ""
        if _ia.disponivel():
            historia = _ia.perguntar(
                f"Conte em 4 a 6 frases, em português do Brasil e em segunda pessoa, como foi o período {rotulo} do usuário, "
                "como uma retrospectiva animada (destaque o projeto principal, conquistas e números). Use só os dados:\n"
                + "\n".join(linhas) + ("\nCommits: " + "; ".join(d.get("mensagens_commit", [])) if d.get("mensagens_commit") else ""),
                False, 40) or ""
        mostrar(player, f"RETROSPECTIVA — {rotulo}", (historia + "\n\n" if historia else "") + "\n".join(linhas[2:]))
        return f"[RETROSPECTIVA {rotulo}] " + (historia or "; ".join(linhas[2:6]))
    except Exception as e:
        return f"A retrospectiva falhou: {e}"
