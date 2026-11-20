"""
Central de avisos com prioridade (fork PT-BR 2.4).

Em vez de cada plugin falar na hora, os avisos falados passam por aqui:

    urgente  → fala na hora (internet caiu na live, temperatura crítica,
               sentinela, programa mandando GB de madrugada).
    normal   → espera uma brecha: você não está jogando, numa chamada, numa
               live, e o JARVIS não está falando. Se demorar mais de 2 horas,
               vira resumo.
    baixa    → vira RESUMO: quando a atividade acaba (você parou de jogar,
               voltou para o PC) ele conta tudo de uma vez:
               "Enquanto você jogava: 2 downloads terminaram e 1 alerta de RAM."

O registro, o painel, o push e o WhatsApp continuam na hora (só a FALA é
organizada). "Jarvis, o que eu perdi?" conta o que está guardado.

Quem chama: plugins/_notificar.notificar e plugins/_comum.avisar.
"""

from __future__ import annotations

import threading
import time
from collections import Counter

ESPERA_MAX_S = 2 * 3600
RESUMO_SOZINHO_S = 3600            # sem mudança de atividade: resumo depois de 1 h, numa brecha
LOOP_S = 5.0

_lock = threading.Lock()
_fila: list[dict] = []             # normais esperando brecha
_resumo: list[dict] = []           # baixas (e normais velhas)
_estado = {"thread": None, "falar": None, "player": None, "atividade_resumo": ""}
_parar = threading.Event()


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def prioridade_de(etiqueta: str = "", prioridade_push: str = "", texto: str = "") -> str:
    """Prioridade da fala a partir do que o plugin já dizia (pura)."""
    p = str(prioridade_push or "").lower()
    e = str(etiqueta or "").upper()
    t = str(texto or "").lower()
    if p in ("urgent", "max", "critica", "urgente") or any(x in e for x in ("URGENTE", "CRÍTIC", "CRITIC", "SENTINELA")) \
            or any(x in t for x in ("crític", "critic", "internet caiu", "sem internet", "fora do ar", "invas")):
        return "urgente"
    if p in ("low", "min", "baixa") or any(x in e for x in ("DOWNLOAD", "DICA", "SUGEST", "COMPANHEIRO")):
        return "baixa"
    return "normal"


def _categoria(item: dict) -> str:
    e = item.get("etiqueta", "").upper()
    t = item.get("texto", "").lower()
    if "DOWNLOAD" in e or "download" in t:
        return "download"
    if "ram" in t or "memória" in t:
        return "ram"
    if "cpu" in t or "temperatura" in t:
        return "cpu"
    return ""


def montar_resumo(itens: list[dict], atividade: str = "") -> str:
    """'Enquanto você jogava: 2 downloads terminaram e 1 alerta de RAM.' (pura)"""
    if not itens:
        return ""
    quando = {"jogando": "Enquanto você jogava", "em_chamada": "Enquanto você estava na chamada",
              "live": "Durante a live", "ausente": "Enquanto você estava fora",
              "programando": "Enquanto você programava", "editando": "Enquanto você editava",
              "dormindo": "Enquanto o senhor dormia"}.get(atividade,                          # 2.8
                                                                                                 "Enquanto isso")
    cont = Counter(_categoria(i) for i in itens)
    partes = []
    if cont["download"]:
        partes.append(f"{cont['download']} download{'s terminaram' if cont['download'] > 1 else ' terminou'}")
    for cat, nome in (("ram", "RAM"), ("cpu", "CPU/temperatura")):
        if cont[cat]:
            partes.append(f"{cont[cat]} alerta{'s' if cont[cat] > 1 else ''} de {nome}")
    outros = [i["texto"] for i in itens if not _categoria(i)]
    vistos, unicos = set(), []
    for t in outros:
        if t not in vistos:
            vistos.add(t)
            unicos.append(t)
    if len(unicos) > 3:
        partes.append(f"{len(unicos)} outros avisos (o primeiro: {unicos[0][:120]})")
    else:
        partes += [t[:160] for t in unicos]
    if len(partes) == 1:
        corpo = partes[0]
    else:
        corpo = ", ".join(partes[:-1]) + " e " + partes[-1]
    return f"{quando}: {corpo.rstrip('.')}."


def separar(fila: list[dict], estado: dict, agora: float) -> tuple[list[dict], list[dict], list[dict]]:
    """(falar_agora, continuar_esperando, mandar_para_resumo) (pura)."""
    from core.estado_mundo import permite
    if not fila:
        return [], [], []
    if permite(estado, "normal"):
        return list(fila), [], []
    velhos = [i for i in fila if agora - i["ts"] > ESPERA_MAX_S]
    return [], [i for i in fila if i not in velhos], velhos


