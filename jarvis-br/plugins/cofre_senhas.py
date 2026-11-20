"""
Cofre de senhas offline (fork PT-BR 2.16, ideia 18).

    "Jarvis, guarda a senha do Instagram"       → abre uma caixinha para você digitar (ou gerar)
    "Jarvis, gera uma senha forte para o banco"
    "Jarvis, copia a senha do Instagram"        → copia para a área de transferência por 20 s
    "Jarvis, quais senhas eu guardei?"          → só os NOMES
    "Jarvis, apaga a senha do Netflix"          → com confirmação na tela
    "Jarvis, tranca o cofre"

SEGURANÇA
    • O cofre (memory/cofre.bin) é criptografado com AES (Fernet, da biblioteca
      cryptography) e uma chave tirada da sua SENHA MESTRA com scrypt. Sem ela,
      ninguém abre — nem o JARVIS. Perdeu a senha mestra, perdeu o cofre.
    • A senha mestra e as senhas são digitadas numa caixinha com asteriscos: NÃO
      passam pela conversa, pela IA nem pelo registro.
    • O JARVIS NUNCA fala nem escreve uma senha. Ele só COPIA, e apaga da área de
      transferência sozinho depois de 20 segundos (e o histórico da área de
      transferência do JARVIS não guarda isso).
    • Destrancado, o cofre fica aberto só na memória, por 5 minutos.
    • Pedidos que chegam pelo celular/WhatsApp não abrem o cofre.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import string
import threading
import time

from plugins._comum import MEMORIA, confirmar

PLUGIN = {
    "name": "cofre_senhas",
    "brief": "Offline encrypted password vault: save (typed in a hidden box), generate, copy for 20 s, list names, delete.",
    "description": (
        "Encrypted offline password vault. action='guardar' with nome (site/app) and optional usuario — the password is "
        "typed by the user in a hidden box (NEVER ask him to say it). action='gerar' with nome creates a strong password "
        "and stores it. action='copiar' with nome copies it to the clipboard for 20 seconds. action='listar' lists names "
        "only. action='apagar' with nome (on-screen confirmation). action='trancar'. NEVER speak, write or repeat a "
        "password; the tool never returns one."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "guardar | gerar | copiar | listar | apagar | trancar"},
                       "nome": {"type": "STRING"}, "usuario": {"type": "STRING"}, "tamanho": {"type": "INTEGER"}},
        "required": ["action"],
    },
}

ARQ = MEMORIA / "cofre.bin"
ABERTO_S = 300
LIMPAR_S = 20
_sessao = {"chave": None, "ate": 0.0, "dados": None}
_lock = threading.Lock()


# ── criptografia ──────────────────────────────────────────────────────────────
def derivar(senha: str, sal: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return base64.urlsafe_b64encode(Scrypt(salt=sal, length=32, n=2 ** 15, r=8, p=1).derive(senha.encode("utf-8")))


def selar(dados: dict, chave: bytes, sal: bytes) -> bytes:
    from cryptography.fernet import Fernet
    return b"JVC1" + sal + Fernet(chave).encrypt(json.dumps(dados).encode("utf-8"))


def abrir(blob: bytes, senha: str) -> tuple[dict, bytes, bytes]:
    """(dados, chave, sal). Senha errada → ValueError (pura)."""
    from cryptography.fernet import Fernet, InvalidToken
    if not blob.startswith(b"JVC1"):
        raise ValueError("arquivo do cofre inválido")
    sal, corpo = blob[4:20], blob[20:]
    chave = derivar(senha, sal)
    try:
        return json.loads(Fernet(chave).decrypt(corpo)), chave, sal
    except InvalidToken as e:
        raise ValueError("senha mestra errada") from e


def gerar_senha(n: int = 20) -> str:
    """Senha aleatória com maiúscula, minúscula, número e símbolo (pura)."""
    n = max(12, min(64, int(n or 20)))
    simbolos = "!@#$%&*?-_+="
    alfabeto = string.ascii_letters + string.digits + simbolos
    while True:
        s = "".join(secrets.choice(alfabeto) for _ in range(n))
        if (any(c.islower() for c in s) and any(c.isupper() for c in s) and any(c.isdigit() for c in s)
                and any(c in simbolos for c in s)):
            return s


# ── interface ─────────────────────────────────────────────────────────────────
def _caixa(player, titulo: str, texto: str) -> str | None:
    from plugins import senha_vazada
    try:
        from core import qt_bridge
        if player is None or not qt_bridge.disponivel():
            return None
        pronto, caixa = threading.Event(), {}

        def abrir_caixa():
            try:
                from PyQt6.QtWidgets import QInputDialog, QLineEdit
                t, ok = QInputDialog.getText(None, titulo, texto, QLineEdit.EchoMode.Password)
                caixa["v"] = t if ok and t else None
            except Exception:
                caixa["v"] = None
            finally:
                pronto.set()
        if not qt_bridge.na_interface(abrir_caixa):
            return None
        pronto.wait(180)
        return caixa.get("v")
    except Exception:
        return senha_vazada.pedir_senha(player)


def _remoto() -> bool:
    try:
        from core import verificacao
        return float(verificacao._estado.get("remoto_ate", 0)) > time.time()
    except Exception:
        return False


def _destrancar(player) -> str | None:
    """None se abriu; senão, a mensagem do problema."""
    with _lock:
        if _sessao["chave"] and time.time() < _sessao["ate"]:
            _sessao["ate"] = time.time() + ABERTO_S
            return None
    if _remoto():
        return "Por segurança, o cofre não abre por pedido do celular. Peça no PC."
    if not ARQ.exists():
        s1 = _caixa(player, "J.A.R.V.I.S — criar cofre", "Crie a SENHA MESTRA do cofre (anote em lugar seguro):")
        if not s1:
            return "Cancelado."
        if len(s1) < 8:
            return "A senha mestra precisa ter pelo menos 8 caracteres."
        s2 = _caixa(player, "J.A.R.V.I.S — criar cofre", "Digite a senha mestra de novo:")
        if s1 != s2:
            return "As duas senhas mestras não batem. Nada foi criado."
        sal = os.urandom(16)
        chave = derivar(s1, sal)
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        ARQ.write_bytes(selar({"senhas": {}}, chave, sal))
        with _lock:
            _sessao.update(chave=chave, sal=sal, ate=time.time() + ABERTO_S, dados={"senhas": {}})
        return None
    s = _caixa(player, "J.A.R.V.I.S — cofre", "Senha mestra do cofre:")
    if not s:
        return "Cancelado."
    try:
        dados, chave, sal = abrir(ARQ.read_bytes(), s)
    except ValueError as e:
        return f"Não abri o cofre: {e}."
    with _lock:
        _sessao.update(chave=chave, sal=sal, ate=time.time() + ABERTO_S, dados=dados)
    return None


def _gravar() -> None:
    ARQ.write_bytes(selar(_sessao["dados"], _sessao["chave"], _sessao["sal"]))


def _copiar_temporario(segredo: str) -> None:
    import pyperclip
    pyperclip.copy(segredo)                       # o histórico do JARVIS já ignora o que parece senha

    def limpar():
        time.sleep(LIMPAR_S)
        try:
            if pyperclip.paste() == segredo:
                pyperclip.copy("")
        except Exception:
            pass
    threading.Thread(target=limpar, daemon=True).start()


def _achar(nome: str) -> str | None:
    n = nome.strip().lower()
    senhas = _sessao["dados"]["senhas"]
    if n in senhas:
        return n
    parecidos = [k for k in senhas if n in k or k in n]
    return parecidos[0] if len(parecidos) == 1 else None


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    nome = str(p.get("nome") or "").strip().lower()
    try:
        if a == "trancar":
            with _lock:
                _sessao.update(chave=None, ate=0.0, dados=None)
            return "Cofre trancado."
        problema = _destrancar(player)
        if problema:
            return problema
        senhas = _sessao["dados"]["senhas"]
        if a == "listar":
            if not senhas:
                return "O cofre está vazio."
            return "No cofre: " + ", ".join(sorted(senhas)) + "."
        if not nome:
            return "De qual site ou app?"
        if a in ("guardar", "gerar"):
            if a == "gerar":
                segredo = gerar_senha(int(p.get("tamanho") or 20))
            else:
                segredo = _caixa(player, "J.A.R.V.I.S — cofre", f"Senha de {nome} (deixe vazio e OK para cancelar):")
                if not segredo:
                    return "Cancelado; nada foi guardado."
            senhas[nome] = {"senha": segredo, "usuario": str(p.get("usuario") or ""),
                            "atualizada": time.strftime("%Y-%m-%d")}
            _gravar()
            if a == "gerar":
                _copiar_temporario(segredo)
                return (f"Gerei e guardei uma senha forte para {nome}. Ela está copiada por {LIMPAR_S} segundos: cole "
                        "no site agora.")
            return f"Senha de {nome} guardada no cofre."
        chave = _achar(nome)
        if not chave:
            return f"Não achei '{nome}' no cofre." if not any(nome in k for k in senhas) else \
                "Achei mais de uma; diga o nome exato: " + ", ".join(k for k in senhas if nome in k) + "."
        if a == "copiar":
            item = senhas[chave]
            _copiar_temporario(item["senha"])
            usuario = f" O usuário é {item['usuario']}." if item.get("usuario") else ""
            return f"Senha de {chave} copiada. Some da área de transferência em {LIMPAR_S} segundos.{usuario}"
        if a == "apagar":
            def executar():
                senhas.pop(chave, None)
                _gravar()
                return f"Senha de {chave} apagada do cofre."
            return confirmar(f"cofre_apagar_{chave}", f"Apagar a senha de {chave}?", "Não dá para desfazer.", executar)
        return "Use guardar, gerar, copiar, listar, apagar ou trancar."
    except Exception as e:
        return f"O cofre falhou: {e.__class__.__name__}"     # nunca mostra detalhes que possam ter segredo
