"""
Modo anônimo (fork PT-BR 3.2): conversar sem deixar rastro.

    "Jarvis, modo anônimo"            "Jarvis, sai do modo anônimo"

Ligado:
    • a sessão recomeça SEM as suas memórias: o Gemini não recebe seu nome, rotina nem nada guardado;
    • nada da conversa é gravado no PC: memória de longo prazo, resumo da sessão, diário de uso
      (registro de ferramentas e falas), ganchos de fim de turno (diário por entrevista, evolução)
      e os parâmetros que o sistema imune guardaria num incidente;
    • o JARVIS é avisado para não guardar nada e para dizer isso se você pedir para lembrar algo.

O que continua: o que você PEDE de propósito (pôr um item na lista de compras, criar um lembrete)
é gravado, como num navegador anônimo um download continua salvo. E a conversa em si passa pelo
Gemini (Google) — isso é o que faz o JARVIS entender você; o modo anônimo não muda isso.

O estado fica em memory/modo_anonimo.json só com {"ativo": true}: se o JARVIS reiniciar, ele volta anônimo.
"""

from __future__ import annotations

import json
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / "memory" / "modo_anonimo.json"
INSTRUCAO = ("[MODO ANÔNIMO] O usuário ligou o modo anônimo. Nada desta conversa é guardado: NÃO salve memórias, não "
             "use ferramentas para memorizar e não traga assuntos pessoais de antes. Se ele pedir para lembrar algo, diga em "
             "uma frase que no modo anônimo nada é guardado (listas e lembretes que ele pedir de propósito continuam valendo).")
_estado: dict = {"ativo": None}


def ativo() -> bool:
    if _estado["ativo"] is None:
        try:
            _estado["ativo"] = bool(json.loads(ARQ.read_text(encoding="utf-8")).get("ativo"))
        except Exception:
            _estado["ativo"] = False
    return bool(_estado["ativo"])


def definir(ligado: bool) -> None:
    try:                                       # Fork PT-BR 3.6: o livro-razão marca só o liga/desliga (sem conteúdo)
        if bool(ligado) != ativo():
            from core import livro_razao
            livro_razao.registrar("anonimo", {"ligado": bool(ligado)}, forcar=True)
    except Exception:
        pass
    _estado["ativo"] = bool(ligado)
    try:
        if ligado:
            ARQ.parent.mkdir(parents=True, exist_ok=True)
            ARQ.write_text('{"ativo": true}', encoding="utf-8")
        elif ARQ.exists():
            ARQ.unlink()
    except OSError:
        pass
