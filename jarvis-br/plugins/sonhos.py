"""
Sonhos (2.20): de madrugada, enquanto você dorme, o JARVIS "sonha" — cruza os dados de todos os
plugins (vendas da loja, água, hábitos, ponto, corrida, treino, modos) e procura padrões que
ninguém pediu. De manhã ele conta o que descobriu.

Exemplos do que ele pode descobrir:
    "Nas sextas a loja vende 42% mais que a média."
    "Nos dias com mais água bebida, as horas trabalhadas ficam 18% maiores."
    "Depois de um dia de corrida, o volume de treino no dia seguinte cai 30%."
    "Ontem as vendas da loja foram muito acima do normal."

É padrão nos seus números, não prova de causa: ele avisa isso. Tudo roda no seu PC, sem internet
e sem gastar token. Sonha às 3h (se o PC estiver parado) e conta de manhã, quando você voltar.
"""

from __future__ import annotations

import random
import statistics as st
import time
from datetime import date, datetime, timedelta

from plugins import _lote2
from plugins._comum import falar, mostrar
from plugins._lote2 import Colecao, P, carregar, guardar, rodar

PLUGIN = P("sonhos", "JARVIS 'dreams' at night: cross-checks data from all plugins (sales, water, habits, work hours, runs, training, modes) "
           "and finds patterns nobody asked for; tells them in the morning.",
           "sonhar | ultimo | diario | dados",
           "sonhar: dream now (find patterns). ultimo: last dream. diario: past dreams. dados: which data series it can see.",
           "")

SEMANA = ["Nas segundas", "Nas terças", "Nas quartas", "Nas quintas", "Nas sextas", "Nos sábados", "Nos domingos"]
T_MIN = 2.5            # filtro rápido antes do teste de permutação
ALFA = 0.05            # chance de alarme falso por NOITE (dividida pelo número de hipóteses testadas)
MIN_DIAS = 10          # menos que isso é chute


# ─────────────────────────────────────────────── séries (data → valor) ───
def series() -> dict[str, dict[str, float]]:
    """Junta o que cada plugin guardou, uma série por assunto. Plugin sem dado não entra."""
    s: dict[str, dict[str, float]] = {}

    def soma(nome, dia, v):
        s.setdefault(nome, {})
        s[nome][dia] = s[nome].get(dia, 0.0) + float(v)

    for dia, d in (carregar("caixa", {}).get("dias") or {}).items():
        for v, _ in d.get("vendas", []):
            soma("vendas da loja", dia, v)
    agua = _lote2.ler_json(_lote2.PASTA / "agua.json", {}) or {}
    for dia, v in agua.items():
        if dia[:2] == "20" and isinstance(v, (int, float)):
            soma("água bebida", dia, v)
    try:
        from plugins.ponto import horas
        for dia, b in (carregar("ponto", {}).get("dias") or {}).items():
            if len(b) >= 2 and len(b) % 2 == 0:
                soma("horas trabalhadas", dia, horas(b))
    except Exception:
        pass
    for x in carregar("corridas", []):
        soma("km corridos", x["d"], x["km"])
    for x in _lote2.ler_json(_lote2.PASTA / "treino.json", []) or []:
        soma("volume de treino", x["d"], x["s"] * x["r"] * x["kg"])
    for h in Colecao("sequencias").tudo().values():
        dias = sorted(h.get("dias") or [])
        if len(dias) >= 3:                       # hábito vira 0/1 a partir do primeiro dia marcado
            ini, feitos = date.fromisoformat(dias[0]), set(dias)
            for k in range((date.today() - ini).days + 1):
                d = (ini + timedelta(k)).isoformat()
                s.setdefault(f"hábito {h['nome']}", {})[d] = 1.0 if d in feitos else 0.0
    try:
        from plugins import modos
        for x in modos.historico():
            if x.get("dur"):
                soma("tempo em modos de foco" if x["m"] in ("foco_profundo", "estudo", "programador", "debug") else "tempo em modos",
                     time.strftime("%Y-%m-%d", time.localtime(x["t"])), x["dur"] / 60)
    except Exception:
        pass
    return {k: v for k, v in s.items() if len(v) >= 3}


# ─────────────────────────────────────────────── descobertas (puras) ───
def _pct(a: float, b: float) -> float:
    return (a - b) / abs(b) * 100 if b else 0.0


def postos(a: list[float], b: list[float]) -> tuple[list[float], list[float]]:
    """Troca cada valor pela posição no ranking dos dois grupos juntos (empates = média). Pura."""
    pos: dict = {}
    for i, v in enumerate(sorted(a + b)):
        pos.setdefault(v, []).append(i)
    r = {v: st.mean(ix) for v, ix in pos.items()}
    return [r[v] for v in a], [r[v] for v in b]


