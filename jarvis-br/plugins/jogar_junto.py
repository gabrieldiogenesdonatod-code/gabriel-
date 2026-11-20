"""
Jogar junto — Roblox, Minecraft e outros (fork PT-BR 2.16).

O JARVIS vira seu parceiro de jogo de três jeitos:

  COPILOTO (ele olha e fala)
    "Jarvis, joga Roblox comigo"          → a cada ~20 s olha a tela do jogo e comenta
                                            ou avisa: "tem um obstáculo vermelho à frente",
                                            "a vida está baixa", "o portal é à direita"
    "Jarvis, o que eu faço agora?"        → olha agora e dá a dica

  CONTROLE POR VOZ (você manda, ele aperta)
    "Jarvis, pula" · "anda pra frente 3 segundos" · "vira à direita" · "corre"
    "Jarvis, pula 5 vezes" · "aperta E" · "usa o item 2" · "ataca"
    "Jarvis, escreve no chat: gg pessoal"

  PILOTO AUTOMÁTICO CURTO (ele joga um pouco sozinho)
    "Jarvis, segue em frente e desvia dos obstáculos por 30 segundos"
    "Jarvis, tenta passar essa parte do obby"
        → olha a tela, decide (andar, pular, virar), aperta, olha de novo…
          Máximo 2 minutos por vez. Para na hora com "Jarvis, para" ou Ctrl+Alt+X.

REGRAS DE SEGURANÇA
  • Só aperta teclas com a janela do JOGO na frente; se você trocar de janela,
    ele solta tudo e para.
  • Nada de farm/AFK: o piloto automático dura no máximo 2 minutos e precisa de
    você ali. Isso respeita as regras do Roblox e de outros jogos online, que
    proíbem bots jogando sozinhos. Não usa nem injeta nada no jogo: só aperta
    teclas como um teclado, e só olha a tela.
  • O piloto automático e o copiloto precisam da chave do Gemini (visão).
    O controle por voz funciona sem IA.

As teclas de cada jogo ficam em PERFIS (Roblox, Minecraft e um padrão WASD).
"""

from __future__ import annotations

import json
import platform
import re
import threading
import time
import unicodedata

from plugins._comum import falar, registrar

PLUGIN = {
    "name": "jogar_junto",
    "brief": "Play games WITH the user (Roblox, Minecraft…): watch and give callouts, press keys on voice command, short autopilot.",
    "description": (
        "Play-together mode. action='copiloto' (valor ligar/desligar, optional jogo) watches the game screen and gives "
        "short callouts/tips every ~20 s. action='dica' looks now and says what to do. action='acao' with comando = the "
        "user's words ('pula', 'anda pra frente 3 segundos', 'vira à direita', 'corre', 'pula 5 vezes', 'aperta E', 'usa "
        "o item 2', 'ataca', 'escreve no chat: texto') presses the keys in the game. action='sozinho' with objetivo and "
        "optional segundos (max 120) plays a short autopilot watching the screen. action='parar' stops everything. "
        "Only works with the game window in front."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "copiloto | dica | acao | sozinho | parar"},
                       "comando": {"type": "STRING"}, "objetivo": {"type": "STRING"}, "segundos": {"type": "NUMBER"},
                       "valor": {"type": "STRING"}, "jogo": {"type": "STRING"}},
        "required": ["action"],
    },
}

WIN = platform.system() == "Windows"
MAX_SOZINHO_S = 120

PERFIS = {
    "roblox": {"frente": "w", "tras": "s", "esquerda": "a", "direita": "d", "pular": "space", "correr": "shift",
               "agachar": "c", "interagir": "e", "virar_esquerda": "left", "virar_direita": "right", "chat": "/",
               "atacar": "clique", "processo": ("robloxplayerbeta", "roblox")},
    "minecraft": {"frente": "w", "tras": "s", "esquerda": "a", "direita": "d", "pular": "space", "correr": "ctrl",
                  "agachar": "shift", "interagir": "clique_direito", "virar_esquerda": "mouse_esquerda",
                  "virar_direita": "mouse_direita", "chat": "t", "atacar": "clique",
                  "processo": ("javaw", "minecraft")},
    "padrao": {"frente": "w", "tras": "s", "esquerda": "a", "direita": "d", "pular": "space", "correr": "shift",
               "agachar": "ctrl", "interagir": "e", "virar_esquerda": "mouse_esquerda", "virar_direita": "mouse_direita",
               "chat": "enter", "atacar": "clique", "processo": ()},
}

