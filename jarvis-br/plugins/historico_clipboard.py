"""
Histórico da área de transferência — plugin do J.A.R.V.I.S BR.

Guarda os últimos 50 textos que você copiou (os fixados não contam no limite).

    "Jarvis, o que eu copiei?"                 → lista
    "Jarvis, cola de novo o endereço"          → acha pelo texto e cola
    "Jarvis, copia o terceiro de novo"         → só copia, sem colar
    "Jarvis, fixa esse" / "apaga o segundo"    → fixar / apagar
    "Jarvis, pausa o histórico"                → para de guardar até retomar

PRIVACIDADE
    * NÃO guarda o que parece senha (uma palavra só, 8–64 caracteres, misturando
      maiúsculas, minúsculas, números e símbolos) nem chaves de API (sk-…,
      AIza…, ghp_…, tokens longos);
    * no Windows, respeita o aviso que gerenciadores de senha (KeePass,
      Bitwarden, 1Password…) mandam junto com o que copiam;
    * fica só em memory/clipboard_historico.json, que está no .gitignore.
"""

from __future__ import annotations

import re
import threading
import time

from plugins._comum import (MEMORIA, WIN, cfg, confirmar, gravar_json, ler_json,
                            mostrar, num, plugin_ligado, salvar_cfg, sim)

