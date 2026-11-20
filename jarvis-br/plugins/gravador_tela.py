"""
Gravação de tela — plugin do J.A.R.V.I.S BR.

    "Jarvis, grava a tela"                       → tela inteira (monitor principal)
    "Jarvis, grava só o CapCut"                  → só a janela daquele app
    "Jarvis, grava a tela na vertical"           → corte 9:16 (Reels/TikTok/Stories)
    "Jarvis, para a gravação"                    → salva em Vídeos/JARVIS

Dois motores:
    * ffmpeg (se estiver instalado no PATH): H.264, arquivo menor, pouca CPU;
    * mss + OpenCV (já vêm com o JARVIS): funciona sem instalar nada.
Grava só imagem (sem som). Limite de duração configurável, para não lotar o disco.
"""

from __future__ import annotations

import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from plugins._comum import (CNW, LINUX, MAC, WIN, abrir_no_sistema, cfg, num,
                            pasta_usuario, registrar, sim, tamanho, tem)

PLUGIN = {
    "name": "gravador_tela",
    "brief": "Screen recording: start (screen, monitor, window, vertical 9:16), stop, status.",
    "description": (
        "Screen recording. action='iniciar' with alvo = 'tela' (default), 'monitor 2', or an "
        "app/window name to record only that window; vertical=sim crops to 9:16 for "
        "Reels/TikTok. action='parar' stops and saves to the Videos folder; 'status'; "
        "'abrir_pasta' opens the recordings folder."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "iniciar | parar | status | abrir_pasta"},
            "alvo": {"type": "STRING"},
            "vertical": {"type": "STRING", "description": "sim for 9:16"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "gravador_tela",
    "title": "Gravação de tela",
    "fields": [
        {"key": "fps", "label": "Quadros por segundo", "type": "text", "default": "30"},
        {"key": "max_min", "label": "Duração máxima (minutos)", "type": "text", "default": "60"},
        {"key": "motor", "label": "Motor", "type": "choice",
         "options": ["automático", "ffmpeg", "mss + opencv"], "default": "automático"},
        {"key": "pasta", "label": "Pasta (vazio = Vídeos/JARVIS)", "type": "text", "default": ""},
    ],
}

_estado: dict = {}


def pasta_saida() -> Path:
    c = cfg("gravador_tela", PLUGIN_SETTINGS)
    p = Path(str(c.get("pasta") or "").strip()) if c.get("pasta") else pasta_usuario("Videos") / "JARVIS"
    p.mkdir(parents=True, exist_ok=True)
    return p


def recorte_vertical(largura: int, altura: int) -> tuple[int, int, int, int]:
    """(x, y, w, h) do maior retângulo 9:16 centralizado, com lados pares."""
    w = int(altura * 9 / 16)
    h = altura
    if w > largura:
        w, h = largura, int(largura * 16 / 9)
    w -= w % 2
    h -= h % 2
    return (largura - w) // 2, (altura - h) // 2, w, h


def _regiao(alvo: str) -> tuple[dict | None, dict | None, str]:
    """(região mss {left, top, width, height}, janela, descrição)."""
    import mss
    t = str(alvo or "tela").lower().strip()
    with mss.mss() as sct:
        monitores = sct.monitors[1:] or sct.monitors
        if t in ("", "tela", "tela inteira", "tudo", "monitor", "monitor principal"):
            m = monitores[0]
            return dict(m), None, "tela inteira"
        if t.startswith("monitor"):
            n = int(num(t.replace("monitor", ""), 1))
            if not 1 <= n <= len(monitores):
                raise ValueError(f"só existem {len(monitores)} monitores")
            return dict(monitores[n - 1]), None, f"monitor {n}"
    from plugins import _janelas
    j = _janelas.achar(alvo)
    if not j:
        raise ValueError(f"não achei a janela {alvo}")
    if j.get("minimizada"):
        _janelas.estado(j, "restaurar")
        time.sleep(0.4)
        j = _janelas.achar(alvo) or j
    l, t_, r, b = j["ret"]
    return {"left": l, "top": t_, "width": r - l, "height": b - t_}, j, f"janela {j['titulo'][:40]}"


# ── motor mss + OpenCV ─────────────────────────────────────────────────────────
def _gravar_mss(arquivo: Path, regiao: dict, janela: dict | None, vertical: bool, fps: int,
                max_s: float, parar: threading.Event):
    import cv2
    import mss
    import numpy as np
    w, h = regiao["width"] - regiao["width"] % 2, regiao["height"] - regiao["height"] % 2
    corte = recorte_vertical(w, h) if vertical else (0, 0, w, h)
    saida_w, saida_h = corte[2], corte[3]
    escrita = cv2.VideoWriter(str(arquivo), cv2.VideoWriter_fourcc(*"mp4v"), fps, (saida_w, saida_h))
    intervalo = 1.0 / fps
    inicio = time.perf_counter()
    quadros = 0
    ultimo_quadro = None
    from plugins import _janelas
    with mss.mss() as sct:
        while not parar.is_set() and time.perf_counter() - inicio < max_s:
            if janela is not None and quadros % fps == 0:          # segue a janela 1×/s
                atual = _janelas.achar(janela["titulo"][:30])
                if atual and not atual.get("minimizada"):
                    l, t = atual["ret"][0], atual["ret"][1]
                    regiao = {"left": l, "top": t, "width": w, "height": h}
            try:
                img = np.asarray(sct.grab(regiao))[:, :, :3]
                img = img[: h, : w]
                x, y, cw, ch = corte
                quadro = np.ascontiguousarray(img[y:y + ch, x:x + cw])
                if quadro.shape[0] != saida_h or quadro.shape[1] != saida_w:
                    quadro = cv2.resize(quadro, (saida_w, saida_h))
                ultimo_quadro = quadro
            except Exception:
                quadro = ultimo_quadro
            # mantém a duração real: se atrasou, repete o quadro
            devido = int((time.perf_counter() - inicio) / intervalo) + 1
            while quadros < devido and quadro is not None:
                escrita.write(quadro)
                quadros += 1
            espera = inicio + quadros * intervalo - time.perf_counter()
            if espera > 0:
                parar.wait(espera)
    escrita.release()


# ── motor ffmpeg ───────────────────────────────────────────────────────────────
def comando_ffmpeg(arquivo: Path, regiao: dict, janela: dict | None, vertical: bool,
                   fps: int, max_s: float) -> list[str] | None:
    filtros = ["crop=trunc(iw/2)*2:trunc(ih/2)*2"]
    if vertical:
        filtros.append("crop='trunc(min(iw,ih*9/16)/2)*2':'trunc(min(ih,iw*16/9)/2)*2'")
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if WIN:
        entrada = ["-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1"]
        if janela is not None:
            entrada += ["-i", f"title={janela['titulo']}"]
        else:
            entrada += ["-offset_x", str(regiao["left"]), "-offset_y", str(regiao["top"]),
                        "-video_size", f"{regiao['width']}x{regiao['height']}", "-i", "desktop"]
    elif LINUX:
        if janela is not None:
            return None
        import os
        tela = os.environ.get("DISPLAY", ":0")
        entrada = ["-f", "x11grab", "-framerate", str(fps),
                   "-video_size", f"{regiao['width']}x{regiao['height']}",
                   "-i", f"{tela}+{regiao['left']},{regiao['top']}"]
    else:
        return None
    return base + entrada + ["-t", str(int(max_s)), "-vf", ",".join(filtros), "-c:v", "libx264",
                             "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", str(arquivo)]


def iniciar(alvo: str, vertical: bool, player) -> str:
    if _estado.get("ativo"):
        return f"Já estou gravando ({_estado['descricao']}). Diga 'para a gravação'."
    try:
        import mss  # noqa: F401
    except ImportError:
        return "Para gravar a tela preciso do mss: pip install mss"
    c = cfg("gravador_tela", PLUGIN_SETTINGS)
    fps = max(5, min(60, int(num(c.get("fps"), 30))))
    max_s = max(1.0, num(c.get("max_min"), 60)) * 60
    try:
        regiao, janela, descricao = _regiao(alvo)
    except Exception as e:
        return f"Não consegui preparar a gravação: {e}"
    arquivo = pasta_saida() / f"gravacao_{datetime.now():%Y%m%d_%H%M%S}{'_vertical' if vertical else ''}.mp4"
    motor = str(c.get("motor") or "automático")
    cmd = None
    if motor != "mss + opencv" and tem("ffmpeg") and not MAC:
        cmd = comando_ffmpeg(arquivo, regiao, janela, vertical, fps, max_s)
    parar = threading.Event()
    _estado.update({"ativo": True, "arquivo": arquivo, "inicio": time.time(), "parar": parar,
                    "descricao": descricao + (" (vertical)" if vertical else ""), "proc": None})
    if cmd:
        try:
            _estado["proc"] = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                               stderr=subprocess.PIPE, **CNW)
            _estado["motor"] = "ffmpeg"
        except Exception as e:
            print(f"[Gravador] ffmpeg falhou ({e}); usando mss")
            cmd = None
    if not cmd:
        try:
            import cv2  # noqa: F401
        except ImportError:
            _estado.clear()
            return "Para gravar sem ffmpeg preciso do OpenCV: pip install opencv-python"
        _estado["motor"] = "mss"
        t = threading.Thread(target=_gravar_mss, args=(arquivo, regiao, janela, vertical, fps, max_s, parar),
                             daemon=True, name="gravador")
        _estado["thread"] = t
        t.start()
    registrar(player, f"● GRAVANDO {_estado['descricao']} — diga 'para a gravação'.")
    return (f"Gravando {_estado['descricao']} a {fps} quadros por segundo. "
            f"Diga 'para a gravação' quando terminar (limite de {int(max_s / 60)} minutos).")