_estado = {"copiloto": False, "sozinho": False, "parar": threading.Event(), "jogo": "padrao", "janela": None,
           "apertadas": set(), "dicas": []}


def _n(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


# ── teclado e mouse (SendInput com scan codes: funciona em jogos DirectX) ──────
_SCAN = {"w": 0x11, "a": 0x1E, "s": 0x1F, "d": 0x20, "e": 0x12, "q": 0x10, "r": 0x13, "f": 0x21, "c": 0x2E,
         "t": 0x14, "space": 0x39, "shift": 0x2A, "ctrl": 0x1D, "enter": 0x1C, "esc": 0x01, "tab": 0x0F,
         "/": 0x35, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07, "7": 0x08, "8": 0x09,
         "9": 0x0A, "0": 0x0B, "left": 0x4B, "right": 0x4D, "up": 0x48, "down": 0x50}
_EXTENDIDAS = {"left", "right", "up", "down"}


def _send(tecla: str, soltar: bool) -> None:
    if not WIN:
        import pyautogui
        (pyautogui.keyUp if soltar else pyautogui.keyDown)(tecla)
        return
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    flags = 0x0008 | (0x0002 if soltar else 0) | (0x0001 if tecla in _EXTENDIDAS else 0)   # SCANCODE, KEYUP, EXTENDED
    i = INPUT(type=1)
    i.ki = KEYBDINPUT(0, _SCAN[tecla], flags, 0, 0)
    ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))


def _mouse(acao: str, dx: int = 0) -> None:
    if not WIN:
        import pyautogui
        if acao == "mover":
            pyautogui.moveRel(dx, 0)
        else:
            pyautogui.click(button="right" if acao == "direito" else "left")
        return
    import ctypes
    u = ctypes.windll.user32
    if acao == "mover":
        u.mouse_event(0x0001, dx, 0, 0, 0)                     # MOUSEEVENTF_MOVE (relativo)
    else:
        baixo, cima = (0x0008, 0x0010) if acao == "direito" else (0x0002, 0x0004)
        u.mouse_event(baixo, 0, 0, 0, 0)
        time.sleep(0.05)
        u.mouse_event(cima, 0, 0, 0, 0)


def _janela() -> dict | None:
    try:
        from plugins import olha_isso
        return olha_isso.janela_alvo()
    except Exception:
        return None


def jogo_da_janela(j: dict | None) -> str:
    """Qual perfil usar pela janela em foco (pura)."""
    if not j:
        return "padrao"
    alvo = _n(f"{j.get('processo', '')} {j.get('titulo', '')}")
    for nome, perfil in PERFIS.items():
        if any(p in alvo for p in perfil.get("processo", ())):
            return nome
    return "padrao"


def _jogo_na_frente() -> bool:
    j = _janela()
    if not j:
        return False
    alvo = _n(f"{j.get('processo', '')} {j.get('titulo', '')}")
    if any(x in alvo for x in ("jarvis", "python", "explorer", "code", "chrome", "edge", "firefox", "discord")):
        return jogo_da_janela(j) != "padrao"
    return True


def soltar_tudo() -> None:
    for t in list(_estado["apertadas"]):
        try:
            _send(t, True)
        except Exception:
            pass
    _estado["apertadas"].clear()


def segurar(tecla: str, segundos: float) -> None:
    if tecla in ("clique", "clique_direito"):
        _mouse("direito" if tecla == "clique_direito" else "esquerdo")
        return
    if tecla in ("mouse_esquerda", "mouse_direita"):
        passos = max(1, int(segundos * 20))
        for _ in range(passos):
            if _estado["parar"].is_set():
                return
            _mouse("mover", -25 if tecla == "mouse_esquerda" else 25)
            time.sleep(0.02)
        return
    _send(tecla, False)
    _estado["apertadas"].add(tecla)
    fim = time.time() + segundos
    try:
        while time.time() < fim:
            if _estado["parar"].is_set() or not _jogo_na_frente():
                break
            time.sleep(0.03)
    finally:
        _send(tecla, True)
        _estado["apertadas"].discard(tecla)


