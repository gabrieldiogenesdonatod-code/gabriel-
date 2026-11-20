"""
Fila de leitura (fork PT-BR 2.16, ideia 13).

    "Jarvis, salva esse link para ler depois"        (o link copiado, ou o da aba do navegador)
    "Jarvis, salva https://… para depois"
    Mandar um link pelo seu WhatsApp do JARVIS com "depois" na mensagem
    "Jarvis, o que tem na minha fila?"
    "Jarvis, tô livre, lê minha fila"               → resume em voz alta, um por um
    "Jarvis, lê o artigo inteiro do segundo"         → lê o texto todo (sem resumir)
    "Jarvis, já li o primeiro" / "limpa a fila"

Ao salvar, ele já baixa o texto da página e faz o resumo (se tiver IA), então
na hora de ouvir é instantâneo — e funciona até sem internet. Fica em
memory/fila_leitura.json. Se você ficar 20 minutos ocioso no fim do dia com
itens na fila, ele pergunta uma vez se quer ouvir (pode desligar em ⚙).
"""

from __future__ import annotations

import re
import threading
import time

from plugins import _web
from plugins._comum import MEMORIA, cfg, falar, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "fila_leitura",
    "brief": "Read-later queue: save links, pre-summarize, read summaries or full articles aloud when free.",
    "description": (
        "Reading queue. action='salvar' with optional url (default: the copied link) saves it and prepares a summary. "
        "action='listar'. action='ler' (optional n = item number, optional completo=true for the full text) returns the "
        "summary/text for YOU TO READ ALOUD to the user, naturally, then ask if he wants the next one. "
        "action='lido' with n marks as read; action='limpar' clears read items (valor 'tudo' clears all)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "salvar | listar | ler | lido | limpar"},
                       "url": {"type": "STRING"}, "n": {"type": "INTEGER"}, "completo": {"type": "BOOLEAN"},
                       "valor": {"type": "STRING"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {"namespace": "fila_leitura", "title": "Fila de leitura",
                   "fields": [{"key": "oferecer", "label": "Oferecer a fila quando eu estiver livre à noite",
                               "type": "toggle", "default": True}]}

ARQ = MEMORIA / "fila_leitura.json"
_lock = threading.Lock()
_ofereceu = {"dia": ""}


def achar_url(texto: str) -> str:
    m = re.search(r"https?://[^\s<>\"']+", texto or "")
    return m.group(0).rstrip(").,;") if m else ""


def _clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


def _preparar(item: dict) -> None:
    try:
        texto, titulo = _web.get_texto(item["url"])
        item["titulo"] = (titulo or item["url"])[:140]
        item["texto"] = texto[:40_000]
        item["minutos"] = max(1, round(len(texto.split()) / 200))
        from plugins import _ia
        if _ia.disponivel() and texto:
            item["resumo"] = _ia.perguntar(
                "Resuma este artigo em português do Brasil para ser LIDO EM VOZ ALTA: 4 a 6 frases simples, sem "
                "listas nem símbolos, começando pelo ponto principal.\n\n" + texto[:15_000], False, 60) or ""
        if not item.get("resumo"):
            item["resumo"] = " ".join(texto.split(".")[:4]).strip()[:700]
    except Exception as e:
        item["erro"] = str(e)
    item["pronto"] = True
    with _lock:
        fila = ler_json(ARQ, []) or []
        for i, x in enumerate(fila):
            if x["url"] == item["url"]:
                fila[i] = item
        gravar_json(ARQ, fila)


def salvar(url: str) -> str:
    url = achar_url(url) or url.strip()
    if not url.startswith("http"):
        return "Não achei um link. Copie o link e me peça de novo."
    with _lock:
        fila = ler_json(ARQ, []) or []
        if any(x["url"] == url and not x.get("lido") for x in fila):
            return "Esse link já está na fila."
        item = {"url": url, "salvo": time.strftime("%Y-%m-%d %H:%M"), "titulo": url, "pronto": False, "lido": False}
        fila.append(item)
        gravar_json(ARQ, fila)
    threading.Thread(target=_preparar, args=(dict(item),), daemon=True).start()
    pendentes = sum(1 for x in fila if not x.get("lido"))
    return f"Salvo para depois. Você tem {pendentes} na fila."


def _pendentes() -> list[dict]:
    return [x for x in (ler_json(ARQ, []) or []) if not x.get("lido")]


def _laco(player) -> None:
    while True:
        time.sleep(300)
        try:
            if not cfg("fila_leitura", PLUGIN_SETTINGS).get("oferecer", True):
                continue
            hoje = time.strftime("%Y-%m-%d")
            h = time.localtime().tm_hour
            if _ofereceu["dia"] == hoje or not (19 <= h <= 22):
                continue
            pend = _pendentes()
            if not pend:
                continue
            from core import telemetria
            ocioso = (telemetria.get().snapshot().get("ocioso_s") or 0) if hasattr(telemetria, "get") else 0
            if ocioso and ocioso < 60:
                continue
            _ofereceu["dia"] = hoje
            falar(player, f"[FILA DE LEITURA] Em UMA frase, diga ao usuário que ele tem {len(pend)} leitura(s) "
                          "salvas e pergunte se quer que você resuma agora. Não chame ferramentas.")
        except Exception as e:
            print(f"[Fila] {e}")


def on_session_start(player) -> None:
    threading.Thread(target=_laco, args=(player,), daemon=True, name="fila_leitura").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    try:
        if a == "salvar":
            return salvar(str(p.get("url") or "") or _clipboard())
        pend = _pendentes()
        if a == "listar":
            if not pend:
                return "Sua fila de leitura está vazia."
            mostrar(player, "FILA DE LEITURA", "\n".join(
                f"{i}. {x['titulo']}  ({x.get('minutos', '?')} min)  {x['url']}" for i, x in enumerate(pend, 1)))
            return f"{len(pend)} na fila: " + "; ".join(f"{i}. {x['titulo'][:60]}" for i, x in enumerate(pend[:5], 1)) + "."
        if a in ("ler", "lido"):
            if not pend:
                return "A fila está vazia."
            n = int(p.get("n") or 1)
            if not 1 <= n <= len(pend):
                return f"A fila tem {len(pend)} itens."
            item = pend[n - 1]
            if a == "lido":
                with _lock:
                    fila = ler_json(ARQ, []) or []
                    for x in fila:
                        if x["url"] == item["url"]:
                            x["lido"] = True
                    gravar_json(ARQ, fila)
                return f"Marquei '{item['titulo'][:60]}' como lido."
            if not item.get("pronto"):
                return "Ainda estou baixando esse; me peça de novo em alguns segundos."
            if item.get("erro") and not item.get("texto"):
                return f"Não consegui abrir esse link ({item['erro']}). O endereço é {item['url']}."
            if p.get("completo"):
                return (f"[LEITURA] Leia em voz alta, naturalmente, o texto de '{item['titulo']}' (pode pular "
                        f"menus e propagandas): {item.get('texto', '')[:6000]}")
            return (f"[LEITURA] Item {n} de {len(pend)}: '{item['titulo']}' ({item.get('minutos', '?')} min de leitura). "
                    f"Leia este resumo em voz alta e depois pergunte se ele quer o próximo, o texto completo ou "
                    f"marcar como lido: {item.get('resumo', '')}")
        if a == "limpar":
            with _lock:
                fila = ler_json(ARQ, []) or []
                novos = [] if str(p.get("valor") or "").lower() in ("tudo", "todos") else [x for x in fila if not x.get("lido")]
                gravar_json(ARQ, novos)
            return f"Fila limpa; ficaram {len(novos)}."
        return "Use salvar, listar, ler, lido ou limpar."
    except Exception as e:
        return f"A fila de leitura falhou: {e}"
