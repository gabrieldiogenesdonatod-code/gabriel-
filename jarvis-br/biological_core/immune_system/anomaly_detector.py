"""
Camada 1 (parte estatística) — detector de anomalias: comportamento fora do normal.

    • lentidão: cada ferramenta tem a sua média e variação de tempo (média móvel exponencial);
      uma chamada muito acima do normal dela vira sintoma (z alto E pelo menos 2× a média);
    • rajada de erros: taxa de falha recente muito acima da taxa histórica da ferramenta;
    • vazamento de memória: reta de tendência da memória do JARVIS na última hora
      (mínimos quadrados) — sobe sem parar? avisa e estima quando passa do limite;
    • tempestade de eventos: o sistema nervoso disparando muito acima do normal (um laço);
    • threads vazando: número de threads crescendo muito acima da base.

Os limites são adaptativos: um alarme falso (você liberou na hora) deixa aquela ferramenta mais
tolerante; um problema que se confirmou deixa mais atenta.
"""

from __future__ import annotations

import math
import time
from collections import deque


class MediaMovel:
    def __init__(self, alfa: float = 0.1):
        self.alfa, self.media, self.var, self.n = alfa, 0.0, 0.0, 0

    def z(self, x: float) -> float:
        if self.n < 2:
            return 0.0
        return (x - self.media) / max(math.sqrt(self.var), 1e-9)

    def atualizar(self, x: float) -> None:
        if self.n == 0:
            self.media = x
        else:
            d = x - self.media
            self.media += self.alfa * d
            self.var = (1 - self.alfa) * (self.var + self.alfa * d * d)
        self.n += 1


def tendencia(pontos: list[tuple[float, float]]) -> tuple[float, float]:
    """(inclinação por hora, r²) da reta dos pontos (ts, valor)."""
    n = len(pontos)
    if n < 3:
        return 0.0, 0.0
    t0 = pontos[0][0]
    xs = [(t - t0) / 3600 for t, _ in pontos]
    ys = [v for _, v in pontos]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return 0.0, 0.0
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    syy = sum((y - my) ** 2 for y in ys)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else 0.0
    return b, r2


