"""
Ditado inteligente (fork PT-BR 1.9): você fala, ele escreve formatado no app que estiver aberto.

    "Jarvis, escreve um e-mail educado recusando a proposta do fornecedor"
    "Jarvis, escreve uma função que valida CPF"        (no VS Code: no idioma do arquivo aberto)
    "Jarvis, responde essa mensagem dizendo que chego às 8"
    "Jarvis, digita: bom dia vírgula tudo certo ponto de interrogação"   (ditado literal)
    "Jarvis, desfaz o que você escreveu"

O texto entra no lugar do cursor (colado pela área de transferência, que volta
ao que era antes). No editor de código ele escreve só o código, no estilo e
na linguagem do arquivo. Precisa da chave do Gemini para os pedidos (o ditado
literal funciona sem).
"""

from __future__ import annotations

import re
import time
import unicodedata

from plugins._comum import MAC, registrar

PLUGIN = {
    "name": "ditado",
    "brief": "Smart dictation into any app: writes emails, messages or code (in the open editor's language) at the cursor.",
    "description": (
        "Smart dictation at the cursor of the app in front. action='escrever' with pedido = what to write, exactly as "
        "the user asked (e.g. 'um e-mail educado recusando…', 'uma função que…'); it detects the app (code editor → "
        "only code in the open file's language). action='digitar' with texto = literal dictation with spoken "
        "punctuation ('vírgula', 'ponto', 'nova linha'). action='desfazer' undoes the last insertion (Ctrl+Z)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "escrever | digitar | desfazer"},
                       "pedido": {"type": "STRING"}, "texto": {"type": "STRING"}},
        "required": [],
    },
}

EDITORES = ("code.exe", "cursor.exe", "pycharm", "idea", "sublime", "notepad++", "devenv", "vscodium", "zed")
LINGUAGENS = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript/React",
              ".jsx": "JavaScript/React", ".html": "HTML", ".css": "CSS", ".java": "Java", ".cs": "C#",
              ".cpp": "C++", ".c": "C", ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".kt": "Kotlin",
              ".sql": "SQL", ".sh": "Bash", ".ps1": "PowerShell", ".lua": "Lua", ".ino": "Arduino C++",
              ".json": "JSON", ".md": "Markdown", ".dart": "Dart", ".swift": "Swift"}
