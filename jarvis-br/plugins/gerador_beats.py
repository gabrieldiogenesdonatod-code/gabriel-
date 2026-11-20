"""
Gerador de beats (fork PT-BR 1.6).

Instrumentais simples feitos na hora, em Python puro (numpy), sem samples:
bumbo, caixa, chimbal, palma e baixo 808 com a progressão de acordes.

    "Jarvis, faz um beat de trap"               "Jarvis, beat boom bap a 88 BPM"
    "Jarvis, um lo-fi para estudar"             "Jarvis, faz um funk"     "Jarvis, um drill"
    "Jarvis, faz outro parecido"                (muda a variação)

Salva um WAV em Música\\JARVIS\\beats (e um .mid, se você tiver o pacote mido,
para abrir no FL Studio/LMMS) e toca.
"""

from __future__ import annotations

import random
import re
import time

from plugins import _som
from plugins._comum import MEMORIA, abrir_no_sistema, gravar_json, ler_json, pasta_usuario

PLUGIN = {
    "name": "gerador_beats",
    "brief": "Makes simple instrumental beats (trap, boom bap, lo-fi, funk, drill) as WAV (and MIDI), synthesized.",
    "description": (
        "Beat generator: estilo = trap | boom bap | lofi | funk | drill; optional bpm, compassos (bars, default 8), "
        "tom (e.g. 'Am', 'C#m'), outro = true for a new variation of the last style. Saves a WAV (and MIDI if mido is "
        "installed) in Music/JARVIS/beats and plays it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"estilo": {"type": "STRING"}, "bpm": {"type": "INTEGER"}, "compassos": {"type": "INTEGER"},
                       "tom": {"type": "STRING"}, "outro": {"type": "BOOLEAN"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "beats.json"
# 16 passos por compasso. 1 = toca; números entre 0 e 1 = probabilidade (variação a cada compasso)
ESTILOS = {
    "trap": {"bpm": 140, "swing": 0.0, "bumbo": [1, 0, 0, 0, 0, 0, 0, .5, 1, 0, .3, 0, 0, 0, 0, 0],
             "caixa": [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0], "chimbal": [1] * 16, "rolos": True, "palma": True},
    "boom bap": {"bpm": 90, "swing": 0.58, "bumbo": [1, 0, 0, 0, 0, 0, 0, .4, 0, 0, 1, 0, 0, 0, .3, 0],
                 "caixa": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], "chimbal": [1, 0] * 8, "rolos": False, "palma": False},
    "lofi": {"bpm": 80, "swing": 0.6, "bumbo": [1, 0, 0, 0, 0, 0, .3, 0, 0, 0, 1, 0, 0, 0, 0, 0],
             "caixa": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, .2], "chimbal": [1, 0, .6, 0] * 4, "rolos": False,
             "palma": False},
    "funk": {"bpm": 130, "swing": 0.0, "bumbo": [1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0],
             "caixa": [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0], "chimbal": [0, 0, 1, 0] * 4, "rolos": False,
             "palma": True},
    "drill": {"bpm": 142, "swing": 0.0, "bumbo": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
              "caixa": [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, .5], "chimbal": [1, 0, 0, 1, 0, 0, 1, 0] * 2,
              "rolos": True, "palma": False},
}
NOTAS = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8,
         "A": 9, "A#": 10, "BB": 10, "B": 11}
PROGRESSAO = [0, 8, 3, 10]                                     # i – VI – III – VII (menor)


def estilo_de(texto: str) -> str:
    t = (texto or "").lower().replace("-", " ")
    for nome in ESTILOS:
        if nome in t or nome.replace(" ", "") in t.replace(" ", ""):
            return nome
    return "lofi" if "estud" in t or "relax" in t else "funk" if "baile" in t or "tamborz" in t else "trap"


def freq_tom(tom: str) -> float:
    """'Am' → frequência da tônica na oitava do 808 (~ 41–78 Hz) (pura)."""
    m = re.match(r"([A-Ga-g])([#b]?)", (tom or "A").strip())
    nota = NOTAS.get((m.group(1) + m.group(2)).upper(), 9) if m else 9
    return 440.0 * 2 ** ((nota - 9) / 12) / 8 * (2 if nota < 5 else 1)


def padrao(estilo: str, compassos: int, semente: int) -> dict[str, list[list[int]]]:
    """Para cada instrumento, os passos que tocam em cada compasso (pura com semente)."""
    e, r = ESTILOS[estilo], random.Random(semente)
    saida: dict[str, list[list[int]]] = {"bumbo": [], "caixa": [], "chimbal": [], "rolos": [], "palma": []}
    for c in range(compassos):
        for inst in ("bumbo", "caixa", "chimbal"):
            saida[inst].append([i for i, v in enumerate(e[inst]) if v >= 1 or (v > 0 and r.random() < v)])
        saida["rolos"].append(sorted(r.sample(range(16), 2)) if e["rolos"] and c % 2 == 1 else [])
        saida["palma"].append(saida["caixa"][-1] if e["palma"] else [])
    return saida