def forca(a: list[float], b: list[float]) -> float:
    """Teste t de Welch sobre os postos: um dia absurdo não infla a variação. Pura."""
    if len(a) < 3 or len(b) < 3:
        return 0.0
    a, b = postos(a, b)
    va, vb = st.variance(a), st.variance(b)
    erro = (va / len(a) + vb / len(b)) ** 0.5
    return abs(st.mean(a) - st.mean(b)) / erro if erro else 0.0


def acaso(a: list[float], b: list[float], limite: float, rng: random.Random, voltas: int = 2000) -> bool:
    """Teste de permutação por postos: embaralha os dois grupos e vê se o acaso produz uma diferença tão grande.
    True = a diferença PODE ser acaso (com chance acima de 'limite'). Pura (com rng)."""
    a, b = postos(a, b)                                     # posição no ranking: um dia absurdo não distorce o teste
    obs, tudo, n = abs(st.mean(a) - st.mean(b)), a + b, len(a)
    maximo, vezes = limite * voltas, 0
    for _ in range(voltas):
        rng.shuffle(tudo)
        if abs(st.mean(tudo[:n]) - st.mean(tudo[n:])) >= obs:
            vezes += 1
            if vezes > maximo:
                return True
    return False


def _mais(p: float) -> str:
    return f"{abs(p):.0f}% a {'mais' if p > 0 else 'menos'}"


def dia_da_semana(nome: str, serie: dict[str, float]) -> list[tuple[float, str]]:
    """O dia da semana que mais destoa da média (só com 3+ semanas de dados)."""
    if len(serie) < 21 or nome.startswith("hábito"):
        return []
    por: dict[int, list[float]] = {}
    for d, v in serie.items():
        por.setdefault(date.fromisoformat(d).weekday(), []).append(v)
    out = []
    for wd, vals in por.items():
        resto = [v for d, v in serie.items() if date.fromisoformat(d).weekday() != wd]
        if len(vals) >= 3:
            p = _pct(st.median(vals), st.median(resto))         # comparado com os outros dias, não com ele mesmo
            if abs(p) >= 15 and len(vals) >= 4 and forca(vals, resto) >= T_MIN:
                out.append((min(abs(p), 80) * 1.2, f"{SEMANA[wd]} há {_mais(p)} de {nome} que num dia comum.", vals, resto))
    return sorted(out, reverse=True)[:1]


def _aparada(vals: list[float]) -> float:
    """Média sem os 10% mais altos e mais baixos: robusta a dia fora da curva e a valores que pulam."""
    v = sorted(vals)
    k = len(v) // 10
    return st.mean(v[k:len(v) - k] or v)


def _grupos(pares):
    """Dias com X acima e abaixo da mediana; os empatados bem no meio ficam de fora (não são nem muito nem pouco)."""
    corte = st.median(v for v, _ in pares)
    alto, baixo = [vy for vx, vy in pares if vx > corte], [vy for vx, vy in pares if vx < corte]
    if len(baixo) < 3:                       # muitos empates no meio: o meio vai para o lado que faltar
        baixo = [vy for vx, vy in pares if vx <= corte]
    elif len(alto) < 3:
        alto = [vy for vx, vy in pares if vx >= corte]
    return alto, baixo


def _efeito(pares: list[tuple[float, float]]) -> float | None:
    alto, baixo = _grupos(pares)
    if len(alto) < 3 or len(baixo) < 3 or not _aparada(baixo):
        return None
    return _pct(_aparada(alto), _aparada(baixo))


def cruzar(nx: str, x: dict[str, float], ny: str, y: dict[str, float], atraso: int = 0) -> list[tuple[float, str]]:
    """Compara Y nos dias em que X foi alto com os dias em que X foi baixo (X de 'atraso' dias antes).
    Só vale se o efeito aparecer na primeira E na segunda metade dos dias, no mesmo sentido."""
    pares = []
    for d in sorted(x):
        dy = (date.fromisoformat(d) + timedelta(atraso)).isoformat()
        if dy in y:
            pares.append((x[d], y[dy]))
    if len(pares) < MIN_DIAS:
        return []
    p = _efeito(pares)
    meio = len(pares) // 2
    p1, p2 = _efeito(pares[:meio]), _efeito(pares[meio:])
    if p is None or p1 is None or p2 is None or abs(p) < 20 or p1 * p2 <= 0 or min(abs(p1), abs(p2)) < 10 \
            or forca(*_grupos(pares)) < T_MIN:
        return []
    se_habito = nx.startswith("hábito")
    if se_habito:
        sujeito = f"Nos dias em que você cumpre o {nx}" if not atraso else f"No dia seguinte ao {nx} cumprido"
    else:
        sujeito = f"Nos dias com mais {nx}" if not atraso else f"No dia seguinte a um dia com mais {nx}"
    return [(min(abs(p), 80) * min(1.0, len(pares) / 30), f"{sujeito}, há {_mais(p)} de {ny} (vi isso em {len(pares)} dias).",
             *_grupos(pares))]


