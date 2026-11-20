"""
Caçador de promessas (3.0): quando você diz "amanhã eu mando o orçamento para a Ana", o JARVIS
anota a promessa e cobra no dia.

Ele lê o que você fala com ele (o registro "Você: …") e reconhece frases de compromisso: "vou
mandar", "te passo", "fico de entregar", "prometo pagar"… com o prazo ("amanhã", "sexta", "dia
20", "semana que vem"). Também dá para anotar direto: "Jarvis, anota a promessa: pagar a Bia na
sexta". No dia do prazo, de manhã, ele lembra.
"""

from __future__ import annotations

import re
import time
from datetime import date, timedelta

from plugins._lote2 import P, carregar, guardar, norm, numeros, rodar

PLUGIN = P("cacador_promessas", "Promise hunter: detects commitments you say ('amanhã eu mando o orçamento para a Ana') with their deadline, "
           "reminds you on the day; also add promises by hand, list, mark done.",
           "anotar | listar | cumpri | esquecer | varrer",
           "anotar: texto (the promise with deadline). cumpri/esquecer: numero or texto. varrer: scan recent speech now.",
           "texto numero")

VERBOS = (r"mandar|enviar|entregar|pagar|ligar|responder|passar|fazer|terminar|devolver|levar|buscar|comprar|montar|arrumar|"
          r"consertar|mando|envio|entrego|pago|ligo|respondo|passo|faco|termino|devolvo|levo|busco|compro|monto|arrumo|conserto|"
          r"resolvo|resolver|marco|marcar|visito|visitar|ajudo|ajudar")
GATILHO = re.compile(r"\b(vou|irei|prometo|fico de|pode deixar que eu|deixa que eu|amanha eu|hoje eu|eu)\s+(te |lhe |pra (?:voce|ele|ela) )?"
                     rf"({VERBOS})\b")
SEMANA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def prazo(texto: str, ref: date) -> date:
    """Data do compromisso pela frase (sem prazo dito: depois de amanhã). Pura."""
    t = norm(texto)
    if "depois de amanha" in t:
        return ref + timedelta(2)
    if "amanha" in t:
        return ref + timedelta(1)
    if re.search(r"\b(hoje|mais tarde|agora a noite|daqui a pouco)\b", t):
        return ref
    if "semana que vem" in t or "proxima semana" in t:
        return ref + timedelta(7 - ref.weekday())
    if "fim de semana" in t or "final de semana" in t:
        return ref + timedelta((5 - ref.weekday()) % 7)
    for i, d in enumerate(SEMANA):
        if re.search(rf"\b{d}(-feira)?\b", t):
            return ref + timedelta((i - ref.weekday()) % 7 or 7)
    m = re.search(r"\bdia (\d{1,2})\b", t)
    if m and 1 <= int(m.group(1)) <= 31:
        dia = int(m.group(1))
        for k in range(3):                                  # este mês ou os próximos (dia 31 pula meses curtos)
            mes, ano = (ref.month - 1 + k) % 12 + 1, ref.year + (ref.month - 1 + k) // 12
            try:
                alvo = date(ano, mes, dia)
            except ValueError:
                continue
            if alvo >= ref:
                return alvo
    return ref + timedelta(2)


def eh_promessa(frase: str) -> bool:
    t = norm(frase).strip()
    if not t or t.endswith("?") or t.startswith(("se ", "quando ", "sera que")):
        return False
    return bool(GATILHO.search(t))


def _limpar(frase: str) -> str:
    return re.sub(r"^\s*(jarvis|ei jarvis|ok jarvis)[,!.]?\s*", "", frase.strip(), flags=re.I)[:160]


def adicionar(lista: list[dict], frase: str, ref: date, fonte: str) -> dict | None:
    txt = _limpar(frase)
    if any(norm(x["texto"]) == norm(txt) for x in lista):
        return None
    p = {"texto": txt, "prazo": prazo(txt, ref).isoformat(), "criada": ref.isoformat(), "fonte": fonte, "feita": False}
    lista.append(p)
    return p


def varrer(desde: float, ref: date | None = None) -> list[dict]:
    from core import registro_uso
    ref, lista, novas = ref or date.today(), carregar("promessas", []), []
    for l in registro_uso.linhas_registro(desde=desde):
        linha = str(l["linha"])
        if linha.startswith("Você: ") and eh_promessa(linha[6:]):
            p = adicionar(lista, linha[6:], ref, "conversa")
            if p:
                novas.append(p)
    guardar("promessas", lista[-300:])
    return novas


def _abertas(lista):
    return [p for p in lista if not p["feita"]]


def passo(player) -> None:
    est = carregar("promessas_estado", {"lido_ate": time.time() - 3600, "lembrado": ""})
    varrer(est["lido_ate"])
    est["lido_ate"] = time.time()
    hoje = date.today().isoformat()
    if est.get("lembrado") != hoje and 8 <= time.localtime().tm_hour < 20:
        do_dia = [p for p in _abertas(carregar("promessas", [])) if p["prazo"] <= hoje]
        if do_dia:
            from plugins._comum import avisar
            avisar(player, "Promessas para hoje: " + "; ".join(p["texto"] for p in do_dia[:4]) + ".", "PROMESSAS")
        est["lembrado"] = hoje
    guardar("promessas_estado", est)


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("cacador_promessas", lambda: passo(player), a_cada_s=1800, primeira_em_s=300)


def _go(p, pl):
    a, lista = p["action"], carregar("promessas", [])
    if a == "anotar":
        nova = adicionar(lista, str(p.get("texto") or ""), date.today(), "anotada")
        guardar("promessas", lista)
        return f"Promessa anotada para {nova['prazo'][8:]}/{nova['prazo'][5:7]}: {nova['texto']}." if nova else "Essa já estava anotada."
    if a == "varrer":
        novas = varrer(time.time() - 24 * 3600)
        return ("Achei: " + "; ".join(f"{x['texto']} (até {x['prazo'][8:]}/{x['prazo'][5:7]})" for x in novas)) if novas else \
            "Não achei promessa nova nas últimas 24 horas."
    abertas = _abertas(lista)
    if a == "listar":
        return "\n".join(f"{i}. {x['texto']} — até {x['prazo'][8:]}/{x['prazo'][5:7]}" + (" (ATRASADA)" if x["prazo"] < date.today().isoformat() else "")
                         for i, x in enumerate(abertas, 1)) or "Nenhuma promessa em aberto."
    n = numeros(p.get("numero"))
    alvo = abertas[int(n[0]) - 1] if n and 0 < n[0] <= len(abertas) else next(
        (x for x in abertas if norm(p.get("texto")) and norm(p.get("texto")) in norm(x["texto"])), None)
    if not alvo:
        return "Não achei essa promessa. Diga o número da lista."
    if a == "cumpri":
        alvo["feita"] = date.today().isoformat()
    else:
        lista.remove(alvo)
    guardar("promessas", lista)
    return "Promessa cumprida. Palavra é palavra! 🤝" if a == "cumpri" else "Esqueci essa promessa."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("anotar listar cumpri esquecer varrer".split(), _go), player, "Promessas")
