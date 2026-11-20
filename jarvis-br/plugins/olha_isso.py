"""
"Jarvis, olha isso" (fork PT-BR 1.4).

Captura SÓ a janela ativa (VS Code, terminal, um erro no navegador — não a
tela inteira, e nunca a própria janela do JARVIS) e manda para o modelo com o
contexto: nome do programa, título da janela e, se houver, o erro copiado.

    "Jarvis, olha isso"                     → explica o que está na janela
    "Jarvis, olha isso: por que esse teste falha?"
    Atalho global: Ctrl+Alt+J (configurável) — funciona com o JARVIS minimizado.

VIGIA DE ERROS (proativo)
    Quando um Traceback do Python (ou um erro comum de npm, pip, git, Node,
    Java, C#) aparece, o rosto flutuante pergunta baixinho: "Senhor, quer que eu
    explique esse erro?". Diga "sim" ou "explica" e ele explica.
    Como ele vê o erro:
      • na área de transferência (você copiou o erro) — sempre, quase sem custo;
      • na tela do terminal/VS Code, se houver um leitor de texto instalado:
        rapidocr-onnxruntime (pip install rapidocr-onnxruntime, offline) ou
        Tesseract (pytesseract). Sem eles, só pela área de transferência.
    Um aviso por erro diferente, no máximo um a cada 2 minutos.

SEM CHAVE DE IA ele não "enxerga" a imagem, mas ainda explica Tracebacks do
Python pelas regras locais (módulo faltando, erro de sintaxe, arquivo não
encontrado, KeyError, None…).
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from pathlib import Path
import threading
import time

from plugins._comum import WIN, cfg, falar, mostrar, registrar

PLUGIN = {
    "name": "olha_isso",
    "brief": "Look at the active window (screenshot of just that window) and explain it, e.g. an error.",
    "description": (
        "'Look at this': captures ONLY the active window (not the whole screen, never JARVIS's own "
        "window) and analyses it with the vision model, with the app name, window title and any copied "
        "error as context. Use for 'olha isso', 'what is this error', 'explain what's on my screen in "
        "VS Code'. action='olhar' with pergunta (optional, the user's exact question); "
        "action='explicar_erro' when the user accepts the offer to explain the error that just appeared."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "olhar | explicar_erro"},
            "pergunta": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "olha_isso",
    "title": "Olha isso / vigia de erros",
    "fields": [
        {"key": "atalho", "label": "Atalho global (ex.: ctrl+alt+j)", "type": "text", "default": "ctrl+alt+j"},
        {"key": "vigia", "label": "Perguntar quando aparecer um erro", "type": "toggle", "default": True},
        {"key": "vigia_tela", "label": "Procurar erros na tela do terminal (precisa de OCR instalado)",
         "type": "toggle", "default": True},
    ],
}

_estado = {"erro": "", "erro_hash": "", "ultimo_aviso": 0.0, "janela": None}
_iniciado = threading.Event()

# ── erros: reconhecer e explicar sem IA ────────────────────────────────────────
_RE_ERRO = re.compile(
    r"Traceback \(most recent call last\)|^\w*(?:Error|Exception): .+|npm ERR!|error: .+|"
    r"fatal: .+|ERROR: .+|Exception in thread|at .+\(.+\.(?:java|js|ts):\d+\)|error CS\d{4}|"
    r"SyntaxError|ModuleNotFoundError|UnhandledPromiseRejection", re.M)


def parece_erro(texto: str) -> bool:
    return bool(texto) and bool(_RE_ERRO.search(texto)) and len(texto) < 60000


def resumo_erro(texto: str) -> str:
    """A linha que importa ('KeyError: x' / 'npm ERR! ...')."""
    linhas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    for l in reversed(linhas):
        if re.match(r"^[\w.]*(?:Error|Exception|Warning)\b", l) or l.startswith(("npm ERR!", "fatal:", "error")):
            return l[:200]
    return (linhas[-1] if linhas else "")[:200]


_EXPLICACOES = [
    (r"ModuleNotFoundError: No module named '([\w.]+)'", lambda m: _modulo_faltando(m.group(1))),
    (r"ImportError: cannot import name '(\w+)' from '([\w.]+)'",
     lambda m: f"'{m.group(1)}' não existe em {m.group(2)}: nome errado, versão diferente da biblioteca ou import circular."),
    (r"IndentationError: (.+)", lambda m: f"Indentação errada ({m.group(1)}). Misturou tab com espaço ou "
                                          "faltou/sobrou recuo na linha indicada."),
    (r"SyntaxError: (.+)", lambda m: f"Erro de sintaxe: {m.group(1)}. Olhe a linha indicada e a anterior "
                                     "(parêntese, aspas ou dois-pontos faltando)."),
    (r"FileNotFoundError: .*?'(.+?)'", lambda m: f"O arquivo '{m.group(1)}' não existe nesse caminho. Confira o "
                                                 "nome e a pasta de onde o programa está rodando."),
    (r"PermissionError: .*?'(.+?)'", lambda m: f"Sem permissão para '{m.group(1)}': o arquivo está aberto em outro "
                                               "programa ou precisa de administrador."),
    (r"KeyError: (.+)", lambda m: f"A chave {m.group(1)} não existe no dicionário. Use .get() ou confira a origem dos dados."),
    (r"IndexError: (.+)", lambda m: f"Índice fora da lista ({m.group(1)}): a lista tem menos itens do que o código supõe."),
    (r"AttributeError: 'NoneType' object has no attribute '(\w+)'",
     lambda m: f"Uma variável estava None quando o código tentou usar .{m.group(1)}: alguma função não devolveu nada "
               "ou uma busca não achou resultado."),
    (r"AttributeError: (.+)", lambda m: f"Atributo inexistente: {m.group(1)}. Nome errado ou objeto de outro tipo."),
    (r"TypeError: (.+)", lambda m: f"Tipo errado: {m.group(1)}. Confira os argumentos passados na linha indicada."),
    (r"ValueError: (.+)", lambda m: f"Valor inválido: {m.group(1)}."),
    (r"ZeroDivisionError", lambda m: "Divisão por zero: proteja o cálculo quando o divisor puder ser 0."),
    (r"RecursionError", lambda m: "Recursão infinita: a função chama a si mesma sem condição de parada."),
    (r"(?:ConnectionError|ConnectTimeout|ReadTimeout|Max retries exceeded)",
     lambda m: "Falha de rede: o servidor não respondeu. Confira a internet, o endereço e se o serviço está no ar."),
    (r"UnicodeDecodeError", lambda m: "Erro de codificação: abra o arquivo com encoding='utf-8' (ou o correto)."),
    (r"npm ERR! code (\w+)", lambda m: f"O npm falhou com {m.group(1)}. Rode 'npm install' de novo e confira a versão do Node."),
    (r"fatal: not a git repository", lambda m: "Você não está dentro de uma pasta com git. Entre na pasta do projeto ou rode git init."),
    (r"fatal: (.+)", lambda m: f"O git recusou: {m.group(1)}."),
]


_PIP = {"cv2": "opencv-python", "PIL": "pillow", "yaml": "pyyaml", "sklearn": "scikit-learn",
        "bs4": "beautifulsoup4", "dotenv": "python-dotenv", "win32api": "pywin32", "win32con": "pywin32",
        "docx": "python-docx", "fitz": "pymupdf", "serial": "pyserial", "Crypto": "pycryptodome",
        "google": "google-genai", "skimage": "scikit-image", "pptx": "python-pptx", "telegram": "python-telegram-bot"}
_ultimo_tb = {"texto": ""}


def _modulo_faltando(mod: str) -> str:
    topo = mod.split(".")[0]
    arquivos = re.findall(r'File "([^"]+)", line \d+', _ultimo_tb["texto"])
    for arq in reversed(arquivos):                       # é uma pasta do próprio projeto?
        pasta = Path(re.sub(r"[\\/][^\\/]+$", "", arq))
        for raiz in ((pasta, pasta.parent) if pasta.is_absolute() else ()):
            if (raiz / topo).is_dir():
                if not (raiz / topo / "__init__.py").exists():
                    return (f"'{topo}' é uma pasta do seu projeto, mas falta o arquivo __init__.py dentro dela, "
                            "ou o programa foi aberto de outra pasta. Rode de dentro da pasta do projeto.")
                return (f"'{topo}' é uma pasta do seu projeto: rode o programa de dentro da pasta do projeto "
                        f"(cd até ela) para o Python achar o módulo.")
        if arquivos and not any(x in arq.lower() for x in ("site-packages", "python3", "lib\\")):
            if not (pasta / topo).exists() and topo.islower() and topo in ("memory", "core", "plugins", "config", "actions"):
                return (f"A pasta '{topo}' não existe no projeto em {pasta}: o projeto está incompleto. Use o ZIP "
                        "completo e extraia tudo na mesma pasta.")
    pacote = _PIP.get(topo, topo)
    return (f"Falta instalar o módulo '{mod}'. Rode: pip install {pacote} — no MESMO Python que roda o programa "
            f"(py -m pip install {pacote}).")


def explicar_local(texto: str) -> str:
    _ultimo_tb["texto"] = texto
    linha = resumo_erro(texto)
    onde = re.findall(r'File "([^"]+)", line (\d+)', texto)
    # Fork PT-BR 2.8: a barra invertida dentro da f-string era erro de sintaxe no Python 3.11
    # (o mínimo do setup.py) — o plugin nem carregava nele.
    arquivo = re.split(r"[\\/]", onde[-1][0])[-1] if onde else ""
    local = f" Aconteceu em {arquivo}, linha {onde[-1][1]}." if onde else ""
    for rx, fazer in _EXPLICACOES:
        m = re.search(rx, texto)
        if m:
            return fazer(m) + local
    return f"O erro foi: {linha}.{local}" if linha else "Não reconheci o erro."


# ── janela ativa ───────────────────────────────────────────────────────────────
def janela_alvo() -> dict | None:
    """A janela em foco; se for o próprio JARVIS, a próxima janela visível abaixo dela."""
    if not WIN:
        try:
            from plugins._janelas import ativa
            return ativa()
        except Exception:
            return None
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    meu = os.getpid()
    h = u32.GetForegroundWindow()
    for _ in range(60):
        if not h:
            return None
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        n = u32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        if pid.value != meu and u32.IsWindowVisible(h) and not u32.IsIconic(h) and buf.value.strip():
            r = wintypes.RECT()
            # DWMWA_EXTENDED_FRAME_BOUNDS (9): sem as bordas invisíveis do Windows 10/11
            if ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
                u32.GetWindowRect(h, ctypes.byref(r))
            try:
                import psutil
                proc = psutil.Process(pid.value).name()
            except Exception:
                proc = "?"
            return {"hwnd": int(h), "titulo": buf.value, "processo": proc,
                    "ret": (r.left, r.top, r.right, r.bottom)}
        h = u32.GetWindow(h, 2)                 # GW_HWNDNEXT: a de baixo na ordem Z
    return None


def capturar(j: dict, largura_max: int = 1600) -> tuple[bytes, str] | None:
    """JPEG só da janela. None se não der."""
    try:
        import mss
    except ImportError:
        return None
    x1, y1, x2, y2 = j.get("ret") or (0, 0, 0, 0)
    if x2 - x1 < 50 or y2 - y1 < 50:
        return None
    with mss.mss() as sct:
        img = sct.grab({"left": int(x1), "top": int(y1), "width": int(x2 - x1), "height": int(y2 - y1)})
        try:
            from PIL import Image
            im = Image.frombytes("RGB", img.size, img.rgb)
            if im.width > largura_max:
                im = im.resize((largura_max, int(im.height * largura_max / im.width)))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            return buf.getvalue(), "image/jpeg"
        except ImportError:
            import mss.tools
            return mss.tools.to_png(img.rgb, img.size), "image/png"


def _clipboard() -> str:
    try:
        from plugins.controle_sistema import clipboard_ler
        return clipboard_ler() or ""
    except Exception:
        return ""


def olhar(pergunta: str = "", player=None, erro: str = "") -> tuple[str, str]:
    """(resposta completa, frase curta para falar)."""
    from plugins import _ia
    j = janela_alvo()
    copiado = erro or _clipboard()
    copiado = copiado if parece_erro(copiado) else ""
    contexto = f"Programa: {j['processo']} — janela: \"{j['titulo']}\"" if j else "janela desconhecida"
    if _ia.disponivel() and j:
        imagem = capturar(j)
        if imagem:
            try:
                from google.genai import types as gtypes
                from core import gemini
                prompt = ("Você é o J.A.R.V.I.S, assistente de um programador brasileiro. O usuário disse \"olha "
                          f"isso\" sobre a janela abaixo. {contexto}.\n"
                          + (f"Pergunta dele: {pergunta}\n" if pergunta else "")
                          + (f"Texto de erro copiado:\n{copiado[-3000:]}\n" if copiado else "")
                          + "Se houver erro/Traceback: diga a causa provável e a correção exata (arquivo, linha, "
                          "o que mudar). Senão, explique o que está na tela e o que é útil fazer. Português do "
                          "Brasil, direto, no máximo 10 linhas. Primeira frase = resumo falável.")
                resp = gemini.call([gtypes.Part.from_bytes(data=imagem[0], mime_type=imagem[1]), prompt],
                                   tier=gemini.SMART, timeout_ms=60_000)
                texto = (getattr(resp, "text", "") or "").strip() if resp is not None else ""
                if texto:
                    curta = re.split(r"(?<=[.!?])\s", texto, maxsplit=1)[0]
                    return texto, curta
            except Exception as e:
                print(f"[OlhaIsso] visão: {e}")
    if copiado:
        exp = explicar_local(copiado)
        return f"{contexto}\n\nErro: {resumo_erro(copiado)}\n\n{exp}", exp
    if not j:
        return "Não achei a janela ativa.", "Não achei a janela ativa."
    return (f"{contexto}\n\nSem a chave de IA eu não consigo enxergar a imagem. Copie o texto do erro "
            "(Ctrl+C) e diga 'olha isso' de novo.",
            "Sem IA eu não enxergo a janela; copie o texto do erro e peça de novo.")


# ── vigia: área de transferência e tela ────────────────────────────────────────
def _seq_clipboard() -> int:
    if WIN:
        import ctypes
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    return 0


_ocr = {"motor": None, "testado": False}


def ocr_disponivel() -> bool:
    _ler_tela(b"")
    return bool(_ocr["motor"])


def _ler_tela(imagem: bytes, inicio: float = 0.55) -> str:
    """OCR local opcional (rapidocr ou tesseract). Por padrão lê só a parte de
    BAIXO da janela (onde a saída nova do terminal aparece); inicio=0 lê tudo.
    '' quando não há OCR."""
    if not _ocr["testado"]:
        _ocr["testado"] = True
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr["motor"] = ("rapid", RapidOCR())
        except Exception:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                _ocr["motor"] = ("tess", pytesseract)
            except Exception:
                _ocr["motor"] = None
    if not _ocr["motor"] or not imagem:
        return ""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(imagem))
        if inicio > 0:
            im = im.crop((0, int(im.height * inicio), im.width, im.height))
        tipo, motor = _ocr["motor"]
        if tipo == "rapid":
            import numpy as np
            res, _ = motor(np.array(im))
            return "\n".join(r[1] for r in (res or []))
        return motor.image_to_string(im)
    except Exception as e:
        print(f"[OlhaIsso] OCR: {e}")
        return ""


_TERMINAIS = re.compile(r"windowsterminal|cmd\.exe|powershell|pwsh|code|pycharm|idea64|conhost|wezterm|alacritty", re.I)


def _avisar_erro(player, texto: str, origem: str) -> None:
    linha = resumo_erro(texto)
    h = hashlib.sha1(linha.encode()).hexdigest()[:10]
    if h == _estado["erro_hash"] or time.time() - _estado["ultimo_aviso"] < 120:
        return
    _estado.update(erro=texto[-6000:], erro_hash=h, ultimo_aviso=time.time())
    registrar(player, f"Erro detectado ({origem}): {linha}")
    try:
        from plugins import _rosto_ui
        _rosto_ui.frase(player, "JARVIS", "Senhor, quer que eu explique esse erro?")
    except Exception:
        pass
    falar(player, "[OLHA ISSO] Apareceu um erro na tela do usuário (" + linha[:120] + "). Pergunte, em voz baixa "
                  "e em UMA frase curta no idioma da conversa, se ele quer que você explique esse erro. Se ele "
                  "aceitar, chame a ferramenta olha_isso com action='explicar_erro'. Não chame nada agora.")


def _laco(player) -> None:
    ultima_seq, ultimo_hash_tela, ultima_tela = _seq_clipboard(), "", 0.0
    c, lido = {}, 0.0
    while True:
        time.sleep(2)
        try:
            if time.time() - lido > 30:                 # lê a configuração a cada 30 s, não a cada volta
                c, lido = cfg("olha_isso", PLUGIN_SETTINGS), time.time()
            if str(c.get("vigia", True)).lower() in ("false", "0", "nao", "não"):
                continue
            seq = _seq_clipboard()
            if seq != ultima_seq:
                ultima_seq = seq
                texto = _clipboard()
                if parece_erro(texto):
                    _avisar_erro(player, texto, "área de transferência")
            if (str(c.get("vigia_tela", True)).lower() not in ("false", "0", "nao", "não")
                    and time.time() - ultima_tela >= 15 and ocr_disponivel()):
                ultima_tela = time.time()
                j = janela_alvo()
                if j and _TERMINAIS.search(j.get("processo", "")):
                    img = capturar(j, 1400)
                    if img:
                        h = hashlib.sha1(img[0][::97]).hexdigest()
                        if h != ultimo_hash_tela:
                            ultimo_hash_tela = h
                            texto = _ler_tela(img[0])
                            if "Traceback (most recent call last)" in texto or re.search(r"^\w+Error: ", texto, re.M):
                                _avisar_erro(player, texto, "tela")
        except Exception as e:
            print(f"[OlhaIsso] vigia: {e}")


# ── atalho global (RegisterHotKey, sem pacotes extras) ─────────────────────────
_MODS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}


def _parse_atalho(txt: str) -> tuple[int, int] | None:
    partes = [p.strip().lower() for p in (txt or "").split("+") if p.strip()]
    if not partes:
        return None
    mods = 0x4000                                   # MOD_NOREPEAT
    for p in partes[:-1]:
        if p not in _MODS:
            return None
        mods |= _MODS[p]
    tecla = partes[-1]
    if len(tecla) == 1 and tecla.isalnum():
        vk = ord(tecla.upper())
    elif re.fullmatch(r"f([1-9]|1[0-2])", tecla):
        vk = 0x6F + int(tecla[1:])
    else:
        return None
    return mods, vk


def _atalho(player) -> None:
    if not WIN:
        return
    import ctypes
    from ctypes import wintypes
    par = _parse_atalho(str(cfg("olha_isso", PLUGIN_SETTINGS).get("atalho") or "ctrl+alt+j"))
    if not par:
        return
    u32 = ctypes.windll.user32
    if not u32.RegisterHotKey(None, 0xB0A, par[0], par[1]):
        registrar(player, "O atalho do 'olha isso' já está em uso por outro programa; mude em Configurações.")
        return
    msg = wintypes.MSG()
    while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312:                   # WM_HOTKEY
            threading.Thread(target=_pelo_atalho, args=(player,), daemon=True).start()


def _pelo_atalho(player) -> None:
    completo, curta = olhar("", player)
    mostrar(player, "OLHA ISSO", completo)
    falar(player, f"[OLHA ISSO] O usuário apertou o atalho para você olhar a janela dele. Diga, em até 2 frases "
                  f"e no idioma da conversa, o essencial desta análise: {completo[:900]} Não chame ferramentas.")


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="olha_isso_vigia").start()
        threading.Thread(target=_atalho, args=(player,), daemon=True, name="olha_isso_atalho").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "olhar").lower()
    try:
        if acao == "explicar_erro":
            if not _estado["erro"]:
                acao = "olhar"
            else:
                completo, curta = olhar(p.get("pergunta") or "Explique este erro e como corrigir.", player,
                                        erro=_estado["erro"])
                mostrar(player, "ERRO EXPLICADO", completo)
                return completo[:900]
        completo, curta = olhar(str(p.get("pergunta") or ""), player)
        mostrar(player, "OLHA ISSO", completo)
        return completo[:900]
    except Exception as e:
        return f"Não consegui olhar a janela: {e}"
