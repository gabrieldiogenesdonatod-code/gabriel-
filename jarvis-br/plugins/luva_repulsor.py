"""
Luva repulsor (fork PT-BR 2.5) — ESP32 + acelerômetro/giroscópio MPU6050 (+ sensor de flexão opcional).

    "Jarvis, configura a luva"            → IP e CHAVE para o sketch esp32/luva
    "Jarvis, trava a luva" / "destrava a luva"
    "Jarvis, o repulsor passa o slide"    (muda a ação de um gesto)

Você abre a mão com a palma para a frente (a pose do repulsor): toca o som do
repulsor no PC e o JARVIS faz a ação — por padrão, fecha a janela da frente.
Gestos que o sketch manda: repulsor, punho, tapa_direita, tapa_esquerda, cima, baixo.
Cada gesto tem uma ação em ⚙ → Luva repulsor. A janela do próprio JARVIS e os
programas protegidos nunca são fechados.
"""

from __future__ import annotations

import threading
import time

from plugins import _esp32
from plugins._comum import WIN, cfg, registrar, salvar_cfg, sim

ACOES = ["nada", "fechar_janela", "minimizar", "proximo_slide", "slide_anterior", "play_pausa", "proxima_musica",
         "volume_mais", "volume_menos", "print", "chamar_jarvis"]
GESTOS = {"repulsor": "fechar_janela", "punho": "nada", "tapa_direita": "proximo_slide",
          "tapa_esquerda": "slide_anterior", "cima": "volume_mais", "baixo": "volume_menos"}
NOMES_GESTO = {"repulsor": "Repulsor (abrir a mão com a palma para a frente)", "punho": "Fechar a mão",
               "tapa_direita": "Passar a mão para a direita", "tapa_esquerda": "Passar a mão para a esquerda",
               "cima": "Levantar a mão", "baixo": "Abaixar a mão"}