class DetectorAnomalias:
    def __init__(self, minimo_amostras: int = 10, z_padrao: float = 4.0):
        self.minimo = minimo_amostras
        self.z_padrao = z_padrao
        self.z_limiar: dict[str, float] = {}
        self.lat: dict[str, MediaMovel] = {}
        self.janela: dict[str, deque] = {}
        self.taxa: dict[str, MediaMovel] = {}
        self.memoria_pontos: deque = deque(maxlen=720)
        self.eventos = MediaMovel(0.05)
        self.threads_base: float | None = None
        self.ultimo_alarme: dict[str, float] = {}

    def _alarme(self, chave: str, intervalo_s: float = 600) -> bool:
        agora = time.time()
        if agora - self.ultimo_alarme.get(chave, 0) < intervalo_s:
            return False
        self.ultimo_alarme[chave] = agora
        return True

    def latencia(self, ferramenta: str, ms: float) -> dict | None:
        m = self.lat.setdefault(ferramenta, MediaMovel())
        z = m.z(ms)
        anomalo = (m.n >= self.minimo and z > self.z_limiar.get(ferramenta, self.z_padrao)
                   and ms > 2 * m.media and ms > 1500)
        m.atualizar(min(ms, m.media * 5 if m.n >= self.minimo else ms))     # um travão não estraga a média
        if anomalo and self._alarme(f"lat:{ferramenta}"):
            return {"tipo": "lentidao", "ferramenta": ferramenta, "ms": round(ms), "media_ms": round(m.media), "z": round(z, 1),
                    "mensagem": f"'{ferramenta}' levou {ms / 1000:.1f} s; o normal dela é {m.media / 1000:.1f} s"}
        return None

    def resultado(self, ferramenta: str, ok: bool) -> dict | None:
        j = self.janela.setdefault(ferramenta, deque(maxlen=20))
        t = self.taxa.setdefault(ferramenta, MediaMovel(0.02))
        j.append(not ok)
        historica = t.media if t.n >= 30 else 0.1
        t.atualizar(0.0 if ok else 1.0)
        recentes = list(j)[-10:]
        falhas = sum(recentes)
        if len(recentes) >= 8 and falhas >= 5 and falhas / len(recentes) >= 0.5 and historica < 0.2 and self._alarme(f"erro:{ferramenta}"):
            return {"tipo": "rajada_de_erros", "ferramenta": ferramenta, "taxa": round(falhas / len(recentes), 2),
                    "historica": round(historica, 2),
                    "mensagem": f"'{ferramenta}' falhou {falhas} das últimas {len(recentes)} vezes (o normal é {historica:.0%})"}
        return None

    def memoria(self, ts: float, rss_mb: float | None, limite_mb: float = 2000) -> dict | None:
        if rss_mb is None:
            return None
        self.memoria_pontos.append((ts, float(rss_mb)))
        pts = list(self.memoria_pontos)
        if len(pts) < 30 or pts[-1][0] - pts[0][0] < 3600:
            return None
        b, r2 = tendencia(pts)
        if b > 50 and r2 > 0.7 and rss_mb > 400 and self._alarme("memoria", 3 * 3600):
            horas = (limite_mb - rss_mb) / b if b > 0 and rss_mb < limite_mb else 0
            return {"tipo": "vazamento_de_memoria", "mb_por_hora": round(b), "r2": round(r2, 2), "rss_mb": round(rss_mb),
                    "horas_ate_limite": round(horas, 1),
                    "mensagem": f"a memória do JARVIS sobe ~{b:.0f} MB por hora sem parar ({rss_mb:.0f} MB agora)"
                                + (f"; no ritmo atual passa de {limite_mb:.0f} MB em ~{horas:.1f} h" if horas > 0 else "")}
        return None

    def previsao_memoria(self) -> dict:
        b, r2 = tendencia(list(self.memoria_pontos))
        return {"mb_por_hora": round(b, 1), "confianca": round(r2, 2), "amostras": len(self.memoria_pontos)}

    def taxa_eventos(self, por_minuto: float) -> dict | None:
        m = self.eventos
        anomalo = m.n >= 30 and por_minuto > max(200, 5 * max(m.media, 1))
        m.atualizar(min(por_minuto, max(m.media * 3, 50)) if m.n >= 30 else por_minuto)
        if anomalo and self._alarme("eventos"):
            return {"tipo": "tempestade_de_eventos", "por_minuto": round(por_minuto), "normal": round(m.media),
                    "mensagem": f"o sistema nervoso disparou {por_minuto:.0f} eventos por minuto (o normal é {m.media:.0f})"}
        return None

    def threads(self, n: int) -> dict | None:
        if self.threads_base is None:
            self.threads_base = float(n)
            return None
        self.threads_base = min(self.threads_base, float(n)) * 0.999 + 0.001 * n
        if n > self.threads_base + 60 and self._alarme("threads", 3600):
            return {"tipo": "threads_vazando", "threads": n, "base": round(self.threads_base),
                    "mensagem": f"{n} threads abertas (a base é ~{self.threads_base:.0f}): algo está abrindo thread sem fechar"}
        return None

    def ajustar(self, ferramenta: str, alarme_falso: bool) -> float:
        z = self.z_limiar.get(ferramenta, self.z_padrao)
        z = min(8.0, z + 0.5) if alarme_falso else max(3.0, z - 0.25)
        self.z_limiar[ferramenta] = z
        return z

    def semear(self, chamadas: list[dict]) -> int:
        """Aprende o normal de cada ferramenta com o diário de uso (core/registro_uso)."""
        n = 0
        for c in chamadas[-3000:]:
            try:
                self.lat.setdefault(c["ferramenta"], MediaMovel()).atualizar(float(c["ms"]))
                self.taxa.setdefault(c["ferramenta"], MediaMovel(0.02)).atualizar(0.0 if c.get("ok") else 1.0)
                n += 1
            except Exception:
                continue
        return n

    def estado(self) -> dict:
        return {"ferramentas_conhecidas": len(self.lat), "memoria": self.previsao_memoria(),
                "eventos_normal_por_min": round(self.eventos.media, 1), "threads_base": round(self.threads_base or 0),
                "limiares_ajustados": {k: v for k, v in self.z_limiar.items() if v != self.z_padrao}}