def parar(player) -> str:
    if not _estado.get("ativo"):
        return "Não estou gravando nada."
    _estado["parar"].set()
    proc = _estado.get("proc")
    if proc is not None:
        try:
            proc.communicate(input=b"q", timeout=15)
        except Exception:
            proc.kill()
    elif _estado.get("thread"):
        _estado["thread"].join(timeout=15)
    arquivo, dur = _estado["arquivo"], time.time() - _estado["inicio"]
    _estado.clear()
    if not arquivo.exists() or arquivo.stat().st_size < 1024:
        return "A gravação falhou: o arquivo não foi criado."
    registrar(player, f"Gravação salva: {arquivo}")
    return (f"Gravação salva: {arquivo.name}, {int(dur // 60)} min {int(dur % 60)} s, "
            f"{tamanho(arquivo.stat().st_size)}, na pasta {arquivo.parent.name}.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "iniciar").strip().lower()
    try:
        if a == "iniciar":
            return iniciar(str(p.get("alvo") or "tela"), sim(p.get("vertical")), player)
        if a == "parar":
            return parar(player)
        if a == "status":
            if not _estado.get("ativo"):
                return "Não estou gravando."
            return f"Gravando {_estado['descricao']} há {int(time.time() - _estado['inicio'])} segundos."
        if a == "abrir_pasta":
            return "Abrindo a pasta de gravações." if abrir_no_sistema(str(pasta_saida())) else \
                "Não consegui abrir a pasta."
        return "Use iniciar, parar, status ou abrir_pasta."
    except Exception as e:
        return f"O gravador falhou: {e}"
