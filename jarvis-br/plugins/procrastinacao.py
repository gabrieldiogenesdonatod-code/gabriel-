"""
Detector de procrastinação (fork PT-BR 2.10).

O JARVIS repara quando você fica voltando pra uma distração (abriu o YouTube três
vezes em poucos minutos, por exemplo) e puxa conversa — de leve, sem dar sermão.

Ele usa o que a linha do tempo (plugins/linha_do_tempo.py) já vê: qual janela está
na frente. Conta só as VEZES que você ENTRA numa distração (não o tempo que fica), e
só cutuca se você abriu demais num intervalo curto. Fica quieto quando você está
jogando, em chamada, no modo cinema ou dormindo, e respeita um descanso entre os
toques (pra não encher o saco). Liga/desliga e ajusta tudo em ⚙.

    (sozinho) "Senhor, é a terceira vez no YouTube em 8 minutos — era pra estar no
               projeto do SENAI, né? Quer que eu te traga de volta?"
    "Jarvis, tô procrastinando?"      "Jarvis, foca" (silencia os toques por 1h)
"""

from __future__ import annotations

import threading
import time
import unicodedata
from datetime import datetime

from plugins._comum import cfg, registrar, sim

PLUGIN = {
    "name": "procrastinacao",
    "brief": "Procrastination nudge: notices you keep reopening a distraction (YouTube, Instagram…) and gently checks in.",
    "description": (
        "Watches (via the activity timeline) when the user keeps reopening a distraction site/app in a short window "
        "and gently checks in — it runs by itself. Use when the user asks 'tô procrastinando?', 'me ajuda a focar', "
        "'quanto tempo perdi hoje?', or 'foca'/'silencia' to mute the nudges for a while. action: 'status' (am I "
        "procrastinating right now / today's distraction time), 'focar' (mute nudges, optional minutos), 'retomar' "
        "(unmute). The proactive nudge is automatic; this tool is for the user asking about it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | focar | retomar"},
            "minutos": {"type": "NUMBER", "description": "for 'focar': how long to stay quiet (default 60)"},
        },
    },
}

PLUGIN_SETTINGS = {
    "namespace": "procrastinacao",
    "title": "Detector de procrastinação",
    "fields": [
        {"key": "ligado", "label": "Me cutucar quando eu ficar procrastinando", "type": "toggle", "default": True},
        {"key": "distracoes", "label": "O que conta como distração (separado por vírgula)", "type": "text",
         "default": "YouTube, Instagram, TikTok, Facebook, Netflix, Twitch, X/Twitter, Shopee, Mercado Livre, Twitter"},
        {"key": "vezes", "label": "Cutucar depois de quantas aberturas seguidas", "type": "text", "default": "3"},
        {"key": "janela_min", "label": "…dentro de quantos minutos", "type": "text", "default": "10"},
        {"key": "descanso_min", "label": "Descanso entre um toque e outro (minutos)", "type": "text", "default": "30"},
        {"key": "so_trabalhando", "label": "Só me cutucar se eu estava num trabalho/projeto antes", "type": "toggle",
         "default": False},
    ],
}

_lock = threading.RLock()
_iniciou = threading.Event()
_estado = {"ultima_ativ": "", "aberturas": [], "ultimo_cutucao": 0.0, "silencio_ate": 0.0, "ultimo_trabalho": "",
           "distracao_s_hoje": 0.0, "dia": "", "ultimo_poll": 0.0}


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def _c() -> dict:
    return cfg("procrastinacao", PLUGIN_SETTINGS)


def _int(v, padrao: int) -> int:
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return padrao


def lista_distracoes(texto: str) -> set[str]:
    return {dobrar(x).strip() for x in str(texto or "").split(",") if x.strip()}


def eh_distracao(atividade: str, distracoes: set[str]) -> bool:
    a = dobrar(atividade)
    return bool(a) and any(d and (d in a or a in d) for d in distracoes)


# ── o miolo, puro e testável ────────────────────────────────────────────────────
def registrar_troca(aberturas: list[dict], ultima_ativ: str, atividade: str, agora: float,
                    distracoes: set[str], janela_s: float) -> tuple[list[dict], bool]:
    """Se a pessoa ACABOU de entrar numa distração (trocou de janela pra ela), anota a abertura.
    Devolve (aberturas podadas, entrou_numa_distracao_agora) — puro."""
    entrou = False
    if atividade and dobrar(atividade) != dobrar(ultima_ativ) and eh_distracao(atividade, distracoes):
        aberturas = aberturas + [{"ativ": dobrar(atividade), "ts": agora}]
        entrou = True
    aberturas = [a for a in aberturas if agora - a["ts"] <= janela_s][-50:]
    return aberturas, entrou


def contar(aberturas: list[dict], atividade: str, agora: float, janela_s: float) -> int:
    a = dobrar(atividade)
    return sum(1 for x in aberturas if x["ativ"] == a and agora - x["ts"] <= janela_s)


def deve_cutucar(vezes_agora: int, vezes_alvo: int, agora: float, ultimo_cutucao: float, descanso_s: float,
                silencio_ate: float) -> bool:
    """Puro: já pode cutucar? (abriu demais, passou o descanso, não está em foco silenciado)."""
    if agora < silencio_ate:
        return False
    if vezes_agora < max(2, vezes_alvo):
        return False
    if not ultimo_cutucao:                      # nunca cutucou ainda: pode (não depende do relógio absoluto)
        return True
    return agora - ultimo_cutucao >= descanso_s


