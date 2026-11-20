"""
Aprender tarefas por demonstração (fork PT-BR 1.5).

    "Jarvis, observa"            → você faz a tarefa uma vez (cliques, teclas)
    F9 ou "Jarvis, pronto"       → ele guarda e pede um nome
    "Jarvis, faz aquilo de novo" / "repete a tarefa nota fiscal"

DIFERENTE DE UMA MACRO COMUM: além das coordenadas, ele guarda
    • em QUAL janela/programa cada clique foi (e foca essa janela antes);
    • uma FOTINHO de 64×64 em volta de cada clique — na hora de repetir, procura
      essa imagem na tela (OpenCV) e clica onde ela estiver, mesmo que a janela
      tenha mudado de lugar ou de tamanho;
    • o texto digitado como TEXTO (não tecla por tecla) e os atalhos como atalhos.
Durante a repetição, F12 PARA TUDO na hora. A primeira repetição de cada
tarefa pede confirmação na tela.

Usa pynput (já usado pelas macros), mss e OpenCV.
Tarefas ficam em config/demonstracoes/.
"""

from __future__ import annotations

import json
import threading
import time

from plugins._comum import CONFIG, WIN, confirmar, registrar

PLUGIN = {
    "name": "demonstracao",
    "brief": "Learn a task by watching once (clicks/keys with window and image anchors) and repeat it.",
    "description": (
        "Learning by demonstration: action='observar' starts watching the user do a task once (clicks with the "
        "target window and an image patch around each click, typed text, shortcuts); 'parar' (or F9) stops and "
        "saves with nome; 'repetir' with nome replays it, finding each click target on screen by image (F12 "
        "aborts); 'listar'; 'apagar' with nome."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "observar | parar | repetir | listar | apagar"},
            "nome": {"type": "STRING"}, "velocidade": {"type": "NUMBER"},
        },
        "required": [],
    },
}

PASTA = CONFIG / "demonstracoes"
_estado = {"gravando": None, "rodando": False, "abortar": False}


def _slug(nome: str) -> str:
    from plugins.macros import slug
    return slug(nome or "tarefa")


def janela_em(x: int, y: int) -> dict:
    """Programa e título da janela debaixo do ponto (Windows)."""
    if not WIN:
        return {}
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        h = u32.GetAncestor(u32.WindowFromPoint(wintypes.POINT(x, y)), 2)          # GA_ROOT
        n = u32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        r = wintypes.RECT()
        u32.GetWindowRect(h, ctypes.byref(r))
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        import psutil
        return {"titulo": buf.value, "processo": psutil.Process(pid.value).name(),
                "ret": [r.left, r.top, r.right, r.bottom]}
    except Exception:
        return {}


