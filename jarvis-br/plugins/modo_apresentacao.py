"""
Modo apresentação (fork PT-BR 2.11).

Pra quando você vai apresentar slides. O JARVIS entra em "não perturbe" (nada de
avisos no meio da fala), impede a tela de apagar e passa os slides por voz.

    "Jarvis, modo apresentação."     → silêncio + tela sempre acesa + comando de slides
    "próximo slide" / "volta um slide" / "começar apresentação" / "tela preta"
    "Jarvis, sair da apresentação."

Os comandos de slide mandam as teclas que o PowerPoint, o Google Slides e o PDF
entendem (seta direita/esquerda, F5, Esc, B). Não perturbe vale pelo estado do
mundo (core/estado_mundo.py), igual ao modo cinema.
"""

from __future__ import annotations

import threading
import time
import unicodedata

from plugins._comum import MEMORIA, WIN, gravar_json, ler_json, registrar

PLUGIN = {
    "name": "modo_apresentacao",
    "brief": "Presentation mode: Do-Not-Disturb, keeps screen awake, advances slides by voice.",
    "description": (
        "Presentation mode for giving a slideshow. action: 'ligar' (Do-Not-Disturb + keep the screen awake + enable "
        "voice slide control), 'desligar', 'proximo'/'anterior' (next/previous slide), 'inicio' (start from first, "
        "F5), 'fim' (end the show, Esc), 'preto' (black screen, B), 'status'. Use for 'modo apresentação', 'próximo "
        "slide', 'volta um slide', 'começar apresentação', 'tela preta', 'sair da apresentação'. The slide commands "
        "send the keys PowerPoint/Google Slides/PDF understand."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "ligar | desligar | proximo | anterior | inicio | fim | preto | status"},
        },
        "required": ["action"],
    },
}

ARQ = MEMORIA / "apresentacao.json"      # o carregador dos testes troca este caminho; guarda só {ativa, inicio}
_lock = threading.RLock()
_keep_awake = {"on": False}

TECLAS = {"proximo": "right", "anterior": "left", "inicio": "f5", "fim": "esc", "preto": "b"}
FALA = {"proximo": "Próximo.", "anterior": "Voltei um.", "inicio": "Começando a apresentação.",
        "fim": "Encerrando a apresentação.", "preto": "Tela preta."}


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def normalizar_acao(acao: str) -> str:
    """Fala solta → ação (puro). 'passa o slide' → proximo, 'volta' → anterior…"""
    t = dobrar(acao).strip()
    if any(w in t for w in ("sair", "desligar", "encerrar modo", "fim do modo", "parar apresenta")):
        return "desligar"
    if "apresenta" in t and any(w in t for w in ("modo", "ligar", "entrar", "iniciar modo")):
        return "ligar"
    if any(w in t for w in ("proximo", "avanca", "passa", "proxima", "next", "adiante", "segue")):
        return "proximo"
    if any(w in t for w in ("anterior", "volta", "atras", "previous", "voltar")):
        return "anterior"
    if any(w in t for w in ("comeca", "iniciar apresenta", "do inicio", "start", "primeiro slide", "f5")):
        return "inicio"
    if any(w in t for w in ("tela preta", "preto", "escurece", "apaga a tela", "black")):
        return "preto"
    if any(w in t for w in ("termina", "acaba", "esc", "sai do slide")):
        return "fim"
    if "status" in t or "apresenta" in t:
        return "status"
    return t


def ativa() -> bool:
    return bool((ler_json(ARQ, {}) or {}).get("ativa"))


def _set_ativa(valor: bool) -> None:
    gravar_json(ARQ, {"ativa": bool(valor), "inicio": time.time() if valor else 0})


# ── tela sempre acesa ────────────────────────────────────────────────────────
def manter_tela_acesa(on: bool) -> bool:
    """Impede o Windows de apagar a tela/dormir durante a apresentação."""
    if not WIN:
        _keep_awake["on"] = on
        return False
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_DISPLAY_REQUIRED = 0x00000002
        ES_SYSTEM_REQUIRED = 0x00000001
        flags = (ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED) if on else ES_CONTINUOUS
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
        _keep_awake["on"] = on
        return True
    except Exception as e:
        print(f"[Apresentação] manter a tela acesa: {e}")
        return False


def _tecla(nome: str) -> bool:
    try:
        import pyautogui
        pyautogui.press(nome)
        return True
    except Exception as e:
        print(f"[Apresentação] tecla {nome}: {e}")
        return False


# ── ações ──────────────────────────────────────────────────────────────────────
def ligar() -> str:
    with _lock:
        _set_ativa(True)
    manter_tela_acesa(True)
    registrar(None, "🎤 Modo apresentação ligado.")
    aviso = "" if WIN else " (a tela sempre acesa só funciona no Windows)"
    return ("Modo apresentação ligado: não perturbe, tela sempre acesa e comando de slides por voz." + aviso +
            " Diga 'próximo', 'volta um slide', 'começar' ou 'tela preta'. Para sair, 'sair da apresentação'. "
            "Responda numa frase curta.")


def desligar() -> str:
    with _lock:
        _set_ativa(False)
    manter_tela_acesa(False)
    registrar(None, "🎤 Modo apresentação desligado.")
    return "Modo apresentação desligado. Mandou bem na apresentação, senhor!"


def comando(acao: str) -> str:
    if not ativa():
        return "O modo apresentação não está ligado. Diga 'modo apresentação' primeiro."
    tecla = TECLAS.get(acao)
    if not tecla:
        return "Não entendi o comando do slide."
    ok = _tecla(tecla)
    if acao == "fim":
        pass
    return (FALA.get(acao, "Ok.") if ok else "Não consegui mandar a tecla (o pyautogui pode não estar instalado).")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = normalizar_acao(p.get("action") or "status")
    try:
        if acao in ("ligar", "apresentacao", "modo_apresentacao"):
            return ligar()
        if acao in ("desligar", "sair"):
            return desligar()
        if acao in TECLAS:
            return comando(acao)
        if acao == "status":
            return ("Modo apresentação está LIGADO." if ativa() else
                    "Modo apresentação desligado. Diga 'modo apresentação' pra ligar.")
        return comando(acao) if ativa() else ligar() if "apresenta" in dobrar(p.get("action") or "") else (
            "Diga 'modo apresentação' pra ligar, ou 'próximo'/'volta' durante a apresentação.")
    except Exception as e:
        return f"O modo apresentação falhou: {e}"
