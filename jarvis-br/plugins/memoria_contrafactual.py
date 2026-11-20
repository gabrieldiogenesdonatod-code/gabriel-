"""
Memória contrafactual — ideia 9 (fork PT-BR 1.4).

Depois de cada tarefa, o JARVIS se pergunta: "e se eu tivesse feito de outro
jeito?" — e guarda a LIÇÃO, não só o que aconteceu.

O QUE ELE ANALISA (no diário de uso, core/registro_uso.py)
    • Protocolos e cadeias com passos independentes feitos em fila (abrir,
      sites, fechar). Com os tempos medidos de cada passo ele calcula quanto
      teria levado em PARALELO: "o protocolo trabalho levou 14 s; em paralelo
      teria levado 6 s". 'aplicar' liga o modo paralelo naquele protocolo.
    • Falha seguida de sucesso na MESMA ferramenta com parâmetros diferentes
      ("vscode" falhou, "Visual Studio Code" funcionou): vira lição e, quando
      é um app, 'aplicar' cria o apelido para da próxima vez acertar de
      primeira.
    • Passos de protocolo que falham sempre: sugere tirar.
    • Ferramenta que foi chamada várias vezes seguidas com o mesmo pedido
      (sinal de que a primeira resposta não serviu).

    "Jarvis, o que você aprendeu com as últimas tarefas?"
    "Jarvis, e se o protocolo trabalho rodasse em paralelo?"
    "Jarvis, aplica a lição 3"

As lições ficam em memory/contrafactual.json.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "memoria_contrafactual",
    "brief": "Lessons from past tasks: what would have been faster or would have worked.",
    "description": (
        "Counterfactual memory: analyses recent tasks and tool calls and stores lessons (steps that "
        "could run in parallel and the time saved, failures that worked with other parameters, steps "
        "that always fail, repeated retries). action='analisar' (find new lessons), 'licoes' (list "
        "them; 'what did you learn'), 'aplicar' with id (apply: parallel mode for a protocol or an app "
        "alias), 'e_se' with nome (estimate a protocol run in parallel), 'esquecer' with id."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "analisar | licoes | aplicar | e_se | esquecer"},
            "id": {"type": "STRING"}, "nome": {"type": "STRING"},
        },
        "required": [],
    },
}

_ARQ = MEMORIA / "contrafactual.json"
_PARALELIZAVEIS = ("abrir", "site", "fechar")


def _id(*partes) -> str:
    return hashlib.sha1("|".join(map(str, partes)).encode()).hexdigest()[:5]


# ── análise (pura) ─────────────────────────────────────────────────────────────
def tempo_paralelo(passos: list[dict]) -> tuple[float, float]:
    """(tempo em fila, tempo estimado em paralelo) em segundos, a partir dos
    tempos medidos. Blocos seguidos de passos paralelizáveis contam pelo maior."""
    fila = sum(p.get("ms", 0) for p in passos) / 1000
    paralelo, bloco = 0.0, []
    for p in passos + [{"tipo": "_fim", "ms": 0}]:
        tipo = p.get("tipo") or p.get("descricao", "").split(" ")[0]
        if tipo in _PARALELIZAVEIS:
            bloco.append(p.get("ms", 0))
            continue
        if bloco:
            paralelo += max(bloco) / 1000
            bloco = []
        paralelo += p.get("ms", 0) / 1000
    return round(fila, 2), round(paralelo, 2)


def licoes_de_tarefas(tarefas: list[dict], minimo_s: float = 3.0) -> list[dict]:
    saida = []
    por_nome = defaultdict(list)
    for t in tarefas:
        por_nome[(t["tipo"], t["nome"])].append(t)
    for (tipo, nome), ts in por_nome.items():
        ultima = ts[-1]
        passos = ultima.get("passos") or []
        fila, par = tempo_paralelo(passos) if tipo == "protocolo" else (0.0, 0.0)
        if fila - par >= minimo_s:
            saida.append({"id": _id("par", tipo, nome), "tipo": "paralelizar", "alvo": nome, "origem": tipo,
                          "economia_s": round(fila - par, 1),
                          "texto": f"O {tipo} '{nome}' levou {fila:.1f} s; com os passos independentes em "
                                   f"paralelo teria levado cerca de {par:.1f} s."})
        # passo que falha em todas as execuções recentes
        if len(ts) >= 2:
            recentes = ts[-3:]
            descricoes = [{p["descricao"] for p in (t.get("passos") or []) if not p.get("ok")} for t in recentes]
            sempre = set.intersection(*descricoes) if descricoes else set()
            for d in sempre:
                saida.append({"id": _id("falha", nome, d), "tipo": "passo_falha", "alvo": nome,
                              "texto": f"No {tipo} '{nome}', o passo '{d}' falhou nas últimas {len(recentes)} vezes. "
                                       f"Talvez valha tirar ou corrigir esse passo."})
    return saida


def _params(c: dict) -> dict:
    try:
        return json.loads(c.get("params") or "{}")
    except Exception:
        return {}


_CAMPOS_ALVO = ("alvo", "app_name", "nome", "query", "termo", "city")


def licoes_de_chamadas(chamadas: list[dict], janela_s: float = 120) -> list[dict]:
    saida = []
    for i, c in enumerate(chamadas):
        if c.get("ok"):
            continue
        pc = _params(c)
        for d in chamadas[i + 1:i + 6]:
            if d["ts"] - c["ts"] > janela_s:
                break
            if d["ferramenta"] != c["ferramenta"] or not d.get("ok") or (d.get("acao") or "") != (c.get("acao") or ""):
                continue
            pd = _params(d)
            mudou = {k: (pc.get(k), pd.get(k)) for k in set(pc) | set(pd) if pc.get(k) != pd.get(k)}
            if not mudou:
                continue
            campo = next((k for k in _CAMPOS_ALVO if k in mudou), next(iter(mudou)))
            antes, depois = mudou[campo]
            licao = {"id": _id("troca", c["ferramenta"], antes, depois), "tipo": "parametro",
                     "ferramenta": c["ferramenta"], "campo": campo, "antes": antes, "depois": depois,
                     "texto": f"{c['ferramenta']} falhou com {campo}='{antes}' e funcionou com '{depois}'."}
            if campo in ("alvo", "app_name") and c["ferramenta"] in ("open_app", "controle_pc"):
                licao["texto"] += f" Posso criar o apelido '{antes}' → '{depois}' para acertar de primeira."
                licao["aplicavel"] = "apelido"
            saida.append(licao)
            break
    # mesma chamada repetida em sequência (a primeira resposta não serviu)
    seguidas = 1
    for a, b in zip(chamadas, chamadas[1:]):
        if a["ferramenta"] == b["ferramenta"] and a.get("params") == b.get("params") and b["ts"] - a["ts"] < 60:
            seguidas += 1
            if seguidas == 3:
                saida.append({"id": _id("rep", b["ferramenta"], b.get("params")), "tipo": "repeticao",
                              "ferramenta": b["ferramenta"],
                              "texto": f"{b['ferramenta']} foi chamada 3 vezes seguidas com o mesmo pedido: a "
                                       f"resposta não estava servindo."})
        else:
            seguidas = 1
    return saida


# ── armazenamento ──────────────────────────────────────────────────────────────
def carregar() -> list[dict]:
    d = ler_json(_ARQ, [])
    return d if isinstance(d, list) else []


def analisar(dias: float = 7) -> list[dict]:
    from core import registro_uso
    desde = time.time() - dias * 86400
    novas = licoes_de_tarefas(registro_uso.tarefas(desde)) + licoes_de_chamadas(registro_uso.chamadas(desde))
    atuais = carregar()
    por_id = {l["id"]: l for l in atuais}
    adicionadas = []
    for l in novas:
        if l["id"] in por_id:
            velho = por_id[l["id"]]
            velho["vezes"] = velho.get("vezes", 1) + (0 if velho.get("texto") == l["texto"] else 1)
            velho.update({k: v for k, v in l.items() if k not in ("aplicada", "criada", "vezes")})
            continue
        l.update(criada=time.strftime("%Y-%m-%d %H:%M"), aplicada=False, vezes=1)
        atuais.append(l)
        adicionadas.append(l)
    gravar_json(_ARQ, atuais[-200:])
    try:                         # lição também vira memória (com esquecimento inteligente)
        from plugins import memoria_inteligente
        for l in adicionadas[:5]:
            memoria_inteligente.lembrar(f"lição: {l['texto']}", "experiencia", "observado")
    except Exception:
        pass
    return adicionadas


def aplicar(ident: str) -> str:
    licoes = carregar()
    l = next((x for x in licoes if x["id"] == ident), None)
    if not l:
        return f"Não tenho a lição {ident}."
    if l["tipo"] == "paralelizar" and l.get("origem") == "protocolo":
        from plugins import protocolos
        dados = protocolos._load()
        if not isinstance(dados, dict) or l["alvo"] not in dados:
            return f"Não achei o protocolo {l['alvo']}."
        dados[l["alvo"]]["paralelo"] = True
        protocolos._save(dados)
        msg = f"Pronto: o protocolo {l['alvo']} agora abre e fecha as coisas em paralelo."
    elif l.get("aplicavel") == "apelido":
        from plugins import _indice_apps
        msg = _indice_apps.definir_apelido(str(l["antes"]), str(l["depois"]))
    else:
        return "Essa lição é só um aviso; não há o que aplicar automaticamente."
    l["aplicada"] = True
    gravar_json(_ARQ, licoes)
    return msg


def e_se(nome: str) -> str:
    from core import registro_uso
    ts = [t for t in registro_uso.tarefas(time.time() - 60 * 86400) if t["nome"].lower() == nome.lower()]
    if not ts:
        return f"Ainda não tenho medições do '{nome}'. Rode ele uma vez e eu calculo."
    fila, par = tempo_paralelo(ts[-1].get("passos") or [])
    if fila - par < 0.5:
        return f"O '{nome}' levou {fila:.1f} s e quase não ganharia nada em paralelo."
    return (f"Na última vez o '{nome}' levou {fila:.1f} s. Com os passos independentes em paralelo, teria "
            f"levado cerca de {par:.1f} s, {fila - par:.1f} s a menos.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "licoes").lower()
    try:
        if acao == "analisar":
            novas = analisar()
            if not novas:
                return "Analisei as tarefas recentes e não encontrei lição nova."
            return f"{len(novas)} lição(ões) nova(s). Por exemplo: {novas[0]['texto']}"
        if acao == "aplicar":
            return aplicar(str(p.get("id") or "").strip())
        if acao == "e_se":
            return e_se(str(p.get("nome") or "").strip())
        if acao == "esquecer":
            licoes = carregar()
            restantes = [l for l in licoes if l["id"] != str(p.get("id") or "").strip()]
            gravar_json(_ARQ, restantes)
            return "Esqueci essa lição." if len(restantes) < len(licoes) else "Não achei essa lição."
        analisar()
        licoes = [l for l in carregar() if not l.get("aplicada")]
        if not licoes:
            return "Ainda não tenho lições guardadas."
        mostrar(player, "LIÇÕES (MEMÓRIA CONTRAFACTUAL)",
                "\n\n".join(f"[{l['id']}] {l['texto']}" + (f"\n   economia: {l['economia_s']} s" if l.get("economia_s") else "")
                            for l in licoes[-15:]))
        top = max(licoes, key=lambda l: l.get("economia_s", 0))
        return f"Tenho {len(licoes)} lição(ões). A mais útil: {top['texto']} Diga 'aplica a lição {top['id']}' se quiser."
    except Exception as e:
        return f"A memória contrafactual falhou: {e}"
