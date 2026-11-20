"""
Macros de teclado e mouse — plugin do J.A.R.V.I.S BR.

    "Jarvis, grava a macro relatório"   → começa a gravar (teclado e mouse)
    "Jarvis, para de gravar"  ou  F9    → salva em config/macros/relatorio.json
    "Jarvis, roda a macro relatório"    → repete
    "…duas vezes mais rápido", "…3 vezes" → velocidade e repetições
    F12 durante a reprodução            → PARA na hora (tecla de emergência)

Usa o pynput (pip install pynput). Sem ele, só este plugin fica desligado.

CUIDADO: durante a gravação, tudo o que você digita fica salvo no arquivo da
macro — não digite senhas enquanto grava. As macros ficam só no seu PC e a
pasta config/macros/ está no .gitignore.
"""

from __future__ import annotations

import re
import threading
import time

from plugins._comum import CONFIG, gravar_json, ler_json, mostrar, num, registrar

PLUGIN = {
    "name": "macros",
    "brief": "Record, stop, play, list and delete keyboard/mouse macros.",
    "description": (
        "Keyboard and mouse macros. action='gravar' (nome) starts recording; "
        "'parar' stops recording or a running macro; 'rodar' (nome, velocidade = 0.5 to 4, "
        "repeticoes; 0 = keep repeating until F12, max 8 h; optional jogo = only act while that game/app window is in "
        "front, pausing otherwise) plays one back; 'listar'; 'apagar' (nome). F9 also stops recording and F12 stops "
        "playback. Repeating routines in online games (e.g. Roblox) can get the account banned: say so once."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "gravar | parar | rodar | listar | apagar"},
            "nome": {"type": "STRING"},
            "velocidade": {"type": "NUMBER", "description": "1 = normal, 2 = twice as fast"},
            "repeticoes": {"type": "NUMBER", "description": "0 = until F12"},
            "jogo": {"type": "STRING", "description": "game/app that must be in front (e.g. roblox)"},
        },
        "required": ["action"],
    },
}

PASTA = CONFIG / "macros"
TECLA_PARAR_GRAVACAO = "Key.f9"
TECLA_EMERGENCIA = "Key.f12"

_estado = {"gravando": None, "rodando": None}
_parar_reproducao = threading.Event()


def slug(nome: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:40] or "macro"


def _pynput():
    try:
        from pynput import keyboard, mouse
        return keyboard, mouse
    except Exception:
        return None


def tecla_para_texto(tecla) -> str:
    """pynput Key/KeyCode → texto guardável ('Key.enter', 'c:a', 'vk:65')."""
    nome = str(tecla)
    if nome.startswith("Key."):
        return nome
    char = getattr(tecla, "char", None)
    if char:
        return f"c:{char}"
    vk = getattr(tecla, "vk", None)
    return f"vk:{vk}" if vk is not None else nome


def texto_para_tecla(texto: str, keyboard):
    if texto.startswith("Key."):
        return getattr(keyboard.Key, texto[4:], None)
    if texto.startswith("c:"):
        return keyboard.KeyCode.from_char(texto[2:])
    if texto.startswith("vk:"):
        return keyboard.KeyCode.from_vk(int(texto[3:]))
    return None


# ── gravação ───────────────────────────────────────────────────────────────────
class Gravador:
    def __init__(self, nome: str, player):
        self.nome, self.player = nome, player
        self.eventos: list[list] = []
        self.inicio = time.perf_counter()
        self._ult_mov = 0.0
        self._k = self._m = None

    def _t(self) -> float:
        return round(time.perf_counter() - self.inicio, 4)

    def comecar(self):
        keyboard, mouse = _pynput()

        def press(tecla):
            t = tecla_para_texto(tecla)
            if t == TECLA_PARAR_GRAVACAO:
                threading.Thread(target=parar_gravacao, daemon=True).start()
                return False
            if t != TECLA_EMERGENCIA:
                self.eventos.append([self._t(), "kd", t])

        def release(tecla):
            t = tecla_para_texto(tecla)
            if t not in (TECLA_PARAR_GRAVACAO, TECLA_EMERGENCIA):
                self.eventos.append([self._t(), "ku", t])

        def mover(x, y):
            agora = time.perf_counter()
            if agora - self._ult_mov >= 0.04:                  # até 25 pontos/s
                self._ult_mov = agora
                self.eventos.append([self._t(), "mm", int(x), int(y)])

        def clique(x, y, botao, apertou):
            self.eventos.append([self._t(), "mc", int(x), int(y), botao.name, bool(apertou)])

        def rolar(x, y, dx, dy):
            self.eventos.append([self._t(), "ms", int(x), int(y), int(dx), int(dy)])

        self._k = keyboard.Listener(on_press=press, on_release=release)
        self._m = mouse.Listener(on_move=mover, on_click=clique, on_scroll=rolar)
        self._k.start()
        self._m.start()

    def terminar(self) -> dict:
        for l in (self._k, self._m):
            try:
                if l:
                    l.stop()
            except Exception:
                pass
        return {"nome": self.nome, "criado": time.time(),
                "duracao": self._t(), "eventos": self.eventos}


