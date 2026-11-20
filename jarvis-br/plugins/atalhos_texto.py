"""
Atalhos de texto (fork PT-BR 2.16, ideia 15).

Em QUALQUER programa, digite o atalho e ele vira o texto completo:

    //end   → seu endereço completo
    //pix   → sua chave Pix
    //cel   → seu celular
    //email → seu e-mail
    //data  → a data de hoje (09/11/2026)        //hora → a hora agora
    //obg   → "Muito obrigado! Qualquer dúvida, estou à disposição."

    "Jarvis, cria o atalho //loja com 'Cristal Malhas — Rua X, 123, Goiânia'"
    "Jarvis, quais atalhos de texto eu tenho?"     "Jarvis, apaga o atalho //obg"
    "Jarvis, pausa os atalhos de texto"

COMO FUNCIONA E PRIVACIDADE
    Um ouvinte de teclado (pynput) guarda SÓ os últimos 30 caracteres digitados,
    na memória, para ver se terminam num atalho; nada vai para o disco nem para
    a internet, e o resto é descartado. Quando bate, apaga o atalho com
    Backspace e cola o texto. Os atalhos ficam em config/atalhos_texto.json.
    Atalhos sempre começam com // para não disparar sem querer.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from plugins._comum import CONFIG, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "atalhos_texto",
    "brief": "Text expander in any app: //end, //pix… become full text; create, list, delete, pause.",
    "description": (
        "Text expander. action='criar' with atalho (starts with //) and texto. action='listar'. action='apagar' with "
        "atalho. action='pausar' / 'retomar'. Built-ins: //data, //hora. Never read sensitive expansions aloud; just "
        "confirm the shortcut exists."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "criar | listar | apagar | pausar | retomar"},
                       "atalho": {"type": "STRING"}, "texto": {"type": "STRING"}},
        "required": [],
    },
}

ARQ = CONFIG / "atalhos_texto.json"
PADRAO = {"//obg": "Muito obrigado! Qualquer dúvida, estou à disposição."}
_estado = {"pausado": False, "rodando": False}
_buffer: list[str] = []


def atalhos() -> dict[str, str]:
    d = ler_json(ARQ, None)
    if not isinstance(d, dict):
        d = dict(PADRAO)
        gravar_json(ARQ, d)
    return d


def expandir(atalho: str, tabela: dict[str, str], agora: datetime | None = None) -> str | None:
    agora = agora or datetime.now()
    embutidos = {"//data": agora.strftime("%d/%m/%Y"), "//hora": agora.strftime("%H:%M")}
    return tabela.get(atalho) or embutidos.get(atalho)


def casou(buffer: str, tabela: dict[str, str]) -> str | None:
    """O atalho com que o buffer termina (o mais longo), se houver (pura)."""
    candidatos = [a for a in list(tabela) + ["//data", "//hora"] if buffer.endswith(a)]
    if not candidatos:
        return None
    a = max(candidatos, key=len)
    antes = buffer[:-len(a)]
    if antes and antes[-1] not in " \n\t([{\"'":                # precisa começar numa palavra nova
        return None
    return a


def _trocar(atalho: str, texto: str) -> None:
    try:
        import pyperclip
        from pynput.keyboard import Controller, Key
        teclado = Controller()
        antes = pyperclip.paste()
        for _ in range(len(atalho)):
            teclado.press(Key.backspace)
            teclado.release(Key.backspace)
        pyperclip.copy(texto)
        time.sleep(0.03)
        with teclado.pressed(Key.ctrl):
            teclado.press("v")
            teclado.release("v")
        time.sleep(0.25)
        pyperclip.copy(antes)
    except Exception as e:
        print(f"[Atalhos de texto] {e}")


def _ouvinte() -> None:
    try:
        from pynput import keyboard
    except ImportError:
        print("[Atalhos de texto] instale o pynput: pip install pynput")
        _estado["rodando"] = False
        return
    tabela = {"t": 0.0, "d": {}}

    def ao_apertar(tecla):
        if _estado["pausado"]:
            return
        ch = getattr(tecla, "char", None)
        if ch is None:
            if tecla in (keyboard.Key.space, keyboard.Key.enter, keyboard.Key.tab):
                _buffer.append(" ")
            elif tecla == keyboard.Key.backspace and _buffer:
                _buffer.pop()
            elif tecla not in (keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.alt_gr):
                _buffer.clear()                              # setas, cliques de atalho: começa de novo
            return
        _buffer.append(ch)
        del _buffer[:-30]
        if time.time() - tabela["t"] > 5:
            tabela.update(t=time.time(), d=atalhos())
        a = casou("".join(_buffer), tabela["d"])
        if a:
            texto = expandir(a, tabela["d"])
            _buffer.clear()
            if texto:
                threading.Thread(target=_trocar, args=(a, texto), daemon=True).start()

    with keyboard.Listener(on_press=ao_apertar) as ouvinte:
        ouvinte.join()


def on_session_start(player) -> None:
    if not _estado["rodando"]:
        _estado["rodando"] = True
        atalhos()
        threading.Thread(target=_ouvinte, daemon=True, name="atalhos_texto").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "listar").lower()
    tab = atalhos()
    at = str(p.get("atalho") or "").strip().lower().replace(" ", "")
    if at and not at.startswith("//"):
        at = "//" + at.lstrip("/")
    try:
        if a == "criar":
            texto = str(p.get("texto") or "")
            if len(at) < 3 or not texto:
                return "Diga o atalho (ex.: //end) e o texto."
            tab[at] = texto
            gravar_json(ARQ, tab)
            on_session_start(player)
            return f"Pronto: digite {at} em qualquer lugar."
        if a == "apagar":
            if at in tab:
                tab.pop(at)
                gravar_json(ARQ, tab)
                return f"Atalho {at} apagado."
            return f"Não existe o atalho {at}."
        if a in ("pausar", "retomar"):
            _estado["pausado"] = a == "pausar"
            return "Atalhos de texto pausados." if _estado["pausado"] else "Atalhos de texto ligados."
        mostrar(player, "ATALHOS DE TEXTO", "\n".join(f"{k:<10} {v[:70]}" for k, v in sorted(tab.items()))
                + "\n//data     data de hoje\n//hora     hora agora")
        registrar(player, "Atalhos de texto listados.")
        return "Você tem: " + ", ".join(sorted(tab) + ["//data", "//hora"]) + "."
    except Exception as e:
        return f"Os atalhos de texto falharam: {e}"
