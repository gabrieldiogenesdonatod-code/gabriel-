"""
HUD 3.9 desenhado DENTRO da janela principal (fork PT-BR 3.9.1) — o centro do HudCanvas no estilo "hud39".

A mesma arte de hud39/static/hud.jpg, com os números reais e as animações pintadas pelo QPainter, sem
navegador. Só ocupa o lugar do rosto: caixa de texto, mudo, falar e microfone continuam onde sempre estiveram.

Desempenho: a arte escalada fica em cache por tamanho; os números vêm da fotografia da telemetria a cada
1,5 s (uma cópia de dicionário); as informações fixas são lidas uma vez numa thread. Nada aqui bloqueia a
thread da interface.
"""
from __future__ import annotations

import math
import random
import threading
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPixmap, QPolygonF, QRadialGradient)

ARTE = Path(__file__).resolve().parent / "static" / "hud.jpg"
LW, LH = 1672.0, 941.0
DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
_FONTES = ["Bahnschrift", "Rajdhani", "Agency FB", "Segoe UI", "Arial"]

CIANO = QColor(53, 214, 255)
CLARO = QColor(233, 251, 255)
LARANJA = QColor(255, 154, 31)
VERM = QColor(255, 77, 77)
VERDE = QColor(61, 255, 168)
CINZA = QColor(120, 140, 155)

# Áreas clicáveis (x, y, w, h na arte) → nome do painel. Círculos usam (cx, cy, r).
MENU = [("sistema", "SISTEMA"), ("internet", "INTERNET"), ("arquivos", "ARQUIVOS"), ("musica", "MÚSICA"),
        ("videos", "VÍDEOS"), ("jogos", "JOGOS"), ("config", "CONFIG.")]
RETANGULOS = [(94, 124 + 56 * i, 126, 42, nome) for i, (nome, _r) in enumerate(MENU)] + [
    (996, 118, 262, 240, "processos"), (1316, 118, 280, 200, "gpu"), (250, 118, 360, 128, "sistema"),
    (1062, 22, 400, 66, "discos"), (1500, 10, 160, 140, "diagnostico")]
CIRCULOS = [(60, 65, 52, "jarvis"), (318, 668, 133, "comando"), (842, 720, 82, "diagnostico"),
            (1437, 463, 107, "internet"), (1522, 794, 82, "config"), (450, 350, 85, "internet")]
DICAS = {"sistema": "Sobre o sistema", "internet": "Internet e rede", "arquivos": "Abrir pastas",
         "musica": "Controles de música", "videos": "Vídeos", "jogos": "Jogos", "config": "Configurações do HUD",
         "processos": "Processos", "gpu": "Placa de vídeo", "discos": "Memória e discos",
         "diagnostico": "Diagnóstico do sistema", "jarvis": "Sobre o J.A.R.V.I.S",
         "comando": "Escrever para o JARVIS"}


def _fonte(px: float, negrito: bool = False) -> QFont:
    f = QFont()
    f.setFamilies(_FONTES)
    f.setPixelSize(max(1, int(round(px))))
    if negrito:
        f.setWeight(QFont.Weight.DemiBold)
    return f


def _vel(b) -> str:
    if b is None:
        return "--"
    return f"{b / 1048576:.1f} MB/s" if b >= 1048576 else f"{b / 1024:.1f} KB/s"


def _pct(v) -> str:
    return "--" if v is None else f"{round(v)}%"


def _caneta(cor: QColor, larg: float, redonda: bool = False, tracejada: bool = False) -> QPen:
    pen = QPen(cor)
    pen.setWidthF(float(larg))
    if redonda:
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    if tracejada:
        pen.setStyle(Qt.PenStyle.DashLine)
    return pen


def _alpha(c: QColor, a: float) -> QColor:
    q = QColor(c)
    q.setAlphaF(max(0.0, min(1.0, a)))
    return q


