"""
Painel de LED na parede (fork PT-BR 2.5) — matriz MAX7219 com ESP32.

    "Jarvis, configura o painel de LED"       → IP e CHAVE para o sketch esp32/painel_led
    "Jarvis, escreve no painel: Feliz aniversário, mãe!"   (fica 10 minutos)
    "Jarvis, brilho do painel no 2"           "Jarvis, tira as vendas do painel"

O texto passa da direita para a esquerda, estilo letreiro:
    15:42 * > Matue - Quer Voar * Hoje: 3 vendas, R$ 245 * Aviso: a conta de luz vence sexta
Aviso novo chega na hora (e o painel pisca). A matriz só tem letras sem
acento, então o JARVIS tira os acentos ("Goiânia" vira "Goiania").
"""

from __future__ import annotations

import threading
import time
import unicodedata
from datetime import datetime

from plugins import _esp32
from plugins._comum import cfg, salvar_cfg, sim

PLUGIN = {
    "name": "painel_led",
    "brief": "LED matrix on the wall (ESP32): scrolls time, song playing, notices and today's sales; custom messages.",
    "description": (
        "LED wall panel. action='mensagem' with texto (shows it for minutos, default 10). 'brilho' with valor 0-15. "
        "'itens' with item (hora | musica | avisos | vendas) and valor ligar/desligar. 'configurar' gives the PC IP "
        "and key for the ESP32 sketch. 'status' shows what the panel is showing now."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mensagem | brilho | itens | configurar | status"},
            "texto": {"type": "STRING"}, "minutos": {"type": "NUMBER"}, "valor": {"type": "STRING"},
            "item": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "painel_led",
    "title": "Painel de LED (ESP32)",
    "fields": [
        {"key": "hora", "label": "Mostrar a hora", "type": "toggle", "default": True},
        {"key": "musica", "label": "Mostrar a música tocando", "type": "toggle", "default": True},
        {"key": "avisos", "label": "Mostrar os avisos do JARVIS", "type": "toggle", "default": True},
        {"key": "vendas", "label": "Mostrar as vendas do dia (Cristal Malhas)", "type": "toggle", "default": True},
        {"key": "brilho", "label": "Brilho (0 a 15)", "type": "text", "default": "4"},
        {"key": "velocidade", "label": "Velocidade (menor = mais rápido, em ms)", "type": "text", "default": "35"},
    ],
}

SEPARADOR = "  *  "
_iniciou = threading.Event()
_estado = {"mensagem": "", "mensagem_ate": 0.0, "ultimo_aviso": 0.0, "cache_musica": ("", 0.0), "ultimo_texto": ""}


def _c() -> dict:
    return cfg("painel_led", PLUGIN_SETTINGS)


def ascii_painel(texto: str, limite: int = 220) -> str:
    """Sem acento e só ASCII visível — a fonte da MAX7219 não tem acento (puro)."""
    t = str(texto or "").replace("♪", ">").replace("•", "*").replace("—", "-").replace("–", "-")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in t)
    return " ".join(t.split())[:limite]


def montar(hora: str = "", musica: str = "", vendas: str = "", avisos: list[str] | None = None,
           mensagem: str = "") -> str:
    """Junta as partes do letreiro (puro). Mensagem fixa vem antes de tudo."""
    partes = [mensagem] if mensagem else []
    partes += [p for p in (hora, f"> {musica}" if musica else "", vendas) if p]
    partes += [f"Aviso: {a}" for a in (avisos or [])[:2]]
    return ascii_painel(SEPARADOR.join(partes))


def _musica() -> str:
    texto, quando = _estado["cache_musica"]
    if time.time() - quando < 20:
        return texto
    texto = ""
    try:
        from plugins import musica
        e = musica.estado_player()
        if e.get("tocando") and e.get("titulo"):
            texto = f"{e.get('titulo')}" + (f" - {e['artistas']}" if e.get("artistas") else "")
    except Exception:
        texto = ""
    _estado["cache_musica"] = (texto, time.time())
    return texto


