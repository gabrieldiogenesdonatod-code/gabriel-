"""
Eu do futuro (3.3): uma conversa com você mesmo daqui a alguns meses, feita com os SEUS números.

    "Jarvis, como eu vou estar daqui a 6 meses?"          → projeção de cada coisa que o JARVIS acompanha
    "Jarvis, fala com o meu eu do futuro"                  → mensagem do você de daqui a 6 meses
    "Jarvis, pergunta pro meu eu do futuro se a loja vai melhorar"
    "Jarvis, e se eu vender 15% a mais?"                    "Jarvis, e se eu estudar 4 horas por semana?"
    "Jarvis, mostra o gráfico do eu do futuro"             "Jarvis, sela a carta do eu do futuro"
    "Jarvis, confere o eu do futuro"                       → o quanto as projeções seladas acertaram

De onde vêm os números: caixa da loja, água, ponto, corridas, treino, hábitos, modos (o mesmo
levantamento do plugin sonhos) e as sessões de estudo do quadro. Cada assunto vira um total por
semana, e a projeção usa uma tendência AMORTECIDA (Holt com φ = 0,9): o ritmo de agora continua,
mas a subida ou a queda perde força com o tempo, para não prometer milagre nem desgraça.

É uma projeção do ritmo atual, não destino — e é isso que o JARVIS diz junto. "Selar" guarda a
projeção e cria uma cápsula do tempo que abre na data; depois, "conferir" mostra o quanto acertou.
"""

from __future__ import annotations

import html as _html
import math
import statistics as st
import time
from datetime import date, timedelta

from plugins._lote2 import P, carregar, dias_ate, guardar, norm, num1, pagina, reais, rodar

PLUGIN = P("eu_do_futuro", "Talk to your future self: projects your tracked numbers (sales, habits, study, runs) N months ahead, "
                           "what-if from now on, sealed forecasts.",
           "projecao | conversar | e_se | grafico | selar | conferir",
           "projecao: meses (default 6). conversar: meses, pergunta (optional question to the future self). e_se (from now on; "
           "for the past use the e_se plugin): serie "
           "(e.g. 'vendas', 'estudo', 'km'), mudanca (percent, e.g. '15' or '-10') OR ritmo (new weekly amount in the units "
           "projecao shows, e.g. '4' hours per week), meses. grafico: meses. selar: meses. conferir: no params.",
           "meses pergunta serie mudanca ritmo")

ALFA, BETA, PHI = 0.4, 0.2, 0.9
MIN_SEMANAS = 4
AVISO = "É uma projeção do seu ritmo atual, não destino: muda no momento em que você muda."
SEM_DADOS = ("Ainda não tenho números suficientes: preciso de pelo menos 4 semanas de algum registro (caixa da loja, água, "
             "ponto, corridas, treino, hábitos ou sessões de estudo).")
_VAZIO_E_FALTA = {"vendas da loja", "água bebida", "horas trabalhadas"}     # semana sem registro = esqueceu de anotar
_SUBIR_NEM_SEMPRE_BOM = {"horas trabalhadas"}
CONSELHOS = {
    "vendas da loja": "escolhe 3 peças paradas e faz uma promoção relâmpago, mas antes simula no gêmeo da loja",
    "água bebida": "deixa uma garrafa cheia do lado do computador e termina ela antes do almoço",
    "km corridos": "marca 3 corridas curtas na agenda; 20 minutos já contam",
    "volume de treino": "marca 3 treinos curtos na agenda; feito vale mais que perfeito",
    "horas trabalhadas": "bloqueia 2 horas de foco por dia e respeita a hora de parar",
    "tempo de estudo": "estuda 25 minutos por dia, um pomodoro, antes de abrir o celular",
    "tempo em modos de foco": "liga o modo foco profundo uma vez por dia, nem que seja por 25 minutos",
}


# ───────────────────────────────────────────────────────────── contas (puras) ───
def _semana_de(d: date) -> date:
    return d - timedelta(days=d.weekday())


