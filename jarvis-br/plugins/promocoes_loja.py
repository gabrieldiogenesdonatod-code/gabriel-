"""Promoções (2.18): simula desconto, leve X pague Y, progressivo, mostra a margem que sobra e escreve o texto do post.

3.3 — gêmeo digital da loja: antes de fazer a promoção, o JARVIS simula a semana inteira com o histórico do
caixa (a mesma previsão do oráculo) e mostra vendas e lucro com e sem a promoção, quanto as peças precisam
subir só para o lucro empatar e qual desconto deixa mais lucro. Depois que a promoção acaba, ele confere
com o caixa e APRENDE como os seus clientes respondem a desconto (começa com um chute conservador e vai
trocando pelo que acontece de verdade na sua loja).

    "Jarvis, simula 20% de desconto na loja essa semana"      "Jarvis, e leve 3 pague 2 no sábado, dá lucro?"
    "Jarvis, registra a promoção"                              "Jarvis, confere a promoção"
    "Jarvis, o que você aprendeu das minhas promoções?"
"""
from __future__ import annotations

import math
import time
from datetime import date, timedelta

from plugins._lote2 import P, carregar, guardar, norm, num1, numeros, reais, rodar
from plugins.precificacao import margem_real

PLUGIN = P("promocoes_loja", "Promo simulator + store digital twin: % off, buy X pay Y, margin, caption; sales/profit with vs without the "
                             "promo; learns from past promos.",
           "desconto | leve_pague | progressivo | texto | prever | registrar | conferir | aprendizado",
           "desconto: preco, custo, valor (% off). leve_pague: preco, custo, valor ('3 2'). progressivo: preco, valor "
           "('5 10 15' % for 1,2,3 items). texto: produto, valor (promo) -> caption. prever (digital twin): tipo (desconto | "
           "leve_pague), valor ('20' or '3 2'), dias (default 7), inicio (dd/mm, default tomorrow), alcance (% of sales the promo "
           "covers, default 100), margem (store gross margin %, remembered) or preco+custo of the item, vendas (normal weekly "
           "sales if there is no cash history). registrar: confirms the last simulation (or pass the same params for a promo "
           "already done). conferir: compares finished promos with the cash register and learns. aprendizado: what it learned.",
           "preco custo valor produto tipo dias inicio alcance margem vendas")


def _x(p, k):
    n = numeros(p.get(k))
    return n[0] if n else 0.0


def leve_pague(preco, leve, pague) -> float:
    return preco * pague / leve


def _go(p, pl):
    a, pr, cu = str(p.get("action")).lower(), _x(p, "preco"), _x(p, "custo")
    v = numeros(p.get("valor"))
    if a in ("desconto", "leve_pague") and pr <= 0:
        return "Qual o preço da peça?"
    if a == "desconto":
        novo = pr * (1 - (v[0] if v else 0) / 100)
    elif a == "leve_pague":
        leve, pague = (int(v[0]), int(v[1])) if len(v) > 1 else (3, 2)
        novo = leve_pague(pr, leve, pague)
    elif a == "progressivo":
        return "; ".join(f"{i + 1} peça(s): {reais(pr * (1 - d / 100))} cada" for i, d in enumerate(v or [0, 5, 10]))
    else:
        prod, promo = str(p.get("produto") or "nossas peças"), str(p.get("valor") or "preço especial")
        return (f"🔥 PROMOÇÃO na Cristal Malhas! {prod} com {promo}. Só enquanto durar o estoque — chama no WhatsApp "
                f"e garanta o seu! 💛 #modainfantil #promocao #goiania")
    msg = f"Preço efetivo {reais(novo)} por peça ({(1 - novo / pr) * 100:.0f}% de desconto)"
    if cu:
        msg += f"; margem cai para {margem_real(cu, novo):.1f}%" + (" — PREJUÍZO!" if novo < cu else "")
    return msg + "."