def frase_cutucao(atividade: str, vezes: int, janela_min: int, trabalho: str = "") -> str:
    """O que ele fala (pura)."""
    base = f"Senhor, é a {vezes}ª vez no {atividade} em {janela_min} minutos."
    if trabalho:
        return base + f" Você estava em {trabalho} — quer que eu te traga de volta, ou é pausa mesmo?"
    return base + " Tá rolando uma procrastinada? Se for pausa, tudo bem; se não, eu te ajudo a voltar ao foco."


# ── laço (usa a linha do tempo que já existe) ────────────────────────────────────
def _poll(agora: float | None = None, leitura: tuple | None = None) -> str:
    """Uma leitura do foco. Devolve o texto do cutucão se for a hora, senão ''.
    `leitura` = (atividade, projeto, ocioso) pode ser injetada (testes); senão lê a linha do tempo."""
    agora = time.time() if agora is None else agora
    c = _c()
    if not sim(c.get("ligado", True)):
        return ""
    distracoes = lista_distracoes(c.get("distracoes"))
    janela_s = _int(c.get("janela_min"), 10) * 60
    vezes_alvo = _int(c.get("vezes"), 3)
    descanso_s = _int(c.get("descanso_min"), 30) * 60
    if leitura is not None:
        atividade, projeto, ocioso = leitura
    else:
        try:
            from plugins import linha_do_tempo
            proc, titulo = linha_do_tempo.foco_atual()
            _app, atividade, projeto = linha_do_tempo.classificar(proc, titulo)
            ocioso = linha_do_tempo.ocioso_segundos()
        except Exception:
            return ""
    with _lock:
        ult_poll = _estado["ultimo_poll"]
        _estado["ultimo_poll"] = agora
        # tempo de distração de hoje (pro "quanto perdi hoje")
        dia = datetime.fromtimestamp(agora).strftime("%Y-%m-%d")
        if _estado["dia"] != dia:
            _estado.update(dia=dia, distracao_s_hoje=0.0)
        if ult_poll and agora - ult_poll < 90 and ocioso < 60 and eh_distracao(_estado["ultima_ativ"], distracoes):
            _estado["distracao_s_hoje"] += agora - ult_poll
        # trabalho que ele estava fazendo antes (pra citar)
        if projeto or atividade in ("Programando", "programando", "código", "VS Code", "Word", "Excel"):
            _estado["ultimo_trabalho"] = projeto or atividade
        aberturas, entrou = registrar_troca(_estado["aberturas"], _estado["ultima_ativ"], atividade, agora,
                                            distracoes, janela_s)
        _estado["aberturas"] = aberturas
        _estado["ultima_ativ"] = atividade
        if ocioso >= 60 or not entrou:
            return ""
        vezes = contar(aberturas, atividade, agora, janela_s)
        if not deve_cutucar(vezes, vezes_alvo, agora, _estado["ultimo_cutucao"], descanso_s, _estado["silencio_ate"]):
            return ""
        trabalho = _estado["ultimo_trabalho"] if sim(c.get("so_trabalhando")) or _estado["ultimo_trabalho"] else ""
        if sim(c.get("so_trabalhando")) and not trabalho:
            return ""
        _estado["ultimo_cutucao"] = agora
        janela_min = _int(c.get("janela_min"), 10)
    return frase_cutucao(atividade, vezes, janela_min, trabalho)


def _pode_falar() -> bool:
    try:
        from core import estado_mundo
        return estado_mundo.permite(estado_mundo.agora(), "default")
    except Exception:
        return True


def _laco(player) -> None:
    time.sleep(90)
    while True:
        try:
            texto = _poll()
            if texto and _pode_falar():
                from plugins._notificar import notificar
                notificar(player, texto, titulo="Foco", etiqueta="FOCO", chave="procrastinacao",
                          intervalo_s=_int(_c().get("descanso_min"), 30) * 60, prioridade="default")
                registrar(player, f"🎯 {texto}")
        except Exception as e:
            print(f"[Procrastinação] {e}")
        time.sleep(8)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, args=(player,), daemon=True, name="procrastinacao").start()


# ── ferramenta ───────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "status").strip()
    if acao in ("focar", "foca", "silenciar", "modo_foco"):
        mins = _int(p.get("minutos"), 60)
        with _lock:
            _estado["silencio_ate"] = time.time() + mins * 60
        return f"Modo foco: não te cutuco por {mins} minutos. Bom trabalho, senhor."
    if acao in ("retomar", "voltar", "dessilenciar"):
        with _lock:
            _estado["silencio_ate"] = 0.0
        return "Voltei a ficar de olho — te aviso se você começar a enrolar."
    with _lock:
        hoje = _estado["distracao_s_hoje"]
        aberturas = list(_estado["aberturas"])
        ativ = _estado["ultima_ativ"]
    c = _c()
    distracoes = lista_distracoes(c.get("distracoes"))
    janela_s = _int(c.get("janela_min"), 10) * 60
    from plugins._comum import duracao
    agora = time.time()
    if eh_distracao(ativ, distracoes):
        n = contar(aberturas, ativ, agora, janela_s)
        extra = f" É a {n}ª vez no {ativ} em {_int(c.get('janela_min'), 10)} min." if n >= 2 else f" (agora no {ativ})"
        return f"Hoje você já passou {duracao(hoje)} em distrações.{extra} Quer que eu te ajude a focar?"
    return (f"Agora você não está enrolando (nada de distração na frente). Hoje deu {duracao(hoje)} em distrações no "
            "total. Diga 'foca' se quiser que eu fique quieto por um tempo.")