def _recorte(x: int, y: int, lado: int = 64):
    """Imagem em volta do clique (numpy BGR) ou None."""
    try:
        import mss
        import numpy as np
        with mss.mss() as sct:
            img = sct.grab({"left": x - lado // 2, "top": y - lado // 2, "width": lado, "height": lado})
            return np.array(img)[:, :, :3]
    except Exception:
        return None


# ── compactar os eventos crus em passos (pura) ─────────────────────────────────
_MODS = {"Key.ctrl", "Key.ctrl_l", "Key.ctrl_r", "Key.alt", "Key.alt_l", "Key.alt_r", "Key.alt_gr",
         "Key.cmd", "Key.cmd_l", "Key.cmd_r", "Key.shift", "Key.shift_l", "Key.shift_r"}


def _tecla_base(tecla: str) -> str:
    """'c:\x03' (Ctrl+C no Windows) → 'c'; 'vk:65' → 'a'; 'Key.tab' → 'tab'."""
    if tecla.startswith("vk:"):
        vk = int(tecla[3:])
        return chr(vk).lower() if 65 <= vk <= 90 or 48 <= vk <= 57 else tecla
    base = tecla[2:] if tecla.startswith("c:") else tecla.replace("Key.", "")
    if len(base) == 1 and ord(base) < 32:
        base = chr(ord(base) + 96)
    return base.lower() if len(base) == 1 else base


def compactar(eventos: list[list]) -> list[dict]:
    """[t, 'kd'|'ku'|'clique', ...] → passos: clique, texto, atalho, tecla, esperar."""
    passos, texto, apertadas, ultimo_t = [], "", set(), 0.0

    def fechar_texto(t):
        nonlocal texto
        if texto:
            passos.append({"tipo": "texto", "texto": texto, "t": t})
            texto = ""

    for ev in eventos:
        t, tipo = ev[0], ev[1]
        if t - ultimo_t > 1.5 and passos:
            fechar_texto(t)
            passos.append({"tipo": "esperar", "segundos": round(min(t - ultimo_t, 10), 1), "t": t})
        ultimo_t = t
        if tipo == "clique":
            fechar_texto(t)
            passos.append({"tipo": "clique", "x": ev[2], "y": ev[3], "botao": ev[4], "janela": ev[5],
                           "recorte": ev[6], "t": t})
        elif tipo == "kd":
            tecla = ev[2]
            mods = apertadas & _MODS
            if tecla in _MODS:
                apertadas.add(tecla)
            elif mods:
                fechar_texto(t)
                nomes = sorted({m.replace("Key.", "").split("_")[0] for m in mods})
                passos.append({"tipo": "atalho", "teclas": "+".join(nomes + [_tecla_base(tecla)]), "t": t})
            elif tecla.startswith("c:"):
                texto += tecla[2:]
            elif tecla == "Key.space":
                texto += " "
            elif tecla == "Key.backspace" and texto:
                texto = texto[:-1]
            else:
                fechar_texto(t)
                passos.append({"tipo": "tecla", "tecla": tecla, "t": t})
        elif tipo == "ku":
            apertadas.discard(ev[2])
    fechar_texto(ultimo_t)
    return passos


# ── gravação ───────────────────────────────────────────────────────────────────
class Observador:
    def __init__(self, nome: str, player):
        self.nome, self.player = nome or "tarefa", player
        self.eventos: list[list] = []
        self.recortes: list = []
        self.inicio = time.perf_counter()
        self._k = self._m = None

    def _t(self) -> float:
        return round(time.perf_counter() - self.inicio, 3)

    def comecar(self) -> None:
        from plugins.macros import _pynput, tecla_para_texto
        keyboard, mouse = _pynput()

        def press(tecla):
            t = tecla_para_texto(tecla)
            if t == "Key.f9":
                threading.Thread(target=parar, args=(None, self.player), daemon=True).start()
                return False
            self.eventos.append([self._t(), "kd", t])

        def release(tecla):
            self.eventos.append([self._t(), "ku", tecla_para_texto(tecla)])

        def clique(x, y, botao, apertou):
            if not apertou:
                return
            idx = len(self.recortes)
            self.recortes.append(_recorte(int(x), int(y)))
            self.eventos.append([self._t(), "clique", int(x), int(y), botao.name, janela_em(int(x), int(y)), idx])

        self._k = keyboard.Listener(on_press=press, on_release=release)
        self._m = mouse.Listener(on_click=clique)
        self._k.start()
        self._m.start()

    def terminar(self) -> list[dict]:
        for l in (self._k, self._m):
            try:
                l and l.stop()
            except Exception:
                pass
        return compactar(self.eventos)


def observar(nome: str, player) -> str:
    from plugins.macros import _pynput
    if _pynput() is None:
        return "Para observar preciso do pynput: pip install pynput"
    if _estado["gravando"]:
        return "Já estou observando. Aperte F9 ou diga 'pronto' quando terminar."
    o = Observador(nome, player)
    o.comecar()
    _estado["gravando"] = o
    registrar(player, "Demonstração: observando. F9 ou 'pronto' para terminar.")
    return "Pode fazer a tarefa: estou observando. Quando terminar, aperte F9 ou diga 'pronto'."


def parar(nome: str | None, player) -> str:
    o = _estado["gravando"]
    if not o:
        return "Eu não estava observando nada."
    _estado["gravando"] = None
    passos = o.terminar()
    if nome:
        o.nome = nome
    if not passos:
        return "Não vi nenhum clique ou tecla; nada foi guardado."
    pasta = PASTA / _slug(o.nome)
    pasta.mkdir(parents=True, exist_ok=True)
    try:
        import cv2
        for i, img in enumerate(o.recortes):
            if img is not None:
                cv2.imwrite(str(pasta / f"clique_{i}.png"), img)
    except Exception:
        pass
    (pasta / "tarefa.json").write_text(json.dumps({"nome": o.nome, "criado": time.time(), "aprovada": False,
                                                   "passos": passos}, ensure_ascii=False, indent=2), encoding="utf-8")
    cliques = sum(1 for p in passos if p["tipo"] == "clique")
    return (f"Guardei a tarefa '{o.nome}': {len(passos)} passos ({cliques} cliques). Diga 'repete a tarefa {o.nome}' "
            "quando quiser.")


# ── repetição ──────────────────────────────────────────────────────────────────
def achar_na_tela(recorte, perto: tuple[int, int] | None = None, limiar: float = 0.85):
    """Procura o recorte na tela; devolve o centro (x, y) ou None."""
    try:
        import cv2
        import mss
        import numpy as np
        with mss.mss() as sct:
            mon = sct.monitors[0]
            tela = np.array(sct.grab(mon))[:, :, :3]
            res = cv2.matchTemplate(tela, recorte, cv2.TM_CCOEFF_NORMED)
            _mn, nota, _p, pos = cv2.minMaxLoc(res)
            if nota < limiar:
                return None
            h, w = recorte.shape[:2]
            return pos[0] + w // 2 + mon["left"], pos[1] + h // 2 + mon["top"]
    except Exception:
        return None


def _focar(janela: dict) -> None:
    if not janela:
        return
    try:
        from plugins import _janelas
        alvo = _janelas.achar(janela.get("titulo") or "") or _janelas.achar(
            (janela.get("processo") or "").replace(".exe", ""))
        if alvo:
            _janelas.focar(alvo)
            time.sleep(0.4)
    except Exception:
        pass


def _executar(nome: str, dados: dict, velocidade: float, player) -> str:
    import cv2
    from plugins.macros import _pynput, texto_para_tecla
    keyboard, mouse = _pynput()
    kb, ms = keyboard.Controller(), mouse.Controller()
    pasta = PASTA / _slug(nome)
    _estado.update(rodando=True, abortar=False)

    def emergencia(tecla):
        if str(tecla) == "Key.f12":
            _estado["abortar"] = True
            return False
    escuta = keyboard.Listener(on_press=emergencia)
    escuta.start()
    feitos, por_imagem = 0, 0
    try:
        for p in dados["passos"]:
            if _estado["abortar"]:
                return f"Parei no passo {feitos + 1} (F12)."
            if p["tipo"] == "esperar":
                time.sleep(min(10.0, p["segundos"] / velocidade))
            elif p["tipo"] == "clique":
                _focar(p.get("janela") or {})
                alvo = None
                img = pasta / f"clique_{p['recorte']}.png"
                if img.exists():
                    alvo = achar_na_tela(cv2.imread(str(img)))
                if alvo:
                    por_imagem += 1
                else:
                    alvo = (p["x"], p["y"])
                ms.position = alvo
                time.sleep(0.08)
                ms.click(getattr(mouse.Button, p.get("botao") or "left", mouse.Button.left))
                time.sleep(0.25 / velocidade)
            elif p["tipo"] == "texto":
                kb.type(p["texto"])
            elif p["tipo"] == "atalho":
                teclas = []
                for parte in p["teclas"].split("+"):
                    k = getattr(keyboard.Key, parte, None) or (keyboard.KeyCode.from_char(parte) if len(parte) == 1 else None)
                    if k is not None:
                        teclas.append(k)
                for k in teclas:
                    kb.press(k)
                for k in reversed(teclas):
                    kb.release(k)
            elif p["tipo"] == "tecla":
                k = texto_para_tecla(p["tecla"], keyboard)
                if k is not None:
                    kb.press(k)
                    kb.release(k)
            feitos += 1
    finally:
        escuta.stop()
        _estado["rodando"] = False
    return f"Tarefa '{nome}' feita: {feitos} passos ({por_imagem} cliques achados pela imagem)."


def repetir(nome: str, velocidade: float, player) -> str:
    from plugins.macros import _pynput
    if _pynput() is None:
        return "Para repetir preciso do pynput: pip install pynput"
    arqs = sorted(PASTA.glob("*/tarefa.json")) if PASTA.exists() else []
    if not arqs:
        return "Ainda não aprendi nenhuma tarefa. Diga 'observa' e faça uma vez."
    alvo = PASTA / _slug(nome) / "tarefa.json" if nome else max(arqs, key=lambda a: a.stat().st_mtime)
    if not alvo.exists():
        from plugins._indice_apps import pontuar
        alvo = max(arqs, key=lambda a: pontuar(nome, a.parent.name.replace("_", " ")))
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    nome = dados["nome"]
    if _estado["rodando"]:
        return "Já estou repetindo uma tarefa."

    def fazer() -> str:
        dados["aprovada"] = True
        alvo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        threading.Thread(target=lambda: registrar(player, _executar(nome, dados, velocidade, player)), daemon=True).start()
        return f"Repetindo '{nome}'. Não mexa no mouse; F12 para na hora."

    if not dados.get("aprovada"):
        resumo = "\n".join(f"{i + 1}. {p['tipo']} {p.get('texto') or p.get('teclas') or (p.get('janela') or {}).get('titulo', '')}"
                           for i, p in enumerate(dados["passos"][:25]))
        return confirmar(f"demonstracao:{nome}", f"Repetir a tarefa '{nome}' pela primeira vez?",
                         resumo + "\n\nF12 interrompe a qualquer momento.", fazer)
    return fazer()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    nome = str(p.get("nome") or "").strip()
    try:
        if acao == "observar":
            return observar(nome or time.strftime("tarefa %d-%m %H%M"), player)
        if acao == "parar":
            return parar(nome or None, player)
        if acao == "repetir":
            return repetir(nome, max(0.25, min(4.0, float(p.get("velocidade") or 1.0))), player)
        if acao == "apagar":
            import shutil
            pasta = PASTA / _slug(nome)
            if not pasta.exists():
                return f"Não tenho a tarefa '{nome}'."
            shutil.rmtree(pasta)
            return f"Apaguei a tarefa '{nome}'."
        arqs = sorted(PASTA.glob("*/tarefa.json")) if PASTA.exists() else []
        if not arqs:
            return "Nenhuma tarefa aprendida ainda. Diga 'observa' e faça a tarefa uma vez."
        nomes = [json.loads(a.read_text(encoding="utf-8"))["nome"] for a in arqs]
        return "Tarefas que aprendi: " + ", ".join(nomes) + "."
    except Exception as e:
        return f"A demonstração falhou: {e}"
