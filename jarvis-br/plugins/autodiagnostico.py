"""Autodiagnóstico (2.19): o JARVIS confere a si mesmo — plugins que não carregaram, pacotes opcionais faltando e dados."""
from __future__ import annotations

import importlib.util
import platform
import re
import sys

from plugins._comum import BASE, MEMORIA
from plugins._lote2 import P, rodar

PLUGIN = P("autodiagnostico", "JARVIS self-check: plugins that failed to load (and why), missing optional Python packages, data size, versions.",
           "tudo | plugins | pacotes | dados | versao | lentos | fundo",
           "Read-only checks; changes nothing. lentos: slowest tools (last 7 days). fundo: background routines, threads and tools "
           "the anti-freeze watchdog had to hold.", "")

IMPORTA = {"opencv-python": "cv2", "pillow": "PIL", "pyyaml": "yaml", "scikit-learn": "sklearn", "beautifulsoup4": "bs4",
           "python-dotenv": "dotenv", "pyserial": "serial", "python-docx": "docx", "google-genai": "google.genai",
           "pywin32": "win32api", "python-pptx": "pptx", "piper-tts": "piper", "paho-mqtt": "paho", "pyqt6": "PyQt6",
           "pyqt6-webengine": "PyQt6.QtWebEngineWidgets", "python-multipart": "multipart", "pypdf2": "PyPDF2",
           "speechrecognition": "speech_recognition", "pyaudio": "pyaudio", "pynput": "pynput"}


def tem(pacote: str) -> bool:
    nome = IMPORTA.get(pacote.lower(), pacote.lower().replace("-", "_"))
    try:
        return importlib.util.find_spec(nome) is not None
    except Exception:
        return False


def pacotes_faltando(requisitos: str) -> list[str]:
    nomes = [re.split(r"[<>=!~\[; ]", l.split("#")[0].strip())[0] for l in requisitos.splitlines()]
    return sorted({n for n in nomes if n and not n.startswith("-") and not tem(n)})


def _plugins(p, pl):
    from core import registro_ferramentas
    regs = registro_ferramentas._plugins_reg().list_for_ui()
    ruins = [f"{r['name']}: {str(r.get('error'))[:90]}" for r in regs if not r["valid"]]
    return f"{len(regs) - len(ruins)} plugins carregados" + (f"; {len(ruins)} com problema:\n" + "\n".join(ruins) if ruins else ", nenhum com problema.")


def _pacotes(p, pl):
    arq = BASE / "requirements.txt"
    falta = pacotes_faltando(arq.read_text(encoding="utf-8")) if arq.is_file() else []
    return ("Pacotes opcionais que não estão instalados (os plugins que dependem deles avisam quando usados): " +
            ", ".join(falta) + ".") if falta else "Todos os pacotes do requirements.txt estão instalados."


def _dados(p, pl):
    fs = [f for f in MEMORIA.rglob("*") if f.is_file() and f.suffix not in (".py", ".pyc")]
    return f"{len(fs)} arquivo(s) de dados, {sum(f.stat().st_size for f in fs) / 1e6:.1f} MB em {MEMORIA}."


def _versao(p, pl):
    try:
        v = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (BASE / "ui.py").read_text(encoding="utf-8")).group(1)
    except Exception:
        v = "J.A.R.V.I.S BR"
    return f"{v}, Python {sys.version.split()[0]}, {platform.system()} {platform.release()}."


def lentos(chamadas: list[dict], n: int = 8) -> list[tuple[str, float, float, int]]:
    """[(ferramenta, média ms, pior ms, chamadas)] das mais lentas (3+ chamadas). Pura."""
    por: dict[str, list[float]] = {}
    for c in chamadas:
        por.setdefault(c["ferramenta"], []).append(float(c.get("ms") or 0))
    res = [(f, sum(v) / len(v), max(v), len(v)) for f, v in por.items() if len(v) >= 3]
    return sorted(res, key=lambda x: -x[1])[:n]


def _lentos(p, pl):
    import time as _t
    from core import registro_uso
    res = lentos(registro_uso.chamadas(desde=_t.time() - 7 * 86400))
    if not res:
        return "Ainda não tenho chamadas suficientes para medir (preciso de 3+ de cada ferramenta)."
    return "Mais lentas nos últimos 7 dias:\n" + "\n".join(f"{f}: média {m / 1000:.1f} s, pior {x / 1000:.1f} s ({n} chamadas)" for f, m, x, n in res)


def _fundo(p, pl):
    import threading
    from core import relogio, vigia
    rot = relogio.tarefas()
    linhas = [f"{threading.active_count()} threads ativas; relógio central com {len(rot)} rotina(s)."]
    linhas += [f"  {t['nome']}: a cada {t['a_cada_s'] / 60:.0f} min, última levou {t['ultima_ms']:.0f} ms" +
               (f", {t['erros']} erro(s): {t['ultimo_erro']}" if t["erros"] else "") for t in rot]
    linhas.append(f"Vigia de travamento: {vigia.ocupadas()} ferramenta(s) rodando agora; " +
                  (f"{len(vigia.ATRASADAS)} passaram do limite nesta sessão: " +
                   ", ".join(f"{n} ({s:.0f} s)" for _, n, s in vigia.ATRASADAS[-5:]) if vigia.ATRASADAS else "nenhuma passou do limite."))
    return "\n".join(linhas)


def _tudo(p, pl):
    return "\n".join(f(p, pl) for f in (_versao, _plugins, _pacotes, _dados))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"tudo": _tudo, "plugins": _plugins, "pacotes": _pacotes, "dados": _dados, "versao": _versao,
                              "lentos": _lentos, "fundo": _fundo},
                 player, "Autodiagnóstico")
