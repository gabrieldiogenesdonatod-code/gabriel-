"""
Modo Jogo / Desempenho — plugin do J.A.R.V.I.S BR.

"Jarvis, modo jogo":
    1. fecha os apps pesados da sua lista (respeitando a lista de proteção) e
       lembra quais eram;
    2. troca o plano de energia para Alto desempenho;
    3. pausa as notificações do Windows (os "toasts");
    4. mostra um overlay pequeno, sempre no topo e que não pega cliques, com
       CPU, GPU, RAM, temperatura e FPS (o FPS vem do PresentMon, se você
       instalar; sem ele o overlay mostra o resto).

"Jarvis, modo normal" desfaz tudo: plano anterior, notificações de volta, apps
reabertos e overlay fechado. O estado fica em memory/modo_jogo.json, então dá
para voltar ao normal mesmo depois de reiniciar o JARVIS.
"""

from __future__ import annotations

import csv
import io
import subprocess
import threading
import time
from pathlib import Path

import psutil

from plugins._comum import (CNW, MEMORIA, WIN, cfg, gravar_json, iniciar, ler_json,
                            registrar, sim)
from plugins._protecao import nome_base, proteger_processo

PLUGIN = {
    "name": "modo_jogo",
    "brief": "Game mode on/off: closes heavy apps, high performance, pauses notifications, overlay.",
    "description": (
        "Game / performance mode. action='ligar' for 'modo jogo', 'modo desempenho', "
        "'vou jogar'; action='desligar' for 'modo normal', 'sai do modo jogo'; "
        "action='status'; action='overlay' with ligar=sim|nao to show or hide only the "
        "performance overlay."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ligar | desligar | status | overlay"},
            "ligar": {"type": "STRING", "description": "overlay: sim | nao"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "modo_jogo",
    "title": "Modo jogo",
    "fields": [
        {"key": "apps_pesados", "label": "Apps para fechar (separados por vírgula)", "type": "text",
         "default": "OneDrive, Teams, ms-teams, Skype, Dropbox, GoogleDriveFS, "
                    "AdobeCollabSync, CCXProcess, Creative Cloud"},
        {"key": "fechar_navegadores", "label": "Fechar também os navegadores", "type": "toggle",
         "default": False},
        {"key": "reabrir", "label": "Reabrir os apps no modo normal", "type": "toggle", "default": True},
        {"key": "alto_desempenho", "label": "Plano de energia Alto desempenho", "type": "toggle",
         "default": True},
        {"key": "pausar_notificacoes", "label": "Pausar notificações", "type": "toggle", "default": True},
        {"key": "overlay", "label": "Mostrar overlay de desempenho", "type": "toggle", "default": True},
        {"key": "posicao", "label": "Posição do overlay", "type": "choice",
         "options": ["superior direito", "superior esquerdo", "inferior direito", "inferior esquerdo"],
         "default": "superior direito"},
        {"key": "presentmon", "label": "Caminho do PresentMon.exe (para FPS, opcional)",
         "type": "text", "default": "", "placeholder": r"C:\Ferramentas\PresentMon.exe"},
    ],
}

_ESTADO = MEMORIA / "modo_jogo.json"
_NAVEGADORES = ("chrome", "msedge", "firefox", "opera", "brave", "vivaldi")

_overlay = None
_fps = {"valor": None, "proc": None, "pid": None}


def _cfg() -> dict:
    return cfg("modo_jogo", PLUGIN_SETTINGS)


def lista_fechar(c: dict) -> list[str]:
    nomes = [n.strip() for n in str(c.get("apps_pesados") or "").split(",") if n.strip()]
    if sim(c.get("fechar_navegadores")):
        nomes += list(_NAVEGADORES)
    return nomes


# ── apps ───────────────────────────────────────────────────────────────────────
def _fechar(nomes: list[str]) -> tuple[list[str], list[str]]:
    """Fecha e devolve (nomes fechados, executáveis para reabrir)."""
    alvos = {nome_base(n) for n in nomes}
    fechados, exes, procs = set(), [], []
    for p in psutil.process_iter(["name", "exe"]):
        n = nome_base(p.info.get("name") or "")
        if n not in alvos or proteger_processo(p):
            continue
        procs.append(p)
        fechados.add(p.info.get("name") or n)
        exe = p.info.get("exe")
        if exe and exe not in exes:
            exes.append(exe)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    _vivos, restantes = psutil.wait_procs(procs, timeout=4)
    for p in restantes:
        try:
            p.kill()
        except Exception:
            pass
    return sorted(fechados), exes


# ── notificações (Windows) ─────────────────────────────────────────────────────
_TOAST = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"


def _toasts(ligar: bool | None):
    """Lê (ligar=None) ou define o interruptor de notificações. None se não der."""
    if not WIN:
        return None
    try:
        import winreg
        k = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _TOAST, 0,
                               winreg.KEY_READ | winreg.KEY_SET_VALUE)
        try:
            atual = bool(winreg.QueryValueEx(k, "ToastEnabled")[0])
        except OSError:
            atual = True
        if ligar is not None:
            winreg.SetValueEx(k, "ToastEnabled", 0, winreg.REG_DWORD, 1 if ligar else 0)
        winreg.CloseKey(k)
        return atual
    except Exception as e:
        print(f"[ModoJogo] notificações: {e}")
        return None


# ── FPS pelo PresentMon (opcional) ─────────────────────────────────────────────
def _pid_da_frente() -> int | None:
    if not WIN:
        return None
    import ctypes
    from ctypes import wintypes
    h = ctypes.windll.user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return pid.value or None


def fps_de_linhas(linhas: list[dict], janela_ms: float = 1000.0) -> float | None:
    """FPS a partir das linhas CSV do PresentMon (v1 ou v2)."""
    tempos = []
    for l in linhas:
        for chave, valor in l.items():
            k = (chave or "").lower().replace(" ", "")
            if "betweenpresents" in k or k in ("frametime", "msbetweendisplaychange"):
                try:
                    tempos.append(float(valor))
                except (TypeError, ValueError):
                    pass
                break
    if not tempos:
        return None
    soma, n = 0.0, 0
    for t in reversed(tempos):
        if t <= 0:
            continue
        soma += t
        n += 1
        if soma >= janela_ms:
            break
    return round(1000.0 * n / soma, 0) if soma > 0 else None


def _leitor_presentmon(exe: str):
    while _overlay is not None:
        pid = _pid_da_frente()
        if not pid or pid == _fps.get("pid"):
            time.sleep(2)
            continue
        if _fps.get("proc"):
            try:
                _fps["proc"].terminate()
            except Exception:
                pass
        _fps["pid"] = pid
        try:
            proc = subprocess.Popen([exe, "--process_id", str(pid), "--output_stdout",
                                     "--stop_existing_session", "--session_name", "jarvis_fps"],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, **CNW)
        except Exception as e:
            print(f"[ModoJogo] PresentMon não iniciou: {e}")
            return
        _fps["proc"] = proc
        cabecalho, buffer = None, []
        for linha in proc.stdout:
            if _overlay is None or _fps.get("pid") != pid:
                break
            if cabecalho is None:
                cabecalho = next(csv.reader(io.StringIO(linha)))
                continue
            valores = next(csv.reader(io.StringIO(linha)))
            buffer.append(dict(zip(cabecalho, valores)))
            buffer = buffer[-400:]
            _fps["valor"] = fps_de_linhas(buffer)
        time.sleep(1)


# ── overlay (Qt, criado na thread da interface) ────────────────────────────────
def _criar_overlay(posicao: str):
    global _overlay
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QGuiApplication
    from PyQt6.QtWidgets import QLabel

    from core import telemetria

    lbl = QLabel()
    lbl.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                       | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    lbl.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    lbl.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
    lbl.setStyleSheet("QLabel { color: #00ff88; background: rgba(0, 0, 0, 150); "
                      "border: 1px solid rgba(0, 212, 255, 120); border-radius: 4px; padding: 4px 8px; }")
    tel = telemetria.get()

    def atualizar():
        s = tel.snapshot()
        g = s.get("gpu") or {}
        partes = []
        if _fps.get("valor"):
            partes.append(f"FPS {int(_fps['valor'])}")
        partes.append(f"CPU {s['cpu']:.0f}%")
        if g:
            partes.append(f"GPU {g.get('uso', 0):.0f}%" + (f" {g['temp']:.0f}°" if g.get("temp") else ""))
        partes.append(f"RAM {s['ram'].get('pct', 0):.0f}%")
        if s.get("cpu_temp"):
            partes.append(f"{s['cpu_temp']:.0f}°C")
        lbl.setText("  ".join(partes))
        lbl.adjustSize()
        tela = QGuiApplication.primaryScreen().availableGeometry()
        x = tela.left() + 10 if "esquerdo" in posicao else tela.right() - lbl.width() - 10
        y = tela.top() + 10 if "superior" in posicao else tela.bottom() - lbl.height() - 10
        lbl.move(x, y)

    timer = QTimer(lbl)
    timer.timeout.connect(atualizar)
    timer.start(1000)
    atualizar()
    lbl.show()
    _overlay = lbl


def _fechar_overlay():
    global _overlay
    if _overlay is not None:
        try:
            _overlay.close()
            _overlay.deleteLater()
        except Exception:
            pass
    _overlay = None
    if _fps.get("proc"):
        try:
            _fps["proc"].terminate()
        except Exception:
            pass
    _fps.update({"valor": None, "proc": None, "pid": None})


def mostrar_overlay(ligar: bool) -> str:
    from core import qt_bridge
    if not qt_bridge.disponivel():
        return "O overlay precisa da interface aberta."
    if not ligar:
        qt_bridge.na_interface(_fechar_overlay)
        return "Overlay fechado."
    if _overlay is not None:
        return "O overlay já está na tela."
    c = _cfg()
    qt_bridge.na_interface(lambda: _criar_overlay(str(c.get("posicao") or "superior direito")))
    exe = str(c.get("presentmon") or "").strip()
    if exe and Path(exe).exists() and WIN:
        def iniciar_leitor():
            time.sleep(1.5)                  # espera o overlay existir
            _leitor_presentmon(exe)
        threading.Thread(target=iniciar_leitor, daemon=True, name="presentmon").start()
        return "Overlay ligado, com FPS pelo PresentMon."
    return "Overlay ligado (FPS aparece se você configurar o PresentMon)."


# ── ligar / desligar ───────────────────────────────────────────────────────────
def ligar(player) -> str:
    estado = ler_json(_ESTADO, {}) or {}
    if estado.get("ativo"):
        return "O modo jogo já está ligado."
    c = _cfg()
    novo = {"ativo": True, "inicio": time.time(), "exes": [], "plano_anterior": "",
            "toasts_antes": None}
    partes = []
    fechados, exes = _fechar(lista_fechar(c))
    novo["exes"] = exes if sim(c.get("reabrir")) else []
    if fechados:
        partes.append("fechei " + ", ".join(n.rsplit(".", 1)[0] for n in fechados))
    if sim(c.get("alto_desempenho")):
        from plugins.controle_sistema import definir_plano
        ok, msg, anterior = definir_plano("alto desempenho")
        if ok:
            novo["plano_anterior"] = anterior
            partes.append("plano de energia em alto desempenho")
        else:
            registrar(player, f"Modo jogo: plano de energia — {msg}")
    if sim(c.get("pausar_notificacoes")):
        antes = _toasts(False)
        if antes is not None:
            novo["toasts_antes"] = antes
            partes.append("notificações pausadas")
    gravar_json(_ESTADO, novo)
    if sim(c.get("overlay")):
        r = mostrar_overlay(True)
        if r.startswith("Overlay ligado"):
            partes.append("overlay na tela")
    return "Modo jogo ligado: " + (", ".join(partes) if partes else "nada precisou mudar") + ". Bom jogo!"


def desligar(player) -> str:
    estado = ler_json(_ESTADO, {}) or {}
    mostrar_overlay(False)
    if not estado.get("ativo"):
        return "O modo jogo não estava ligado."
    partes = []
    if estado.get("plano_anterior"):
        from plugins._comum import rodar
        if WIN:
            rodar(["powercfg", "/setactive", estado["plano_anterior"]])
        else:
            rodar(["powerprofilesctl", "set", estado["plano_anterior"]])
        partes.append("plano de energia de volta")
    if estado.get("toasts_antes") is not None:
        _toasts(bool(estado["toasts_antes"]))
        partes.append("notificações de volta")
    reabertos = [Path(e).stem for e in estado.get("exes", []) if Path(e).exists() and iniciar([e])]
    if reabertos:
        partes.append("reabri " + ", ".join(reabertos))
    minutos = int((time.time() - estado.get("inicio", time.time())) / 60)
    gravar_json(_ESTADO, {"ativo": False})
    return f"Modo normal. {', '.join(partes).capitalize() or 'Tudo como antes'}. Você jogou {minutos} minutos."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "ligar").strip().lower()
    try:
        if a in ("ligar", "ativar", "on"):
            return ligar(player)
        if a in ("desligar", "normal", "off"):
            return desligar(player)
        if a == "status":
            e = ler_json(_ESTADO, {}) or {}
            if not e.get("ativo"):
                return "Modo jogo desligado."
            return f"Modo jogo ligado há {int((time.time() - e['inicio']) / 60)} minutos."
        if a == "overlay":
            return mostrar_overlay(True if p.get("ligar") in (None, "") else sim(p.get("ligar")))
        return "Use ligar, desligar, status ou overlay."
    except Exception as e:
        return f"O modo jogo falhou: {e}"
