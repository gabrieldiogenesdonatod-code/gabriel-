"""
Todos os jeitos de o JARVIS falar com você fora do PC (fork PT-BR 2.0). Começa com "_": não é ferramenta.

WhatsApp, Telegram e Discord (mensagem) e ligação de verdade (Twilio).
`mandar()` usa os canais ligados, na ordem que você escolheu em ⚙ → Companheiro.
"""

from __future__ import annotations

from pathlib import Path

NOMES = {"whatsapp": "WhatsApp", "telegram": "Telegram", "discord": "Discord", "ligacao": "ligação"}


def ativos() -> list[str]:
    saida = []
    try:
        from plugins import _whatsapp
        if _whatsapp.rodando() and _whatsapp.chats_dono():
            saida.append("whatsapp")
    except Exception:
        pass
    try:
        from plugins import _telegram
        if _telegram.rodando() and _telegram.dados()["chats"]:
            saida.append("telegram")
    except Exception:
        pass
    try:
        from plugins import _discord
        if _discord.rodando():
            saida.append("discord")
    except Exception:
        pass
    try:
        from plugins import ligacao
        if ligacao.configurada():
            saida.append("ligacao")
    except Exception:
        pass
    return saida


def ordem(preferidos: str, disponiveis: list[str]) -> list[str]:
    """'telegram, whatsapp' + disponíveis → ordem de tentativa (pura). Ligação nunca entra sozinha."""
    pref = [p.strip().lower() for p in str(preferidos or "").replace(";", ",").split(",") if p.strip()]
    lista = [p for p in pref if p in disponiveis and p != "ligacao"]
    lista += [c for c in disponiveis if c not in lista and c != "ligacao"]
    return lista


def mandar(texto: str, arquivo: Path | None = None, canal: str = "", todos: bool = False,
           botoes: list[list[tuple[str, str]]] | None = None, preferidos: str = "") -> list[str]:
    """Manda pelo canal pedido, ou pelo primeiro que funcionar (ou por todos). Devolve por onde foi."""
    disp = ativos()
    alvos = [canal] if canal and canal in disp else ordem(preferidos, disp)
    usados = []
    for c in alvos:
        ok = False
        try:
            if c == "whatsapp":
                from plugins import _whatsapp
                extra = ("\n\n" + " / ".join(t for linha in botoes for t, _d in linha)) if botoes else ""
                ok = _whatsapp.para_donos(texto + extra, arquivo) > 0
            elif c == "telegram":
                from plugins import _telegram
                ok = _telegram.para_donos(texto, arquivo, botoes) > 0
            elif c == "discord":
                from plugins import _discord
                ok = _discord.enviar_arquivo(texto, arquivo) if arquivo else _discord.enviar(texto)
            elif c == "ligacao":
                from plugins import ligacao
                ok = ligacao.ligar(texto) == "Ligação feita."
        except Exception as e:
            print(f"[Canais] {c}: {e}")
        if ok:
            usados.append(c)
            if not todos:
                break
    return usados


def ligar(texto: str) -> str:
    try:
        from plugins import ligacao
        if not ligacao.configurada():
            return "A ligação não está configurada (⚙ → Ligação de alerta, com a sua conta Twilio)."
        return ligacao.ligar(texto, forcar=False)
    except Exception as e:
        return f"A ligação falhou: {e}"
