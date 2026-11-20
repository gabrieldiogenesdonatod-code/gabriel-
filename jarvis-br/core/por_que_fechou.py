"""
"Por que o JARVIS fechou?" — em português, sem precisar entender o log (fork PT-BR 2.8.1).

Junta três pistas da ÚLTIMA vez que o JARVIS rodou:
  1. memory/erros.log — o motivo anotado na saída (pedido de fechar, janela
     fechada), a pilha do faulthandler numa queda nativa, e a linha do tempo
     ("· evento: …": conectou, a sessão caiu, reconectando, dormiu…);
  2. memory/ultimo_sinal.json — o "sinal de vida" de 15 em 15 s: a que horas ele
     ainda estava vivo, a RAM do PC, a última ferramenta;
  3. o registro de erros do Windows (Visualizador de Eventos → Aplicativo):
     "Application Error" (1000) diz QUAL arquivo (.dll) derrubou o python.exe e o
     código do erro, mesmo quando o Python não consegue escrever nada;
     "Application Hang" (1002) quer dizer que ele travou e foi fechado; o
     "Resource-Exhaustion-Detector" (Sistema) diz que faltou memória.

Usado por: core/protecao_falhas.py (na abertura), iniciar.bat
(`python -m core.por_que_fechou`, logo depois de fechar) e o plugin
plugins/por_que_fechou.py ("Jarvis, por que você fechou?").
As regras de explicação são puras e testadas em tests/test_34_quedas.py.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG = BASE / "memory" / "erros.log"
SINAL = BASE / "memory" / "ultimo_sinal.json"
MARCA = "· JARVIS iniciado ==="
_SAIDA = re.compile(r"· JARVIS fechado: (.+?) ===")
_INICIO = re.compile(r"=== (\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) · JARVIS iniciado ===\n(.*)")
_PID = re.compile(r"\bpid (\d+)")
_EVENTO = re.compile(r"^(\d{2}:\d{2}:\d{2}) · evento: (.+)$", re.M)

# ── o que cada pedaço do Windows é, em português ──────────────────────────────
MODULOS = [
    (("portaudio", "_sounddevice", "wdmaud", "audioses", "mmdevapi", "audiokse", "audioeng", "dsound"),
     "o som (a placa de som ou o driver de áudio)",
     "Atualize o driver de áudio; se usa fone Bluetooth, teste com a caixa de som do PC. Troque a saída/entrada em ⚙."),
    (("ig9icd", "ig7icd", "igxelp", "igd10", "igdumd", "igc64", "intelocl"),
     "o driver de vídeo da Intel",
     "Atualize o driver de vídeo da Intel (Windows Update → Atualizações opcionais, ou o site da Intel)."),
    (("nvoglv", "nvwgf2", "nvd3dum", "nvcuda"), "o driver de vídeo da NVIDIA", "Atualize o driver da NVIDIA."),
    (("atio6", "atiumd", "amdxx", "aticfx"), "o driver de vídeo da AMD", "Atualize o driver da AMD."),
    (("qt6multimedia", "avcodec", "avformat", "avutil", "swresample", "ffmpegmediaplugin"),
     "o player de vídeo da janela (Qt Multimedia)", "Evite abrir vídeos na tela do JARVIS até atualizar o PyQt6."),
    (("qt6core", "qt6gui", "qt6widgets", "qt6opengl", "qwindows", "pyqt6", "qt6svg"),
     "a janela do JARVIS (Qt)",
     "Rode: python -m pip install --upgrade PyQt6 . Se continuar, me mande o memory\\erros.log."),
    (("opencv", "cv2", "mfplat", "mfreadwrite", "ksproxy"), "a câmera (OpenCV)",
     "Feche outros apps que usam a câmera; se continuar, desligue a visão pela câmera."),
    (("onnxruntime",), "o reconhecimento local (onnxruntime: 'Hey Jarvis', rosto ou leitor de tela)",
     "Rode: python -m pip install --upgrade onnxruntime . Ou desligue a ativação por voz."),
    (("ctranslate2", "faster_whisper"), "o reconhecimento de fala local (faster-whisper)",
     "Rode: python -m pip install --upgrade faster-whisper ctranslate2 , ou desligue 'Jarvis, acorda' em ⚙."),
    (("mediapipe", "tensorflow", "tflite"), "o reconhecimento de mãos/gestos (mediapipe)", "Desligue os gestos."),
    (("torch", "c10", "libiomp", "mkl_"), "o PyTorch (voz do dono / modelos locais)", "Desligue a voz do dono."),
    (("python3", "python.exe", "pythonw.exe"), "o próprio Python (quase sempre falta de memória ou uma extensão)",
     "Feche programas pesados; se puder, use o Python 3.12 ou 3.13 (o 3.14 é novo para várias bibliotecas)."),
    (("ucrtbase", "msvcp140", "vcruntime140", "msvcrt"), "uma biblioteca que pediu para encerrar (abort)",
     "Instale o 'Microsoft Visual C++ Redistributable' mais novo (x64)."),
    (("ntdll", "kernelbase", "kernel32"), "o Windows, a pedido de alguma biblioteca", ""),
]
CODIGOS = {
    "c0000005": "acesso inválido à memória",
    "c0000409": "encerramento forçado por uma biblioteca (abort/fail-fast)",
    "c00000fd": "estouro de pilha",
    "c0000374": "memória corrompida",
    "c0000017": "falta de memória", "c000012d": "falta de memória (arquivo de paginação cheio)",
    "e06d7363": "erro C++ não tratado numa biblioteca",
    "80000003": "parada de emergência de uma biblioteca (assert)",
    "c0000142": "falha ao carregar uma DLL",
    "c0000135": "uma DLL que falta no PC",
}
PILHA = [
    (("comtypes", "pycaw"), "o COM do Windows (volume/medidor de som, pycaw)"),
    (("sounddevice", "_fechar_placa", "_play_audio", "_listen_audio", "_som.py", "_dupla.py", "tts.py"),
     "o som"),
    (("pyqt6", "ui.py", "avatar", "rosto", "qt_bridge"), "a janela"),
    (("cv2", "camera", "screen_processor", "visao"), "a câmera/tela"),
    (("openwakeword", "onnxruntime", "wake_word"), "o 'Hey Jarvis'"),
    (("faster_whisper", "ctranslate2", "stt"), "o reconhecimento de fala local"),
    (("mediapipe",), "os gestos"),
    (("google", "genai", "websockets"), "a conexão com o Gemini"),
]


def _norm(t: str) -> str:
    return str(t or "").lower()


def explicar_modulo(modulo: str) -> tuple[str, str]:
    m = _norm(modulo)
    for chaves, nome, dica in MODULOS:
        if any(c in m for c in chaves):
            return nome, dica
    return (f"o arquivo {modulo}" if modulo else "um arquivo desconhecido"), ""


def codigo(c: str) -> str:
    c = _norm(c).replace("0x", "").strip()
    return c.zfill(8) if c else ""


def explicar_codigo(c: str) -> str:
    c = codigo(c)
    return CODIGOS.get(c, f"erro 0x{c}" if c else "erro")


# ── a última execução, no erros.log (pura) ────────────────────────────────────
def ultima_execucao(txt: str, pular_atual: bool = False) -> dict:
    """O pedaço do erros.log da última execução (pura). pular_atual=True ignora a que está rodando agora."""
    marcas = list(_INICIO.finditer(txt or ""))
    if pular_atual and marcas:
        marcas = marcas[:-1]
    if not marcas:
        return {}
    m = marcas[-1]
    prox = _INICIO.search(txt, m.end())
    corpo = txt[m.start():prox.start() if prox else len(txt)]
    try:
        inicio = datetime.strptime(m.group(1), "%d/%m/%Y %H:%M:%S").timestamp()
    except ValueError:
        inicio = 0.0
    pid = _PID.search(m.group(2))
    saida = _SAIDA.search(corpo)
    queda = ""
    for marca in ("Windows fatal exception", "Fatal Python error"):
        i = corpo.find(marca)
        if i >= 0:
            queda = corpo[i:i + 60000]                  # 2.8.3: a thread que caiu vem depois das outras
            break
    ver = re.search(r"versão (\S+)", m.group(2))
    return {"inicio": inicio, "pid": int(pid.group(1)) if pid else 0,
            "saida": saida.group(1).strip() if saida else "", "queda": queda,
            "eventos": [f"{h} {e}" for h, e in _EVENTO.findall(corpo)][-8:], "versao": ver.group(1) if ver else ""}


def onde_caiu(queda: str) -> str:
    """Da pilha do faulthandler: em que parte do JARVIS a queda aconteceu (pura)."""
    if not queda:
        return ""
    i = queda.find("Current thread")
    trecho = queda[i:i + 1500] if i >= 0 else queda[:1500]
    frames = re.findall(r'File "([^"]+)", line (\d+) in (\S+)', trecho)
    if not frames:
        return ""
    texto = " ".join(f"{a} {fn}" for a, _l, fn in frames[:6]).lower()
    parte = next((nome for chaves, nome in PILHA if any(c in texto for c in chaves)), "")
    a, linha, fn = frames[0]
    arquivo = re.split(r"[\\/]", a)[-1]
    lixo = " (soltando um objeto velho na coleta de lixo)" if "Garbage-collecting" in trecho[:400] else ""
    return (f"{parte} — " if parte else "") + f"{arquivo}, linha {linha}, em {fn}(){lixo}"


# ── o registro de erros do Windows ────────────────────────────────────────────
_PS = r"""
$ini = (Get-Date).AddMinutes(-{min});
$saida = @();
try {{ $ev = Get-WinEvent -FilterHashtable @{{LogName='Application'; Id=1000,1002; StartTime=$ini}} -MaxEvents 40 -ErrorAction Stop }} catch {{ $ev = @() }}
foreach ($e in $ev) {{ $saida += [pscustomobject]@{{ t=$e.TimeCreated.ToUniversalTime().ToString('o'); id=$e.Id; p=@($e.Properties | ForEach-Object {{ [string]$_.Value }}) }} }}
try {{ $m = Get-WinEvent -FilterHashtable @{{LogName='System'; ProviderName='Microsoft-Windows-Resource-Exhaustion-Detector'; StartTime=$ini}} -MaxEvents 5 -ErrorAction Stop }} catch {{ $m = @() }}
foreach ($e in $m) {{ $saida += [pscustomobject]@{{ t=$e.TimeCreated.ToUniversalTime().ToString('o'); id=$e.Id; p=@([string]$e.Message) }} }}
ConvertTo-Json -InputObject @($saida) -Depth 4 -Compress
"""


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except ValueError:
        return 0.0


def eventos_windows(minutos: int = 24 * 60) -> list[dict]:
    """Os erros de programas e de falta de memória do Windows nesse período. [] fora do Windows."""
    if platform.system() != "Windows":
        return []
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS.format(min=int(minutos))],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        dados = json.loads(r.stdout or "[]")
    except Exception:
        return []
    saida = []
    for e in dados if isinstance(dados, list) else [dados]:
        p = [str(x) for x in (e.get("p") or [])]
        ev = {"ts": _ts(str(e.get("t") or "")), "id": int(e.get("id") or 0)}
        if ev["id"] == 1000 and len(p) >= 9:
            ev.update(app=p[0], modulo=p[3], codigo=codigo(p[6]), pid=_hex(p[8]), caminho=p[10] if len(p) > 10 else "")
        elif ev["id"] == 1002 and len(p) >= 3:
            ev.update(app=p[0], pid=_hex(p[2]), caminho=p[5] if len(p) > 5 else "")
        elif ev["id"] == 2004:
            ev.update(app="memoria", texto=p[0][:600] if p else "")
        else:
            continue
        saida.append(ev)
    return saida


def _hex(v: str) -> int:
    try:
        return int(str(v), 16) if str(v).lower().startswith("0x") else int(v)
    except ValueError:
        return 0


def do_jarvis(eventos: list[dict], ultima: dict, sinal: dict) -> list[dict]:
    """Os eventos do Windows que são desta execução do JARVIS (pelo pid, ou python.exe na hora) (pura)."""
    pid = int(ultima.get("pid") or sinal.get("pid") or 0)
    inicio = float(ultima.get("inicio") or 0)
    fim = float(sinal.get("ts") or 0) + 300 if sinal.get("ts") else time.time() + 60
    meus = []
    for e in eventos:
        if e.get("app") == "memoria":
            if inicio - 60 <= e["ts"] <= fim:
                meus.append(e)
            continue
        if not re.match(r"pythonw?(\d|\.|$)", _norm(e.get("app"))):
            continue
        if (pid and e.get("pid") == pid) or (not pid and inicio - 5 <= e["ts"] <= fim):
            meus.append(e)
    return meus


# ── a explicação ──────────────────────────────────────────────────────────────
def explicar(ultima: dict, eventos: list[dict], sinal: dict) -> str:
    """Pura: o texto 'por que fechou' para a pessoa (e uma dica)."""
    if not ultima:
        return "Ainda não tenho registro de nenhuma vez em que o JARVIS fechou."
    saida = ultima.get("saida") or ""
    if saida and not ultima.get("queda"):
        return f"Da última vez o JARVIS fechou normalmente: {saida}."
    partes, dica = [], ""
    hang = [e for e in eventos if e.get("id") == 1002]
    crash = [e for e in eventos if e.get("id") == 1000]
    falta = [e for e in eventos if e.get("id") == 2004]
    if crash:
        e = crash[-1]
        nome, dica = explicar_modulo(e.get("modulo", ""))
        partes.append(f"o Windows registrou que o JARVIS caiu por causa de {nome} "
                      f"({e.get('modulo') or '?'}, {explicar_codigo(e.get('codigo', ''))})")
    elif hang:
        partes.append("o JARVIS travou (parou de responder) e foi fechado — pelo Windows ou pelo botão "
                      "'Fechar o programa'")
        dica = "Se acontecer de novo, espere uns 30 s antes de fechar e me mande o memory\\erros.log."
    if ultima.get("queda"):
        onde = onde_caiu(ultima["queda"])
        if not crash:
            tipo = ultima["queda"].split("\n", 1)[0].strip()
            partes.append("caiu numa queda do Windows/driver" + (f" ({tipo})" if tipo else ""))
        if onde:
            partes.append(f"na hora ele estava em: {onde}")
    if falta or (sinal.get("ram_pc") or 0) >= 95:
        partes.append("o PC estava SEM MEMÓRIA" + (f" (RAM em {sinal['ram_pc']:.0f}%)" if sinal.get("ram_pc") else ""))
        dica = dica or "Feche abas do navegador e programas pesados; com 8 GB de RAM, o JARVIS precisa de espaço."
    if not partes:
        partes.append("ninguém anotou o motivo: o processo foi encerrado de fora (Gerenciador de Tarefas, "
                      "antivírus, a janela preta fechada, o Windows desligando) ou caiu sem o Windows registrar")
        dica = "Abra sempre pelo iniciar.bat e não feche a janela preta; se fechar sozinho, me mande o erros.log."
    texto = "Da última vez: " + "; ".join(partes) + "."
    if sinal.get("ts"):
        vivo = datetime.fromtimestamp(float(sinal["ts"])).strftime("%H:%M:%S")
        extra = []
        if sinal.get("ram_pc"):
            extra.append(f"RAM do PC {sinal['ram_pc']:.0f}%")
        if sinal.get("ram_jarvis_mb"):
            extra.append(f"JARVIS usando {sinal['ram_jarvis_mb']:.0f} MB")
        if sinal.get("atividade"):
            extra.append(str(sinal["atividade"])[:80])
        texto += f" Último sinal de vida às {vivo}" + (f" ({'; '.join(extra)})" if extra else "") + "."
    if ultima.get("eventos"):
        texto += " Antes disso: " + " → ".join(ultima["eventos"][-3:]) + "."
    if dica:
        texto += f" O que fazer: {dica}"
    return texto


def ler_sinal() -> dict:
    try:
        d = json.loads(SINAL.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def diagnosticar(txt: str | None = None, pular_atual: bool = False, esperar_s: float = 0.0) -> str:
    """A explicação da última vez que o JARVIS fechou (lê os arquivos e o registro do Windows)."""
    if txt is None:
        try:
            txt = LOG.read_text(encoding="utf-8", errors="replace")[-200000:]
        except OSError:
            txt = ""
    ultima = ultima_execucao(txt, pular_atual=pular_atual)
    sinal = ler_sinal()
    if sinal.get("pid") and ultima.get("pid") and sinal["pid"] != ultima["pid"]:
        sinal = {}                                           # o sinal é de outra execução
    eventos = []
    precisa = not (ultima.get("saida") and not ultima.get("queda"))
    if ultima and precisa:
        fim = time.time() + esperar_s                        # o Windows leva uns segundos para anotar a queda
        while True:
            eventos = do_jarvis(eventos_windows(), ultima, sinal)
            if eventos or time.time() >= fim:
                break
            time.sleep(1.5)
    return explicar(ultima, eventos, sinal)


def historico(txt: str, n: int = 10) -> list[str]:
    """Pura: as últimas n execuções e como cada uma terminou."""
    linhas = []
    for m in re.finditer(r"=== (\d{2}/\d{2}/\d{4} \d{2}:\d{2}):\d{2} · JARVIS iniciado ===", txt):
        resto = txt[m.end():]
        prox = resto.find(MARCA)
        corpo = resto[:prox] if prox >= 0 else resto
        s = _SAIDA.search(corpo)
        if "Windows fatal exception" in corpo or "Fatal Python error" in corpo:
            como = "caiu (queda do Windows/driver)"
        elif s:
            como = s.group(1).strip()
        else:
            como = "sem registro (encerrado de fora)" if prox >= 0 else "rodando agora (ou sem registro)"
        linhas.append(f"{m.group(1)} → {como}")
    return linhas[-n:]


if __name__ == "__main__":                                   # iniciar.bat, logo depois de o JARVIS fechar
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(diagnosticar(esperar_s=6.0))
