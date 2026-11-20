"""
Negociação de distração no foco (fork PT-BR 2.5). Começa com "_": não é ferramenta.

    "Jarvis, me dá 5 minutos de YouTube?"  →  "Libero 5 se você terminar essa função primeiro."
    "Terminei a função"                    →  libera 5 minutos e avisa quando acabar ("combinado é combinado")
    "Libera agora, depois eu compenso"      →  fiado: libera já e cobra os minutos a mais no fim do foco

Tudo aqui é puro (testado em tests/test_27_foco.py); o pomodoro guarda o estado.
"""

from __future__ import annotations

import math

MAX_POR_FOCO = 2
MAX_MINUTOS = 10
CONDICOES = {
    "programando": ("tarefa", "terminar essa função"),
    "editando": ("tarefa", "fechar essa parte"),
}


def minutos_txt(n: float) -> str:
    n = max(1, int(math.ceil(n)))
    return f"{n} minuto{'s' if n > 1 else ''}"


def propor(pedido_min: float, o_que: str, restante_s: float | None, atividade: str, acordos: int,
           pausa_min: float, agora: float) -> dict:
    """{'resposta', 'acordo' (ou None), 'liberar_agora'}"""
    o_que = (o_que or "distração").strip()
    pedido = max(1, int(round(pedido_min or 5)))
    if restante_s is None:
        return {"resposta": "Não tem foco rolando agora: pode ir, sem negociação.", "acordo": None,
                "liberar_agora": False}
    falta = minutos_txt(restante_s / 60)
    if acordos >= MAX_POR_FOCO:
        return {"resposta": f"Já liberei {MAX_POR_FOCO} vezes nesse foco. Faltam {falta} pra pausa — aí são "
                            f"{minutos_txt(pausa_min)} livres.", "acordo": None, "liberar_agora": False}
    if restante_s <= 8 * 60:
        return {"resposta": f"Faltam só {falta} pra pausa. Aguenta firme: na pausa são {minutos_txt(pausa_min)} de "
                            f"{o_que} à vontade.", "acordo": None, "liberar_agora": False}
    minutos = min(pedido, 5) if pedido > MAX_MINUTOS else min(pedido, MAX_MINUTOS)
    prefixo = f"{pedido} no meio do foco é muito. " if pedido > MAX_MINUTOS else ""
    tipo, condicao = CONDICOES.get(atividade, ("tempo", ""))
    if tipo == "tarefa":
        frase = f"{prefixo}Libero {minutos} se você {condicao} primeiro."
        acordo = {"o_que": o_que, "minutos": minutos, "condicao": "tarefa", "texto": condicao, "criado": agora}
    else:
        espera = 10 if restante_s > 18 * 60 else 5
        frase = f"{prefixo}Libero {minutos} daqui a {espera} minutos de foco. Combinado?"
        acordo = {"o_que": o_que, "minutos": minutos, "condicao": "tempo", "libera_em": agora + espera * 60,
                  "texto": f"mais {espera} minutos de foco", "criado": agora}
    return {"resposta": frase, "acordo": acordo, "liberar_agora": False}


def cumprir(acordo: dict | None, agora: float) -> tuple[str, dict | None]:
    """'Terminei.' → (resposta, liberação {'termo', 'minutos', 'ate'} ou None)."""
    if not acordo:
        return "Não tem acordo aberto. Quer negociar uns minutos?", None
    if acordo["condicao"] == "tempo" and agora < acordo.get("libera_em", 0):
        return f"Ainda faltam {minutos_txt((acordo['libera_em'] - agora) / 60)} pro combinado.", None
    lib = {"termo": acordo["o_que"], "minutos": acordo["minutos"], "ate": agora + acordo["minutos"] * 60}
    return (f"Fechado: {acordo['minutos']} minutos de {acordo['o_que']} liberados, valendo a partir de agora. "
            f"Eu aviso quando acabar."), lib


def fiado(acordo: dict | None, o_que: str, minutos: float, agora: float) -> tuple[str, dict, int]:
    """Libera já e anota a dívida. (resposta, liberação, dívida em segundos)"""
    o_que = (acordo or {}).get("o_que") or o_que or "distração"
    m = int((acordo or {}).get("minutos") or min(MAX_MINUTOS, max(1, int(round(minutos or 5)))))
    lib = {"termo": o_que, "minutos": m, "ate": agora + m * 60}
    return (f"Tá bom, libero {m} minutos de {o_que} agora — mas fica devendo: são {m} minutos a mais de foco no fim. "
            f"Eu cobro."), lib, m * 60


def liberado(lib: dict | None, nome: str, agora: float) -> bool:
    """O site/app `nome` está liberado agora pelo acordo? (YouTube ↔ youtube.com, Discord ↔ discord.exe)"""
    if not lib or agora >= lib.get("ate", 0):
        return False
    a, b = str(lib.get("termo") or "").lower().strip(), str(nome or "").lower().strip()
    a, b = a.replace(".exe", ""), b.replace(".exe", "")
    return bool(a and b and (a in b or b in a))


def frase_celular(restante_s: float) -> str:
    if restante_s < 60:
        return "Senhor, falta menos de um minuto pra pausa — aí o celular é todo seu."
    return f"Senhor, o celular pode esperar mais {minutos_txt(restante_s / 60)}."
