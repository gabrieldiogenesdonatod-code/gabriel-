"""
Cofre com condição (3.0): uma mensagem para o seu futuro que só abre quando algo ACONTECER — não
numa data.

    "Jarvis, guarda uma mensagem para quando a loja vender 10 mil no mês: 'Lembra quando era só um
     sonho? Você conseguiu.'"
    "Jarvis, mensagem para quando a minha IA chegar na loss 2."
    "Jarvis, mensagem para quando eu fizer 30 dias seguidos de leitura."

Condições que ele entende: vendas da loja no mês, semana ou dia; loss do treino de IA; dias
seguidos de um hábito; meta do cofrinho batida; km corridos no total; e data. Ele confere sozinho
de hora em hora e avisa quando uma mensagem for desbloqueada.
"""

from __future__ import annotations

import re
import time
from datetime import date

from plugins._lote2 import Colecao, P, carregar, guardar, norm, numeros, rodar

PLUGIN = P("cofre_condicional", "Time capsule that opens on a condition (store sales, ML loss, habit streak, savings goal, km run, date), not a date only.",
           "guardar | listar | checar | abertas",
           "guardar: mensagem, condicao (Portuguese, e.g. 'loja vender 10 mil no mês', 'loss 2', '30 dias seguidos de ler', "
           "'cofrinho PC', '100 km', '01/01/2027'). listar shows conditions and progress (not the messages).",
           "mensagem condicao")


def _valor(t: str) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)*)\s*(mil|k)?\b", t)
    if not m:
        return 0.0
    bruto = m.group(1)
    v = float(bruto.replace(".", "").replace(",", ".")) if re.fullmatch(r"\d{1,3}(\.\d{3})+", bruto) else float(bruto.replace(",", "."))
    return v * 1000 if m.group(2) else v


def entender(texto: str) -> dict | None:
    """Condição em português → dicionário. Pura."""
    t = norm(texto)
    data = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if data:
        d, m, a = (int(x) for x in data.groups())
        return {"tipo": "data", "alvo": date(a + 2000 if a < 100 else a, m, d).isoformat()}
    if "loss" in t or "perda" in t:
        return {"tipo": "loss", "alvo": (numeros(t) or [2])[0]}
    if "vend" in t or "faturar" in t or "faturamento" in t:
        periodo = "semana" if "semana" in t else "dia" if re.search(r"\b(dia|hoje)\b", t) else "mes"
        return {"tipo": "vendas", "periodo": periodo, "alvo": _valor(t)}
    if "seguid" in t or "ofensiva" in t:
        nome = re.sub(r".*?(dias seguidos|ofensiva)\s*(de|do|da)?\s*", "", t).strip() or t
        return {"tipo": "habito", "nome": nome, "alvo": int((numeros(t) or [7])[0])}
    if "cofrinho" in t or "meta de economia" in t or "juntar" in t:
        return {"tipo": "cofrinho", "nome": re.sub(r".*?(cofrinho|meta de economia|juntar)\s*(do|da|de|o|a|para)?\s*", "", t).strip()}
    if re.search(r"\bkm\b|quilometr|correr", t):
        return {"tipo": "km", "alvo": (numeros(t) or [100])[0]}
    return None


def descrever(c: dict) -> str:
    if c["tipo"] == "data":
        return f"no dia {c['alvo'][8:]}/{c['alvo'][5:7]}/{c['alvo'][:4]}"
    if c["tipo"] == "vendas":
        quando = {"mes": "no mês", "semana": "na semana", "dia": "num dia"}[c["periodo"]]
        return f"quando a loja vender R$ {c['alvo']:,.0f} {quando}".replace(",", ".")
    return {"loss": lambda: f"quando a loss do treino chegar a {c['alvo']:g}",
            "habito": lambda: f"com {c['alvo']} dias seguidos de {c['nome']}",
            "cofrinho": lambda: f"quando a meta do cofrinho '{c['nome']}' for batida",
            "km": lambda: f"quando você completar {c['alvo']:g} km corridos"}[c["tipo"]]()


