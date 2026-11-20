"""
Emoções do rosto (fork PT-BR 2.14).

Um lugar só para dizer "como o rosto está agora". Quem desenha um rosto lê
daqui; quem sabe de uma emoção escreve aqui:

    • o rosto 3D do HUD e o rosto flutuante (core/avatar.py) — JARVIS ou SEXTA,
      conforme a persona ativa;
    • o palco das cenas a dois (dashboard/static/palco.html), uma emoção por
      personagem;
    • o main.py manda o texto que o JARVIS está falando: `ao_falar(texto)`
      acha a emoção pelas palavras ("infelizmente…" → triste, "uau" → surpresa,
      "as chances são de 92%" → feliz) enquanto ele fala;
    • o plugin `expressoes` deixa você (ou o próprio modelo) pedir uma cara:
      "Jarvis, fica feliz", "faz cara de surpresa".

Emoções: neutro, feliz, animado, triste, surpresa, serio, raiva, desconfiado,
pensativo, envergonhado. Cada uma é um conjunto de alvos (sorriso, abertura da
boca, sobrancelhas, olhos, olhar, cabeça, cor da aura); o rosto chega neles
suavemente e, passado o tempo, volta sozinho ao neutro.

Tudo aqui é Python puro e barato: pode ser chamado de qualquer thread.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata

# Alvos de cada emoção. Unidades:
#   sorriso      -1 cantos da boca para baixo … +1 para cima
#   abre         0..1 boca aberta sem estar falando (o "Oh!")
#   sobr         sobrancelhas inteiras: -0.5 baixas … 1 bem altas
#   sobr_dentro  ponta de dentro: +1 sobe (tristeza/preocupação) … -1 desce (bravo)
#   sobr_torto   uma sobe e a outra desce (desconfiança)
#   olhos        abertura: 0.55 apertados … 1.35 arregalados
#   olhar_y      +1 olha para baixo … -1 para cima
#   cabeca       inclinação para a frente (+) / para trás (-)
#   cor          tom da aura (r, g, b) misturado à cor do tema
EMOCOES: dict[str, dict] = {
    "neutro":       {},
    "feliz":        {"sorriso": .9, "sobr": .25, "olhos": .78, "cor": (255, 210, 90)},
    "animado":      {"sorriso": 1.0, "abre": .32, "sobr": .55, "olhos": 1.12, "cor": (255, 170, 60)},
    "triste":       {"sorriso": -.75, "sobr_dentro": .9, "sobr": -.1, "olhos": .78, "olhar_y": .55,
                     "cabeca": .07, "cor": (90, 140, 255)},
    "surpresa":     {"abre": .55, "sobr": 1.0, "olhos": 1.35, "sorriso": .05, "cabeca": -.05,
                     "cor": (235, 245, 255)},
    "serio":        {"sobr_dentro": -.45, "sobr": -.2, "olhos": .85, "sorriso": -.2, "cor": (255, 140, 80)},
    "raiva":        {"sobr_dentro": -1.0, "sobr": -.35, "olhos": .7, "sorriso": -.4, "cabeca": .04,
                     "cor": (255, 60, 60)},
    "desconfiado":  {"sobr_torto": .85, "olhos": .72, "sorriso": -.15, "cor": (200, 160, 255)},
    "pensativo":    {"sobr_torto": .35, "olhar_y": -.55, "sorriso": -.05, "olhos": .92, "cor": (140, 220, 255)},
    "envergonhado": {"sorriso": .45, "sobr_dentro": .4, "olhos": .82, "olhar_y": .5, "cabeca": .05,
                     "cor": (255, 120, 150)},
}
NOMES = {"neutro": "neutro", "feliz": "feliz", "animado": "animado", "triste": "triste", "surpresa": "surpresa",
         "serio": "sério", "raiva": "bravo", "desconfiado": "desconfiado", "pensativo": "pensativo",
         "envergonhado": "envergonhado"}
APELIDOS = {"alegre": "feliz", "contente": "feliz", "sorrindo": "feliz", "sorri": "feliz", "sorriso": "feliz",
            "empolgado": "animado", "empolgada": "animado", "animada": "animado", "triste": "triste",
            "chateado": "triste", "chateada": "triste", "magoado": "triste", "surpreso": "surpresa",
            "surpresa": "surpresa", "surpresa!": "surpresa", "espanto": "surpresa", "assustado": "surpresa",
            "chocado": "surpresa", "serio": "serio", "séria": "serio", "seria": "serio", "sério": "serio",
            "bravo": "raiva", "brava": "raiva", "raiva": "raiva", "irritado": "raiva", "irritada": "raiva",
            "nervoso": "raiva", "desconfiado": "desconfiado", "desconfiada": "desconfiado", "suspeito": "desconfiado",
            "pensativo": "pensativo", "pensativa": "pensativo", "pensando": "pensativo", "envergonhado":
            "envergonhado", "envergonhada": "envergonhado", "timido": "envergonhado", "tímido": "envergonhado",
            "normal": "neutro", "neutro": "neutro", "neutra": "neutro"}

DURACAO_PADRAO = 5.0
AUTOMATICO = {"ligado": True}          # o plugin "expressoes" liga/desliga a detecção pela fala

_lock = threading.Lock()
# "principal" é o rosto do HUD; os outros são personagens do palco ("JARVIS", "FRIDAY"…)
_estado: dict[str, dict] = {}
_estilo = {"valor": "jarvis", "lido": 0.0}
_ultimo_texto = {"t": 0.0, "texto": ""}


def _d(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


def normalizar(nome: str) -> str | None:
    """'Surpreso' → 'surpresa'; desconhecida → None (pura)."""
    n = str(nome or "").strip().lower()
    if n in EMOCOES:
        return n
    if n in APELIDOS:
        return APELIDOS[n]
    nd = _d(n)
    for k in EMOCOES:
        if _d(k) == nd:
            return k
    for k, v in APELIDOS.items():
        if _d(k) == nd:
            return v
    return None


# ── detecção pelo texto ───────────────────────────────────────────────────────
_REGRAS: list[tuple[str, str]] = [
    # (regex sobre o texto sem acento, emoção) — a primeira que casar ganha
    (r"\b(uau|nossa|caramba|eita|minha nossa|nao acredito|serio\?|que surpresa|inacreditavel|incrivel!)", "surpresa"),
    (r"\b(infelizmente|lamento|sinto muito|que pena|nao consegui|falhou|deu errado|perdemos|triste)", "triste"),
    (r"\b(perigo|perigoso|cuidado|alerta|bloquei|proibid|ameaca|ataque|virus|golpe|invasao)", "serio"),
    (r"\b(hmm+|talvez|nao tenho certeza|suspeit|desconfi|estranho|curioso)", "desconfiado"),
    (r"\b(deixa eu ver|vou pensar|analisando|calculando|considerando)", "pensativo"),
    (r"\b(desculpe|desculpa|perdao|foi mal|me enganei|errei)", "envergonhado"),
    (r"\b(parabens|consegui|conseguimos|deu certo|perfeito|excelente|otimo|maravilh|feliz|que bom|adoro|"
     r"incrivel|sucesso|pronto, senhor|feito, senhor|haha|kkk)", "feliz"),
]
_CHANCE = re.compile(r"chances? de sucesso (?:sao|e) de (\d{1,3})\s*%")


def detectar(texto: str) -> str | None:
    """A emoção que o texto pede, ou None se for neutro (pura)."""
    t = _d(texto)
    if not t:
        return None
    m = _CHANCE.search(t)                 # "Senhor, as chances de sucesso são de 14%"
    if m:
        pct = int(m.group(1))
        return "feliz" if pct >= 75 else "serio" if pct >= 40 else "triste"
    for padrao, emo in _REGRAS:
        if re.search(padrao, t):
            return emo
    if t.count("!") >= 2:
        return "animado"
    return None


# ── estado ────────────────────────────────────────────────────────────────────
def definir(nome: str, segundos: float | None = DURACAO_PADRAO, intensidade: float = 1.0,
            quem: str = "principal") -> str | None:
    """Muda a emoção de um rosto. segundos=None (ou 0) fica até mudar de novo."""
    emo = normalizar(nome)
    if emo is None:
        return None
    intensidade = max(0.0, min(1.5, float(intensidade or 1.0)))
    ate = (time.monotonic() + float(segundos)) if segundos else None
    with _lock:
        _estado[str(quem or "principal").upper() if quem != "principal" else "principal"] = {
            "emocao": emo, "intensidade": intensidade, "ate": ate, "desde": time.monotonic()}
    return emo


def atual(quem: str = "principal") -> tuple[str, float]:
    """(emoção, intensidade) agora; volta ao neutro quando o tempo acaba."""
    chave = "principal" if quem == "principal" else str(quem or "").upper()
    with _lock:
        e = _estado.get(chave)
    if not e:
        return "neutro", 0.0
    if e["ate"] is not None and time.monotonic() > e["ate"]:
        return "neutro", 0.0
    return e["emocao"], e["intensidade"]


def alvos(quem: str = "principal") -> dict:
    """Os números que o rosto deve buscar agora, já multiplicados pela intensidade."""
    emo, k = atual(quem)
    base = EMOCOES.get(emo, {})
    out = {c: float(base.get(c, 0.0)) * k for c in ("sorriso", "abre", "sobr", "sobr_dentro", "sobr_torto",
                                                    "olhar_y", "cabeca")}
    out["olhos"] = 1.0 + (float(base.get("olhos", 1.0)) - 1.0) * k
    out["cor"] = base.get("cor")
    out["cor_forca"] = 0.0 if emo == "neutro" else min(1.0, .45 * k)
    out["emocao"] = emo
    return out


def ao_falar(texto: str, quem: str = "principal") -> str | None:
    """Chamado com o que o assistente está falando. Só troca se achar uma emoção
    e no máximo a cada 1,2 s, para o rosto não ficar piscando de cara."""
    if not AUTOMATICO["ligado"]:
        return None
    agora = time.monotonic()
    if agora - _ultimo_texto["t"] < 1.2:
        return None
    emo = detectar(texto)
    if emo is None:
        return None
    _ultimo_texto.update(t=agora, texto=str(texto)[-200:])
    atual_emo, _k = atual(quem)
    if atual_emo == emo:
        with _lock:                       # renova o tempo
            e = _estado.get("principal" if quem == "principal" else quem.upper())
            if e and e["ate"] is not None:
                e["ate"] = agora + DURACAO_PADRAO
        return emo
    return definir(emo, DURACAO_PADRAO, 1.0, quem)


def todas_do_palco() -> dict:
    """Emoção de cada personagem do palco (para /api/palco)."""
    with _lock:
        chaves = [k for k in _estado if k != "principal"]
    saida = {}
    for k in chaves:
        emo, i = atual(k)
        saida[k] = {"emocao": emo, "intensidade": round(i, 2)}
    return saida


# ── qual rosto: JARVIS ou SEXTA ───────────────────────────────────────────────
def estilo() -> str:
    """'friday' quando a persona ativa é a F.R.I.D.A.Y (a SEXTA), senão 'jarvis'.
    Relido do disco no máximo a cada 3 s."""
    agora = time.monotonic()
    if agora - _estilo["lido"] > 3.0:
        _estilo["lido"] = agora
        try:
            from plugins import _personas
            ativa = str(_personas.carregar().get("ativa") or "jarvis").lower()
            _estilo["valor"] = "friday" if ativa == "friday" else "jarvis"
        except Exception:
            pass
    return _estilo["valor"]


def forcar_estilo(valor: str) -> None:
    """Usado pela troca de persona, para o rosto mudar na hora."""
    _estilo.update(valor="friday" if str(valor).lower() in ("friday", "sexta") else "jarvis",
                   lido=time.monotonic())
