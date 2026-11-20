"""
Gamificação da vida (fork PT-BR 1.6).

Você ganha XP, sobe de nível e desbloqueia conquistas com o que já faz:
tarefas concluídas, Pomodoros, commits, revisões do modo professor, treinos de
inglês e entrevista, código ditado… e com o que você contar ("treinei 40 min",
"li 20 páginas", "fiz 30 min de alongamento"). O JARVIS comemora quando você
sobe de nível — na 1.9, estilo Stark: "Parabéns, senhor. Nível 12 alcançado.
Novo título desbloqueado: Engenheiro Chefe." Vídeos da loja, aulas gravadas e
testes rodados também dão XP.

    "Jarvis, quanto XP eu tenho?"          "Jarvis, minhas conquistas"
    "Jarvis, treinei 40 minutos"           "Jarvis, estudei 1 hora de inglês"
"""

from __future__ import annotations

import re
import threading
import time
from datetime import date, timedelta

from plugins._comum import MEMORIA, falar, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "gamificacao",
    "brief": "Life gamification: XP, levels and achievements from tasks, focus, commits, study and reported activities.",
    "description": (
        "Life gamification. action='status' (XP, level, streak), 'conquistas' (achievements), 'registrar' with "
        "atividade (treino, estudo, leitura, cuidado, limpeza, outro) + minutos (when the user says they did something). "
        "Levels have Stark-style titles (Recruta … Engenheiro Chefe … Homem de Ferro); read level-ups as returned."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "status | conquistas | registrar"},
                       "atividade": {"type": "STRING"}, "minutos": {"type": "INTEGER"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "gamificacao.json"
# (ferramenta, ação ou None para qualquer) → XP
REGRAS = {("prioridades", "concluir"): 20, ("pomodoro", "iniciar"): 10, ("modo_professor", "responder"): 5,
          ("ditado_codigo", "pronto"): 25, ("gerador_testes", None): 15, ("documentacao", None): 15,
          ("professor_ingles", "comecar"): 15, ("ensina_errado", "palpite"): 5, ("entrevista", "terminar"): 30,
          ("cuidador", "feito"): 10, ("turno_noite", "agora"): 5,
          # 1.9
          ("cristal_video", None): 30, ("cristal_malhas", "conteudo"): 15, ("testes_vivos", "rodar"): 5,
          ("modo_aula", "parar"): 25, ("memoria_projeto", "anotar"): 2, ("snapshots", "agora"): 3}
# 1.9: títulos estilo Stark (nível mínimo, título)
TITULOS = [(1, "Recruta"), (3, "Estagiário da Stark Industries"), (5, "Técnico de Laboratório"),
           (8, "Engenheiro Júnior"), (10, "Engenheiro"), (12, "Engenheiro Chefe"), (15, "Diretor de P&D"),
           (18, "Mestre das Armaduras"), (20, "Arquiteto do Reator Arc"), (25, "Vingador Honorário"),
           (30, "Gênio, Bilionário, Playboy, Filantropo"), (40, "Homem de Ferro")]


def titulo_de(nivel: int) -> str:
    """O título do nível (pura)."""
    return [t for n, t in TITULOS if nivel >= n][-1]


def frase_nivel(nivel_antes: int, nivel: int) -> str:
    """'Parabéns, senhor. Nível 12 alcançado. Novo título desbloqueado: Engenheiro Chefe.' (pura)."""
    if nivel <= nivel_antes:
        return ""
    txt = f"Parabéns, senhor. Nível {nivel} alcançado."
    if titulo_de(nivel) != titulo_de(nivel_antes):
        txt += f" Novo título desbloqueado: {titulo_de(nivel)}."
    return txt
CATEGORIAS = {"treino": 1 / 2, "estudo": 1 / 2, "leitura": 1 / 3, "cuidado": 1 / 2, "limpeza": 1 / 3, "outro": 1 / 4}
CONQUISTAS = [  # (id, nome, teste(estado) )
    ("primeiro_xp", "Primeiro passo", lambda e: e["xp"] > 0),
    ("nivel5", "Nível 5", lambda e: nivel_de(e["xp"])[0] >= 5),
    ("nivel10", "Nível 10", lambda e: nivel_de(e["xp"])[0] >= 10),
    ("seq3", "3 dias seguidos", lambda e: sequencia(e["dias"]) >= 3),
    ("seq7", "Uma semana sem parar", lambda e: sequencia(e["dias"]) >= 7),
    ("seq30", "Um mês sem parar", lambda e: sequencia(e["dias"]) >= 30),
    ("commits10", "10 commits", lambda e: e["contagem"].get("commit", 0) >= 10),
    ("commits100", "100 commits", lambda e: e["contagem"].get("commit", 0) >= 100),
    ("tarefas25", "25 tarefas concluídas", lambda e: e["contagem"].get("prioridades", 0) >= 25),
    ("foco20", "20 Pomodoros", lambda e: e["contagem"].get("pomodoro", 0) >= 20),
    ("estudante", "100 revisões no modo professor", lambda e: e["contagem"].get("modo_professor", 0) >= 100),
    ("atleta", "10 treinos", lambda e: e["contagem"].get("treino", 0) >= 10),
    ("cuidador", "30 cuidados registrados", lambda e: e["contagem"].get("cuidado", 0) + e["contagem"].get("cuidador", 0) >= 30),
    ("entrevistado", "Primeira entrevista simulada", lambda e: e["contagem"].get("entrevista", 0) >= 1),
]
_iniciado = threading.Event()


def nivel_de(xp: float) -> tuple[int, int, int]:
    """(nível, XP dentro do nível, XP que o nível pede). Nível n começa em 100·n·(n−1)/2 (pura)."""
    n = 1
    while 100 * (n + 1) * n / 2 <= xp:
        n += 1
    inicio = 100 * n * (n - 1) / 2
    return n, int(xp - inicio), 100 * n


def sequencia(dias: list[str], hoje: date | None = None) -> int:
    """Dias seguidos com XP até hoje (ou ontem) (pura)."""
    hoje = hoje or date.today()
    s = set(dias)
    d = hoje if hoje.isoformat() in s else hoje - timedelta(days=1)
    n = 0
    while d.isoformat() in s:
        n += 1
        d -= timedelta(days=1)
    return n


def estado() -> dict:
    e = ler_json(_ARQ, {}) or {}
    e.setdefault("xp", 0)
    e.setdefault("dias", [])
    e.setdefault("contagem", {})
    e.setdefault("conquistas", {})
    e.setdefault("ultima_varredura", time.time())
    e.setdefault("historico", [])
    return e


def ganhar(e: dict, xp: float, motivo: str, chave: str) -> None:
    if xp <= 0:
        return
    e["xp"] += xp
    hoje = date.today().isoformat()
    if hoje not in e["dias"]:
        e["dias"] = (e["dias"] + [hoje])[-400:]
    e["contagem"][chave] = e["contagem"].get(chave, 0) + 1
    e["historico"] = (e["historico"] + [{"ts": time.time(), "xp": round(xp), "motivo": motivo}])[-300:]


def novas_conquistas(e: dict) -> list[str]:
    novas = []
    for cid, nome, teste in CONQUISTAS:
        if cid not in e["conquistas"] and teste(e):
            e["conquistas"][cid] = time.time()
            novas.append(nome)
    return novas


def varrer(e: dict) -> None:
    """XP pelo que aconteceu desde a última varredura (diário de uso e commits)."""
    desde, agora = float(e["ultima_varredura"]), time.time()
    try:
        from core import registro_uso
        for c in registro_uso.chamadas(desde, agora):
            if not c.get("ok"):
                continue
            xp = REGRAS.get((c["ferramenta"], (c.get("acao") or "").lower())) or REGRAS.get((c["ferramenta"], None))
            if xp:
                ganhar(e, xp, f"{c['ferramenta']} {c.get('acao') or ''}".strip(), c["ferramenta"])
    except Exception:
        pass
    try:
        from plugins import _projetos
        hoje_commits = 0
        for repo in _projetos.repos():
            for _c in _projetos.commits(repo, desde):
                if hoje_commits < 10:                          # no máximo 100 XP de commits por varredura
                    ganhar(e, 10, f"commit em {repo.name}", "commit")
                    hoje_commits += 1
    except Exception:
        pass
    e["ultima_varredura"] = agora


def _comemorar(player, e: dict, nivel_antes: int, novas: list[str]) -> None:
    nivel = nivel_de(e["xp"])[0]
    stark = frase_nivel(nivel_antes, nivel)
    if stark:
        extra = f" Depois, em meia frase, mencione as conquistas: {', '.join(novas)}." if novas else ""
        falar(player, f"[CONQUISTA] Diga exatamente, com tom de mordomo britânico orgulhoso: \"{stark}\"{extra} "
                      "Não chame nenhuma ferramenta.")
    elif novas:
        falar(player, f"[CONQUISTA] Comemore em UMA frase, estilo Stark: o usuário desbloqueou {', '.join(novas)}. "
                      "Não chame nenhuma ferramenta.")


def _laco(player) -> None:
    time.sleep(180)
    while True:
        try:
            e = estado()
            antes = nivel_de(e["xp"])[0]
            varrer(e)
            novas = novas_conquistas(e)
            gravar_json(_ARQ, e)
            _comemorar(player, e, antes, novas)
        except Exception as ex:
            print(f"[Gamificação] {ex}")
        time.sleep(600)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="gamificacao").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        e = estado()
        if acao == "registrar":
            atividade = str(p.get("atividade") or "outro").lower()
            cat = next((c for c in CATEGORIAS if c in atividade or atividade.startswith(c[:4])), "outro")
            if re.search(r"academia|corr|trein|muscula|bike|futebol|caminh", atividade):
                cat = "treino"
            minutos = max(1, min(240, int(p.get("minutos") or 30)))
            antes = nivel_de(e["xp"])[0]
            xp = round(minutos * CATEGORIAS[cat])
            ganhar(e, xp, f"{atividade} ({minutos} min)", cat)
            novas = novas_conquistas(e)
            gravar_json(_ARQ, e)
            n, dentro, precisa = nivel_de(e["xp"])
            extra = (f" {frase_nivel(antes, n)}" if n > antes else "") + (f" Conquista: {', '.join(novas)}!" if novas else "")
            return f"+{xp} XP por {atividade}. Nível {n} ({dentro}/{precisa}).{extra}"
        if acao == "conquistas":
            feitas = [nome for cid, nome, _t in CONQUISTAS if cid in e["conquistas"]]
            faltam = [nome for cid, nome, _t in CONQUISTAS if cid not in e["conquistas"]]
            mostrar(player, "CONQUISTAS", "\n".join([f"🏆 {x}" for x in feitas] + [f"🔒 {x}" for x in faltam]))
            return f"{len(feitas)} de {len(CONQUISTAS)} conquistas" + (f": {', '.join(feitas[-4:])}" if feitas else "") + \
                (f". Próxima fácil: {faltam[0]}." if faltam else ". Todas desbloqueadas!")
        varrer(e)
        novas_conquistas(e)
        gravar_json(_ARQ, e)
        n, dentro, precisa = nivel_de(e["xp"])
        hoje = sum(h["xp"] for h in e["historico"] if h["ts"] >= time.mktime(date.today().timetuple()))
        return (f"Nível {n} — {titulo_de(n)}. {dentro}/{precisa} XP para o próximo ({int(e['xp'])} XP no total). Hoje: +{hoje} XP. "
                f"Sequência: {sequencia(e['dias'])} dia(s).")
    except Exception as ex:
        return f"A gamificação falhou: {ex}"
