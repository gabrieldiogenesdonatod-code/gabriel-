"""
Metacognição (fork PT-BR 3.6) — o JARVIS mede o quanto pode confiar em si mesmo.

Quase toda IA fala com a mesma firmeza quando acerta e quando erra. O JARVIS mede:

  • CÉREBRO LOCAL, em sombra: a cada pedido que o Gemini resolveu com uma ferramenta, o cérebro local
    responde por dentro "o que EU teria feito?" — antes de aprender com aquele pedido. Comparando com o
    que foi feito de verdade, sai o placar: quanto ele acerta, quanto acertaria se agisse sozinho, e se a
    certeza que ele declara combina com o acerto (calibração).
  • PREVISÕES: junta num placar só o erro medido do oráculo de vendas, do eu do futuro, do gêmeo da loja,
    do motor de probabilidades e do cérebro do organismo — com a tendência (melhorando ou piorando).

EVOLUÇÃO CONTROLADA — melhora só com prova e com o seu SIM:
  1. Quando a sombra mostra que o cérebro acertaria frases PARECIDAS com as que você já usou (piso de
     confiança de 85% com pelo menos 20 casos; piso de Wilson, que é pessimista de propósito), ele
     PROPÕE passar a fazer essas sozinho. Não liga nada: propõe.
  2. Só você aprova ("Jarvis, aprova a evolução do cérebro"). Vale só para ferramentas livres.
  3. Se depois de promovido ele errar 3 das últimas 12, ele mesmo se REBAIXA e avisa — tirar
     autonomia não precisa de permissão.
  Proposta, aprovação e rebaixamento ficam provados no livro-razão.

Tudo é conta sobre o que aconteceu no seu PC; nada sai dele. No modo anônimo nada é medido.
Arquivo: memory/metacognicao.json.
"""

from __future__ import annotations

import json
import math
import statistics as st
import threading
import time
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / "memory" / "metacognicao.json"
MAX_REGISTROS = 800
PROPRIA = "propria"            # o cérebro fez sozinho por semelhança (depois da sua aprovação): acerto até você corrigir
MIN_CASOS, PISO_PROMOVER = 20, 0.85
JANELA_REBAIXAR, ERROS_REBAIXAR = 12, 3
FAIXAS = ((0.0, 0.2), (0.2, 0.5), (0.5, 0.8), (0.8, 1.01))
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────── puras ───
def wilson(acertos: int, n: int, z: float = 1.96) -> float:
    """Piso do intervalo de Wilson: 'com o que vi, o acerto de verdade é pelo menos isto'. Pura."""
    if n <= 0:
        return 0.0
    p = acertos / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def tendencia(erros: list[float]) -> str:
    """Erro caindo = 'melhorando'. Compara a primeira metade com a segunda. Pura."""
    if len(erros) < 4:
        return "—"
    meio = len(erros) // 2
    antes, depois = st.mean(erros[:meio]), st.mean(erros[meio:])
    if not antes:
        return "estável" if not depois else "piorando"
    return "melhorando" if depois < antes * 0.85 else "piorando" if depois > antes * 1.15 else "estável"


def tipo_de(normal: dict, simulado: dict) -> str:
    """Em que situação o cérebro estava naquele pedido. Pura."""
    if normal.get("reflexo") and not normal.get("semelhanca"):
        return "reflexo"                                   # frase conhecida: ele já faz sozinho hoje
    if (normal.get("reflexo") and normal.get("semelhanca")) or (simulado.get("reflexo") and simulado.get("semelhanca")):
        return "parecida"                                  # por semelhança: faria com a evolução ligada (ou já faz, se você aprovou)
    return "palpite" if normal.get("ferramenta") else "nada"


def placar_de(regs: list[list]) -> dict:
    """Placar do cérebro a partir dos registros [ts, tipo, certeza, acertou_ferramenta, exato]. Pura.
    O que ele fez sozinho (PROPRIA) fica à parte: não é medição, porque ninguém conferiu — só você, quando corrige."""
    sozinho = [r for r in regs if r[1] == PROPRIA]
    regs = [r for r in regs if r[1] != PROPRIA]

    def bloco(tipo):
        rs = [r for r in regs if r[1] == tipo]
        ac = sum(1 for r in rs if r[4])
        return {"n": len(rs), "acertos": ac, "taxa": ac / len(rs) if rs else None, "piso": wilson(ac, len(rs))}
    com_palpite = [r for r in regs if r[1] != "nada"]
    cal = []
    for lo, hi in FAIXAS:
        rs = [r for r in com_palpite if lo <= r[2] < hi]
        if rs:
            cal.append({"faixa": (lo, min(hi, 1.0)), "n": len(rs), "certeza": st.mean(r[2] for r in rs),
                        "acerto": sum(1 for r in rs if r[3]) / len(rs)})
    return {"n": len(regs), "sabia": len(com_palpite),
            "top1": (sum(1 for r in com_palpite if r[3]) / len(com_palpite)) if com_palpite else None,
            "reflexo": bloco("reflexo"), "parecida": bloco("parecida"), "palpite": bloco("palpite"), "calibracao": cal,
            "sozinho": {"n": len(sozinho), "corrigidos": sum(1 for r in sozinho if not r[4])}}


