"""
Você no talk show (fork PT-BR 2.7). Tudo software, grátis.

O JARVIS vira apresentador de um programa de entrevistas e te entrevista como
se você fosse famoso: seus projetos, suas músicas, seu dia. Ele grava (o seu
microfone e o som do PC, onde sai a voz dele) e no fim você ganha um
"episódio": o áudio mixado (episodio.wav) e a transcrição com título,
descrição e os melhores momentos (episodio.md).

    "Jarvis, me entrevista no talk show"          → abertura com vinheta e a primeira pergunta
    "Talk show sobre o meu projeto J.A.R.V.I.S"   → com tema
    "Encerra o programa"                          → fecha, mixa e salva em Documentos\\JARVIS\\talk_show
"""

from __future__ import annotations

import threading
import time
import wave
from datetime import datetime
from pathlib import Path

from plugins._comum import abrir_no_sistema, mostrar, pasta_usuario

PLUGIN = {
    "name": "talk_show",
    "brief": "Talk show: JARVIS interviews the user like a celebrity, records it and makes an episode.",
    "description": (
        "Talk show where JARVIS is the host interviewing the user as a celebrity guest. action: 'comecar' (tema "
        "optional: projects, music, the day) returns host instructions you must follow — one question at a time, "
        "short, playful; 'encerrar' finishes the show and saves the episode (audio + transcript); 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING"}, "tema": {"type": "STRING"}, "titulo": {"type": "STRING"}},
        "required": ["action"],
    },
}

TAXA = 16000
_estado = {"ativo": False, "inicio": 0.0, "tema": "", "falas": [], "pasta": "", "erro": ""}
_arq: dict = {}
_parar = threading.Event()
_lock = threading.Lock()


def _slug(t: str) -> str:
    import re
    return re.sub(r"[^a-zA-Z0-9]+", "_", t)[:40].strip("_")


