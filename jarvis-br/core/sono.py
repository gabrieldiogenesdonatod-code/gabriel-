"""
Modo dormir do JARVIS (fork PT-BR 2.8).

Até a 2.7.4 o JARVIS só "dormia" com a palavra de ativação ligada (o pacote
openwakeword + o modelo "Hey Jarvis"); sem ela, o botão DORMIR nem aparecia.
Agora ele dorme de verdade em qualquer configuração:

    "Jarvis, vai dormir"     "dorme 30 minutos"     "fica quieto até as 15h"
    "Jarvis, vou dormir"     (a rotina de boa noite do plugin modo_dormir)
    o botão 😴 DORMIR AGORA  ·  Ctrl+Alt+D em qualquer janela (Windows)

Dormindo:
    • o microfone NÃO vai para o Gemini — nada do que se fala no quarto sai do PC;
    • a conversa continua aberta (o silêncio de 15 em 15 s da 2.7.4), então
      acordar é na hora, sem reconectar;
    • o que os plugins pediriam para falar fica guardado e vira o "Enquanto eu
      dormia…" — só o urgente (sentinela, alarme, despertador) passa e acorda;
    • se o JARVIS ou o PC reiniciar de madrugada, ele volta dormindo.

Acorda com: "Hey Jarvis" (se o modelo estiver baixado), DUAS PALMAS, "Jarvis,
acorda" (reconhecido no próprio PC, com o faster-whisper instalado), Ctrl+Alt+D,
o botão 👂 ACORDAR AGORA, qualquer coisa digitada, a tecla do push-to-talk, um
pedido pelo celular/WhatsApp — ou sozinho, na hora marcada.

Quem usa: main.py (o portão do microfone e da fala) e plugins/modo_dormir.py
(boa noite, despertador, diário do sono). As regras são puras e testadas em
tests/test_33_sono.py.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

BASE = Path(__file__).resolve().parent.parent
ARQ = BASE / "memory" / "sono_estado.json"
NAMESPACE = "modo_dormir"                 # ⚙ CONFIG. DE PLUGINS → Modo dormir (plugins/modo_dormir.py)
ATALHO = ("ctrl", "alt", "d")             # dorme/acorda de qualquer janela (core/hotkey.py, Windows)
TAXA = 16000                              # o microfone do main.py: 16 kHz, mono, int16
MAX_RECADOS = 30
SEM_HORA_MAX_S = 6 * 3600                 # dormindo sem hora marcada: volta dormindo se reiniciar em até 6 h
ATRASO_MAX_S = 3 * 3600                   # hora de acordar que passou com o PC desligado: ainda vale por 3 h

_lock = threading.RLock()
_ouvintes: dict[str, Callable[[dict], bool]] = {}
_ultimo = {"acordou": 0.0, "motivo": ""}


def _vazio() -> dict:
    return {"dormindo": False, "desde": 0.0, "ate": 0.0, "motivo": "", "rotina": False, "alarme": False,
            "recados": [], "retorno": None}


_estado: dict = _vazio()


# ── configuração (⚙ Modo dormir) ──────────────────────────────────────────────
def config(chave: str, padrao=None):
    try:
        from memory.config_manager import get_plugin_setting
        v = get_plugin_setting(NAMESPACE, chave, padrao)
        return padrao if v in (None, "") else v
    except Exception:
        return padrao


def config_bool(chave: str, padrao: bool = True) -> bool:
    v = config(chave, padrao)
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("false", "0", "nao", "não", "off", "no", "")


# ── estado ────────────────────────────────────────────────────────────────────
def _gravar() -> None:
    try:
        with _lock:
            dados = dict(_estado)
            dados["recados"] = list(dados.get("recados") or [])
            dados["retorno"] = None                  # voltar a dormir não sobrevive a um reinício
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        tmp = ARQ.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(ARQ)
    except Exception as e:
        print(f"[Sono] não gravei o estado: {e}")


def dormindo() -> bool:
    """O JARVIS está no modo dormir (por pedido). A espera da palavra de ativação NÃO conta."""
    return bool(_estado.get("dormindo"))


def estado() -> dict:
    with _lock:
        e = dict(_estado)
        e["recados"] = list(e.get("recados") or [])
    return e


def ultimo_acordar() -> dict:
    return dict(_ultimo)


def dormir(motivo: str = "pedido", ate: float = 0.0, rotina: bool = False, alarme: bool = False,
           agora: float | None = None) -> dict:
    """Entra no modo dormir (ou, se já dorme, troca a hora de acordar). Devolve o estado."""
    agora = time.time() if agora is None else agora
    with _lock:
        ja = bool(_estado["dormindo"])
        if not ja:
            _estado.update(_vazio())
            _estado.update(dormindo=True, desde=agora)
        _estado.update(ate=max(0.0, float(ate or 0.0)), motivo=str(motivo or "")[:80],
                       rotina=bool(rotina) or (ja and bool(_estado["rotina"])),
                       alarme=bool(alarme) and bool(ate), retorno=None)
        e = dict(_estado)
    _gravar()
    return e


def acordar(motivo: str = "pedido", agora: float | None = None) -> dict | None:
    """Sai do modo dormir. Devolve o que aconteceu (para o bom dia), ou None se não dormia."""
    agora = time.time() if agora is None else agora
    with _lock:
        if not _estado["dormindo"]:
            return None
        e = dict(_estado)
        pela_hora = bool(e["ate"]) and agora >= e["ate"] - 1
        info = {"motivo": str(motivo or ""), "desde": e["desde"], "ate": e["ate"], "agora": agora,
                "dormiu_s": max(0.0, agora - e["desde"]), "rotina": bool(e["rotina"]),
                "tem_alarme": bool(e["alarme"]), "pela_hora": pela_hora,
                "alarme": bool(e["alarme"]) and pela_hora or str(motivo) == "despertador",
                "recados": list(e.get("recados") or [])}
        _estado.update(_vazio())
        _ultimo.update(acordou=agora, motivo=info["motivo"])
    _gravar()
    return info


def limpar() -> None:
    with _lock:
        _estado.update(_vazio())
    try:
        ARQ.unlink(missing_ok=True)
    except Exception:
        pass


def deve_acordar(agora: float | None = None) -> bool:
    agora = time.time() if agora is None else agora
    with _lock:
        return bool(_estado["dormindo"] and _estado["ate"] and agora >= _estado["ate"])


def motivo_da_hora() -> str:
    return "despertador" if _estado.get("alarme") else "hora de acordar"


def restaurar(agora: float | None = None) -> dict | None:
    """Ao abrir: se o JARVIS dormia quando fechou (o PC reiniciou de madrugada), volta dormindo."""
    agora = time.time() if agora is None else agora
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(d, dict) or not d.get("dormindo"):
        return None
    try:
        ate, desde = float(d.get("ate") or 0.0), float(d.get("desde") or 0.0)
    except (TypeError, ValueError):
        limpar()
        return None
    valido = (agora <= ate + ATRASO_MAX_S) if ate else (0 <= agora - desde <= SEM_HORA_MAX_S)
    if not valido:
        limpar()
        return None
    with _lock:
        _estado.update(_vazio())
        for k, padrao in _vazio().items():
            if k in d and k != "retorno":
                _estado[k] = d[k] if not isinstance(padrao, list) else list(d[k] or [])
        _estado["dormindo"] = True
    return estado()


# ── acordou no meio da noite → volta a dormir sozinho ────────────────────────
def voltar_a_dormir(depois_s: float = 120.0, ate: float = 0.0, rotina: bool = True, alarme: bool = False,
                    agora: float | None = None) -> None:
    """Depois de um aviso urgente ou de uma pergunta de madrugada: dorme de novo após `depois_s`
    sem ninguém falar com o JARVIS (o main.py confere a cada 5 s)."""
    agora = time.time() if agora is None else agora
    with _lock:
        _estado["retorno"] = {"depois_de": agora + max(10.0, depois_s), "ocioso_s": max(10.0, depois_s),
                              "ate": float(ate or 0.0), "rotina": bool(rotina), "alarme": bool(alarme)}


def cancelar_retorno() -> None:
    with _lock:
        _estado["retorno"] = None


def retorno_pendente(agora: float, ocioso_s: float) -> dict | None:
    """A hora de voltar a dormir chegou? (pura sobre o estado em memória)"""
    with _lock:
        r = _estado.get("retorno")
        if not r or _estado["dormindo"]:
            return None
        if r["ate"] and agora >= r["ate"]:
            _estado["retorno"] = None                 # já passou da hora de acordar: fica acordado
            return None
        if agora < r["depois_de"] or ocioso_s < r["ocioso_s"]:
            return None
        _estado["retorno"] = None
        return dict(r)


# ── o que os plugins falariam enquanto ele dorme ─────────────────────────────
_ETIQUETA = re.compile(r"^\s*\[([^\]]{1,48})\]")
_MIOLO = re.compile(r"idioma da conversa:\s*(.+?)\s*(?:N[ãa]o chame nenhuma ferramenta\.?)?\s*$", re.S | re.I)
_URGENTES = ("URGENTE", "SENTINELA", "ALARME", "DESPERTADOR", "INVAS", "INCEND", "FUMACA", "EMERG", "CRITIC",
             "SEGURANCA", "INTRUSO", "SOS", "ACORDAR")
_TEXTO_URGENTE = re.compile(r"(?i)\b(invas|intruso|inc[eê]ndio|fuma[cç]a|vazamento de g[aá]s|socorro)")


def sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()


def etiqueta(instrucao: str) -> str:
    m = _ETIQUETA.match(str(instrucao or ""))
    return m.group(1).strip() if m else ""


def texto_do_aviso(instrucao: str) -> str:
    """'[DOWNLOAD] Diga ao usuário, … no idioma da conversa: X terminou. Não chame…' → 'X terminou.' (pura)"""
    t = " ".join(str(instrucao or "").split())
    m = _MIOLO.search(t)
    if m:
        return m.group(1).strip()
    return _ETIQUETA.sub("", t).strip()[:240]


def eh_urgente(instrucao: str) -> bool:
    """Passa mesmo com o JARVIS dormindo (e acorda ele)? (pura)"""
    e = sem_acento(etiqueta(instrucao)).upper()
    if any(x in e for x in _URGENTES):
        return True
    return bool(_TEXTO_URGENTE.search(texto_do_aviso(instrucao)))


def segurar(instrucao: str, agora: float | None = None) -> bool:
    """Dormindo: guarda a fala pedida por um plugin para o "Enquanto eu dormia…".
    False = não guardou (é urgente, ou ele não está dormindo): a fala segue."""
    if eh_urgente(instrucao):
        return False
    texto = texto_do_aviso(instrucao)
    with _lock:
        if not _estado["dormindo"]:
            return False
        recs = _estado.setdefault("recados", [])
        if texto and all(r.get("texto") != texto for r in recs[-10:]):    # o mesmo aviso não entra duas vezes
            recs.append({"ts": time.time() if agora is None else agora, "texto": texto[:300],
                         "etiqueta": etiqueta(instrucao)[:40]})
            del recs[:-MAX_RECADOS]
    _gravar()
    return True


def lista_recados(recados: list[dict], maximo: int = 12) -> str:
    """'- 02:14 O download terminou.' por linha (pura)."""
    linhas = []
    for r in (recados or [])[-maximo:]:
        try:
            h = datetime.fromtimestamp(float(r.get("ts") or 0)).strftime("%H:%M")
        except (OSError, OverflowError, ValueError):
            h = "--:--"
        linhas.append(f"- {h} {r.get('texto', '')}")
    if len(recados or []) > maximo:
        linhas.append(f"- (e mais {len(recados) - maximo} avisos no registro)")
    return "\n".join(linhas)


def instrucao_recados(recados: list[dict]) -> str:
    """O pedido de fala do 'Enquanto eu dormia…' (pura). '' sem recados."""
    if not recados:
        return ""
    return ("[ENQUANTO EU DORMIA] Você acabou de sair do modo dormir. Estes avisos chegaram enquanto você "
            "dormia:\n" + lista_recados(recados) + "\nConte ao usuário em até 3 frases curtas, no idioma da "
            "conversa, começando com 'Enquanto eu dormia'. Não chame nenhuma ferramenta.")


# ── avisar os plugins (modo_dormir: bom dia e diário do sono) ────────────────
def ao_acordar(fn: Callable[[dict], bool], chave: str = "") -> None:
    """fn(info) → True se já falou com o usuário (aí o main.py não fala o resumo)."""
    _ouvintes[chave or getattr(fn, "__module__", "") or repr(fn)] = fn


def avisar_ouvintes(info: dict) -> bool:
    tratou = False
    for fn in list(_ouvintes.values()):
        try:
            tratou = bool(fn(info)) or tratou
        except Exception as e:
            print(f"[Sono] ao acordar: {e}")
    return tratou


# ── horários falados ─────────────────────────────────────────────────────────
_NUM = {"zero": 0, "uma": 1, "um": 1, "duas": 2, "dois": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
        "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14,
        "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
        "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50}


def _numero_por_extenso(t: str) -> str:
    """'sete e meia' → '7 e 30', 'seis e quarenta e cinco' → '6 e 45', 'vinte e duas' → '22' (pura)."""
    t = re.sub(r"\be meia\b", " e 30", t)
    palavras, saida, i = t.split(), [], 0
    while i < len(palavras):
        p = palavras[i]
        if p in _NUM:
            v = _NUM[p]
            if v >= 20 and i + 2 < len(palavras) and palavras[i + 1] == "e" and palavras[i + 2] in _NUM \
                    and _NUM[palavras[i + 2]] < 10:
                v += _NUM[palavras[i + 2]]
                i += 2
            saida.append(str(v))
        else:
            saida.append(p)
        i += 1
    return " ".join(saida)


def ler_hora(texto) -> tuple[int, int] | None:
    """'07:30', '7h30', '7h', 'às 7', '7 e meia', '6 e 45', 'meia-noite', 'meio-dia', '10 da noite' (pura)."""
    t = sem_acento(str(texto or "")).lower().strip()
    if not t:
        return None
    if "meia-noite" in t or "meia noite" in t:
        return 0, 0
    if "meio-dia" in t or "meio dia" in t:
        return 12, 30 if "e meia" in t else 0
    t = _numero_por_extenso(t)
    m = re.search(r"(\d{1,2})(?:\s*[:h.]\s*(\d{1,2})|\s+e\s+(\d{1,2}))?", t)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2) or m.group(3) or 0)
    if ("da noite" in t or "da tarde" in t or "pm" in t) and h < 12:
        h += 12
    if "da manha" in t and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def interpretar_hora(texto, agora: datetime | None = None) -> datetime | None:
    """A PRÓXIMA vez que der esse horário (hoje, ou amanhã se já passou) (pura)."""
    hm = ler_hora(texto)
    if hm is None:
        return None
    agora = agora or datetime.now()
    alvo = agora.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
    if alvo <= agora:
        alvo += timedelta(days=1)
    return alvo


def hora_txt(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%H:%M")
    except (OSError, OverflowError, ValueError, TypeError):
        return "?"


def como_acordar(hey_jarvis: bool = False, palmas: bool = True, voz: bool = False, atalho: bool = False) -> str:
    """'Para me acordar: bata duas palmas, aperte Ctrl+Alt+D ou toque em ACORDAR AGORA.' (pura)"""
    jeitos = []
    if hey_jarvis:
        jeitos.append("diga 'Hey Jarvis'")
    if voz:
        jeitos.append("diga 'Jarvis, acorda'")
    if palmas:
        jeitos.append("bata duas palmas")
    if atalho:
        jeitos.append("aperte Ctrl+Alt+D")
    jeitos.append("toque em ACORDAR AGORA (ou digite algo)")
    corpo = jeitos[0] if len(jeitos) == 1 else ", ".join(jeitos[:-1]) + " ou " + jeitos[-1]
    return f"Para me acordar: {corpo}."


# ── duas palmas ──────────────────────────────────────────────────────────────
class DetectorPalmas:
    """Duas (ou três) palmas seguidas, com silêncio antes e depois.

    Palma = subida brusca (o trecho de 16 ms fica muito acima dos 96 ms
    anteriores) e queda rápida (50–100 ms depois já caiu para menos de 30%).
    Fala, música e TV não têm essa queda; digitar dá estalos demais seguidos
    (o grupo precisa ter 2 ou 3 e estar isolado). O main.py ainda ignora as
    palmas se o teclado/mouse foi usado no último segundo e meio.
    Tudo no próprio PC, alguns microssegundos por bloco do microfone.
    """

    SUB = 256                              # 16 ms a 16 kHz

    def __init__(self, taxa: int = TAXA, pico_min: float = 7000.0, subida: float = 4.0, queda: float = 0.3,
                 gap_min: float = 0.12, gap_max: float = 0.75, isolar_antes: float = 0.8, isolar_depois: float = 0.85,
                 refratario: float = 2.0):
        self.taxa, self.pico_min, self.subida, self.queda = taxa, pico_min, subida, queda
        self.gap_min, self.gap_max = gap_min, gap_max
        self.isolar_antes, self.isolar_depois, self.refratario = isolar_antes, isolar_depois, refratario
        self.zerar()

    def zerar(self) -> None:
        self._t = 0.0
        self._hist: list[float] = []               # rms dos últimos trechos de 16 ms
        self._cands: list[dict] = []               # palmas esperando a confirmação da queda
        self._grupo: list[float] = []
        self._grupo_ok = True
        self._ultimo_evento = -99.0
        self._bloqueado_ate = 0.0
        self._resto = None

    def _evento(self, t: float) -> None:
        if self._grupo:
            gap = t - self._grupo[-1]
            if gap < self.gap_min:                 # o eco da mesma palma
                return
            if gap > self.gap_max:
                self._grupo_ok = False
            self._grupo.append(t)
        else:
            self._grupo = [t]
            self._grupo_ok = (t - self._ultimo_evento) >= self.isolar_antes
        self._ultimo_evento = t

    @staticmethod
    def agudos(x, taxa: int = TAXA, corte: float = 1200.0) -> float:
        """Fração da energia acima de `corte` Hz. Palma é 'chiado' (alta); batida na porta e
        passos são 'tum' (baixa) (pura)."""
        import numpy as np
        if not len(x):
            return 0.0
        e = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
        f = np.fft.rfftfreq(len(x), 1 / taxa)
        total = float(e.sum())
        return float(e[f >= corte].sum()) / total if total > 0 else 0.0

    def _trecho(self, x) -> bool:
        import numpy as np
        t = self._t
        self._t += len(x) / self.taxa
        a = np.abs(x)
        pico = float(a.max()) if len(a) else 0.0
        rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
        antes = self._hist[-6:]
        base = (sum(antes) / len(antes)) if antes else rms
        # 1) confirma os candidatos: 48–96 ms depois, caiu bem?
        for c in list(self._cands):
            c["depois"].append(rms)
            if len(c["depois"]) >= 6:
                self._cands.remove(c)
                ref = max(c["rms"], c["depois"][0])     # a palma pode cair no fim do trecho
                cauda = sum(c["depois"][2:6]) / 4
                if cauda < self.queda * ref:
                    self._evento(c["t"])
        # 2) este trecho começa uma palma?
        if (pico >= self.pico_min and rms >= self.subida * max(base, 20.0) and t >= self._bloqueado_ate
                and not self._cands and self.agudos(x, self.taxa) >= 0.3):
            self._cands.append({"t": t, "rms": rms, "depois": []})
        self._hist.append(rms)
        del self._hist[:-24]
        # 3) fecha o grupo depois do silêncio de isolamento
        if self._grupo and not self._cands and (self._t - self._grupo[-1]) >= self.isolar_depois:
            grupo, ok = self._grupo, self._grupo_ok
            self._grupo, self._grupo_ok = [], True
            if ok and 2 <= len(grupo) <= 3 and self._t >= self._bloqueado_ate:
                self._bloqueado_ate = self._t + self.refratario
                return True
        return False

    def bloco(self, amostras) -> bool:
        """Um bloco do microfone (int16, qualquer formato). True quando ouviu as duas palmas."""
        import numpy as np
        x = np.asarray(amostras).reshape(-1).astype(np.float32)
        if self._resto is not None and len(self._resto):
            x = np.concatenate([self._resto, x])
            self._resto = None
        disparou = False
        n = (len(x) // self.SUB) * self.SUB
        for i in range(0, n, self.SUB):
            disparou = self._trecho(x[i:i + self.SUB]) or disparou
        if n < len(x):
            self._resto = x[n:]
        return disparou


# ── "Jarvis, acorda" no próprio PC ──────────────────────────────────────────
NOMES = ("jarvis", "jarves", "jarvas", "jarvi", "jarbas", "jervis", "javis", "chavis", "jarviz", "djarvis",
         "jarvys", "jarviss", "garvis")


def contem_chamado(texto: str) -> bool:
    """O texto reconhecido chama o JARVIS? ('Jarvis, acorda', 'ei Jarbas', 'Jarvis!') (pura)"""
    t = re.sub(r"[^a-z ]", " ", sem_acento(texto).lower())
    palavras = t.split()
    return any(p in NOMES for p in palavras) or "jarvis" in "".join(palavras)


class OuvidoAcordar:
    """Só enquanto dorme: separa as falas curtas do microfone e reconhece no próprio PC
    (faster-whisper, modelo 'tiny', ~75 MB na primeira vez) se alguém chamou o JARVIS.
    Nada vai para a internet. Sem o pacote, nem liga. O modelo sai da memória ao acordar."""

    LIMIAR_MIN = 450.0
    FIM_S = 0.55
    MAX_S = 3.5
    MIN_S = 0.35

    def __init__(self, on_detect: Callable[[], None], modelo: str = "tiny",
                 transcrever: Callable | None = None, logger: Callable[[str], None] = print):
        self._on_detect = on_detect
        self._modelo_nome = modelo or "tiny"
        self._transcrever = transcrever            # testes: fn(np.ndarray float32 16 kHz) -> str
        self._log = logger
        self._fila: queue.Queue = queue.Queue(maxsize=200)
        self._falas: queue.Queue = queue.Queue(maxsize=2)
        self._rodando = False
        self._threads: list[threading.Thread] = []
        self._modelo = None
        self.zerar_segmento()

    @staticmethod
    def disponivel() -> bool:
        try:
            import importlib.util
            return importlib.util.find_spec("faster_whisper") is not None
        except Exception:
            return False

    # segmentação (determinística, nos testes)
    def zerar_segmento(self) -> None:
        self._fundo = 200.0
        self._blocos: list = []
        self._previa: list = []
        self._voz_seguida = 0
        self._silencio_s = 0.0
        self._voz_s = 0.0
        self._falando = False

    def segmentar(self, bloco):
        """Recebe um bloco int16; devolve a fala inteira (float32, -1..1) quando ela termina."""
        import numpy as np
        x = np.asarray(bloco).reshape(-1).astype(np.float32)
        if not len(x):
            return None
        dur = len(x) / TAXA
        rms = float(np.sqrt(np.mean(x * x)))
        voz = rms >= max(self.LIMIAR_MIN, 3.0 * self._fundo)
        if not self._falando:
            if voz:
                self._voz_seguida += 1
                self._blocos.append(x)
                if self._voz_seguida >= 2:
                    self._falando = True
                    self._voz_s = dur * self._voz_seguida
                    self._blocos = self._previa + self._blocos
                    self._previa = []
            else:
                self._voz_seguida = 0
                self._previa = (self._previa + self._blocos + [x])[-3:]
                self._blocos = []
                self._fundo = 0.95 * self._fundo + 0.05 * rms
            return None
        self._blocos.append(x)
        self._silencio_s = 0.0 if voz else self._silencio_s + dur
        self._voz_s += dur if voz else 0.0
        total = sum(len(b) for b in self._blocos) / TAXA
        if self._silencio_s >= self.FIM_S or total >= self.MAX_S:
            audio = np.concatenate(self._blocos)
            longa, curta = total >= self.MAX_S, self._voz_s < self.MIN_S
            self._blocos, self._previa, self._falando, self._voz_seguida, self._silencio_s = [], [], False, 0, 0.0
            self._voz_s = 0.0
            if longa or curta:
                return None                        # conversa comprida (TV) ou barulho curto: ignora
            return np.clip(audio / 32768.0, -1.0, 1.0).astype(np.float32)
        return None

    def iniciar(self) -> bool:
        if self._rodando:
            return True
        if self._transcrever is None and not self.disponivel():
            return False
        self._rodando = True
        self._threads = [threading.Thread(target=self._laco_segmentos, daemon=True, name="sono_ouvido"),
                         threading.Thread(target=self._laco_texto, daemon=True, name="sono_reconhece")]
        for t in self._threads:
            t.start()
        return True

    def parar(self) -> None:
        self._rodando = False
        for f in (self._fila, self._falas):
            try:
                f.put_nowait(None)
            except queue.Full:
                pass
        self._modelo = None                        # libera a memória (~150 MB)

    def feed(self, bloco) -> None:
        """Chamado na callback do microfone: só uma cópia numa fila."""
        if not self._rodando:
            return
        try:
            self._fila.put_nowait(bloco.copy())
        except (queue.Full, AttributeError):
            pass

    def _laco_segmentos(self) -> None:
        while self._rodando:
            b = self._fila.get()
            if b is None:
                break
            try:
                fala = self.segmentar(b)
            except Exception:
                fala = None
            if fala is not None:
                try:
                    self._falas.put_nowait(fala)
                except queue.Full:
                    pass                           # ainda reconhecendo a anterior: pula esta

    def _texto(self, audio) -> str:
        if self._transcrever is not None:
            return str(self._transcrever(audio) or "")
        if self._modelo is None:
            from faster_whisper import WhisperModel
            self._log(f"[Sono] carregando o reconhecimento local ({self._modelo_nome})…")
            self._modelo = WhisperModel(self._modelo_nome, device="cpu", compute_type="int8", cpu_threads=2)
        segs, _info = self._modelo.transcribe(audio, language="pt", beam_size=1, vad_filter=False,
                                              condition_on_previous_text=False, without_timestamps=True)
        partes = []
        for s in segs:
            if getattr(s, "no_speech_prob", 0.0) < 0.6 and getattr(s, "avg_logprob", 0.0) > -1.3:
                partes.append(s.text)
        return " ".join(partes)

    def _laco_texto(self) -> None:
        while self._rodando:
            fala = self._falas.get()
            if fala is None or not self._rodando:
                break
            try:
                texto = self._texto(fala)
            except Exception as e:
                self._log(f"[Sono] reconhecimento local indisponível: {e}")
                self._rodando = False
                break
            if texto.strip():
                print(f"[Sono] ouvi: {texto.strip()[:60]}")
            if contem_chamado(texto):
                try:
                    self._on_detect()
                except Exception as e:
                    print(f"[Sono] acordar: {e}")
                break


def tem_voz(pcm: bytes, limiar: float = 500.0) -> bool:
    """Um pedaço de áudio int16 tem voz (não é só o silêncio do mãos-livres)? (pura)"""
    try:
        import numpy as np
        x = np.frombuffer(pcm or b"", dtype=np.int16).astype(np.float32)
        return bool(len(x)) and float(np.sqrt(np.mean(x * x))) >= limiar
    except Exception:
        return False
