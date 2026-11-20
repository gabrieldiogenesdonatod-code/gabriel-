"""
WhatsApp ↔ J.A.R.V.I.S (fork PT-BR 1.8). Começa com "_": não é ferramenta.

Liga a ponte Node (whatsapp_ponte/ponte.js, whatsapp-web.js), lê as mensagens
do DONO e responde. Quem é dono:
  • você mesmo, no chat "Você" (mensagem para mim), se a ponte estiver no seu número;
  • os números da opção "Números do dono" (⚙ → WhatsApp do JARVIS);
  • quem mandar o código de pareamento que o JARVIS mostra na tela ("autoriza meu whats").
Mensagens de qualquer outra pessoa nem chegam aqui (a ponte filtra).

Comandos rápidos (respondem na hora, sem IA): foto, foto 2, tela, status,
link, câmeras, confirmar, cancelar, ajuda. O resto vira pedido para o JARVIS,
com as mesmas ferramentas da voz; a resposta volta por texto e, por padrão, NÃO
é falada em casa. Áudio é transcrito; foto com legenda é explicada.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

from plugins._comum import BASE, CNW, MEMORIA, WIN, cfg, gravar_json, ler_json

PASTA = BASE / "whatsapp_ponte"
SESSAO = MEMORIA / "whatsapp_sessao"
ARQ = MEMORIA / "whatsapp.json"
LOG = SESSAO / "ponte.log"

PLUGIN_SETTINGS = {
    "namespace": "whatsapp",
    "title": "WhatsApp do JARVIS",
    "fields": [
        {"key": "donos", "label": "Números do dono (com DDD, separados por vírgula)", "type": "text", "default": ""},
        {"key": "falar_em_casa", "label": "Também falar em voz alta no PC as respostas do WhatsApp", "type": "toggle",
         "default": False},
        {"key": "avisos", "label": "Mandar os avisos do JARVIS (Sentinela, alertas) no WhatsApp", "type": "toggle",
         "default": True},
        {"key": "confirmar_pelo_whats", "label": "Aceitar 'confirmar' pelo WhatsApp para ações com confirmação",
         "type": "toggle", "default": True},
        {"key": "ligar_ao_abrir", "label": "Ligar o WhatsApp quando o JARVIS abrir", "type": "toggle", "default": False},
        {"key": "modo_loja", "label": "Modo loja: mensagens de clientes viram RASCUNHO de resposta para você aprovar "
         "(nada é enviado sozinho)", "type": "toggle", "default": False},
        # 2.3: o JARVIS lê as SUAS conversas privadas (nunca grupos) e conversa por você só onde você liberar.
        {"key": "modo_pessoal", "label": "Modo pessoal: o JARVIS lê as mensagens que outras pessoas te mandam (conversas "
         "privadas, nunca grupos) para te avisar e sugerir resposta", "type": "toggle", "default": False},
        {"key": "rascunho_pessoal", "label": "No modo pessoal, já preparar um RASCUNHO de resposta para você aprovar",
         "type": "toggle", "default": True},
        {"key": "auto_contatos", "label": "Resposta AUTOMÁTICA liberada para estes contatos (nomes ou números, separados "
         "por vírgula). O JARVIS sempre se apresenta como seu assistente", "type": "text", "default": ""},
        {"key": "secretaria", "label": "Secretária: recusar ligações do WhatsApp e pedir um recado por mensagem",
         "type": "toggle", "default": False},
        {"key": "nome_dono", "label": "Seu nome (o JARVIS se apresenta como 'Assistente de …')", "type": "text",
         "default": ""},
    ],
}

_p: dict = {"proc": None, "porta": 0, "token": "", "ultimo": 0, "thread": None}
_lock = threading.Lock()
_parar = threading.Event()


def config() -> dict:
    return cfg("whatsapp", PLUGIN_SETTINGS)


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def so_digitos(t: str) -> str:
    return re.sub(r"\D", "", str(t or ""))


def mesmo_numero(a: str, b: str) -> bool:
    """'62 99999-1234' == '5562999991234' (com/sem 55, com/sem DDD, com/sem o 9 extra) (pura)."""
    def norm(x):
        x = so_digitos(x)
        return x[2:] if x.startswith("55") and len(x) >= 12 else x
    na, nb = norm(a), norm(b)
    if len(na) < 8 or len(nb) < 8 or na[-8:] != nb[-8:]:
        return False
    return na[:2] == nb[:2] if len(na) >= 10 and len(nb) >= 10 else True


def decidir(ev: dict, ids: list[str], numeros: list[str], codigo: str) -> str:
    """'dono', 'parear', 'ligacao', 'outro', 'cliente' ou 'ignorar'."""
    if ev.get("ligacao"):
        return "ligacao"                                       # a ligação do próprio dono também (ev['dono'])
    if ev.get("eu"):
        return "dono"
    if ev.get("chat") in ids:
        return "dono"
    if ev.get("numero") and any(mesmo_numero(ev["numero"], n) for n in numeros):
        return "dono"
    if codigo and codigo.upper() in str(ev.get("texto") or "").upper():
        return "parear"
    if ev.get("outro") and (ev.get("recado") or ev.get("contato") or not ev.get("cliente")):
        return "outro"                                         # 2.3: modo pessoal (contatos salvos ganham da loja)
    if ev.get("cliente"):
        return "cliente"
    return "ignorar"


COMANDOS = [
    ("ajuda", r"(ajuda|menu|comandos|\?|o que voce faz)"),
    ("confirmar", r"(sim[, ]*)?(confirm[ao]r?|confirmo|pode confirmar)"),
    ("cancelar", r"(nao[, ]*)?(cancel[ao]r?|cancela isso)"),
    ("foto", r"(manda (uma )?)?(foto|camera|cam)( da camera| do pc)?( \d+)?"),
    ("tela", r"(manda (um |a )?)?(print|tela|screenshot)( do pc| da tela)?"),
    ("status", r"(status|como (esta|ta) o pc\??)"),
    ("link", r"(link|acesso|painel|central)( do painel| remoto)?"),
    ("cameras", r"(cameras|lista (de )?cameras)"),
]


def comando_rapido(texto: str) -> tuple[str, int]:
    """Mensagem curta que é comando direto → (nome, número da câmera). ('', 0) se não for."""
    t = re.sub(r"[!.]+$", "", _dobrar(texto)).strip()
    if len(t) > 40:
        return "", 0
    for nome, padrao in COMANDOS:
        if re.fullmatch(padrao, t):
            n = re.search(r"(\d+)$", t)
            return nome, int(n.group(1)) - 1 if (nome == "foto" and n) else 0
    return "", 0


AJUDA = ("Sou o J.A.R.V.I.S. Pode falar normalmente comigo, como na voz (\"liga a TV da sala\", \"como está o PC\", "
         "\"me lembra às 18h\"). Atalhos: *foto* (ou *foto 2*), *tela*, *status*, *link*, *câmeras*, *confirmar*, "
         "*cancelar*. Mande áudio que eu transcrevo; mande foto com uma pergunta que eu explico.")


# ── ponte ──────────────────────────────────────────────────────────────────────
def node_exe() -> str | None:
    achado = shutil.which("node")
    if achado:
        return achado
    c = Path(r"C:\Program Files\nodejs\node.exe")
    return str(c) if c.exists() else None


def npm_exe() -> str | None:
    achado = shutil.which("npm.cmd" if WIN else "npm") or shutil.which("npm")
    if achado:
        return achado
    c = Path(r"C:\Program Files\nodejs\npm.cmd")
    return str(c) if c.exists() else None


def navegador_exe() -> str | None:
    """Edge ou Chrome já instalados (2.2: a ponte usa ele e não baixa os 150 MB do Chromium)."""
    if WIN:
        bases = [os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("LOCALAPPDATA", "")]
        for b in bases:
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe"):
                c = Path(b) / rel
                if b and c.exists():
                    return str(c)
        return None
    for nome in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
        achado = shutil.which(nome)
        if achado:
            return achado
    mac = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    return str(mac) if mac.exists() else None


def dependencias_ok() -> bool:
    return (PASTA / "node_modules" / "whatsapp-web.js").exists() and (PASTA / "node_modules" / "qrcode").exists()


def instalar() -> str:
    if not node_exe():
        if WIN and shutil.which("winget"):
            from plugins._comum import rodar
            cod, out = rodar(["winget", "install", "--id", "OpenJS.NodeJS.LTS", "-e", "--silent",
                              "--accept-source-agreements", "--accept-package-agreements"], timeout=900)
            if cod != 0 and "instal" not in out.lower():
                return f"Não consegui instalar o Node.js: {out[-200:]}. Baixe em https://nodejs.org (versão LTS)."
            return "Instalei o Node.js. Feche e abra o JARVIS de novo e peça 'liga o WhatsApp'."
        return "Preciso do Node.js (https://nodejs.org, versão LTS). Instale e peça de novo."
    npm = npm_exe()
    if not npm:
        return "Achei o Node, mas não o npm. Reinstale o Node.js LTS."
    try:
        env = dict(os.environ)
        if navegador_exe():                                     # 2.2: já tem Edge/Chrome → não baixa o Chromium
            env.update(PUPPETEER_SKIP_DOWNLOAD="1", PUPPETEER_SKIP_CHROMIUM_DOWNLOAD="1")
        r = subprocess.run([npm, "install", "--omit=dev", "--no-audit", "--no-fund"], cwd=str(PASTA),
                           capture_output=True, timeout=1500, env=env, **CNW)
        if r.returncode != 0 or not dependencias_ok():
            return "O npm não conseguiu instalar: " + (r.stderr or r.stdout or b"").decode("utf-8", "replace")[-300:]
        return ""
    except subprocess.TimeoutExpired:
        return "A instalação demorou demais (ela baixa um navegador de ~150 MB). Tente de novo."
    except Exception as e:
        return f"Falhou: {e}"


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def rodando() -> bool:
    p = _p["proc"]
    return p is not None and p.poll() is None


def _http(metodo: str, caminho: str, corpo: dict | None = None, timeout: float = 15) -> dict:
    if not _p["porta"]:
        return {"erro": "ponte desligada"}
    req = urllib.request.Request(f"http://127.0.0.1:{_p['porta']}{caminho}", method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"X-Token": _p["token"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}") or {"erro": str(e)}
        except ValueError:
            return {"erro": str(e)}
    except Exception as e:
        return {"erro": str(e)}


def iniciar() -> str:
    """Liga a ponte (instala na primeira vez). '' = ligou."""
    with _lock:
        if rodando():
            return ""
    if not dependencias_ok():
        erro = instalar()
        if erro:
            return erro
    node = node_exe()
    if not node:
        return "Preciso do Node.js (https://nodejs.org, versão LTS)."
    SESSAO.mkdir(parents=True, exist_ok=True)
    porta, token = _porta_livre(), secrets.token_urlsafe(24)
    env = dict(os.environ, JARVIS_WA_PORTA=str(porta), JARVIS_WA_TOKEN=token, JARVIS_WA_SESSAO=str(SESSAO),
               JARVIS_WA_MIDIA=str(SESSAO / "midia"))
    nav = navegador_exe()
    if nav:
        env["JARVIS_WA_NAVEGADOR"] = nav
    try:
        log = open(LOG, "a", encoding="utf-8")
        proc = subprocess.Popen([node, str(PASTA / "ponte.js")], cwd=str(PASTA), env=env, stdin=subprocess.PIPE,
                                stdout=log, stderr=subprocess.STDOUT, **CNW)
        log.close()
    except OSError as e:
        return f"A ponte não abriu: {e}"
    with _lock:
        _p.update(proc=proc, porta=porta, token=token, ultimo=0)
    for _ in range(40):                                        # espera a ponte ouvir
        if _http("GET", "/estado", timeout=2).get("estado"):
            break
        if proc.poll() is not None:
            return "A ponte fechou ao iniciar. Veja memory/whatsapp_sessao/ponte.log."
        time.sleep(0.25)
    enviar_donos_para_ponte()
    _parar.clear()
    if _p["thread"] is None or not _p["thread"].is_alive():
        _p["thread"] = threading.Thread(target=_laco, daemon=True, name="whatsapp")
        _p["thread"].start()
    return ""


# ── 2.2: ligar em segundo plano, com a etapa visível na tela do QR ───────────
preparo = {"etapa": "", "erro": "", "desde": 0.0}


def ultimas_linhas_log(n: int = 6) -> str:
    try:
        return "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def iniciar_em_segundo_plano() -> None:
    """Instala (se preciso) e liga sem travar a conversa; a página /whatsapp mostra o andamento e o QR."""
    if preparo["etapa"] in ("instalando", "abrindo") and time.time() - preparo["desde"] < 1800:
        return

    def tarefa():
        preparo.update(erro="", desde=time.time())
        if not dependencias_ok():
            preparo["etapa"] = "instalando"
            erro = instalar()
            if erro:
                preparo.update(etapa="erro", erro=erro)
                return
        preparo["etapa"] = "abrindo"
        erro = iniciar()
        preparo.update(etapa="erro" if erro else "ligada", erro=erro)
    threading.Thread(target=tarefa, daemon=True, name="whatsapp_preparo").start()


def estado_para_tela() -> dict:
    """O que a página do QR mostra."""
    e = estado() if rodando() else {"estado": "desligado"}
    saida = {"estado": e.get("estado", "desligado"), "qr": e.get("qr", ""), "numero": e.get("numero", ""),
             "etapa": preparo["etapa"], "erro": preparo["erro"] or e.get("erro", ""),
             "node": bool(node_exe()), "navegador": bool(navegador_exe())}
    if saida["estado"] in ("falha", "desconectado") or saida["etapa"] == "erro":
        saida["log"] = ultimas_linhas_log()
    return saida


def parar() -> bool:
    _parar.set()
    with _lock:
        p, _p["proc"], _p["porta"] = _p["proc"], None, 0
    if p is None or p.poll() is not None:
        return False
    try:
        p.stdin.close()                                        # a ponte fecha sozinha quando a entrada acaba
        p.wait(timeout=10)
    except Exception:
        p.kill()
    return True


def estado() -> dict:
    if not rodando():
        return {"estado": "desligado"}
    return _http("GET", "/estado", timeout=5) or {"estado": "?"}


def pronto() -> bool:
    return rodando() and estado().get("estado") == "pronto"


def qr_png() -> Path | None:
    arq = SESSAO / "qr.png"
    return arq if arq.exists() else None


# ── donos ────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("ids", [])
    d.setdefault("codigo", "")
    return d


def numeros_dono() -> list[str]:
    return [n for n in (so_digitos(x) for x in str(config().get("donos") or "").split(",")) if len(n) >= 8]


def enviar_donos_para_ponte() -> None:
    d = dados()
    c = config()
    _http("POST", "/donos", {"ids": d["ids"], "codigo": d["codigo"], "numeros": numeros_dono(),
                             "loja": bool(c.get("modo_loja")), "pessoal": bool(c.get("modo_pessoal")),
                             "secretaria": bool(c.get("secretaria"))}, timeout=5)


def novo_codigo() -> str:
    d = dados()
    d["codigo"] = "J" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
    gravar_json(ARQ, d)
    enviar_donos_para_ponte()
    return d["codigo"]


def adicionar_dono(chat: str) -> None:
    d = dados()
    if chat not in d["ids"]:
        d["ids"].append(chat)
    d["codigo"] = ""
    gravar_json(ARQ, d)
    enviar_donos_para_ponte()


def remover_donos() -> int:
    d = dados()
    n = len(d["ids"])
    d.update(ids=[], codigo="")
    gravar_json(ARQ, d)
    enviar_donos_para_ponte()
    return n


def chats_dono() -> list[str]:
    """Chats para onde vão os avisos: o "Você" (mensagem para mim) e quem já falou como dono."""
    ids = list(dados()["ids"])
    numero = estado().get("numero") if rodando() else ""
    if numero:                                                 # o chat "Você" (mensagem para mim)
        ids.append(f"{numero}@c.us")
    vistos, saida = set(), []
    for i in ids:
        if i not in vistos:
            vistos.add(i)
            saida.append(i)
    return saida


# ── enviar ───────────────────────────────────────────────────────────────────
def enviar(chat: str, texto: str = "", arquivo: str | Path | None = None, sem_prefixo: bool = False) -> bool:
    corpo = {"para": chat, "texto": texto[:4000], "sem_prefixo": sem_prefixo}
    if arquivo:
        corpo = {"para": chat, "arquivo": str(arquivo), "legenda": texto[:1000] or "📷"}
    r = _http("POST", "/enviar", corpo, timeout=60)
    if r.get("erro"):
        print(f"[WhatsApp] envio falhou: {r['erro']}")
    return bool(r.get("ok"))


def para_donos(texto: str, arquivo: str | Path | None = None) -> int:
    if not pronto():
        return 0
    return sum(enviar(c, texto, arquivo) for c in chats_dono())


# ── receber ──────────────────────────────────────────────────────────────────
def _laco() -> None:
    while not _parar.is_set():
        if not rodando():
            time.sleep(2)
            continue
        r = _http("GET", f"/eventos?desde={_p['ultimo']}", timeout=10)
        for ev in r.get("eventos") or []:
            _p["ultimo"] = max(_p["ultimo"], int(ev.get("n", 0)))
            try:
                tratar(ev)
            except Exception as e:
                print(f"[WhatsApp] erro: {e}")
        time.sleep(1)


def transcrever_audio(arq: str) -> str:
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel("base", device="cpu", compute_type="int8")
        segs, _ = m.transcribe(str(arq), language="pt", vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip()
    except ImportError:
        pass
    except Exception as e:
        print(f"[WhatsApp] whisper: {e}")
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return ""
        from google.genai import types as gtypes

        from core import gemini
        resp = gemini.call([gtypes.Part.from_bytes(data=Path(arq).read_bytes(), mime_type="audio/ogg"),
                            "Transcreva exatamente o que foi falado (português do Brasil). Responda só o texto."],
                           tier=gemini.FAST, timeout_ms=60_000)
        return ((getattr(resp, "text", "") or "") if resp is not None else "").strip()
    except Exception as e:
        print(f"[WhatsApp] transcrição: {e}")
        return ""


def executar_rapido(nome: str, cam: int = 0) -> tuple[str, Path | None]:
    from plugins import _camera_remota as cr
    if nome == "ajuda":
        return AJUDA, None
    if nome == "foto":
        dadosjpg, erro = cr.foto_jpeg(cam, largura=1280, qualidade=80)
        if not dadosjpg:
            return f"Sem foto: {erro}.", None
        nomes = {c["id"]: c["nome"] for c in cr.cameras()}
        return f"{nomes.get(cam, 'Câmera')} · {time.strftime('%H:%M:%S')}", cr.salvar(dadosjpg, "camera")
    if nome == "tela":
        dadosjpg, erro = cr.tela_jpeg(largura=1600, qualidade=70)
        return (f"Tela do PC · {time.strftime('%H:%M:%S')}", cr.salvar(dadosjpg, "tela")) if dadosjpg else \
            (f"Sem print: {erro}.", None)
    if nome == "cameras":
        return "Câmeras: " + ", ".join(f"{c['id'] + 1}. {c['nome']}" for c in cr.cameras()) + \
            ". Peça *foto 2* para a segunda.", None
    if nome == "status":
        try:
            from plugins._painel_remoto import resumo_status
            s = resumo_status()
            return (f"💻 CPU {s['cpu']}% · RAM {s['ram']}%" + (f" · GPU {s['gpu']}%" if s.get("gpu") is not None else "")
                    + (f" · {round(s['cpu_temp'])}°C" if s.get("cpu_temp") else "")
                    + f"\nInternet: {'ok' if s.get('internet') else 'sem'}" + (f" ({s['ping']} ms)" if s.get("ping") else "")
                    + "\nTop: " + ", ".join(f"{p['nome']} {p['cpu']}%" for p in s.get("top", [])[:3])), None
        except Exception as e:
            return f"Status indisponível: {e}", None
    if nome == "link":
        from plugins import _tunel
        end = _tunel.enderecos()
        fora = {k: v for k, v in end.items() if k != "local"}
        if not fora:
            return ("O acesso pela internet está desligado. Diga *liga o acesso remoto* (ou peça aqui mesmo) e depois "
                    "*link*."), None
        return "\n\n".join(f"🛰 {k.capitalize()} (uso único, 10 min):\n{_tunel.link_de_entrada(v)}"
                           for k, v in fora.items()) + "\n\nDepois de entrar, toque em 🛰 Central.", None
    if nome in ("confirmar", "cancelar"):
        from core import confirm
        titulo = confirm.pending_title()
        if not titulo:
            return "Não há nada esperando confirmação.", None
        if nome == "confirmar" and not config().get("confirmar_pelo_whats", True):
            return f"'{titulo}' só pode ser confirmado no PC (opção desligada).", None
        confirm.resolve(nome == "confirmar")
        return (f"✅ Confirmado: {titulo}" if nome == "confirmar" else f"❎ Cancelado: {titulo}"), None
    return "", None


def tratar(ev: dict) -> None:
    chat = str(ev.get("chat") or "")
    d = dados()
    decisao = decidir(ev, d["ids"], numeros_dono(), d["codigo"])
    if decisao == "ignorar":
        return
    if decisao == "cliente":
        rascunho_cliente(ev)
        return
    if decisao in ("ligacao", "outro"):                         # 2.3: secretária e modo pessoal
        from plugins import _whatsapp_pessoal as P
        (P.tratar_ligacao if decisao == "ligacao" else P.tratar_outro)(ev)
        return
    if decisao == "parear":
        adicionar_dono(chat)
        enviar(chat, "Pronto, este WhatsApp agora fala com o J.A.R.V.I.S. Mande *ajuda* para ver o que dá para fazer.")
        try:
            from plugins._comum import registrar
            registrar(None, "WhatsApp: novo dono autorizado.")
        except Exception:
            pass
        return
    if ev.get("numero") and chat not in d["ids"] and not ev.get("eu"):
        adicionar_dono(chat)                                   # número do dono: lembra o chat
    texto = str(ev.get("texto") or "").strip()
    if texto and not ev.get("arquivo"):
        resp_loja = comando_loja(texto)
        if resp_loja:
            enviar(chat, resp_loja)
            return
    from plugins._conversa_remota import atender                # 2.0: o mesmo atendimento do Telegram e do Discord
    atender(texto, lambda t: enviar(chat, t), lambda legenda, arq: enviar(chat, legenda, arq), "whatsapp",
            ev.get("arquivo"), str(ev.get("tipo") or ""))


# ── 1.9: modo loja — rascunhos de resposta para clientes (você aprova; nunca envia sozinho) ──
def ler_comando_loja(texto: str) -> tuple[str, int, str]:
    """'aprovar 3' / 'editar 3 novo texto' / 'ignorar 3' / 'rascunhos' → (acao, id, texto) (pura)."""
    t = str(texto or "").strip()
    m = re.match(r"(?i)^\s*(aprovar|aprova|enviar|envia|ok|ignorar|ignora|descartar)\s*#?(\d+)\s*$", t)
    if m:
        a = _dobrar(m.group(1))
        return ("aprovar" if a in ("aprovar", "aprova", "enviar", "envia", "ok") else "ignorar"), int(m.group(2)), ""
    m = re.match(r"(?is)^\s*editar?\s*#?(\d+)\s*[:\-]?\s*(.+)$", t)
    if m:
        return "editar", int(m.group(1)), m.group(2).strip()
    if _dobrar(t) in ("rascunhos", "pendentes", "clientes", "mensagens pendentes"):
        return "listar", 0, ""
    return "", 0, ""


def estoque_para_ia(limite: int = 150) -> str:
    try:
        from plugins._dados_br import chave, ler, numero
        estoque = ler("cristal_estoque.csv")
        precos = {}
        for v in ler("cristal_vendas.csv"):
            if numero(v.get("valor_unitario")):
                precos[chave(v.get("produto", ""))] = v.get("valor_unitario")
        linhas = [f"- {e.get('produto')}: {e.get('quantidade')} un."
                  + (f" (último preço R$ {precos[chave(e.get('produto', ''))]})" if chave(e.get("produto", "")) in precos else "")
                  for e in estoque[:limite]]
        return "\n".join(linhas) or "(estoque vazio)"
    except Exception:
        return "(estoque indisponível)"


def montar_prompt_cliente(nome: str, mensagem: str, estoque: str, tom: str, loja: str) -> str:
    return (f"Você ajuda o dono da loja {loja} a responder clientes no WhatsApp. Escreva UM rascunho curto de resposta, "
            f"tom {tom}, em português do Brasil, para a mensagem do cliente{(' ' + nome) if nome else ''}: \"{mensagem}\".\n"
            "Use só o estoque abaixo para dizer se tem ou não (nomes podem incluir tamanho e cor). Se não der para "
            "saber, diga que vai conferir. Não invente preço, prazo nem promoção. Sem assinatura. Responda só o texto.\n\n"
            f"ESTOQUE:\n{estoque}")


def rascunho_cliente(ev: dict, pessoal: bool = False) -> None:
    """Rascunho para você aprovar. pessoal=True (2.3): conversa sua, escrito como se fosse você."""
    texto = str(ev.get("texto") or "").strip()
    if not texto:
        return
    d = dados()
    rs = d.setdefault("rascunhos", [])
    agora = time.time()
    anterior = next((r for r in reversed(rs) if r["chat"] == ev["chat"] and r["status"] == "pendente"
                     and agora - r["ts"] < 120), None)
    pergunta = (anterior["pergunta"] + "\n" + texto) if anterior else texto
    try:
        from plugins import _ia
        if not _ia.disponivel():
            sugestao = ""
        elif pessoal:
            from plugins import _whatsapp_pessoal as P
            sugestao = _ia.perguntar(P.prompt_rascunho(P.nome_dono(), str(ev.get("nome") or ""),
                                                       P.historico_texto(ev["chat"]), pergunta), False, 40) or ""
        else:
            from plugins.cristal_malhas import _cfg as cfg_loja
            tom = str(cfg_loja().get("tom") or "carinhoso")
            sugestao = _ia.perguntar(montar_prompt_cliente(str(ev.get("nome") or ""), pergunta, estoque_para_ia(), tom,
                                                           "Cristal Malhas"), False, 40) or ""
    except Exception:
        sugestao = ""
    if anterior:
        anterior.update(pergunta=pergunta, texto=sugestao or anterior["texto"], ts=agora)
        r = anterior
    else:
        r = {"id": (max([x["id"] for x in rs], default=0) % 999) + 1, "chat": ev["chat"], "nome": ev.get("nome") or "",
             "numero": ev.get("numero") or "", "pergunta": pergunta, "texto": sugestao, "ts": agora, "status": "pendente",
             "tipo": "pessoal" if pessoal else "loja"}
        rs.append(r)
    d["rascunhos"] = rs[-50:]
    gravar_json(ARQ, d)
    quem = r["nome"] or r["numero"] or ("contato" if pessoal else "cliente")
    aviso = (f"{'💬' if pessoal else '📩'} *{quem}*: “{pergunta[-300:]}”\n\n"
             + (f"✏️ Rascunho #{r['id']}:\n{r['texto']}\n\n" if r["texto"] else "(sem rascunho — sem a chave do Gemini)\n\n")
             + f"Responda *aprovar {r['id']}*, *editar {r['id']} seu texto* ou *ignorar {r['id']}*.")
    para_donos(aviso)
    try:
        from plugins._comum import registrar
        registrar(None, f"WhatsApp{'' if pessoal else ' da loja'}: mensagem de {quem}. Rascunho #{r['id']} esperando "
                        "você aprovar.")
    except Exception:
        pass


def comando_loja(texto: str) -> str:
    acao, rid, novo = ler_comando_loja(texto)
    if not acao:
        return ""
    d = dados()
    rs = d.setdefault("rascunhos", [])
    if acao == "listar":
        pend = [r for r in rs if r["status"] == "pendente"]
        if not pend:
            return "Nenhum rascunho esperando."
        return "\n\n".join(f"#{r['id']} {r['nome'] or r['numero']}: “{r['pergunta'][-120:]}”\n→ {r['texto'][:300]}"
                             for r in pend[-10:])
    r = next((x for x in rs if x["id"] == rid and x["status"] == "pendente"), None)
    if r is None:
        return f"Não achei o rascunho #{rid} pendente."
    if acao == "ignorar":
        r["status"] = "ignorado"
        gravar_json(ARQ, d)
        return f"Rascunho #{rid} descartado."
    texto_final = novo if acao == "editar" else r["texto"]
    if not texto_final:
        return f"O rascunho #{rid} está vazio; use *editar {rid} seu texto*."
    if not enviar(r["chat"], texto_final, sem_prefixo=True):
        return "Não consegui enviar agora (o WhatsApp está conectado?)."
    r.update(status="enviado", enviado=texto_final, ts_envio=time.time())
    gravar_json(ARQ, d)
    return f"✅ Enviado para {r['nome'] or r['numero'] or 'o contato'}."
