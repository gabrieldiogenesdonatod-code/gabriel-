"""
Ata de chamadas (fork PT-BR 1.6).

Durante uma chamada no Discord, Meet, Zoom, Teams ou WhatsApp do PC, o JARVIS
grava o que SAI do PC (as outras pessoas) e o seu microfone, separados. No
fim, transcreve e entrega a ata: resumo, decisões e tarefas combinadas (quem
faz o quê e até quando).

    "Jarvis, grava a ata da reunião"      ...      "Jarvis, termina a ata"
    "Jarvis, mostra a última ata"

Ele não "entra" na chamada como um robô: grava o áudio do seu PC. Avise os
participantes que a conversa está sendo gravada. Dica: mute o JARVIS (F4)
durante a chamada para ele não responder — a gravação continua.

Precisa do soundcard (pip install soundcard) para ouvir o PC. A transcrição
usa o faster-whisper (no PC) ou a chave do Gemini. Tudo fica em
Documentos\\JARVIS\\atas.
"""

from __future__ import annotations

import threading
import time
import wave
from datetime import datetime
from pathlib import Path

from plugins._comum import abrir_no_sistema, mostrar, pasta_usuario

PLUGIN = {
    "name": "ata_chamada",
    "brief": "Meeting minutes: records call audio (PC output + mic), transcribes and lists decisions and tasks.",
    "description": (
        "Call minutes for Discord/Meet/Zoom/Teams calls on the PC: action='iniciar' (records what the PC plays and the "
        "user's mic, separately; remind the user to tell participants it is being recorded), 'parar' (stops, "
        "transcribes and writes the minutes: summary, decisions, tasks with owner and deadline), 'status', 'ultima'."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING", "description": "iniciar | parar | status | ultima"}},
                   "required": []},
}

TAXA = 16000
PEDACO_S = 300                               # transcreve em pedaços de 5 min
_estado = {"gravando": False, "pasta": None, "inicio": 0.0, "erro": "", "ultima": None, "tipo": "ata"}
_parar = threading.Event()
_arquivos: dict = {}


