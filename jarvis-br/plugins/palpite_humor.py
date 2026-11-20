"""
Palpite de humor / energia (fork PT-BR 2.11).

Um palpite leve de como você deve estar — pelo HORÁRIO e pelo quanto você está
ativo no PC. NÃO grava o que você digita nem lê o que você escreve: é só horário,
tempo de tela e se você está há muito tempo sem pausa.

    "Jarvis, como eu tô?"      "Jarvis, qual meu humor agora?"

É palpite, não ciência — serve pra ele sugerir uma pausa, uma água, um descanso
na hora certa. Se você disser como está de verdade, ele acredita em você, não no
palpite.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

PLUGIN = {
    "name": "palpite_humor",
    "brief": "Light energy/mood guess from time of day and screen activity (no keylogging) + a gentle suggestion.",
    "description": (
        "A light guess of the user's energy/mood from the TIME of day and how long they've been active at the PC "
        "(never from what they type). action='palpite' (default). Use for 'como eu tô?', 'qual meu humor/minha "
        "energia agora?'. It is a guess, not a diagnosis — it offers a gentle suggestion (a break, water). If the "
        "user says how they actually feel, believe them over the guess."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "palpite"}}},
}


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── pura ───────────────────────────────────────────────────────────────────────
def fase_do_dia(hora: int) -> tuple[str, str]:
    if 0 <= hora < 5:
        return "madrugada", "Você devia estar dormindo, senhor — amanhã o corpo cobra."
    if 5 <= hora < 9:
        return "cedo", "Começo de dia; um café e uma água caem bem."
    if 9 <= hora < 12:
        return "manhã", "Costuma ser a hora de mais foco — bom pra tarefa pesada."
    if 12 <= hora < 14:
        return "pós-almoço", "A hora da sonolência; se der, uma pausa curta ajuda."
    if 14 <= hora < 18:
        return "tarde", "Pique bom pra resolver pendências."
    if 18 <= hora < 22:
        return "noite", "Fim de dia; vale ir fechando as coisas."
    return "fim da noite", "Tá ficando tarde; o descanso conta tanto quanto o trabalho."


def estimar(hora: int, minutos_seguidos: float, ocioso_s: float) -> tuple[str, str]:
    """(leitura, sugestão) a partir do horário e do tempo de tela sem pausa (puro)."""
    fase, dica_fase = fase_do_dia(hora)
    if ocioso_s >= 300:
        return f"Parece que você acabou de voltar ({fase}).", "Bom descanso ajuda — retoma com calma."
    if minutos_seguidos >= 120:
        return (f"Você está há mais de 2 horas direto no PC ({fase}).",
                "Faz uma pausa de 5 minutos, levanta e bebe água — seu foco agradece.")
    if minutos_seguidos >= 60:
        return f"Já é mais de uma hora de tela sem parar ({fase}).", "Daqui a pouco vale esticar as pernas."
    if fase in ("madrugada", "fim da noite"):
        return f"Tarde da noite e ainda de pé ({fase}).", dica_fase
    return f"Ritmo tranquilo, {fase}.", dica_fase


# ── sinais (sem teclar nada) ─────────────────────────────────────────────────
def _minutos_seguidos() -> float:
    try:
        from plugins import linha_do_tempo
        import time
        r = linha_do_tempo.resumo(time.time() - 3 * 3600)
        return float(r.get("sem_pausa_min", 0) or 0)
    except Exception:
        return 0.0


def _ocioso() -> float:
    try:
        from plugins import linha_do_tempo
        return linha_do_tempo.ocioso_segundos()
    except Exception:
        return 0.0


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        hora = datetime.now().hour
        leitura, sugestao = estimar(hora, _minutos_seguidos(), _ocioso())
        return (f"[PALPITE] {leitura} {sugestao} Diga isso ao usuário em 1 ou 2 frases, de leve, deixando claro que "
                "é só um palpite pelo horário e pela atividade — e pergunte como ele está de verdade. Não chame "
                "nenhuma ferramenta.")
    except Exception as e:
        return f"O palpite de humor falhou: {e}"