PLUGIN = {
    "name": "luva_repulsor",
    "brief": "Iron Man repulsor glove (ESP32 + MPU6050): gestures play the repulsor sound and run PC actions.",
    "description": (
        "Repulsor glove. action='configurar' gives the PC IP and key for the ESP32 sketch. 'acao' with gesto "
        "(repulsor | punho | tapa_direita | tapa_esquerda | cima | baixo) and valor (one of: " + ", ".join(ACOES) +
        ") changes what a gesture does. 'travar' / 'destravar'. 'testar' with gesto runs it now. 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "configurar | acao | travar | destravar | testar | status"},
            "gesto": {"type": "STRING"}, "valor": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "luva_repulsor",
    "title": "Luva repulsor (ESP32)",
    "fields": [{"key": "ligada", "label": "Luva destravada (obedece aos gestos)", "type": "toggle", "default": True},
               {"key": "som", "label": "Tocar o som do repulsor", "type": "toggle", "default": True}]
    + [{"key": g, "label": NOMES_GESTO[g], "type": "choice", "options": ACOES, "default": a} for g, a in GESTOS.items()],
}

INTERVALO_S = 0.8
_iniciou = threading.Event()
_estado = {"ultimo": 0.0, "som": None, "historico": []}


def _c() -> dict:
    return cfg("luva_repulsor", PLUGIN_SETTINGS)


# ── som do repulsor (gerado, sem arquivo) ─────────────────────────────────────
def som_repulsor(taxa: int = 22050):
    """Carga subindo (0,35 s) + disparo (0,5 s): o 'piuuu-PÁ' do repulsor."""
    import numpy as np

    from plugins import _som
    rng = np.random.default_rng(7)
    t1 = _som.tempo(0.35, taxa)
    f = 300 + 1500 * (t1 / 0.35) ** 2
    carga = np.sin(2 * np.pi * np.cumsum(f) / taxa) * (0.15 + 0.6 * t1 / 0.35)
    carga += 0.08 * _som.filtrar(_som.ruido(0.35, rng, taxa), alta=3000, taxa=taxa)
    t2 = _som.tempo(0.5, taxa)
    queda = np.sin(2 * np.pi * np.cumsum(1400 * np.exp(-t2 * 7) + 120) / taxa) * np.exp(-t2 * 6)
    estouro = _som.filtrar(_som.ruido(0.5, rng, taxa), baixa=2200, taxa=taxa) * np.exp(-t2 * 9)
    baque = np.sin(2 * np.pi * 70 * t2) * np.exp(-t2 * 10)
    x = np.concatenate([carga, 0.7 * queda + 1.2 * estouro + 0.9 * baque])
    return _som.normalizar(x.astype("float32"), 0.85)


def _tocar() -> None:
    try:
        from plugins import _som
        if _estado["som"] is None:
            _estado["som"] = som_repulsor()
        _som.tocar_uma(_estado["som"], 22050, 0.7)
    except Exception as e:
        print(f"[Luva] som: {e}")


# ── ações ─────────────────────────────────────────────────────────────────────
def _tecla_vk(vk: int) -> bool:
    if not WIN:
        return False
    try:
        import ctypes
        u32 = ctypes.windll.user32
        u32.keybd_event(vk, 0, 1, 0)
        u32.keybd_event(vk, 0, 1 | 2, 0)
        return True
    except Exception:
        return False


def _janela_pode_fechar(j: dict | None) -> str:
    """'' se pode; senão o motivo (puro, a não ser o que o _protecao consulta)."""
    if not j:
        return "nenhuma janela na frente"
    titulo = str(j.get("titulo") or "")
    if "J.A.R.V.I.S" in titulo.upper() or "JARVIS" in titulo.upper():
        return "é a janela do JARVIS"
    try:
        from plugins._protecao import eh_protegido, pids_proprios
        if j.get("pid") in pids_proprios() or eh_protegido(nome=str(j.get("processo") or ""),
                                                           pid=j.get("pid") or None):
            return "é um programa protegido"
    except Exception:
        pass
    if str(j.get("processo") or "").lower() in ("explorer.exe", "searchhost.exe", "shellexperiencehost.exe"):
        return "é a área de trabalho/barra do Windows"
    return ""


def executar(acao: str) -> str:
    """Faz a ação e devolve o que aconteceu (para o registro)."""
    if acao == "nada":
        return ""
    if acao in ("fechar_janela", "minimizar"):
        from plugins import _janelas
        j = _janelas.ativa()
        motivo = _janela_pode_fechar(j) if acao == "fechar_janela" else ("" if j else "nenhuma janela na frente")
        if motivo:
            return f"não fechei: {motivo}"
        _janelas.estado(j, "fechar" if acao == "fechar_janela" else "minimizar")
        return f"{'fechei' if acao == 'fechar_janela' else 'minimizei'} {str(j.get('titulo') or '')[:40]}"
    if acao in ("proximo_slide", "slide_anterior", "print"):
        try:
            import pyautogui
            if acao == "print":
                pyautogui.hotkey("win", "printscreen")
            else:
                pyautogui.press("right" if acao == "proximo_slide" else "left")
            return {"proximo_slide": "próximo slide", "slide_anterior": "slide anterior", "print": "print da tela"}[acao]
        except Exception as e:
            return f"falhou ({e})"
    if acao in ("play_pausa", "proxima_musica"):
        from plugins import _midia
        _midia.tecla("play_pause" if acao == "play_pausa" else "proxima")
        return "play/pausa" if acao == "play_pausa" else "próxima música"
    if acao in ("volume_mais", "volume_menos"):
        if not _tecla_vk(0xAF if acao == "volume_mais" else 0xAE):
            try:
                import pyautogui
                pyautogui.press("volumeup" if acao == "volume_mais" else "volumedown")
            except Exception:
                return "volume indisponível"
        return "volume +" if acao == "volume_mais" else "volume -"
    if acao == "chamar_jarvis":
        try:
            from core import registro_ferramentas
            app = registro_ferramentas.app()
            if app is not None and hasattr(app, "wake"):
                app.wake(reason="luva")
        except Exception:
            pass
        return "JARVIS chamado"
    return ""


def receber(corpo: dict, _q: dict | None = None) -> dict:
    gesto = str(corpo.get("gesto") or "").strip().lower()
    if gesto not in GESTOS:
        return {"ok": False, "erro": "gesto desconhecido"}
    c = _c()
    if not sim(c.get("ligada", True)):
        return {"ok": True, "acao": "travada"}
    agora = time.time()
    if agora - _estado["ultimo"] < INTERVALO_S:
        return {"ok": True, "acao": "ignorado (rápido demais)"}
    _estado["ultimo"] = agora
    acao = str(c.get(gesto) or GESTOS[gesto])
    if acao not in ACOES:
        acao = GESTOS[gesto]
    if gesto == "repulsor" and sim(c.get("som", True)):
        threading.Thread(target=_tocar, daemon=True).start()
        time.sleep(0.3)                                       # a ação acontece junto com o "PÁ"
    feito = executar(acao)
    _estado["historico"] = (_estado["historico"] + [(agora, gesto, feito)])[-20:]
    if feito:
        registrar(None, f"Luva: {gesto} → {feito}")
    return {"ok": True, "acao": acao, "feito": feito}


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    _esp32.registrar_rota("POST", "/esp32/luva", receber)
    _esp32.iniciar_se_ligado()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "configurar":
            _esp32.registrar_rota("POST", "/esp32/luva", receber)
            return _esp32.configuracao("luva")
        if acao in ("travar", "destravar"):
            salvar_cfg("luva_repulsor", {"ligada": acao == "destravar"})
            return "Luva travada: ignoro os gestos." if acao == "travar" else "Luva destravada. Repulsores prontos."
        gesto = str(p.get("gesto") or "").strip().lower().replace(" ", "_")
        if acao == "acao":
            nova = str(p.get("valor") or "").strip().lower().replace(" ", "_")
            if gesto not in GESTOS or nova not in ACOES:
                return f"Gestos: {', '.join(GESTOS)}. Ações: {', '.join(ACOES)}."
            salvar_cfg("luva_repulsor", {gesto: nova})
            return f"Pronto: {gesto} agora faz {nova.replace('_', ' ')}."
        if acao == "testar":
            if gesto not in GESTOS:
                gesto = "repulsor"
            _estado["ultimo"] = 0
            r = receber({"gesto": gesto})
            return f"Testei {gesto}: {r.get('feito') or r.get('acao')}."
        c = _c()
        visto = _esp32.visto("luva")
        mapa = "; ".join(f"{g} → {str(c.get(g) or a).replace('_', ' ')}" for g, a in GESTOS.items())
        estado = "destravada" if sim(c.get("ligada", True)) else "travada"
        conexao = f"último gesto às {time.strftime('%H:%M', time.localtime(visto))}" if visto else "ainda não conectou"
        return f"Luva {estado}, {conexao}. Gestos: {mapa}."
    except Exception as e:
        return f"A luva falhou: {e}"