def decisao(placar: dict, ligada: bool, recentes_parecida: list[int], proposta_aberta: bool, bloqueada: bool) -> str:
    """'propor' | 'rebaixar' | 'nada'. Pura.
    recentes_parecida: 1/0 (acertou/errou) dos casos parecidos DESDE a promoção, do mais velho ao mais novo — os que o
    Gemini resolveu (medidos em sombra) e os que o cérebro fez sozinho (erro = você corrigiu)."""
    if ligada:
        ult = recentes_parecida[-JANELA_REBAIXAR:]
        return "rebaixar" if len(ult) - sum(ult) >= ERROS_REBAIXAR else "nada"
    par = placar["parecida"]
    if not proposta_aberta and not bloqueada and par["n"] >= MIN_CASOS and par["piso"] >= PISO_PROMOVER:
        return "propor"
    return "nada"


# ─────────────────────────────────────────────────────────── arquivo ───
def _ler() -> dict:
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _gravar(d: dict) -> None:
    try:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        tmp = ARQ.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ARQ)
    except OSError:
        pass


def _agora() -> float:
    """Relógio dos registros, arredondado PARA BAIXO: o que acontece depois da aprovação nunca fica "antes" dela."""
    return int(time.time() * 1000) / 1000


def _livro(acao: str, dados: dict) -> None:
    try:
        from core import livro_razao
        livro_razao.registrar("evolucao", {"acao": acao, **dados})
    except Exception:
        pass


# ─────────────────────────────────────────────────────────── cérebro em sombra ───
def sombra_cerebro(ferramenta: str, args: dict, normal: dict, simulado: dict) -> dict | None:
    """Um pedido resolvido de verdade (ferramenta, args) x o que o cérebro teria feito. Guarda e reavalia a evolução."""
    tipo = tipo_de(normal, simulado)
    palpite = simulado if tipo == "parecida" else normal
    acertou = int(palpite.get("ferramenta") == ferramenta)
    exato = int(acertou and (palpite.get("args") or {}) == (args or {}))
    with _lock:
        d = _ler()
        d.setdefault("cerebro", []).append([_agora(), tipo, float(palpite.get("confianca") or 0.0), acertou, exato])
        del d["cerebro"][:-MAX_REGISTROS]
        _gravar(d)
    feito = avaliar_evolucao()
    if feito:
        _contar(feito)
    return feito


def reflexo_proprio(decisao: dict) -> bool:
    """O cérebro agiu sozinho. Se foi por semelhança (a evolução aprovada), anota como acerto — até você corrigir.
    Devolve True quando anotou."""
    if not (decisao.get("reflexo") and decisao.get("semelhanca")):
        return False
    with _lock:
        d = _ler()
        d.setdefault("cerebro", []).append([_agora(), PROPRIA, float(decisao.get("confianca") or 0.0), 1, 1])
        del d["cerebro"][:-MAX_REGISTROS]
        _gravar(d)
    return True


def reflexo_corrigido() -> dict | None:
    """Você corrigiu o que o cérebro fez sozinho numa frase parecida: aquele acerto vira erro e a evolução é reavaliada."""
    with _lock:
        d = _ler()
        alvo = next((r for r in reversed(d.get("cerebro", [])) if r[1] == PROPRIA and r[4]), None)
        if alvo is None:
            return None
        alvo[3] = alvo[4] = 0
        _gravar(d)
    feito = avaliar_evolucao()
    if feito:
        _contar(feito)
    return feito


def texto_de(feito: dict) -> str:
    """A proposta ou o rebaixamento em português. Pura."""
    if feito["acao"] == "proposta":
        return (f"Medi o meu cérebro local: em {feito['n']} pedidos parecidos com os que você já usou, eu teria acertado "
                f"{feito['acertos']}. Posso passar a fazer esses sozinho? Diga 'aprova a evolução do cérebro' ou 'recusa a evolução'.")
    return (f"Errei {feito['erros']} das últimas {feito['de']} frases parecidas, então desliguei sozinho o reflexo por semelhança. "
            "Volto a medir do zero.")


