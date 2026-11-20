"""Diário de treino de IA (2.19): anota a loss de cada experimento, diz se está caindo, estagnou ou deu overfitting e compara os experimentos."""
from __future__ import annotations

from plugins._lote2 import Colecao, P, rodar
from plugins.calculadora_ia import grande

PLUGIN = P("diario_treino_ia", "ML experiment log: record step/train loss/val loss per run, trend (falling, plateau, overfitting), best checkpoint, compare runs, notes.",
           "novo | registrar | status | comparar | nota | listar | apagar",
           "novo: nome, config (free text: lr, layers…). registrar: nome, passo, loss, val (optional). nota: nome, texto.",
           "nome config passo loss val texto")

T = Colecao("treinos_ia")


def tendencia(pontos: list[list], janela: int = 5) -> str:
    """Olha a loss de treino nos últimos pontos. Pura."""
    ls = [p[1] for p in pontos[-janela:]]
    if len(ls) < 3:
        return "poucos pontos ainda"
    queda = (ls[0] - ls[-1]) / max(1e-9, abs(ls[0]))
    return "caindo bem" if queda > 0.03 else "subindo (taxa de aprendizado alta?)" if queda < -0.03 else "estagnada"


def overfitting(pontos: list[list]) -> bool:
    vs = [p for p in pontos if p[2] is not None][-3:]
    return len(vs) == 3 and vs[0][1] > vs[-1][1] and vs[0][2] < vs[1][2] < vs[2][2]


def melhor(pontos: list[list]) -> list | None:
    com_val = [p for p in pontos if p[2] is not None]
    return min(com_val, key=lambda p: p[2]) if com_val else (min(pontos, key=lambda p: p[1]) if pontos else None)


def _go(p, pl):
    a, nome = p["action"], p.get("nome")
    if a == "novo":
        T.por(nome, {"config": str(p.get("config") or ""), "pontos": [], "notas": []})
        return f"Experimento '{nome}' criado."
    tudo = list(T.tudo().values())
    if a == "listar":
        return "\n".join(f"{t['nome']}: {len(t['pontos'])} ponto(s). {t['config']}" for t in tudo) or "Nenhum experimento."
    if a == "comparar":
        linhas = sorted(((melhor(t["pontos"]), t) for t in tudo if t["pontos"]), key=lambda x: x[0][2] if x[0][2] is not None else x[0][1])
        return "\n".join(f"{t['nome']}: melhor {'val' if m[2] is not None else 'loss'} {m[2] if m[2] is not None else m[1]:.4f} no passo {m[0]:g} ({t['config']})"
                         for m, t in linhas) or "Nada para comparar."
    t = T.pegar(nome) or (tudo[-1] if tudo and not nome else None)
    if not t:
        return "Não achei esse experimento."
    if a == "apagar":
        T.tirar(t["nome"])
        return "Experimento apagado."
    if a == "nota":
        t["notas"].append(str(p.get("texto") or ""))
    elif a == "registrar":
        t["pontos"].append([grande(p.get("passo")), grande(p.get("loss")), grande(p.get("val")) if p.get("val") else None])
    T.por(t["nome"], t)
    if not t["pontos"]:
        return f"{t['nome']}: sem pontos ainda."
    u, m = t["pontos"][-1], melhor(t["pontos"])
    msg = f"{t['nome']} no passo {u[0]:g}: loss {u[1]:.4f}" + (f", val {u[2]:.4f}" if u[2] is not None else "") + f". Loss {tendencia(t['pontos'])}."
    if overfitting(t["pontos"]):
        msg += f" Sinal de OVERFITTING: a validação vem subindo. Melhor ponto foi o passo {m[0]:g}."
    return msg


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("novo registrar status comparar nota listar apagar".split(), _go), player, "Treino IA")