def progresso(c: dict, hoje: date | None = None) -> tuple[bool, str]:
    """(cumpriu, onde está). Lê os dados dos plugins."""
    hoje = hoje or date.today()
    if c["tipo"] == "data":
        return hoje.isoformat() >= c["alvo"], f"faltam {(date.fromisoformat(c['alvo']) - hoje).days} dias"
    if c["tipo"] == "vendas":
        from plugins.sonhos import series
        v = series().get("vendas da loja", {})
        if c["periodo"] == "mes":
            tot = sum(x for d, x in v.items() if d[:7] == hoje.isoformat()[:7])
        elif c["periodo"] == "semana":
            tot = sum(x for d, x in v.items() if 0 <= (hoje - date.fromisoformat(d)).days < 7)
        else:
            tot = v.get(hoje.isoformat(), 0)
        return tot >= c["alvo"], f"R$ {tot:,.0f} de R$ {c['alvo']:,.0f}".replace(",", ".")
    if c["tipo"] == "loss":
        melhores = [min((pt[2] if pt[2] is not None else pt[1]) for pt in t["pontos"]) for t in Colecao("treinos_ia").tudo().values() if t.get("pontos")]
        if not melhores:
            return False, "nenhum treino anotado"
        return min(melhores) <= c["alvo"], f"melhor loss {min(melhores):.3f}"
    if c["tipo"] == "habito":
        from plugins.sequencias import ofensiva
        h = Colecao("sequencias").pegar(c["nome"])
        n = ofensiva(h["dias"], hoje) if h else 0
        return n >= c["alvo"], f"{n} de {c['alvo']} dias seguidos"
    if c["tipo"] == "cofrinho":
        m = Colecao("cofrinho").pegar(c["nome"])
        if not m:
            return False, "meta não encontrada"
        return m["saldo"] >= m["meta"], f"{m['saldo']:.0f} de {m['meta']:.0f}"
    km = sum(x["km"] for x in carregar("corridas", []))
    return km >= c["alvo"], f"{km:.0f} de {c['alvo']:g} km"


def checar(hoje: date | None = None) -> list[dict]:
    cofre, abertas = carregar("cofre_condicional", []), []
    for m in cofre:
        if not m.get("aberta"):
            try:
                ok, _ = progresso(m["condicao"], hoje)
            except Exception:
                ok = False
            if ok:
                m["aberta"] = time.strftime("%Y-%m-%d %H:%M")
                abertas.append(m)
    if abertas:
        guardar("cofre_condicional", cofre)
    return abertas


def anunciar(m: dict) -> str:
    return f"Mensagem guardada em {m['criada']} ({descrever(m['condicao'])}) foi desbloqueada: \"{m['mensagem']}\""


def passo(player) -> None:
    for m in checar():
        from plugins._comum import avisar, mostrar
        mostrar(player, "COFRE DESBLOQUEADO", anunciar(m))
        avisar(player, "Uma mensagem que o senhor guardou para o futuro acabou de abrir. Está no painel.", "COFRE")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("cofre_condicional", lambda: passo(player), a_cada_s=3600, primeira_em_s=420)


def _go(p, pl):
    a, cofre = p["action"], carregar("cofre_condicional", [])
    if a == "guardar":
        msg, c = str(p.get("mensagem") or "").strip(), entender(str(p.get("condicao") or ""))
        if not msg or not c:
            return ("Diga a mensagem e a condição. Entendo: vendas da loja no mês/semana/dia, loss do treino, dias seguidos de "
                    "um hábito, cofrinho, km corridos ou uma data.")
        cofre.append({"mensagem": msg, "condicao": c, "criada": time.strftime("%d/%m/%Y"), "aberta": None})
        guardar("cofre_condicional", cofre)
        return f"Guardado no cofre. Abre {descrever(c)}. Até lá, nem eu leio."
    if a == "listar":
        fechadas = [m for m in cofre if not m.get("aberta")]
        return "\n".join(f"{i}. Abre {descrever(m['condicao'])} — agora: {progresso(m['condicao'])[1]}"
                         for i, m in enumerate(fechadas, 1)) or "O cofre está vazio."
    if a == "abertas":
        return "\n".join(anunciar(m) for m in cofre if m.get("aberta")) or "Nenhuma mensagem foi aberta ainda."
    abertas = checar()
    return "\n".join(anunciar(m) for m in abertas) or "Nenhuma condição foi cumprida ainda."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("guardar listar checar abertas".split(), _go), player, "Cofre")
