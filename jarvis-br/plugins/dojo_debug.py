"""
Dojo de debug (3.0): o JARVIS coloca bugs DE PROPÓSITO numa cópia do seu código para você treinar a
caçar bugs — e marca o tempo.

    "Jarvis, abre um dojo com o arquivo jogo.py, 3 bugs."
    → cria jogo_dojo.py (o seu arquivo original não é tocado) com 3 bugs sutis: < virou <=, == virou
      !=, + 1 virou - 1, and virou or, True virou False…
    "Jarvis, o bug está na linha 42."     "Jarvis, me dá uma dica."     "Jarvis, desisto: mostra."

Cada bug achado conta pontos; quanto mais rápido, melhor. O placar guarda o seu melhor tempo.
"""

from __future__ import annotations

import random
import re
import time
from pathlib import Path

from plugins._lote2 import P, carregar, guardar, num1, rodar

PLUGIN = P("dojo_debug", "Debug dojo: plants N subtle bugs in a copy of your Python file; you hunt them by line number with hints and a best-time score.",
           "novo | chute | dica | revelar | placar",
           "novo: arquivo (.py), bugs (default 3). chute: linha. dica: hint about one remaining bug.",
           "arquivo bugs linha")

TROCAS = [(" <= ", " < "), (" < ", " <= "), (" >= ", " > "), (" > ", " >= "), (" == ", " != "), (" != ", " == "),
          (" + 1", " - 1"), (" - 1", " + 1"), (" and ", " or "), (" or ", " and "), ("True", "False"), ("False", "True"),
          (" is None", " is not None"), (" is not None", " is None"), ("[0]", "[1]"), ("[-1]", "[0]"), (" += ", " -= ")]
DICAS = {" <= ": "uma comparação ficou com um sinal de igual a mais ou a menos", " < ": "uma comparação perdeu ou ganhou o igual",
         " >= ": "uma comparação ficou com um sinal de igual a mais ou a menos", " > ": "uma comparação perdeu ou ganhou o igual",
         " == ": "uma igualdade virou diferença (ou o contrário)", " != ": "uma diferença virou igualdade (ou o contrário)",
         " + 1": "um +1 ou -1 trocou de sinal", " - 1": "um +1 ou -1 trocou de sinal", " and ": "um 'and' e um 'or' trocaram de lugar",
         " or ": "um 'and' e um 'or' trocaram de lugar", "True": "um True/False foi invertido", "False": "um True/False foi invertido",
         " is None": "um teste de None foi invertido", " is not None": "um teste de None foi invertido",
         "[0]": "um índice de lista mudou", "[-1]": "um índice de lista mudou", " += ": "um += virou -="}


def _codigo(linha: str) -> str:
    """A linha sem strings e comentário (para não plantar bug dentro de texto)."""
    sem = re.sub(r"(\"\"\"|''').*?\1|\"[^\"]*\"|'[^']*'", '""', linha)
    return sem.split("#")[0]


def plantar(src: str, n: int, rng=random) -> tuple[str, list[dict]]:
    """Planta até n bugs em linhas diferentes; cada versão continua compilando. Pura (com rng)."""
    linhas = src.splitlines(keepends=True)
    candidatos = [(i, de, para) for i, l in enumerate(linhas) for de, para in TROCAS
                  if de in _codigo(l) and not l.lstrip().startswith(("#", "def ", "class ", "import ", "from ", "@"))]
    rng.shuffle(candidatos)
    bugs, usadas = [], set()
    for i, de, para in candidatos:
        if len(bugs) >= n or i in usadas:
            continue
        original = linhas[i]
        pos = _codigo(original).find(de)
        linhas[i] = original[:pos] + para + original[pos + len(de):]
        try:
            compile("".join(linhas), "<dojo>", "exec")
        except SyntaxError:
            linhas[i] = original
            continue
        usadas.add(i)
        bugs.append({"linha": i + 1, "de": de, "para": para, "achado": None})
    return "".join(linhas), sorted(bugs, key=lambda b: b["linha"])


def _go(p, pl):
    a, d = p["action"], carregar("dojo", {"atual": None, "placar": []})
    if a == "placar":
        pl_ = sorted(d["placar"], key=lambda x: x["segundos"] / max(1, x["bugs"]))[:5]
        return "\n".join(f"{x['arquivo']}: {x['bugs']} bug(s) em {x['segundos'] // 60:.0f}min{x['segundos'] % 60:02.0f}s" for x in pl_) \
            or "Nenhum dojo completo ainda."
    if a == "novo":
        arq = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser()
        if not arq.is_file() or arq.suffix != ".py":
            return "Me diga um arquivo .py que exista."
        novo, bugs = plantar(arq.read_text(encoding="utf-8", errors="ignore"), max(1, min(10, int(num1(p, "bugs", 3)))))
        if not bugs:
            return "Esse arquivo não tem lugares bons para esconder bugs (comparações, +1, and/or…). Tente outro maior."
        destino = arq.with_name(arq.stem + "_dojo.py")
        destino.write_text(novo, encoding="utf-8")
        d["atual"] = {"arquivo": str(destino), "bugs": bugs, "inicio": time.time(), "dicas": 0}
        guardar("dojo", d)
        return f"Dojo pronto: {destino.name} tem {len(bugs)} bug(s) escondido(s). O original não foi tocado. Valendo! Diga a linha quando achar."
    at = d.get("atual")
    if not at:
        return "Nenhum dojo aberto. Diga 'novo' com um arquivo .py."
    faltam = [b for b in at["bugs"] if not b["achado"]]
    if a == "dica":
        at["dicas"] += 1
        guardar("dojo", d)
        b = faltam[0]
        return f"Dica: {DICAS.get(b['de'], 'algo mudou')}, entre as linhas {max(1, b['linha'] - 5)} e {b['linha'] + 5}."
    if a == "revelar":
        d["atual"] = None
        guardar("dojo", d)
        return "Os bugs eram: " + "; ".join(f"linha {b['linha']}: '{b['de'].strip()}' virou '{b['para'].strip()}'" for b in at["bugs"]) + "."
    chute = int(num1(p, "linha"))
    b = next((x for x in faltam if x["linha"] == chute), None)
    if not b:
        perto = any(abs(x["linha"] - chute) <= 3 for x in faltam)
        return "Não é aí." + (" Mas está quente!" if perto else "")
    b["achado"] = time.time()
    resto = len(faltam) - 1
    if resto:
        guardar("dojo", d)
        return f"Achou! Linha {chute}: '{b['de'].strip()}' tinha virado '{b['para'].strip()}'. Faltam {resto}."
    seg = time.time() - at["inicio"]
    d["placar"].append({"arquivo": Path(at["arquivo"]).name, "bugs": len(at["bugs"]), "segundos": seg, "dicas": at["dicas"]})
    d["atual"] = None
    guardar("dojo", d)
    return f"Todos os {len(at['bugs'])} bugs achados em {seg // 60:.0f} min {seg % 60:02.0f} s" + (f" com {at['dicas']} dica(s)" if at["dicas"] else "") + ". Mestre do debug! 🥋"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("novo chute dica revelar placar".split(), _go), player, "Dojo")
