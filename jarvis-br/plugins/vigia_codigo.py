"""
Vigia de código em tempo real (fork PT-BR 2.13).

O JARVIS fica OLHANDO a sua tela de código e, quando vê um erro, FALA o erro e a
correção — erros de digitação/ortografia (em nomes, strings, comentários),
sintaxe (parêntese/aspas faltando, dois-pontos, indentação) e deslizes óbvios
(variável não definida, vírgula faltando). Não repete o mesmo erro toda hora.

    "Jarvis, vigia meu código."              (começa a olhar, de X em X segundos)
    "Jarvis, olha meu código agora."         (uma olhada só, na hora)
    "Jarvis, para de vigiar o código."       (para)

É sob demanda: só olha depois que VOCÊ liga, sempre a SUA tela, e aparece um
aviso de que está vigiando. Cada captura é usada na hora e não é salva. Ele FALA
a correção (e mostra na tela); não digita sozinho no seu editor — a correção é
sua para aplicar. Precisa da visão (Gemini) ligada.
"""

from __future__ import annotations

import threading
import time
import unicodedata

from plugins._comum import avisar, mostrar, registrar

PLUGIN = {
    "name": "vigia_codigo",
    "brief": "Watch my code on screen in real time and speak out errors (typos, syntax, obvious bugs) with the fix.",
    "description": (
        "Watches the user's code on screen and announces errors out loud as they appear — typos/spelling (in names, "
        "strings, comments), syntax (missing bracket/quote/colon, indentation) and obvious mistakes (undefined "
        "variable, missing comma). action='ligar' (start watching; optional intervalo in seconds, default 20), "
        "'desligar' (stop), 'olhar' (one look right now), 'status'. On demand only, always the user's own screen, "
        "shows a watching notice, saves nothing, and only SPEAKS the fix (does not type into the editor). Needs "
        "Gemini vision. Use for 'vigia meu código', 'olha meu código', 'me avisa dos erros na tela', 'para de vigiar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ligar | desligar | olhar | status"},
            "intervalo": {"type": "NUMBER", "description": "segundos entre cada olhada (padrão 20)"},
        },
    },
}

PLUGIN_SETTINGS = {
    "namespace": "vigia_codigo",
    "title": "Vigia de código",
    "fields": [
        {"key": "intervalo", "label": "Segundos entre cada olhada", "type": "text",
         "default": "20", "placeholder": "20"},
        {"key": "so_erros", "label": "Falar só quando houver erro (não narrar 'está tudo certo')",
         "type": "toggle", "default": True},
    ],
}

_INTERVALO_MIN = 8.0
_INTERVALO_PADRAO = 20.0
_MAX_VISTOS = 60

_lock = threading.RLock()
_thread: threading.Thread | None = None
_parar = threading.Event()
_vistos: list[str] = []            # erros já falados (para não repetir)

_PROMPT = (
    "Você está vendo a tela de CÓDIGO do usuário agora. Procure APENAS erros concretos e visíveis: "
    "erros de digitação/ortografia (em nomes de variáveis, strings ou comentários), erro de sintaxe "
    "(parêntese, colchete, chave ou aspas faltando, dois-pontos, ponto e vírgula, indentação errada) e "
    "deslizes óbvios (variável usada mas não definida, vírgula faltando, nome de função escrito errado). "
    "Para CADA erro, escreva UMA linha curta no formato: 'linha ~N: <o que está errado> → <correção>'. "
    "Use no máximo 3 linhas, só os erros mais importantes. Se NÃO houver nenhum erro claro, responda "
    "exatamente 'OK'. Não explique o código, não elogie, não invente erro. Português do Brasil."
)


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── puras (testáveis) ────────────────────────────────────────────────────────
def intervalo_valido(valor) -> float:
    try:
        n = float(str(valor).replace(",", ".")) if valor not in (None, "") else _INTERVALO_PADRAO
    except (ValueError, TypeError):
        n = _INTERVALO_PADRAO
    return max(_INTERVALO_MIN, n)


def _extrair_erros(resposta: str) -> list[str]:
    """Quebra a resposta da visão em linhas de erro. 'OK'/vazio → nenhuma (pura)."""
    if not resposta:
        return []
    bruto = resposta.strip()
    if _dobrar(bruto) in ("ok", "ok.", "tudo certo", "sem erros", "nenhum erro"):
        return []
    erros = []
    for linha in bruto.splitlines():
        t = linha.strip(" -•*\t")
        if not t:
            continue
        if _dobrar(t) in ("ok", "ok.", "tudo certo", "sem erros"):
            continue
        erros.append(t)
    return erros[:3]