def _abrir_wav(caminho: Path):
    w = wave.open(str(caminho), "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(TAXA)
    return w


def _gravar_pc() -> None:
    import numpy as np
    try:
        import soundcard as sc
        alto = sc.default_speaker()
        mic = sc.get_microphone(id=str(alto.name), include_loopback=True)
        with mic.recorder(samplerate=TAXA, channels=1, blocksize=1024) as rec:
            while not _parar.is_set():
                dados = rec.record(numframes=TAXA)
                mono = dados[:, 0] if getattr(dados, "ndim", 1) > 1 else dados
                _arquivos["outros"].writeframes((np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes())
    except ImportError:
        _estado["erro"] = "instale o soundcard para gravar o som do PC: python -m pip install soundcard"
    except Exception as e:
        _estado["erro"] = f"captura do PC falhou: {e}"


def _mic(_ts, bloco, _mudo, _jarvis_falando) -> None:
    w = _arquivos.get("voce")
    if w is not None and _estado["gravando"]:
        try:
            w.writeframes(bloco.astype("<i2").tobytes())
        except Exception:
            pass


def iniciar(tipo: str = "ata", titulo: str = "") -> str:
    """tipo 'ata' (reunião) ou 'aula' (1.9: modo aula, plugins/modo_aula.py)."""
    if _estado["gravando"]:
        return f"Já estou gravando {'a aula' if _estado['tipo'] == 'aula' else 'a ata'}."
    nome = datetime.now().strftime("%Y-%m-%d_%H%M") + (f"_{_slug(titulo)}" if titulo else "")
    pasta = pasta_usuario("Documents") / "JARVIS" / ("aulas" if tipo == "aula" else "atas") / nome
    pasta.mkdir(parents=True, exist_ok=True)
    _arquivos.update(outros=_abrir_wav(pasta / "outros.wav"), voce=_abrir_wav(pasta / "voce.wav"))
    _parar.clear()
    _estado.update(gravando=True, pasta=str(pasta), inicio=time.time(), erro="", tipo=tipo, titulo=titulo)
    threading.Thread(target=_gravar_pc, daemon=True, name="ata_pc").start()
    from core import escuta
    escuta.inscrever(_mic)
    if tipo == "aula":
        return ("Gravando a aula (o som do PC e o microfone). No fim, diga 'termina a aula' que eu faço o resumo, "
                "os tópicos e as tarefas.")
    return ("Gravando a ata (o som do PC e o seu microfone). Avise os participantes que a conversa está sendo gravada. "
            "Diga 'termina a ata' no fim.")


def _ler_wav(caminho: Path):
    import numpy as np
    with wave.open(str(caminho), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0


def transcrever(audio) -> list[tuple[float, str]]:
    """[(segundo, texto)] de um áudio 16 kHz. faster-whisper no PC ou, sem ele, a IA em pedaços de 5 min."""
    import numpy as np
    if not len(audio) or float(np.sqrt(np.mean(np.square(audio)))) < 0.002:
        return []
    from plugins.legenda_ao_vivo import _modelo_whisper, _wav
    modelo = _modelo_whisper()
    if modelo is not None:
        segs, _info = modelo.transcribe(audio, vad_filter=True, beam_size=1, language="pt")
        return [(s.start, s.text.strip()) for s in segs if s.text.strip()]
    from plugins import _ia
    if not _ia.disponivel():
        raise RuntimeError("sem faster-whisper e sem chave do Gemini não dá para transcrever (o áudio ficou salvo)")
    from google.genai import types as gtypes

    from core import gemini
    saida = []
    for ini in range(0, len(audio), PEDACO_S * TAXA):
        pedaco = audio[ini:ini + PEDACO_S * TAXA]
        if float(np.sqrt(np.mean(np.square(pedaco)))) < 0.002:
            continue
        resp = gemini.call([gtypes.Part.from_bytes(data=_wav(pedaco), mime_type="audio/wav"),
                            "Transcreva esta fala em português, fiel, sem comentar. Se não houver fala, responda: -"],
                           tier=gemini.SMART, timeout_ms=120_000)
        texto = (getattr(resp, "text", "") or "").strip() if resp is not None else ""
        if texto and texto != "-":
            saida.append((ini / TAXA, texto))
    return saida


def juntar(voce: list[tuple[float, str]], outros: list[tuple[float, str]]) -> str:
    """As duas trilhas numa conversa só, em ordem de tempo (pura)."""
    linhas = sorted([(t, "Você", x) for t, x in voce] + [(t, "Participantes", x) for t, x in outros])
    return "\n".join(f"[{int(t) // 60:02d}:{int(t) % 60:02d}] {quem}: {x}" for t, quem, x in linhas)


def _slug(t: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


PROMPT_AULA = ("Você recebeu a transcrição de uma AULA. Escreva em português do Brasil, em Markdown: ## Resumo (um "
               "parágrafo), ## Tópicos principais (lista com uma linha de explicação cada), ## Conceitos e definições, "
               "## Tarefas e prazos (o que o professor pediu; 'nenhuma' se não houve), ## Dúvidas para revisar. Use só o "
               "que está na transcrição.")


def parar(player=None) -> str:
    if not _estado["gravando"]:
        return "Não estou gravando nada agora."
    aula = _estado.get("tipo") == "aula"
    _parar.set()
    _estado["gravando"] = False
    from core import escuta
    escuta.desinscrever(_mic)
    time.sleep(1.2)
    for w in list(_arquivos.values()):
        try:
            w.close()
        except Exception:
            pass
    _arquivos.clear()
    pasta = Path(_estado["pasta"])
    minutos = (time.time() - _estado["inicio"]) / 60
    try:
        transcricao = juntar(transcrever(_ler_wav(pasta / "voce.wav")), transcrever(_ler_wav(pasta / "outros.wav")))
    except Exception as e:
        return f"Gravei {minutos:.0f} min em {pasta}, mas não transcrevi: {e}"
    (pasta / "transcricao.txt").write_text(transcricao, encoding="utf-8")
    if not transcricao.strip():
        return f"Gravei {minutos:.0f} min, mas não ouvi fala. Os áudios estão em {pasta}."
    from plugins import _ia
    ata = ""
    if _ia.disponivel() and aula:
        ata = _ia.perguntar(f"{PROMPT_AULA}\n\nTítulo: {_estado.get('titulo') or 'aula'}\n\n{transcricao[-60000:]}",
                            True, 150) or ""
    elif _ia.disponivel():
        ata = _ia.perguntar(
            "Escreva a ATA desta reunião em português do Brasil, em Markdown: ## Resumo (até 5 frases), ## Decisões "
            "(lista), ## Tarefas (tabela: Quem | O quê | Prazo; 'a definir' se não disseram), ## Pendências. Use só o "
            f"que está na transcrição.\n\n{transcricao[-60000:]}", True, 150) or ""
    titulo = "# Aula" + (f": {_estado.get('titulo')}" if _estado.get("titulo") else "") if aula else "# Ata"
    texto = (ata or f"{titulo}\n\n(Sem a chave do Gemini, só a transcrição.)") + "\n\n---\n\n## Transcrição\n\n" + transcricao
    arq = pasta / ("aula.md" if aula else "ata.md")
    arq.write_text(texto, encoding="utf-8")
    _estado["ultima"] = str(arq)
    mostrar(player, "RESUMO DA AULA" if aula else "ATA DA CHAMADA", texto[:8000])
    abrir_no_sistema(str(arq))
    if aula:
        return f"Resumo da aula pronto ({minutos:.0f} min) em {arq}: resumo, tópicos, conceitos e tarefas."
    return f"Ata pronta ({minutos:.0f} min) em {arq}." + (" Resumo e tarefas no começo do arquivo." if ata else "")


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {}).get("action") or "status").lower()
    try:
        if acao == "iniciar":
            return iniciar()
        if acao == "parar":
            return parar(player)
        if acao == "ultima":
            pasta = pasta_usuario("Documents") / "JARVIS" / "atas"
            atas = sorted(pasta.glob("*/ata.md")) if pasta.exists() else []
            if not atas:
                return "Ainda não há atas."
            abrir_no_sistema(str(atas[-1]))
            return f"Abri a última ata ({atas[-1].parent.name})."
        if _estado["gravando"]:
            return f"Gravando a ata há {(time.time() - _estado['inicio']) / 60:.0f} min." + \
                (f" Problema: {_estado['erro']}" if _estado["erro"] else "")
        return "Não estou gravando. Diga 'grava a ata da reunião'."
    except Exception as e:
        return f"A ata falhou: {e}"
