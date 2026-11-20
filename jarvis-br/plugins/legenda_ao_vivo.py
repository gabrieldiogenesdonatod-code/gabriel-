"""
Legenda e tradução ao vivo (fork PT-BR 1.4).

Escuta o ÁUDIO DO SISTEMA (o que sai nas caixas/fone: vídeo em inglês, call,
live) e mostra a tradução no balão do rosto flutuante, em pedaços de ~5 s.

    "Jarvis, liga a legenda"        "Jarvis, traduz esse vídeo para mim"
    "Jarvis, desliga a legenda"

COMO FUNCIONA
    captura   'soundcard' (loopback do Windows, sem placa virtual):
              pip install soundcard
    ouvir     faster-whisper LOCAL, se instalado (o mesmo do motor de voz
              offline) — grátis e sem internet; senão, o modelo de IA ouve o
              áudio direto;
    traduzir  o modelo de IA (texto curto, barato). Sem chave de IA, a legenda
              aparece no idioma original (só com o faster-whisper).
    Pedaços em silêncio são pulados, e nada é capturado enquanto o próprio
    JARVIS está falando (para ele não traduzir a si mesmo).

A transcrição fica em memory/legendas/AAAA-MM-DD.txt.
"""

from __future__ import annotations

import io
import queue
import threading
import time
import wave
from datetime import datetime

from plugins._comum import MEMORIA, registrar

PLUGIN = {
    "name": "legenda_ao_vivo",
    "brief": "Live captions/translation of the PC's own audio in the floating face bubble.",
    "description": (
        "Live captions and translation of the computer's audio output (a video, a call, a stream) shown "
        "in the floating face's speech bubble. action='ligar' (optional idioma = target language, default "
        "Brazilian Portuguese) for 'turn on subtitles', 'translate this video'; 'desligar'; 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ligar | desligar | status"},
            "idioma": {"type": "STRING"},
        },
        "required": [],
    },
}

TAXA = 16000
PEDACO_S = 5.0
_estado = {"ligado": False, "idioma": "português do Brasil", "motor": "", "erro": "", "linhas": 0,
           "silencioso": False}
# 2.16: quem mais quer o texto do áudio do PC (ex.: o alerta de nome em reunião).
# Cada função recebe o texto de ~5 s; erros nelas não param a legenda.
ouvintes: list = []
_parar = threading.Event()
_fila: queue.Queue = queue.Queue(maxsize=3)
_whisper = {"modelo": None, "testado": False}


def _jarvis_falando(player) -> bool:
    try:
        return bool(player._win.hud.speaking)
    except Exception:
        return False