# ── interpretar comandos ──────────────────────────────────────────────────────
_NUM = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
        "nove": 9, "dez": 10, "meio": 0.5}


def _numero(t: str, padrao: float) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)", t)
    if m:
        return float(m.group(1).replace(",", "."))
    for k, v in _NUM.items():
        if re.search(rf"\b{k}\b", t):
            return v
    return padrao


def interpretar(comando: str, perfil: dict) -> list[tuple]:
    """'anda pra frente 3 segundos e pula' → [('segurar','w',3), ('tocar','space',1)] (pura).
    Passos: ('segurar', tecla, s) · ('tocar', tecla, vezes) · ('chat', texto) · ('juntos', [teclas], s)."""
    original = str(comando or "")
    m = re.search(r"(?:escreve|digita|fala|manda)\s+no\s+chat[:,]?\s*(.+)$", original, re.I)
    if m:
        return [("chat", m.group(1).strip())]
    passos = []
    for parte in re.split(r"\s+e\s+(?:depois\s+)?|,\s*|\s+depois\s+", _n(original)):
        t = parte.strip()
        if not t:
            continue
        seg = _numero(t, 1.0) if re.search(r"seg|s\b", t) else None
        vezes = int(_numero(t, 1)) if re.search(r"vez|vezes", t) else 1
        if re.search(r"\bpul|\bsalt", t):
            if "frente" in t or "correndo" in t:
                passos.append(("juntos", [perfil["frente"], perfil["pular"]], seg or 1.0))
            else:
                passos.append(("tocar", perfil["pular"], vezes))
        elif re.search(r"corr", t):
            passos.append(("juntos", [perfil["correr"], perfil["frente"]], seg or 2.0))
        elif re.search(r"vira|gira", t):
            lado = "virar_esquerda" if "esquer" in t else "virar_direita"
            passos.append(("segurar", perfil[lado], seg or (0.5 if "pouco" in t else 0.8)))
        elif re.search(r"\b(anda|vai|segue|ande|va|move)", t) or any(w in t for w in ("frente", "tras", "esquerda", "direita")):
            lado = "tras" if re.search(r"tras|volta|re\b", t) else "esquerda" if "esquer" in t else \
                "direita" if "direit" in t else "frente"
            passos.append(("segurar", perfil[lado], seg or 1.5))
        elif re.search(r"agach|abaix", t):
            passos.append(("segurar", perfil["agachar"], seg or 1.0))
        elif re.search(r"atac|bate|soca|clica|acerta", t):
            passos.append(("tocar", perfil["atacar"], vezes if vezes > 1 else int(_numero(t, 1))))
        elif re.search(r"\b(item|slot|arma|ferramenta)\b", t):
            n = int(_numero(t, 1)) % 10
            passos.append(("tocar", str(n), 1))
        elif m2 := re.search(r"aperta\s+(?:o\s+|a\s+)?([a-z0-9]|espaco|enter|shift|esc)\b", t):
            tecla = {"espaco": "space"}.get(m2.group(1), m2.group(1))
            if tecla in _SCAN:
                passos.append(("tocar", tecla, vezes))
        elif re.search(r"interag|pega|abre|usa\b", t):
            passos.append(("tocar", perfil["interagir"], 1))
    return passos


