"""
Segundo cérebro por voz (fork PT-BR 2.9).

Você fala uma ideia, um lembrete ou uma informação solta e o JARVIS guarda sozinho,
já organizado em PASTA e TAGS — e depois acha quando você pede.

    "Jarvis, guarda no meu cérebro: o fornecedor de Jaraguá fecha às 17h."
    "Jarvis, anota que a senha do wifi da loja é a data de aniversário da vó."
    "Jarvis, o que eu falei sobre o fornecedor de Jaraguá?"
    "Jarvis, me mostra tudo da pasta loja."         "Jarvis, o que tem no meu segundo cérebro?"

Cada nota vira um arquivo Markdown com as tags no topo, dentro de
Documentos\\JARVIS\\segundo_cerebro\\<pasta>\\ (ou direto no seu cofre do Obsidian, se
você apontar o caminho em ⚙). Assim dá pra abrir e editar fora do JARVIS também.
Um índice em memory/segundo_cerebro.json deixa a busca rápida, sem abrir tudo.

A pasta e as tags saem por regras (funciona sem internet); com a chave do Gemini,
ficam mais certeiras. É diferente da caixinha de ideias (plugins/ideias.py): lá é
ideia → projeto; aqui é a sua memória do dia a dia, de qualquer assunto.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from plugins._comum import (MEMORIA, abrir_no_sistema, cfg, gravar_json, ler_json, mostrar, pasta_usuario, registrar)

PLUGIN = {
    "name": "segundo_cerebro",
    "brief": "Second brain: saves any note/idea/fact by voice, auto-filed into a folder + tags, recalls it later.",
    "description": (
        "The user's second brain — saves any loose note, reminder or fact and files it by itself into a FOLDER + "
        "TAGS, then finds it later. Use for 'guarda/anota isso no meu cérebro/segundo cérebro', 'lembra que...', "
        "'o que eu falei sobre X?', 'o que tem na pasta Y?'. NOT for ideas meant to become projects (use 'ideias') "
        "nor for reusable AI prompts (use 'biblioteca_prompts'). action: 'anotar' (texto = the note in the user's "
        "words; optional pasta and tags to force them); 'buscar' (termo = what to recall); 'listar' (optional pasta; "
        "no pasta = the folders and recent notes); 'abrir' (open the folder); 'remover' (nota = id or words). "
        "Always pass the note/query in the user's own words."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "anotar | buscar | listar | abrir | remover"},
            "texto": {"type": "STRING", "description": "the note, in the user's words (for 'anotar')"},
            "termo": {"type": "STRING", "description": "what to recall (for 'buscar')"},
            "pasta": {"type": "STRING"}, "tags": {"type": "STRING", "description": "comma-separated, optional"},
            "nota": {"type": "STRING", "description": "id or words (for 'remover')"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "segundo_cerebro",
    "title": "Segundo cérebro",
    "fields": [
        {"key": "cofre", "label": "Pasta onde salvar (vazio = Documentos\\JARVIS\\segundo_cerebro; pode ser o seu "
                                   "cofre do Obsidian)", "type": "text", "default": ""},
        {"key": "subpasta", "label": "Subpasta dentro do cofre do Obsidian (ex.: JARVIS)", "type": "text",
         "default": ""},
        {"key": "usar_ia", "label": "Usar o Gemini para escolher pasta e tags (fica mais certeiro)", "type": "toggle",
         "default": True},
        {"key": "abrir_ao_criar", "label": "Abrir o arquivo da nota ao guardar", "type": "toggle", "default": False},
    ],
}

ARQ = MEMORIA / "segundo_cerebro.json"      # o carregador dos testes troca este caminho

_lock = threading.RLock()
MAX_TAGS = 6
PASTAS = [
    ("loja", r"\bloja\b|cristal|malha|cliente|estoque|venda|vender|roupa|cole[çc][ãa]o|pe[çc]a|fornecedor|vitrine|"
             r"pre[çc]o|frete|encomenda"),
    ("programação", r"\bapp\b|aplicativo|sistema|software|c[óo]digo|site|programa|bug|erro|api\b|script|python|jarvis|"
                    r"servidor|deploy|git\b|reposit[óo]rio"),
    ("estudo", r"estud|curso|aprender|livro|faculdade|prova|senai|aula|mat[ée]ria|resumo|anota[çc]"),
    ("música", r"m[úu]sica|\brap\b|beat|letra|rima|clipe|\bfeat\b|[áa]lbum|\bep\b|batida|kaiser|markinho"),
    ("conteúdo", r"v[íi]deo|youtube|tiktok|reels|canal|\blive\b|\bpost\b|instagram|podcast|roteiro|legenda"),
    ("finanças", r"conta|boleto|pagar|pagamento|divida|d[íi]vida|empr[ée]stimo|cart[ãa]o|pix|sal[áa]rio|or[çc]amento|"
                 r"gasto|banco"),
    ("casa", r"\bcasa\b|quarto|cozinha|reforma|m[óo]vel|jardim|planta|mercado|supermercado|lista de compras|"
             r"limpeza|conta de luz|[áa]gua"),
    ("saúde", r"m[ée]dico|consulta|exame|rem[ée]dio|dentista|vacina|academia|treino|dieta|sono|dormir"),
    ("trabalho", r"trabalho|emprego|chefe|reuni[ãa]o|cliente|prazo|entrega|projeto do trabalho|servi[çc]o"),
    ("senhas", r"senha|login|c[óo]digo de acesso|pin\b|wifi|wi-fi"),
    ("pessoal", r"\bv[óo]\b|av[óo]|m[ãa]e|pai|irm[ãa]o|amigo|namorada|fam[íi]lia|anivers[áa]rio|presente"),
    ("contatos", r"telefone|celular|whatsapp|contato|e-?mail|endere[çc]o"),
]
_STOP = {"que", "para", "pra", "com", "sobre", "uma", "uns", "umas", "dos", "das", "nos", "nas", "por", "mas", "como",
         "meu", "minha", "isso", "aqui", "tem", "the", "and", "lembra", "guarda", "anota", "nota", "cerebro", "segundo",
         "jarvis", "falei", "sobre", "coisa", "fazer", "ter", "vou", "voce", "ele", "ela", "num", "numa", "naquele"}


# ── texto (puro) ───────────────────────────────────────────────────────────────
def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def limpar(texto: str) -> str:
    """Tira o 'guarda no meu cérebro:' do começo e arruma o texto (puro)."""
    t = " ".join(str(texto or "").split())
    t = re.sub(r"(?i)^(jarvis[,:]?\s*)?(guarda|guarde|anota|anote|lembra|lembre|salva|grava|p[õo]e)\b"
               r"(\s+(isso|aqui|a[íi]))?"
               r"(\s+no\s+(meu\s+)?(segundo\s+)?c[ée]rebro)?"
               r"(\s+que)?\s*[:,\-]?\s*", "", t, count=1).strip()
    return (t or " ".join(str(texto or "").split())).strip(" .")


def titulo_de(texto: str, limite: int = 60) -> str:
    """Primeira linha curta para o nome do arquivo e o título (puro)."""
    t = " ".join(str(texto or "").split())
    corte = re.split(r"[.!?\n]", t, maxsplit=1)[0]
    if len(corte) > limite:
        corte = corte[:limite].rsplit(" ", 1)[0] + "…"
    return corte or "nota"


def slug(texto: str, limite: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", dobrar(texto)).strip("-")
    return s[:limite].strip("-") or "nota"


def pasta_por_regra(texto: str) -> str:
    t = dobrar(texto)
    for nome, padrao in PASTAS:
        if re.search(padrao, t):
            return nome
    return ""


def tags_de(texto: str, maximo: int = MAX_TAGS) -> list[str]:
    """Palavras-chave da nota, por frequência e tamanho (puro)."""
    brutas = re.findall(r"[a-z0-9][a-z0-9\-]{2,}", dobrar(texto))
    contagem: dict[str, int] = {}
    primeira: dict[str, int] = {}
    for i, p in enumerate(brutas):
        if p in _STOP or p.isdigit():
            continue
        primeira.setdefault(p, i)
        contagem[p] = contagem.get(p, 0) + 1
    chaves = sorted(primeira, key=lambda p: (-contagem[p], -len(p), primeira[p]))
    return chaves[:maximo]


def frontmatter(nota: dict) -> str:
    """Topo YAML do .md — o Obsidian lê as tags daqui (puro)."""
    tags = " ".join(f"#{t}" for t in nota.get("tags") or [])
    quando = datetime.fromtimestamp(nota.get("criada") or time.time()).strftime("%Y-%m-%d %H:%M")
    linhas = ["---", f"criada: {quando}", f"pasta: {nota.get('pasta') or 'geral'}",
              "tags: [" + ", ".join(nota.get("tags") or []) + "]", "---", "", f"# {nota.get('titulo') or 'Nota'}", "",
              nota.get("texto") or "", ""]
    if tags:
        linhas += ["", tags]
    return "\n".join(linhas)


def buscar_notas(notas: list[dict], termo: str) -> list[dict]:
    """Notas que combinam com o termo, melhores primeiro (puro)."""
    t = str(termo or "").strip()
    if t.lstrip("#").isdigit():
        return [n for n in notas if n.get("id") == int(t.lstrip("#"))]
    palavras = [w for w in re.findall(r"[a-z0-9]+", dobrar(t)) if len(w) > 2 and w not in _STOP]
    if not palavras:
        return []
    pontuadas = []
    for n in notas:
        alvo = dobrar(" ".join([n.get("texto", ""), n.get("pasta", "")] + (n.get("tags") or [])))
        alvo_tags = set(n.get("tags") or [])
        pontos = sum(2 if w in alvo_tags else (1 if w in alvo else 0) for w in palavras)
        if pontos:
            pontuadas.append((pontos, n.get("criada", 0), n))
    pontuadas.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [n for _p, _c, n in pontuadas]


# ── dados ──────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("notas", [])
    d.setdefault("proximo_id", 1)
    return d


def _gravar(d: dict) -> None:
    with _lock:
        d["notas"] = d.get("notas", [])[-2000:]
        gravar_json(ARQ, d)


def _c() -> dict:
    return cfg("segundo_cerebro", PLUGIN_SETTINGS)


def base_cofre() -> Path:
    c = _c()
    raiz = str(c.get("cofre") or "").strip()
    if raiz:
        p = Path(raiz).expanduser()
        sub = str(c.get("subpasta") or "").strip()
        return (p / sub) if sub else p
    return pasta_usuario("Documents") / "JARVIS" / "segundo_cerebro"


def classificar(texto: str, pasta: str = "", tags=None) -> tuple[str, list[str]]:
    """Pasta + tags da nota: o que você mandou vale; senão regra; senão o Gemini (se ligado)."""
    pasta = (pasta or "").strip().lower()
    tags = [t.strip().lower() for t in (tags or []) if str(t).strip()]
    if pasta and tags:
        return pasta[:24], tags[:MAX_TAGS]
    pasta = pasta or pasta_por_regra(texto)
    tags = tags or tags_de(texto)
    if (not pasta or len(tags) < 2) and _c().get("usar_ia", True):
        try:
            from plugins import _ia
            existentes = sorted({n.get("pasta", "") for n in dados()["notas"] if n.get("pasta")})
            j = _ia.perguntar_json(
                "Organize esta anotação pessoal. Devolva {\"pasta\": \"uma ou duas palavras em minúsculas\", "
                "\"tags\": [\"3\", \"a\", \"5 palavras-chave\"]}. Prefira uma destas pastas se servir: "
                f"{', '.join(sorted(set(existentes + [p for p, _ in PASTAS]))) or 'nenhuma ainda'}. "
                f"Anotação: \"{texto[:500]}\".", inteligente=False, segundos=12) or {}
            pasta = pasta or str(j.get("pasta") or "").strip().lower()[:24]
            if len(tags) < 2 and isinstance(j.get("tags"), list):
                tags = [str(t).strip().lower().lstrip("#") for t in j["tags"] if str(t).strip()][:MAX_TAGS]
        except Exception:
            pass
    return (pasta or "geral"), (tags or ["nota"])


# ── ações ──────────────────────────────────────────────────────────────────────
def anotar(texto: str, pasta: str = "", tags=None) -> str:
    texto = limpar(texto)
    if len(texto) < 3:
        return "O que você quer que eu guarde?"
    pasta, tags = classificar(texto, pasta, tags)
    agora = time.time()
    with _lock:
        d = dados()
        if any(dobrar(n.get("texto", "")) == dobrar(texto) for n in d["notas"]):
            return "Isso eu já tinha guardado."
        nota = {"id": d["proximo_id"], "titulo": titulo_de(texto), "texto": texto, "pasta": pasta, "tags": tags,
                "criada": agora, "arquivo": ""}
        caminho = _escrever_md(nota)
        nota["arquivo"] = str(caminho) if caminho else ""
        d["notas"].append(nota)
        d["proximo_id"] += 1
        quantas = sum(1 for n in d["notas"] if n.get("pasta") == pasta)
        _gravar(d)
    registrar(None, f"🧠 Guardei na pasta {pasta}: {nota['titulo']}")
    if caminho and _c().get("abrir_ao_criar"):
        abrir_no_sistema(str(caminho))
    etq = ", ".join("#" + t for t in tags)
    return (f"Guardado na pasta **{pasta}** com as tags {etq} (nota #{nota['id']}). Você tem {quantas} "
            f"nota{'s' if quantas != 1 else ''} aí. Confirme numa frase curta, repetindo a pasta e as tags.")


def _escrever_md(nota: dict) -> Path | None:
    try:
        pasta = base_cofre() / slug(nota["pasta"], 32)
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / f"{slug(nota['titulo'])}-{nota['id']}.md"
        alvo.write_text(frontmatter(nota), encoding="utf-8")
        return alvo
    except Exception as e:
        print(f"[Cérebro] não gravei o .md (guardei só no índice): {e}")
        return None


def buscar(termo: str) -> str:
    termo = re.sub(r"(?i)^(o que (eu )?(falei|disse|guardei|anotei) (sobre|de|da|do)\s+)", "", str(termo or "")).strip()
    with _lock:
        achados = buscar_notas(dados()["notas"], termo)
    if not termo:
        return "Sobre o que você quer lembrar?"
    if not achados:
        return f"Não achei nada sobre “{termo}” no seu segundo cérebro."
    corpo = "\n".join(f"• [{n['pasta']}] {n['texto']}" + (f"  ({', '.join('#' + t for t in n['tags'])})"
                                                          if n.get("tags") else "") for n in achados[:8])
    mostrar(None, f"CÉREBRO · {termo}", corpo)
    melhores = achados[:5]
    ctx = " | ".join(f"[{n['pasta']}] {n['texto']}" for n in melhores)
    return (f"Achei {len(achados)} nota(s). As mais próximas: {ctx}. Responda ao usuário usando o que está nessas "
            "notas, em até 4 frases, sem inventar nada que não esteja aí.")


def listar(pasta: str = "") -> str:
    with _lock:
        notas = dados()["notas"]
    if not notas:
        return "Seu segundo cérebro está vazio. Diga 'guarda no meu cérebro: ...' que eu começo a anotar."
    pasta = (pasta or "").strip().lower()
    if pasta:
        da_pasta = [n for n in notas if n.get("pasta") == pasta]
        if not da_pasta:
            return f"Não tenho nada na pasta {pasta} ainda."
        corpo = "\n".join(f"#{n['id']} {n['titulo']}" for n in sorted(da_pasta, key=lambda n: -n.get("criada", 0))[:20])
        mostrar(None, f"CÉREBRO · {pasta}", corpo)
        return f"Na pasta {pasta} você tem {len(da_pasta)} nota(s). Mostrei na tela; resuma em 2 frases."
    pastas: dict[str, int] = {}
    for n in notas:
        pastas[n.get("pasta", "geral")] = pastas.get(n.get("pasta", "geral"), 0) + 1
    linhas = [f"{nome}: {q}" for nome, q in sorted(pastas.items(), key=lambda x: -x[1])]
    mostrar(None, "SEGUNDO CÉREBRO", "\n".join(linhas))
    total = len(notas)
    resumo = ", ".join(f"{nome} ({q})" for nome, q in sorted(pastas.items(), key=lambda x: -x[1])[:6])
    return f"Você tem {total} nota(s) no segundo cérebro, em {len(pastas)} pasta(s): {resumo}. Resuma em 2 frases."


def remover(termo: str) -> str:
    with _lock:
        d = dados()
        achados = buscar_notas(d["notas"], termo)
        if not achados:
            return f"Não achei “{termo}” para apagar."
        if len(achados) > 1 and not str(termo).lstrip("#").isdigit():
            return ("Achei mais de uma: " + "; ".join(f"#{n['id']} {n['titulo']}" for n in achados[:5])
                    + ". Qual? (diga o número)")
        nota = achados[0]
        d["notas"] = [n for n in d["notas"] if n.get("id") != nota["id"]]
        _gravar(d)
    try:
        if nota.get("arquivo"):
            Path(nota["arquivo"]).unlink(missing_ok=True)
    except Exception:
        pass
    return f"Apaguei a nota #{nota['id']} ({nota['titulo']})."


def abrir() -> str:
    base = base_cofre()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    abrir_no_sistema(str(base))
    return f"Abri a pasta do seu segundo cérebro: {base}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "listar").strip()
    try:
        if acao in ("anotar", "guardar", "salvar", "lembrar", "nota"):
            tags = [t for t in re.split(r"[,;]", str(p.get("tags") or "")) if t.strip()]
            return anotar(str(p.get("texto") or p.get("termo") or ""), str(p.get("pasta") or ""), tags)
        if acao in ("buscar", "achar", "lembrar_de", "recordar", "o_que"):
            return buscar(str(p.get("termo") or p.get("texto") or p.get("pasta") or ""))
        if acao in ("listar", "lista", "mostrar", "ver"):
            return listar(str(p.get("pasta") or ""))
        if acao in ("abrir", "pasta"):
            return abrir()
        if acao in ("remover", "apagar", "excluir"):
            return remover(str(p.get("nota") or p.get("termo") or p.get("texto") or ""))
        return listar(str(p.get("pasta") or ""))
    except Exception as e:
        return f"O segundo cérebro falhou: {e}"