def semanas(serie: dict[str, float], hoje: date, nome: str = "") -> list[tuple[date, float | None]]:
    """Total de cada semana completa (segunda a domingo) até a semana passada. A primeira semana só entra se o
    registro começou na segunda. Semana sem nenhum registro: None quando isso quer dizer 'esqueceu de anotar'
    (vendas, água, ponto) e 0 quando quer dizer 'não fez' (corrida, treino, estudo). Pura."""
    if not serie:
        return []
    baldes: dict[date, float] = {}
    dias = []
    for d, v in serie.items():
        try:
            dia, valor = date.fromisoformat(d), float(v)
        except (TypeError, ValueError):
            continue
        dias.append(dia)
        baldes[_semana_de(dia)] = baldes.get(_semana_de(dia), 0.0) + valor
    if not dias:
        return []
    primeiro = min(dias)
    s = _semana_de(primeiro) + (timedelta(7) if primeiro.weekday() else timedelta(0))
    atual, out = _semana_de(hoje), []
    while s < atual:
        out.append((s, baldes.get(s, None if nome in _VAZIO_E_FALTA else 0.0)))
        s += timedelta(7)
    return out


def holt(valores: list[float], alfa: float = ALFA, beta: float = BETA, phi: float = PHI) -> tuple[float, float, float]:
    """(nível, tendência, desvio dos erros de um passo) — suavização de Holt com tendência amortecida. Pura."""
    k = min(3, len(valores) - 1)
    nivel, tend = valores[0], ((valores[k] - valores[0]) / k if k else 0.0)
    erros = []
    for y in valores[1:]:
        previsto = nivel + phi * tend
        erros.append(y - previsto)
        novo = alfa * y + (1 - alfa) * previsto
        tend = beta * (novo - nivel) + (1 - beta) * phi * tend
        nivel = novo
    return nivel, tend, (math.sqrt(sum(e * e for e in erros) / len(erros)) if erros else 0.0)


def projetar(nivel: float, tend: float, passos: int, phi: float = PHI) -> float:
    return nivel + tend * sum(phi ** i for i in range(1, passos + 1))


def semanas_de(meses: float) -> int:
    return max(1, round(meses * 4.345))


def analisar(serie: dict[str, float], nome: str, hoje: date, meses: float) -> dict | None:
    """Projeção de uma série: ritmo agora, ritmo no fim, faixa provável, total no período e caminho semana a semana. Pura."""
    vals = [v for _, v in semanas(serie, hoje, nome) if v is not None]
    if len(vals) < MIN_SEMANAS:
        return None
    h, teto = semanas_de(meses), (7.0 if nome.startswith("hábito") else math.inf)
    nivel, tend, sd = holt(vals)
    cam = [min(teto, max(0.0, projetar(nivel, tend, i))) for i in range(1, h + 1)]
    agora, fim = st.mean(vals[-4:]), cam[-1]
    meia = 1.28 * sd * math.sqrt(1 + (h - 1) * ALFA ** 2)          # ~80% (aproximação da suavização exponencial)
    mud = (fim - agora) / agora if agora else (1.0 if fim > 0 else 0.0)
    real = abs(fim - agora) >= max(sd, 1e-9)                       # mudança menor que o ruído de uma semana não é rumo
    return {"nome": nome, "agora": agora, "fim": fim, "baixo": max(0.0, fim - meia), "alto": min(teto, fim + meia),
            "total": sum(cam), "cam": cam, "hist": vals[-26:], "sd": sd, "semanas": len(vals), "mudanca": mud,
            "rumo": "subindo" if mud >= 0.05 and real else "caindo" if mud <= -0.05 and real else "estável"}


def unidade(nome: str) -> tuple[str, float, str]:
    """(unidade, divisor, 'semana' ou 'dia') para mostrar o total semanal guardado. Pura."""
    if nome == "vendas da loja":
        return "R$", 1, "semana"
    if nome == "água bebida":
        return "ml", 7, "dia"
    if nome in ("km corridos", "volume de treino"):
        return ("km" if nome == "km corridos" else "kg"), 1, "semana"
    if nome == "horas trabalhadas":
        return "h", 1, "semana"
    if nome.startswith("hábito"):
        return "dia(s)", 1, "semana"
    if nome == "tempo de estudo" or nome.startswith("tempo em modos"):
        return "h", 60, "semana"
    return "", 1, "semana"


def _num(x: float) -> str:
    casas = 0 if abs(x) >= 100 else 1
    s = f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s[:-2] if s.endswith(",0") else s


