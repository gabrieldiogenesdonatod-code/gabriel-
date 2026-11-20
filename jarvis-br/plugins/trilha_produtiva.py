"""
Trilha sonora da produtividade (3.0): o JARVIS descobre QUAIS músicas tocavam nas suas horas mais
produtivas e monta a sua trilha de foco calculada.

Ele cruza o que você pediu para tocar (música, playlist, DJ) com o quanto você produziu nas 2
horas seguintes: ferramentas de trabalho usadas no JARVIS (código, testes, git, loja, caixa…) e,
se você indicar a pasta, os commits do projeto. Compara com as horas sem música.

    "Jarvis, qual música me deixa mais produtivo?"      "Jarvis, toca a minha trilha de foco."

São padrões, não ciência: precisa de pelo menos 3 vezes com cada música para opinar.
"""

from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("trilha_produtiva", "Productivity soundtrack: which music you played before your most productive hours; plays the best one.",
           "analisar | tocar_melhor", "analisar: pasta (git repo, optional). tocar_melhor: plays the top music.", "pasta")

MUSICA = {"musica", "spotify", "jarvis_dj", "youtube_musica", "radio"}
TRABALHO = {"vigia_codigo", "testes_vivos", "git_assistente", "qualidade_codigo", "commit_mentiroso", "raio_x_projeto", "snippets",
            "regex_ajuda", "conversor_dados", "http_teste", "sqlite_ajuda", "log_analisador", "explorar_json", "caixa_loja",
            "clientes_loja", "cristal_malhas", "precificacao", "etiquetas", "fornecedores", "diario_treino_ia", "calculadora_ia",
            "documentacao", "pomodoro", "prioridades", "ponto", "dojo_debug", "arqueologo_codigo", "segredos_codigo"}
JANELA = 2 * 3600


def rotulo(params_json: str) -> str:
    try:
        p = json.loads(params_json or "{}")
    except ValueError:
        return ""
    for k in ("pedido", "musica", "playlist", "busca", "query", "nome", "genero"):
        if p.get(k):
            return norm(p[k])[:40]
    return ""


def efeitos(eventos: list[tuple[float, str]], trabalho: list[float], fim: float) -> list[tuple[str, float, int]]:
    """[(música, efeito %, vezes)] — produtividade nas 2 h após tocar contra a média das janelas sem música. Pura."""
    if not eventos or not trabalho:
        return []
    trabalho = sorted(trabalho)

    def conta(t0):
        return sum(1 for t in trabalho if t0 <= t < t0 + JANELA)
    com = {}
    for t, nome in eventos:
        com.setdefault(nome, []).append(conta(t))
    musicas = sorted(t for t, _ in eventos)
    ini = trabalho[0]
    sem = [conta(t0) for t0 in range(int(ini), int(fim) - JANELA, JANELA)
           if not any(t0 - JANELA < m < t0 + JANELA for m in musicas)]
    base = st.mean(sem) if len(sem) >= 3 else None
    if not base:
        return []
    out = [(n, (st.mean(v) - base) / base * 100, len(v)) for n, v in com.items() if len(v) >= 3]
    return sorted(out, key=lambda x: -x[1])


def _go(p, pl):
    from core import registro_uso
    desde = time.time() - 60 * 86400
    ch = registro_uso.chamadas(desde=desde)
    eventos = [(c["ts"], rotulo(c.get("params"))) for c in ch if c["ferramenta"] in MUSICA and c.get("ok") and
               str(c.get("acao") or "").lower() in ("tocar", "play", "ligar", "playlist", "")]
    eventos = [(t, n) for t, n in eventos if n]
    trabalho = [c["ts"] for c in ch if c["ferramenta"] in TRABALHO and c.get("ok")]
    pasta = str(p.get("pasta") or "")
    if pasta and Path(pasta).expanduser().is_dir():
        try:
            from plugins.commit_mentiroso import git
            trabalho += [float(x) for x in git(Path(pasta).expanduser(), "log", f"--since={int(desde)}", "--format=%at").split()]
        except Exception:
            pass
    res = efeitos(eventos, trabalho, time.time())
    if p["action"] == "tocar_melhor":
        melhor = (carregar("trilha", {}) or {}).get("melhor") or (res[0][0] if res and res[0][1] > 0 else "")
        if not melhor:
            return "Ainda não descobri a sua música de foco. Diga 'analisar' depois de alguns dias ouvindo música enquanto trabalha."
        from core import registro_ferramentas
        return registro_ferramentas.executar("musica", {"action": "tocar", "pedido": melhor}, pl)
    if not res:
        return (f"Ainda não dá para dizer: vi {len(eventos)} pedido(s) de música e {len(trabalho)} sinal(is) de trabalho em 60 dias. "
                "Preciso de cada música pelo menos 3 vezes e de horas de trabalho sem música para comparar.")
    if res[0][1] > 0:
        guardar("trilha", {"melhor": res[0][0], "quando": time.strftime("%Y-%m-%d")})
    return "Música × produtividade nas 2 horas seguintes:\n" + "\n".join(
        f"{n}: {e:+.0f}% ({v} vezes)" for n, e, v in res[:6]) + "\nSão padrões dos seus dados, não regra."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"analisar": _go, "tocar_melhor": _go}, player, "Trilha")
