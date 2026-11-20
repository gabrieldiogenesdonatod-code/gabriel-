"""
Organizador de abas (fork PT-BR 2.11).

Guarda conjuntos de links por assunto (sessões) e reabre tudo de uma vez.

    "Jarvis, salva na sessão trabalho: github.com, gmail.com e o painel da Hostinger."
    "Jarvis, abre a sessão trabalho."          (abre todos os links de uma vez)
    "Jarvis, quais sessões eu tenho?"          "Jarvis, apaga a sessão trabalho"
    "Jarvis, salva as abas abertas como estudo."   (tenta pegar as janelas do navegador)

Cada sessão é um grupo de links com um assunto. Os links que você dita entram na
hora; "salva as abas abertas" é melhor-esforço: lê os TÍTULOS das janelas de
navegador abertas (a aba da frente de cada janela), porque o navegador não deixa
um programa de fora ler todas as abas. Tudo em memory/sessoes_abas.json.
"""

from __future__ import annotations

import re
import threading
import unicodedata
import webbrowser

from plugins._comum import MEMORIA, abrir_no_sistema, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "organizador_abas",
    "brief": "Tab sessions: save named groups of links by topic and reopen them all at once.",
    "description": (
        "Saves named groups of browser links (sessions) by topic and reopens them together. action: 'salvar' "
        "(nome = session name; links = URLs/sites, comma or space separated) adds links to a session; 'abrir' "
        "(nome) opens all links of a session; 'capturar' (nome) best-effort saves the currently open browser "
        "windows' front tabs into a session; 'listar' (optional nome to see its links); 'remover' (nome). Use for "
        "'salva na sessão X: ...', 'abre a sessão X', 'salva as abas abertas como X', 'quais sessões eu tenho'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "salvar | abrir | capturar | listar | remover"},
            "nome": {"type": "STRING", "description": "the session name/topic"},
            "links": {"type": "STRING", "description": "URLs/sites, comma or space separated (for 'salvar')"},
        },
    },
}

ARQ = MEMORIA / "sessoes_abas.json"      # o carregador dos testes troca este caminho
_lock = threading.RLock()
MAX_ABRIR = 20
SITES_CONHECIDOS = {
    "gmail": "https://mail.google.com", "youtube": "https://youtube.com", "github": "https://github.com",
    "chatgpt": "https://chat.openai.com", "claude": "https://claude.ai", "gemini": "https://gemini.google.com",
    "whatsapp": "https://web.whatsapp.com", "instagram": "https://instagram.com", "drive": "https://drive.google.com",
    "docs": "https://docs.google.com", "hostinger": "https://hpanel.hostinger.com", "canva": "https://canva.com",
    "netflix": "https://netflix.com", "spotify": "https://open.spotify.com",
}


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── links (puro) ───────────────────────────────────────────────────────────────
def normalizar_url(bruto: str) -> str:
    """'github.com', 'o github', 'https://x.com' → uma URL utilizável. '' se não parecer link (puro)."""
    t = str(bruto or "").strip().strip(".,;")
    if not t:
        return ""
    if re.match(r"(?i)^https?://", t):
        return t
    baixo = dobrar(t)
    for chave, url in SITES_CONHECIDOS.items():
        if baixo == chave or baixo == f"o {chave}" or baixo == f"a {chave}":
            return url
    if re.search(r"[a-z0-9-]+\.[a-z]{2,}(/|$)", baixo):      # tem cara de domínio
        return "https://" + t.lstrip("/")
    return ""


def separar_links(texto: str) -> list[str]:
    """Texto ditado → lista de URLs (puro). Separa por vírgula, 'e', ponto-e-vírgula ou espaço."""
    bruto = re.split(r"\s*(?:,|;|\be\b|\n)\s*|\s+(?=https?://)", str(texto or "").strip())
    saida, vistos = [], set()
    for pedaco in bruto:
        for parte in (pedaco.split() if " " in pedaco and "." in pedaco else [pedaco]):
            url = normalizar_url(parte)
            if url and url.lower() not in vistos:
                vistos.add(url.lower())
                saida.append(url)
    return saida


def url_do_titulo(titulo: str) -> str:
    """Título de janela de navegador → melhor palpite de URL (puro). '' se não der."""
    t = dobrar(titulo)
    for chave, url in SITES_CONHECIDOS.items():
        if chave in t:
            return url
    m = re.search(r"([a-z0-9-]+\.(?:com|net|org|br|io|dev|gov|edu)(?:\.[a-z]{2})?)", t)
    return "https://" + m.group(1) if m else ""


# ── dados ──────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("sessoes", {})          # {nome: {"links": [...], "criada": ts}}
    return d


def _gravar(d: dict) -> None:
    with _lock:
        gravar_json(ARQ, d)


def _achar(d: dict, nome: str) -> str:
    """Nome da sessão que combina (exato ou aproximado) (puro-ish)."""
    alvo = dobrar(nome).strip()
    if not alvo:
        return ""
    if alvo in {dobrar(k) for k in d["sessoes"]}:
        return next(k for k in d["sessoes"] if dobrar(k) == alvo)
    for k in d["sessoes"]:
        if alvo in dobrar(k) or dobrar(k) in alvo:
            return k
    return ""


# ── captura das janelas de navegador ─────────────────────────────────────────
NAVEGADORES = ("chrome", "msedge", "firefox", "opera", "brave", "edge")