def valor(nome: str, v_semana: float) -> str:
    """Só a quantidade, na unidade de mostrar (sem 'por semana'). Projeção em dinheiro sem centavos. Pura."""
    un, div, _ = unidade(nome)
    x = v_semana / div
    if un == "R$":
        return f"R$ {_num(round(x))}" if abs(x) >= 100 else reais(x)
    if un == "dia(s)":
        un = "dia" if round(x, 1) == 1 else "dias"
    return f"{_num(x)} {un}".strip()


def ritmo(nome: str, v_semana: float) -> str:
    return f"{valor(nome, v_semana)} por {unidade(nome)[2]}"


def total(nome: str, v: float) -> str:
    un, div, _ = unidade(nome)
    if un == "R$":
        return f"R$ {_num(round(v))}" if abs(v) >= 100 else reais(v)
    if un == "ml":
        return f"{_num(v / 1000)} litros"
    if un == "kg" and v >= 10_000:
        return f"{_num(v / 1000)} toneladas"
    return f"{_num(v / (60 if div == 60 else 1))} {'dias' if un == 'dia(s)' else un}".strip()


def linha(a: dict, meses: float) -> str:
    faixa = (f" (faixa provável {valor(a['nome'], a['baixo'])} a {ritmo(a['nome'], a['alto'])})"
             if a["alto"] - a["baixo"] > 0.02 * max(1.0, a["fim"]) else "")
    return (f"{a['nome']}: agora {ritmo(a['nome'], a['agora'])} → em {_num(meses)} {'mês' if meses == 1 else 'meses'} "
            f"{ritmo(a['nome'], a['fim'])}{faixa}, {a['rumo']}; no período, uns {total(a['nome'], a['total'])}.")


def conselho(nome: str) -> str:
    if nome.startswith("hábito"):
        return f"não quebra a corrente do '{nome[7:]}': faz a versão mínima mesmo no dia ruim"
    return CONSELHOS.get(nome, "escolhe UMA coisa pequena e faz todo dia desta semana")


def carta_offline(analises: list[dict], meses: float, metas: list[str] | None = None, pergunta: str = "") -> str:
    """A mensagem do 'você do futuro' sem IA: só com as contas. Pura."""
    bom = lambda a: a["rumo"] == "subindo" and a["nome"] not in _SUBIR_NEM_SEMPRE_BOM  # noqa: E731
    sobe = sorted([a for a in analises if bom(a)], key=lambda a: -a["mudanca"])
    cai = sorted([a for a in analises if a["rumo"] == "caindo"], key=lambda a: a["mudanca"])
    trab = [a for a in analises if a["nome"] in _SUBIR_NEM_SEMPRE_BOM and a["rumo"] == "subindo"]
    t = f"{_num(meses)} {'mês' if meses == 1 else 'meses'}"
    partes = [f"E aí, aqui é você, daqui a {t}."]
    if pergunta:
        partes.append(f"Você me perguntou: \"{pergunta.strip()[:140]}\". Eu só posso responder com o que os números de hoje mostram.")
    if sobe:
        partes.append("O que você está fazendo certo: " + "; ".join(
            f"{a['nome']}, de {valor(a['nome'], a['agora'])} para {ritmo(a['nome'], a['fim'])}" for a in sobe[:2]) + ". Não para.")
    if trab:
        partes.append(f"Você está trabalhando mais ({ritmo(trab[0]['nome'], trab[0]['fim'])}). Bom para a loja, mas descansa.")
    if cai:
        partes.append("O que me preocupa: " + "; ".join(
            f"{a['nome']}, caindo de {valor(a['nome'], a['agora'])} para {ritmo(a['nome'], a['fim'])}" for a in cai[:2]) + ".")
    if not sobe and not cai and not trab:
        partes.append("Está tudo no mesmo ritmo. Estável é bom, mas é aqui que dá para escolher uma coisa e subir de nível.")
    if metas:
        partes.append("Suas metas agora: " + "; ".join(metas[:3]) + ".")
    alvo = cai[0]["nome"] if cai else (sobe[0]["nome"] if sobe else (analises[0]["nome"] if analises else ""))
    partes.append(f"Um conselho para esta semana: {conselho(alvo)}.")
    return " ".join(partes)