def _contar(feito: dict) -> None:
    try:
        from plugins._comum import avisar
        avisar(None, texto_de(feito), "EVOLUÇÃO")
    except Exception as e:
        print(f"[Metacognição] aviso: {e}")


def placar_cerebro() -> dict:
    return placar_de(_ler().get("cerebro", []))


def proposta() -> dict | None:
    return _ler().get("proposta")


def avaliar_evolucao(agora: float | None = None) -> dict | None:
    """Propõe a evolução (não liga) ou rebaixa (liga o freio sozinho). Devolve o que fez, ou None."""
    from core import cerebro
    agora = agora or time.time()
    with _lock:
        d = _ler()
        regs = d.get("cerebro", [])
        ligada = cerebro.semelhanca_ligada()
        desde = d.get("promovido_em") or 0
        recentes = [r[4] for r in regs if r[1] in ("parecida", PROPRIA) and r[0] >= desde] if ligada else []
        pl = placar_de(regs)
        oque = decisao(pl, ligada, recentes, bool(d.get("proposta")), agora < (d.get("nao_propor_ate") or 0))
        if oque == "propor":
            par = pl["parecida"]
            d["proposta"] = {"ts": agora, "n": par["n"], "acertos": par["acertos"], "piso": round(par["piso"], 3)}
            _gravar(d)
            _livro("proposta", d["proposta"])
            return {"acao": "proposta", **d["proposta"]}
        if oque == "rebaixar":
            ult = recentes[-JANELA_REBAIXAR:]
            cerebro.ligar_semelhanca(False)
            d.update(promovido_em=None, nao_propor_ate=agora + 14 * 86400)
            d["cerebro"] = [r for r in regs if r[1] not in ("parecida", PROPRIA)]   # a prova antiga não vale mais: recomeça
            d.setdefault("historico", []).append({"ts": agora, "acao": "rebaixado", "erros": len(ult) - sum(ult), "de": len(ult)})
            _gravar(d)
            _livro("rebaixado", {"erros": len(ult) - sum(ult), "de": len(ult)})
            return {"acao": "rebaixado", "erros": len(ult) - sum(ult), "de": len(ult)}
    return None


def aprovar() -> str:
    """SÓ por pedido seu: liga o reflexo por semelhança que a sombra mediu."""
    from core import cerebro
    with _lock:
        d = _ler()
        p = d.get("proposta")
        if not p:
            return "Não há evolução esperando a sua aprovação."
        cerebro.ligar_semelhanca(True)
        d.update(proposta=None, promovido_em=_agora())
        d.setdefault("historico", []).append({"ts": time.time(), "acao": "aprovada", **{k: p[k] for k in ("n", "acertos", "piso")}})
        _gravar(d)
    _livro("aprovada", {k: p[k] for k in ("n", "acertos", "piso")})
    return (f"Evolução aprovada: agora eu faço sozinho também frases PARECIDAS com as que você já usou (só ferramentas livres). "
            f"A prova: {p['acertos']} acertos em {p['n']} casos medidos. Se eu errar 3 das próximas 12, eu mesmo volto atrás.")


def recusar() -> str:
    with _lock:
        d = _ler()
        if not d.get("proposta"):
            return "Não há evolução esperando resposta."
        d.update(proposta=None, nao_propor_ate=time.time() + 30 * 86400)
        d.setdefault("historico", []).append({"ts": time.time(), "acao": "recusada"})
        _gravar(d)
    _livro("recusada", {})
    return "Recusado. Continuo só medindo e não proponho de novo por 30 dias."


def rebaixar() -> str:
    """Você tira a evolução quando quiser."""
    from core import cerebro
    if not cerebro.semelhanca_ligada():
        return "O reflexo por semelhança já está desligado."
    cerebro.ligar_semelhanca(False)
    with _lock:
        d = _ler()
        d.update(promovido_em=None, nao_propor_ate=time.time() + 30 * 86400)
        d["cerebro"] = [r for r in d.get("cerebro", []) if r[1] != PROPRIA]        # o que foi medido em sombra continua valendo
        d.setdefault("historico", []).append({"ts": time.time(), "acao": "desligada por você"})
        _gravar(d)
    _livro("desligada", {"por": "usuario"})
    return "Desligado: frase parecida volta a passar pelo Gemini."