def _vendas_hoje() -> str:
    try:
        from plugins._dados_br import ler, numero
        hoje = datetime.now().strftime("%Y-%m-%d")
        vendas = [v for v in ler("cristal_vendas.csv") if str(v.get("data", "")).startswith(hoje)]
    except Exception:
        return ""
    if not vendas:
        return ""
    total = sum(numero(v.get("total")) for v in vendas)
    valor = f"R$ {int(round(total)):,}".replace(",", ".")
    return f"Hoje: {len(vendas)} venda{'s' if len(vendas) > 1 else ''}, {valor}"


def texto_atual() -> tuple[str, bool]:
    """(texto, alerta) — alerta = chegou aviso novo desde a última vez."""
    c = _c()
    agora = time.time()
    mensagem = _estado["mensagem"] if agora < _estado["mensagem_ate"] else ""
    avisos, alerta = [], False
    if sim(c.get("avisos", True)):
        try:
            from plugins._notificar import recentes
            novos = recentes(900)
            avisos = [t for _q, _ti, t in reversed(novos)]
            alerta = bool(novos) and novos[-1][0] > _estado["ultimo_aviso"]
            if novos:
                _estado["ultimo_aviso"] = max(_estado["ultimo_aviso"], novos[-1][0])
        except Exception:
            pass
    texto = montar(datetime.now().strftime("%H:%M") if sim(c.get("hora", True)) else "",
                   _musica() if sim(c.get("musica", True)) else "",
                   _vendas_hoje() if sim(c.get("vendas", True)) else "", avisos, mensagem)
    _estado["ultimo_texto"] = texto
    return texto or datetime.now().strftime("%H:%M"), alerta


def _numero(v, padrao: int, minimo: int, maximo: int) -> int:
    try:
        return max(minimo, min(maximo, int(float(str(v)))))
    except (TypeError, ValueError):
        return padrao


def para_o_painel(_corpo: dict, _q: dict) -> dict:
    texto, alerta = texto_atual()
    c = _c()
    return {"texto": texto, "alerta": alerta, "brilho": _numero(c.get("brilho"), 4, 0, 15),
            "velocidade": _numero(c.get("velocidade"), 35, 10, 200)}


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    _esp32.registrar_rota("GET", "/esp32/painel", para_o_painel)
    _esp32.iniciar_se_ligado()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "configurar":
            _esp32.registrar_rota("GET", "/esp32/painel", para_o_painel)
            return _esp32.configuracao("painel_led")
        if acao == "mensagem":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                _estado["mensagem_ate"] = 0
                return "Tirei a mensagem do painel."
            minutos = _numero(p.get("minutos"), 10, 1, 24 * 60)
            _estado["mensagem"], _estado["mensagem_ate"] = texto, time.time() + minutos * 60
            visto = _esp32.visto("painel")
            aviso = "" if visto and time.time() - visto < 300 else " (O painel não falou com o PC nos últimos minutos: " \
                                                                     "confira se ele está ligado.)"
            return f"Mostrando \"{ascii_painel(texto)}\" no painel por {minutos} minutos.{aviso}"
        if acao == "brilho":
            b = _numero(p.get("valor"), 4, 0, 15)
            salvar_cfg("painel_led", {"brilho": str(b)})
            return f"Brilho do painel em {b} (de 0 a 15)."
        if acao == "itens":
            item = str(p.get("item") or "").lower()
            chave = next((k for k in ("hora", "musica", "avisos", "vendas") if k in item.replace("ú", "u")), "")
            if not chave:
                return "Qual item? hora, música, avisos ou vendas."
            ligar = not str(p.get("valor") or "ligar").lower().startswith(("deslig", "tir", "off", "não", "nao"))
            salvar_cfg("painel_led", {chave: ligar})
            return f"{chave.capitalize()} {'aparece' if ligar else 'não aparece mais'} no painel."
        texto, _alerta = texto_atual()
        visto = _esp32.visto("painel")
        quando = f"falou com o PC às {datetime.fromtimestamp(visto).strftime('%H:%M')}" if visto else \
            "ainda não falou com o PC (diga 'configura o painel de LED')"
        return f"O painel {quando}. Agora ele mostra: {texto}"
    except Exception as e:
        return f"O painel de LED falhou: {e}"
