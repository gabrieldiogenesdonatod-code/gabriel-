"""Catálogo (2.19): acha a ferramenta certa entre as centenas do JARVIS, mostra como usar cada uma e conta plugins e modos."""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from plugins._lote2 import P, norm, rodar

PLUGIN = P("catalogo", "Find the right JARVIS tool among hundreds: search by need (Portuguese), show a tool's parameters, count plugins and modes.",
           "buscar | ajuda | contar",
           "buscar: texto = what the user wants. ajuda: nome = tool name -> its parameters and actions. "
           "contar: how many tools and modes exist.",
           "texto nome")

PARADAS = set("""a o e é as os um uma uns umas de da do das dos em no na nos nas por pra para pro com sem que se me te
lhe isso esse essa este esta isto aquele aquela ai aí la lá ja já so só tem ter tenho temos fazer faz faça faca poe põe
bota da dá dar quero queria preciso precisa pode podia quanto quanta quantos quantas quando qual quais como onde quem
meu minha meus minhas seu sua seus suas voce você vai vou vamos foi ser sou é está esta estou estão hoje agora ontem
amanha amanhã jarvis senhor coisa algo alguma algum mais menos muito muita tudo todo toda todos todas ainda tambem também
sobre usar plugin plugins ferramenta favor por_favor ok oi ola olá the and for of to with""".split())


def declaracoes() -> list[dict]:
    from core import registro_ferramentas
    return registro_ferramentas.declaracoes()


def doc_pt(nome: str) -> str:
    """Primeira frase do arquivo do plugin (em português), para as telas e a lista."""
    linhas = [l.strip() for l in doc_completo(nome).splitlines() if l.strip()]
    if not linhas:
        return ""
    t = re.sub(r"\s*\((?:fork PT-BR )?[\d.]+\)", "", " ".join(linhas[:2]))
    return re.sub(r"\s+([:.,])", r"\1", re.sub(r"\s{2,}", " ", t)).strip(" —:-")[:220]


def _sem_acento(t: str) -> str:
    return norm(t)


CURTAS = {"vo", "pc", "tv", "qr", "dj", "ip"}          # palavras de 2 letras que dizem muito ("vó", "PC"…)


def raizes(texto: str) -> list[tuple[str, str]]:
    """Cada palavra útil vira (raiz de 5 letras, raiz de 4 letras): 'sorteia' e 'sorteio' → 'sorte'. Pura."""
    out = []
    for w in re.findall(r"[a-z]+", _sem_acento(texto)):
        if (len(w) < 3 and w not in CURTAS) or w in PARADAS:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append((w[:5], w[:4]))
    return out


def palavras(texto: str) -> list[str]:
    """Compatível com a 2.19: só as raízes de 5 letras."""
    return [r5 for r5, _ in raizes(texto)]


def doc_completo(nome: str) -> str:
    try:
        from core import registro_ferramentas
        rec = registro_ferramentas._plugins_reg()._plugins.get(nome)
        mod = sys.modules.get(f"plugins.{Path(rec.file).stem}") if rec else None
        return str(getattr(mod, "__doc__", "") or "")[:2500]
    except Exception:
        return ""


_INDICE: dict = {"chave": None}


def _indice(decls: list[dict]) -> dict:
    """Índice das raízes de cada ferramenta (nome, descrições e o texto em português do arquivo), com o peso de cada
    raiz (raiz rara vale mais: 'churrasco' diz mais que 'calcular')."""
    chave = tuple(d["name"] for d in decls)
    if _INDICE.get("chave") == chave:
        return _INDICE
    docs = []
    for d in decls:
        nome = raizes(d["name"].replace("_", " "))
        props = (d.get("parameters") or {}).get("properties") or {}
        acoes = " ".join(f"{k} {v.get('description', '')}".replace("_", " ") for k, v in props.items())
        corpo = raizes(" ".join([d["name"].replace("_", " "), str(d.get("brief") or ""), str(d.get("description") or ""),
                                 acoes, doc_completo(d["name"])]))
        docs.append({"nome5": {r5 for r5, _ in nome}, "r5": {r5 for r5, _ in corpo}, "r4": {r4 for _, r4 in corpo}})
    n = len(docs) or 1
    df5, df4 = {}, {}
    for doc in docs:
        for r in doc["r5"]:
            df5[r] = df5.get(r, 0) + 1
        for r in doc["r4"]:
            df4[r] = df4.get(r, 0) + 1
    _INDICE.update(chave=chave, docs=docs, n=n, df5=df5, df4=df4)
    return _INDICE


