"""
JARVIS + FRIDAY em voz alta (fork PT-BR 2.7). Começa com "_": não é ferramenta.

O motor das cenas com mais de um personagem: diálogo, debate, reunião,
radionovela, comentário de filme, podcast. Cada personagem tem a SUA voz
(Edge TTS, grátis, precisa de internet; sem ele, a voz do Windows) e o seu
rosto no palco (dashboard/static/palco.html), que acende e mexe a boca quando
ele fala. Enquanto a cena roda, o microfone do JARVIS fica pausado (para ele
não responder à própria conversa) — diga "Jarvis, para" ou aperte Esc no palco.

    roteiro(prompt, personagens)  → [{"quem": "FRIDAY", "texto": "..."}]  (com a IA)
    encenar(falas, titulo, ...)   → toca em segundo plano (uma cena por vez)
    falar(quem, texto)            → uma fala só, já com a voz certa
Personagens criados pelo usuário ficam em memory/personagens.json.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import threading
import time
import wave
from pathlib import Path

from plugins._comum import CNW, MEMORIA, WIN, gravar_json, ler_json

ARQ_PERSONAGENS = MEMORIA / "personagens.json"
PERSONAGENS = {
    "JARVIS": {"voz": "pt-BR-AntonioNeural", "taxa": "+0%", "tom": "-6Hz", "cor": "56,214,255",
               "estilo": "mordomo britânico, formal, calmo, ironia sutil; chama o usuário de 'senhor'",
               "sapi": "male"},
    "FRIDAY": {"voz": "pt-BR-FranciscaNeural", "taxa": "+8%", "tom": "+0Hz", "cor": "255,120,190",
               "estilo": "jovem, direta, animada, bom humor, provoca o JARVIS com carinho; chama o usuário de 'chefe'",
               "sapi": "female"},
    "FRIDAY_NOITE": {"nome": "FRIDAY", "voz": "pt-BR-FranciscaNeural", "taxa": "-10%", "tom": "-2Hz",
                     "cor": "190,140,255", "estilo": "a FRIDAY no turno da noite: calma, voz baixa, acolhedora",
                     "sapi": "female"},
    "ULTRON": {"voz": "pt-BR-AntonioNeural", "taxa": "-12%", "tom": "-22Hz", "cor": "255,77,94",
               "estilo": "vilão robótico dramático e engraçado, ameaça arquivos temporários, mas é inofensivo",
               "sapi": "male"},
    "ENGENHEIRO": {"voz": "pt-BR-ThalitaMultilingualNeural", "taxa": "+0%", "tom": "-4Hz", "cor": "120,255,170",
                   "estilo": "engenheira prática, pensa em custo, prazo e o que dá para entregar", "sapi": "female"},
    "CRÍTICO": {"voz": "pt-PT-DuarteNeural", "taxa": "-4%", "tom": "-8Hz", "cor": "255,181,71",
                "estilo": "crítico cético e sarcástico, aponta os riscos e o que pode dar errado", "sapi": "male"},
    "VILAO": {"nome": "VILÃO", "voz": "pt-BR-AntonioNeural", "taxa": "-8%", "tom": "-18Hz", "cor": "170,90,255",
              "estilo": "o vilão da semana da campanha de herói: teatral, ameaçador e engraçado", "sapi": "male"},
    "NARRADOR": {"voz": "pt-BR-AntonioNeural", "taxa": "-6%", "tom": "-12Hz", "cor": "200,200,200",
                 "estilo": "narrador de radionovela, voz grave e dramática", "sapi": "male"},
}
_lock = threading.Lock()
_estado = {"cena": None, "titulo": "", "personagens": [], "quem": "", "texto": "", "nivel": 0.0, "id": 0,
           "parar": threading.Event(), "rodando": False, "opcoes": [], "fim": False, "rodape": ""}


# ── personagens ───────────────────────────────────────────────────────────────
def personagens() -> dict:
    extra = ler_json(ARQ_PERSONAGENS, {}) or {}
    return {**PERSONAGENS, **{k.upper(): v for k, v in extra.items() if isinstance(v, dict)}}


def criar_personagem(nome: str, estilo: str, feminino: bool = False) -> str:
    nome = re.sub(r"[^\wÀ-ú ]", "", str(nome or "")).strip().upper()[:20]
    if not nome or not estilo:
        return "Diga o nome e o jeito do personagem."
    extra = ler_json(ARQ_PERSONAGENS, {}) or {}
    cores = ["160,220,255", "255,220,120", "180,255,200", "255,160,140", "220,180,255"]
    extra[nome] = {"voz": "pt-BR-FranciscaNeural" if feminino else "pt-BR-AntonioNeural",
                   "taxa": "+0%", "tom": f"{(len(nome) * 7) % 15 - 7:+d}Hz", "cor": cores[len(extra) % len(cores)],
                   "estilo": str(estilo)[:200], "sapi": "female" if feminino else "male"}
    gravar_json(ARQ_PERSONAGENS, extra)
    return f"Criei {nome}: {estilo}."


def nome_visivel(quem: str) -> str:
    return personagens().get(quem, {}).get("nome", quem)


# ── voz ───────────────────────────────────────────────────────────────────────
def _edge(texto: str, p: dict):
    import edge_tts
    import miniaudio
    import numpy as np

    async def junta():
        buf = bytearray()
        async for parte in edge_tts.Communicate(texto, p["voz"], rate=p.get("taxa", "+0%"),
                                                pitch=p.get("tom", "+0Hz")).stream():
            if parte["type"] == "audio":
                buf.extend(parte["data"])
        return bytes(buf)
    mp3 = asyncio.run(junta())
    d = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1, sample_rate=24000)
    return np.asarray(d.samples, dtype=np.float32), 24000


def _sapi(texto: str, p: dict):
    """Voz do próprio Windows (sem internet)."""
    import numpy as np
    if not WIN:
        return None
    # Fork PT-BR 2.7.1: o texto vai num arquivo UTF-8 (pela entrada padrão os acentos chegavam trocados)
    # e cada fala usa arquivos próprios (duas falas ao mesmo tempo não brigam pelo mesmo .wav).
    marca = f"{threading.get_ident()}_{time.monotonic_ns()}"
    destino = Path(MEMORIA) / f"_fala_{marca}.wav"
    origem = Path(MEMORIA) / f"_fala_{marca}.txt"
    origem.write_text(texto, encoding="utf-8")
    aspas = lambda c: str(c).replace("'", "''")                  # noqa: E731 — caminho com apóstrofo
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"try {{ $s.SelectVoiceByHints('{'Female' if p.get('sapi') == 'female' else 'Male'}') }} catch {{}}; "
          f"$t = [IO.File]::ReadAllText('{aspas(origem)}', [Text.Encoding]::UTF8); "
          f"$s.SetOutputToWaveFile('{aspas(destino)}'); $s.Speak($t); $s.Dispose()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=60, creationflags=CNW,
                       capture_output=True)
        with wave.open(str(destino), "rb") as w:
            sr, n, larg = w.getframerate(), w.getnframes(), w.getsampwidth()
            bruto = w.readframes(n)
    finally:
        origem.unlink(missing_ok=True)
        destino.unlink(missing_ok=True)
    x = np.frombuffer(bruto, dtype=np.int16 if larg == 2 else np.uint8).astype(np.float32)
    return (x / 32768.0 if larg == 2 else (x - 128) / 128.0), sr


def sintetizar(quem: str, texto: str):
    """(amostras float32, taxa) ou None."""
    p = personagens().get(quem) or PERSONAGENS["JARVIS"]
    for motor in (_edge, _sapi):
        try:
            r = motor(texto, p)
            if r is not None and len(r[0]):
                return r
        except Exception as e:
            print(f"[Dupla] voz ({motor.__name__}): {e}")
    return None


def envelope(x, sr: int, passo_s: float = 0.05) -> list[float]:
    """Nível (0..1) a cada 50 ms, para a boca do rosto no palco (puro)."""
    import numpy as np
    n = max(1, int(sr * passo_s))
    blocos = [float(np.sqrt(np.mean(x[i:i + n] ** 2))) for i in range(0, len(x), n)]
    pico = max(blocos) if blocos else 1.0
    return [min(1.0, b / (pico or 1.0) * 1.2) for b in blocos]


def _tocar(x, sr: int) -> None:
    """Toca e anima a boca; para no meio se pedirem."""
    env = envelope(x, sr)
    try:
        import sounddevice as sd
        sd.play(x, sr)
    except Exception as e:
        print(f"[Dupla] som: {e}")
        sd = None
    inicio = time.time()
    dur = len(x) / sr
    while time.time() - inicio < dur:
        if _estado["parar"].is_set():
            if sd is not None:
                sd.stop()
            break
        i = int((time.time() - inicio) / 0.05)
        _estado["nivel"] = env[i] if i < len(env) else 0.0
        time.sleep(0.03)
    _estado["nivel"] = 0.0
    time.sleep(0.25)


def falar(quem: str, texto: str, emocao: str | None = None) -> bool:
    """Uma fala, com a voz e o rosto do personagem. True se tocou som."""
    quem = (quem or "JARVIS").upper()
    try:                                         # 2.14: o rosto no palco faz a cara da fala
        from core import emocoes
        emocoes.definir(emocao or emocoes.detectar(texto) or "neutro", 3.0 + len(texto) / 12, 1.0, quem)
    except Exception:
        pass
    with _lock:
        _estado.update(quem=quem, texto=texto)
        _estado["id"] += 1
    s = sintetizar(quem, texto)
    if s is None:
        time.sleep(min(8.0, 1.0 + len(texto) / 15))           # sem voz: deixa a legenda na tela o tempo de ler
        return False
    _tocar(*s)
    return True


# ── roteiro com a IA ──────────────────────────────────────────────────────────
def roteiro(pedido: str, elenco: list[str], falas: int = 8, extra: str = "") -> list[dict]:
    from plugins import _ia
    ps = personagens()
    descr = "\n".join(f"- {nome_visivel(n)} ({n}): {ps.get(n, {}).get('estilo', '')}" for n in elenco)
    j = _ia.perguntar_json(
        f"Escreva uma cena falada em português do Brasil, natural e divertida, com estes personagens:\n{descr}\n\n"
        f"CENA: {pedido}\n{extra}\nRegras: {falas} falas no máximo, cada uma com até 2 frases curtas (vai ser "
        "lida em voz alta), um responde o outro de verdade, nada de narração entre parênteses nem emojis. "
        f"Use no campo 'quem' exatamente um destes códigos: {', '.join(elenco)}. Devolva "
        '{"falas": [{"quem": "...", "texto": "..."}]}', inteligente=True, segundos=60)
    saida = []
    for f in ((j or {}).get("falas") or []) if isinstance(j, dict) else []:
        quem = str(f.get("quem") or "").upper().strip()
        texto = re.sub(r"\s*\([^)]*\)", "", str(f.get("texto") or "")).strip()
        if quem in elenco and texto:
            saida.append({"quem": quem, "texto": texto[:400]})
    return saida[:max(1, falas + 2)]


# ── cena em segundo plano + palco ────────────────────────────────────────────
def rodando() -> bool:
    return _estado["rodando"]


def parar() -> None:
    _estado["parar"].set()


def encenar(falas: list[dict], titulo: str = "", elenco: list[str] | None = None, abrir_palco: bool = True,
            opcoes: list[str] | None = None, ao_terminar=None, rodape: str = "", pausar_microfone: bool = True) -> bool:
    """Toca as falas numa thread. False se já há uma cena rodando."""
    if _estado["rodando"] or not falas:
        return False
    try:                                         # Fork PT-BR 2.8: no modo dormir nenhuma cena começa sozinha
        from core import sono
        if sono.dormindo():
            print(f"[Dupla] cena '{titulo}' não começou: o JARVIS está no modo dormir")
            return False
    except Exception:
        pass
    elenco = elenco or list(dict.fromkeys(f["quem"] for f in falas))
    _estado["parar"].clear()
    with _lock:
        _estado.update(rodando=True, titulo=titulo, personagens=elenco, quem="", texto="", opcoes=[], fim=False,
                       rodape=rodape)
        _estado["id"] += 1
    if abrir_palco:
        abrir()

    def rodar():
        from core import microfone
        try:
            if pausar_microfone:
                microfone.esperar_jarvis_calar(maximo_s=12)
                microfone.reservar("cena", 60 * 20)
            time.sleep(1.2)
            for f in falas:
                if _estado["parar"].is_set():
                    break
                if f.get("efeito"):
                    efeito(f["efeito"])
                if f.get("emocao"):                     # 2.14: cara escolhida pela cena
                    falar(f["quem"], f["texto"], f["emocao"])
                else:
                    falar(f["quem"], f["texto"])
            with _lock:
                _estado.update(opcoes=list(opcoes or []), fim=True, quem="", texto="")
                _estado["id"] += 1
        except Exception as e:
            print(f"[Dupla] {e}")
        finally:
            if pausar_microfone:
                microfone.liberar()
            _estado["rodando"] = False
            if ao_terminar:
                try:
                    ao_terminar()
                except Exception as e:
                    print(f"[Dupla] fim: {e}")
    threading.Thread(target=rodar, daemon=True, name="cena").start()
    return True


def efeito(nome: str) -> None:
    """Efeitos curtos gerados na hora (sem arquivo)."""
    try:
        import numpy as np

        from plugins import _som
        taxa = 22050
        t = _som.tempo(0.6, taxa)
        rng = np.random.default_rng(1)
        if nome == "porta":
            x = _som.filtrar(_som.ruido(0.6, rng, taxa), baixa=400, taxa=taxa) * np.exp(-t * 8)
        elif nome == "trovao":
            t = _som.tempo(1.8, taxa)
            x = _som.filtrar(_som.ruido(1.8, rng, taxa), baixa=250, taxa=taxa) * np.exp(-t * 2)
        elif nome == "suspense":
            t = _som.tempo(1.5, taxa)
            x = 0.4 * np.sin(2 * np.pi * 110 * t) * np.sin(2 * np.pi * 0.7 * t) + 0.3 * np.sin(2 * np.pi * 116 * t)
        elif nome == "vinheta":
            t = _som.tempo(1.6, taxa)
            x = sum(np.sin(2 * np.pi * f * t) * (t > k * 0.18) for k, f in enumerate((392, 523, 659, 784)))
            x *= np.exp(-t * 1.2)
        else:                                                   # "whoosh"
            x = _som.filtrar(_som.ruido(0.6, rng, taxa), alta=800, taxa=taxa) * np.sin(np.pi * t / 0.6)
        _som.tocar_uma(_som.normalizar(np.asarray(x, dtype="float32"), 0.6), taxa, 0.6)
    except Exception as e:
        print(f"[Dupla] efeito: {e}")


def estado_palco(_q: dict | None = None) -> dict:
    ps = personagens()
    with _lock:
        return {"id": _estado["id"], "titulo": _estado["titulo"], "rodando": _estado["rodando"],
                "quem": _estado["quem"], "texto": _estado["texto"], "nivel": round(_estado["nivel"], 3),
                "opcoes": _estado["opcoes"], "fim": _estado["fim"], "rodape": _estado["rodape"],
                "personagens": [{"id": n, "nome": nome_visivel(n), "cor": ps.get(n, {}).get("cor", "56,214,255"),
                                 "emocao": _emocao(n), "rosto": _rosto(n)}
                                for n in _estado["personagens"]]}


def _emocao(n: str) -> str:
    """2.14: a emoção atual do personagem no palco."""
    try:
        from core import emocoes
        return emocoes.atual(n)[0]
    except Exception:
        return "neutro"


def _rosto(n: str) -> str:
    """2.14: qual desenho de rosto: 'friday' (cabelo, cílios, batom) para as personagens femininas."""
    p = personagens().get(n, {})
    if n.startswith("FRIDAY") or p.get("sapi") == "female":
        return "friday"
    return "jarvis"


def comando_palco(b: dict) -> dict:
    if b.get("acao") == "parar":
        parar()
    return {"ok": True}


def abrir() -> bool:
    try:
        from plugins import _arcade
        _arcade.ROTAS_GET["/api/palco"] = estado_palco
        _arcade.ROTAS_POST["/api/palco/cmd"] = comando_palco
        return _arcade.abrir_pagina("/palco", 1100, 640, extras=["--autoplay-policy=no-user-gesture-required"])
    except Exception as e:
        print(f"[Dupla] palco: {e}")
        return False


def texto_falas(falas: list[dict]) -> str:
    return "\n".join(f"{nome_visivel(f['quem'])}: {f['texto']}" for f in falas)

