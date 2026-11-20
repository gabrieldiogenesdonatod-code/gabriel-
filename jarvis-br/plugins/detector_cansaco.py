"""
Detector de cansaço (3.0): o JARVIS percebe que você está cansado e muda o jeito de ajudar.

Sinais que ele soma: madrugada; horas seguidas usando sem pausa; você repetindo pedidos ou
corrigindo ele várias vezes em pouco tempo ("repete", "não foi isso"). Quando o cansaço passa do
ponto, ele sugere uma pausa (no máximo uma vez a cada 2 horas) e passa a responder mais curto.

    "Jarvis, eu estou cansado?"      "Jarvis, desliga o detector de cansaço."
"""

from __future__ import annotations

import time

from plugins._lote2 import P, carregar, guardar, rodar

PLUGIN = P("detector_cansaco", "Fatigue detector: late hours, long sessions without breaks, repeated requests and corrections → suggests a "
           "break (at most every 2 h) and makes JARVIS answer shorter.",
           "checar | ligar | desligar", "checar: current fatigue level and why. ligar/desligar: automatic warnings.", "")

PAUSA_S = 20 * 60          # 20 min sem nada = pausa


def sessao_continua(tempos: list[float], agora: float) -> float:
    """Há quantos segundos você usa sem pausa de 20 min (tempos = momentos de atividade). Pura."""
    ts = sorted(t for t in tempos if t <= agora)
    if not ts or agora - ts[-1] > PAUSA_S:
        return 0.0
    inicio = ts[-1]
    for t in reversed(ts[:-1]):
        if inicio - t > PAUSA_S:
            break
        inicio = t
    return agora - inicio


def avaliar(hora: int, sessao_s: float, repeticoes: int) -> tuple[int, list[str]]:
    """(pontos, motivos). 0-1 descansado, 2-3 um pouco cansado, 4+ cansado. Pura."""
    pts, motivos = 0, []
    if 0 <= hora < 5:
        pts, motivos = pts + 2, motivos + ["é madrugada"]
    elif hora == 23:
        pts, motivos = pts + 1, motivos + ["já passou das 23h"]
    if sessao_s >= 5 * 3600:
        pts, motivos = pts + 2, motivos + [f"{sessao_s / 3600:.0f} horas seguidas sem pausa"]
    elif sessao_s >= 3 * 3600:
        pts, motivos = pts + 1, motivos + [f"{sessao_s / 3600:.0f} horas seguidas sem pausa"]
    if repeticoes:
        pts, motivos = pts + min(3, repeticoes), motivos + [f"{repeticoes} pedido(s) repetido(s) ou corrigido(s) na última meia hora"]
    return pts, motivos


def nivel(pts: int) -> str:
    return "cansado" if pts >= 4 else "um pouco cansado" if pts >= 2 else "descansado"


def medir(agora: float | None = None) -> tuple[int, list[str]]:
    agora = agora or time.time()
    from core import evolucao, registro_uso
    linhas = registro_uso.linhas_registro(desde=agora - 8 * 3600)
    tempos = [l["ts"] for l in linhas] + [c["ts"] for c in registro_uso.chamadas(desde=agora - 8 * 3600)]
    falas = [l["linha"][7:] for l in linhas if l["ts"] >= agora - 1800 and str(l["linha"]).startswith("Você: ")]
    rep = sum(1 for f in falas if evolucao.sinal(f) in ("repetir", "corrigir"))
    return avaliar(time.localtime(agora).tm_hour, sessao_continua(tempos, agora), rep)


def passo(player) -> None:
    est = carregar("cansaco", {"ligado": True, "ultimo_aviso": 0})
    if not est.get("ligado", True) or time.time() - est.get("ultimo_aviso", 0) < 2 * 3600:
        return
    pts, motivos = medir()
    if pts >= 4:
        est["ultimo_aviso"] = time.time()
        guardar("cansaco", est)
        from plugins._comum import falar
        falar(player, "[CANSAÇO] Com carinho e em UMA frase, diga que percebeu sinais de cansaço (" + ", ".join(motivos) +
                      ") e sugira uma pausa de 10 minutos com água. A partir de agora, nesta conversa, responda mais curto e "
                      "simples. Não chame nenhuma ferramenta.")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("detector_cansaco", lambda: passo(player), a_cada_s=900, primeira_em_s=600)


def _go(p, pl):
    a, est = p["action"], carregar("cansaco", {"ligado": True, "ultimo_aviso": 0})
    if a in ("ligar", "desligar"):
        est["ligado"] = a == "ligar"
        guardar("cansaco", est)
        return "Detector de cansaço ligado." if est["ligado"] else "Detector de cansaço desligado."
    pts, motivos = medir()
    return f"Pelos sinais, o senhor está {nivel(pts)}" + (f": {', '.join(motivos)}." if motivos else ".")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("checar ligar desligar".split(), _go), player)
