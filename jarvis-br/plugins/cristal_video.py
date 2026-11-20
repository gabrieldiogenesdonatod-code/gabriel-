"""
Montador de vídeo de produto — Cristal Malhas (fork PT-BR 1.4).

Você grava os clipes crus (celular, qualquer orientação) e solta numa pasta.
O JARVIS:
    1. corta os SILÊNCIOS de cada clipe (fala ou som ambiente ficam);
    2. junta tudo em ordem de nome/data;
    3. deixa em 9:16 (1080×1920), preenchendo a tela (Reels/TikTok/Stories);
    4. põe a LOGO da loja no canto (se você indicar o PNG nas configurações);
    5. gera a LEGENDA falada com o Whisper (faster-whisper, o mesmo do motor
       offline) e queima no vídeo — ou, sem ele, com o modelo de IA;
    6. exporta MP4 (H.264 + AAC) pronto para postar.

    "Jarvis, monta o vídeo do produto"           (pasta padrão de clipes)
    "Jarvis, monta o vídeo do vestido floral sem legenda"

Precisa do ffmpeg: winget install Gyan.FFmpeg  (ou pip install imageio-ffmpeg).
Pastas padrão: Vídeos\\Cristal Malhas\\Brutos  →  Vídeos\\Cristal Malhas\\Prontos
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from plugins._comum import CNW, WIN, abrir_no_sistema, cfg, pasta_usuario

PLUGIN = {
    "name": "cristal_video",
    "brief": "Builds a 9:16 product video from raw clips: cuts silences, adds logo and burned subtitles.",
    "description": (
        "Product video builder for the Cristal Malhas store: takes the raw clips in a folder, cuts "
        "silences, joins them, makes 9:16 1080x1920, overlays the store logo, adds burned-in Portuguese "
        "subtitles (Whisper or AI) and exports MP4. action='montar' (optional pasta, nome, legenda "
        "sim/nao, logo sim/nao) runs in the background and warns when done; 'status'; 'abrir_pasta'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "montar | status | abrir_pasta"},
            "pasta": {"type": "STRING"}, "nome": {"type": "STRING"},
            "legenda": {"type": "STRING"}, "logo": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "cristal_video",
    "title": "Cristal Malhas — vídeos",
    "fields": [
        {"key": "pasta_brutos", "label": "Pasta dos clipes crus (vazio = Vídeos\\Cristal Malhas\\Brutos)",
         "type": "text", "default": ""},
        {"key": "pasta_prontos", "label": "Pasta dos vídeos prontos (vazio = Vídeos\\Cristal Malhas\\Prontos)",
         "type": "text", "default": ""},
        {"key": "logo", "label": "Logo da loja (arquivo PNG)", "type": "text", "default": ""},
        {"key": "silencio_db", "label": "Silêncio abaixo de (dB)", "type": "text", "default": "-35"},
        {"key": "modelo_whisper", "label": "Modelo do Whisper", "type": "choice",
         "choices": ["base", "small", "medium"], "default": "small"},
    ],
}

_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".3gp"}
_estado = {"rodando": False, "etapa": "", "ultimo": "", "erro": ""}


# ── ffmpeg ─────────────────────────────────────────────────────────────────────
def achar_ffmpeg() -> str | None:
    for nome in ("ffmpeg",):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    if WIN:
        for c in (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
                  Path("C:/ffmpeg/bin/ffmpeg.exe"), Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe")):
            if c.exists():
                return str(c)
    return None


def _rodar(args: list[str], timeout: float = 1800, cwd: str | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, cwd=cwd, **CNW)
        return r.returncode, (r.stderr or b"").decode("utf-8", "replace") + (r.stdout or b"").decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return -9, "demorou demais"
    except Exception as e:
        return -1, str(e)


def info(ff: str, arq: Path) -> dict:
    """Duração e se tem áudio, lendo a saída do próprio ffmpeg (sem ffprobe)."""
    _c, saida = _rodar([ff, "-hide_banner", "-i", str(arq)], timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", saida)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    return {"duracao": dur, "audio": bool(re.search(r"Stream #\S+.*Audio:", saida)),
            "video": bool(re.search(r"Stream #\S+.*Video:", saida))}


def silencios(ff: str, arq: Path, limiar_db: float = -35, minimo_s: float = 0.6) -> list[tuple[float, float]]:
    _c, saida = _rodar([ff, "-hide_banner", "-nostats", "-i", str(arq), "-af",
                        f"silencedetect=noise={limiar_db}dB:d={minimo_s}", "-f", "null", "-"], timeout=600)
    inicios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", saida)]
    fins = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", saida)]
    pares = []
    for i, ini in enumerate(inicios):
        pares.append((max(0.0, ini), fins[i] if i < len(fins) else float("inf")))
    return pares


def partes_com_som(duracao: float, sil: list[tuple[float, float]], folga: float = 0.15,
                   minimo: float = 0.4) -> list[tuple[float, float]]:
    """O complemento dos silêncios, com uma folga nas pontas (pura)."""
    partes, cursor = [], 0.0
    for ini, fim in sorted(sil):
        if ini - cursor > 0:
            partes.append((max(0.0, cursor - folga if cursor > 0 else 0.0), min(duracao, ini + folga)))
        cursor = max(cursor, fim)
    if duracao - cursor > 0:
        partes.append((max(0.0, cursor - folga if cursor > 0 else 0.0), duracao))
    return [(round(a, 3), round(b, 3)) for a, b in partes if b - a >= minimo]


# ── legendas ───────────────────────────────────────────────────────────────────
def _tempo_srt(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    seg, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{seg:02d},{ms:03d}"


def srt_de(segmentos: list[tuple[float, float, str]], max_chars: int = 32) -> str:
    """Quebra frases longas em pedaços curtos (cabe na tela vertical)."""
    blocos, n = [], 1
    for ini, fim, texto in segmentos:
        palavras = texto.split()
        if not palavras:
            continue
        linhas, atual = [], ""
        for w in palavras:
            if len(atual) + len(w) + 1 > max_chars and atual:
                linhas.append(atual)
                atual = w
            else:
                atual = f"{atual} {w}".strip()
        linhas.append(atual)
        passo = (fim - ini) / len(linhas)
        for i, l in enumerate(linhas):
            blocos.append(f"{n}\n{_tempo_srt(ini + i * passo)} --> {_tempo_srt(ini + (i + 1) * passo)}\n{l}\n")
            n += 1
    return "\n".join(blocos)


def transcrever(arq: Path, modelo: str = "small") -> tuple[list[tuple[float, float, str]], str]:
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
        segs, _info = m.transcribe(str(arq), language="pt", vad_filter=True)
        return [(s.start, s.end, s.text.strip()) for s in segs if s.text.strip()], "faster-whisper"
    except ImportError:
        pass
    except Exception as e:
        print(f"[CristalVideo] whisper: {e}")
    from plugins import _ia
    if not _ia.disponivel():
        return [], "nenhum (instale faster-whisper ou configure a IA)"
    ff = achar_ffmpeg()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        _rodar([ff, "-y", "-i", str(arq), "-ac", "1", "-ar", "16000", str(wav)], timeout=300)
        if not wav.exists() or wav.stat().st_size > 18_000_000:
            return [], "IA (áudio grande demais)"
        try:
            from google.genai import types as gtypes
            from core import gemini
            resp = gemini.call([gtypes.Part.from_bytes(data=wav.read_bytes(), mime_type="audio/wav"),
                                "Transcreva a fala em português do Brasil com tempos. Responda SÓ JSON: "
                                '[{"inicio": segundos, "fim": segundos, "texto": "..."}]'],
                               tier=gemini.SMART, timeout_ms=120_000)
            bruto = (getattr(resp, "text", "") or "") if resp is not None else ""
            bruto = bruto[bruto.find("["): bruto.rfind("]") + 1]
            dados = json.loads(bruto) if bruto else []
            return [(float(d["inicio"]), float(d["fim"]), str(d["texto"])) for d in dados], "IA"
        except Exception as e:
            print(f"[CristalVideo] IA: {e}")
            return [], "IA (falhou)"


# ── montagem ───────────────────────────────────────────────────────────────────
def _pastas() -> tuple[Path, Path]:
    c = cfg("cristal_video", PLUGIN_SETTINGS)
    base = pasta_usuario("Videos") / "Cristal Malhas"
    brutos = Path(c.get("pasta_brutos") or base / "Brutos")
    prontos = Path(c.get("pasta_prontos") or base / "Prontos")
    return brutos, prontos


def montar(pasta: str = "", nome: str = "", legenda: bool = True, usar_logo: bool = True,
           progresso=lambda _t: None) -> dict:
    ff = achar_ffmpeg()
    if not ff:
        raise RuntimeError("não achei o ffmpeg. Instale com: winget install Gyan.FFmpeg")
    c = cfg("cristal_video", PLUGIN_SETTINGS)
    brutos, prontos = _pastas()
    origem = Path(pasta) if pasta else brutos
    clipes = sorted((a for a in origem.iterdir() if a.suffix.lower() in _VIDEO), key=lambda a: (a.stat().st_mtime, a.name)) \
        if origem.is_dir() else []
    if not clipes:
        origem.mkdir(parents=True, exist_ok=True)
        raise RuntimeError(f"não há clipes em {origem}. Coloque os vídeos crus lá.")
    try:
        limiar = float(str(c.get("silencio_db") or -35).replace(",", "."))
    except ValueError:
        limiar = -35.0
    prontos.mkdir(parents=True, exist_ok=True)
    nome_saida = re.sub(r'[<>:"/\\|?*]+', "_", nome or "produto").strip() or "produto"
    saida = prontos / f"{nome_saida}_{time.strftime('%Y%m%d_%H%M')}.mp4"
    logo = Path(str(c.get("logo") or "")) if usar_logo else None
    if logo is not None and not logo.is_file():
        logo = None
    entradas, filtros, rotulos = [], [], []
    k = 0
    tempo_total, cortado = 0.0, 0.0
    for i, clip in enumerate(clipes):
        progresso(f"analisando {clip.name}")
        inf = info(ff, clip)
        if not inf["video"] or inf["duracao"] <= 0:
            continue
        entradas += ["-i", str(clip)]
        partes = partes_com_som(inf["duracao"], silencios(ff, clip, limiar)) if inf["audio"] else [(0.0, inf["duracao"])]
        if not partes:
            partes = [(0.0, inf["duracao"])]
        tempo_total += inf["duracao"]
        cortado += inf["duracao"] - sum(b - a for a, b in partes)
        idx = len(entradas) // 2 - 1
        for a, b in partes:
            filtros.append(f"[{idx}:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,"
                           f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[v{k}]")
            if inf["audio"]:
                filtros.append(f"[{idx}:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                               f"aresample=44100,aformat=channel_layouts=stereo[a{k}]")
            else:
                filtros.append(f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=duration={b - a}[a{k}]")
            rotulos.append(f"[v{k}][a{k}]")
            k += 1
    if not rotulos:
        raise RuntimeError("nenhum clipe de vídeo válido")
    filtros.append(f"{''.join(rotulos)}concat=n={k}:v=1:a=1[vc][ac]")
    final_v = "[vc]"
    if logo:
        entradas += ["-i", str(logo)]
        idx_logo = len(entradas) // 2 - 1
        filtros.append(f"[{idx_logo}:v]scale=240:-1[logo];[vc][logo]overlay=W-w-40:60[vl]")
        final_v = "[vl]"
    with tempfile.TemporaryDirectory(prefix="jarvis_video_") as tmp:
        meio = Path(tmp) / "montado.mp4"
        progresso(f"juntando {k} trecho(s) em 9:16")
        cod, log = _rodar([ff, "-y", "-hide_banner", *entradas, "-filter_complex", ";".join(filtros),
                           "-map", final_v, "-map", "[ac]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(meio)])
        if cod != 0 or not meio.exists():
            raise RuntimeError("o ffmpeg falhou ao montar: " + log.strip()[-400:])
        motor_leg = "desligada"
        if legenda:
            progresso("gerando a legenda")
            segs, motor_leg = transcrever(meio, str(c.get("modelo_whisper") or "small"))
            if segs:
                (Path(tmp) / "leg.srt").write_text(srt_de(segs), encoding="utf-8")
                estilo = ("FontName=Arial,FontSize=13,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                          "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=70,Bold=1")
                cod, log = _rodar([ff, "-y", "-hide_banner", "-i", "montado.mp4", "-vf",
                                   f"subtitles=leg.srt:force_style='{estilo}'", "-c:v", "libx264", "-preset",
                                   "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "copy",
                                   "-movflags", "+faststart", "final.mp4"], cwd=tmp)
                if cod == 0 and (Path(tmp) / "final.mp4").exists():
                    meio = Path(tmp) / "final.mp4"
                    shutil.copy2(Path(tmp) / "leg.srt", saida.with_suffix(".srt"))
                else:
                    motor_leg += " (não consegui queimar: ffmpeg sem libass?)"
            else:
                motor_leg += " — sem fala detectada" if "nenhum" not in motor_leg else ""
        shutil.copy2(meio, saida)
    dur = info(ff, saida)["duracao"]
    return {"arquivo": str(saida), "clipes": len(clipes), "trechos": k, "duracao": round(dur, 1),
            "cortado_s": round(cortado, 1), "bruto_s": round(tempo_total, 1), "legenda": motor_leg,
            "logo": bool(logo)}


def _em_segundo_plano(player, pasta, nome, legenda, logo) -> None:
    from plugins._notificar import notificar
    _estado.update(rodando=True, erro="", etapa="começando")
    try:
        r = montar(pasta, nome, legenda, logo, progresso=lambda t: _estado.update(etapa=t))
        _estado["ultimo"] = r["arquivo"]
        notificar(player, f"Vídeo pronto: {Path(r['arquivo']).name}, {r['duracao']:.0f} s, {r['trechos']} trechos; "
                          f"cortei {r['cortado_s']:.0f} s de silêncio. Legenda: {r['legenda']}.",
                  titulo="Cristal Malhas", etiqueta="VÍDEO")
    except Exception as e:
        _estado["erro"] = str(e)
        notificar(player, f"Não consegui montar o vídeo: {e}", titulo="Cristal Malhas", etiqueta="VÍDEO")
    finally:
        _estado.update(rodando=False, etapa="")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "montar").lower()
    nao = ("nao", "não", "sem", "false", "0", "no")
    try:
        if acao == "status":
            if _estado["rodando"]:
                return f"Montando: {_estado['etapa']}."
            return (f"Último vídeo: {Path(_estado['ultimo']).name}." if _estado["ultimo"] else "Nenhum vídeo montado ainda.") \
                + (f" Último erro: {_estado['erro']}" if _estado["erro"] else "")
        if acao == "abrir_pasta":
            _b, prontos = _pastas()
            prontos.mkdir(parents=True, exist_ok=True)
            abrir_no_sistema(str(prontos))
            return "Abri a pasta dos vídeos prontos."
        if _estado["rodando"]:
            return f"Já estou montando um vídeo ({_estado['etapa']})."
        if not achar_ffmpeg():
            return "Preciso do ffmpeg para montar vídeos. Instale com: winget install Gyan.FFmpeg"
        threading.Thread(target=_em_segundo_plano, daemon=True,
                         args=(player, str(p.get("pasta") or ""), str(p.get("nome") or ""),
                               str(p.get("legenda") or "sim").lower() not in nao,
                               str(p.get("logo") or "sim").lower() not in nao)).start()
        brutos, _p = _pastas()
        return (f"Montando o vídeo com os clipes de {Path(p.get('pasta') or brutos).name}. Corto os silêncios, "
                "deixo em 9:16 e te aviso quando ficar pronto.")
    except Exception as e:
        return f"O montador falhou: {e}"