def comecar_gravacao(nome: str, player) -> str:
    if _pynput() is None:
        return "Para gravar macros preciso do pynput: pip install pynput"
    if _estado["gravando"]:
        return f"Já estou gravando a macro {_estado['gravando'].nome}."
    if not nome:
        return "Qual o nome da macro?"
    g = Gravador(nome, player)
    g.comecar()
    _estado["gravando"] = g
    registrar(player, f"● GRAVANDO a macro '{nome}' — F9 ou 'para de gravar' para terminar.")
    return (f"Gravando a macro {nome}. Faça os passos agora e diga 'para de gravar' ou aperte F9. "
            "Não digite senhas enquanto eu gravo.")


def parar_gravacao() -> str:
    g = _estado["gravando"]
    if not g:
        return "Não estou gravando nenhuma macro."
    _estado["gravando"] = None
    dados = g.terminar()
    # tira o finzinho: o clique/fala que pediu para parar não faz parte da macro
    while dados["eventos"] and dados["eventos"][-1][1] in ("mm",):
        dados["eventos"].pop()
    if not dados["eventos"]:
        return "A macro ficou vazia; não salvei nada."
    gravar_json(PASTA / f"{slug(g.nome)}.json", dados)
    registrar(g.player, f"Macro '{g.nome}' salva ({len(dados['eventos'])} ações).")
    return f"Macro {g.nome} salva com {len(dados['eventos'])} ações em {dados['duracao']:.0f} segundos."


# ── reprodução ─────────────────────────────────────────────────────────────────
def carregar(nome: str) -> dict | None:
    caminho = PASTA / f"{slug(nome)}.json"
    if not caminho.exists():
        from plugins._indice_apps import pontuar
        candidatos = sorted(PASTA.glob("*.json"), key=lambda p: -pontuar(nome, p.stem.replace("_", " ")))
        if not candidatos or pontuar(nome, candidatos[0].stem.replace("_", " ")) < 60:
            return None
        caminho = candidatos[0]
    return ler_json(caminho)


def janela_ok(alvo: str, janela: dict | None) -> bool:
    """A janela em frente é a do jogo? ('roblox' bate com RobloxPlayerBeta.exe ou o título 'Roblox') (pura)."""
    if not alvo:
        return True
    if not janela:
        return False
    a = alvo.lower().replace(" ", "")
    return a in str(janela.get("processo", "")).lower().replace(" ", "") or a in str(janela.get("titulo", "")).lower().replace(" ", "")


def _esperar_janela(alvo: str) -> None:
    """Pausa enquanto o jogo não estiver em frente (2.0: modo jogo)."""
    if not alvo:
        return
    from plugins._janelas import ativa
    avisou = False
    while not _parar_reproducao.is_set():
        try:
            if janela_ok(alvo, ativa()):
                return
        except Exception:
            return
        if not avisou:
            print(f"[Macros] pausada: {alvo} não está em frente")
            avisou = True
        _parar_reproducao.wait(1.0)


