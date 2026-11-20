"""
Garagem (fork PT-BR 3.8) — manutenção do carro ou da moto por km e por data.

    "Jarvis, cadastra meu carro, Gol, com 85 mil km"     "Jarvis, cadastra a moto Titan com 32 mil km"
    "Jarvis, o carro está com 86.400 km"                 "Jarvis, troquei o óleo do carro hoje, paguei 180"
    "Jarvis, o que está vencendo no carro?"              "Jarvis, quanto gastei com a moto?"
    "Jarvis, histórico do carro"

Cada item (óleo, filtros, pneus, correia, freio, bateria, revisão…) tem um intervalo em km e em meses;
vence o que chegar primeiro. Os intervalos são os comuns no Brasil e servem de lembrete: o manual do seu
veículo manda. Se você anota os abastecimentos no plugin `combustivel` com o km do painel, a garagem
usa esse km também. Uma vez por dia ele avisa quando um item entra na faixa de vencer.
"""
from __future__ import annotations

import re
from datetime import date

from plugins import _comum
from plugins._lote2 import P, carregar, guardar, ler_json, norm, numeros, reais, rodar

PLUGIN = P("veiculo", "Car/motorcycle maintenance: oil, filters, tires, timing belt, brakes by km and date; what is due, history and costs.",
           "proximas | cadastrar | km | fiz | historico | gastos | remover | itens",
           "cadastrar: nome (model), tipo (carro or moto), km. km: veiculo + km (odometer now). fiz: veiculo, item (oleo, filtro de ar, "
           "pneus, correia, freio, bateria, revisao…), km optional, valor optional (R$). proximas: what is due or close. "
           "historico, gastos: per vehicle. itens: maintenance list with intervals. remover: vehicle.",
           "veiculo nome tipo km item valor")

# item: (km, meses, nome falado) — intervalos comuns, o manual do veículo manda
ITENS = {
    "carro": {"oleo": (10000, 12, "troca de óleo"), "filtro_oleo": (10000, 12, "filtro de óleo"), "filtro_ar": (15000, 12, "filtro de ar"),
              "filtro_combustivel": (20000, 24, "filtro de combustível"), "filtro_cabine": (15000, 12, "filtro do ar-condicionado"),
              "rodizio": (10000, 12, "rodízio dos pneus"), "alinhamento": (10000, 12, "alinhamento e balanceamento"),
              "pneus": (50000, 60, "troca dos pneus"), "correia": (50000, 48, "correia dentada"), "fluido_freio": (0, 24, "fluido de freio"),
              "pastilhas": (30000, 0, "pastilhas de freio"), "arrefecimento": (40000, 24, "líquido de arrefecimento"),
              "velas": (30000, 0, "velas de ignição"), "bateria": (0, 36, "bateria"), "revisao": (10000, 12, "revisão geral")},
    "moto": {"oleo": (3000, 6, "troca de óleo"), "filtro_oleo": (6000, 12, "filtro de óleo"), "filtro_ar": (12000, 12, "filtro de ar"),
             "corrente": (500, 0, "lubrificar a corrente"), "relacao": (20000, 0, "kit relação (corrente, coroa e pinhão)"),
             "pneus": (15000, 48, "troca dos pneus"), "pastilhas": (10000, 0, "pastilhas de freio"), "fluido_freio": (0, 24, "fluido de freio"),
             "velas": (10000, 0, "vela de ignição"), "bateria": (0, 24, "bateria"), "revisao": (6000, 12, "revisão geral")},
}
FALADO = [("filtro de oleo", "filtro_oleo"), ("filtro do oleo", "filtro_oleo"), ("filtro de ar condicionado", "filtro_cabine"),
          ("filtro do ar condicionado", "filtro_cabine"), ("filtro de cabine", "filtro_cabine"), ("filtro de combustivel", "filtro_combustivel"),
          ("filtro de ar", "filtro_ar"), ("filtro do ar", "filtro_ar"), ("kit relacao", "relacao"), ("relacao", "relacao"),
          ("corrente", "corrente"), ("correia", "correia"), ("rodizio", "rodizio"), ("alinhamento", "alinhamento"),
          ("balanceamento", "alinhamento"), ("pneu", "pneus"), ("fluido de freio", "fluido_freio"), ("oleo de freio", "fluido_freio"),
          ("pastilha", "pastilhas"), ("freio", "pastilhas"), ("arrefecimento", "arrefecimento"), ("radiador", "arrefecimento"),
          ("agua do radiador", "arrefecimento"), ("vela", "velas"), ("bateria", "bateria"), ("revisao", "revisao"), ("oleo", "oleo")]