# ── fala de verdade ──────────────────────────────────────────────────────────
def _falar(texto: str, etiqueta: str = "AVISO") -> None:
    fn = _estado["falar"]
    if fn is not None:                                         # nos testes
        fn(texto)
        return
    from plugins._comum import falar
    player = _estado["player"]
    if player is None:
        try:
            from core import registro_ferramentas
            player = registro_ferramentas.player()
        except Exception:
            player = None
    falar(player, f"[{etiqueta}] Diga ao usuário, em UMA ou duas frases curtas e no idioma da conversa: {texto} "
                  "Não chame nenhuma ferramenta.")


def avisar(texto: str, prioridade: str = "normal", etiqueta: str = "AVISO", player=None) -> str:
    """Entrega a fala de um aviso. Devolve 'falado', 'na_fila' ou 'resumo'."""
    texto = " ".join(str(texto or "").split())
    if not texto:
        return ""
    if player is not None:
        _estado["player"] = player
    _garantir_laco()
    item = {"texto": texto, "etiqueta": etiqueta, "ts": time.time(), "prioridade": prioridade}
    if prioridade == "urgente":
        _falar(texto, etiqueta)
        return "falado"
    try:
        from core import estado_mundo
        e = estado_mundo.agora()
    except Exception:
        e = {"fala": "normal", "atividade": "livre"}
    if prioridade == "baixa":
        with _lock:
            _resumo.append(item)
            if not _estado["atividade_resumo"] and e.get("atividade") not in ("livre", "assistindo"):
                _estado["atividade_resumo"] = e.get("atividade", "")
        return "resumo"
    from core.estado_mundo import permite
    with _lock:
        vazia = not _fila
    if vazia and permite(e, "normal"):
        _falar(texto, etiqueta)
        return "falado"
    with _lock:
        _fila.append(item)
        if not _estado["atividade_resumo"] and e.get("atividade") not in ("livre", "assistindo"):
            _estado["atividade_resumo"] = e.get("atividade", "")
    return "na_fila"


def pendentes() -> dict:
    with _lock:
        return {"fila": list(_fila), "resumo": list(_resumo)}


def o_que_perdi(limpar: bool = True) -> str:
    with _lock:
        itens = _fila + _resumo
        atividade = _estado["atividade_resumo"]
        if limpar:
            _fila.clear()
            _resumo.clear()
            _estado["atividade_resumo"] = ""
    return montar_resumo(itens, atividade) or "Nada guardado: você não perdeu nenhum aviso."


def passo(estado: dict | None = None, agora: float | None = None) -> list[str]:
    """Uma volta do laço: fala o que pode, joga os velhos no resumo e solta o resumo na hora certa."""
    agora = agora or time.time()
    if estado is None:
        from core import estado_mundo
        estado = estado_mundo.agora()
    from core.estado_mundo import permite
    falados = []
    with _lock:
        falar_ja, esperar, velhos = separar(_fila, estado, agora)
        _fila[:] = esperar
        _resumo.extend(velhos)
        soltar_resumo = bool(_resumo) and permite(estado, "normal") and (
            estado.get("atividade") != _estado["atividade_resumo"] or
            agora - min(i["ts"] for i in _resumo) > RESUMO_SOZINHO_S)
        itens_resumo = list(_resumo) if soltar_resumo else []
        atividade = _estado["atividade_resumo"]
        if soltar_resumo:
            _resumo.clear()
            _estado["atividade_resumo"] = ""
    if falar_ja:
        texto = " ".join(i["texto"] for i in falar_ja[:3])
        if len(falar_ja) > 3:
            texto += f" E mais {len(falar_ja) - 3} avisos no registro."
        _falar(texto, falar_ja[0]["etiqueta"])
        falados.append(texto)
    if itens_resumo:
        r = montar_resumo(itens_resumo, atividade)
        _falar(r, "RESUMO")
        falados.append(r)
    return falados


def _laco() -> None:
    while not _parar.wait(LOOP_S):
        try:
            with _lock:
                tem = bool(_fila or _resumo)
            if tem:
                passo()
        except Exception as e:
            print(f"[CentralAvisos] {e}")


def _garantir_laco() -> None:
    if _estado["falar"] is not None:
        return                                                 # testes: sem thread
    t = _estado["thread"]
    if t is None or not t.is_alive():
        _estado["thread"] = threading.Thread(target=_laco, daemon=True, name="central_avisos")
        _estado["thread"].start()