def _reproduzir(dados: dict, velocidade: float, repeticoes: int, player, jogo: str = ""):
    keyboard, mouse = _pynput()
    teclado, rato = keyboard.Controller(), mouse.Controller()
    apertadas = set()

    def emergencia(tecla):
        if tecla_para_texto(tecla) == TECLA_EMERGENCIA:
            _parar_reproducao.set()
            return False

    vigia = keyboard.Listener(on_press=emergencia)
    vigia.start()
    try:
        fim_maximo = time.time() + 8 * 3600                       # "até parar" nunca passa de 8 horas
        rodada = 0
        ultima_checagem = 0.0
        while (repeticoes == 0 and time.time() < fim_maximo) or rodada < repeticoes:
            rodada += 1
            _esperar_janela(jogo)
            inicio, t0 = time.perf_counter(), None
            for ev in dados["eventos"]:
                if jogo and time.perf_counter() - ultima_checagem > 1.0:
                    ultima_checagem = time.perf_counter()
                    from plugins._janelas import ativa
                    if not janela_ok(jogo, ativa()):
                        for t in list(apertadas):                 # solta tudo antes de pausar
                            tecla = texto_para_tecla(t, keyboard)
                            if tecla is not None:
                                teclado.release(tecla)
                        apertadas.clear()
                        _esperar_janela(jogo)
                        inicio = time.perf_counter() - (ev[0] - (t0 or ev[0])) / velocidade
                if _parar_reproducao.is_set():
                    return
                t0 = ev[0] if t0 is None else t0
                alvo = inicio + (ev[0] - t0) / velocidade
                while True:
                    falta = alvo - time.perf_counter()
                    if falta <= 0 or _parar_reproducao.wait(min(falta, 0.05)):
                        break
                if _parar_reproducao.is_set():
                    return
                tipo = ev[1]
                if tipo in ("kd", "ku"):
                    tecla = texto_para_tecla(ev[2], keyboard)
                    if tecla is None:
                        continue
                    if tipo == "kd":
                        teclado.press(tecla)
                        apertadas.add(ev[2])
                    else:
                        teclado.release(tecla)
                        apertadas.discard(ev[2])
                elif tipo == "mm":
                    rato.position = (ev[2], ev[3])
                elif tipo == "mc":
                    rato.position = (ev[2], ev[3])
                    botao = getattr(mouse.Button, ev[4], mouse.Button.left)
                    (rato.press if ev[5] else rato.release)(botao)
                elif tipo == "ms":
                    rato.position = (ev[2], ev[3])
                    rato.scroll(ev[4], ev[5])
            time.sleep(0.3 / velocidade)
    finally:
        # Nenhuma tecla pode ficar "presa" se a macro parou no meio.
        for t in list(apertadas):
            tecla = texto_para_tecla(t, keyboard)
            if tecla is not None:
                try:
                    teclado.release(tecla)
                except Exception:
                    pass
        vigia.stop()
        _estado["rodando"] = None
        registrar(player, "Macro interrompida (F12)." if _parar_reproducao.is_set() else "Macro concluída.")


def rodar(nome: str, velocidade, repeticoes, player, jogo: str = "") -> str:
    if _pynput() is None:
        return "Para rodar macros preciso do pynput: pip install pynput"
    if _estado["gravando"]:
        return "Termine a gravação antes de rodar uma macro."
    if _estado["rodando"]:
        return "Já tem uma macro rodando. Aperte F12 para parar."
    dados = carregar(nome)
    if not dados:
        return f"Não encontrei a macro {nome}."
    v = max(0.25, min(4.0, num(velocidade, 1.0) or 1.0))
    r = num(repeticoes, 1)
    r = 0 if r == 0 and repeticoes not in (None, "") else max(1, min(1000, int(r or 1)))
    jogo = str(jogo or "").strip()
    _parar_reproducao.clear()
    _estado["rodando"] = dados["nome"]
    threading.Thread(target=_reproduzir, args=(dados, v, r, player, jogo), daemon=True, name="macro").start()
    vezes = " sem parar (até F12, no máximo 8 h)" if r == 0 else (f", {r} vezes" if r > 1 else "")
    so = f" Só age com o {jogo} em frente; se você trocar de janela, ela pausa." if jogo else ""
    return f"Rodando a macro {dados['nome']} em {v:g}x{vezes}.{so} F12 para parar."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "").strip().lower()
    nome = str(p.get("nome") or "").strip()
    try:
        if a == "gravar":
            return comecar_gravacao(nome, player)
        if a == "parar":
            if _estado["gravando"]:
                return parar_gravacao()
            if _estado["rodando"]:
                _parar_reproducao.set()
                return "Parei a macro."
            return "Não há macro gravando nem rodando."
        if a == "rodar":
            return rodar(nome, p.get("velocidade"), p.get("repeticoes"), player, str(p.get("jogo") or ""))
        if a == "listar":
            arquivos = sorted(PASTA.glob("*.json")) if PASTA.exists() else []
            if not arquivos:
                return "Nenhuma macro gravada ainda."
            infos = [ler_json(a, {}) for a in arquivos]
            mostrar(player, "MACROS", "\n".join(
                f"{i.get('nome', '?'):<24} {len(i.get('eventos', [])):>5} ações  {i.get('duracao', 0):.0f}s"
                for i in infos))
            return "Macros: " + ", ".join(i.get("nome", "?") for i in infos) + "."
        if a == "apagar":
            caminho = PASTA / f"{slug(nome)}.json"
            if not caminho.exists():
                return f"Não encontrei a macro {nome}."
            from plugins._comum import confirmar
            return confirmar(f"macro-{slug(nome)}", f"Apagar a macro {nome}",
                             "O arquivo da macro será apagado.",
                             lambda: (caminho.unlink(missing_ok=True), f"Macro {nome} apagada.")[1])
        return "Use gravar, parar, rodar, listar ou apagar."
    except Exception as e:
        return f"As macros falharam: {e}"