FAIXA_KM, FAIXA_DIAS = 0.10, 30          # "perto de vencer": faltam 10% do intervalo de km ou 30 dias


def item_de(texto, tipo: str = "carro") -> str | None:
    t = norm(texto).replace("-", " ")
    for frase, chave in FALADO:
        if frase in t and chave in ITENS[tipo]:
            return chave
    return None


def km_de(texto) -> float | None:
    """'85 mil' → 85000; '86.400' → 86400; '86400 km' → 86400. Pura."""
    t = norm(texto)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*mil\b", t)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    t = re.sub(r"(\d)\.(\d{3})\b", r"\1\2", t)
    n = numeros(t)
    return n[0] if n else None


def situacao(item: str, tipo: str, ultimo: dict | None, km_atual: float, hoje: date) -> dict:
    """Quanto falta (km e dias) e se venceu ou está perto. Pura.
    Sem registro de quando foi feito, conta a partir do km 0 / não sabe a data."""
    km_int, meses, nome = ITENS[tipo][item]
    feito_km = (ultimo or {}).get("km", 0.0) or 0.0
    feito_d = (ultimo or {}).get("d")
    falta_km = (feito_km + km_int - km_atual) if km_int else None
    falta_d = None
    if meses and feito_d:
        falta_d = round(meses * 30.44 - (hoje - date.fromisoformat(feito_d)).days)
    vencido = (falta_km is not None and falta_km <= 0) or (falta_d is not None and falta_d <= 0)
    perto = not vencido and ((falta_km is not None and falta_km <= km_int * FAIXA_KM) or (falta_d is not None and falta_d <= FAIXA_DIAS))
    return {"item": item, "nome": nome, "falta_km": falta_km, "falta_dias": falta_d, "vencido": vencido, "perto": perto,
            "sem_registro": ultimo is None}


def texto_situacao(s: dict) -> str:
    partes = []
    if s["falta_km"] is not None:
        partes.append(f"passou {abs(s['falta_km']):,.0f} km".replace(",", ".") if s["falta_km"] <= 0 else f"faltam {s['falta_km']:,.0f} km".replace(",", "."))
    if s["falta_dias"] is not None:
        partes.append(f"venceu há {-s['falta_dias']} dias" if s["falta_dias"] <= 0 else f"faltam {s['falta_dias']} dias")
    marca = "VENCIDO" if s["vencido"] else "perto" if s["perto"] else "ok"
    extra = " (sem registro: contei do zero)" if s["sem_registro"] else ""
    return f"{s['nome']}: {marca}, {' / '.join(partes) or 'sem data'}{extra}"


# ─────────────────────────────────────────────────────────── estado ───
def _est() -> dict:
    return carregar("veiculo", {"veiculos": []})


def _gravar(e: dict) -> None:
    guardar("veiculo", e)


def _achar(e: dict, texto) -> dict | None:
    vs = e["veiculos"]
    if not vs:
        return None
    t = norm(texto)
    for v in vs:
        if norm(v["nome"]) and norm(v["nome"]) in t:
            return v
    for v in vs:
        if v["tipo"] in t:
            return v
    return vs[0] if len(vs) == 1 or not t else None


def km_combustivel() -> float:
    """Último km do painel anotado no plugin combustivel (0 se não tiver)."""
    try:
        from plugins import _lote2
        log = ler_json(_lote2.PASTA / "combustivel.json", []) or []
        return max((float(x.get("km") or 0) for x in log), default=0.0)
    except Exception:
        return 0.0


def km_atual(v: dict, e: dict) -> float:
    k = float(v.get("km") or 0)
    if len(e["veiculos"]) == 1 and v["tipo"] == "carro":           # o combustivel não diz qual veículo: só com 1 carro
        k = max(k, km_combustivel())
    return k


def todas(v: dict, e: dict, hoje: date) -> list[dict]:
    k = km_atual(v, e)
    return [situacao(i, v["tipo"], v["itens"].get(i), k, hoje) for i in ITENS[v["tipo"]]]


