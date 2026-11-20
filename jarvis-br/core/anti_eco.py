"""
Anti-eco (fork PT-BR 3.2): o JARVIS não responde mais a própria voz.

Por que ainda acontecia
    O microfone fica fechado para o modelo enquanto o JARVIS fala, e depois disso havia uma
    "cauda" curta (latência da placa + 0,25 s). Só que caixa Bluetooth, TV/HDMI e os "efeitos de
    som" do Windows atrasam o áudio além do que a placa informa: o fim da frase dele ainda saía
    da caixa quando o microfone já tinha voltado a mandar áudio, e o modelo respondia a si mesmo.
    A interrupção por voz (ligada por padrão) piorava numa sala com eco, e o som tocado pelos
    plugins (alarme, efeitos, vozes) nem passava por proteção nenhuma.

O que este módulo faz (sem precisar de pacote novo)
    1. ECO PELO TEXTO: o Gemini transcreve o que ouve. Se o que "você disse" é, em boa parte, a
       mesma sequência de palavras que o JARVIS falou nos últimos 25 s, é eco: a resposta a ele é
       cortada e descartada, e não vai para o registro como fala sua.
    2. APRENDE A SALA: cada eco pego aumenta a cauda (+0,35 s, até +1,5 s) e fica salvo
       (memory/anti_eco.json). Dois ecos em 10 minutos suspendem a interrupção por voz por 24 h
       (ESC, Ctrl+Alt+P e o botão continuam cortando a fala).
    3. SOM DOS PLUGINS: o que os plugins tocam com sd.play conta como "o JARVIS falando".
    4. CAUDA MÍNIMA: nunca menos que 0,6 s ("eco_cauda_minima_ms" em config/api_keys.json).

Com fone de ouvido nada disso atrapalha: sem eco, a cauda continua curta e a interrupção por voz ligada.
"""

from __future__ import annotations

import difflib
import json
import re
import threading
import time
import unicodedata
from collections import deque
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / "memory" / "anti_eco.json"
JANELA_S = 25.0
EXTRA_PASSO, EXTRA_MAX = 0.35, 1.5
CAUDA_MINIMA_PADRAO = 0.6


def palavras(texto: str) -> list[str]:
    t = unicodedata.normalize("NFKD", str(texto or "").lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", t)


def cobertura(entrada: list[str], falado: list[str]) -> float:
    """Quanto da entrada aparece, na mesma ordem, no que foi falado (0 a 1). Pura."""
    if not entrada or not falado:
        return 0.0
    m = difflib.SequenceMatcher(None, falado, entrada, autojunk=False)
    return sum(b.size for b in m.get_matching_blocks()) / len(entrada)


class AntiEco:
    def __init__(self, arquivo: Path | None = None, agora=time.monotonic):
        self.arquivo = Path(arquivo or ARQ)
        self.agora = agora
        self._lock = threading.Lock()
        self._falas: deque[tuple[float, list[str]]] = deque(maxlen=200)
        self._ecos: deque[float] = deque(maxlen=20)
        self._plugin_ate = 0.0
        try:
            d = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except Exception:
            d = {}
        self.extra = min(EXTRA_MAX, max(0.0, float(d.get("cauda_extra_s", 0.0))))
        self.suspenso_ate_ts = float(d.get("barge_in_suspenso_ate", 0.0))   # relógio de parede (sobrevive a reinício)
        self.total = int(d.get("ecos_total", 0))

    # ── o que o JARVIS falou ──────────────────────────────────────────────────
    def falou(self, texto: str) -> None:
        ws = palavras(texto)
        if ws:
            with self._lock:
                self._falas.append((self.agora(), ws))

    def _recente(self) -> list[str]:
        limite = self.agora() - JANELA_S
        with self._lock:
            out = []
            for t, ws in self._falas:
                if t >= limite:
                    out += ws
            return out

    def similaridade(self, entrada: str) -> float:
        return cobertura(palavras(entrada), self._recente())

    def eh_eco(self, entrada: str, minimo_palavras: int = 3, limiar: float = 0.6) -> bool:
        """Frases de 1–2 palavras ("sim", "para") nunca contam como eco: podem ser você."""
        ws = palavras(entrada)
        return len(ws) >= minimo_palavras and cobertura(ws, self._recente()) >= limiar

    # ── aprendizado ───────────────────────────────────────────────────────────
    def registrar_eco(self) -> list[str]:
        agora = self.agora()
        feito = []
        with self._lock:
            self._ecos.append(agora)
            self.total += 1
            if self.extra < EXTRA_MAX:
                self.extra = min(EXTRA_MAX, self.extra + EXTRA_PASSO)
                feito.append(f"cauda +{EXTRA_PASSO:.2f} s (agora +{self.extra:.2f} s)")
            if sum(1 for t in self._ecos if agora - t <= 600) >= 2 and not self.barge_in_suspenso():
                self.suspenso_ate_ts = time.time() + 86400
                feito.append("interrupção por voz suspensa por 24 h")
        self._gravar()
        return feito

    def barge_in_suspenso(self) -> bool:
        return time.time() < self.suspenso_ate_ts

    def barge_in_permitido(self) -> bool:
        return not self.barge_in_suspenso()

    def cauda_s(self, base: float) -> float:
        try:
            from memory.config_manager import load_api_keys
            minimo = float(load_api_keys().get("eco_cauda_minima_ms", CAUDA_MINIMA_PADRAO * 1000)) / 1000
        except Exception:
            minimo = CAUDA_MINIMA_PADRAO
        return max(minimo, base) + self.extra

    def zerar(self) -> None:
        """'Jarvis, zera o anti-eco' (trocou de caixa para fone, por exemplo)."""
        with self._lock:
            self.extra, self.suspenso_ate_ts = 0.0, 0.0
            self._ecos.clear()
        self._gravar()

    # ── som dos plugins ───────────────────────────────────────────────────────
    def marcar_audio_plugin(self, segundos: float) -> None:
        with self._lock:
            self._plugin_ate = max(self._plugin_ate, self.agora() + max(0.0, segundos) + 0.6)

    def audio_plugin_tocando(self) -> bool:
        return self.agora() < self._plugin_ate

    def estado(self) -> dict:
        return {"cauda_extra_s": round(self.extra, 2), "ecos_total": self.total,
                "interrupcao_por_voz": "suspensa" if self.barge_in_suspenso() else "permitida"}

    def _gravar(self) -> None:
        try:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.arquivo.with_suffix(".tmp")
            tmp.write_text(json.dumps({"cauda_extra_s": self.extra, "barge_in_suspenso_ate": self.suspenso_ate_ts,
                                       "ecos_total": self.total}), encoding="utf-8")
            tmp.replace(self.arquivo)
        except Exception:
            pass


_inst: AntiEco | None = None


def get() -> AntiEco:
    global _inst
    if _inst is None:
        _inst = AntiEco()
    return _inst