# ───────────────────────────────────────────── 3.3: gêmeo digital da loja ───
E0 = {"desconto": 2.0, "leve_pague": 1.5}      # chute inicial da elasticidade (troca pelo que a sua loja mostrar)
PESO_CHUTE = 2                                  # o chute vale como 2 promoções; cada promoção conferida vale 1
MARGEM_PADRAO = 0.5
AVISO_GEMEO = ("É simulação com o histórico do seu caixa. Promoção também adianta compra que viria depois; "
               "por isso eu confiro quando ela acabar e aprendo com a sua loja.")


def desconto_efetivo(tipo: str, nums: list[float]) -> float:
    """Fração de desconto (0,2 = 20%). Leve X pague Y = 1 − Y/X. Pura."""
    if tipo == "leve_pague":
        leve, pague = (nums[0], nums[1]) if len(nums) > 1 and nums[0] > nums[1] > 0 else (3.0, 2.0)
        return 1 - pague / leve
    return min(0.9, max(0.0, (nums[0] if nums else 0.0) / 100))


def simular(base: float, d: float, e: float, alcance: float = 1.0, margem: float = MARGEM_PADRAO) -> dict:
    """Vendas e lucro bruto do período com a promoção (elasticidade constante: peças × (1−d)^−e). Pura."""
    pecas = (1 - d) ** (-e)
    receita_rel = (1 - d) * pecas
    c, m = alcance, margem
    return {"receita": base * (1 - c + c * receita_rel), "lucro0": base * m,
            "lucro": base * ((1 - c) * m + c * (receita_rel - (1 - m) * pecas)),
            "pecas": 1 - c + c * pecas, "pecas_promo": pecas, "empate": (m / (m - d)) if m > d else math.inf}


def melhor_desconto(e: float, margem: float, alcance: float = 1.0) -> float:
    """O desconto (0 a 50%, de 5 em 5) que deixa mais lucro; empate fica com o menor. Pura."""
    return max((k / 100 for k in range(0, 55, 5)), key=lambda d: (round(simular(1.0, d, e, alcance, margem)["lucro"], 6), -d))


def elasticidade_vista(razao: float, d: float, alcance: float = 1.0) -> float | None:
    """A elasticidade que explica 'vendeu razão × o normal' com desconto d em 'alcance' das vendas. Pura."""
    if d <= 0 or alcance <= 0:
        return None
    x = (razao - 1 + alcance) / alcance
    if x <= 0:
        return 0.0
    return max(0.0, min(6.0, 1 - math.log(x) / math.log(1 - d)))


def _gemeo() -> dict:
    return carregar("gemeo_loja", {"margem": None, "promocoes": [], "ultimo": None})


def elasticidade(tipo: str, est: dict | None = None) -> tuple[float, int]:
    obs = [o["e"] for o in (est or _gemeo()).get("promocoes", []) if o.get("tipo") == tipo and o.get("e") is not None]
    return (E0.get(tipo, 2.0) * PESO_CHUTE + sum(obs)) / (PESO_CHUTE + len(obs)), len(obs)


def base_periodo(serie: dict[str, float], inicio: date, dias: int) -> dict[str, float]:
    """Vendas normais (sem promoção) dia a dia, só com o caixa de ANTES do início. Pura."""
    from plugins.oraculo import prever_semana
    antes = {d: v for d, v in serie.items() if d < inicio.isoformat()}
    out: dict[str, float] = {}
    for k in range(0, dias, 7):
        out.update(prever_semana(antes, inicio + timedelta(k)))
    fim = (inicio + timedelta(dias)).isoformat()
    return {d: v for d, v in sorted(out.items()) if d < fim}


def dias_de_promocao(est: dict) -> set[str]:
    """Dias que tiveram promoção registrada: ficam fora do 'normal' das próximas simulações. Pura."""
    out = set()
    for pr in est.get("promocoes", []):
        try:
            ini, fim = date.fromisoformat(pr["inicio"]), date.fromisoformat(pr["fim"])
        except (KeyError, ValueError):
            continue
        out.update((ini + timedelta(k)).isoformat() for k in range((fim - ini).days + 1))
    return out