def _chave(erro: str) -> str:
    """Identidade de um erro para não repetir (ignora caixa/acentos/espaços) (pura)."""
    return " ".join(_dobrar(erro).split())


def _novos(erros: list[str], vistos: list[str]) -> tuple[list[str], list[str]]:
    """(erros ainda não falados, lista de vistos atualizada) (pura)."""
    chaves = set(vistos)
    novos, atual = [], list(vistos)
    for e in erros:
        c = _chave(e)
        if c and c not in chaves:
            chaves.add(c)
            novos.append(e)
            atual.append(c)
    return novos, atual[-_MAX_VISTOS:]


# ── captura + visão ──────────────────────────────────────────────────────────
def _player():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.player()
    except Exception:
        return None


def _capturar():
    try:
        from actions import screen_processor as sp
        dados, _fmt = sp._capture_screen()
        return dados
    except Exception as e:
        print(f"[VigiaCodigo] captura: {e}")
        return None


def _olhar_uma_vez():
    """Devolve (resposta_bruta, erro_str). resposta None se não deu para ver."""
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return None, "Pra olhar o código eu preciso da visão (Gemini) ligada — coloque a chave em ⚙."
        dados = _capturar()
        if not dados:
            return None, "Não consegui capturar a tela agora."
        resposta = _ia.ver_imagem(_PROMPT, dados, inteligente=False, segundos=40)
        return (resposta or ""), ""
    except Exception as e:
        return None, f"A visão falhou: {e}"


# ── laço em segundo plano ────────────────────────────────────────────────────
def _loop(intervalo: float) -> None:
    global _vistos
    player = _player()
    while not _parar.is_set():
        resposta, erro = _olhar_uma_vez()
        if resposta is not None:
            erros = _extrair_erros(resposta)
            with _lock:
                novos, _vistos = _novos(erros, _vistos)
            for e in novos:
                avisar(player, "No código: " + e, "CÓDIGO")
        elif erro:
            registrar(player, f"VigiaCódigo: {erro}")
        _parar.wait(intervalo)


def ativa() -> bool:
    return bool(_thread and _thread.is_alive())


def ligar(intervalo: float) -> str:
    global _thread, _vistos
    with _lock:
        if ativa():
            return "Já estou vigiando o seu código. Diga 'para de vigiar o código' quando quiser."
        _parar.clear()
        _vistos = []
        _thread = threading.Thread(target=_loop, args=(intervalo,), daemon=True)
        _thread.start()
    player = _player()
    mostrar(player, "VIGIANDO O CÓDIGO",
            f"Olhando a sua tela a cada {int(intervalo)}s. Falo quando achar um erro.\n"
            "É sob demanda e não salvo nada. Diga 'para de vigiar o código' para parar.")
    return (f"Pronto, vou ficar de olho no seu código a cada {int(intervalo)} segundos e te aviso quando "
            "achar um erro de digitação, sintaxe ou algo fora do lugar. Para parar, é só pedir.")


def desligar() -> str:
    global _thread
    with _lock:
        if not ativa():
            return "Não estava vigiando o código."
        _parar.set()
        _thread = None
    return "Parei de vigiar o código."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = _dobrar(p.get("action") or "ligar").strip()
    try:
        if acao in ("desligar", "parar", "para", "stop"):
            return desligar()
        if acao in ("status", "estado"):
            return "Estou vigiando o seu código agora." if ativa() else "Não estou vigiando o código."
        if acao in ("olhar", "olha", "agora", "ver", "uma"):
            resposta, erro = _olhar_uma_vez()
            if resposta is None:
                return erro or "Não consegui olhar agora."
            erros = _extrair_erros(resposta)
            if not erros:
                return "Olhei seu código e não vi nenhum erro claro agora."
            mostrar(player, "ERROS NO CÓDIGO", "\n".join(erros))
            return "Achei isto no seu código:\n" + "\n".join(f"• {e}" for e in erros)
        # ligar
        return ligar(intervalo_valido(p.get("intervalo")))
    except Exception as e:
        return f"O vigia de código falhou: {e}"