def comparar(selo: dict, series_atuais: dict, hoje: date) -> list[tuple[str, float, float, int]]:
    """Projeção selada x o que aconteceu, só nas semanas já completas: (série, previsto/semana, real/semana, semanas). Pura."""
    inicio, atual, out = date.fromisoformat(selo["inicio"]), _semana_de(hoje), []
    for nome, info in selo.get("series", {}).items():
        reais_sem = dict(semanas(series_atuais.get(nome, {}), hoje, nome))
        pares = []
        for i, prev in enumerate(info.get("cam", [])):
            seg = inicio + timedelta(7 * i)
            if seg >= atual:
                break
            if reais_sem.get(seg) is not None:
                pares.append((prev, reais_sem[seg]))
        if pares:
            out.append((nome, st.mean(p for p, _ in pares), st.mean(r for _, r in pares), len(pares)))
    return out


def svg(a: dict, meses: float, largura: int = 680, altura: int = 190) -> str:
    """Gráfico de uma série: passado (linha cheia), projeção (tracejada) e faixa provável. Pura."""
    hist, cam, n_h = a["hist"], a["cam"], len(a["hist"])
    teto = 7.0 if a["nome"].startswith("hábito") else math.inf
    meias = [1.28 * a["sd"] * math.sqrt(1 + i * ALFA ** 2) for i in range(len(cam))]
    topo = max(hist + [min(teto, c + m) for c, m in zip(cam, meias)] + [1e-9]) * 1.08
    n = n_h + len(cam)
    X = lambda i: 66 + i * (largura - 80) / max(1, n - 1)  # noqa: E731
    Y = lambda v: altura - 28 - max(0.0, v) / topo * (altura - 52)  # noqa: E731
    pts = lambda vs, ini: " ".join(f"{X(ini + i):.1f},{Y(v):.1f}" for i, v in enumerate(vs))  # noqa: E731
    cima = [f"{X(n_h + i):.1f},{Y(min(teto, c + m)):.1f}" for i, (c, m) in enumerate(zip(cam, meias))]
    baixo = [f"{X(n_h + i):.1f},{Y(max(0.0, c - m)):.1f}" for i, (c, m) in reversed(list(enumerate(zip(cam, meias))))]
    hoje_x = X(n_h - 0.5)
    titulo = _html.escape(f"{a['nome']}: agora {ritmo(a['nome'], a['agora'])} → em {_num(meses)} meses {ritmo(a['nome'], a['fim'])}")
    return (f"<h3 style='margin:18px 0 4px'>{titulo}</h3>"
            f"<svg viewBox='0 0 {largura} {altura}' width='100%' role='img' aria-label='{titulo}' style='max-width:{largura}px'>"
            f"<line x1='66' y1='{altura - 28}' x2='{largura - 14}' y2='{altura - 28}' stroke='#999'/>"
            f"<text x='4' y='{Y(topo / 1.08) + 4:.0f}' font-size='11' fill='#666'>{_html.escape(valor(a['nome'], topo / 1.08))}</text>"
            f"<text x='4' y='{altura - 24}' font-size='11' fill='#666'>0</text>"
            f"<polygon points='{' '.join(cima + baixo)}' fill='rgba(232,89,12,.16)'/>"
            f"<polyline points='{pts(hist, 0)}' fill='none' stroke='#1f6feb' stroke-width='2.4'/>"
            f"<polyline points='{pts([hist[-1]] + cam, n_h - 1)}' fill='none' stroke='#e8590c' stroke-width='2.4' stroke-dasharray='6 5'/>"
            f"<line x1='{hoje_x:.1f}' y1='14' x2='{hoje_x:.1f}' y2='{altura - 28}' stroke='#888' stroke-dasharray='2 3'/>"
            f"<text x='{hoje_x + 4:.0f}' y='24' font-size='11' fill='#666'>hoje</text>"
            f"<text x='{largura - 14}' y='{altura - 10}' font-size='11' fill='#666' text-anchor='end'>em {_num(meses)} meses</text>"
            f"<text x='66' y='{altura - 10}' font-size='11' fill='#666'>{len(hist)} semanas atrás</text></svg>")