def _abas_abertas() -> list[str]:
    try:
        from plugins import _janelas
        janelas = _janelas.listar() or []
    except Exception:
        return []
    urls, vistos = [], set()
    for j in janelas:
        proc = dobrar(j.get("processo", ""))
        if not any(n in proc for n in NAVEGADORES):
            continue
        url = url_do_titulo(j.get("titulo", ""))
        if url and url.lower() not in vistos:
            vistos.add(url.lower())
            urls.append(url)
    return urls


# ── ações ──────────────────────────────────────────────────────────────────────
def salvar(nome: str, links_txt: str) -> str:
    nome = " ".join(str(nome or "").split()).strip() or "sem nome"
    links = separar_links(links_txt)
    if not links:
        return "Quais links? Diga, por exemplo, 'salva na sessão trabalho: github.com e gmail'."
    with _lock:
        d = dados()
        chave = _achar(d, nome) or nome
        sessao = d["sessoes"].setdefault(chave, {"links": [], "criada": _agora()})
        novos = [u for u in links if u.lower() not in {x.lower() for x in sessao["links"]}]
        sessao["links"].extend(novos)
        _gravar(d)
        total = len(sessao["links"])
    registrar(None, f"🗂️ Sessão de abas “{chave}”: +{len(novos)} link(s)")
    return (f"Salvei {len(novos)} link(s) na sessão “{chave}” (agora tem {total}). "
            f"Diga 'abre a sessão {chave}' quando quiser abrir tudo.")


def abrir(nome: str) -> str:
    with _lock:
        d = dados()
        chave = _achar(d, nome)
        if not chave:
            return (f"Não achei a sessão “{nome}”." if nome else "Qual sessão?") + " Diga 'quais sessões eu tenho'."
        links = list(d["sessoes"][chave]["links"])
    if not links:
        return f"A sessão “{chave}” está vazia."
    abertos = 0
    for url in links[:MAX_ABRIR]:
        try:
            if not webbrowser.open(url):
                abrir_no_sistema(url)
            abertos += 1
        except Exception:
            abrir_no_sistema(url)
    extra = f" (abri os {MAX_ABRIR} primeiros de {len(links)})" if len(links) > MAX_ABRIR else ""
    return f"Abrindo a sessão “{chave}”: {abertos} aba(s){extra}."


def capturar(nome: str) -> str:
    nome = " ".join(str(nome or "").split()).strip() or "abas de " + _hoje()
    urls = _abas_abertas()
    if not urls:
        return ("Não consegui identificar as abas abertas (o navegador não deixa ler todas, e os títulos não "
                "tinham site reconhecível). Me dite os links que eu salvo: 'salva na sessão " + nome + ": ...'.")
    with _lock:
        d = dados()
        chave = _achar(d, nome) or nome
        sessao = d["sessoes"].setdefault(chave, {"links": [], "criada": _agora()})
        novos = [u for u in urls if u.lower() not in {x.lower() for x in sessao["links"]}]
        sessao["links"].extend(novos)
        _gravar(d)
    return (f"Peguei {len(novos)} aba(s) da frente das janelas de navegador e salvei em “{chave}”. "
            "(Só a aba da frente de cada janela — o navegador não deixa ler as de trás.)")


def listar(nome: str = "", player=None) -> str:
    with _lock:
        d = dados()
        if nome:
            chave = _achar(d, nome)
            if not chave:
                return f"Não achei a sessão “{nome}”."
            links = d["sessoes"][chave]["links"]
            mostrar(player, f"SESSÃO · {chave}", "\n".join(links) or "(vazia)")
            return f"A sessão “{chave}” tem {len(links)} link(s). Mostrei na tela; diga 'abre a sessão {chave}'."
        sessoes = d["sessoes"]
    if not sessoes:
        return "Você não tem sessões salvas. Diga 'salva na sessão trabalho: github.com e gmail'."
    linhas = [f"{nome}: {len(s['links'])} link(s)" for nome, s in sessoes.items()]
    mostrar(player, "SESSÕES DE ABAS", "\n".join(linhas))
    return f"Você tem {len(sessoes)} sessão(ões): {', '.join(sessoes)}. Resuma em 1 frase."


def remover(nome: str) -> str:
    with _lock:
        d = dados()
        chave = _achar(d, nome)
        if not chave:
            return f"Não achei a sessão “{nome}”."
        del d["sessoes"][chave]
        _gravar(d)
    return f"Apaguei a sessão “{chave}”."


def _agora() -> float:
    import time
    return time.time()


def _hoje() -> str:
    from datetime import datetime
    return datetime.now().strftime("%d/%m")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "listar").strip()
    nome = str(p.get("nome") or "")
    try:
        if acao in ("salvar", "salva", "adicionar", "guardar"):
            return salvar(nome, str(p.get("links") or p.get("texto") or ""))
        if acao in ("abrir", "abre", "restaurar"):
            return abrir(nome)
        if acao in ("capturar", "pegar_abas", "salvar_abertas", "capturar_abas"):
            return capturar(nome)
        if acao in ("listar", "lista", "quais", "ver"):
            return listar(nome, player)
        if acao in ("remover", "apagar", "excluir"):
            return remover(nome)
        return listar(nome, player)
    except Exception as e:
        return f"O organizador de abas falhou: {e}"