def _vendas_serie() -> dict[str, float]:
    try:
        from plugins.oraculo import _vendas
        return _vendas()
    except Exception as e:
        print(f"[Gêmeo] caixa: {e}")
        return {}


def _tipo(p) -> str:
    t, v = norm(p.get("tipo")), norm(p.get("valor"))
    nums = numeros(p.get("valor"))
    if "leve" in t or "leve" in v or "pague" in v:
        return "leve_pague"
    if not t and len(nums) >= 2 and nums[0] > nums[1] > 0 and nums[0] <= 10 and "%" not in v:
        return "leve_pague"
    return "desconto"


def _nome(tipo: str, nums: list[float]) -> str:
    if tipo == "leve_pague":
        leve, pague = (nums[0], nums[1]) if len(nums) > 1 and nums[0] > nums[1] > 0 else (3, 2)
        return f"leve {leve:g} pague {pague:g}"
    return f"{desconto_efetivo(tipo, nums):.0%} de desconto"


def _margem(p, est: dict) -> tuple[float, str]:
    """(margem, de onde veio). A margem da loja dita uma vez fica guardada."""
    if numeros(p.get("margem")):
        est["margem"] = max(0.05, min(0.95, num1(p, "margem") / 100))
        return est["margem"], ""
    pr, cu = num1(p, "preco"), num1(p, "custo")
    if pr > 0 and 0 < cu < pr:
        return (pr - cu) / pr, " (margem da peça que você disse)"
    if est.get("margem"):
        return float(est["margem"]), ""
    return MARGEM_PADRAO, " Considerei margem de 50%; diga a margem média da loja que eu guardo e a conta fica certa."


def _planejar(p) -> dict | str:
    tipo, nums = _tipo(p), numeros(p.get("valor"))
    if not nums and tipo == "desconto":
        return "Qual promoção? Ex.: 20% de desconto, ou leve 3 pague 2."
    d = desconto_efetivo(tipo, nums)
    dias = int(max(1, min(31, num1(p, "dias", 7) or 7)))
    alcance = max(0.05, min(1.0, (num1(p, "alcance", 100) or 100) / 100))
    try:
        from plugins.calculadora_datas import ler_data
        inicio = ler_data(p.get("inicio"), date.today() + timedelta(1)) if str(p.get("inicio") or "").strip() else date.today() + timedelta(1)
    except ValueError as e:
        return str(e)
    est = _gemeo()
    margem, nota_margem = _margem(p, est)
    promo = dias_de_promocao(est)
    base_dias = base_periodo({d: v for d, v in _vendas_serie().items() if d not in promo}, inicio, dias)
    if base_dias:
        base, fonte = sum(base_dias.values()), "pela previsão do caixa"
    elif num1(p, "vendas") > 0:
        base, fonte = num1(p, "vendas") * dias / 7, "pelo que você me disse"
    else:
        return ("Para simular eu preciso do histórico do caixa (pelo menos uma semana usando o caixa da loja) "
                "ou que você me diga quanto vende numa semana normal.")
    e, n = elasticidade(tipo, est)
    return {"tipo": tipo, "nome": _nome(tipo, nums), "d": d, "dias": dias, "alcance": alcance, "inicio": inicio.isoformat(),
            "fim": (inicio + timedelta(dias - 1)).isoformat(), "margem": margem, "nota_margem": nota_margem, "base": base,
            "base_dias": base_dias, "fonte": fonte, "e": e, "n": n, "sim": simular(base, d, e, alcance, margem),
            "melhor": melhor_desconto(e, margem, alcance), "est": est}