# ───────────────────────────────────────────────────────────── dados ───
def _series() -> dict[str, dict[str, float]]:
    s: dict[str, dict[str, float]] = {}
    try:
        from plugins.sonhos import series
        s.update(series())
    except Exception as e:
        print(f"[EuDoFuturo] séries: {e}")
    try:
        est: dict[str, float] = {}
        for h in carregar("estudos", {}).get("historico") or []:
            est[h["dia"]] = est.get(h["dia"], 0.0) + float(h.get("minutos") or 0)
        if len(est) >= 3:
            s["tempo de estudo"] = est
    except Exception:
        pass
    return s


def _metas() -> list[str]:
    try:
        from plugins.metas_pessoais import M, percentual
        return [f"{m.get('nome') or k} {percentual(m)}%" + (f" com {dias_ate(m['prazo'])} dia(s) de prazo" if m.get("prazo") else "")
                for k, m in M.tudo().items()]
    except Exception:
        return []


def _meses(p) -> float:
    return max(1.0, min(24.0, num1(p, "meses", 6) or 6))


def analises(meses: float, hoje: date | None = None) -> list[dict]:
    hoje = hoje or date.today()
    out = [a for nome, serie in _series().items() if (a := analisar(serie, nome, hoje, meses))]
    return sorted(out, key=lambda a: (not a["nome"].startswith("vendas"), -abs(a["mudanca"])))


def _achar(an: list[dict], pedido: str) -> dict | None:
    q = norm(pedido)
    sin = {"estud": "estudo", "vend": "vendas", "loja": "vendas", "corr": "km", "agua": "agua", "trein": "treino",
           "trabalh": "horas", "foco": "foco"}
    for raiz, alvo in sin.items():
        if raiz in q:
            q = alvo
            break
    return next((a for a in an if q and q in norm(a["nome"])), None)


# ───────────────────────────────────────────────────────────── ações ───
def _projecao(p, pl):
    meses = _meses(p)
    an = analises(meses)
    if not an:
        return SEM_DADOS
    return f"Se tudo continuar no ritmo de agora, daqui a {_num(meses)} meses:\n" + "\n".join(linha(a, meses) for a in an[:8]) + f"\n{AVISO}"


def _conversar(p, pl):
    meses, pergunta = _meses(p), str(p.get("pergunta") or "").strip()
    an = analises(meses)
    if not an:
        return SEM_DADOS
    metas = _metas()
    texto = None
    try:
        from plugins import _ia
        pedido = (f"Escreva uma mensagem curta (até 110 palavras), em português do Brasil, falada pelo PRÓPRIO usuário daqui a "
                  f"{_num(meses)} meses para o eu de hoje, num tom de amigo: direto, carinhoso e com um pouco de humor. Use SOMENTE "
                  "os números abaixo, que são projeções do ritmo atual e não destino; não invente acontecimentos, pessoas, valores "
                  "ou conquistas. Elogie o que sobe, alerte com carinho o que cai e termine com UM conselho prático para esta "
                  "semana. Não use listas nem emojis.\n\nProjeções:\n" + "\n".join(linha(a, meses) for a in an[:8])
                  + ("\nMetas: " + "; ".join(metas[:4]) if metas else "")
                  + (f"\n\nO usuário perguntou ao eu do futuro: \"{pergunta[:200]}\". Responda isso primeiro, com honestidade: "
                     "se os números não dizem, diga que não dá para saber." if pergunta else ""))
        texto = _ia.perguntar(pedido, inteligente=True, segundos=30)
    except Exception as e:
        print(f"[EuDoFuturo] IA: {e}")
    texto = (texto or carta_offline(an, meses, metas, pergunta)).strip()
    return f"Mensagem do você de daqui a {_num(meses)} meses:\n{texto}\n({AVISO})"