def _wav(amostras) -> bytes:
    import numpy as np
    pcm = (np.clip(amostras, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm)
    return buf.getvalue()


def _modelo_whisper():
    if not _whisper["testado"]:
        _whisper["testado"] = True
        try:
            from faster_whisper import WhisperModel
            _whisper["modelo"] = WhisperModel("small", device="cpu", compute_type="int8")
        except Exception as e:
            print(f"[Legenda] faster-whisper indisponível: {e}")
    return _whisper["modelo"]


def _traduzir_texto(texto: str, idioma: str) -> str:
    from plugins import _ia
    if not _ia.disponivel():
        return texto
    r = _ia.perguntar(f"Traduza para {idioma}, como legenda curta e natural. Responda SÓ a tradução:\n{texto}",
                      inteligente=False, segundos=15)
    return r or texto


def _ouvir_com_ia(wav: bytes, idioma: str) -> str:
    try:
        from google.genai import types as gtypes
        from core import gemini
        resp = gemini.call([gtypes.Part.from_bytes(data=wav, mime_type="audio/wav"),
                            f"Este é um trecho de ~5 s do áudio do computador. Escreva a fala traduzida para "
                            f"{idioma}, como legenda curta. Se não houver fala, responda exatamente: -"],
                           tier=gemini.FAST, timeout_ms=20_000)
        t = (getattr(resp, "text", "") or "").strip() if resp is not None else ""
        return "" if t in ("-", "—") else t
    except Exception as e:
        print(f"[Legenda] IA: {e}")
        return ""


def processar(amostras, idioma: str) -> str:
    """Um pedaço de áudio → texto da legenda ('' se não há fala)."""
    import numpy as np
    if float(np.sqrt(np.mean(np.square(amostras)))) < 0.004:      # silêncio
        return ""
    modelo = _modelo_whisper()
    if modelo is not None:
        segs, info = modelo.transcribe(amostras.astype("float32"), vad_filter=True, beam_size=1)
        texto = " ".join(s.text.strip() for s in segs).strip()
        if not texto:
            return ""
        _estado["motor"] = "faster-whisper" + (" + IA (tradução)" if info.language != "pt" else "")
        return texto if info.language == "pt" else _traduzir_texto(texto, idioma)
    from plugins import _ia
    if _ia.disponivel():
        _estado["motor"] = "IA (ouve e traduz)"
        return _ouvir_com_ia(_wav(amostras), idioma)
    raise RuntimeError("sem faster-whisper e sem chave de IA não há como transcrever")


def _gravar(player) -> None:
    try:
        import soundcard as sc
    except ImportError:
        _estado.update(ligado=False, erro="instale o soundcard: pip install soundcard")
        registrar(player, "Legenda: " + _estado["erro"])
        return
    try:
        alto = sc.default_speaker()
        mic = sc.get_microphone(id=str(alto.name), include_loopback=True)
        with mic.recorder(samplerate=TAXA, channels=1, blocksize=1024) as rec:
            while not _parar.is_set():
                dados = rec.record(numframes=int(TAXA * PEDACO_S))
                if _jarvis_falando(player):
                    continue
                mono = dados[:, 0] if getattr(dados, "ndim", 1) > 1 else dados
                try:
                    _fila.put_nowait(mono)
                except queue.Full:                       # atrasou: descarta o mais velho
                    try:
                        _fila.get_nowait()
                        _fila.put_nowait(mono)
                    except Exception:
                        pass
    except Exception as e:
        _estado.update(ligado=False, erro=f"captura falhou: {e}")
        registrar(player, "Legenda: " + _estado["erro"])
    finally:
        _parar.set()


def _trabalhar(player) -> None:
    from plugins import _rosto_ui
    pasta = MEMORIA / "legendas"
    pasta.mkdir(parents=True, exist_ok=True)
    primeira = True
    while not (_parar.is_set() and _fila.empty()):
        try:
            amostras = _fila.get(timeout=1)
        except queue.Empty:
            continue
        try:
            texto = processar(amostras, _estado["idioma"])
        except Exception as e:
            _estado.update(ligado=False, erro=str(e))
            registrar(player, f"Legenda: {e}")
            _parar.set()
            break
        if not texto:
            continue
        _estado["linhas"] += 1
        for ouvinte in list(ouvintes):                         # 2.16
            try:
                ouvinte(texto, player)
            except Exception as e:
                print(f"[Legenda] ouvinte: {e}")
        if _estado.get("silencioso"):                          # 2.16: só escutando, sem balão
            continue
        _rosto_ui.frase(player, "Legenda", texto, mostrar_rosto=primeira)
        primeira = False
        try:
            with open(pasta / f"{datetime.now():%Y-%m-%d}.txt", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now():%H:%M:%S}] {texto}\n")
        except OSError:
            pass
    _estado["ligado"] = False


def ligar(player, idioma: str = "", silencioso: bool = False) -> str:
    if _estado["ligado"]:
        if not silencioso:
            _estado["silencioso"] = False                      # 2.16: pediu a legenda de verdade: mostra
        return "A legenda já está ligada."
    _parar.clear()
    _estado.update(ligado=True, erro="", linhas=0, idioma=idioma or "português do Brasil", motor="",
                   silencioso=silencioso)
    threading.Thread(target=_gravar, args=(player,), daemon=True, name="legenda_captura").start()
    threading.Thread(target=_trabalhar, args=(player,), daemon=True, name="legenda_texto").start()
    time.sleep(1.2)
    if not _estado["ligado"]:
        return f"Não consegui ligar a legenda: {_estado['erro']}."
    return (f"Legenda ligada, traduzindo para {_estado['idioma']}. Ela aparece no balão do rosto, com uns "
            "5 segundos de atraso.")


def desligar() -> str:
    if not _estado["ligado"]:
        return "A legenda já está desligada."
    _parar.set()
    _estado["ligado"] = False
    return f"Legenda desligada ({_estado['linhas']} trechos)."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "ligar").lower()
    try:
        if acao == "desligar":
            return desligar()
        if acao == "status":
            if _estado["ligado"]:
                return f"Legenda ligada ({_estado['motor'] or 'iniciando'}), {_estado['linhas']} trechos até agora."
            return "Legenda desligada." + (f" Último erro: {_estado['erro']}" if _estado["erro"] else "")
        return ligar(player, str(p.get("idioma") or ""))
    except Exception as e:
        return f"A legenda falhou: {e}"
