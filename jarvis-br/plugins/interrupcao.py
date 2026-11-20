"""
Interromper o JARVIS (fork PT-BR 2.4.1) — veja core/interrupcao.py.

Jeitos de cortar a fala dele:
    falar por cima          (interrupção por voz)
    ESC / ✋ INTERROMPER     (com a janela do JARVIS na frente)
    Ctrl+Alt+P               (em qualquer janela, no Windows)
    a tecla do push-to-talk  (se estiver usando)

    "Jarvis, desliga a interrupção por voz"   (se ele estiver se cortando sozinho com o eco)
    "Jarvis, liga a interrupção por voz"
    "Jarvis, como eu te interrompo?"

Dica: com caixa de som alta e o microfone perto dela, a interrupção por voz
fica mais exigente (precisa de mais tempo de fala sua). Com fone, funciona
na hora.
"""

from __future__ import annotations

from core import interrupcao as I
from plugins._comum import salvar_cfg

PLUGIN = {
    "name": "interrupcao",
    "brief": "How the user interrupts JARVIS mid-speech (voice, ESC, Ctrl+Alt+P, push-to-talk key); turn voice "
             "interruption on/off.",
    "description": (
        "Interrupting JARVIS while it speaks. action='status' explains the ways to interrupt (talking over it, ESC "
        "or the INTERROMPER button, Ctrl+Alt+P in any window on Windows, the push-to-talk key) and whether voice "
        "interruption is on; 'voz' with valor ligar/desligar turns voice interruption on or off (turn it off if "
        "JARVIS keeps cutting itself off because of speaker echo)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "status | voz"},
                       "valor": {"type": "STRING", "description": "ligar | desligar"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "interrupcao",
    "title": "Interrupção",
    "fields": [
        {"key": "por_voz", "label": "Interromper o JARVIS falando por cima dele", "type": "toggle", "default": True},
        {"key": "atalho_global", "label": "Ctrl+Alt+P interrompe em qualquer janela (Windows; vale ao reabrir)",
         "type": "toggle", "default": True},
    ],
}


def _app():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.app()
    except Exception:
        return None


def _desligar(valor) -> bool:
    return str(valor or "").strip().lower() in ("desligar", "desliga", "off", "nao", "não", "false", "0")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        app = _app()
        if acao == "voz":
            ligar = not _desligar(p.get("valor"))
            salvar_cfg("interrupcao", {"por_voz": ligar})
            if app is not None:
                app._interromper_por_voz = ligar
            return ("Interrupção por voz ligada: é só falar por cima de mim." if ligar else
                    "Interrupção por voz desligada. Para me cortar: ESC, o botão INTERROMPER ou Ctrl+Alt+P.")
        voz = bool(getattr(app, "_interromper_por_voz", I.config("por_voz", True)))
        atalho = getattr(app, "_atalho_intr", None) is not None
        return ("Para me interromper: " + ("fale por cima de mim (ligado); " if voz else
                                          "falar por cima está DESLIGADO; ")
                + "ESC ou o botão INTERROMPER com a minha janela na frente"
                + ("; Ctrl+Alt+P em qualquer janela" if atalho else "")
                + "; ou aperte a tecla de falar, se usar push-to-talk.")
    except Exception as e:
        return f"A interrupção falhou: {e}"
