"""
Porta de entrada do J.A.R.V.I.S BR — tela de login (fork PT-BR 2.12).

O que esta tela faz
    * Login de verdade por e-mail e senha (a senha NUNCA é guardada em texto:
      fica só o "resumo" PBKDF2-HMAC-SHA256, com sal aleatório — não dá para
      voltar à senha a partir dele).
    * Cadastro de conta com uma pergunta de segurança, para recuperar a senha
      depois SEM depender de servidor de e-mail (tudo offline, só no seu PC).
    * Entrar por ROSTO ou por VOZ, se você tiver cadastrado — reaproveitando o
      MESMO cadastro que o JARVIS já usa (memory/rostos/dono.npy e
      memory/voz/dono.npy). Cadastrou uma vez, vale para sempre: não pede de
      novo a cada abertura.
    * "Lembrar de mim": da próxima vez abre com um clique, sem digitar senha.

Regra de ouro (resolve o "fica pedindo o rosto / dá erro e não abre")
    A biometria é SEMPRE opcional e NUNCA trava a abertura. Se a câmera, o
    microfone ou os modelos falharem, o botão só avisa e você entra pela senha.
    Nada aqui levanta exceção para a tela — o JARVIS sempre consegue abrir.

Como abre o JARVIS
    Ao entrar, esta janela fecha e roda `main.py` no mesmo console (então o
    iniciar.bat continua mostrando o "por que fechou" normalmente).

Depende de: customtkinter (pip install customtkinter). A parte de contas é só
Python puro — dá para testar sem interface.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import subprocess
import sys
import threading
from pathlib import Path

# ── caminhos ─────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config"
ARQ_CONTAS = CONFIG / "contas.json"
ARQ_API = CONFIG / "api_keys.json"
ARQ_SESSAO = CONFIG / "sessao.json"

_PBKDF2_ROUNDS = 240_000
_SENHA_MINIMA = 6

# cores (do desenho original "JARVIS OS")
C_FUNDO = "#0a0e1a"
C_PAINEL = "#0d1220"
C_CENTRO = "#0f1528"
C_CARD = "#1a1f35"
C_HOVER = "#252b45"
C_ACENTO = "#00d4ff"
C_OK = "#00ff88"
C_ERRO = "#ff5d6c"
C_FRACO = "#888888"


# ══════════════════════════════════════════════════════════════════════════════
#  LÓGICA DE CONTAS  (Python puro — sem interface, dá para testar)
# ══════════════════════════════════════════════════════════════════════════════
def _ler_json(caminho: Path, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def _gravar_json(caminho: Path, dados) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(caminho)


def normalizar_email(email: str) -> str:
    return str(email or "").strip().lower()


def _normalizar_resposta(resposta: str) -> str:
    return " ".join(str(resposta or "").strip().lower().split())


def hash_senha(senha: str, sal: bytes | None = None, rodadas: int = _PBKDF2_ROUNDS) -> dict:
    """Resumo irreversível da senha. Guarda sal + rodadas para conferir depois."""
    sal = sal or secrets.token_bytes(16)
    bruto = hashlib.pbkdf2_hmac("sha256", str(senha or "").encode("utf-8"), sal, rodadas)
    return {
        "algo": "pbkdf2_sha256",
        "rodadas": rodadas,
        "sal": base64.b64encode(sal).decode(),
        "hash": base64.b64encode(bruto).decode(),
    }


def conferir_senha(senha: str, registro: dict) -> bool:
    """Confere uma senha contra o resumo guardado, em tempo constante."""
    try:
        sal = base64.b64decode(registro["sal"])
        esperado = base64.b64decode(registro["hash"])
        rodadas = int(registro.get("rodadas", _PBKDF2_ROUNDS))
    except Exception:
        return False
    bruto = hashlib.pbkdf2_hmac("sha256", str(senha or "").encode("utf-8"), sal, rodadas)
    return hmac.compare_digest(bruto, esperado)


def carregar_contas() -> dict:
    d = _ler_json(ARQ_CONTAS, {}) or {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("contas", {})   # {email: {nome, senha{...}, pergunta, resposta{...}, criada}}
    return d


def _salvar_contas(d: dict) -> None:
    _gravar_json(ARQ_CONTAS, d)


def tem_contas() -> bool:
    return bool(carregar_contas()["contas"])


def validar_email(email: str) -> bool:
    e = normalizar_email(email)
    return bool(e) and "@" in e and "." in e.split("@")[-1] and " " not in e


def criar_conta(email: str, senha: str, nome: str = "",
                pergunta: str = "", resposta: str = "") -> tuple[bool, str]:
    email = normalizar_email(email)
    if not validar_email(email):
        return False, "E-mail inválido. Use algo como voce@exemplo.com."
    if len(str(senha or "")) < _SENHA_MINIMA:
        return False, f"A senha precisa de pelo menos {_SENHA_MINIMA} caracteres."
    d = carregar_contas()
    if email in d["contas"]:
        return False, "Já existe uma conta com esse e-mail. Faça login."
    conta = {
        "nome": str(nome or "").strip(),
        "senha": hash_senha(senha),
        "pergunta": str(pergunta or "").strip(),
        "resposta": hash_senha(_normalizar_resposta(resposta)) if resposta else None,
        "criada": _agora(),
    }
    d["contas"][email] = conta
    _salvar_contas(d)
    return True, "Conta criada. Agora é só entrar."


def autenticar(email: str, senha: str) -> tuple[bool, str, dict | None]:
    email = normalizar_email(email)
    d = carregar_contas()
    conta = d["contas"].get(email)
    if not conta:
        return False, "Não encontrei uma conta com esse e-mail.", None
    if not conferir_senha(senha, conta.get("senha", {})):
        return False, "Senha incorreta.", None
    return True, "Bem-vindo de volta.", conta


def pergunta_de(email: str) -> str:
    conta = carregar_contas()["contas"].get(normalizar_email(email))
    return (conta or {}).get("pergunta", "") if conta else ""


def recuperar_senha(email: str, resposta: str, nova_senha: str) -> tuple[bool, str]:
    email = normalizar_email(email)
    d = carregar_contas()
    conta = d["contas"].get(email)
    if not conta:
        return False, "Não encontrei uma conta com esse e-mail."
    reg = conta.get("resposta")
    if not reg:
        return False, "Essa conta não tem pergunta de segurança cadastrada."
    if not conferir_senha(_normalizar_resposta(resposta), reg):
        return False, "A resposta da pergunta de segurança não confere."
    if len(str(nova_senha or "")) < _SENHA_MINIMA:
        return False, f"A nova senha precisa de pelo menos {_SENHA_MINIMA} caracteres."
    conta["senha"] = hash_senha(nova_senha)
    _salvar_contas(d)
    return True, "Senha redefinida. Já pode entrar com a senha nova."


def definir_usuario_atual(nome: str, email: str = "") -> None:
    """Grava o nome do dono em api_keys.json (sem apagar as outras chaves)."""
    dados = _ler_json(ARQ_API, {}) or {}
    if not isinstance(dados, dict):
        dados = {}
    if nome:
        dados["user_name"] = str(nome).strip()
    if email:
        dados["user_email"] = normalizar_email(email)
    _gravar_json(ARQ_API, dados)


# ── "lembrar de mim" ───────────────────────────────────────────────────────────
def lembrar_sessao(email: str, nome: str) -> None:
    _gravar_json(ARQ_SESSAO, {"email": normalizar_email(email), "nome": nome, "quando": _agora()})


def sessao_lembrada() -> dict | None:
    d = _ler_json(ARQ_SESSAO, None)
    if isinstance(d, dict) and d.get("email") in carregar_contas()["contas"]:
        return d
    return None


def esquecer_sessao() -> None:
    try:
        ARQ_SESSAO.unlink(missing_ok=True)
    except Exception:
        pass


def _agora() -> str:
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


# ══════════════════════════════════════════════════════════════════════════════
#  BIOMETRIA  (sempre opcional, nunca levanta exceção para a tela)
# ══════════════════════════════════════════════════════════════════════════════
def rosto_cadastrado() -> bool:
    try:
        from plugins import reconhecimento_facial as rf
        return rf._load_owner() is not None
    except Exception:
        return False


def voz_cadastrada() -> bool:
    try:
        from plugins import _voz
        return _voz.disponivel() and _voz.perfil() is not None
    except Exception:
        return False


def cadastrar_rosto() -> tuple[bool, str]:
    """Olha para a câmera e guarda a assinatura do rosto (mesmo arquivo do JARVIS)."""
    try:
        from plugins import reconhecimento_facial as rf
        msg = rf._cadastrar(None)
        ok = rf._load_owner() is not None
        return ok, msg
    except Exception as e:
        return False, f"Não deu para cadastrar o rosto agora ({e}). Você ainda pode entrar pela senha."


def verificar_rosto() -> tuple[bool, str]:
    """Confere se quem está na câmera é o dono. Falha nunca trava: cai na senha."""
    try:
        from plugins import reconhecimento_facial as rf
        if rf._load_owner() is None:
            return False, "Nenhum rosto cadastrado ainda."
        res = rf._look(None, frames=6)
        if not res:
            return False, "Não consegui abrir a câmera. Entre pela senha."
        saw_owner, strangers, best = res
        if saw_owner and not strangers:
            return True, f"Rosto reconhecido (confiança {best:.0%})."
        if saw_owner and strangers:
            return False, "Vi você e mais alguém — chegue sozinho na frente da câmera."
        return False, "Não reconheci o rosto. Tente de novo ou use a senha."
    except Exception as e:
        return False, f"O reconhecimento de rosto falhou ({e}). Entre pela senha."


def _capturar_voz(segundos: float = 3.0):
    """Grava um trecho curto do microfone (16 kHz mono int16). None se não der."""
    try:
        import numpy as np  # noqa: F401
        import sounddevice as sd
    except Exception:
        return None
    try:
        from core import placa_som as _placa
        _placa.instalar()
    except Exception:
        pass
    try:
        gravacao = sd.rec(int(segundos * 16000), samplerate=16000, channels=1, dtype="int16")
        sd.wait()
        return gravacao.reshape(-1)
    except Exception:
        return None


def verificar_voz() -> tuple[bool, str]:
    """Confere a voz do dono. Falha nunca trava: cai na senha."""
    try:
        from plugins import _voz
        if not _voz.disponivel():
            return False, "O reconhecimento de voz não está instalado."
        if _voz.perfil() is None:
            return False, "Nenhuma voz cadastrada ainda."
        pcm = _capturar_voz(3.0)
        if pcm is None:
            return False, "Não consegui usar o microfone. Entre pela senha."
        score = _voz.comparar_trecho(pcm)
        if score is None:
            return False, "Não entendi a fala. Fale uma frase inteira e tente de novo."
        if score >= _voz.limiar():
            return True, f"Voz reconhecida (confiança {score:.0%})."
        return False, "A voz não bateu com a cadastrada. Tente de novo ou use a senha."
    except Exception as e:
        return False, f"O reconhecimento de voz falhou ({e}). Entre pela senha."


# ══════════════════════════════════════════════════════════════════════════════
#  ABRIR O JARVIS
# ══════════════════════════════════════════════════════════════════════════════
def abrir_jarvis_bloqueante() -> int:
    """Roda main.py no mesmo console e devolve o código de saída."""
    return subprocess.run([sys.executable, str(BASE / "main.py")], cwd=str(BASE)).returncode


# ══════════════════════════════════════════════════════════════════════════════
#  INTERFACE  (customtkinter) — baseada no desenho "JARVIS OS"
# ══════════════════════════════════════════════════════════════════════════════
def construir_app():
    import customtkinter as ctk

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    class JarvisLogin(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.lancar = False            # vira True quando o login é aprovado
            self.conta_email = ""
            self.conta_nome = ""

            self.title("JARVIS OS - Entrar")
            self.geometry("1100x640")
            self.configure(fg_color=C_FUNDO)
            self.resizable(False, False)
            self._centralizar()

            self.grid_columnconfigure(0, weight=0, minsize=180)
            self.grid_columnconfigure(1, weight=1)
            self.grid_columnconfigure(2, weight=0, minsize=400)
            self.grid_rowconfigure(0, weight=1)

            self._barra_lateral()
            self._centro()
            self._formularios()
            self._rodape()

            # primeira vez (sem conta) → já começa no cadastro
            self.mostrar("signup" if not tem_contas() else "login")

        # ── layout base ──────────────────────────────────────────────────────
        def _centralizar(self):
            self.update_idletasks()
            w, h = 1100, 640
            x = (self.winfo_screenwidth() // 2) - (w // 2)
            y = (self.winfo_screenheight() // 2) - (h // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")

        def _barra_lateral(self):
            import customtkinter as ctk
            self.sidebar = ctk.CTkFrame(self, fg_color=C_PAINEL, corner_radius=0, width=180)
            self.sidebar.grid(row=0, column=0, sticky="nsew")
            self.sidebar.grid_propagate(False)

            topo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            topo.pack(pady=(30, 30))
            ctk.CTkLabel(topo, text="J", font=ctk.CTkFont(size=28, weight="bold"),
                         text_color=C_ACENTO, width=52, height=52,
                         fg_color=C_CARD, corner_radius=12).pack()
            ctk.CTkLabel(topo, text="JARVIS OS", font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=C_ACENTO).pack(pady=(8, 0))

            self.nav = {}
            for texto, modo in (("Entrar", "login"), ("Cadastrar", "signup"),
                                ("Recuperar\nsenha", "recover"), ("Biometria", "bio")):
                btn = ctk.CTkButton(self.sidebar, text=texto, font=ctk.CTkFont(size=13),
                                    height=58, width=140, fg_color=C_CARD, hover_color=C_HOVER,
                                    corner_radius=10, command=lambda m=modo: self.mostrar(m))
                btn.pack(pady=6)
                self.nav[modo] = btn

        def _centro(self):
            import customtkinter as ctk
            self.center = ctk.CTkFrame(self, fg_color=C_CENTRO, corner_radius=0)
            self.center.grid(row=0, column=1, sticky="nsew")

            canvas = ctk.CTkCanvas(self.center, width=280, height=280, bg=C_CENTRO, highlightthickness=0)
            canvas.place(relx=0.5, rely=0.32, anchor="center")
            canvas.create_oval(20, 20, 260, 260, outline=C_ACENTO, width=3)
            canvas.create_oval(40, 40, 240, 240, outline="#00a0cc", width=2)
            canvas.create_line(90, 90, 190, 190, fill=C_ACENTO, width=2)
            canvas.create_line(190, 90, 90, 190, fill=C_ACENTO, width=2)

            self.titulo = ctk.CTkLabel(self.center, text="Bem-vindo\nao JARVIS OS",
                                       font=ctk.CTkFont(size=40, weight="bold"),
                                       text_color="white", justify="center")
            self.titulo.place(relx=0.5, rely=0.62, anchor="center")
            self.subtitulo = ctk.CTkLabel(self.center, text="SISTEMA DE INTELIGÊNCIA PESSOAL · 2.12",
                                          font=ctk.CTkFont(size=12), text_color=C_ACENTO)
            self.subtitulo.place(relx=0.5, rely=0.75, anchor="center")

        # ── formulários ──────────────────────────────────────────────────────
        def _formularios(self):
            import customtkinter as ctk
            self.painel = ctk.CTkFrame(self, fg_color=C_PAINEL, corner_radius=0)
            self.painel.grid(row=0, column=2, sticky="nsew")

            # === LOGIN ===
            self.f_login = ctk.CTkFrame(self.painel, fg_color="transparent")
            ctk.CTkLabel(self.f_login, text="Entrar na sua conta",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(40, 16))

            self.banner_lembrado = ctk.CTkButton(
                self.f_login, text="", height=44, width=320, fg_color=C_CARD,
                hover_color=C_HOVER, text_color=C_ACENTO, command=self._entrar_lembrado)
            # só aparece se houver sessão lembrada (ver mostrar())

            ctk.CTkLabel(self.f_login, text="Seu e-mail", text_color=C_FRACO).pack(anchor="w", padx=40)
            self.login_email = ctk.CTkEntry(self.f_login, width=320, height=42,
                                            placeholder_text="voce@exemplo.com")
            self.login_email.pack(pady=(4, 12), padx=40)
            ctk.CTkLabel(self.f_login, text="Senha", text_color=C_FRACO).pack(anchor="w", padx=40)
            self.login_senha = ctk.CTkEntry(self.f_login, width=320, height=42,
                                            placeholder_text="••••••••", show="•")
            self.login_senha.pack(pady=(4, 8), padx=40)
            self.login_senha.bind("<Return>", lambda _e: self.do_login())

            self.lembrar_var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(self.f_login, text="Lembrar de mim", variable=self.lembrar_var,
                            font=ctk.CTkFont(size=12), text_color=C_FRACO,
                            fg_color=C_ACENTO).pack(anchor="w", padx=40, pady=(0, 8))

            ctk.CTkButton(self.f_login, text="Entrar", height=46, width=320, fg_color=C_ACENTO,
                          text_color=C_FUNDO, command=self.do_login).pack(pady=(6, 10))

            self.linha_bio = ctk.CTkFrame(self.f_login, fg_color="transparent")
            self.linha_bio.pack(pady=(0, 6))
            self.btn_rosto = ctk.CTkButton(self.linha_bio, text="🙂  Entrar com rosto", height=40,
                                           width=150, fg_color=C_CARD, hover_color=C_HOVER,
                                           command=self.do_rosto)
            self.btn_voz = ctk.CTkButton(self.linha_bio, text="🎙  Entrar com voz", height=40,
                                         width=150, fg_color=C_CARD, hover_color=C_HOVER,
                                         command=self.do_voz)

            ctk.CTkButton(self.f_login, text="Não tem conta? Cadastre-se", fg_color="transparent",
                          text_color=C_ACENTO, command=lambda: self.mostrar("signup")).pack(pady=(6, 0))

            # === CADASTRO ===
            self.f_signup = ctk.CTkFrame(self.painel, fg_color="transparent")
            ctk.CTkLabel(self.f_signup, text="Criar sua conta",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(24, 12))
            self.su_nome = self._campo(self.f_signup, "Nome completo", "Seu nome")
            self.su_email = self._campo(self.f_signup, "E-mail", "voce@exemplo.com")
            self.su_senha = self._campo(self.f_signup, "Senha", "Mínimo 6 caracteres", oculto=True)
            self.su_senha2 = self._campo(self.f_signup, "Confirmar senha", "Repita a senha", oculto=True)
            self.su_pergunta = self._campo(self.f_signup, "Pergunta de segurança",
                                           "Ex.: nome do meu primeiro pet")
            self.su_resposta = self._campo(self.f_signup, "Resposta", "A resposta (guarde com você)")
            ctk.CTkButton(self.f_signup, text="Criar conta", height=44, width=320, fg_color=C_ACENTO,
                          text_color=C_FUNDO, command=self.do_signup).pack(pady=(10, 6))
            ctk.CTkButton(self.f_signup, text="Já tem conta? Fazer login", fg_color="transparent",
                          text_color=C_ACENTO, command=lambda: self.mostrar("login")).pack()

            # === RECUPERAR ===
            self.f_recover = ctk.CTkFrame(self.painel, fg_color="transparent")
            ctk.CTkLabel(self.f_recover, text="Recuperar sua senha",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(40, 14))
            self.rec_email = self._campo(self.f_recover, "E-mail cadastrado", "voce@exemplo.com")
            ctk.CTkButton(self.f_recover, text="Buscar pergunta", height=42, width=320,
                          fg_color=C_CARD, hover_color=C_HOVER,
                          command=self.do_buscar_pergunta).pack(pady=(4, 10))
            self.rec_pergunta_lbl = ctk.CTkLabel(self.f_recover, text="", text_color=C_ACENTO,
                                                 wraplength=320, font=ctk.CTkFont(size=13))
            self.rec_pergunta_lbl.pack(padx=40)
            self.rec_resposta = self._campo(self.f_recover, "Resposta", "Sua resposta de segurança")
            self.rec_nova = self._campo(self.f_recover, "Nova senha", "Mínimo 6 caracteres", oculto=True)
            ctk.CTkButton(self.f_recover, text="Redefinir senha", height=44, width=320,
                          fg_color=C_ACENTO, text_color=C_FUNDO,
                          command=self.do_recover).pack(pady=(10, 6))
            ctk.CTkButton(self.f_recover, text="Voltar ao login", fg_color="transparent",
                          text_color=C_ACENTO, command=lambda: self.mostrar("login")).pack()

            # === BIOMETRIA (cadastrar rosto/voz — reaproveita o do JARVIS) ===
            self.f_bio = ctk.CTkFrame(self.painel, fg_color="transparent")
            ctk.CTkLabel(self.f_bio, text="Rosto e voz",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(40, 6))
            ctk.CTkLabel(self.f_bio, text="Cadastre uma vez — vale para entrar aqui e dentro do JARVIS.\n"
                                          "É opcional: a senha sempre funciona.",
                         text_color=C_FRACO, wraplength=320, justify="center").pack(pady=(0, 16), padx=30)
            self.bio_status = ctk.CTkLabel(self.f_bio, text="", text_color=C_ACENTO,
                                           wraplength=320, justify="center")
            self.bio_status.pack(pady=(0, 12), padx=30)
            ctk.CTkButton(self.f_bio, text="Cadastrar meu rosto", height=44, width=320,
                          fg_color=C_CARD, hover_color=C_HOVER,
                          command=self.do_cadastrar_rosto).pack(pady=6)
            ctk.CTkLabel(self.f_bio, text="A voz é cadastrada dentro do JARVIS (diga "
                                          "\"Jarvis, aprenda minha voz\").",
                         text_color=C_FRACO, wraplength=320, justify="center",
                         font=ctk.CTkFont(size=11)).pack(pady=(14, 0), padx=30)
            ctk.CTkButton(self.f_bio, text="Voltar ao login", fg_color="transparent",
                          text_color=C_ACENTO, command=lambda: self.mostrar("login")).pack(pady=(16, 0))

        def _campo(self, pai, rotulo, placeholder, oculto=False):
            import customtkinter as ctk
            ctk.CTkLabel(pai, text=rotulo, text_color=C_FRACO).pack(anchor="w", padx=40)
            ent = ctk.CTkEntry(pai, width=320, height=40, placeholder_text=placeholder,
                               show="•" if oculto else "")
            ent.pack(pady=(4, 8), padx=40)
            return ent

        def _rodape(self):
            import customtkinter as ctk
            barra = ctk.CTkFrame(self, fg_color="#05070f", height=42)
            barra.grid(row=1, column=0, columnspan=3, sticky="ew")
            itens = [
                ("ROSTO", "Cadastrado" if rosto_cadastrado() else "Opcional",
                 C_OK if rosto_cadastrado() else C_FRACO),
                ("VOZ", "Cadastrada" if voz_cadastrada() else "Opcional",
                 C_OK if voz_cadastrada() else C_FRACO),
                ("PYTHON", "Pronto", C_ACENTO),
            ]
            for rotulo, valor, cor in itens:
                f = ctk.CTkFrame(barra, fg_color="transparent")
                f.pack(side="left", expand=True, pady=6)
                ctk.CTkLabel(f, text=rotulo, text_color="#666", font=ctk.CTkFont(size=10)).pack()
                ctk.CTkLabel(f, text=valor, text_color=cor,
                             font=ctk.CTkFont(size=11, weight="bold")).pack()

        # ── navegação ────────────────────────────────────────────────────────
        def mostrar(self, modo):
            for f in (self.f_login, self.f_signup, self.f_recover, self.f_bio):
                f.pack_forget()
            for b in self.nav.values():
                b.configure(fg_color=C_CARD, text_color="#ffffff")
            self.nav[modo].configure(fg_color=C_ACENTO, text_color=C_FUNDO)

            textos = {
                "login": ("Bem-vindo\nao JARVIS OS", "ENTRE PARA COMEÇAR"),
                "signup": ("Junte-se\nao JARVIS OS", "CRIE SUA CONTA"),
                "recover": ("Recuperar\nAcesso", "RESPONDA SUA PERGUNTA"),
                "bio": ("Rosto e\nVoz", "ENTRAR SEM DIGITAR SENHA"),
            }
            self.titulo.configure(text=textos[modo][0])
            self.subtitulo.configure(text=textos[modo][1])

            if modo == "login":
                self.f_login.pack(fill="both", expand=True)
                self._ajustar_login()
            elif modo == "signup":
                self.f_signup.pack(fill="both", expand=True)
            elif modo == "recover":
                self.f_recover.pack(fill="both", expand=True)
            else:
                self.f_bio.pack(fill="both", expand=True)
                self.bio_status.configure(
                    text="Rosto já cadastrado ✔" if rosto_cadastrado() else "Nenhum rosto cadastrado ainda.")

        def _ajustar_login(self):
            # botões de biometria só aparecem se houver cadastro
            self.btn_rosto.pack_forget()
            self.btn_voz.pack_forget()
            if rosto_cadastrado():
                self.btn_rosto.pack(side="left", padx=6)
            if voz_cadastrada():
                self.btn_voz.pack(side="left", padx=6)
            # banner "continuar como ..." se houver sessão lembrada
            sess = sessao_lembrada()
            self.banner_lembrado.pack_forget()
            if sess:
                nome = sess.get("nome") or sess.get("email")
                self.banner_lembrado.configure(text=f"➜  Continuar como {nome}")
                self.banner_lembrado.pack(pady=(0, 14), padx=40)
                self.login_email.delete(0, "end")
                self.login_email.insert(0, sess.get("email", ""))

        # ── ações ────────────────────────────────────────────────────────────
        def do_login(self):
            email = self.login_email.get()
            senha = self.login_senha.get()
            if not email or not senha:
                return self.aviso("Preencha e-mail e senha.")
            ok, msg, conta = autenticar(email, senha)
            if not ok:
                return self.aviso(msg)
            self._entrar(email, conta.get("nome", ""), lembrar=self.lembrar_var.get())

        def _entrar_lembrado(self):
            sess = sessao_lembrada()
            if sess:
                self._entrar(sess["email"], sess.get("nome", ""), lembrar=True)

        def do_signup(self):
            nome = self.su_nome.get().strip()
            email = self.su_email.get()
            senha = self.su_senha.get()
            senha2 = self.su_senha2.get()
            pergunta = self.su_pergunta.get().strip()
            resposta = self.su_resposta.get().strip()
            if not all([email, senha, senha2]):
                return self.aviso("Preencha e-mail e as duas senhas.")
            if senha != senha2:
                return self.aviso("As senhas não coincidem.")
            if pergunta and not resposta:
                return self.aviso("Você pôs uma pergunta de segurança — responda-a também.")
            ok, msg = criar_conta(email, senha, nome, pergunta, resposta)
            self.aviso(msg)
            if ok:
                self.login_email.delete(0, "end")
                self.login_email.insert(0, normalizar_email(email))
                self.mostrar("login")

        def do_buscar_pergunta(self):
            email = self.rec_email.get()
            q = pergunta_de(email)
            if not carregar_contas()["contas"].get(normalizar_email(email)):
                self.rec_pergunta_lbl.configure(text="Não encontrei conta com esse e-mail.", text_color=C_ERRO)
            elif not q:
                self.rec_pergunta_lbl.configure(
                    text="Essa conta não tem pergunta de segurança. Peça ajuda de outra forma.", text_color=C_ERRO)
            else:
                self.rec_pergunta_lbl.configure(text=f"Pergunta: {q}", text_color=C_ACENTO)

        def do_recover(self):
            ok, msg = recuperar_senha(self.rec_email.get(), self.rec_resposta.get(), self.rec_nova.get())
            self.aviso(msg)
            if ok:
                self.mostrar("login")

        def do_rosto(self):
            self._biometria_async(verificar_rosto, "Olhando para a câmera…")

        def do_voz(self):
            self._biometria_async(verificar_voz, "Fale uma frase inteira agora…")

        def do_cadastrar_rosto(self):
            self.bio_status.configure(text="Olhe para a câmera e mexa a cabeça devagar…", text_color=C_ACENTO)

            def tarefa():
                ok, msg = cadastrar_rosto()
                self.after(0, lambda: (
                    self.bio_status.configure(text=msg, text_color=C_OK if ok else C_ERRO),
                    self._rodape_atualizar()))
            threading.Thread(target=tarefa, daemon=True).start()

        def _biometria_async(self, funcao, msg_espera):
            self.aviso(msg_espera, auto=True)

            def tarefa():
                ok, msg = funcao()
                self.after(0, lambda: self._pos_biometria(ok, msg))
            threading.Thread(target=tarefa, daemon=True).start()

        def _pos_biometria(self, ok, msg):
            if ok:
                email = self.login_email.get() or (sessao_lembrada() or {}).get("email", "")
                conta = carregar_contas()["contas"].get(normalizar_email(email), {})
                self._entrar(email, conta.get("nome", ""), lembrar=True)
            else:
                self.aviso(msg)

        def _entrar(self, email, nome, lembrar=False):
            definir_usuario_atual(nome, email)
            if lembrar:
                lembrar_sessao(email, nome)
            else:
                esquecer_sessao()
            self.lancar = True
            self.destroy()

        def _rodape_atualizar(self):
            # recria o rodapé para refletir o novo cadastro
            try:
                self._rodape()
            except Exception:
                pass

        # ── caixinha de aviso ──────────────────────────────────────────────────
        def aviso(self, texto, auto=False):
            import customtkinter as ctk
            win = ctk.CTkToplevel(self)
            win.title("JARVIS OS")
            win.geometry("400x170")
            win.configure(fg_color=C_FUNDO)
            win.transient(self)
            try:
                win.grab_set()
            except Exception:
                pass
            ctk.CTkLabel(win, text=texto, font=ctk.CTkFont(size=14), text_color=C_ACENTO,
                         wraplength=360).pack(pady=(34, 14))
            ctk.CTkButton(win, text="OK", fg_color=C_ACENTO, text_color=C_FUNDO,
                          command=win.destroy).pack()
            if auto:
                win.after(1600, lambda: win.winfo_exists() and win.destroy())
            return win

    return JarvisLogin()


def main() -> None:
    try:
        app = construir_app()
    except Exception as e:
        # Sem customtkinter? Não trava o usuário: abre o JARVIS direto.
        print(f"[Login] Interface indisponível ({e}). Abrindo o JARVIS direto.")
        raise SystemExit(abrir_jarvis_bloqueante())
    app.mainloop()
    if getattr(app, "lancar", False):
        raise SystemExit(abrir_jarvis_bloqueante())
    # fechou a janela sem entrar → não abre o JARVIS
    raise SystemExit(0)


if __name__ == "__main__":
    main()
