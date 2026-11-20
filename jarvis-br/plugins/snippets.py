"""Snippets de código (2.18): guarda trechos com etiqueta, busca e cola na área de transferência."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, lista, norm, rodar

PLUGIN = P("snippets", "Code snippet library: save code by name/tags/language, search, copy to clipboard, list, delete. Uses clipboard when no code given.",
           "salvar | copiar | buscar | listar | apagar",
           "salvar: nome, codigo (or clipboard), tags, linguagem. copiar: nome. buscar: texto.",
           "nome codigo tags linguagem texto")

S = Colecao("snippets")


def buscar(snips: list[dict], q: str) -> list[str]:
    q = norm(q)
    return [s["nome"] for s in snips if q in norm(s["nome"]) or q in norm(" ".join(s["tags"])) or q in norm(s["lang"])
            or q in s["codigo"].lower()]


def _clip(texto=None):
    try:
        import pyperclip
        return pyperclip.paste() if texto is None else pyperclip.copy(texto)
    except Exception:
        return "" if texto is None else None


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "salvar":
        cod = str(p.get("codigo") or "") or _clip()
        if not cod:
            return "Copie o código antes ou me passe ele."
        S.por(nome, {"codigo": cod, "tags": lista(p.get("tags")), "lang": str(p.get("linguagem") or "")})
        return f"Snippet '{nome}' salvo ({len(cod.splitlines())} linhas)."
    if a == "listar":
        return ", ".join(S.nomes()) or "Nenhum snippet."
    if a == "buscar":
        return ", ".join(buscar(list(S.tudo().values()), p.get("texto") or nome)) or "Nada encontrado."
    s = S.pegar(nome)
    if not s:
        return "Não achei."
    if a == "apagar":
        S.tirar(nome)
        return "Apagado."
    _clip(s["codigo"])
    return f"'{s['nome']}' copiado. Cole com Ctrl+V."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("salvar copiar buscar listar apagar".split(), _go), player)