def _abrir_wav(caminho: Path):
    w = wave.open(str(caminho), "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(TAXA)
    return w


def _ao_turno(entrada: str, saida: str, interrompido: bool) -> None:
    if _estado["ativo"]:
        with _lock:
            if entrada:
                _estado["falas"].append({"quem": "Convidado", "texto": entrada.strip(), "t": time.time()})
            if saida:
                _estado["falas"].append({"quem": "JARVIS", "texto": saida.strip(), "t": time.time()})


def _mic(_ts, bloco, _mudo, _jarvis) -> None:
    w = _arq.get("voce")
    if w is not None and _estado["ativo"]:
        try:
            w.writeframes(bloco.astype("<i2").tobytes())
        except Exception:
            pass


def _gravar_pc() -> None:
    try:
        import numpy as np
        import soundcard as sc
        mic = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)
        with mic.recorder(samplerate=TAXA, channels=1, blocksize=1024) as rec:
            while not _parar.is_set():
                x = rec.record(numframes=TAXA // 2)
                mono = x[:, 0] if getattr(x, "ndim", 1) > 1 else x
                if _arq.get("pc") is not None:
                    _arq["pc"].writeframes((np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes())
    except ImportError:
        _estado["erro"] = "sem o pacote soundcard, só gravei o seu microfone"
    except Exception as e:
        _estado["erro"] = f"gravação do som do PC falhou: {e}"


def mixar(a, b):
    """Pura (numpy): soma duas faixas mono float de tamanhos diferentes sem estourar."""
    import numpy as np
    n = max(len(a), len(b))
    x = np.zeros(n, dtype="float32")
    x[:len(a)] += a
    x[:len(b)] += b
    pico = float(np.abs(x).max()) if n else 0.0
    return x / pico * 0.95 if pico > 0.95 else x


def roteiro_md(tema: str, falas: list[dict], extra: dict | None = None, quando: datetime | None = None) -> str:
    """Pura: o episódio em Markdown."""
    extra = extra or {}
    quando = quando or datetime.now()
    linhas = [f"# {extra.get('titulo') or 'Talk show do JARVIS'}", "",
              f"*Gravado em {quando.strftime('%d/%m/%Y às %H:%M')}" + (f" · tema: {tema}" if tema else "") + "*", ""]
    if extra.get("descricao"):
        linhas += [extra["descricao"], ""]
    if extra.get("momentos"):
        linhas += ["## Melhores momentos", ""] + [f"- {m}" for m in extra["momentos"]] + [""]
    linhas += ["## Transcrição", ""] + [f"**{f['quem']}:** {f['texto']}" for f in falas]
    return "\n".join(linhas) + "\n"


def comecar(tema: str = "") -> str:
    if _estado["ativo"]:
        return "O programa já está no ar."
    pasta = pasta_usuario("Documents") / "JARVIS" / "talk_show" / (
        datetime.now().strftime("%Y-%m-%d_%H%M") + (f"_{_slug(tema)}" if tema else ""))
    pasta.mkdir(parents=True, exist_ok=True)
    _arq.update(voce=_abrir_wav(pasta / "voce.wav"), pc=_abrir_wav(pasta / "pc.wav"))
    _parar.clear()
    _estado.update(ativo=True, inicio=time.time(), tema=tema, falas=[], pasta=str(pasta), erro="")
    threading.Thread(target=_gravar_pc, daemon=True, name="talk_pc").start()
    try:
        from core import escuta, ganchos_turno
        escuta.inscrever(_mic)
        ganchos_turno.registrar(_ao_turno)
    except Exception:
        pass
    try:
        from plugins import _dupla
        _dupla.efeito("vinheta")
    except Exception:
        pass
    foco = f" O tema principal é: {tema}." if tema else " Pergunte sobre os projetos, a música e o dia dele."
    return ("[TALK SHOW] Você agora é o apresentador carismático de um talk show de TV e o usuário é o convidado "
            "famoso. Abra o programa com energia (\"Boa noite, boa noite! Hoje recebemos…\") e faça UMA pergunta "
            f"por vez, curta, curiosa e bem-humorada; reaja ao que ele disser antes da próxima.{foco} Faça umas 6 "
            "perguntas, com um 'jogo rápido' de 3 perguntas no meio. Quando ele disser para encerrar, ou depois da "
            "última pergunta, se despeça da 'plateia' e chame talk_show com action='encerrar'. O programa está "
            "sendo gravado.")


def _extras(tema: str, falas: list[dict]) -> dict:
    try:
        from plugins import _ia
        txt = "\n".join(f"{f['quem']}: {f['texto']}" for f in falas[-80:])
        r = _ia.perguntar_json(f"Esta é a transcrição de um talk show em que o JARVIS entrevistou o usuário"
                               f"{' sobre ' + tema if tema else ''}:\n{txt}\n\nResponda SÓ JSON: "
                               '{"titulo": "título chamativo do episódio", "descricao": "2 frases", '
                               '"momentos": ["3 a 5 melhores momentos, curtos"]}', inteligente=False)
        return r if isinstance(r, dict) else {}
    except Exception:
        return {}


def encerrar() -> str:
    if not _estado["ativo"]:
        return "Não há programa no ar."
    _estado["ativo"] = False
    _parar.set()
    time.sleep(0.8)
    try:
        from core import escuta
        escuta.desinscrever(_mic)
    except Exception:
        pass
    for k in ("voce", "pc"):
        w = _arq.pop(k, None)
        if w is not None:
            try:
                w.close()
            except Exception:
                pass
    pasta = Path(_estado["pasta"])
    mixado = False
    try:
        import numpy as np

        def ler(c: Path):
            if not c.exists():
                return np.zeros(0, dtype="float32")
            with wave.open(str(c), "rb") as w:
                return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
        x = mixar(ler(pasta / "voce.wav"), ler(pasta / "pc.wav"))
        if len(x):
            with _abrir_wav(pasta / "episodio.wav") as w:
                w.writeframes((x * 32767).astype("<i2").tobytes())
            mixado = True
    except Exception as e:
        print(f"[TalkShow] mixagem: {e}")
    with _lock:
        falas = list(_estado["falas"])
    extra = _extras(_estado["tema"], falas) if falas else {}
    md = roteiro_md(_estado["tema"], falas, extra)
    (pasta / "episodio.md").write_text(md, encoding="utf-8")
    mostrar(None, "TALK SHOW", md[:3000])
    abrir_no_sistema(str(pasta))
    dur = int((time.time() - _estado["inicio"]) / 60)
    return (f"Episódio salvo: '{extra.get('titulo') or 'Talk show do JARVIS'}', {dur} min, "
            f"{'áudio mixado e ' if mixado else ''}transcrição em {pasta}." +
            (f" Aviso: {_estado['erro']}." if _estado["erro"] else "") + " Abri a pasta.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "").lower()
    try:
        if acao in ("comecar", "começar", "iniciar"):
            return comecar(str(p.get("tema") or ""))
        if acao in ("encerrar", "fim", "parar"):
            return encerrar()
        if acao == "status":
            return ("No ar há " + str(int((time.time() - _estado["inicio"]) / 60)) + " min.") if _estado["ativo"] \
                else "Fora do ar."
        return "Ações: comecar, encerrar, status."
    except Exception as e:
        return f"Talk show falhou: {e}"