# ─────────────────────────────────────────────────────────── ações ───
def _cadastrar(p, pl):
    e = _est()
    tipo = "moto" if "moto" in norm(f"{p.get('tipo')} {p.get('nome')}") else "carro"
    nome = re.sub(r"\b(carro|moto|meu|minha|a|o)\b", "", str(p.get("nome") or ""), flags=re.I).strip(" ,") or tipo
    if any(norm(v["nome"]) == norm(nome) for v in e["veiculos"]):
        return f"Já tenho o {nome} cadastrado."
    km = km_de(p.get("km")) or 0.0
    e["veiculos"].append({"nome": nome, "tipo": tipo, "km": km, "km_d": date.today().isoformat(), "itens": {}, "historico": []})
    _gravar(e)
    return (f"Cadastrei {'a moto' if tipo == 'moto' else 'o carro'} {nome} com {km:,.0f} km. ".replace(",", ".") +
            "Me diga o que já foi feito (por exemplo 'troquei o óleo com 84 mil km') para eu calcular certo.")


def _km(p, pl):
    e = _est()
    v = _achar(e, p.get("veiculo") or p.get("nome"))
    if not v:
        return "De qual veículo? Cadastre com 'cadastra meu carro …'." if not e["veiculos"] else "De qual veículo?"
    km = km_de(p.get("km"))
    if not km:
        return f"Com quantos km o {v['nome']} está?"
    if km < float(v.get("km") or 0):
        return f"O {v['nome']} já estava com {v['km']:,.0f} km: o odômetro não volta.".replace(",", ".")
    v["km"], v["km_d"] = km, date.today().isoformat()
    _gravar(e)
    venc = [s for s in todas(v, e, date.today()) if s["vencido"] or s["perto"]]
    return f"{v['nome']} com {km:,.0f} km.".replace(",", ".") + (" Atenção: " + "; ".join(texto_situacao(s) for s in venc) + "." if venc else "")


def _fiz(p, pl):
    e = _est()
    v = _achar(e, f"{p.get('veiculo') or ''} {p.get('item') or ''}")
    if not v:
        return "Em qual veículo?" if e["veiculos"] else "Primeiro cadastre o veículo: 'cadastra meu carro, Gol, com 85 mil km'."
    item = item_de(p.get("item"), v["tipo"])
    if not item:
        return f"Qual serviço? Itens da {v['tipo']}: " + ", ".join(x[2] for x in ITENS[v["tipo"]].values()) + "."
    km = km_de(p.get("km")) or km_atual(v, e)
    valor = numeros(str(p.get("valor") or "").replace(".", "").replace(",", ".")) if re.search(r"\d\.\d{3}", str(p.get("valor") or "")) \
        else numeros(p.get("valor"))
    hoje = date.today().isoformat()
    reg = {"d": hoje, "km": km}
    v["itens"][item] = reg
    v["historico"].append({"d": hoje, "item": item, "km": km, "valor": valor[0] if valor else 0.0})
    if km > float(v.get("km") or 0):
        v["km"], v["km_d"] = km, hoje
    if item == "oleo" and "filtro" in norm(p.get("item")):
        v["itens"]["filtro_oleo"] = dict(reg)
    _gravar(e)
    prox = []
    km_int, meses, nome = ITENS[v["tipo"]][item]
    if km_int:
        prox.append(f"com {km + km_int:,.0f} km".replace(",", "."))
    if meses:
        prox.append(f"em {meses} meses")
    return f"Anotado: {nome} no {v['nome']} com {km:,.0f} km".replace(",", ".") + (f", {reais(valor[0])}" if valor else "") + \
        f". Próxima: {' ou '.join(prox)} (o que vier primeiro)."


