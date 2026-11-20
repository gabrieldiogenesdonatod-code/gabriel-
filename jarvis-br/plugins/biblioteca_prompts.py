"""
Biblioteca de prompts (fork PT-BR 2.9).

Guarda os pedidos que deram certo e reaproveita por voz — pra você não reescrever
o mesmo prompt bom toda vez.

    "Jarvis, salva esse prompt como 'post de produto': Escreva uma legenda de
     Instagram animada pra foto de uma peça infantil, com 3 hashtags."
    "Jarvis, usa o prompt do post de produto."      → ele te devolve o texto pronto
    "Jarvis, quais prompts eu tenho?"               "Jarvis, apaga o prompt do post de produto"

Fica tudo em memory/prompts.json. Combina com o segundo cérebro (que guarda notas)
e com a caixinha de ideias (que vira projeto): este aqui é só a sua coleção de
prompts favoritos.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "biblioteca_prompts",
    "brief": "Prompt library: saves good prompts by name/tags and reuses them by voice.",
    "description": (
        "The user's library of good, reusable prompts. Use for 'salva esse prompt como X', 'usa/pega o prompt de "
        "X', 'quais prompts eu tenho?', 'apaga o prompt X'. action: 'salvar' (nome = short name; texto = the prompt "
        "text, in full; optional tags); 'usar' (termo = name or words → returns the saved prompt text to reuse); "
        "'listar' (optional tag); 'remover' (termo = name/id). For 'usar', hand the returned prompt text back so it "
        "can be used right away. Do NOT use for notes/facts (that is 'segundo_cerebro') or ideas ('ideias')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "salvar | usar | listar | remover"},
            "nome": {"type": "STRING"}, "texto": {"type": "STRING", "description": "the full prompt (for 'salvar')"},
            "termo": {"type": "STRING", "description": "name or words (for 'usar'/'remover')"},
            "tags": {"type": "STRING", "description": "comma-separated, optional"},
        },
        "required": ["action"],
    },
}

ARQ = MEMORIA / "prompts.json"          # o carregador dos testes troca este caminho
_lock = threading.RLock()
_STOP = {"prompt", "prompts", "o", "a", "de", "da", "do", "the", "usa", "usar", "pega", "salva", "salvar", "com",
         "para", "pra", "um", "uma", "meu", "minha", "esse", "essa", "jarvis"}


# ── texto (puro) ───────────────────────────────────────────────────────────────
def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def limpar_nome(nome: str) -> str:
    n = " ".join(str(nome or "").split())
    n = re.sub(r"(?i)^(o )?prompt (d[aeo] |chamad[oa] )?", "", n).strip().strip("\"'“”")
    return n[:60]


def palavras(termo: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", dobrar(termo)) if len(w) > 1 and w not in _STOP]


def achar(prompts: list[dict], termo: str) -> list[dict]:
    """Prompts que combinam com o termo, melhores primeiro (puro). Nome vale mais que tag, que vale mais que texto."""
    t = str(termo or "").strip()
    if t.lstrip("#").isdigit():
        return [p for p in prompts if p.get("id") == int(t.lstrip("#"))]
    ps = palavras(t)
    if not ps:
        return []
    pontuados = []
    for pr in prompts:
        nome = dobrar(pr.get("nome", ""))
        tags = set(pr.get("tags") or [])
        corpo = dobrar(pr.get("texto", ""))
        pontos = 0
        for w in ps:
            if w in nome:
                pontos += 4
            elif w in tags:
                pontos += 2
            elif w in corpo:
                pontos += 1
        if dobrar(t) == nome:
            pontos += 20
        if pontos:
            pontuados.append((pontos, pr.get("usos", 0), pr))
    pontuados.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [p for _pt, _u, p in pontuados]


def formatar_lista(prompts: list[dict]) -> str:
    linhas = []
    for p in prompts:
        tags = "  " + " ".join("#" + t for t in p.get("tags") or []) if p.get("tags") else ""
        usos = f"  ({p['usos']}x)" if p.get("usos") else ""
        linhas.append(f"#{p['id']} {p['nome']}{tags}{usos}")
    return "\n".join(linhas)


# ── dados ──────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("prompts", [])
    d.setdefault("proximo_id", 1)
    return d


def _gravar(d: dict) -> None:
    with _lock:
        gravar_json(ARQ, d)


# ── ações ──────────────────────────────────────────────────────────────────────
def salvar(nome: str, texto: str, tags=None) -> str:
    nome = limpar_nome(nome)
    texto = str(texto or "").strip()
    if not texto:
        return "Qual é o prompt que eu guardo?"
    if not nome:
        nome = " ".join(texto.split()[:5])
    tags = [dobrar(t).strip() for t in (tags or []) if str(t).strip()][:6]
    agora = time.time()
    with _lock:
        d = dados()
        igual = next((p for p in d["prompts"] if dobrar(p["nome"]) == dobrar(nome)), None)
        if igual:
            igual.update(texto=texto, tags=tags or igual.get("tags", []), alterado=agora)
            _gravar(d)
            return f"Atualizei o prompt “{igual['nome']}”."
        pr = {"id": d["proximo_id"], "nome": nome, "texto": texto, "tags": tags, "criado": agora, "usos": 0}
        d["prompts"].append(pr)
        d["proximo_id"] += 1
        _gravar(d)
    registrar(None, f"📚 Prompt salvo: {nome}")
    etq = (" com as tags " + ", ".join("#" + t for t in tags)) if tags else ""
    return f"Salvei o prompt “{nome}”{etq}. É só dizer 'usa o prompt {nome}' quando precisar."


def usar(termo: str) -> str:
    with _lock:
        d = dados()
        achados = achar(d["prompts"], termo)
        if not achados:
            return (f"Não achei nenhum prompt com “{termo}”. Diga 'quais prompts eu tenho?' pra ver a lista."
                    if termo else "Qual prompt você quer usar?")
        exato = str(termo).lstrip("#").isdigit() or dobrar(termo) == dobrar(achados[0]["nome"])
        if len(achados) > 1 and not exato and achados[0]["nome"] != achados[1]["nome"]:
            return ("Achei mais de um: " + "; ".join(f"#{p['id']} {p['nome']}" for p in achados[:5])
                    + ". Qual deles? (diga o nome ou o número)")
        pr = achados[0]
        pr["usos"] = pr.get("usos", 0) + 1
        pr["ultimo_uso"] = time.time()
        _gravar(d)
    mostrar(None, f"PROMPT · {pr['nome']}", pr["texto"])
    return (f"Aqui está o seu prompt “{pr['nome']}”:\n\n{pr['texto']}\n\n"
            "(Entregue esse texto ao usuário exatamente como está, pronto pra usar.)")


def listar(tag: str = "") -> str:
    with _lock:
        prompts = dados()["prompts"]
    if not prompts:
        return "Sua biblioteca de prompts está vazia. Diga 'salva esse prompt como ...' que eu começo a guardar."
    tag = dobrar(tag).strip().lstrip("#")
    if tag:
        prompts = [p for p in prompts if tag in (p.get("tags") or [])]
        if not prompts:
            return f"Não tenho prompts com a tag #{tag}."
    prompts = sorted(prompts, key=lambda p: (-p.get("usos", 0), -p.get("criado", 0)))
    mostrar(None, "BIBLIOTECA DE PROMPTS", formatar_lista(prompts))
    nomes = ", ".join(f"“{p['nome']}”" for p in prompts[:8])
    return f"Você tem {len(prompts)} prompt(s): {nomes}. Mostrei a lista na tela; resuma em 1 ou 2 frases."


def remover(termo: str) -> str:
    with _lock:
        d = dados()
        achados = achar(d["prompts"], termo)
        if not achados:
            return f"Não achei o prompt “{termo}” pra apagar."
        if len(achados) > 1 and not str(termo).lstrip("#").isdigit() and dobrar(termo) != dobrar(achados[0]["nome"]):
            return ("Achei mais de um: " + "; ".join(f"#{p['id']} {p['nome']}" for p in achados[:5]) + ". Qual?")
        pr = achados[0]
        d["prompts"] = [p for p in d["prompts"] if p.get("id") != pr["id"]]
        _gravar(d)
    return f"Apaguei o prompt “{pr['nome']}”."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "listar").strip()
    try:
        if acao in ("salvar", "salva", "guardar", "adicionar"):
            tags = [t for t in re.split(r"[,;]", str(p.get("tags") or "")) if t.strip()]
            return salvar(str(p.get("nome") or p.get("termo") or ""), str(p.get("texto") or ""), tags)
        if acao in ("usar", "usa", "pegar", "buscar", "mostrar_prompt"):
            return usar(str(p.get("termo") or p.get("nome") or ""))
        if acao in ("listar", "lista", "quais", "ver"):
            return listar(str(p.get("tags") or p.get("termo") or ""))
        if acao in ("remover", "apagar", "excluir"):
            return remover(str(p.get("termo") or p.get("nome") or ""))
        return listar()
    except Exception as e:
        return f"A biblioteca de prompts falhou: {e}"
