"""
"Jarvis, por que você fechou?" (fork PT-BR 2.8.1)

Explica, em português, como o JARVIS terminou da última vez — pedido de fechar,
janela fechada, queda do som/vídeo/janela (com o arquivo do Windows que caiu),
travamento, falta de memória ou encerrado de fora — e mostra as últimas
aberturas. Tudo vem de memory/erros.log, memory/ultimo_sinal.json e do
registro de erros do Windows (core/por_que_fechou.py).
"""

from __future__ import annotations

from core import por_que_fechou as P
from core import protecao_falhas
from plugins._comum import mostrar

PLUGIN = {
    "name": "por_que_fechou",
    "brief": "Explains why JARVIS closed or crashed last time and the recent history (error log + Windows log).",
    "description": (
        "Explains why JARVIS closed/crashed the last time it ran, in plain Portuguese: requested shutdown, window "
        "closed, a native crash (which Windows file failed: sound, video driver, window, camera…), a freeze, low "
        "memory or killed from outside — plus what to do. action: 'ultima' (default) or 'historico' (last runs "
        "and how each ended). Use for 'por que você fechou?', 'por que o Jarvis fecha sozinho?', 'o que derrubou "
        "o Jarvis?', 'por que você caiu?'."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "ultima | historico"}}},
}


def _log() -> str:
    try:
        return P.LOG.read_text(encoding="utf-8", errors="replace")[-200000:]
    except OSError:
        return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "ultima").strip().lower()
    txt = _log()
    linhas = P.historico(txt, 12)
    if acao.startswith("hist"):
        if not linhas:
            return "Ainda não tenho registro de aberturas do JARVIS."
        mostrar(player, "COMO O JARVIS TERMINOU", "\n".join(linhas))
        sozinho = sum(1 for linha in linhas if "caiu" in linha or "sem registro" in linha)
        return (f"Das últimas {len(linhas)} aberturas, {sozinho} terminaram sem pedido (queda ou encerrado de fora). "
                "A lista está na tela. Resuma em 2 frases.")
    texto = protecao_falhas.explicacao_anterior() or P.diagnosticar(txt, pular_atual=True)
    mostrar(player, "POR QUE O JARVIS FECHOU", texto + ("\n\nÚltimas aberturas:\n" + "\n".join(linhas[-6:])
                                                         if linhas else ""))
    return texto + " Explique isso ao usuário em até 3 frases simples, com o que fazer."