def nota(ind: dict, i: int, consulta: list[tuple[str, str]]) -> float:
    doc, n, total = ind["docs"][i], ind["n"], 0.0
    for r5, r4 in consulta:
        if r5 in doc["r5"]:
            peso = math.log(1 + n / ind["df5"][r5])
        elif r4 in doc["r4"]:
            peso = 0.5 * math.log(1 + n / ind["df4"][r4])
        else:
            continue
        total += peso * (2.0 if r5 in doc["nome5"] else 1.0)
    return total / max(1.0, len(doc["r5"])) ** 0.15          # texto enorme não ganha só por falar de tudo


def buscar(decls: list[dict], pergunta: str, n: int = 6) -> list[dict]:
    """As n ferramentas que mais combinam com o pedido em português (raízes, peso pela raridade, nome vale o dobro). Pura."""
    consulta = list(dict.fromkeys(raizes(pergunta)))
    if not consulta:
        return []
    ind = _indice(decls)
    notas = sorted(((nota(ind, i, consulta), i) for i in range(len(decls))), reverse=True)[:n]
    return [decls[i] for s, i in notas if s > 0]


def com_cerebro(decls: list[dict], pergunta: str, n: int = 6) -> list[dict]:
    """3.4: a busca de sempre, com as ferramentas que o cérebro local aprendeu COM VOCÊ na frente."""
    achadas = buscar(decls, pergunta, n)
    try:
        from core import cerebro
        por_nome = {d["name"]: d for d in decls}
        pessoais = [por_nome[f] for f in cerebro.sugerir(pergunta) if f in por_nome]
    except Exception:
        pessoais = []
    vistos, out = set(), []
    for d in pessoais + achadas:
        if d["name"] not in vistos:
            vistos.add(d["name"])
            out.append(d)
    return out[:n]


def assinatura(d: dict, completa: bool = False) -> str:
    from core.orcamento_ferramentas import assinatura as curta
    if not completa:
        return curta(d) + (f" — {doc_pt(d['name'])}" if doc_pt(d["name"]) else "")
    props = (d.get("parameters") or {}).get("properties") or {}
    campos = "; ".join(f"{k}: {v.get('description')}" if v.get("description") else k for k, v in props.items())
    return f"{d['name']} — {' '.join(str(d.get('description') or '').split())[:700]}\nParâmetros: {campos}"


def _buscar(p, pl):
    achadas = com_cerebro(declaracoes(), p.get("texto") or p.get("nome") or "")
    return "\n".join(assinatura(d) for d in achadas) or "Nenhuma ferramenta parecida. Tente outras palavras."


def _ajuda(p, pl):
    nome, decls = norm(p.get("nome") or p.get("texto")).replace(" ", "_"), declaracoes()
    d = next((x for x in decls if x["name"] == nome), None) or next(iter(buscar(decls, nome.replace("_", " "), 1)), None)
    return assinatura(d, completa=True) if d else f"Não achei a ferramenta '{nome}'. Use buscar."


def _contar(p, pl):
    from plugins import modos
    return f"Tenho {len(declaracoes())} ferramentas e {len(modos.todos())} modos, senhor."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"buscar": _buscar, "ajuda": _ajuda, "contar": _contar}, player)
