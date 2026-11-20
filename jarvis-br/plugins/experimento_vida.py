"""
Experimentos na sua vida (3.6): o JARVIS vira o cientista dos SEUS hábitos e da SUA loja — e descobre
CAUSA de verdade, não coincidência.

Os sonhos do JARVIS acham padrões ("nos dias com mais água você trabalha mais"). Mas padrão não é causa:
talvez nos dias bons você beba mais água E trabalhe mais. O único jeito de saber é o da ciência: SORTEAR.

    "Jarvis, cria um experimento: postar no status da loja, medindo as vendas, por 14 dias"
    "Jarvis, cria um experimento: treinar de manhã, medindo o tempo de estudo"
    "Jarvis, cria um experimento: dormir antes das 23h, com nota de 0 a 10"     (você dá a nota do dia)
    "Jarvis, qual o experimento de hoje?"         → "hoje é dia COM: poste no status" / "hoje é dia SEM"
    "Jarvis, nota 8 hoje"      "Jarvis, hoje eu não segui o sorteio"
    "Jarvis, resultado do experimento"            "Jarvis, que experimentos você sugere?"

Como funciona (é o mesmo método de um teste de remédio, com uma pessoa só: você):
  1. Ele sorteia, para cada dia, COM ou SEM — equilibrado dentro de cada dia da semana (uma segunda
     COM, outra SEM), para o sábado forte da loja não enganar a conta.
  2. O plano é selado no livro-razão ANTES de os dados chegarem (não dá para "ajeitar" depois).
  3. Os números vêm sozinhos do que o JARVIS já acompanha (caixa, água, estudo, corrida, treino,
     hábitos, ponto) — ou da nota que você dá.
  4. No fim ele compara os dias COM e SEM e pergunta ao acaso: "embaralhando o sorteio milhares de
     vezes, quantas dão uma diferença desse tamanho?" (teste de re-randomização). Se quase nunca, é efeito.

Honesto: vale para VOCÊ (não para todo mundo); precisa de 8 dias no mínimo (14 ou 28 é melhor); efeito
pequeno pode passar despercebido, e ele diz o tamanho do que conseguiria enxergar. A análise segue o
sorteio mesmo nos dias que você não cumpriu — é o jeito que não engana.
"""

from __future__ import annotations

import hashlib
import json
import random
import statistics as st
import time
from datetime import date, datetime, timedelta

from plugins._lote2 import P, carregar, guardar, norm, num1, reais, rodar

PLUGIN = P("experimento_vida", "Randomized self-experiments on the user's LIFE (habits, store, study — not code): daily COM/SEM draw, "
                               "automatic data, honest statistics.",
           "criar | hoje | cumpri | nota | resultado | listar | encerrar | sugerir",
           "criar: tratamento (what the user does on COM days), medida (tracked series: vendas, agua, estudo, km, treino, horas "
           "trabalhadas, a habit name — or 'nota' for a 0-10 daily rating), dias (default 14, min 8), atraso (1 = effect measured "
           "the next day), nome (optional label). hoje: today's draw. cumpri: valor (sim | nao). nota: valor (0-10). resultado / "
           "encerrar: experimento (number or name). sugerir: experiments worth running, from patterns found in the user's data.",
           "tratamento medida dias atraso nome experimento valor")

MIN_DIAS, MAX_DIAS, MIN_GRUPO = 8, 60, 3
VOLTAS = 4000
ANALISE = "diferença das médias COM − SEM; re-randomização dentro dos estratos do sorteio; por sorteio (intenção de tratar)"
SINONIMOS = {"vend": "vendas da loja", "loja": "vendas da loja", "caixa": "vendas da loja", "agua": "água bebida",
             "estud": "tempo de estudo", "corr": "km corridos", "km": "km corridos", "trein": "volume de treino",
             "trabalh": "horas trabalhadas", "foco": "tempo em modos de foco"}


# ─────────────────────────────────────────────────────────── sorteio (puras) ───
def estratos(inicio: date, dias: int) -> list[list[str]]:
    """Os grupos dentro dos quais o sorteio é equilibrado: os pares de cada dia da semana e, por último,
    os dias que sobraram sem par. Pura."""
    por_dia: dict[int, list[date]] = {}
    for k in range(dias):
        d = inicio + timedelta(k)
        por_dia.setdefault(d.weekday(), []).append(d)
    grupos, sobra = [], []
    for wd in sorted(por_dia):
        ds = por_dia[wd]
        par = len(ds) - len(ds) % 2
        if par:
            grupos.append([d.isoformat() for d in ds[:par]])
        sobra += ds[par:]
    if sobra:
        grupos.append([d.isoformat() for d in sorted(sobra)])
    return grupos