PLUGIN = {
    "name": "historico_clipboard",
    "brief": "Clipboard history: list, search, paste again, copy, pin, delete, pause.",
    "description": (
        "Clipboard history (last 50 copied texts). action='listar'; 'buscar' (termo); "
        "'colar' (termo or indice; pastes into the active window); 'copiar' (termo or "
        "indice; only puts it back on the clipboard); 'fixar' / 'desafixar' (indice); "
        "'apagar' (indice, or termo='tudo'); 'pausar' / 'retomar' capturing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "termo": {"type": "STRING"}, "indice": {"type": "NUMBER", "description": "1 = most recent"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "historico_clipboard",
    "title": "Histórico da área de transferência",
    "fields": [
        {"key": "capturar", "label": "Guardar o que eu copio", "type": "toggle", "default": True},
        {"key": "limite", "label": "Quantos itens guardar", "type": "text", "default": "50"},
    ],
}

ARQUIVO = MEMORIA / "clipboard_historico.json"
_lock = threading.Lock()
_thread: threading.Thread | None = None
_parar = threading.Event()

_SEGREDOS = re.compile(
    r"^(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}"
    r"|gho_[A-Za-z0-9]{30,}|xox[abpr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\..+)$")


def parece_senha(texto: str) -> bool:
    t = (texto or "").strip()
    if not t or len(t) > 200:
        return False
    if _SEGREDOS.match(t):
        return True
    if any(ch.isspace() for ch in t) or not 8 <= len(t) <= 64:
        return False
    if re.match(r"^(https?://|www\.|[\w.+-]+@[\w-]+\.[\w.]+$|[A-Za-z]:\\|/)", t):
        return False
    classes = sum(bool(re.search(p, t)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w]"))
    if classes >= 3:
        return True
    # Token longo e aleatório (32+ letras/números misturados), mesmo sem símbolos.
    return len(t) >= 32 and classes >= 2 and not re.fullmatch(r"[0-9a-f]+", t)


def _gerenciador_de_senha_avisou() -> bool:
    """Windows: o formato que KeePass, Bitwarden etc. põem junto do que copiam."""
    if not WIN:
        return False
    try:
        import ctypes
        u32 = ctypes.windll.user32
        for nome in ("ExcludeClipboardContentFromMonitorProcessing", "Clipboard Viewer Ignore"):
            fmt = u32.RegisterClipboardFormatW(nome)
            if fmt and u32.IsClipboardFormatAvailable(fmt):
                return True
    except Exception:
        pass
    return False


def _ler_clipboard() -> str | None:
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        return None


def carregar() -> list[dict]:
    d = ler_json(ARQUIVO, [])
    return d if isinstance(d, list) else []


def adicionar(texto: str, limite: int = 50) -> bool:
    texto = texto or ""
    if not texto.strip() or len(texto) > 20000 or parece_senha(texto):
        return False
    with _lock:
        itens = carregar()
        fixado = any(i["texto"] == texto and i.get("fixado") for i in itens)
        itens = [i for i in itens if i["texto"] != texto]
        itens.insert(0, {"texto": texto, "ts": time.time(), "fixado": fixado})
        soltos = [i for i in itens if not i.get("fixado")]
        sobra = {id(i) for i in soltos[limite:]}
        itens = [i for i in itens if id(i) not in sobra]
        gravar_json(ARQUIVO, itens)
    return True


def _laco():
    ultimo = _ler_clipboard()
    while not _parar.wait(1.5):
        if not plugin_ligado("historico_clipboard"):
            continue
        c = cfg("historico_clipboard", PLUGIN_SETTINGS)
        if not sim(c.get("capturar", True)):
            continue
        atual = _ler_clipboard()
        if atual is None or atual == ultimo:
            continue
        ultimo = atual
        if _gerenciador_de_senha_avisou():
            continue
        adicionar(atual, int(num(c.get("limite"), 50)) or 50)


def on_session_start(player) -> None:
    global _thread
    if _ler_clipboard() is None:
        print("[Clipboard] pyperclip não instalado — histórico desligado (pip install pyperclip)")
        return
    if _thread and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_laco, daemon=True, name="historico-clipboard")
    _thread.start()


def _escolher(itens: list[dict], p: dict) -> tuple[int, dict] | tuple[None, None]:
    if p.get("indice") not in (None, ""):
        i = int(num(p.get("indice"), 1)) - 1
        return (i, itens[i]) if 0 <= i < len(itens) else (None, None)
    termo = str(p.get("termo") or "").lower().strip()
    if termo:
        for i, it in enumerate(itens):
            if termo in it["texto"].lower():
                return i, it
    return (0, itens[0]) if itens and not termo else (None, None)


def _resumo(t: str, n: int = 70) -> str:
    t = " ".join(t.split())
    return t if len(t) <= n else t[: n - 1] + "…"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").strip().lower()
    try:
        if a == "pausar":
            salvar_cfg("historico_clipboard", {"capturar": False})
            return "Parei de guardar o que você copia."
        if a == "retomar":
            salvar_cfg("historico_clipboard", {"capturar": True})
            on_session_start(player)
            return "Voltei a guardar o que você copia."
        itens = carregar()
        if not itens:
            return "O histórico da área de transferência está vazio."
        if a in ("listar", "buscar"):
            termo = str(p.get("termo") or "").lower()
            lista = [(i, it) for i, it in enumerate(itens) if not termo or termo in it["texto"].lower()]
            if not lista:
                return f"Nada no histórico com {termo}."
            mostrar(player, "ÁREA DE TRANSFERÊNCIA — HISTÓRICO", "\n".join(
                f"{i + 1:>2}. {'📌 ' if it.get('fixado') else ''}{time.strftime('%d/%m %H:%M', time.localtime(it['ts']))}"
                f"  {_resumo(it['texto'], 90)}" for i, it in lista[:30]))
            return f"{len(lista)} item(ns); o mais recente: {_resumo(lista[0][1]['texto'], 80)}"
        i, it = _escolher(itens, p)
        if it is None:
            return "Não achei esse item no histórico."
        if a in ("colar", "copiar"):
            import pyperclip
            pyperclip.copy(it["texto"])
            if a == "colar":
                try:
                    import pyautogui
                    time.sleep(0.15)
                    pyautogui.hotkey("ctrl", "v")
                except Exception:
                    return f"Copiei {_resumo(it['texto'], 50)}; cole com Ctrl+V."
                return f"Colei: {_resumo(it['texto'], 60)}"
            return f"Copiado de novo: {_resumo(it['texto'], 60)}"
        if a in ("fixar", "desafixar"):
            with _lock:
                itens = carregar()
                itens[i]["fixado"] = a == "fixar"
                gravar_json(ARQUIVO, itens)
            return f"Item {i + 1} {'fixado' if a == 'fixar' else 'solto'}."
        if a == "apagar":
            if str(p.get("termo") or "").lower() in ("tudo", "todos", "todo"):
                return confirmar("clipboard-tudo", "Apagar todo o histórico da área de transferência",
                                 f"{len(itens)} itens, inclusive os fixados.",
                                 lambda: (gravar_json(ARQUIVO, []), "Histórico apagado.")[1])
            with _lock:
                itens = carregar()
                itens.pop(i)
                gravar_json(ARQUIVO, itens)
            return f"Item {i + 1} apagado do histórico."
        return "Ação desconhecida para o histórico."
    except Exception as e:
        return f"O histórico da área de transferência falhou: {e}"
