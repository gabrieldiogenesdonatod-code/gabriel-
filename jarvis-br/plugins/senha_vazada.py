"""
Senha vazada? (fork PT-BR 1.6)

Confere se uma senha sua já apareceu em vazamentos, pelo Have I Been Pwned,
SEM mandar a senha para ninguém: o JARVIS calcula o SHA-1 aqui, manda só os 5
primeiros caracteres do hash (k-anonimato) e compara o resto no seu PC.

A senha é digitada numa janelinha do JARVIS (com asteriscos) — ela NÃO passa
pela conversa nem pela IA e não fica guardada em lugar nenhum.

    "Jarvis, minha senha foi vazada?"
"""

from __future__ import annotations

import hashlib
import threading

PLUGIN = {
    "name": "senha_vazada",
    "brief": "Checks if a password appeared in data breaches (HIBP k-anonymity); typed in a local box, never sent.",
    "description": (
        "Leaked password check with Have I Been Pwned using k-anonymity. Opens a local password box on the PC; the "
        "password never goes through the conversation. Never ask the user to say the password aloud. No parameters."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}}, "required": []},
}


def partes_hash(senha: str) -> tuple[str, str]:
    h = hashlib.sha1(senha.encode("utf-8")).hexdigest().upper()
    return h[:5], h[5:]


def contar(resposta: str, sufixo: str) -> int:
    """Linhas 'SUFIXO:QUANTIDADE' da API → quantas vezes este sufixo apareceu (pura)."""
    for linha in (resposta or "").splitlines():
        s, _, n = linha.strip().partition(":")
        if s.upper() == sufixo.upper():
            try:
                return int(n)
            except ValueError:
                return 0
    return 0


def vezes_vazada(senha: str) -> int:
    import requests
    prefixo, sufixo = partes_hash(senha)
    r = requests.get(f"https://api.pwnedpasswords.com/range/{prefixo}", timeout=15,
                     headers={"Add-Padding": "true", "User-Agent": "JARVIS-BR"})
    r.raise_for_status()
    return contar(r.text, sufixo)


def pedir_senha(player, segundos: float = 180) -> str | None:
    """Caixinha de senha (asteriscos) na interface. None se não deu para abrir ou cancelou."""
    from core import qt_bridge
    if player is None or not qt_bridge.disponivel():
        return None
    pronto, caixa = threading.Event(), {}

    def abrir():
        try:
            from PyQt6.QtWidgets import QInputDialog, QLineEdit
            texto, ok = QInputDialog.getText(None, "J.A.R.V.I.S — senha vazada?",
                                             "Digite a senha (ela não sai deste PC):", QLineEdit.EchoMode.Password)
            caixa["senha"] = texto if ok else None
        except Exception:
            caixa["senha"] = None
        finally:
            pronto.set()
    if not qt_bridge.na_interface(abrir):
        return None
    pronto.wait(segundos)
    return caixa.get("senha")


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        senha = pedir_senha(player)
        if senha is None:
            return "Cancelado (ou a janelinha não abriu). Não diga a senha em voz alta: eu sempre peço numa caixinha."
        if not senha:
            return "A senha estava vazia."
        n = vezes_vazada(senha)
        del senha
        if n:
            return (f"ATENÇÃO: essa senha apareceu {n:,} vezes em vazamentos. Troque em todo lugar que você usa e não "
                    "repita senha entre sites; um gerenciador de senhas e a verificação em duas etapas ajudam."
                    ).replace(",", ".")
        return "Boa notícia: essa senha não aparece nos vazamentos conhecidos. Mesmo assim, não repita entre sites."
    except Exception as e:
        return f"Não consegui conferir agora: {e}"
