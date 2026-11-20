"""
Palavras secretas (2.21): o JARVIS observa o que você sempre pede junto e INVENTA uma palavra para isso.

    "Percebi que nos dias de semana, de manhã, você abre o caixa, olha a meta de vendas e põe música.
     Inventei o 'Protocolo Pequi': é só falar e eu faço os três."

Ele lê o diário de uso (core/registro_uso.py), acha sequências de 2 a 4 ferramentas que se repetem em
dias diferentes, dá um nome e, se você aceitar, vira um protocolo de verdade (plugin `protocolos`).
Com o tempo vocês dois têm uma língua que só existe entre vocês.
"""

from __future__ import annotations

import json
import time
import zlib
from collections import Counter, defaultdict

from plugins._lote2 import P, carregar, guardar, norm, rodar

PLUGIN = P("palavras_secretas", "JARVIS watches which tools you always use together, invents a secret word (protocol name) for that sequence "
           "and turns it into a one-phrase protocol if you accept.",
           "descobrir | aceitar | recusar | minhas",
           "descobrir: look for repeated sequences (last 30 days). aceitar/recusar: nome (the invented word). minhas: accepted words.",
           "nome")

NOMES = ["Pequi", "Impossível", "Vibranium", "Aurora", "Cristal", "Kaiser", "Arco Reator", "Cerrado", "Mark 85", "Nébula",
         "Supernova", "Fênix", "Ônix", "Trovão", "Quasar", "Eclipse", "Goiânia", "Órbita", "Titânio", "Cometa"]
IGNORAR = {"palavras_secretas", "protocolos", "outras_ferramentas", "catalogo", "sonhos", "resumo_do_dia", "autodiagnostico"}
JANELA_S = 15 * 60          # passos com até 15 min entre si contam como uma sequência


def sessoes(chamadas: list[dict]) -> list[list[tuple[str, str, str]]]:
    """Agrupa as chamadas bem-sucedidas em blocos (pausa > 15 min separa). Cada passo: (ferramenta, ação, dia). Pura."""
    blocos, atual, ultimo = [], [], 0.0
    for c in sorted(chamadas, key=lambda c: c["ts"]):
        if not c.get("ok") or c["ferramenta"] in IGNORAR:
            continue
        if atual and c["ts"] - ultimo > JANELA_S:
            blocos.append(atual)
            atual = []
        passo = (c["ferramenta"], c.get("acao") or "", time.strftime("%Y-%m-%d", time.localtime(c["ts"])))
        if not atual or atual[-1][:2] != passo[:2]:              # repetir a mesma coisa seguida não conta
            atual.append(passo)
        ultimo = c["ts"]
    return blocos + ([atual] if atual else [])


def padroes(blocos, min_dias: int = 3) -> list[tuple[tuple, int]]:
    """Sequências de 2 a 4 passos que aparecem em pelo menos 'min_dias' dias diferentes, maiores primeiro. Pura."""
    dias = defaultdict(set)
    for b in blocos:
        for n in (2, 3, 4):
            for i in range(len(b) - n + 1):
                seq = tuple(p[:2] for p in b[i:i + n])
                if len({p[0] for p in seq}) == n:                 # ferramentas diferentes
                    dias[seq].add(b[i][2])
    bons = [(s, len(d)) for s, d in dias.items() if len(d) >= min_dias]
    bons.sort(key=lambda x: (-len(x[0]), -x[1]))
    escolhidos = []
    for s, n in bons:                                             # não sugere um pedaço de algo já sugerido
        if not any(all(p in maior for p in s) for maior, _ in escolhidos):
            escolhidos.append((s, n))
    return escolhidos[:3]


def inventar_nome(seq: tuple, usados: set[str]) -> str:
    i = zlib.crc32(json.dumps(seq).encode())
    for k in range(len(NOMES)):
        nome = NOMES[(i + k) % len(NOMES)]
        if norm(nome) not in usados:
            return nome
    return f"Protocolo {i % 1000}"


def _params_tipicos(chamadas: list[dict], ferramenta: str, acao: str) -> dict:
    vistos = Counter(c.get("params") or "{}" for c in chamadas if c["ferramenta"] == ferramenta and (c.get("acao") or "") == acao)
    try:
        return json.loads(vistos.most_common(1)[0][0]) if vistos else ({"action": acao} if acao else {})
    except ValueError:
        return {"action": acao} if acao else {}


def _go(p, pl):
    a, est = p["action"], carregar("palavras_secretas", {"sugestoes": {}, "aceitas": {}, "recusadas": []})
    if a == "minhas":
        return "\n".join(f"'{n}': {' → '.join(v['descricao'])}" for n, v in est["aceitas"].items()) or "Ainda não temos palavras secretas."
    if a in ("aceitar", "recusar"):
        q = norm(p.get("nome"))
        nome = next((n for n in est["sugestoes"] if q and q in norm(n)), None)
        if not nome:
            return "Não tenho sugestão com esse nome. Diga 'descobrir' primeiro."
        sug = est["sugestoes"].pop(nome)
        if a == "recusar":
            est["recusadas"].append(sug["chave"])
            guardar("palavras_secretas", est)
            return f"Esqueci a palavra '{nome}'."
        from plugins import protocolos
        dados = protocolos._load()
        dados[norm(nome)] = {"mensagem": f"Protocolo {nome} em andamento.", "passos": sug["passos"]}
        protocolos._save(dados)
        est["aceitas"][nome] = sug
        guardar("palavras_secretas", est)
        return f"Pronto. A partir de agora, 'protocolo {nome}' faz: {' → '.join(sug['descricao'])}. É a nossa palavra secreta."
    from core import registro_uso
    chamadas = registro_uso.chamadas(desde=time.time() - 30 * 86400)
    usados = {norm(n) for n in list(est["aceitas"]) + list(est["sugestoes"])}
    novas = []
    for seq, dias in padroes(sessoes(chamadas)):
        chave = json.dumps(seq)
        if chave in est["recusadas"] or any(v["chave"] == chave for v in list(est["aceitas"].values()) + list(est["sugestoes"].values())):
            continue
        nome = inventar_nome(seq, usados)
        usados.add(norm(nome))
        desc = [f"{f}" + (f" ({ac})" if ac else "") for f, ac in seq]
        est["sugestoes"][nome] = {"chave": chave, "dias": dias, "descricao": desc,
                                  "passos": [{"tipo": "ferramenta", "nome": f, "params": _params_tipicos(chamadas, f, ac)} for f, ac in seq]}
        novas.append(f"Em {dias} dias diferentes você pediu: {' → '.join(desc)}. Inventei a palavra '{nome}'.")
    guardar("palavras_secretas", est)
    if not novas:
        return ("Ainda não achei uma sequência que você repete em 3 dias diferentes. Continue usando que eu vou observando."
                if not est["sugestoes"] else "Nada novo. Sugestões esperando resposta: " + ", ".join(est["sugestoes"]) + ".")
    return " ".join(novas) + " Quer que eu crie? Diga 'aceito a palavra' e o nome."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("descobrir aceitar recusar minhas".split(), _go), player, "Palavras secretas")
