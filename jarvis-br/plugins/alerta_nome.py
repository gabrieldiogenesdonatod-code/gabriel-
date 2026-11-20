"""
Alerta de nome em reunião (fork PT-BR 2.16, ideia 11).

    "Jarvis, me avisa se falarem meu nome na reunião"
    "Jarvis, também me avisa se falarem 'orçamento' ou 'Cristal'"
    "Jarvis, para de escutar a reunião"

Escuta o ÁUDIO DO PC (o que as outras pessoas falam na call: Meet, Zoom, Teams,
Discord, WhatsApp) com a mesma captura da legenda ao vivo, sem mostrar legenda.
Se alguém disser o seu nome (ou outra palavra que você pediu) ENQUANTO a janela
da reunião não está na frente — você está distraído em outra coisa —, ele
avisa com um bipe/aviso curto e mostra a última frase dita, para você saber o
que te perguntaram.

Não grava nada em disco e não manda nada para ninguém: o texto fica só na
memória, só os últimos 30 segundos. Funciona melhor com o faster-whisper
(offline); sem ele, usa a IA (Gemini) para ouvir.
"""

from __future__ import annotations

import time
import unicodedata
from collections import deque

from plugins._comum import mostrar, nome_usuario

PLUGIN = {
    "name": "alerta_nome",
    "brief": "During a call, warn when someone says the user's name (or chosen words) while he is distracted.",
    "description": (
        "Name alert in meetings. action='ligar' (optional palavras = extra words, comma separated) listens to the "
        "PC audio and warns with the last sentence when someone says the user's name while the call window is not in "
        "front. action='desligar'; action='status'; action='ultimo' shows the last sentences heard."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "ligar | desligar | status | ultimo"},
                       "palavras": {"type": "STRING"}},
        "required": [],
    },
}

APPS_CHAMADA = ("zoom", "teams", "meet.google", "google meet", "discord", "whatsapp", "skype", "webex", "slack",
                "jitsi", "reuniao", "meeting", "chamada")
_estado = {"ligado": False, "palavras": [], "avisos": 0, "ultimo_aviso": 0.0}
_ouvido: deque = deque(maxlen=8)          # (hora, texto) dos últimos ~40 s


def _n(t: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().split())


def citou(texto: str, palavras: list[str]) -> str | None:
    """A palavra (nome) dita no texto, como palavra inteira; senão None (pura)."""
    t = f" {_n(texto)} "
    for p in palavras:
        alvo = _n(p)
        if alvo and any(f"{sep1}{alvo}{sep2}" in t for sep1 in (" ", ",") for sep2 in (" ", ",", "?", "!", ".")):
            return p
    return None


def janela_da_chamada_na_frente() -> bool:
    try:
        from plugins import olha_isso
        j = olha_isso.janela_alvo() or {}
        alvo = _n(f"{j.get('titulo', '')} {j.get('processo', '')}")
        return any(a in alvo for a in APPS_CHAMADA)
    except Exception:
        return False


def ouvir(texto: str, player=None) -> None:
    if not _estado["ligado"]:
        return
    _ouvido.append((time.time(), texto))
    quem = citou(texto, _estado["palavras"])
    if not quem or time.time() - _estado["ultimo_aviso"] < 20:
        return
    if janela_da_chamada_na_frente():
        return                                        # você já está olhando a reunião
    _estado["ultimo_aviso"] = time.time()
    _estado["avisos"] += 1
    contexto = " ".join(t for _h, t in list(_ouvido)[-2:])
    mostrar(player, f"FALARAM '{quem.upper()}' NA REUNIÃO", contexto)
    try:
        from plugins import _rosto_ui
        _rosto_ui.frase(player, "Reunião", f"Falaram '{quem}': {texto[-140:]}", mostrar_rosto=True)
    except Exception:
        pass
    try:
        from core import emocoes
        emocoes.definir("surpresa", 3)
    except Exception:
        pass
    try:
        import winsound
        winsound.MessageBeep(0x30)
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    from plugins import legenda_ao_vivo as L
    p = parameters or {}
    a = str(p.get("action") or "ligar").lower()
    try:
        if a == "ligar":
            nome = (nome_usuario() or "").split()
            palavras = [x.strip() for x in str(p.get("palavras") or "").split(",") if x.strip()]
            _estado["palavras"] = list(dict.fromkeys(([nome[0]] if nome else []) + palavras))
            if not _estado["palavras"]:
                return "Qual nome devo escutar? Diga 'me avisa se falarem Gabriel'."
            if ouvir not in L.ouvintes:
                L.ouvintes.append(ouvir)
            _estado["ligado"] = True
            r = L.ligar(player, "português do Brasil", silencioso=not L._estado["ligado"])
            if not L._estado["ligado"]:
                _estado["ligado"] = False
                return r
            return (f"Escutando a reunião. Aviso se falarem {', '.join(_estado['palavras'])} enquanto você estiver "
                    "em outra janela. Nada é gravado.")
        if a == "desligar":
            _estado["ligado"] = False
            if ouvir in L.ouvintes:
                L.ouvintes.remove(ouvir)
            if L._estado.get("silencioso"):
                L.desligar()
            _ouvido.clear()
            return f"Parei de escutar ({_estado['avisos']} aviso(s))."
        if a == "ultimo":
            if not _ouvido:
                return "Não ouvi nada ainda."
            return "Últimas falas: " + " … ".join(t for _h, t in list(_ouvido)[-3:])
        if _estado["ligado"]:
            return f"Escutando por: {', '.join(_estado['palavras'])}. {_estado['avisos']} aviso(s) até agora."
        return "O alerta de nome está desligado."
    except Exception as e:
        return f"O alerta de nome falhou: {e}"
