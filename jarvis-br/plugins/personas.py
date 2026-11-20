"""
Segunda persona: F.R.I.D.A.Y (fork PT-BR 1.4).

Outra voz e outra personalidade para outro contexto: o JARVIS cuida da
programação, a FRIDAY da loja. A troca muda o NOME, a VOZ (vozes do Gemini
Live) e o ESTILO de fala, e reconecta a sessão (a voz só muda na conexão).

    "Jarvis, chama a Friday"        "Friday, volta o Jarvis"
    Nos protocolos: passo 'persona' — "protocolo loja" pode trocar até a voz.
    "Jarvis, cria a persona Karen com a voz Aoede, estilo calmo e didático"

Vozes disponíveis: Charon, Puck, Kore, Fenrir, Aoede.
Personas ficam em config/personas.json.
"""

from __future__ import annotations

import threading
import unicodedata

from plugins import _personas

PLUGIN = {
    "name": "personas",
    "brief": "Switch assistant persona (JARVIS / FRIDAY / custom): name, voice and style.",
    "description": (
        "Switch between assistant personas, e.g. JARVIS (programming) and F.R.I.D.A.Y (the store): changes "
        "name, Live voice and speaking style, then reconnects (say goodbye in one short sentence first). "
        "action='trocar' with nome ('chama a Friday', 'volta o Jarvis'); 'listar'; 'qual' (active one); "
        "'criar' with nome, voz (Charon|Puck|Kore|Fenrir|Aoede) and estilo (personality in Portuguese)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "trocar | listar | qual | criar"},
            "nome": {"type": "STRING"}, "voz": {"type": "STRING"}, "estilo": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_VOZES = ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]


def _chave(nome: str) -> str:
    t = unicodedata.normalize("NFKD", (nome or "").lower()).encode("ascii", "ignore").decode()
    return "".join(ch for ch in t if ch.isalnum())


def trocar(nome: str, reconectar: bool = True, atraso: float = 5.0) -> str:
    d = _personas.carregar()
    k = _chave(nome)
    alvo = next((c for c, v in d["personas"].items()
                 if k in (_chave(c), _chave(v["nome"])) or k in [_chave(a) for a in v.get("apelidos", [])]), None)
    if not alvo:
        return f"Não conheço a persona '{nome}'. Tenho: {', '.join(p['nome'] for p in d['personas'].values())}."
    if alvo == d["ativa"]:
        return f"{d['personas'][alvo]['nome']} já está ativa."
    p = d["personas"][alvo]
    try:
        from memory.config_manager import load_api_keys, save_assistant_config, save_voice
        save_voice(p.get("voz") or "Charon")
        save_assistant_config(p["nome"], load_api_keys().get("user_name", ""))
    except Exception as e:
        return f"Não consegui trocar: {e}"
    _personas.salvar(alvo)
    try:                                         # 2.14: o rosto do HUD vira o da SEXTA (ou volta) na hora
        from core import emocoes
        emocoes.forcar_estilo(alvo)
    except Exception:
        pass
    if reconectar:
        from core import registro_ferramentas
        # espera a despedida terminar de ser falada antes de trocar a voz
        threading.Timer(atraso, registro_ferramentas.reconectar,
                        kwargs={"motivo": f"persona {p['nome']}", "manter_conversa": False}).start()
    return (f"Trocando para {p['nome']} (voz {p.get('voz')}). Em alguns segundos a sessão reconecta com a nova voz. "
            "Despeça-se em UMA frase curta.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        d = _personas.carregar()
        if acao == "trocar":
            return trocar(str(p.get("nome") or ""))
        if acao == "qual":
            ativa = d["personas"].get(d["ativa"], {})
            return f"Agora quem fala é {ativa.get('nome', 'JARVIS')}, com a voz {ativa.get('voz', 'Charon')}."
        if acao == "criar":
            nome = str(p.get("nome") or "").strip()
            voz = next((v for v in _VOZES if v.lower() == str(p.get("voz") or "").strip().lower()), "Aoede")
            estilo = str(p.get("estilo") or "").strip()
            if not nome or not estilo:
                return "Diga o nome e o estilo da persona (e a voz: Charon, Puck, Kore, Fenrir ou Aoede)."
            personas = dict(d["personas"])
            personas[_chave(nome)] = {"nome": nome.upper(), "voz": voz, "descricao": estilo[:120],
                                      "estilo": f"[PERSONA: {nome.upper()}]\nVocê é {nome}. {estilo} Mesmas "
                                                "ferramentas e regras de segurança."}
            _personas.salvar(d["ativa"], personas)
            return f"Criei a persona {nome.upper()} com a voz {voz}. Diga 'chama a {nome}' para trocar."
        return "Personas: " + "; ".join(f"{v['nome']} ({v.get('voz')}): {v.get('descricao', '')}"
                                          for v in d["personas"].values()) + f". Ativa: {d['personas'][d['ativa']]['nome']}."
    except Exception as e:
        return f"As personas falharam: {e}"