def _proximas(p, pl):
    e = _est()
    if not e["veiculos"]:
        return "Nenhum veículo cadastrado. Diga: 'cadastra meu carro, Gol, com 85 mil km'."
    pedido = p.get("veiculo") or p.get("nome")
    alvo = _achar(e, pedido) if norm(pedido) else None
    vs = [alvo] if alvo else e["veiculos"]
    partes = []
    for v in vs:
        ss = todas(v, e, date.today())
        conhecidos = [s for s in ss if not s["sem_registro"]]
        avisar = [s for s in conhecidos if s["vencido"]] + [s for s in conhecidos if s["perto"]]
        sem = [s["nome"] for s in ss if s["sem_registro"]]
        t = f"{v['nome']} ({km_atual(v, e):,.0f} km): ".replace(",", ".")
        t += ("; ".join(texto_situacao(s) for s in avisar) + ".") if avisar else ("nada vencendo." if conhecidos else "")
        if sem:
            t += f" Ainda não sei quando foi feito: {', '.join(sem)} (me conte para eu calcular)."
        partes.append(t.strip())
    return " ".join(partes) + " (Intervalos comuns; o manual do veículo manda.)"


def _historico(p, pl):
    e = _est()
    v = _achar(e, p.get("veiculo") or p.get("nome"))
    if not v:
        return "De qual veículo?" if e["veiculos"] else "Nenhum veículo cadastrado."
    h = v["historico"][-10:]
    if not h:
        return f"Nada anotado no {v['nome']} ainda."
    return f"{v['nome']}: " + "; ".join(
        f"{x['d'][8:10]}/{x['d'][5:7]}/{x['d'][:4]} {ITENS[v['tipo']][x['item']][2]} com {x['km']:,.0f} km".replace(",", ".")
        + (f" ({reais(x['valor'])})" if x.get("valor") else "") for x in reversed(h)) + "."


def _gastos(p, pl):
    e = _est()
    v = _achar(e, p.get("veiculo") or p.get("nome"))
    vs = [v] if v else e["veiculos"]
    if not vs:
        return "Nenhum veículo cadastrado."
    partes = []
    ano = str(date.today().year)
    for v in vs:
        total = sum(x.get("valor") or 0 for x in v["historico"])
        no_ano = sum(x.get("valor") or 0 for x in v["historico"] if x["d"].startswith(ano))
        partes.append(f"{v['nome']}: {reais(total)} em manutenção anotada ({reais(no_ano)} em {ano})")
    return "; ".join(partes) + "."


def _remover(p, pl):
    e = _est()
    v = _achar(e, p.get("veiculo") or p.get("nome"))
    if not v or not norm(p.get("veiculo") or p.get("nome")):
        return "Qual veículo eu tiro? Diga o nome."
    e["veiculos"].remove(v)
    _gravar(e)
    return f"Tirei o {v['nome']} da garagem."


def _itens(p, pl):
    tipo = "moto" if "moto" in norm(f"{p.get('tipo')} {p.get('veiculo')}") else "carro"
    def faixa(km, m):
        return " ou ".join(x for x in (f"{km:,} km".replace(",", ".") if km else "", f"{m} meses" if m else "") if x)
    return f"Itens da {tipo}: " + "; ".join(f"{n} a cada {faixa(km, m)}" for km, m, n in ITENS[tipo].values()) + ". O manual do veículo manda."


# ─────────────────────────────────────────────────────────── aviso diário ───
def passo(player) -> None:
    """Uma vez por dia: avisa o que entrou na faixa de vencer desde o último aviso (só itens com registro)."""
    e = _est()
    hoje = date.today()
    if not e["veiculos"] or e.get("avisado_em") == hoje.isoformat():
        return
    e["avisado_em"] = hoje.isoformat()
    agora, textos = [], {}
    for v in e["veiculos"]:
        for s in todas(v, e, hoje):
            if (s["vencido"] or s["perto"]) and not s["sem_registro"]:
                chave = f"{v['nome']}:{s['item']}"
                agora.append(chave)
                textos[chave] = f"{v['nome']}: {texto_situacao(s)}"
    novos = [c for c in agora if c not in e.get("ja_avisei", [])]
    e["ja_avisei"] = agora                       # o que foi resolvido sai; se vencer de novo, avisa de novo
    _gravar(e)
    if novos:
        _comum.avisar(player, "Garagem: " + "; ".join(textos[c] for c in novos) + ".", "veiculo")


def on_session_start(player) -> None:
    try:
        from core import relogio
        relogio.agendar("veiculo_aviso", lambda: passo(player), 3600, 120)
    except Exception:
        pass


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"proximas": _proximas, "cadastrar": _cadastrar, "km": _km, "fiz": _fiz, "historico": _historico,
                              "gastos": _gastos, "remover": _remover, "itens": _itens}, player)