class _HudBase:
    """Pinta o HUD 3.9 num QPainter e diz o que foi clicado. Sem estado de Qt próprio (não é widget).

    As subclasses (a F.R.I.D.A.Y, em friday_qt.py) trocam a arte, o tamanho virtual e as áreas clicáveis."""
    LW, LH = LW, LH
    CIRCULOS, RETANGULOS, DICAS = CIRCULOS, RETANGULOS, DICAS
    COR_ONDA = CIANO

    def __init__(self, arte: Path = ARTE):
        self._arte = QPixmap(str(arte))
        self._ondas: list = []                    # cliques recentes (x, y, t) — o anel que se expande
        self._aviso: tuple | None = None          # ("Abrindo…", t)
        self._cache: tuple | None = None          # (w, h, pixmap)
        self._dados: dict = {}
        self._fixo: dict = {}
        self._hist: dict = {}
        self._t_dados = 0.0
        self._hover: str | None = None
        self._hover_rect = None
        self._barras_dados = [0.5] * 9
        self._t_barras = 0.0
        self.ok = not self._arte.isNull()
        threading.Thread(target=self._ler_fixo, daemon=True, name="hud39-fixo").start()

    # ── dados ────────────────────────────────────────────────────────────────
    def _ler_fixo(self):
        try:
            from hud39 import sistema
            self._fixo = sistema.fixo()
        except Exception:
            self._fixo = {}

    def _atualizar(self):
        agora = time.time()
        if agora - self._t_dados < 1.5:
            return
        self._t_dados = agora
        try:
            from core import telemetria
            from hud39.sistema import processos_top
            t = telemetria.get()
            s = t.snapshot()
            disco = None
            for pt in s.get("particoes") or []:
                ponto = str(pt.get("ponto", "")).upper()
                if ponto in ("C:\\", "/"):
                    disco = pt.get("pct")
            if disco is None:
                import os
                import psutil
                try:
                    disco = psutil.disk_usage((os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else "/").percent
                except Exception:
                    disco = None
            ping = None
            for alvo in ("8.8.8.8", "1.1.1.1", "gateway"):
                v = (s.get("ping") or {}).get(alvo)
                if isinstance(v, dict) and v.get("ms") is not None:
                    ping = v["ms"]
                    break
            rede = s.get("rede") or {}
            self._dados = {"cpu": s.get("cpu"), "ram": (s.get("ram") or {}).get("pct"), "disco": disco,
                           "down": float(rede.get("down") or 0), "up": float(rede.get("up") or 0),
                           "ping": ping, "internet": s.get("internet"), "gpu": s.get("gpu"),
                           "temp": s.get("cpu_temp"), "procs": processos_top(s.get("processos") or [])}
            self._hist = {k: list(t.historico(k))[-60:] for k in ("cpu", "gpu", "temp", "down", "ram")}
        except Exception:
            pass

    # ── geometria ────────────────────────────────────────────────────────────
    def encaixe(self, W: float, H: float):
        s = min(W / self.LW, H / self.LH)
        return s, (W - self.LW * s) / 2.0, (H - self.LH * s) / 2.0

    def alvo_em(self, x: float, y: float, W: float, H: float) -> str | None:
        s, ox, oy = self.encaixe(W, H)
        if s <= 0:
            return None
        ax, ay = (x - ox) / s, (y - oy) / s
        for cx, cy, r, nome in self.CIRCULOS:
            if (ax - cx) ** 2 + (ay - cy) ** 2 <= r * r:
                return nome
        for rx, ry, rw, rh, nome in self.RETANGULOS:
            if rx <= ax <= rx + rw and ry <= ay <= ry + rh:
                return nome
        return None

    def clique(self, x: float, y: float, W: float, H: float, nome: str | None) -> None:
        """Resposta visual imediata ao clique: um anel que se expande e um aviso do que está abrindo."""
        s, ox, oy = self.encaixe(W, H)
        if s <= 0:
            return
        agora = time.time()
        self._ondas = [o for o in self._ondas if agora - o[2] < 0.8][-5:] + [((x - ox) / s, (y - oy) / s, agora)]
        if nome:
            self._aviso = (self.texto_aviso(nome), agora)

    def texto_aviso(self, nome: str) -> str:
        if nome == "comando":
            return "Pode escrever: a caixa de texto está pronta"
        return f"Abrindo {self.DICAS.get(nome, nome).lower()}…"

    def _interacao(self, p: QPainter, t: float, y_aviso: float) -> None:
        """Ondas dos cliques e o aviso (em coordenadas virtuais, já com a escala aplicada)."""
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for ox, oy, t0 in self._ondas:
            k = (t - t0) / 0.7
            if 0 <= k <= 1:
                p.setPen(_caneta(_alpha(self.COR_ONDA, 1 - k), 3 * (1 - k) + 1))
                p.drawEllipse(QPointF(ox, oy), 8 + 70 * k, 8 + 70 * k)
                p.setPen(_caneta(_alpha(self.COR_ONDA, (1 - k) * .5), 1.5))
                p.drawEllipse(QPointF(ox, oy), 4 + 40 * k, 4 + 40 * k)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if self._aviso and t - self._aviso[1] < 1.8:
            a = min(1.0, (1.8 - (t - self._aviso[1])) / 0.4)
            p.setFont(_fonte(16))
            largura = max(220.0, len(self._aviso[0]) * 8.6 + 40)
            caixa = QRectF(self.LW / 2 - largura / 2, y_aviso, largura, 32)
            p.fillRect(caixa, QColor(2, 14, 24, int(230 * a)))
            p.setPen(_caneta(_alpha(self.COR_ONDA, a), 1.2))
            p.drawRect(caixa)
            p.setPen(_alpha(CLARO, a))
            p.drawText(caixa, Qt.AlignmentFlag.AlignCenter, self._aviso[0])

    def mover(self, x, y, W, H) -> str | None:
        """Atualiza o destaque do mouse. Devolve o alvo (para o cursor e a dica)."""
        self._hover = self.alvo_em(x, y, W, H)
        self._hover_rect = None
        if self._hover:
            s, ox, oy = self.encaixe(W, H)
            ax, ay = (x - ox) / s, (y - oy) / s
            for cx, cy, r, nome in self.CIRCULOS:
                if nome == self._hover and (ax - cx) ** 2 + (ay - cy) ** 2 <= r * r:
                    self._hover_rect = ("c", cx, cy, r)
                    break
            else:
                for rx, ry, rw, rh, nome in self.RETANGULOS:
                    if nome == self._hover and rx <= ax <= rx + rw and ry <= ay <= ry + rh:
                        self._hover_rect = ("r", rx, ry, rw, rh)
                        break
        return self._hover

    def sair(self):
        self._hover = self._hover_rect = None

    # ── pintura ──────────────────────────────────────────────────────────────
    def paint(self, p: QPainter, W: int, H: int, hud) -> None:
        self._atualizar()
        s, ox, oy = self.encaixe(W, H)
        w, h = int(round(LW * s)), int(round(LH * s))
        if w < 10 or h < 10:
            return
        if self._cache is None or self._cache[:2] != (w, h):
            self._cache = (w, h, self._arte.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
        p.fillRect(QRectF(0, 0, W, H), QColor(2, 7, 13))
        p.drawPixmap(int(round(ox)), int(round(oy)), self._cache[2])

        t = time.time()
        p.save()
        p.translate(ox, oy)
        p.scale(s, s)
        p.setClipRect(QRectF(0, 0, LW, LH))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        try:
            self._animacoes(p, t, hud)
            self._textos(p, t, hud)
            self._destaque(p)
            self._pintar_barra(p, t)
            self._pintar_painel(p, t)
            self._interacao(p, t, 770)
        finally:
            p.restore()

    # animações ----------------------------------------------------------------
    @staticmethod
    def _anel(p, cx, cy, r, ang, cor, larg, traco):
        p.save()
        p.translate(cx, cy)
        p.rotate(ang)
        pen = _caneta(cor, larg)
        pen.setDashPattern([float(x) for x in traco])
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(0, 0), r, r)
        p.restore()

    @staticmethod
    def _brilho(p, cx, cy, r, a, cor=CIANO):
        g = QRadialGradient(QPointF(cx, cy), r)
        g.setColorAt(0.0, _alpha(QColor(190, 245, 255), a))
        g.setColorAt(0.4, _alpha(cor, a * 0.45))
        g.setColorAt(1.0, _alpha(cor, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _animacoes(self, p: QPainter, t: float, hud) -> None:
        mudo = bool(getattr(hud, "muted", False))
        falando = bool(getattr(hud, "speaking", False))
        estado = str(getattr(hud, "state", ""))
        amp = float(getattr(hud, "_amp_disp", 0.0) or 0.0)
        cor = CINZA if mudo else CIANO
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)

        # logo
        self._anel(p, 60, 65, 51, t * 40, _alpha(QColor(255, 179, 71), .85), 1.8, [5, 3, 1, 3])
        self._brilho(p, 60, 65, 28, .25 + .2 * math.sin(t * 2.6), LARANJA)
        # olhos (piscam de vez em quando)
        piscar = 0.15 if (t % 5.0) < 0.12 else 1.0
        a_olho = (.45 + .25 * math.sin(t * 1.5)) * piscar * (0.4 if mudo else 1.0)
        for ex in (777, 902):
            g = QRadialGradient(QPointF(ex, 262), 44)
            g.setColorAt(0, _alpha(QColor(220, 252, 255), a_olho))
            g.setColorAt(.5, _alpha(CIANO, a_olho * .5))
            g.setColorAt(1, _alpha(CIANO, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.save()
            p.translate(ex, 262)
            p.scale(1.0, 0.4)
            p.translate(-ex, -262)
            p.drawEllipse(QPointF(ex, 262), 44, 44)
            p.restore()
        # radar
        p.save()
        p.translate(450, 350)
        p.rotate(-(t * 112) % 360)
        cg = QConicalGradient(QPointF(0, 0), 0)
        cg.setColorAt(0.0, _alpha(QColor(127, 240, 255), .55))
        cg.setColorAt(0.16, _alpha(QColor(127, 240, 255), 0))
        cg.setColorAt(1.0, _alpha(QColor(127, 240, 255), 0))
        p.setBrush(QBrush(cg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(0, 0), 86, 86)
        p.setPen(_caneta(_alpha(QColor(190, 246, 255), .8), 1.2))
        p.drawLine(QPointF(0, 0), QPointF(86, 0))
        p.restore()
        for bx, by, fase in ((485, 315, 0), (418, 385, 1.7)):
            self._brilho(p, bx, by, 5, .5 + .5 * math.sin(t * 5 + fase), VERDE)
        self._anel(p, 450, 350, 88, -t * 25, _alpha(CIANO, .6), .9, [3, 5])
        # círculo JARVIS
        self._anel(p, 318, 668, 172, t * 16, _alpha(cor, .8), 1.2, [1, 4])
        self._anel(p, 318, 668, 160, -t * 30, _alpha(cor, .7), 2.6, [14, 6, 2, 6])
        self._anel(p, 318, 668, 146, t * 60, _alpha(QColor(189, 247, 255), .8), 1.4, [8, 44])
        nb = 48
        p.setPen(_caneta(_alpha(QColor(127, 233, 255) if not mudo else CINZA, .9), 3.2, redonda=True))
        for i in range(nb):
            a = i / nb * math.tau
            if mudo:
                v = .03
            elif falando:
                v = .25 + min(1.0, amp * 1.6) * (.4 + .6 * abs(math.sin(t * 9 + i * .7)))
            elif estado == "LISTENING":
                v = .1 + .08 * math.sin(t * 4 + i * .5) + amp * .8
            elif estado in ("THINKING", "PROCESSING"):
                v = .12 + .12 * max(0.0, math.sin(t * 6 - i * .4))
            else:
                v = .05 + .04 * math.sin(t * 2 + i * .4)
            r1, r2 = 116, 116 + v * 36
            p.drawLine(QPointF(318 + math.cos(a) * r1, 668 + math.sin(a) * r1),
                       QPointF(318 + math.cos(a) * r2, 668 + math.sin(a) * r2))
        if falando:
            self._brilho(p, 318, 668, 120, .12 + .25 * min(1.0, amp * 2))
        # reator do peito
        self._brilho(p, 842, 720, 100, (.30 + .25 * math.sin(t * 2.6)) * (0.4 if mudo else 1.0))
        self._anel(p, 842, 720, 84, t * 45, _alpha(QColor(158, 240, 255), .8), 1.6, [4, 3])
        self._anel(p, 842, 720, 68, -t * 90, _alpha(CIANO, .7), 3, [12, 12])
        # globo: órbita e satélites
        p.setPen(_caneta(_alpha(CIANO, .35), 1, tracejada=True))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(1437, 432), 176, 38)
        for vel, fase, c, r in ((0.9, 0, QColor(223, 251, 255), 4.5), (-0.57, 2, QColor(255, 179, 71), 3)):
            a = t * vel + fase
            self._brilho(p, 1437 + math.cos(a) * 176, 432 + math.sin(a) * 38, r * 3, .9, c)
        self._brilho(p, 1437, 463, 112, .16 + .1 * math.sin(t * 1.6))
        # reator do canto
        self._anel(p, 1522, 794, 88, t * 72, _alpha(CIANO, .75), 2, [6, 3])
        self._anel(p, 1522, 794, 77, -t * 40, _alpha(QColor(191, 246, 255), .7), 1, [2, 3])
        self._brilho(p, 1522, 794, 60, .3 + .25 * math.sin(t * 3.5))
        # barras laranjas laterais (brilho que sobe)
        for (bx, by, bw, bh, fase) in ((1618, 340, 36, 365, 0), (94, 598, 34, 166, 1.1)):
            y = by + bh - ((t * 0.38 + fase) % 1.0) * (bh * 1.4)
            g = QLinearGradient(0, y - 40, 0, y + 40)
            g.setColorAt(0, _alpha(LARANJA, 0))
            g.setColorAt(.5, _alpha(QColor(255, 200, 90), .5))
            g.setColorAt(1, _alpha(LARANJA, 0))
            p.fillRect(QRectF(bx, by, bw, bh), QBrush(g))
        # anel de uso da CPU
        cpu = self._dados.get("cpu") or 0.0
        p.setPen(_caneta(_alpha(CIANO, .18), 4))
        p.drawEllipse(QPointF(480, 48), 23, 23)
        p.setPen(_caneta(CIANO, 4, redonda=True))
        p.drawArc(QRectF(457, 25, 46, 46), 90 * 16, -int(cpu / 100 * 360 * 16))
        self._anel(p, 480, 48, 16, t * 120, _alpha(QColor(158, 240, 255), .8), 1.4, [3, 14])
        # ponteiro dos segundos
        seg = datetime.now().second
        a = math.radians(seg * 6 - 90)
        p.setPen(_caneta(CIANO, 2.2, redonda=True))
        p.drawLine(QPointF(305, 47), QPointF(305 + math.cos(a) * 14, 47 + math.sin(a) * 14))
        # fluxo de dados no rodapé
        if t - self._t_barras > .12:
            self._t_barras = t
            self._barras_dados = [random.uniform(.15, 1) for _ in range(9)]
        for i, v in enumerate(self._barras_dados):
            p.fillRect(QRectF(792 + i * 10, 906 - 28 * v, 7, 28 * v), _alpha(CIANO, .85))
        # linha de varredura
        y = ((t % 7.0) / 7.0) * (LH * 1.2) - LH * 0.1
        g = QLinearGradient(0, y - 70, 0, y)
        g.setColorAt(0, _alpha(CIANO, 0))
        g.setColorAt(.9, _alpha(QColor(120, 230, 255), .10))
        g.setColorAt(1, _alpha(CIANO, 0))
        p.fillRect(QRectF(0, y - 70, LW, 70), QBrush(g))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    # textos -------------------------------------------------------------------
    @staticmethod
    def _txt(p, x, y, w, h, texto, px, cor=CLARO, alinhar=Qt.AlignmentFlag.AlignLeft, negrito=False):
        p.setFont(_fonte(px, negrito))
        # leve brilho por trás (o mesmo jeito do HUD da arte)
        p.setPen(_alpha(CIANO, .35))
        p.drawText(QRectF(x + .8, y + .8, w, h), alinhar | Qt.AlignmentFlag.AlignVCenter, texto)
        p.setPen(cor)
        p.drawText(QRectF(x, y, w, h), alinhar | Qt.AlignmentFlag.AlignVCenter, texto)

    @staticmethod
    def _barra(p, x, y, w, h, v):
        p.fillRect(QRectF(x, y, w, h), QColor(26, 14, 2))
        v = max(0.0, min(100.0, float(v or 0)))
        g = QLinearGradient(x, 0, x + w, 0)
        if v >= 85:
            g.setColorAt(0, QColor(255, 224, 224)); g.setColorAt(1, QColor(255, 42, 42))
        else:
            g.setColorAt(0, QColor(255, 243, 220)); g.setColorAt(.55, QColor(255, 179, 71)); g.setColorAt(1, QColor(255, 138, 0))
        p.fillRect(QRectF(x, y, w * v / 100.0, h), QBrush(g))

    def _grafico(self, p, x, y, w, h, serie, maximo=None):
        serie = [float(v or 0) for v in (serie or [])]
        if len(serie) < 2:
            return
        m = maximo or max(1.0, max(serie) * 1.15)
        n = len(serie)
        pts = [QPointF(x + i / (n - 1) * w, y + h - min(1.0, v / m) * (h - 2) - 1) for i, v in enumerate(serie)]
        area = QPolygonF([QPointF(x, y + h)] + pts + [QPointF(x + w, y + h)])
        g = QLinearGradient(0, y, 0, y + h)
        g.setColorAt(0, _alpha(CIANO, .45)); g.setColorAt(1, _alpha(CIANO, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawPolygon(area)
        p.setPen(_caneta(CIANO, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF(pts))

    def _textos(self, p: QPainter, t: float, hud) -> None:
        d, f = self._dados, self._fixo
        agora = datetime.now()
        hm = agora.strftime("%H:%M")
        dt = f"{DIAS[agora.weekday()]}, {agora:%d/%m}"
        self._txt(p, 342, 30, 100, 32, hm, 31, negrito=True)
        self._txt(p, 343, 62, 100, 20, dt, 15)
        self._txt(p, 522, 56, 90, 26, _pct(d.get("cpu")), 21)
        # status do JARVIS
        mudo = bool(getattr(hud, "muted", False))
        estado = str(getattr(hud, "state", ""))
        nomes = {"LISTENING": "Ouvindo…", "SPEAKING": "Falando…", "THINKING": "Pensando…",
                 "PROCESSING": "Processando…", "SLEEPING": "Em repouso", "INITIALISING": "Iniciando…"}
        agora_txt = "Falando…" if getattr(hud, "speaking", False) else nomes.get(estado, "Pronto para Assistir")
        self._txt(p, 690, 57, 292, 22, f"Sistema Online • {agora_txt}", 14.5, alinhar=Qt.AlignmentFlag.AlignHCenter)
        voz = "Comando por voz: Mudo • microfone desligado" if mudo else \
            f"Comando por voz: Ativado • {agora_txt if agora_txt != 'Pronto para Assistir' else 'pronto para iniciar tarefas'}"
        self._txt(p, 590, 814, 505, 22, voz, 15.5, VERM if mudo else CLARO, Qt.AlignmentFlag.AlignHCenter)
        # métricas do topo
        self._txt(p, 1075, 50, 90, 22, _pct(d.get("ram")), 17)
        self._txt(p, 1209, 50, 90, 22, _pct(d.get("disco")), 17)
        tot = (d.get("down") or 0) + (d.get("up") or 0)
        self._txt(p, 1343, 50, 110, 22, _vel(tot) if d else "--", 17)
        self._barra(p, 1076, 72, 104, 7, d.get("ram"))
        self._barra(p, 1210, 72, 105, 7, d.get("disco"))
        self._barra(p, 1344, 72, 105, 7, min(100.0, math.log10(1 + tot / 1024) / 5 * 100))
        # dia e selo de temperatura
        self._txt(p, 1527, 18, 92, 90, str(agora.day), 80, QColor(255, 255, 255), Qt.AlignmentFlag.AlignHCenter, True)
        g = QLinearGradient(1541, 0, 1637, 0)
        g.setColorAt(0, QColor(199, 79, 0)); g.setColorAt(.3, QColor(255, 140, 26))
        g.setColorAt(.7, QColor(255, 165, 58)); g.setColorAt(1, QColor(199, 79, 0))
        path = QPainterPath()
        path.addRoundedRect(QRectF(1541, 118, 96, 20), 3, 3)
        p.fillPath(path, QBrush(g))
        temp = d.get("temp")
        if temp is None and isinstance(d.get("gpu"), dict):
            temp = d["gpu"].get("temp")
        p.setFont(_fonte(17))
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(1541, 118, 96, 20), Qt.AlignmentFlag.AlignCenter,
                   "N/D" if temp is None else f"{round(temp)}°C")
        # SISTEMA
        self._txt(p, 262, 158, 190, 21, f"SO: {f.get('so', '…')}", 14)
        self._txt(p, 262, 179, 190, 21, f"Build: {f.get('build', '…')}", 14)
        self._txt(p, 262, 200, 190, 21, f"Arquitetura: {f.get('arquitetura', '…')}", 14)
        # REDE
        ping = d.get("ping")
        ping_txt = ("offline" if d.get("internet") is False else "--") if ping is None else f"{round(ping)} ms"
        for i, (rot, val) in enumerate((("Download:", _vel(d.get("down"))), ("Upload:", _vel(d.get("up"))),
                                        ("Ping:", ping_txt))):
            self._txt(p, 471, 158 + i * 21, 70, 21, rot, 14)
            self._txt(p, 520, 158 + i * 21, 82, 21, val if d else "--", 14, alinhar=Qt.AlignmentFlag.AlignRight)
        self._grafico(p, 470, 224, 130, 15, (self._hist.get("down") or [])[-40:])
        # PROCESSOS
        procs = d.get("procs") or []
        maxc = max([10.0] + [pr["cpu"] for pr in procs])
        for i, pr in enumerate(procs[:8]):
            y = 154 + i * 21.4
            gw = 220 * pr["cpu"] / maxc
            if gw > 1:
                gg = QLinearGradient(1016, 0, 1016 + gw, 0)
                gg.setColorAt(0, _alpha(CIANO, 0)); gg.setColorAt(1, _alpha(CIANO, .2))
                p.fillRect(QRectF(1016, y + 3, gw, 15), QBrush(gg))
            self._txt(p, 1016, y, 160, 21, pr["nome"][:24], 14)
            self._txt(p, 1170, y, 66, 21, f"{pr['cpu']:.1f}%", 14, alinhar=Qt.AlignmentFlag.AlignRight)
        # GPU
        gpu = d.get("gpu") if isinstance(d.get("gpu"), dict) else None
        self._txt(p, 1325, 155, 175, 20, (gpu.get("nome") or "GPU")[:24] if gpu else "GPU não informada", 14.5)
        self._txt(p, 1325, 180, 80, 30, _pct(gpu.get("uso")) if gpu else "--", 26)
        self._txt(p, 1325, 274, 90, 28, f"{round(gpu['temp'])}°C" if gpu and gpu.get("temp") is not None else "--", 24)
        hg = self._hist.get("gpu") or []
        self._grafico(p, 1455, 186, 132, 42, (hg if len(hg) > 1 else self._hist.get("cpu") or [])[-45:], 100)
        ht = self._hist.get("temp") or []
        self._grafico(p, 1405, 284, 182, 32, (ht if len(ht) > 1 else self._hist.get("ram") or [])[-60:], 100)
        # relógio grande
        self._txt(p, 452, 846, 208, 60, hm, 60, QColor(255, 255, 255), Qt.AlignmentFlag.AlignHCenter, True)
        self._txt(p, 452, 906, 208, 24, dt, 16, alinhar=Qt.AlignmentFlag.AlignHCenter)
        p.setPen(_caneta(CIANO, 1))
        p.drawLine(QPointF(470, 918), QPointF(505, 918))
        p.drawLine(QPointF(607, 918), QPointF(642, 918))

    def _destaque(self, p: QPainter) -> None:
        if not self._hover_rect:
            return
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        if self._hover_rect[0] == "c":
            _, cx, cy, r = self._hover_rect
            self._brilho(p, cx, cy, r, .22)
            p.setPen(_caneta(_alpha(CIANO, .8), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)
        else:
            _, x, y, w, h = self._hover_rect
            g = QLinearGradient(x, 0, x + w, 0)
            g.setColorAt(0, _alpha(CIANO, .28)); g.setColorAt(1, _alpha(CIANO, .05))
            p.fillRect(QRectF(x, y, w, h), QBrush(g))
            p.setPen(_caneta(_alpha(CIANO, .7), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(x, y, w, h))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # dica
        nome = self._hover
        if nome in self.DICAS:
            if self._hover_rect[0] == "c":
                _, cx, cy, r = self._hover_rect
                x, y = cx - 90, cy + r + 6
            else:
                _, rx, ry, rw, rh = self._hover_rect
                x, y = rx + rw + 8, ry + rh / 2 - 12
            x = max(4.0, min(self.LW - 184, x))
            y = max(4.0, min(self.LH - 28, y))
            caixa = QRectF(x, y, 180, 24)
            p.fillRect(caixa, QColor(2, 16, 26, 235))
            p.setPen(_caneta(_alpha(CIANO, .7), 1))
            p.drawRect(caixa)
            p.setFont(_fonte(13))
            p.setPen(CLARO)
            p.drawText(caixa, Qt.AlignmentFlag.AlignCenter, self.DICAS[nome])


from .sobreposto import Sobreposto  # noqa: E402


class Hud39Painter(Sobreposto, _HudBase):
    """O HUD 3.9 (J.A.R.V.I.S) com a barra de música, o botão de troca e os painéis por cima (3.9.3)."""
    ESTILO = "hud39"
    BARRA = (896.0, 866.0, 336.0, 44.0)     # cobre o "SEMPRE AO SEU LADO" do rodapé
    TROCA = (1250.0, 862.0, 175.0, 52.0)

    def __init__(self, arte: Path = ARTE):
        _HudBase.__init__(self, arte)
        self._ini_sobreposto()
