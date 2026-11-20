"""
Sequência de boot cinematográfica (fork PT-BR 1.4).

Quando o JARVIS abre:
    1. som de inicialização (gerado pelo próprio JARVIS — sem arquivo de
       terceiros: zumbido subindo, três bipes e um acorde);
    2. "diagnóstico do traje" escrito linha a linha no registro: núcleo,
       sensores (CPU, RAM, GPU), rede, armadura (nota do saude_pc), protocolos
       e plugins carregados;
    3. saudação falada que muda com o horário e o clima ("Bom dia, senhor.
       Todos os sistemas operacionais; 24 graus e céu limpo em Goiânia.").

Se o resumo matinal já vai falar, o boot fica só no som e nas linhas, para
não falar duas vezes (configurável). Também dá para rodar de novo:

    "Jarvis, roda a sequência de boot"     (bom para gravar vídeo)
"""

from __future__ import annotations

import math
import struct
import threading
import time
import wave
from datetime import datetime

from plugins._comum import MEMORIA, WIN, cfg, falar, registrar

PLUGIN = {
    "name": "boot_cinematico",
    "brief": "Cinematic startup sequence: sound, suit diagnostics, greeting by time and weather.",
    "description": (
        "Cinematic boot sequence (startup sound, 'suit diagnostics' lines with the PC health score, "
        "greeting by time of day and weather). Runs automatically at startup; action='rodar' replays it "
        "on request ('run the boot sequence', 'diagnóstico do traje')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "rodar"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "boot_cinematico",
    "title": "Boot cinematográfico",
    "fields": [
        {"key": "ligado", "label": "Rodar ao abrir o JARVIS", "type": "toggle", "default": True},
        {"key": "som", "label": "Tocar o som de inicialização", "type": "toggle", "default": True},
        {"key": "falar", "label": "Saudação falada", "type": "choice",
         "choices": ["só sem o resumo matinal", "sempre", "nunca"], "default": "só sem o resumo matinal"},
    ],
}

_SOM = MEMORIA / "boot_jarvis.wav"
_rodou = threading.Event()


# ── som (sintetizado) ──────────────────────────────────────────────────────────
def gerar_som(caminho=_SOM, taxa: int = 22050) -> str:
    amostras = []

    def tom(freqs, dur, vol=0.3, ataque=0.02, queda=0.3, deslize=None):
        n = int(dur * taxa)
        for i in range(n):
            t = i / taxa
            env = min(1.0, t / ataque) * (1.0 if t < dur - queda else max(0.0, (dur - t) / queda))
            v = 0.0
            for k, f in enumerate(freqs):
                f_atual = f + (deslize * t / dur if deslize else 0)
                v += math.sin(2 * math.pi * f_atual * t) / (k + 1)
            amostras.append(vol * env * v / max(1, len(freqs)) * 1.6)

    tom([70, 140, 210], 1.3, vol=0.35, ataque=0.6, queda=0.25, deslize=180)    # núcleo subindo
    for f in (1200, 1500, 1800):                                                # bipes
        tom([f], 0.07, vol=0.18, ataque=0.005, queda=0.03)
        amostras.extend([0.0] * int(0.06 * taxa))
    tom([440, 554.37, 659.25, 880], 1.6, vol=0.3, ataque=0.05, queda=1.2)        # acorde (lá maior)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, a)) * 32000)) for a in amostras))
    return str(caminho)


def tocar_som() -> bool:
    if not WIN:
        return False
    try:
        import winsound
        if not _SOM.exists():
            gerar_som()
        winsound.PlaySound(str(_SOM), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
    except Exception as e:
        print(f"[Boot] som: {e}")
        return False


# ── diagnóstico ────────────────────────────────────────────────────────────────
def saudacao(hora: int) -> str:
    return "Bom dia" if 5 <= hora < 12 else "Boa tarde" if 12 <= hora < 18 else "Boa noite"


def diagnostico() -> list[tuple[str, str]]:
    linhas = []
    try:
        from core import telemetria
        s = telemetria.get().snapshot()
        ram = (s.get("ram") or {}).get("pct")
        g = s.get("gpu") if isinstance(s.get("gpu"), dict) else {}
        gpu = next((g[k] for k in ("uso", "util", "pct", "carga") if isinstance(g.get(k), (int, float))), None)
        linhas.append(("SENSORES", f"CPU {s.get('cpu') or 0:.0f}% · RAM {ram or 0:.0f}%"
                                   + (f" · GPU {gpu:.0f}%" if gpu is not None else "")))
        pings = [v.get("ms") for k, v in (s.get("ping") or {}).items()
                 if k != "gateway" and isinstance(v, dict) and v.get("ms") is not None]
        net = s.get("internet")
        linhas.append(("REDE", ("online" + (f", ping {min(pings):.0f} ms" if pings else "")) if net is not False
                       else "SEM INTERNET"))
    except Exception:
        linhas.append(("SENSORES", "telemetria indisponível"))
    try:
        from plugins import saude_pc
        nota, probs = saude_pc.calcular_nota(saude_pc.coletar())
        linhas.append(("ARMADURA", f"{nota}/100 — {saude_pc.conceito(nota)}"
                       + (f"; atenção: {probs[0].get('titulo', '')}" if probs else "")))
    except Exception as e:
        linhas.append(("ARMADURA", f"diagnóstico indisponível ({e})"))
    n, oque = pendencias()                                    # 1.6: o que está esperando por você
    linhas.append(("PENDÊNCIAS", f"{n} — {', '.join(oque)}" if n else "nenhuma"))
    try:
        from plugins import protocolos
        from core import registro_ferramentas
        linhas.append(("PROTOCOLOS", f"{len(protocolos._load())} carregados · {len(registro_ferramentas.disponiveis())} ferramentas"))
    except Exception:
        pass
    return linhas


def pendencias() -> tuple[int, list[str]]:
    """Fork PT-BR 1.6: tarefas abertas, aniversários, cápsulas do tempo e cuidados de hoje."""
    total, partes = 0, []

    def somar(qtd, rotulo):
        nonlocal total
        if qtd:
            total += qtd
            partes.append(f"{qtd} {rotulo}")
    try:
        from plugins import prioridades
        somar(sum(1 for t in prioridades.carregar()["tarefas"] if t.get("status") != "feita"), "tarefa(s)")
    except Exception:
        pass
    for modulo, funcao, rotulo in (("aniversarios", "de_hoje", "aniversário(s) hoje"),
                                   ("capsula_tempo", "para_hoje", "cápsula(s) do tempo"),
                                   ("cuidador", "pendentes_hoje", "cuidado(s) do dia")):
        try:
            mod = __import__(f"plugins.{modulo}", fromlist=[funcao])
            somar(len(getattr(mod, funcao)()), rotulo)
        except Exception:
            pass
    return total, partes


def _clima() -> str:
    resultado = {}

    def ler():
        try:
            from plugins import briefing_br
            resultado["c"] = briefing_br.clima()
        except Exception:
            resultado["c"] = ""
    t = threading.Thread(target=ler, daemon=True)
    t.start()
    t.join(8)
    return resultado.get("c") or ""


def rodar(player, automatico: bool = True) -> str:
    c = cfg("boot_cinematico", PLUGIN_SETTINGS)
    if str(c.get("som", True)).lower() not in ("false", "0", "nao", "não"):
        tocar_som()
    registrar(player, "BOOT: J.A.R.V.I.S BR — inicializando núcleo…")
    time.sleep(0.9)
    linhas = diagnostico()
    for rotulo, texto in linhas:
        registrar(player, f"BOOT: {rotulo:<10} {texto}")
        time.sleep(0.45)
    registrar(player, "BOOT: Todos os sistemas operacionais.")
    modo = str(c.get("falar") or "só sem o resumo matinal")
    if modo == "nunca":
        return "Boot concluído."
    if automatico and modo.startswith("só"):
        try:
            from memory.config_manager import get_brief_enabled
            if get_brief_enabled():
                return "Boot concluído (o resumo matinal faz a saudação)."
        except Exception:
            pass
    clima = _clima()
    armadura = next((t for r, t in linhas if r == "ARMADURA"), "")
    rede = next((t for r, t in linhas if r == "REDE"), "")
    pend = next((t for r, t in linhas if r == "PENDÊNCIAS"), "")
    falar(player, "[BOOT] Você acabou de ser ligado. Faça a saudação de inicialização no estilo J.A.R.V.I.S, "
                  f"em até 4 frases curtas, como um sistema que acabou de subir ('sistemas online…'), no idioma da conversa: '{saudacao(datetime.now().hour)}', diga que o "
                  f"diagnóstico do traje terminou ({armadura or 'sistemas ok'}), rede: "
                  f"{'estável' if rede.startswith('online') else rede or 'sem leitura'}, pendências: {pend or 'nenhuma'}"
                  + (f", e comente o clima: {clima}" if clima else "")
                  + ". Termine dizendo que está à disposição. Não chame nenhuma ferramenta.")
    return "Boot concluído."


def on_session_start(player) -> None:
    if _rodou.is_set():
        return
    _rodou.set()
    c = cfg("boot_cinematico", PLUGIN_SETTINGS)
    if str(c.get("ligado", True)).lower() in ("false", "0", "nao", "não"):
        return
    time.sleep(1.5)
    try:
        rodar(player, automatico=True)
    except Exception as e:
        print(f"[Boot] {e}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        threading.Thread(target=rodar, args=(player, False), daemon=True).start()
        return "Iniciando a sequência de boot."
    except Exception as e:
        return f"O boot falhou: {e}"