def renderizar(estilo: str, bpm: int, compassos: int, tom: str, semente: int):
    np = _som._np()
    taxa = _som.TAXA
    e = ESTILOS[estilo]
    passo = 60 / bpm / 4                                       # semicolcheia em segundos
    total = int(compassos * 16 * passo * taxa) + taxa
    mix = np.zeros(total, "float32")
    rng = np.random.default_rng(semente)
    sons = {"bumbo": _som.bumbo(), "caixa": _som.caixa(rng=rng), "chimbal": _som.chimbal(rng=rng),
            "palma": _som.palma(rng=rng)}
    ganhos = {"bumbo": 0.9, "caixa": 0.7, "chimbal": 0.35, "palma": 0.45}

    def por(som, inicio_s, ganho):
        i = int(inicio_s * taxa)
        fim = min(total, i + len(som))
        if 0 <= i < total:
            mix[i:fim] += som[:fim - i] * ganho

    pad = padrao(estilo, compassos, semente)
    for c in range(compassos):
        base = c * 16 * passo
        for inst in ("bumbo", "caixa", "chimbal", "palma"):
            for s in pad[inst][c]:
                atraso = passo * (e["swing"] - 0.5) * 2 if e["swing"] and s % 2 == 1 else 0
                por(sons[inst], base + s * passo + atraso, ganhos[inst] * (0.75 if inst == "chimbal" and s % 4 else 1))
        for s in pad["rolos"][c]:                              # rolos de chimbal (trap/drill)
            for k in range(3):
                por(sons["chimbal"], base + s * passo + k * passo / 3, 0.22)
    raiz = freq_tom(tom)
    for c in range(compassos):                                 # 808 seguindo a progressão, no bumbo
        f = raiz * 2 ** (PROGRESSAO[(c // 2) % 4] / 12)
        for s in pad["bumbo"][c]:
            dur = passo * (4 if estilo in ("trap", "drill") else 2)
            deslize = f * 1.5 if estilo == "drill" and s == 10 else None
            por(_som.baixo808(f, dur, deslize_de=deslize), c * 16 * passo + s * passo, 0.55)
    if estilo == "lofi":                                       # chiado de vinil e tudo mais abafado
        mix = _som.filtrar(mix, baixa=4500, taxa=taxa) + 0.03 * _som.filtrar(
            _som.ruido(len(mix) / taxa, rng), alta=2000, taxa=taxa)[:len(mix)]
    return _som.normalizar(np.tanh(mix * 1.2), 0.92)


def midi(caminho, estilo: str, bpm: int, compassos: int, semente: int) -> bool:
    try:
        import mido
    except ImportError:
        return False
    arq = mido.MidiFile(ticks_per_beat=480)
    pista = mido.MidiTrack()
    arq.tracks.append(pista)
    pista.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
    eventos = []
    pad = padrao(estilo, compassos, semente)
    for c in range(compassos):
        for inst, nota in (("bumbo", 36), ("caixa", 38), ("chimbal", 42)):
            for s in pad[inst][c]:
                eventos.append(((c * 16 + s) * 120, nota))
    agora = 0
    for t, nota in sorted(eventos):
        pista.append(mido.Message("note_on", channel=9, note=nota, velocity=100, time=t - agora))
        pista.append(mido.Message("note_off", channel=9, note=nota, velocity=0, time=60))
        agora = t + 60
    arq.save(str(caminho))
    return True


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    try:
        ultimo = ler_json(_ARQ, {}) or {}
        estilo = estilo_de(str(p.get("estilo") or "")) if p.get("estilo") or not p.get("outro") else \
            ultimo.get("estilo", "trap")
        bpm = int(p.get("bpm") or (ultimo.get("bpm") if p.get("outro") else 0) or ESTILOS[estilo]["bpm"])
        bpm = max(60, min(180, bpm))
        compassos = max(2, min(32, int(p.get("compassos") or 8)))
        tom = str(p.get("tom") or random.choice(["Am", "Cm", "Dm", "Em", "F#m", "Gm"]))
        semente = int(time.time()) % 100000
        audio = renderizar(estilo, bpm, compassos, tom, semente)
        pasta = pasta_usuario("Music") / "JARVIS" / "beats"
        pasta.mkdir(parents=True, exist_ok=True)
        nome = f"{estilo.replace(' ', '_')}_{bpm}bpm_{tom.replace('#', 's')}_{semente}"
        wav = _som.salvar_wav(pasta / f"{nome}.wav", audio)
        tem_midi = midi(pasta / f"{nome}.mid", estilo, bpm, compassos, semente)
        gravar_json(_ARQ, {"estilo": estilo, "bpm": bpm, "tom": tom, "arquivo": str(wav)})
        abrir_no_sistema(str(wav))
        return (f"Beat de {estilo} a {bpm} BPM em {tom}, {compassos} compassos ({len(audio) / _som.TAXA:.0f} s). "
                f"Salvei em {wav}" + (" (e o .mid para editar)" if tem_midi else "") + " e já está tocando.")
    except Exception as e:
        return f"O gerador de beats falhou: {e}"
