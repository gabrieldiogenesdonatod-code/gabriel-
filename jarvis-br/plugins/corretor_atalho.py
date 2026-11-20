"""
Corretor por atalho (fork PT-BR 2.16, ideia 14).

Selecione um texto em QUALQUER programa (WhatsApp Web, Word, e-mail, Discord…)
e aperte:

    Ctrl+Alt+C   corrige ortografia e gramática (mantém o seu jeito de escrever)
    Ctrl+Alt+F   deixa mais formal (para cliente, chefe, e-mail)
    Ctrl+Alt+R   deixa mais curto e direto
    Ctrl+Alt+A   deixa mais amigável/simpático

O texto é trocado no lugar. Errou? Ctrl+Z no próprio programa volta o original.
Também por voz: "Jarvis, corrige o texto selecionado", "deixa mais formal".

Como funciona: copia a seleção (Ctrl+C), manda o texto para a IA com a
instrução, cola o resultado (Ctrl+V) e devolve o que estava na sua área de
transferência antes. Os atalhos podem ser trocados em ⚙ → Corretor por atalho.
Precisa da chave do Gemini. Só o texto selecionado sai do PC.
"""

from __future__ import annotations

import threading
import time

from plugins._comum import cfg, registrar

PLUGIN = {
    "name": "corretor_atalho",
    "brief": "Fix or rewrite the text selected in any app (correct, formal, shorter, friendlier) via hotkeys or voice.",
    "description": (
        "Selected-text rewriter. action='aplicar' with modo = corrigir | formal | curto | amigavel (optional instrucao = "
        "custom instruction like 'em inglês') rewrites the text currently SELECTED in the focused app and pastes it "
        "back. Hotkeys Ctrl+Alt+C/F/R/A do the same without talking. action='atalhos' lists them."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "aplicar | atalhos"},
                       "modo": {"type": "STRING"}, "instrucao": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "corretor_atalho",
    "title": "Corretor por atalho",
    "fields": [
        {"key": "corrigir", "label": "Atalho: corrigir", "type": "text", "default": "ctrl+alt+c"},
        {"key": "formal", "label": "Atalho: mais formal", "type": "text", "default": "ctrl+alt+f"},
        {"key": "curto", "label": "Atalho: mais curto", "type": "text", "default": "ctrl+alt+r"},
        {"key": "amigavel", "label": "Atalho: mais amigável", "type": "text", "default": "ctrl+alt+a"},
    ],
}

INSTRUCOES = {
    "corrigir": "Corrija ortografia, acentuação, pontuação e concordância. Mantenha o MESMO tom, gírias e jeito de "
                "escrever; não reescreva o que já está certo.",
    "formal": "Reescreva de forma educada e profissional, clara, sem ser rebuscada.",
    "curto": "Reescreva mais curto e direto, mantendo todas as informações importantes.",
    "amigavel": "Reescreva de um jeito mais simpático e acolhedor, natural, sem exagero.",
}
_ocupado = threading.Lock()


def prompt(modo: str, texto: str, instrucao: str = "") -> str:
    regra = instrucao or INSTRUCOES.get(modo, INSTRUCOES["corrigir"])
    return (f"{regra} Escreva no mesmo idioma do texto (português do Brasil, se for português), a menos que a "
            f"instrução peça outro. Mantenha quebras de linha, emojis, nomes e números. Responda SÓ com o texto final, "
            f"sem aspas e sem comentários.\n\nTEXTO:\n{texto}")


def limpar_resposta(r: str, original: str) -> str:
    """Tira aspas/cercas que a IA às vezes põe em volta (pura)."""
    t = (r or "").strip()
    if t.startswith("```") and t.endswith("```"):
        t = t.strip("`").split("\n", 1)[-1].strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'“”" and not (original.startswith(t[0])):
        t = t[1:-1].strip()
    for prefixo in ("TEXTO:", "Texto corrigido:", "Texto final:"):
        if t.startswith(prefixo):
            t = t[len(prefixo):].strip()
    return t


def aplicar(modo: str = "corrigir", instrucao: str = "", player=None) -> str:
    if not _ocupado.acquire(blocking=False):
        return "Ainda estou terminando o anterior."
    try:
        import pyautogui
        import pyperclip
        from plugins import _ia
        if not _ia.disponivel():
            return "Preciso da chave do Gemini para reescrever."
        antes = pyperclip.paste()
        marca = f"__jarvis_{time.time()}__"
        pyperclip.copy(marca)
        time.sleep(0.15)                                  # solta as teclas do atalho
        pyautogui.keyUp("alt")
        pyautogui.keyUp("ctrl")
        pyautogui.hotkey("ctrl", "c")
        texto = ""
        for _ in range(20):
            time.sleep(0.05)
            texto = pyperclip.paste()
            if texto != marca:
                break
        if not texto or texto == marca:
            pyperclip.copy(antes)
            return "Não tem texto selecionado."
        if len(texto) > 8000:
            pyperclip.copy(antes)
            return "O texto selecionado é grande demais (máximo 8 mil letras)."
        novo = limpar_resposta(_ia.perguntar(prompt(modo, texto, instrucao), False, 40) or "", texto)
        if not novo:
            pyperclip.copy(antes)
            return "A IA não respondeu; não mexi no texto."
        if texto.endswith("\n") and not novo.endswith("\n"):
            novo += "\n"
        pyperclip.copy(novo)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        pyperclip.copy(antes)
        registrar(player, f"Corretor ({modo}): {len(texto)} → {len(novo)} letras.")
        return "Pronto, troquei o texto. Ctrl+Z no programa volta o original." if novo != texto else \
            "O texto já estava certo; não mudei nada."
    except Exception as e:
        return f"O corretor falhou: {e}"
    finally:
        _ocupado.release()


def on_session_start(player) -> None:
    from plugins import _atalhos_globais
    c = cfg("corretor_atalho", PLUGIN_SETTINGS)
    for modo in INSTRUCOES:
        combo = str(c.get(modo) or PLUGIN_SETTINGS["fields"][list(INSTRUCOES).index(modo)]["default"])
        if not _atalhos_globais.registrar(combo, lambda m=modo: aplicar(m, "", player)) and _atalhos_globais.WIN:
            registrar(player, f"Corretor: o atalho {combo} já está em uso; troque em ⚙ → Corretor por atalho.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    if str(p.get("action") or "aplicar").lower() == "atalhos":
        c = cfg("corretor_atalho", PLUGIN_SETTINGS)
        return "Selecione o texto e aperte: " + ", ".join(f"{c.get(m)} para {m}" for m in INSTRUCOES) + "."
    modo = str(p.get("modo") or "corrigir").lower().replace("á", "a")
    if modo not in INSTRUCOES:
        modo = "corrigir"
    time.sleep(0.4)                                       # dá tempo de a janela do app voltar ao foco
    return aplicar(modo, str(p.get("instrucao") or ""), player)