def executar(passos: list[tuple], perfil: dict) -> str:
    if not _jogo_na_frente():
        return "Deixe a janela do jogo na frente e me peça de novo (eu só aperto teclas no jogo)."
    _estado["parar"].clear()
    feitos = 0
    for p in passos:
        if _estado["parar"].is_set():
            break
        if p[0] == "segurar":
            segurar(p[1], min(10.0, float(p[2])))
        elif p[0] == "tocar":
            for _ in range(max(1, min(20, int(p[2])))):
                segurar(p[1], 0.08)
                time.sleep(0.12 if p[1] == perfil["pular"] else 0.05)
        elif p[0] == "juntos":
            ths = [threading.Thread(target=segurar, args=(k, min(10.0, float(p[2]))), daemon=True) for k in p[1]]
            for th in ths:
                th.start()
                time.sleep(0.05)
            for th in ths:
                th.join()
        elif p[0] == "chat":
            import pyperclip
            segurar(perfil["chat"], 0.06)
            time.sleep(0.25)
            pyperclip.copy(p[1][:120])
            _send("ctrl", False)
            import pyautogui
            pyautogui.press("v")
            _send("ctrl", True)
            time.sleep(0.1)
            segurar("enter", 0.06)
        feitos += 1
    soltar_tudo()
    return "Feito." if feitos == len(passos) else "Parei."


# ── visão ─────────────────────────────────────────────────────────────────────
def _ver(prompt: str, largura: int = 900) -> str:
    from plugins import _ia, olha_isso
    j = _janela()
    if not j or not _ia.disponivel():
        return ""
    img = olha_isso.capturar(j, largura)
    if not img:
        return ""
    from google.genai import types as gtypes

    from core import gemini
    resp = gemini.call([gtypes.Part.from_bytes(data=img[0], mime_type=img[1]), prompt], tier=gemini.FAST,
                       timeout_ms=20_000)
    return (getattr(resp, "text", "") or "").strip() if resp is not None else ""


def decisao(texto: str) -> dict | None:
    """Resposta da IA → {'acao', 'segundos', 'fala'} validada (pura)."""
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    validas = {"frente", "tras", "esquerda", "direita", "pular", "pular_frente", "virar_esquerda", "virar_direita",
               "correr", "interagir", "atacar", "esperar", "concluido"}
    acao = str(d.get("acao") or "").lower()
    if acao not in validas:
        return None
    return {"acao": acao, "segundos": max(0.1, min(3.0, float(d.get("segundos") or 0.6))),
            "fala": str(d.get("fala") or "")[:120]}


def _passo_da_decisao(d: dict, perfil: dict) -> list[tuple]:
    a, s = d["acao"], d["segundos"]
    if a == "pular":
        return [("tocar", perfil["pular"], 1)]
    if a == "pular_frente":
        return [("juntos", [perfil["frente"], perfil["pular"]], s)]
    if a == "correr":
        return [("juntos", [perfil["correr"], perfil["frente"]], s)]
    if a in ("interagir", "atacar"):
        return [("tocar", perfil[a], 1)]
    if a in perfil:
        return [("segurar", perfil[a], s)]
    return []


def _sozinho(objetivo: str, segundos: float, player) -> None:
    perfil = PERFIS[_estado["jogo"]]
    fim = time.time() + min(MAX_SOZINHO_S, segundos)
    historico: list[str] = []
    try:
        while time.time() < fim and not _estado["parar"].is_set():
            if not _jogo_na_frente():
                registrar(player, "Jogar junto: a janela do jogo saiu da frente; parei.")
                break
            r = _ver(f"Você está jogando {_estado['jogo']} pelo jogador, por poucos segundos. Objetivo: {objetivo}. "
                     f"Últimas ações: {', '.join(historico[-5:]) or 'nenhuma'}. Olhe a tela e escolha a PRÓXIMA ação. "
                     "Responda SÓ JSON: {\"acao\": \"frente|tras|esquerda|direita|pular|pular_frente|virar_esquerda|"
                     "virar_direita|correr|interagir|atacar|esperar|concluido\", \"segundos\": 0.2-3, \"fala\": "
                     "\"comentário curto opcional\"}", 768)
            d = decisao(r)
            if not d:
                time.sleep(0.5)
                continue
            if d["fala"]:
                try:
                    from plugins import _rosto_ui
                    _rosto_ui.frase(player, "Jogando", d["fala"])
                except Exception:
                    pass
            if d["acao"] == "concluido":
                falar(player, f"[JOGO] Diga em uma frase curta que você conseguiu: {objetivo}.")
                break
            if d["acao"] == "esperar":
                time.sleep(d["segundos"])
            else:
                executar(_passo_da_decisao(d, perfil), perfil)
            historico.append(f"{d['acao']} {d['segundos']:.1f}s")
    finally:
        soltar_tudo()
        _estado["sozinho"] = False
        registrar(player, "Jogar junto: piloto automático terminou.")