# ─────────────────────────────────────────────────────────── placar de tudo ───
def _carregar(nome: str, padrao):
    from plugins._lote2 import carregar
    return carregar(nome, padrao)


def _oraculo() -> dict | None:
    erros = [p["erro"][0] for p in _carregar("oraculo", {"previsoes": []}).get("previsoes", []) if isinstance(p.get("erro"), list)]
    if not erros:
        return None
    return {"sistema": "oráculo de vendas", "n": len(erros), "erro_pct": st.mean(erros[-8:]), "tendencia": tendencia(erros),
            "mede": "erro do total da semana"}


def _eu_do_futuro() -> dict | None:
    from datetime import date
    from plugins import eu_do_futuro as E
    selos = _carregar("eu_do_futuro", {"selos": []}).get("selos") or []
    if not selos:
        return None
    series, erros = E._series(), []
    for s in selos:
        for _nome, prev, real, _k in E.comparar(s, series, date.today()):
            if prev:
                erros.append(abs(real - prev) / abs(prev) * 100)
    return {"sistema": "eu do futuro", "n": len(erros), "erro_pct": st.mean(erros), "tendencia": tendencia(erros),
            "mede": "projeção x o que aconteceu, por semana"} if erros else None


def _gemeo() -> dict | None:
    from plugins import promocoes_loja as PL
    erros = []
    for pr in _carregar("gemeo_loja", {"promocoes": []}).get("promocoes", []):
        if pr.get("conferida") is True and pr.get("razao"):
            previsto = PL.simular(1.0, pr["d"], pr["e_usada"], pr.get("alcance", 1.0))["receita"]
            erros.append(abs(pr["razao"] - previsto) / previsto * 100)
    return {"sistema": "gêmeo da loja", "n": len(erros), "erro_pct": st.mean(erros), "tendencia": tendencia(erros),
            "mede": "vendas previstas na promoção x vendidas"} if erros else None


def _probabilidades() -> dict | None:
    from plugins import probabilidades
    pr = probabilidades.precisao()
    return {"sistema": "motor de probabilidades", "n": pr["n"], "acerto": pr["acerto"], "tendencia": "—",
            "mede": "'vai dar certo?' x o que você disse que aconteceu"} if pr.get("n") else None


def _organismo() -> dict | None:
    import biological_core
    org = biological_core.atual()
    if not org or not org.ligado:
        return None
    ap = org.cerebro.aprendizado()
    n = int(org.cerebro.metricas.get("decisoes", 0))
    return {"sistema": "cérebro do organismo", "n": n, "acerto": ap["acerto"], "tendencia": "—",
            "mede": "reparos escolhidos que funcionaram"} if n and ap.get("acerto") is not None else None


def _cerebro_local() -> dict | None:
    pc = placar_cerebro()
    if not pc["sabia"]:
        return None
    return {"sistema": "cérebro local", "n": pc["sabia"], "acerto": pc["top1"], "tendencia": "—",
            "mede": "o que ele teria feito x o que foi feito"}


def placar() -> list[dict]:
    """Uma linha por sistema que já tem resultado medido. Sistema sem dado não aparece (nada inventado)."""
    out = []
    for fn in (_cerebro_local, _oraculo, _eu_do_futuro, _gemeo, _probabilidades, _organismo):
        try:
            linha = fn()
        except Exception as e:
            print(f"[Metacognição] {fn.__name__}: {e}")
            linha = None
        if linha:
            linha["confianca"] = confianca_de(linha)
            out.append(linha)
    return out


def confianca_de(linha: dict) -> str:
    """'alta' | 'média' | 'baixa' | 'pouca base' — o quanto dá para confiar naquele sistema, pelo que foi medido. Pura."""
    if linha["n"] < 3:
        return "pouca base"
    if "acerto" in linha and linha["acerto"] is not None:
        return "alta" if linha["acerto"] >= 0.85 else "média" if linha["acerto"] >= 0.65 else "baixa"
    e = linha.get("erro_pct", 100)
    return "alta" if e <= 12 else "média" if e <= 25 else "baixa"


def frase_de(linha: dict) -> str:
    med = (f"acerta {linha['acerto']:.0%}" if linha.get("acerto") is not None else f"erra em média {linha['erro_pct']:.0f}%")
    tend = f", {linha['tendencia']}" if linha.get("tendencia") not in (None, "—") else ""
    return f"{linha['sistema']}: {med} em {linha['n']} caso(s){tend} — confiança {linha['confianca']} ({linha['mede']})."