def anomalia(nome: str, serie: dict[str, float], ref: date) -> list[tuple[float, str]]:
    ontem = (ref - timedelta(1)).isoformat()
    resto = [v for d, v in serie.items() if d != ontem]
    if ontem not in serie or len(resto) < MIN_DIAS or nome.startswith("hábito"):
        return []
    m, dp = st.median(resto), st.pstdev(resto)
    if not dp:
        return []
    z = (serie[ontem] - m) / dp
    if abs(z) < 2.5:
        return []
    return [(min(abs(z), 4) * 10, f"Ontem foi um dia fora da curva: houve {_mais(_pct(serie[ontem], m))} de {nome} que num dia comum.",
             None, None)]


def sonhar_com(dados: dict[str, dict[str, float]], ref: date, n: int = 3, rng: random.Random | None = None) -> list[str]:
    """As n descobertas mais fortes que sobrevivem ao teste de permutação, sem repetir assunto. Pura (com rng)."""
    rng = rng or random.Random(ref.toordinal())
    candidatos, hipoteses = [], 0
    nomes = sorted(dados)
    for a in nomes:
        hipoteses += 7 if len(dados[a]) >= 21 and not a.startswith("hábito") else 0
        for c in dia_da_semana(a, dados[a]) + anomalia(a, dados[a], ref):
            candidatos.append((*c, {a}))
        for b in nomes:
            if a != b:
                for atraso in ((0, 1) if a < b else (1,)):
                    hipoteses += 1
                    for c in cruzar(a, dados[a], b, dados[b], atraso):
                        candidatos.append((*c, {a, b}))
    limite = ALFA / max(1, hipoteses)
    out, usados = [], set()
    for nota, txt, g1, g2, assuntos in sorted(candidatos, key=lambda x: -x[0]):
        chave = {("ontem", t) for t in assuntos} if txt.startswith("Ontem") else assuntos   # dia fora da curva é outro tipo
        if chave <= usados or (g1 is not None and acaso(list(g1), list(g2), limite, rng, max(2000, int(3 / limite)))):
            continue
        out.append(txt)
        usados |= chave
        if len(out) >= n:
            break
    return out


# ─────────────────────────────────────────────── sonho, diário e entrega ───
def sonhar() -> dict:
    dados = series()
    achados = sonhar_com(dados, date.today())
    sonho = {"quando": time.time(), "dia": date.today().isoformat(), "achados": achados,
             "series": {k: len(v) for k, v in dados.items()}, "entregue": False}
    diario = carregar("sonhos", [])
    diario.append(sonho)
    guardar("sonhos", diario[-120:])
    return sonho


def contar(sonho: dict) -> str:
    if not sonho.get("achados"):
        dias = max(sonho.get("series", {}).values() or [0])
        return ("Sonhei com os seus números, mas ainda não achei nenhum padrão forte. "
                f"Tenho no máximo {dias} dia(s) de dados; com umas três semanas de uso eu começo a descobrir coisas.")
    return "Esta noite eu sonhei com os seus números e descobri:\n- " + "\n- ".join(sonho["achados"]) + \
        "\n(São padrões nos seus dados, não certeza de causa.)"


def passo(player) -> None:
    """Uma volta do relógio central (a cada 5 min): sonha às 3h com o PC parado; conta de manhã."""
    agora, diario = datetime.now(), carregar("sonhos", [])
    ult = diario[-1] if diario else {}
    if agora.hour == 3 and ult.get("dia") != date.today().isoformat():
        try:
            from plugins.linha_do_tempo import ocioso_segundos
            parado = ocioso_segundos() > 1200
        except Exception:
            parado = True
        if parado:
            sonhar()
            return
    if ult and not ult.get("entregue") and ult.get("achados") and 6 <= agora.hour < 13 \
            and time.time() - ult.get("quando", 0) < 14 * 3600:
        ult["entregue"] = True
        guardar("sonhos", diario)
        mostrar(player, "O QUE EU SONHEI", contar(ult))
        falar(player, "[SONHO] Dê bom dia e conte, como quem conta um sonho, a descoberta mais interessante: "
                      f"{ult['achados'][0]} Diga que as outras estão no painel. Não chame nenhuma ferramenta.")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("sonhos", lambda: passo(player), a_cada_s=300, primeira_em_s=90)


def _go(p, pl):
    a = p["action"]
    if a == "sonhar":
        return contar(sonhar())
    if a == "dados":
        s = series()
        return ("Vejo: " + ", ".join(f"{k} ({len(v)} dias)" for k, v in s.items()) + ".") if s else \
            "Ainda não tenho dados. Use o caixa da loja, a água, os hábitos, o ponto, a corrida ou o treino e eu começo a sonhar."
    diario = carregar("sonhos", [])
    if not diario:
        return "Ainda não sonhei. Diga 'sonhar' para eu tentar agora."
    if a == "ultimo":
        return contar(diario[-1])
    return "\n".join(f"{s['dia']}: " + (" | ".join(s["achados"]) or "nada forte") for s in diario[-10:])


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("sonhar ultimo diario dados".split(), _go), player, "Sonhos")
