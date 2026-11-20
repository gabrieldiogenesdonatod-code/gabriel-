"""Calculadora musical (2.18): BPM→ms do delay/reverb, frequência das notas, transpor acordes e notas do acorde."""
from __future__ import annotations

import re

from plugins._lote2 import P, numeros, rodar

PLUGIN = P("calculadora_musical", "Music math for beatmaking: BPM to delay ms (1/4, 1/8, dotted, triplet), note frequency, transpose chords, chord notes.",
           "delay | frequencia | transpor | acorde | bpm_de_ms",
           "delay: valor (BPM). frequencia: texto (A4, C#3). transpor: texto (chords 'Am F C G'), valor (semitones). "
           "acorde: texto (Cm7, G, F#dim). bpm_de_ms: valor (ms of a beat).",
           "valor texto")

NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
BEMOL = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
TIPOS = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11],
         "dim": [0, 3, 6], "aug": [0, 4, 8], "sus4": [0, 5, 7], "sus2": [0, 2, 7], "5": [0, 7]}


def delay(bpm: float) -> dict:
    q = 60000 / bpm
    return {"1/4": q, "1/8": q / 2, "1/16": q / 4, "1/4 pontuada": q * 1.5, "1/8 pontuada": q * .75, "1/8 tercina": q / 3}


def _raiz(t: str) -> tuple[int, str]:
    m = re.match(r"([A-G][#b]?)(.*)", t.strip())
    if not m:
        raise ValueError(f"não entendi '{t}'")
    r = BEMOL.get(m.group(1), m.group(1))
    return NOTAS.index(r), m.group(2)


def frequencia(t: str) -> float:
    i, resto = _raiz(t)
    oit = int(re.sub(r"\D", "", resto) or 4)
    return 440 * 2 ** ((i - 9 + (oit - 4) * 12) / 12)


def transpor(acordes: str, semitons: int) -> str:
    out = []
    for a in acordes.split():
        i, resto = _raiz(a)
        if "/" in resto:
            tipo, baixo = resto.split("/", 1)
            bi, _ = _raiz(baixo)
            out.append(f"{NOTAS[(i + semitons) % 12]}{tipo}/{NOTAS[(bi + semitons) % 12]}")
        else:
            out.append(NOTAS[(i + semitons) % 12] + resto)
    return " ".join(out)


def acorde(t: str) -> list[str]:
    i, tipo = _raiz(t)
    return [NOTAS[(i + s) % 12] for s in TIPOS.get(tipo, TIPOS[""])]


def _go(p, pl):
    a, v, t = str(p.get("action")).lower(), numeros(p.get("valor")), str(p.get("texto") or "")
    if a == "delay":
        return "; ".join(f"{k}: {ms:.0f} ms" for k, ms in delay(v[0] if v else 90).items())
    if a == "bpm_de_ms":
        return f"{60000 / v[0]:.1f} BPM."
    if a == "frequencia":
        return f"{t}: {frequencia(t):.2f} Hz."
    if a == "transpor":
        return transpor(t, int(v[0]) if v else 2)
    return f"{t}: {' '.join(acorde(t))}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("delay frequencia transpor acorde bpm_de_ms".split(), _go), player)
