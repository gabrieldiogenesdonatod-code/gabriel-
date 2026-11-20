"""
Estado do mundo (fork PT-BR 2.4).

Um objeto central que sabe o que está acontecendo AGORA: que horas são, o que
você está fazendo (jogando, programando, editando, numa chamada, numa live,
assistindo, ausente), se tem música tocando e se o JARVIS está falando.

Todo plugin pergunta aqui antes de falar ou agir:

    from core import estado_mundo
    e = estado_mundo.agora()                 # dict com tudo
    if estado_mundo.pode_falar("normal"): …   # "urgente" | "normal" | "baixa"

A central de avisos (core/central_avisos.py) usa isto para segurar o que não
é urgente enquanto você joga e entregar um resumo depois. As leituras são
baratas (janela em foco, ociosidade, lista de processos a cada 10 s) e ficam
em cache por 3 segundos.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime

CACHE_S = 3.0
PROCESSOS_S = 10.0
AUSENTE_S = 300.0

PROGRAMACAO = {"code.exe", "pycharm64.exe", "idea64.exe", "devenv.exe", "sublime_text.exe", "cursor.exe",
               "windowsterminal.exe", "rider64.exe", "webstorm64.exe", "android studio.exe", "studio64.exe",
               "notepad++.exe", "arduino ide.exe", "godot.exe"}
EDICAO = {"capcut.exe", "adobe premiere pro.exe", "afterfx.exe", "photoshop.exe", "resolve.exe", "fl64.exe",
          "audacity.exe", "blender.exe", "illustrator.exe", "canva.exe", "lightroom.exe", "kdenlive.exe",
          "vegas200.exe", "vegas190.exe", "filmora.exe"}
CHAMADA_PROC = {"zoom.exe", "ms-teams.exe", "teams.exe", "skype.exe"}
CHAMADA_TITULO = re.compile(r"(?i)(reuni[aã]o do zoom|zoom meeting|google meet|meet - |\| microsoft teams.*chamada|"
                            r"chamada de (voz|v[ií]deo)|in call|em chamada)")
LIVE_PROC = {"obs64.exe", "obs32.exe", "streamlabs obs.exe", "streamlabs desktop.exe", "xsplit.core.exe"}
VIDEO_TITULO = re.compile(r"(?i)( - youtube|netflix|prime video|disney\+|twitch|globoplay|max\b|crunchyroll)")

ROTULOS = {"jogando": "jogando", "programando": "programando", "editando": "editando", "em_chamada": "numa chamada",
           "live": "numa live", "assistindo": "assistindo um vídeo", "ausente": "longe do PC", "livre": "usando o PC",
           "cinema": "numa sessão de cinema",                      # Fork PT-BR 2.7
           "dormindo": "dormindo"}                                 # Fork PT-BR 2.8: modo dormir

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "estado": None, "procs_ts": 0.0, "procs": set()}
_ouvintes: list = []
_anterior = {"atividade": ""}


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def periodo_do_dia(h: int) -> str:
    return "madrugada" if h < 6 else "manhã" if h < 12 else "tarde" if h < 18 else "noite"


def inferir(hora: datetime, processo: str, titulo: str, ocioso_s: float, processos: set[str],
            jogo: str | None = None, presente: bool | None = None, som: bool | None = None,
            jarvis_falando: bool = False, modo_jogo: bool = False, cinema: bool = False,
            dormindo: bool = False) -> dict:
    """Junta as leituras num estado (pura)."""
    p = (processo or "").lower()
    t = titulo or ""
    procs = {x.lower() for x in processos}
    assistindo = bool(VIDEO_TITULO.search(t)) and som is not False
    if dormindo:                                                # Fork PT-BR 2.8: modo dormir = não perturbe
        atividade = "dormindo"
    elif cinema:                                                # Fork PT-BR 2.7: sessão de cinema = não perturbe
        atividade = "cinema"
    elif jogo or modo_jogo:
        atividade = "jogando"
    elif p in CHAMADA_PROC or CHAMADA_TITULO.search(t):
        atividade = "em_chamada"
    elif procs & LIVE_PROC:
        atividade = "live"
    elif (ocioso_s >= AUSENTE_S and not assistindo) or presente is False and ocioso_s >= 60:
        atividade = "ausente"
    elif p in PROGRAMACAO or (p in ("chrome.exe", "msedge.exe", "firefox.exe") and re.search(
            r"(?i)github|stack ?overflow|localhost|127\.0\.0\.1|colab", t)):
        atividade = "programando"
    elif p in EDICAO:
        atividade = "editando"
    elif assistindo:
        atividade = "assistindo"
    else:
        atividade = "livre"
    if atividade in ("jogando", "em_chamada", "live", "cinema", "dormindo"):
        fala = "silencio"
    elif atividade == "ausente":
        fala = "guardar"
    elif atividade in ("programando", "editando"):
        fala = "curto"
    else:
        fala = "normal"
    musica = bool(som) and (bool(procs & {"spotify.exe", "deezer.exe", "tidal.exe"}) or "youtube music" in t.lower()
                            or "spotify" in t.lower())
    return {"hora": hora.strftime("%H:%M"), "periodo": periodo_do_dia(hora.hour), "atividade": atividade,
            "rotulo": ROTULOS[atividade], "jogo": jogo or "", "app": processo or "", "titulo": t[:120],
            "ocioso_s": round(ocioso_s), "presente": presente, "som": som, "musica": musica,
            "jarvis_falando": jarvis_falando, "fala": fala,
            "ocupado": atividade in ("jogando", "em_chamada", "live", "programando", "editando", "cinema",
                                     "dormindo")}


def permite(estado: dict, prioridade: str) -> bool:
    """Pode falar agora com essa prioridade? (pura)"""
    if prioridade == "urgente":
        return True
    if prioridade == "baixa":
        return False
    return estado.get("fala") in ("normal", "curto") and not estado.get("jarvis_falando")


def descrever(e: dict) -> str:
    partes = [f"São {e['hora']} ({e['periodo']}). Você está {e['rotulo']}"]
    if e.get("jogo"):
        partes[0] += f" ({e['jogo']})"
    if e.get("musica"):
        partes.append("tem música tocando")
    if e.get("ocupado"):
        partes.append("estou falando só o essencial")
    elif e.get("fala") == "guardar":
        partes.append("guardo os avisos para quando você voltar")
    return "; ".join(partes) + "."


# ── leituras de verdade ───────────────────────────────────────────────────────
def _processos() -> set[str]:
    agora = time.time()
    if agora - _cache["procs_ts"] < PROCESSOS_S:
        return _cache["procs"]
    try:
        import psutil
        procs = {(p.info.get("name") or "").lower() for p in psutil.process_iter(["name"])}
    except Exception:
        procs = set()
    _cache.update(procs=procs, procs_ts=agora)
    return procs


def _ler() -> dict:
    processo, titulo, ocioso = "", "", 0.0
    try:
        from plugins.linha_do_tempo import foco_atual, ocioso_segundos
        processo, titulo = foco_atual()
        ocioso = ocioso_segundos()
    except Exception:
        pass
    jogo = None
    try:
        from plugins.companheiro_jogo import eh_jogo
        jogo = eh_jogo(processo, titulo)
    except Exception:
        pass
    modo_jogo = cinema = False
    try:
        from plugins._comum import MEMORIA, ler_json
        modo_jogo = bool((ler_json(MEMORIA / "modo_jogo.json", {}) or {}).get("ativo"))
        _s = (ler_json(MEMORIA / "cinema.json", {}) or {}).get("sessao", {})                       # 2.7
        cinema = bool(_s.get("ativa")) and time.time() - float(_s.get("inicio") or 0) < 6 * 3600  # 2.7.1
    except Exception:
        pass
    som = None
    try:
        from plugins import _midia
        v = _midia.pico()
        som = None if v is None else v > 0.01
    except Exception:
        pass
    falando = False
    try:
        from core import registro_ferramentas
        falando = bool(getattr(registro_ferramentas.app(), "_is_speaking", False))
    except Exception:
        pass
    presente = None
    try:
        from plugins import pausa_ausente
        presente = pausa_ausente.presente_agora()
    except Exception:
        pass
    dormindo = False
    try:
        from core import sono                                   # Fork PT-BR 2.8
        dormindo = sono.dormindo()
    except Exception:
        pass
    return inferir(datetime.now(), processo, titulo, ocioso, _processos(), jogo, presente, som, falando, modo_jogo,
                   cinema, dormindo)


def agora(forcar: bool = False) -> dict:
    with _lock:
        if not forcar and _cache["estado"] is not None and time.time() - _cache["ts"] < CACHE_S:
            return dict(_cache["estado"])
    e = _ler()
    with _lock:
        _cache.update(estado=e, ts=time.time())
        mudou = e["atividade"] != _anterior["atividade"]
        antes = _anterior["atividade"]
        _anterior["atividade"] = e["atividade"]
    if mudou and antes:
        for fn in list(_ouvintes):
            try:
                fn(antes, e)
            except Exception as ex:
                print(f"[EstadoMundo] {ex}")
    return dict(e)


def pode_falar(prioridade: str = "normal") -> bool:
    try:
        return permite(agora(), prioridade)
    except Exception:
        return prioridade != "baixa"


def ao_mudar(fn) -> None:
    """fn(atividade_anterior, estado_novo) quando a atividade muda."""
    if fn not in _ouvintes:
        _ouvintes.append(fn)


def instrucao_sessao() -> str:
    """Linha para as instruções da sessão: o modelo sabe o contexto do momento em que conectou."""
    try:
        e = agora()
    except Exception:
        return ""
    regra = {"silencio": "Ele está concentrado: responda em UMA frase curta, sem puxar assunto.",
             "curto": "Ele está trabalhando: respostas curtas e diretas.",
             "guardar": "", "normal": ""}.get(e["fala"], "")
    return f"[ESTADO AGORA] {descrever(e)} {regra}".strip()