def _e_se(p, pl):
    meses = _meses(p)
    an = analises(meses)
    if not an:
        return SEM_DADOS
    a = _achar(an, str(p.get("serie") or "")) or (an[0] if len(an) == 1 else None)
    if not a:
        return "De qual número? Tenho: " + ", ".join(x["nome"] for x in an) + "."
    _, div, _ = unidade(a["nome"])
    if str(p.get("ritmo") or "").strip():                 # novo ritmo, na unidade que a projeção mostra
        novo_sem = max(0.0, num1(p, "ritmo", 0)) * div
        novo_total = novo_sem * len(a["cam"])
    else:
        pct = num1(p, "mudanca", 0)
        if not pct:
            return "Quanto a mais (ou a menos)? Diga em porcentagem, ou o novo ritmo por semana."
        novo_sem, novo_total = a["fim"] * (1 + pct / 100), a["total"] * (1 + pct / 100)
    dif = novo_total - a["total"]
    sinal = "a mais" if dif >= 0 else "a menos"
    return (f"{a['nome']}: no ritmo de agora, em {_num(meses)} meses dá uns {total(a['nome'], a['total'])}. "
            f"Mudando para {ritmo(a['nome'], novo_sem)}, dá uns {total(a['nome'], novo_total)}: "
            f"{total(a['nome'], abs(dif))} {sinal}. {AVISO}")


def _grafico(p, pl):
    meses = _meses(p)
    an = analises(meses)
    if not an:
        return SEM_DADOS
    corpo = ("<p>Linha azul: o que aconteceu, semana a semana. Tracejado laranja: para onde o ritmo de agora leva. "
             f"Faixa: onde o número provavelmente vai cair. {_html.escape(AVISO)}</p>" + "".join(svg(a, meses) for a in an[:8]))
    arq = pagina("Eu do futuro", f"Eu do futuro — daqui a {_num(meses)} meses", corpo)
    return f"Gráfico aberto ({len(an[:8])} assunto(s)). Arquivo: {arq}"


def _selar(p, pl):
    meses = _meses(p)
    hoje = date.today()
    an = analises(meses, hoje)
    if not an:
        return SEM_DADOS
    carta = carta_offline(an, meses, _metas())
    d = carregar("eu_do_futuro", {"selos": []})
    d.setdefault("selos", []).append({"ts": time.time(), "dia": hoje.isoformat(), "meses": meses, "inicio": _semana_de(hoje).isoformat(),
                                       "series": {a["nome"]: {"cam": [round(c, 2) for c in a["cam"]], "agora": round(a["agora"], 2)}
                                                  for a in an}})
    d["selos"] = d["selos"][-30:]
    guardar("eu_do_futuro", d)
    capsula = ""
    try:
        from plugins import capsula_tempo
        msg = (f"Eu do futuro, selado em {hoje:%d/%m/%Y}.\n{carta}\n\nAs projeções eram:\n" + "\n".join(linha(a, meses) for a in an[:8])
               + "\n\nDiga 'Jarvis, confere o eu do futuro' para ver o quanto acertei.")
        quando = f"em {int(round(meses))} meses"
        abre = capsula_tempo.data_de(quando)
        r = capsula_tempo.run({"action": "criar", "mensagem": msg, "quando": quando})
        if "lacrada" in r.lower() and abre:
            capsula = f" Também virou uma cápsula do tempo que abre em {abre:%d/%m/%Y}."
    except Exception as e:
        print(f"[EuDoFuturo] cápsula: {e}")
    return (f"Selado: guardei a projeção de {len(an)} assunto(s) para daqui a {_num(meses)} meses.{capsula} "
            "Quando quiser, diga 'confere o eu do futuro' e eu comparo com o que aconteceu.")


def _conferir(p, pl):
    selos = carregar("eu_do_futuro", {"selos": []}).get("selos") or []
    if not selos:
        return "Nenhuma projeção selada ainda. Diga 'sela a carta do eu do futuro'."
    hoje, series_atuais, out = date.today(), _series(), []
    for s in selos[-5:]:
        comp = comparar(s, series_atuais, hoje)
        quando = date.fromisoformat(s["dia"]).strftime("%d/%m/%Y")
        if not comp:
            out.append(f"Selo de {quando}: ainda não fechou nenhuma semana inteira para comparar.")
            continue
        partes = []
        for nome, prev, real, k in comp:
            dif = (real - prev) / prev * 100 if prev else 0.0
            partes.append(f"{nome}: previ {ritmo(nome, prev)}, foi {ritmo(nome, real)} ({dif:+.0f}% em {k} semana(s))")
        out.append(f"Selo de {quando} ({_num(s['meses'])} meses): " + "; ".join(partes) + ".")
    return "\n".join(out)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"projecao": _projecao, "conversar": _conversar, "e_se": _e_se, "grafico": _grafico,
                              "selar": _selar, "conferir": _conferir}, player, "Eu do futuro")
