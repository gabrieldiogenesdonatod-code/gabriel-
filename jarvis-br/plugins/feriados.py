"""
Planejador de feriados (fork PT-BR 2.16, ideia 2).

    "Jarvis, quais os feriados de 2027?"
    "Jarvis, onde dá para emendar esse ano?"
    "Jarvis, qual o próximo feriado?"
    "Jarvis, anota o feriado municipal de 24 de outubro"   (aniversário de Goiânia, por exemplo)

Calcula tudo aqui, sem internet: os feriados nacionais (Páscoa pelo cálculo
gregoriano: Carnaval, Sexta-feira Santa e Corpus Christi vêm dela; 20 de
novembro é nacional desde 2024) e os que você cadastrar. Para cada feriado em
dia útil, mostra quantos dias de folga você precisa tirar e quantos dias
seguidos ganha — ordenado pelo melhor custo-benefício.

Carnaval e Corpus Christi são ponto facultativo: entram marcados assim, e você
pode tirá-los da conta em ⚙ → Planejador de feriados.
"""

from __future__ import annotations

from datetime import date, timedelta

from plugins._comum import CONFIG, cfg, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "feriados",
    "brief": "Brazilian holidays for any year, bridge days (emendas) ranked by days off gained, next holiday.",
    "description": (
        "Holiday planner (Brazil). action='emendas' (optional ano) ranks where to bridge holidays: days of leave needed vs "
        "consecutive days off. action='lista' (optional ano) lists the holidays. action='proximo'. action='adicionar' "
        "with data (DD/MM) and nome for a state/city holiday; 'remover' with nome."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "emendas | lista | proximo | adicionar | remover"},
            "ano": {"type": "INTEGER"}, "data": {"type": "STRING"}, "nome": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "feriados",
    "title": "Planejador de feriados",
    "fields": [
        {"key": "facultativos", "label": "Contar Carnaval e Corpus Christi como folga", "type": "toggle",
         "default": True},
        {"key": "trabalha_sabado", "label": "Trabalho aos sábados", "type": "toggle", "default": False},
    ],
}

ARQ = CONFIG / "feriados_locais.json"
DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher) (pura)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(ano: int, locais: list[dict] | None = None, facultativos: bool = True) -> list[dict]:
    """[{data, nome, tipo}] do ano, em ordem (pura)."""
    p = pascoa(ano)
    lista = [(date(ano, 1, 1), "Confraternização Universal", "nacional"),
             (p - timedelta(days=2), "Sexta-feira Santa", "nacional"),
             (date(ano, 4, 21), "Tiradentes", "nacional"),
             (date(ano, 5, 1), "Dia do Trabalho", "nacional"),
             (date(ano, 9, 7), "Independência", "nacional"),
             (date(ano, 10, 12), "Nossa Senhora Aparecida", "nacional"),
             (date(ano, 11, 2), "Finados", "nacional"),
             (date(ano, 11, 15), "Proclamação da República", "nacional"),
             (date(ano, 12, 25), "Natal", "nacional")]
    if ano >= 2024:
        lista.append((date(ano, 11, 20), "Dia de Zumbi e da Consciência Negra", "nacional"))
    if facultativos:
        lista += [(p - timedelta(days=48), "Carnaval (segunda)", "facultativo"),
                  (p - timedelta(days=47), "Carnaval (terça)", "facultativo"),
                  (p + timedelta(days=60), "Corpus Christi", "facultativo")]
    for f in locais or []:
        try:
            d, m = (int(x) for x in str(f["data"]).split("/")[:2])
            lista.append((date(ano, m, d), f["nome"], "local"))
        except (ValueError, KeyError):
            continue
    vistos, saida = set(), []
    for d, n, t in sorted(lista):
        if d not in vistos:
            vistos.add(d)
            saida.append({"data": d, "nome": n, "tipo": t})
    return saida


def _janela(d: date, livre, antes: int, depois: int):
    a, b = d - timedelta(days=antes), d + timedelta(days=depois)
    tirar = [a + timedelta(days=i) for i in range((b - a).days + 1) if not livre(a + timedelta(days=i))]
    while livre(a - timedelta(days=1)):
        a -= timedelta(days=1)
    while livre(b + timedelta(days=1)):
        b += timedelta(days=1)
    return a, b, tirar