PONTUACAO = [("ponto de interrogacao", "?"), ("ponto de exclamacao", "!"), ("dois pontos", ":"),
             ("ponto e virgula", ";"), ("ponto final", "."), ("reticencias", "..."), ("virgula", ","),
             ("abre parenteses", "("), ("fecha parenteses", ")"), ("abre aspas", "“"), ("fecha aspas", "”"),
             ("travessao", "—"), ("nova linha", "\n"), ("novo paragrafo", "\n\n"), ("ponto", ".")]


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def formatar_fala(texto: str) -> str:
    """Ditado literal: troca a pontuação falada e acerta maiúsculas (pura)."""
    palavras = str(texto or "").split()
    saida, i = [], 0
    while i < len(palavras):
        achou = False
        for frase, sinal in PONTUACAO:
            n = len(frase.split())
            if _dobrar(" ".join(palavras[i:i + n])).strip(".,!?") == frase:
                saida.append(sinal)
                i += n
                achou = True
                break
        if not achou:
            saida.append(palavras[i])
            i += 1
    t = ""
    for w in saida:
        if w in ".,;:?!)…" or w == "..." or w == "”":
            t = t.rstrip() + w
        elif w.startswith("\n"):
            t = t.rstrip() + w
        elif t.endswith(("(", "“", "\n")) or not t:
            t += w
        else:
            t += " " + w
    t = re.sub(r"(^|[.!?]\s+|\n)([a-zà-ú])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t.strip(" ")


def contexto(janela: dict | None) -> dict:
    """De que tipo é o app em frente: {'tipo': 'codigo'|'email'|'chat'|'texto', 'linguagem', 'app'} (pura)."""
    titulo = (janela or {}).get("titulo", "") or ""
    proc = ((janela or {}).get("processo", "") or "").lower()
    tl = titulo.lower()
    m = re.search(r"(\.[a-z0-9]+)\b", titulo.split(" - ")[0].lower().lstrip("● ")) if titulo else None
    ext = m.group(1) if m else ""
    if any(e in proc for e in EDITORES) or "visual studio code" in tl:
        return {"tipo": "codigo", "linguagem": LINGUAGENS.get(ext, "a linguagem do arquivo aberto"), "app": titulo}
    if any(x in tl for x in ("gmail", "outlook", "e-mail", "email", "thunderbird")) or "outlook" in proc:
        return {"tipo": "email", "linguagem": "", "app": titulo}
    if any(x in tl for x in ("whatsapp", "telegram", "discord", "slack", "teams", "instagram", "messenger")):
        return {"tipo": "chat", "linguagem": "", "app": titulo}
    return {"tipo": "texto", "linguagem": "", "app": titulo}


def montar_prompt(pedido: str, ctx: dict) -> str:
    if ctx["tipo"] == "codigo":
        return (f"Escreva SOMENTE o código pedido, em {ctx['linguagem']}, pronto para colar no editor no lugar do cursor. "
                "Sem explicação, sem cercas ``` e sem texto fora do código; comentários curtos em português só se ajudarem. "
                f"Pedido: {pedido}")
    estilo = {"email": "um e-mail (com saudação, corpo e despedida; sem a linha de assunto, a não ser que peçam)",
              "chat": "uma mensagem de chat, natural e curta",
              "texto": "o texto"}[ctx["tipo"]]
    return (f"Escreva {estilo} em português do Brasil, pronto para colar, sem comentários antes ou depois e sem "
            f"Markdown. Pedido: {pedido}")


def limpar_saida(texto: str) -> str:
    t = (texto or "").strip()
    m = re.match(r"^```[\w+-]*\n(.*?)\n```$", t, re.S)
    return m.group(1) if m else t


_ultimo = {"quando": 0.0, "tam": 0}


def colar(texto: str) -> str:
    try:
        import pyautogui
        import pyperclip
    except ImportError:
        return "Preciso do pyautogui e do pyperclip: python -m pip install pyautogui pyperclip"
    antes = ""
    try:
        antes = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(texto)
    time.sleep(0.05)
    pyautogui.hotkey("command" if MAC else "ctrl", "v")
    time.sleep(0.35)
    try:
        pyperclip.copy(antes)
    except Exception:
        pass
    _ultimo.update(quando=time.time(), tam=len(texto))
    return ""


def _janela():
    try:
        from plugins._janelas import ativa
        return ativa()
    except Exception:
        return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "escrever").lower()
    try:
        j = _janela()
        if j and ("J.A.R.V.I.S" in (j.get("titulo") or "") or "JARVIS" in (j.get("titulo") or "")):
            return "A janela em frente é a do JARVIS. Clique onde quer o texto e peça de novo."
        if acao == "desfazer":
            if time.time() - _ultimo["quando"] > 600:
                return "Não escrevi nada nos últimos minutos."
            import pyautogui
            pyautogui.hotkey("command" if MAC else "ctrl", "z")
            return "Desfiz."
        if acao == "digitar":
            texto = formatar_fala(str(p.get("texto") or ""))
            if not texto:
                return "O que eu digito?"
            erro = colar(texto)
            return erro or f"Digitei: {texto[:80]}"
        pedido = str(p.get("pedido") or p.get("texto") or "").strip()
        if not pedido:
            return "O que eu escrevo?"
        from plugins import _ia
        if not _ia.disponivel():
            return "Para escrever a partir de um pedido eu preciso da chave do Gemini (o ditado literal funciona sem)."
        ctx = contexto(j)
        texto = limpar_saida(_ia.perguntar(montar_prompt(pedido, ctx), ctx["tipo"] == "codigo", 60) or "")
        if not texto:
            return "Não consegui escrever agora."
        erro = colar(texto)
        if erro:
            return erro
        registrar(player, f"Ditado: {len(texto)} caracteres em {ctx['app'][:60]}.")
        oque = {"codigo": f"o código em {ctx['linguagem']}", "email": "o e-mail", "chat": "a mensagem"}.get(ctx["tipo"], "o texto")
        return f"Escrevi {oque} no lugar do cursor ({len(texto.splitlines())} linhas). Se não gostar, diga 'desfaz'."
    except Exception as e:
        return f"O ditado falhou: {e}"