def _copiloto(player) -> None:
    ultima = ""
    while _estado["copiloto"] and not _estado["parar"].is_set():
        time.sleep(20)
        if not _estado["copiloto"] or _estado["sozinho"] or not _jogo_na_frente():
            continue
        try:
            r = _ver(f"Você é o JARVIS assistindo o senhor jogar {_estado['jogo']}, como um amigo do lado. Olhando a "
                     "tela, dê UMA dica ou aviso útil e curto (até 15 palavras) — perigo, objetivo, item, caminho — ou "
                     "um comentário divertido se nada importante. Se nada vale falar, responda só: -. Última fala sua: "
                     f"{ultima or 'nenhuma'} (não repita).")
            if r and r.strip() not in ("-", "—") and r != ultima:
                ultima = r
                _estado["dicas"].append(r)
                from plugins import _rosto_ui
                _rosto_ui.frase(player, "Jogo", r)
        except Exception as e:
            print(f"[Jogar junto] {e}")


def parar() -> str:
    _estado["parar"].set()
    _estado["copiloto"] = False
    soltar_tudo()
    return "Parei de jogar. Soltei todas as teclas."


def on_session_start(player) -> None:
    try:
        from plugins import _atalhos_globais
        _atalhos_globais.registrar("ctrl+alt+x", parar)        # parada de emergência
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = _n(p.get("action") or "acao")
    j = _janela()
    _estado["jogo"] = _n(p.get("jogo")) if _n(p.get("jogo")) in PERFIS else jogo_da_janela(j)
    perfil = PERFIS[_estado["jogo"]]
    try:
        if a == "parar":
            return parar()
        if a == "acao":
            passos = interpretar(str(p.get("comando") or ""), perfil)
            if not passos:
                return "Não entendi o movimento. Ex.: 'pula', 'anda pra frente 2 segundos', 'vira à direita'."
            return executar(passos, perfil)
        if a == "copiloto":
            if _n(p.get("valor") or "ligar").startswith(("deslig", "para", "off")):
                _estado["copiloto"] = False
                return "Copiloto desligado."
            _estado["parar"].clear()
            if not _estado["copiloto"]:
                _estado["copiloto"] = True
                threading.Thread(target=_copiloto, args=(player,), daemon=True, name="jogar_copiloto").start()
            return (f"Bora jogar {_estado['jogo'] if _estado['jogo'] != 'padrao' else 'junto'}! Vou olhando a tela e "
                    "dando dicas. Pode me mandar pular, andar ou virar quando quiser. 'Jarvis, para' ou Ctrl+Alt+X para tudo.")
        if a == "dica":
            r = _ver(f"O senhor está jogando {_estado['jogo']} e pediu ajuda: o que ele deve fazer agora? Olhe a tela e "
                     "responda em até 2 frases práticas.")
            return r or "Não consegui olhar a tela do jogo agora (preciso da chave do Gemini e do jogo na frente)."
        if a == "sozinho":
            objetivo = str(p.get("objetivo") or "seguir em frente sem cair").strip()
            if _estado["sozinho"]:
                return "Já estou jogando; diga 'para' para eu parar."
            from plugins import _ia
            if not _ia.disponivel():
                return "Para jogar sozinho eu preciso enxergar a tela (chave do Gemini)."
            if not _jogo_na_frente():
                return "Deixe a janela do jogo na frente e me peça de novo."
            seg = min(MAX_SOZINHO_S, float(p.get("segundos") or 30))
            _estado["parar"].clear()
            _estado["sozinho"] = True
            threading.Thread(target=_sozinho, args=(objetivo, seg, player), daemon=True, name="jogar_sozinho").start()
            return (f"Assumindo por até {int(seg)} segundos: {objetivo}. Solte o teclado; 'Jarvis, para' ou "
                    "Ctrl+Alt+X me para na hora.")
        return "Use copiloto, dica, acao, sozinho ou parar."
    except Exception as e:
        soltar_tudo()
        return f"Jogar junto falhou: {e}"