def _prever(p, pl):
    plano = _planejar(p)
    if isinstance(plano, str):
        return plano
    est, s, d = plano.pop("est"), plano["sim"], plano["d"]
    est["ultimo"] = {k: v for k, v in plano.items() if k not in ("sim", "nota_margem")} | {"ts": time.time()}
    guardar("gemeo_loja", est)
    ini = date.fromisoformat(plano["inicio"])
    dl = s["lucro"] - s["lucro0"]
    if d >= plano["margem"]:
        veredito = "PREJUÍZO garantido: o desconto é maior que a sua margem; cada peça a mais aumenta a perda."
    elif dl >= -0.02 * s["lucro0"]:
        veredito = "Compensa: vende mais e o lucro não cai."
    elif s["receita"] > plano["base"]:
        veredito = (f"Vende mais, mas o lucro cai uns {reais(-dl)}. Vale para girar estoque parado ou trazer cliente novo, "
                    "não para lucrar.")
    else:
        veredito = "Não compensa: nem as vendas sobem o suficiente."
    empate = "nunca (desconto maior que a margem)" if math.isinf(s["empate"]) else f"{s['empate'] - 1:+.0%}"
    aprendi = (f"Aprendi com {plano['n']} promoção(ões) sua(s)." if plano["n"] else
               "Ainda estou no chute inicial; depois da primeira promoção conferida eu uso o jeito dos seus clientes.")
    return (f"Gêmeo da loja: {plano['nome']} por {plano['dias']} dia(s) a partir de {ini:%d/%m}"
            + (f", em {plano['alcance']:.0%} das vendas" if plano["alcance"] < 1 else "") + ".\n"
            f"Sem promoção: uns {reais(plano['base'])} em vendas e {reais(s['lucro0'])} de lucro bruto ({plano['fonte']}).\n"
            f"Com promoção: uns {reais(s['receita'])} ({s['receita'] / plano['base'] - 1:+.0%}) e {reais(s['lucro'])} de lucro "
            f"({'+' if dl >= 0 else '-'}{reais(abs(dl))}), com {s['pecas'] - 1:+.0%} de peças vendidas.\n"
            f"Para o lucro empatar, as peças em promoção precisam subir {empate}; eu espero {s['pecas_promo'] - 1:+.0%}.\n"
            f"{veredito}\n"
            f"O desconto que mais deixa lucro, pelo que sei da sua loja: {plano['melhor']:.0%}"
            + (" (sem desconto: a promoção aqui é para movimento, não para lucro)." if plano["melhor"] == 0 else ".") + "\n"
            f"{aprendi}{plano['nota_margem']} Se for fazer, diga 'registra a promoção' que eu confiro o resultado depois.")


def _registrar(p, pl):
    if numeros(p.get("valor")):
        plano = _planejar(p)
        if isinstance(plano, str):
            return plano
        est = plano.pop("est")
    else:
        est = _gemeo()
        plano = est.get("ultimo")
        if not plano or time.time() - plano.get("ts", 0) > 7 * 86400:
            return "Qual promoção? Primeiro peça uma simulação (ex.: 'simula 20% de desconto') ou me diga os dados."
    est["seq"] = int(est.get("seq", 0)) + 1
    est.setdefault("promocoes", []).append({"id": est["seq"], "tipo": plano["tipo"], "nome": plano["nome"], "d": plano["d"],
                                            "alcance": plano["alcance"], "inicio": plano["inicio"], "fim": plano["fim"],
                                            "base_dias": plano["base_dias"], "e_usada": plano["e"], "conferida": False})
    est["promocoes"] = est["promocoes"][-60:]
    est["ultimo"] = None
    guardar("gemeo_loja", est)
    fim = date.fromisoformat(plano["fim"])
    feita = f"Promoção registrada: {plano['nome']} de {date.fromisoformat(plano['inicio']):%d/%m} a {fim:%d/%m}."
    if fim < date.today():
        return feita + " Como ela já acabou, diga 'confere a promoção' e eu comparo com o caixa."
    return feita + " Quando acabar, eu comparo sozinho com o caixa e aprendo com ela; use o caixa da loja nesses dias."


