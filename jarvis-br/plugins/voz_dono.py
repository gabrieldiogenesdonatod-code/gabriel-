"""
Voz do dono — cadastro e teste (fork PT-BR 1.5).

    "Jarvis, aprende a minha voz"
        → nos próximos minutos, enquanto você conversa normalmente, ele junta
          uns 25 s da SUA fala (só quando o JARVIS está quieto) e monta a
          impressão de voz. Não precisa ler frase nenhuma.
    "Jarvis, confere a minha voz"     → diz o quanto o último pedido parece você
    "Jarvis, esquece a minha voz"

Depois disso, um pedido sensível fora da sessão confiável é conferido pela
voz do próprio pedido, sem etapa extra.

Precisa de:  python -m pip install webrtcvad-wheels librosa scipy torch
             python -m pip install resemblyzer --no-deps
"""

from __future__ import annotations

import threading
import time

from plugins import _voz
from plugins._comum import registrar

PLUGIN = {
    "name": "voz_dono",
    "brief": "Owner voice print: learn it passively, test the last request, forget it.",
    "description": (
        "Owner's voice verification. action='aprender' ('learn my voice': collects ~25 s of the user's "
        "speech during normal conversation, no phrases to read), 'testar' (how much the last request "
        "sounds like the owner), 'esquecer', 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "aprender | testar | esquecer | status"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "voz_dono",
    "title": "Voz do dono",
    "fields": [
        {"key": "limiar", "label": "Semelhança mínima (0,60 a 0,90; maior = mais rigoroso)", "type": "text",
         "default": "0.75"},
    ],
}

_INSTALAR = ("Para reconhecer a sua voz preciso do resemblyzer. No PowerShell: python -m pip install webrtcvad-wheels librosa scipy torch e depois python -m pip install resemblyzer --no-deps (os comandos estão no INSTALAR.txt).")
_cadastro = {"ativo": False, "impressoes": [], "segundos": 0.0, "fim": 0.0}


def _coletar(player) -> None:
    from core import escuta
    vistos = set()
    while _cadastro["ativo"] and time.time() < _cadastro["fim"]:
        time.sleep(1.5)
        with escuta._lock:
            prontos = [t for t in escuta._trechos if t[0] not in vistos]
        for ini, fim, blocos in prontos:
            vistos.add(ini)
            import numpy as np
            audio = np.concatenate(blocos)
            if len(audio) < 16000 * 1.2:
                continue
            try:
                e = _voz.impressao(audio)
            except Exception as ex:
                print(f"[VozDono] {ex}")
                continue
            if e is not None:
                _cadastro["impressoes"].append(e)
                _cadastro["segundos"] += len(audio) / 16000
        if _cadastro["segundos"] >= 25 and len(_cadastro["impressoes"]) >= 4:
            _voz.salvar_perfil(_cadastro["impressoes"])
            _cadastro["ativo"] = False
            from plugins._notificar import notificar
            notificar(player, "Aprendi a sua voz. Pedidos sensíveis agora também são conferidos pela voz.",
                      titulo="Verificação", etiqueta="VOZ")
            try:
                from core import verificacao
                verificacao.registrar("voz", "impressão de voz cadastrada")
            except Exception:
                pass
            return
    if _cadastro["ativo"]:
        _cadastro["ativo"] = False
        registrar(player, f"Voz: só juntei {_cadastro['segundos']:.0f} s de fala; diga 'aprende a minha voz' de novo.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    try:
        if not _voz.disponivel():
            return _INSTALAR
        if acao == "aprender":
            if _cadastro["ativo"]:
                return f"Já estou aprendendo: tenho {_cadastro['segundos']:.0f} de 25 segundos."
            _cadastro.update(ativo=True, impressoes=[], segundos=0.0, fim=time.time() + 300)
            threading.Thread(target=_coletar, args=(player,), daemon=True, name="voz_cadastro").start()
            return ("Combinado. Converse comigo normalmente pelos próximos minutos; quando eu tiver uns 25 segundos "
                    "da sua voz, aviso que aprendi. Só a sua impressão de voz fica salva, não a gravação.")
        if acao == "testar":
            from core import escuta
            s = _voz.comparar_trecho(escuta.ultimo_trecho())
            if s is None:
                return "Não tenho a sua voz cadastrada ou não ouvi fala suficiente agora."
            return (f"O seu último pedido parece {s * 100:.0f}% com a sua voz cadastrada "
                    f"(o mínimo é {_voz.limiar() * 100:.0f}%): {'é você' if s >= _voz.limiar() else 'não bateu'}.")
        if acao == "esquecer":
            _voz.ARQ_DONO.unlink(missing_ok=True)
            return "Esqueci a sua impressão de voz."
        return ("Voz cadastrada; a conferência acontece no próprio pedido." if _voz.ARQ_DONO.exists()
                else "Ainda não conheço a sua voz. Diga 'aprende a minha voz'.")
    except Exception as e:
        return f"A voz falhou: {e}"
