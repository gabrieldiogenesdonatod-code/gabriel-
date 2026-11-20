"""
IA local (3.5): o JARVIS funcionando SEM INTERNET — ouve, pensa e fala tudo no seu PC.

    "Jarvis, instala a IA local"               (uma vez; pede o seu SIM na tela; ≈ 1,5 GB no total)
    "Jarvis, instala a IA local esperta"       (modelo 3B: entende melhor, mais pesado)
    "Jarvis, como está a IA local?"            "Jarvis, testa a IA local: quanto é 12 vezes 8?"
    "Jarvis, liga a IA local" / "desliga a IA local"
    "Jarvis, desliga a troca automática"        (aí ele não troca sozinho quando a internet cai)

Com internet o Gemini conversa, como sempre. Sem internet, ele troca sozinho para o modo local e
volta quando a rede voltar. Como funciona: core/ia_local.py.
"""

from __future__ import annotations

import threading

from core import ia_local as L
from plugins._lote2 import P, norm, rodar

PLUGIN = P("ia_local", "Offline AI: installs and runs a small local language model (llama.cpp) + Whisper so JARVIS keeps "
                       "working with no internet; auto-switches back to Gemini.",
           "instalar | estado | testar | ligar | desligar | automatico | remover",
           "instalar: modelo (leve = Llama 3.2 1B, default | esperto = Llama 3.2 3B) — downloads once, asks the user's "
           "on-screen YES. estado: status. testar: texto — ask the local model directly. ligar / desligar: start/stop "
           "the local server. automatico: valor (sim | nao) — switch to local by itself when the internet drops. "
           "remover: modelo — delete a downloaded model.",
           "modelo texto valor")


def _chave(p) -> str:
    m = norm(p.get("modelo"))
    return "esperto" if any(x in m for x in ("esper", "3b", "grande", "intelig", "melhor")) else "leve"


def _instalar(p, pl):
    chave = _chave(p)
    m = L.MODELOS[chave]
    if L.pronto() and L.config().get("modelo") == chave:
        return f"A IA local ({m['nome']}) já está instalada."
    precisa = L.mb_necessarios(chave, L.whisper_instalado(), L.exe_servidor().is_file())

    def fazer() -> str:
        def em_fundo():
            from plugins._comum import avisar, mostrar
            r = L.instalar(chave, avisar=lambda t: mostrar(pl, "IA LOCAL", t))
            mostrar(pl, "IA LOCAL", r)
            avisar(pl, r, "IA LOCAL")
        threading.Thread(target=em_fundo, daemon=True, name="instalar_ia_local").start()
        return (f"Comecei a instalar a IA local ({m['nome']}). Demora alguns minutos; eu aviso quando terminar e "
                "você pode continuar usando o JARVIS enquanto isso.")

    try:
        from core import confirm
        return confirm.request("ia_local_instalar", f"Instalar a IA local ({m['nome']})?",
                               f"Vou baixar uns {precisa} MB (servidor llama.cpp do GitHub, modelo {m['nome']} do "
                               "Hugging Face e o Whisper pelo pip) para a pasta ia_local do JARVIS. Precisa de internet "
                               "só agora; depois funciona sem.", fazer)
    except Exception as e:
        return f"Não consegui pedir a sua confirmação ({e}); não instalei nada."


def _estado(p, pl):
    c, inst = L.config(), L.estado_instalacao()
    if inst["ativo"]:
        return f"Instalando a IA local: {inst['etapa']} ({inst['pct']:.0f}%)."
    if not L.pronto():
        return ("A IA local não está instalada. Diga 'instala a IA local' (modelo leve, ≈ 0,8 GB) ou 'instala a IA "
                "local esperta' (≈ 2 GB).")
    m = L.MODELOS.get(c.get("modelo", "leve"), L.MODELOS["leve"])
    return (f"IA local instalada: {m['nome']}. Servidor {'ligado' if L.servidor_ligado() else 'desligado'}; "
            f"troca automática {'ligada' if L.automatico() else 'desligada'}; "
            f"agora estou {'no modo local' if L.no_local() else 'no Gemini'}; "
            f"ouvido sem internet (Whisper): {'pronto' if L.whisper_instalado() else 'falta instalar'}.")


def _testar(p, pl):
    if not L.pronto():
        return "A IA local não está instalada."
    texto = str(p.get("texto") or "Diga oi em uma frase.").strip()
    try:
        return f"A IA local respondeu: {L.conversar(texto)}"
    except Exception as e:
        return f"A IA local não respondeu: {e}"


def _ligar(p, pl):
    return L.ligar_servidor()


def _desligar(p, pl):
    return L.desligar_servidor()


def _automatico(p, pl):
    sim = norm(p.get("valor")) not in ("nao", "não", "off", "desligar", "desliga", "false", "0")
    L.salvar(auto=sim)
    return ("Troca automática ligada: sem internet, eu passo sozinho para a IA local." if sim else
            "Troca automática desligada: sem internet eu não troco para a IA local.")


def _remover(p, pl):
    return L.remover_modelo(_chave(p))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"instalar": _instalar, "estado": _estado, "testar": _testar, "ligar": _ligar,
                              "desligar": _desligar, "automatico": _automatico, "remover": _remover}, player, "IA local")