def sortear(inicio: date, dias: int, rng: random.Random) -> dict[str, str]:
    """{dia: 'com' | 'sem'}, metade de cada dentro de cada estrato. Pura (com rng)."""
    plano = {}
    for g in estratos(inicio, dias):
        rot = ["com", "sem"] * (len(g) // 2)
        if len(g) % 2:
            rot.append(rng.choice(["com", "sem"]))
        rng.shuffle(rot)
        plano.update(zip(g, rot))
    return dict(sorted(plano.items()))


# ─────────────────────────────────────────────────────────── análise (puras) ───
def diferenca(plano: dict[str, str], valores: dict[str, float]) -> tuple[float, list[float], list[float]] | None:
    com = [valores[d] for d, r in plano.items() if r == "com" and d in valores]
    sem = [valores[d] for d, r in plano.items() if r == "sem" and d in valores]
    if len(com) < MIN_GRUPO or len(sem) < MIN_GRUPO:
        return None
    return st.mean(com) - st.mean(sem), com, sem


def analisar(plano: dict[str, str], valores: dict[str, float], grupos: list[list[str]], rng: random.Random,
             voltas: int = VOLTAS) -> dict | None:
    """Efeito e a chance de ele ser sorte. None se ainda não há 3 dias COM e 3 SEM com dado. Pura (com rng)."""
    obs = diferenca(plano, valores)
    if obs is None:
        return None
    d_obs, com, sem = obs
    rotulos = [[plano[d] for d in g] for g in grupos]
    extremos, falsas = 0, []
    for _ in range(voltas):
        falso = {}
        for g, rot in zip(grupos, rotulos):
            r = rot[:]
            rng.shuffle(r)
            falso.update(zip(g, r))
        x = diferenca(falso, valores)
        if x is not None:
            falsas.append(abs(x[0]))
            if abs(x[0]) >= abs(d_obs) - 1e-12:
                extremos += 1
    p = (extremos + 1) / (voltas + 1)
    falsas.sort()
    critico = falsas[int(0.95 * (len(falsas) - 1))] if falsas else 0.0        # o tamanho que o acaso sozinho alcança em 5% das vezes
    mde = 1.43 * critico                                                      # efeito que eu veria 8 em cada 10 vezes (2,8 / 1,96)
    m_sem = st.mean(sem)
    return {"diferenca": d_obs, "pct": (d_obs / m_sem * 100) if m_sem else None, "p": p, "com": st.mean(com), "sem": m_sem,
            "n_com": len(com), "n_sem": len(sem), "faixa": (d_obs - critico, d_obs + critico),
            "enxergaria": mde, "enxergaria_pct": (mde / abs(m_sem) * 100) if m_sem else None}


def fmt(medida: str, v: float) -> str:
    if medida == "vendas da loja":
        return reais(v)
    if medida == "nota":
        return f"{v:.1f}".replace(".", ",")
    if medida.startswith("hábito"):
        return f"{v:.0%} dos dias"
    un = {"água bebida": "ml", "km corridos": "km", "volume de treino": "kg", "horas trabalhadas": "h",
          "tempo de estudo": "min"}.get(medida, "min" if medida.startswith("tempo") else "")
    casas = 0 if abs(v) >= 100 or un in ("ml", "min", "kg") else 1
    return (f"{v:.{casas}f}".replace(".", ",") + f" {un}").strip()


def veredito(r: dict, medida: str, tratamento: str, final: bool = True) -> str:
    """O resultado em português, com o tamanho da certeza. Pura."""
    pct = (f"{r['pct']:+.0f}%" if abs(r["pct"]) >= 0.5 else "0%") if r["pct"] is not None else f"{r['diferenca']:+.2f}"
    base = (f"Dias COM ({r['n_com']}): média {fmt(medida, r['com'])}. Dias SEM ({r['n_sem']}): média {fmt(medida, r['sem'])}. "
            f"Diferença: {pct}.")
    sorte = f"a chance de uma diferença dessas aparecer só por sorte é de {max(r['p'], 0.0005):.1%}".replace(".", ",")
    if r["p"] <= 0.05:
        sentido = "AUMENTA" if r["diferenca"] > 0 else "DIMINUI"
        alvo = "a sua nota do dia" if medida == "nota" else medida
        concl = f"Conclusão: \"{tratamento}\" {sentido} {alvo} para você ({sorte})."
    elif r["p"] <= 0.20:
        concl = (f"Conclusão: sinal fraco ({sorte}). Pode ser efeito, pode ser acaso"
                 + (": repita por mais 14 dias para tirar a dúvida." if final else "; ainda é cedo."))
    else:
        ver = (f" Com esses dias eu só enxergaria um efeito maior que {r['enxergaria_pct']:.0f}%."
               if r["enxergaria_pct"] is not None and r["enxergaria_pct"] < 500 else "")
        concl = f"Conclusão: não achei diferença que não possa ser acaso ({sorte}).{ver}"
    return f"{base} {concl}" + ("" if final else " Resultado PARCIAL: olhar antes da hora engana; o que vale é o do fim.")


# ─────────────────────────────────────────────────────────── dados ───
def _series() -> dict[str, dict[str, float]]:
    try:
        from plugins.eu_do_futuro import _series as todas
        return todas()
    except Exception as e:
        print(f"[Experimento] séries: {e}")
        return {}


def achar_serie(pedido: str, nomes: list[str]) -> str | None:
    """A série acompanhada que o pedido quer ('vendas', 'estudo', 'ler'…). Pura."""
    q = norm(pedido)
    if not q:
        return None
    for raiz, alvo in SINONIMOS.items():
        if raiz in q and alvo in nomes:
            return alvo
    return next((n for n in nomes if q in norm(n) or norm(n) in q), None)


def valores_de(exp: dict, series: dict, hoje: date) -> dict[str, float]:
    """{dia sorteado: valor medido}. Dia de hoje não entra (o total ainda está incompleto), salvo nota. Pura."""
    if exp["medida"] == "nota":
        return {d: float(v) for d, v in exp.get("notas", {}).items() if d in exp["plano"]}
    serie, atraso, out = series.get(exp["medida"], {}), int(exp.get("atraso", 0)), {}
    for d in exp["plano"]:
        dia = date.fromisoformat(d) + timedelta(atraso)
        if dia < hoje and dia.isoformat() in serie:
            out[d] = float(serie[dia.isoformat()])
    return out


def _est() -> dict:
    return carregar("experimento_vida", {"seq": 0, "experimentos": []})


def _achar(est: dict, pedido, so_ativos: bool = False) -> dict | None:
    exps = [e for e in est["experimentos"] if not so_ativos or e["estado"] == "ativo"]
    q = norm(pedido)
    if q:
        num = int(num1({"x": q}, "x", 0))
        por_num = next((e for e in exps if e["id"] == num), None) if num else None
        return por_num or next((e for e in reversed(exps) if q in norm(e["nome"]) or q in norm(e["tratamento"])), None)
    ativos = [e for e in exps if e["estado"] == "ativo"]
    return ativos[-1] if ativos else (exps[-1] if exps else None)


def calcular(exp: dict, hoje: date | None = None) -> dict | None:
    hoje = hoje or date.today()
    ini = date.fromisoformat(exp["inicio"])
    rng = random.Random(int(exp.get("semente", 0)) + 7919)            # mesma conta toda vez que você pedir
    return analisar(exp["plano"], valores_de(exp, _series(), hoje), estratos(ini, exp["dias"]), rng)


def _fechar(exp: dict, hoje: date | None = None) -> str:
    r = calcular(exp, hoje)
    exp["estado"] = "encerrado"
    exp["fim_real"] = (hoje or date.today()).isoformat()
    if r is None:
        exp["resultado"] = None
        return (f"Experimento #{exp['id']} ({exp['nome']}) encerrado sem conclusão: preciso de pelo menos {MIN_GRUPO} dias COM e "
                f"{MIN_GRUPO} dias SEM com dado.")
    exp["resultado"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()}
    texto = veredito(r, exp["medida"], exp["tratamento"])
    try:
        from core import livro_razao
        livro_razao.registrar("experimento.resultado", {"id": exp["id"], "nome": exp["nome"], "p": round(r["p"], 4),
                                                        "diferenca": round(r["diferenca"], 4), "n_com": r["n_com"], "n_sem": r["n_sem"]})
    except Exception:
        pass
    if r["p"] <= 0.05:
        try:
            from plugins import memoria_inteligente
            memoria_inteligente.lembrar(f"Experimento sorteado ({r['n_com'] + r['n_sem']} dias): {texto.split('Conclusão: ')[-1]}",
                                        "experiencia", "observado")
        except Exception:
            pass
    return f"Experimento #{exp['id']} ({exp['nome']}) terminou. {texto}"


def frase_do_dia(exp: dict, dia: str) -> str:
    cond = exp["plano"].get(dia)
    if not cond:
        return ""
    return (f"Experimento #{exp['id']} ({exp['nome']}): hoje é dia COM. Faça: {exp['tratamento']}." if cond == "com" else
            f"Experimento #{exp['id']} ({exp['nome']}): hoje é dia SEM. Hoje NÃO: {exp['tratamento']}.")


# ─────────────────────────────────────────────────────────── sugestões ───
def tratamento_de(nome: str, serie: dict[str, float]) -> str | None:
    """Como transformar uma série que você CONTROLA num 'faça isso nos dias COM'. Pura."""
    vals = sorted(serie.values())
    alto = vals[int(0.75 * (len(vals) - 1))] if vals else 0
    if nome == "água bebida":
        return f"beber pelo menos {max(500, round(alto / 100) * 100):.0f} ml de água"
    if nome == "km corridos":
        return "correr"
    if nome == "volume de treino":
        return "treinar"
    if nome == "tempo de estudo":
        return f"estudar pelo menos {max(20, round(alto / 5) * 5):.0f} minutos"
    if nome.startswith("tempo em modos"):
        return "ligar um modo de foco por pelo menos 25 minutos"
    if nome.startswith("hábito "):
        return f"cumprir o hábito '{nome[7:]}'"
    return None                                     # vendas e horas trabalhadas não são alavanca direta


def descobertas(series: dict | None = None, n: int = 3) -> list[dict]:
    """Padrões que os sonhos acham e que DÁ para testar (a causa é algo que você controla)."""
    series = series if series is not None else _series()
    try:
        from plugins.sonhos import cruzar
    except Exception:
        return []
    out = []
    for a in sorted(series):
        trat = tratamento_de(a, series[a])
        if not trat:
            continue
        for b in sorted(series):
            if a == b:
                continue
            for atraso in (0, 1):
                try:
                    achado = cruzar(a, series[a], b, series[b], atraso)
                except Exception:
                    achado = []
                for c in achado:
                    out.append({"forca": c[0], "texto": c[1], "causa": a, "efeito": b, "atraso": atraso, "tratamento": trat})
    out.sort(key=lambda x: -x["forca"])
    vistos, unicos = set(), []
    for x in out:
        if (x["causa"], x["efeito"]) not in vistos:
            vistos.add((x["causa"], x["efeito"]))
            unicos.append(x)
    return unicos[:n]


# ─────────────────────────────────────────────────────────── ações ───
def _criar(p, pl):
    trat = str(p.get("tratamento") or "").strip().rstrip(".")
    if not trat:
        return "O que você faria nos dias COM? Ex.: 'postar no status da loja', 'treinar de manhã'."
    series = _series()
    pedido = str(p.get("medida") or "").strip()
    medida = "nota" if not pedido or "nota" in norm(pedido) else achar_serie(pedido, list(series))
    if medida is None:
        tenho = ", ".join(series) or "nada ainda"
        return (f"Ainda não acompanho '{pedido}' (tenho: {tenho}). Posso medir por nota: você me dá uma nota de 0 a 10 por dia. "
                "Peça de novo dizendo 'com nota'.")
    dias = int(max(MIN_DIAS, min(MAX_DIAS, num1(p, "dias", 14) or 14)))
    atraso = 1 if int(num1(p, "atraso", 0)) >= 1 else 0
    est = _est()
    if sum(1 for e in est["experimentos"] if e["estado"] == "ativo") >= 3:
        return "Já há 3 experimentos rodando; mais que isso um atrapalha o outro. Encerre um antes."
    est["seq"] += 1
    inicio = date.today() + timedelta(1)
    semente = random.SystemRandom().randrange(1, 2 ** 31)
    plano = sortear(inicio, dias, random.Random(semente))
    exp = {"id": est["seq"], "nome": str(p.get("nome") or trat)[:60], "tratamento": trat[:160], "medida": medida, "dias": dias,
           "atraso": atraso, "inicio": inicio.isoformat(), "plano": plano, "semente": semente, "cumpri": {}, "notas": {},
           "estado": "ativo", "criado": time.time(), "selo": None}
    try:
        from core import livro_razao
        b = livro_razao.registrar("experimento.plano", {
            "id": exp["id"], "nome": exp["nome"], "tratamento": exp["tratamento"], "medida": medida, "dias": dias, "atraso": atraso,
            "inicio": exp["inicio"], "analise": ANALISE,
            "plano_sha256": hashlib.sha256(json.dumps(plano, sort_keys=True).encode()).hexdigest()})
        exp["selo"] = livro_razao.codigo_selo(b["n"], b["hash"]) if b else None
    except Exception:
        pass
    est["experimentos"].append(exp)
    guardar("experimento_vida", est)
    com = sum(1 for r in plano.values() if r == "com")
    como = "pela nota de 0 a 10 que você me der todo dia" if medida == "nota" else f"sozinho, por {medida}" + (" do dia seguinte" if atraso else "")
    return (f"Experimento #{exp['id']} criado: \"{trat}\", por {dias} dias a partir de amanhã ({inicio:%d/%m}): {com} dias COM e "
            f"{dias - com} SEM, sorteados e equilibrados por dia da semana. Vou medir {como}. "
            + (f"Plano selado no livro-razão ({exp['selo']}) antes de qualquer dado. " if exp["selo"] else "")
            + "Todo dia eu digo se é COM ou SEM. " + frase_do_dia(exp, inicio.isoformat()).replace("hoje é", "amanhã é").replace("Hoje NÃO", "Amanhã NÃO"))


def _hoje(p, pl):
    hoje = date.today().isoformat()
    ativos = [e for e in _est()["experimentos"] if e["estado"] == "ativo"]
    if not ativos:
        return "Nenhum experimento rodando. Diga 'cria um experimento' ou 'que experimentos você sugere?'."
    linhas = []
    for e in ativos:
        f = frase_do_dia(e, hoje)
        if f:
            falta = sum(1 for d in e["plano"] if d > hoje)
            linhas.append(f + f" (faltam {falta} dia(s))")
        elif hoje < e["inicio"]:
            linhas.append(f"Experimento #{e['id']} ({e['nome']}) começa em {date.fromisoformat(e['inicio']):%d/%m}.")
        else:
            linhas.append(f"Experimento #{e['id']} ({e['nome']}): os dias acabaram; estou só esperando os últimos números.")
    return "\n".join(linhas)


def _cumpri(p, pl):
    est = _est()
    exp = _achar(est, p.get("experimento"), so_ativos=True)
    if not exp:
        return "Nenhum experimento rodando."
    hoje = date.today().isoformat()
    if hoje not in exp["plano"]:
        return "Hoje não é dia desse experimento."
    sim = norm(p.get("valor")) not in ("nao", "n", "false", "0", "nao segui", "furei")
    exp.setdefault("cumpri", {})[hoje] = sim
    guardar("experimento_vida", est)
    return ("Anotado: você seguiu o sorteio hoje." if sim else
            "Anotado que hoje você não seguiu. Sem problema: a conta continua pelo sorteio, que é o jeito que não engana.")


def _nota(p, pl):
    est = _est()
    exp = _achar(est, p.get("experimento"), so_ativos=True)
    alvo = exp if exp and exp["medida"] == "nota" else next((e for e in est["experimentos"] if e["estado"] == "ativo" and e["medida"] == "nota"), None)
    if not alvo:
        return "Nenhum experimento por nota está rodando."
    if not str(p.get("valor") or "").strip():
        return "Qual a nota de hoje, de 0 a 10?"
    v = max(0.0, min(10.0, num1(p, "valor", 0)))
    hoje = date.today().isoformat()
    if hoje not in alvo["plano"]:
        return "Hoje não é dia desse experimento."
    alvo.setdefault("notas", {})[hoje] = v
    guardar("experimento_vida", est)
    return f"Nota {fmt('nota', v)} anotada para hoje no experimento #{alvo['id']} ({alvo['nome']})."


def _resultado(p, pl):
    est = _est()
    exp = _achar(est, p.get("experimento"))
    if not exp:
        return "Ainda não há experimentos."
    if exp["estado"] == "encerrado":
        r = exp.get("resultado")
        if not r:
            return f"O experimento #{exp['id']} ({exp['nome']}) foi encerrado sem dados suficientes."
        return f"Experimento #{exp['id']} ({exp['nome']}), terminado: " + veredito(r, exp["medida"], exp["tratamento"])
    r = calcular(exp)
    if r is None:
        com = len(valores_de(exp, _series(), date.today()))
        return (f"Experimento #{exp['id']} ({exp['nome']}): ainda é cedo. Tenho {com} dia(s) com dado; preciso de pelo menos "
                f"{MIN_GRUPO} COM e {MIN_GRUPO} SEM.")
    return f"Experimento #{exp['id']} ({exp['nome']}): " + veredito(r, exp["medida"], exp["tratamento"], final=False)


def _listar(p, pl):
    exps = _est()["experimentos"]
    if not exps:
        return "Nenhum experimento ainda. Diga 'que experimentos você sugere?'."
    linhas = []
    for e in exps[-10:]:
        if e["estado"] == "ativo":
            sit = f"rodando até {date.fromisoformat(max(e['plano'])):%d/%m}"
        elif e.get("resultado"):
            r = e["resultado"]
            sit = ("funciona" if r["p"] <= 0.05 and r["diferenca"] > 0 else "piora" if r["p"] <= 0.05 else
                   "sinal fraco" if r["p"] <= 0.2 else "sem efeito visto")
            sit = f"terminou: {sit}" + (f" ({r['pct']:+.0f}%)" if r.get("pct") is not None else "")
        else:
            sit = "terminou sem dados"
        linhas.append(f"#{e['id']} {e['nome']} → {e['medida']}: {sit}")
    return "\n".join(linhas)


def _encerrar(p, pl):
    est = _est()
    exp = _achar(est, p.get("experimento"), so_ativos=True)
    if not exp:
        return "Nenhum experimento rodando com esse nome."
    texto = _fechar(exp)
    guardar("experimento_vida", est)
    return texto


def _sugerir(p, pl):
    achados = descobertas()
    if not achados:
        return ("Ainda não vi um padrão forte nos seus números para testar (preciso de umas 3 semanas de registros). "
                "Mas você pode testar qualquer coisa: 'cria um experimento: postar no status da loja, medindo as vendas'.")
    linhas = ["Padrões que eu vi e que dá para tirar a prova (padrão não é causa; o sorteio é que diz):"]
    for a in achados:
        linhas.append(f"- {a['texto']} Teste: \"cria um experimento: {a['tratamento']}, medindo {a['efeito']}\""
                      + (" (efeito no dia seguinte)." if a["atraso"] else "."))
    return "\n".join(linhas)


def passo(player) -> None:
    """Relógio central (a cada 30 min): avisa o sorteio do dia, pede a nota à noite e fecha o que terminou."""
    from plugins._comum import avisar, mostrar
    est, agora, mudou = _est(), datetime.now(), False
    hoje = agora.date().isoformat()
    for e in est["experimentos"]:
        if e["estado"] != "ativo":
            continue
        fim_dados = date.fromisoformat(max(e["plano"])) + timedelta(int(e.get("atraso", 0)))
        if agora.date() > fim_dados:
            texto = _fechar(e, agora.date())
            mostrar(player, "EXPERIMENTO TERMINADO", texto)
            avisar(player, texto.split(" Conclusão: ")[0][:200] + " O resultado está no painel.", "EXPERIMENTO")
            mudou = True
            continue
        if hoje in e["plano"] and agora.hour >= 6 and e.get("avisado") != hoje:
            avisar(player, frase_do_dia(e, hoje), "EXPERIMENTO")
            e["avisado"], mudou = hoje, True
        if e["medida"] == "nota" and hoje in e["plano"] and agora.hour >= 20 and hoje not in e.get("notas", {}) and e.get("pediu") != hoje:
            avisar(player, f"Experimento #{e['id']} ({e['nome']}): qual a sua nota de hoje, de 0 a 10?", "EXPERIMENTO")
            e["pediu"], mudou = hoje, True
    if mudou:
        guardar("experimento_vida", est)


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("experimento_vida", lambda: passo(player), a_cada_s=1800, primeira_em_s=240)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"criar": _criar, "hoje": _hoje, "cumpri": _cumpri, "nota": _nota, "resultado": _resultado,
                              "listar": _listar, "encerrar": _encerrar, "sugerir": _sugerir}, player, "Experimentos")
