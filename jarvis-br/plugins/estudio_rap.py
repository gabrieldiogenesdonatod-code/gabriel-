"""
Estúdio de rap (fork PT-BR 2.4).

    "Jarvis, me dá rimas com 'impossível'"
    "Jarvis, toca um beat de trap em loop" / "para o beat"
    "Jarvis, grava um take num boom bap"           (conta 1 compasso, toca o beat e grava sua voz por cima)
    "Jarvis, grava 4 voltas num trap a 140"
    "Jarvis, toca o último take" / "lista meus takes"

O take sai em Música\\JARVIS\\takes: a mixagem (voz + beat) e a voz sozinha
(para mixar no FL Studio/Audacity). Enquanto grava, o JARVIS não escuta
(o microfone fica reservado para você) — USE FONE, senão o beat vaza na voz.
Tudo local, com numpy e sounddevice.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

from plugins import _som
from plugins._comum import MEMORIA, abrir_no_sistema, cfg, gravar_json, ler_json, mostrar, pasta_usuario, registrar

PLUGIN = {
    "name": "estudio_rap",
    "brief": "Rap studio: rhymes for a word, beat in loop, record a vocal take over the beat and save it.",
    "description": (
        "Rap studio. action='rimas' with palavra gives rhymes (perfect and slant, plus the user's own words); "
        "'beat' plays a beat in loop (estilo trap|boom bap|lofi|funk|drill, optional bpm) until 'parar'; 'gravar' "
        "records a take: counts in one bar, plays the beat (estilo, bpm, voltas = loops, default 2) and records the "
        "user's voice over it, saving mix + dry vocal (tell him to use headphones and that you will be silent while "
        "recording; after calling, say only one short sentence); 'ouvir' plays the last take; 'takes' lists them."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "rimas | beat | parar | gravar | ouvir | takes"},
                       "palavra": {"type": "STRING"}, "estilo": {"type": "STRING"}, "bpm": {"type": "INTEGER"},
                       "voltas": {"type": "INTEGER"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "estudio_rap",
    "title": "Estúdio de rap",
    "fields": [
        {"key": "atraso_ms", "label": "Compensar atraso da gravação (ms; 0 = automático)", "type": "text", "default": "0"},
        {"key": "volume_beat", "label": "Volume do beat na mixagem (0 a 1)", "type": "text", "default": "0.55"},
    ],
}

ARQ = MEMORIA / "estudio_rap.json"
_estado = {"laco": None, "gravando": False, "ultimo": ""}


def _pasta() -> Path:
    p = pasta_usuario("Music") / "JARVIS" / "takes"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def contagem(bpm: int, taxa: int = _som.TAXA):
    """Um compasso de 4 cliques (o 1º mais agudo) para entrar no tempo."""
    np = _som._np()
    batida = 60 / bpm
    total = np.zeros(int(4 * batida * taxa), "float32")
    for i in range(4):
        t = _som.tempo(0.05, taxa)
        f = 1800 if i == 0 else 1200
        clique = (np.sin(2 * np.pi * f * t) * np.exp(-t * 60)).astype("float32") * 0.7
        ini = int(i * batida * taxa)
        total[ini:ini + len(clique)] += clique[:len(total) - ini]
    return total


def mixar(voz, beat, atraso_amostras: int = 0, volume_beat: float = 0.55):
    """Alinha a voz (tira o atraso de gravação) e soma com o beat, sem estourar."""
    np = _som._np()
    voz = np.asarray(voz, "float32")
    if atraso_amostras > 0:
        voz = voz[atraso_amostras:]
    n = len(beat)
    v = np.zeros(n, "float32")
    v[:min(n, len(voz))] = voz[:n]
    pico_voz = float(np.max(np.abs(v))) if n else 0.0
    if pico_voz > 0:
        v = v * (0.9 / pico_voz)                                # voz na frente
    mix = v + np.asarray(beat, "float32") * volume_beat
    return _som.normalizar(np.tanh(mix * 1.05), 0.95)


def _atraso_amostras(taxa: int) -> int:
    try:
        ms = float(str(cfg("estudio_rap", PLUGIN_SETTINGS).get("atraso_ms") or 0).replace(",", "."))
    except ValueError:
        ms = 0.0
    if ms > 0:
        return int(ms / 1000 * taxa)
    try:
        import sounddevice as sd
        ent = sd.query_devices(kind="input")["default_low_input_latency"]
        sai = sd.query_devices(kind="output")["default_low_output_latency"]
        return int((ent + sai) * taxa)
    except Exception:
        return int(0.12 * taxa)


def _beat(estilo: str, bpm: int, compassos: int = 4):
    from plugins import gerador_beats as gb
    estilo = gb.estilo_de(estilo or "trap")
    bpm = max(60, min(180, int(bpm or gb.ESTILOS[estilo]["bpm"])))
    audio = gb.renderizar(estilo, bpm, compassos, "Am", int(time.time()) % 100000)
    passo = 60 / bpm / 4
    audio = audio[:int(compassos * 16 * passo * _som.TAXA)]     # corta a cauda: o laço fica no tempo
    return estilo, bpm, audio


# ── ações ────────────────────────────────────────────────────────────────────
# Palavras de rap a mais (as terminações que mais aparecem em rima), além do léxico do parceiro_rima.
LEXICO_RAP = """incrível invencível nível visível possível terrível horrível sensível imprevisível invisível indestrutível
irresistível combustível inesquecível acessível compatível crível flexível plausível previsível legível risível
impossível disponível infalível inacessível irreversível perecível desprezível
coração razão visão missão paixão pressão emoção mão chão irmão leão canção visão ilusão prisão solidão
multidão direção decisão perdão revolução evolução geração favela quebrada estrada jornada caminhada parada
madrugada calçada chegada largada pegada camarada nada tudo mundo segundo profundo vagabundo
vida guerra terra serra fera mistério império critério sério verdade cidade saudade vontade liberdade
humildade realidade amizade lealdade felicidade sonho medonho tristonho risonho
correr vencer viver crescer sofrer perder nascer morrer saber poder querer prazer dever
lutar sonhar chegar voar brilhar ganhar mudar acreditar superar conquistar caminhar respirar
estrela favela janela panela tela vela novela trilha milha ilha família maravilha
fogo jogo logo foco louco pouco troco sufoco rouco
dinheiro primeiro guerreiro verdadeiro inteiro parceiro terreiro herdeiro estrangeiro
amor dor flor cor calor valor temor clamor sabor suor rumor motor ator senhor melhor pior
força forca peso preso aceso ileso
batida partida ferida saída medida esquecida perdida vencida corrida subida descida
lírico empírico satírico onírico físico místico artístico
""".split()


def rimas(palavra: str) -> str:
    from plugins import parceiro_rima as pr
    d = ler_json(pr._ARQ, {}) if hasattr(pr, "_ARQ") else {}
    extras = ((d or {}).get("palavras", []) if isinstance(d, dict) else []) + LEXICO_RAP
    perfeitas, toantes = pr.sugerir(palavra, extras)
    perfeitas = [w for w in perfeitas if pr._dobrar(w) != pr._dobrar(palavra)]
    ia = []
    try:
        from plugins import _ia
        if _ia.disponivel():
            r = _ia.perguntar(f"Liste 15 palavras em português que rimam com '{palavra}' (rima perfeita), boas para rap, "
                              "separadas por vírgula, sem explicação.", False, 15) or ""
            ia = [w.strip(" .\n").lower() for w in r.split(",") if 2 < len(w.strip()) < 25 and " " not in w.strip()]
    except Exception:
        ia = []
    todas = list(dict.fromkeys(perfeitas + [w for w in ia if pr.rimam(palavra, w) == "perfeita"]))
    if not todas and not toantes:
        return f"Não achei rimas boas para '{palavra}'."
    return (f"Rimas com '{palavra}': " + ", ".join(todas[:16])
            + (f". Toantes: {', '.join(toantes[:8])}" if toantes else "") + ".")


def tocar_beat(estilo: str, bpm: int) -> str:
    parar()
    estilo, bpm, audio = _beat(estilo, bpm)
    laco = _som.Laco(audio, taxa=_som.TAXA, volume=0.6)
    laco.tocar()
    _estado["laco"] = laco
    return f"Beat de {estilo} a {bpm} BPM em loop. Diga 'para o beat' quando quiser."


def parar() -> bool:
    laco, _estado["laco"] = _estado["laco"], None
    if laco is not None:
        threading.Thread(target=laco.parar, daemon=True).start()
        return True
    return False


def _gravar_take(estilo: str, bpm: int, voltas: int, player) -> None:
    from core import microfone
    try:
        import sounddevice as sd
        np = _som._np()
        estilo, bpm, beat = _beat(estilo, bpm)
        tocar = np.concatenate([contagem(bpm), np.tile(beat, voltas)])
        duracao = len(tocar) / _som.TAXA
        microfone.esperar_jarvis_calar()
        with microfone.reservado_por("estúdio de rap", duracao + 5):
            gravado = sd.playrec(tocar.reshape(-1, 1), samplerate=_som.TAXA, channels=1, dtype="float32")
            sd.wait()
        cont = len(contagem(bpm))
        voz = gravado[cont:, 0]
        beat_total = tocar[cont:]
        try:
            vol = float(str(cfg("estudio_rap", PLUGIN_SETTINGS).get("volume_beat") or 0.55).replace(",", "."))
        except ValueError:
            vol = 0.55
        mix = mixar(voz, beat_total, _atraso_amostras(_som.TAXA), vol)
        nome = f"take_{datetime.now():%Y%m%d_%H%M%S}_{estilo.replace(' ', '')}_{bpm}"
        arq_mix = _som.salvar_wav(_pasta() / f"{nome}.wav", mix)
        _som.salvar_wav(_pasta() / f"{nome}_voz.wav", voz)
        _estado["ultimo"] = str(arq_mix)
        d = ler_json(ARQ, {}) or {}
        d["takes"] = (d.get("takes", []) + [{"arquivo": str(arq_mix), "estilo": estilo, "bpm": bpm,
                                             "segundos": round(len(mix) / _som.TAXA), "ts": time.time()}])[-50:]
        gravar_json(ARQ, d)
        registrar(player, f"🎤 Take salvo: {arq_mix.name} ({len(mix) / _som.TAXA:.0f} s).")
        from plugins._comum import falar
        falar(player, "[ESTÚDIO] Diga em UMA frase curta que o take foi salvo e pergunte se ele quer ouvir. "
                      "Não chame nenhuma ferramenta.")
    except Exception as e:
        registrar(player, f"Estúdio de rap: a gravação falhou: {e}")
    finally:
        _estado["gravando"] = False


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "rimas").lower()
    try:
        if acao == "rimas":
            palavra = str(p.get("palavra") or "").strip().strip("'\"")
            return rimas(palavra) if palavra else "Rima com qual palavra?"
        if acao == "beat":
            return tocar_beat(str(p.get("estilo") or "trap"), int(p.get("bpm") or 0))
        if acao == "parar":
            return "Beat parado." if parar() else "Não tem beat tocando."
        if acao == "gravar":
            if _estado["gravando"]:
                return "Já estou gravando um take."
            import importlib.util
            if importlib.util.find_spec("sounddevice") is None:
                return "Para gravar preciso do sounddevice (python -m pip install sounddevice)."
            parar()
            voltas = max(1, min(8, int(p.get("voltas") or 2)))
            _estado["gravando"] = True
            threading.Thread(target=_gravar_take, args=(str(p.get("estilo") or "trap"), int(p.get("bpm") or 0),
                                                        voltas, player), daemon=True, name="estudio_rap").start()
            return (f"Gravando: espere eu calar, vem 1 compasso de contagem e o beat roda {voltas} vez(es) com você "
                    "por cima. Use fone. Diga só: 'Valendo! Use fone.'")
        if acao == "ouvir":
            alvo = _estado["ultimo"] or ((ler_json(ARQ, {}) or {}).get("takes") or [{}])[-1].get("arquivo", "")
            if not alvo or not Path(alvo).exists():
                return "Ainda não tem take gravado."
            abrir_no_sistema(alvo)
            return f"Tocando {Path(alvo).name}."
        takes = (ler_json(ARQ, {}) or {}).get("takes") or []
        if not takes:
            return "Nenhum take ainda. Diga 'grava um take num trap'."
        texto = "\n".join(f"{datetime.fromtimestamp(t['ts']):%d/%m %H:%M} — {Path(t['arquivo']).name} ({t['segundos']} s)"
                          for t in takes[-10:])
        mostrar(player, "TAKES", texto + f"\n\nPasta: {_pasta()}")
        return f"{len(takes)} take(s); os últimos estão na tela."
    except Exception as e:
        return f"O estúdio falhou: {e}"