def emendas(ano: int, lista: list[dict], trabalha_sabado: bool = False, max_folgas: int = 4) -> list[dict]:
    """Para cada feriado em dia útil: o feriadão de graça (sem tirar nada) e a
    melhor emenda — a que mais dá dias a mais por dia tirado (pura).
    Ordena pela emenda que rende mais; feriadões sem custo vêm junto."""
    livres = {f["data"] for f in lista}

    def livre(d: date) -> bool:
        return d in livres or d.weekday() == 6 or (d.weekday() == 5 and not trabalha_sabado)

    resultado, vistos = [], set()
    for f in lista:
        d = f["data"]
        if d.weekday() == 6 or (d.weekday() == 5 and not trabalha_sabado):
            continue                                            # caiu no fim de semana
        a0, b0, _ = _janela(d, livre, 0, 0)
        base = (b0 - a0).days + 1
        if (a0, b0) in vistos:
            continue                                            # Carnaval: segunda e terça, mesma janela
        vistos.add((a0, b0))
        melhor = None
        for antes in range(0, 10):
            for depois in range(0, 10):
                a, b, tirar = _janela(d, livre, antes, depois)
                if not tirar or len(tirar) > max_folgas:
                    continue
                total = (b - a).days + 1
                rende = (total - base) / len(tirar)
                if melhor is None or (rende, -len(tirar)) > (melhor["rende"], -melhor["custo"]):
                    melhor = {"tirar": tirar, "de": a, "ate": b, "dias": total, "custo": len(tirar), "rende": rende}
        e = {"feriado": f, "gratis": {"de": a0, "ate": b0, "dias": base}, "emenda": None}
        if melhor and melhor["rende"] >= 2:                    # só vale se cada dia tirado rende 2 ou mais
            e["emenda"] = melhor
        resultado.append(e)
    return sorted(resultado, key=lambda x: (-(x["emenda"] or {}).get("rende", 0), -x["gratis"]["dias"]))


def _fmt(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d} ({DIAS[d.weekday()][:3]})"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "emendas").lower()
    c = cfg("feriados", PLUGIN_SETTINGS)
    locais = ler_json(ARQ, []) or []
    hoje = date.today()
    ano = int(p.get("ano") or hoje.year)
    try:
        if a == "adicionar":
            data, nome = str(p.get("data") or "").strip(), str(p.get("nome") or "Feriado local").strip()
            d, m = (int(x) for x in data.replace("-", "/").split("/")[:2])
            date(2024, m, d)
            locais = [x for x in locais if x["nome"].lower() != nome.lower()] + [{"data": f"{d:02d}/{m:02d}", "nome": nome}]
            gravar_json(ARQ, locais)
            return f"Feriado anotado: {nome}, todo {d:02d}/{m:02d}."
        if a == "remover":
            nome = str(p.get("nome") or "").lower()
            novos = [x for x in locais if nome not in x["nome"].lower()]
            gravar_json(ARQ, novos)
            return "Removido." if len(novos) < len(locais) else "Não achei esse feriado local."
        lista = feriados(ano, locais, bool(c.get("facultativos", True)))
        if a == "proximo":
            prox = next((f for f in lista + feriados(ano + 1, locais) if f["data"] >= hoje), None)
            falta = (prox["data"] - hoje).days
            return f"O próximo é {prox['nome']}, {_fmt(prox['data'])}, daqui a {falta} dias."
        if a == "lista":
            mostrar(player, f"FERIADOS {ano}", "\n".join(
                f"{_fmt(f['data'])}  {f['nome']}" + ("  (facultativo)" if f["tipo"] == "facultativo" else "")
                + ("  (local)" if f["tipo"] == "local" else "") for f in lista))
            uteis = sum(1 for f in lista if f["data"].weekday() < 5)
            return f"{len(lista)} feriados em {ano}, {uteis} em dia útil. A lista está no painel."
        inicio = hoje if ano == hoje.year else date(ano, 1, 1)
        es = [e for e in emendas(ano, lista, bool(c.get("trabalha_sabado"))) if e["gratis"]["ate"] >= inicio]
        if not es:
            return f"Não sobrou feriado em dia útil em {ano}."
        linhas = []
        for e in es:
            g, m = e["gratis"], e["emenda"]
            linha = f"{_fmt(e['feriado']['data'])} {e['feriado']['nome']}: {g['dias']} dias sem tirar nada"
            if m:
                linha += (f"  →  tirando {m['custo']} ({', '.join(_fmt(x) for x in m['tirar'])}) vira {m['dias']} dias: "
                          f"{_fmt(m['de'])} a {_fmt(m['ate'])}")
            linhas.append(linha)
        com = [e for e in es if e["emenda"]]
        tirando = sum(e["emenda"]["custo"] for e in com)
        ganhando = sum(e["emenda"]["dias"] for e in com)
        linhas += ["", f"Fazendo todas as emendas: tira {tirando} dia(s) e folga {ganhando} dias nesses feriadões."]
        mostrar(player, f"EMENDAS {ano}", "\n".join(linhas))
        if not com:
            return f"Em {ano} não tem emenda que valha a pena; os feriadões já vêm prontos. A lista está no painel."
        return "As melhores emendas: " + "; ".join(
            f"{e['feriado']['nome']}: tirando {e['emenda']['custo']} dia, {e['emenda']['dias']} dias de folga"
            for e in com[:3]) + f". No total, {tirando} dias tirados viram {ganhando} dias de folga."
    except Exception as e:
        return f"O planejador de feriados falhou: {e}"