def conferir_promocoes(hoje: date | None = None) -> list[str]:
    hoje, est, serie, out = hoje or date.today(), _gemeo(), _vendas_serie(), []
    mudou = False
    for pr in est.get("promocoes", []):
        if pr.get("conferida") or date.fromisoformat(pr["fim"]) >= hoje:
            continue
        dias = [d for d in pr.get("base_dias", {}) if serie.get(d, 0) > 0]
        if not pr.get("base_dias") or len(dias) < max(1, len(pr["base_dias"]) // 2):
            if (hoje - date.fromisoformat(pr["fim"])).days > 14:
                pr["conferida"], mudou = "sem dados", True
                out.append(f"Promoção {pr['nome']}: não tenho o caixa desses dias, então não deu para aprender com ela.")
            continue
        base = sum(pr["base_dias"][d] for d in dias)
        real = sum(serie[d] for d in dias)
        previsto = simular(base, pr["d"], pr["e_usada"], pr["alcance"])["receita"]
        razao = real / base if base else 1.0
        pr.update(conferida=True, razao=round(razao, 3), real=round(real, 2), e=elasticidade_vista(razao, pr["d"], pr["alcance"]))
        mudou = True
        out.append(f"Promoção {pr['nome']} ({date.fromisoformat(pr['inicio']):%d/%m} a {date.fromisoformat(pr['fim']):%d/%m}): "
                   f"sem ela eu esperava {reais(base)}, com ela previ {reais(previsto)}; vendeu {reais(real)} "
                   f"({razao - 1:+.0%} sobre o normal, em {len(dias)} dia(s) com caixa).")
    if mudou:
        guardar("gemeo_loja", est)
    if out:
        for tipo in sorted({pr["tipo"] for pr in est.get("promocoes", []) if pr.get("e") is not None}):
            e, n = elasticidade(tipo, est)
            out.append(f"Agora, em {'desconto' if tipo == 'desconto' else 'leve X pague Y'}: cada 10% de desconto traz uns "
                       f"{0.9 ** -e - 1:+.0%} de peças vendidas (aprendido com {n} promoção(ões)).")
    return out


def _conferir(p, pl):
    out = conferir_promocoes()
    if out:
        return "\n".join(out)
    pendentes = [pr for pr in _gemeo().get("promocoes", []) if not pr.get("conferida")]
    if pendentes:
        prox = min(pendentes, key=lambda x: x["fim"])
        return f"Nenhuma promoção para conferir agora; a próxima ({prox['nome']}) acaba em {date.fromisoformat(prox['fim']):%d/%m}."
    return "Nenhuma promoção registrada. Simule uma e diga 'registra a promoção'."


def _aprendizado(p, pl):
    est = _gemeo()
    linhas = []
    for tipo, nome in (("desconto", "Desconto"), ("leve_pague", "Leve X pague Y")):
        e, n = elasticidade(tipo, est)
        linhas.append(f"{nome}: cada 10% de desconto traz uns {0.9 ** -e - 1:+.0%} de peças vendidas "
                      + (f"(aprendido com {n} promoção(ões) sua(s))." if n else "(ainda é o meu chute inicial)."))
    feitas = [pr for pr in est.get("promocoes", []) if pr.get("conferida") is True][-5:]
    if feitas:
        linhas.append("Últimas conferidas: " + "; ".join(f"{pr['nome']} {pr['razao'] - 1:+.0%}" for pr in feitas) + ".")
    m = est.get("margem")
    linhas.append(f"Margem da loja que eu uso: {m:.0%}." if m else "Ainda não sei a margem média da loja (uso 50%).")
    linhas.append(f"Melhor desconto para lucro hoje: {melhor_desconto(elasticidade('desconto', est)[0], m or MARGEM_PADRAO):.0%}.")
    return "\n".join(linhas)


def passo(player) -> None:
    """Relógio central: quando uma promoção registrada termina e o caixa tem os dias, confere e avisa."""
    out = conferir_promocoes()
    if out:
        from plugins._comum import avisar, mostrar
        mostrar(player, "GÊMEO DA LOJA", "\n".join(out))
        avisar(player, "Conferi a promoção que acabou e aprendi com ela. Está no painel.", "GÊMEO DA LOJA")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("gemeo_loja", lambda: passo(player), a_cada_s=6 * 3600, primeira_em_s=420)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("desconto leve_pague progressivo texto".split(), _go)
                 | {"prever": _prever, "registrar": _registrar, "conferir": _conferir, "aprendizado": _aprendizado},
                 player, "Promoções")
