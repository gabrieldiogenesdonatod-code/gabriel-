"""
Interface F.R.I.D.A.Y (fork PT-BR 3.9.2) — o centro da janela principal no estilo "friday".

A imagem da assistente com os hologramas (hud39/static/friday.jpg, só ela, sem nada embaixo) no meio,
viva: o orbe do dedo pulsa com a voz, o painel da cabeça faz varredura, os hologramas tremulam
quando ela pensa e a imagem acende quando fala. Dos lados, cartões holográficos desenhados pelo Qt:
o menu (clicável) à esquerda e os números reais do PC à direita. Embaixo, a plataforma com a onda da voz.

Tudo é clicável com destaque no mouse, dica, anel no clique e aviso do que está abrindo. A caixa de
texto, o mudo, o falar e o microfone da janela continuam onde sempre estiveram.
"""
from __future__ import annotations

import math
import random
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPixmap, QPolygonF,
                         QRadialGradient)

from .qt_hud import (CIANO, CINZA, CLARO, DIAS, VERDE, VERM, Hud39Painter, _alpha, _caneta, _fonte, _pct,
                     _vel)

ARTE = Path(__file__).resolve().parent / "static" / "friday.jpg"
VW, VH = 1600.0, 900.0
# A imagem (1056×1228) entra no meio, com a altura toda.
ESC = VH / 1228.0
X0 = (VW - 1056 * ESC) / 2.0

ROSA = QColor(255, 111, 145)
CORAL = QColor(255, 150, 120)
FUNDO = QColor(4, 6, 14)


def _im(fx: float, fy: float) -> tuple[float, float]:
    """Ponto da imagem original → ponto da tela virtual."""
    return X0 + fx * ESC, fy * ESC


def _im_ret(x1, y1, x2, y2, nome):
    a, b = _im(x1, y1)
    c, d = _im(x2, y2)
    return (a, b, c - a, d - b, nome)


ORBE = _im(935, 300)
PAINEL_CABECA = _im_ret(30, 465, 365, 1075, "diagnostico")
PAINEIS_PEQUENOS = [_im_ret(800, 745, 1030, 830, "internet"), _im_ret(795, 830, 1030, 915, "musica"),
                    _im_ret(785, 965, 1035, 1055, "config")]

MENU = [("sistema", "SISTEMA", "▣"), ("internet", "INTERNET", "◎"), ("arquivos", "ARQUIVOS", "▤"),
        ("musica", "MÚSICA", "♫"), ("videos", "VÍDEOS", "▶"), ("jogos", "JOGOS", "◆"), ("config", "CONFIG", "⚙")]
MENU_X, MENU_Y, MENU_W, MENU_H, MENU_PASSO = 34.0, 150.0, 330.0, 54.0, 64.0


class FridayPainter(Hud39Painter):
    LW, LH = VW, VH
    ESTILO = "friday"
    BARRA = (34.0, 738.0, 330.0, 46.0)
    TROCA = (34.0, 798.0, 330.0, 52.0)
    COR_ONDA = ROSA
    CIRCULOS = [(ORBE[0], ORBE[1], 52, "comando"), (800, 800, 60, "comando")]
    RETANGULOS = (
        [(MENU_X, MENU_Y + i * MENU_PASSO, MENU_W, MENU_H, nome) for i, (nome, _r, _i) in enumerate(MENU)]
        + PAINEIS_PEQUENOS
        + [PAINEL_CABECA,
           _im_ret(755, 40, 1050, 665, "sistema"),          # painel grande da direita
           _im_ret(120, 180, 310, 300, "processos"),        # painel apagado do alto
           _im_ret(480, 160, 700, 440, "jarvis"),           # o rosto dela
           (1214, 34, 352, 182, "diagnostico"),             # medidores
           (1214, 226, 352, 120, "discos"),
           (1214, 356, 352, 70, "gpu"),
           (1214, 436, 352, 196, "processos"),
           (1214, 642, 352, 120, "internet")])
    DICAS = {"sistema": "Sobre o sistema", "internet": "Internet e rede", "arquivos": "Abrir pastas",
             "musica": "Controles de música", "videos": "Vídeos", "jogos": "Jogos", "config": "Configurações",
             "processos": "Processos", "gpu": "Placa de vídeo", "discos": "Memória e discos",
             "diagnostico": "Diagnóstico do sistema", "jarvis": "Sobre a assistente",
             "comando": "Falar / escrever com a F.R.I.D.A.Y"}

    def __init__(self):
        super().__init__(ARTE)
        self._falhas: list = []
        self._t_falhas = 0.0

    def texto_aviso(self, nome: str) -> str:
        if nome == "comando":
            return "Estou ouvindo — pode escrever na caixa de texto"
        return super().texto_aviso(nome)

    # ── pintura ──────────────────────────────────────────────────────────────
    def paint(self, p: QPainter, W: int, H: int, hud) -> None:
        self._atualizar()
        s, ox, oy = self.encaixe(W, H)
        if s <= 0.05:
            return
        t = time.time()
        mudo = bool(getattr(hud, "muted", False))
        falando = bool(getattr(hud, "speaking", False))
        estado = str(getattr(hud, "state", ""))
        amp = min(1.0, float(getattr(hud, "_amp_disp", 0.0) or 0.0) * 1.6)

        p.fillRect(QRectF(0, 0, W, H), FUNDO)
        p.save()
        p.translate(ox, oy)
        p.scale(s, s)
        p.setClipRect(QRectF(0, 0, VW, VH))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        try:
            self._fundo(p, t)
            self._imagem(p, t, s, falando, amp, estado, mudo)
            self._plataforma(p, t, falando, amp, estado, mudo)
            self._menu(p, t)
            self._medidores(p, t)
            self._topo(p, t, estado, falando, mudo)
            self._destaque(p)
            self._pintar_barra(p, t)
            self._pintar_painel(p, t)
            self._interacao(p, t, 742)
        finally:
            p.restore()

    # fundo: grade, vinheta e varredura ------------------------------------------
    def _fundo(self, p, t):
        p.setPen(_caneta(_alpha(CIANO, .05), 1))
        for x in range(0, int(VW) + 1, 40):
            p.drawLine(QPointF(x, 0), QPointF(x, VH))
        for y in range(0, int(VH) + 1, 40):
            p.drawLine(QPointF(0, y), QPointF(VW, y))
        g = QRadialGradient(QPointF(VW / 2, VH * .45), VW * .55)
        g.setColorAt(0, _alpha(QColor(60, 20, 50), .55))
        g.setColorAt(.6, _alpha(QColor(10, 14, 30), .25))
        g.setColorAt(1, _alpha(FUNDO, 0))
        p.fillRect(QRectF(0, 0, VW, VH), QBrush(g))

    def _imagem(self, p, t, s, falando, amp, estado, mudo):
        w, h = 1056 * ESC, VH
        pw, ph = max(1, int(round(w * s))), max(1, int(round(h * s)))
        if self._cache is None or self._cache[:2] != (pw, ph):
            self._cache = (pw, ph, self._arte.scaled(pw, ph, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))
        alvo = QRectF(X0, 0, w, h)
        # leve "respiração" de holograma
        p.setOpacity(.55 if mudo else (.93 + .07 * math.sin(t * 1.3)))
        p.drawPixmap(alvo, self._cache[2], QRectF(0, 0, pw, ph))
        p.setOpacity(1.0)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        if falando and not mudo:                       # acende quando fala
            p.setOpacity(.10 + .30 * amp)
            p.drawPixmap(alvo, self._cache[2], QRectF(0, 0, pw, ph))
            p.setOpacity(1.0)
        cor = CINZA if mudo else CIANO
        # orbe do dedo
        bx, by = ORBE
        forca = .35 + .25 * math.sin(t * 3.1) + (.5 * amp if falando else 0)
        if estado == "LISTENING" and not mudo:
            forca += .25 + .15 * math.sin(t * 8)
        self._brilho(p, bx, by, 40 + 30 * forca, min(1.0, forca) * (.35 if mudo else 1), cor)
        self._anel(p, bx, by, 58, t * 70, _alpha(cor, .7), 1.6, [6, 4])
        self._anel(p, bx, by, 72, -t * 35, _alpha(QColor(190, 245, 255), .5), 1, [2, 5])
        # varredura do painel da cabeça
        x, y, pw_, ph_, _n = PAINEL_CABECA
        k = (t * .35) % 1.0
        yy = y + 20 + k * (ph_ - 40)
        g = QLinearGradient(0, yy - 16, 0, yy + 1)
        g.setColorAt(0, _alpha(CIANO, 0))
        g.setColorAt(1, _alpha(CIANO, .22 * (0.4 if mudo else 1)))
        p.fillRect(QRectF(x + 14, yy - 16, pw_ - 28, 17), QBrush(g))
        p.fillRect(QRectF(x + 14, yy, pw_ - 28, 1.2), _alpha(QColor(190, 245, 255), .55 * (0.4 if mudo else 1)))
        # brilho que passa nos painéis pequenos
        for i, (x, y, pw_, ph_, _n) in enumerate(PAINEIS_PEQUENOS):
            k = ((t * .45 + i * .33) % 1.6) - .3
            gx = x + k * pw_
            g = QLinearGradient(gx - 40, 0, gx + 40, 0)
            g.setColorAt(0, _alpha(CIANO, 0)); g.setColorAt(.5, _alpha(CIANO, .16)); g.setColorAt(1, _alpha(CIANO, 0))
            esq, dir_ = max(x, gx - 40), min(x + pw_, gx + 40)
            if dir_ > esq:
                p.fillRect(QRectF(esq, y, dir_ - esq, ph_), QBrush(g))
        # tremulação de holograma (mais forte quando pensa)
        pensando = estado in ("THINKING", "PROCESSING")
        if t - self._t_falhas > (.08 if pensando else .22):
            self._t_falhas = t
            n = random.randint(2, 6) if pensando else (1 if random.random() < .35 else 0)
            self._falhas = [(random.uniform(40, VH - 120), random.uniform(X0, X0 + w * .6),
                             random.uniform(40, 260), random.choice([ROSA, CIANO])) for _ in range(n)]
        for fy, fx, fw, c in self._falhas:
            p.fillRect(QRectF(fx, fy, fw, 2), _alpha(c, .35))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # bordas da imagem somem no fundo
        for xa, xb in ((X0 - 1, X0 + 60), (X0 + w + 1, X0 + w - 60)):
            g = QLinearGradient(xa, 0, xb, 0)
            g.setColorAt(0, FUNDO); g.setColorAt(1, _alpha(FUNDO, 0))
            p.fillRect(QRectF(min(xa, xb), 0, 61, VH), QBrush(g))

    # plataforma com a onda da voz -----------------------------------------------
    def _plataforma(self, p, t, falando, amp, estado, mudo):
        cx, cy = 800.0, 812.0
        cor = CINZA if mudo else ROSA
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        g = QRadialGradient(QPointF(cx, cy), 320)
        g.setColorAt(0, _alpha(cor, .30 + (.25 * amp if falando else 0)))
        g.setColorAt(1, _alpha(cor, 0))
        p.save()
        p.translate(cx, cy)
        p.scale(1.0, .16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), 320, 320)
        for r, vel, traco, a in ((300, 12, [10, 6], .7), (250, -20, [3, 8], .6), (200, 30, [24, 10], .5)):
            p.save()
            p.rotate(t * vel)
            pen = _caneta(_alpha(CIANO if r != 250 else cor, a), 6)
            pen.setDashPattern([float(v) for v in traco])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(0, 0), r, r)
            p.restore()
        p.restore()
        # barras da voz
        n = 41
        for i in range(n):
            d = abs(i - n // 2) / (n // 2)
            if mudo:
                v = .04
            elif falando:
                v = (.25 + .75 * amp) * (1 - d * .7) * (.45 + .55 * abs(math.sin(t * 10 + i * .9)))
            elif estado == "LISTENING":
                v = .10 + .10 * abs(math.sin(t * 5 + i * .5)) + amp * (1 - d)
            elif estado in ("THINKING", "PROCESSING"):
                v = .08 + .25 * max(0.0, math.sin(t * 7 - i * .35))
            else:
                v = .05 + .03 * math.sin(t * 2 + i * .4)
            hgt = 4 + 70 * min(1.0, v)
            x = cx - 300 + i * 15
            gg = QLinearGradient(0, cy - hgt, 0, cy)
            gg.setColorAt(0, _alpha(CLARO if not mudo else CINZA, .9))
            gg.setColorAt(1, _alpha(cor, .2))
            p.fillRect(QRectF(x, cy - 14 - hgt, 6, hgt), QBrush(gg))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    # cartões holográficos --------------------------------------------------------
    @staticmethod
    def _cartao(p, x, y, w, h, cor=CIANO, a=.55, fundo=.55):
        c = 14.0
        path = QPainterPath()
        path.moveTo(x + c, y)
        path.lineTo(x + w, y)
        path.lineTo(x + w, y + h - c)
        path.lineTo(x + w - c, y + h)
        path.lineTo(x, y + h)
        path.lineTo(x, y + c)
        path.closeSubpath()
        g = QLinearGradient(x, y, x + w, y + h)
        g.setColorAt(0, _alpha(QColor(10, 34, 52), fundo))
        g.setColorAt(1, _alpha(QColor(4, 12, 24), fundo))
        p.fillPath(path, QBrush(g))
        p.setPen(_caneta(_alpha(cor, a), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(_caneta(_alpha(cor, .9), 3))
        p.drawLine(QPointF(x + c + 4, y), QPointF(x + c + 48, y))

    def _menu(self, p, t):
        # título
        self._txt(p, 34, 34, 340, 52, "F.R.I.D.A.Y", 46, ROSA, negrito=True)
        self._txt(p, 36, 88, 340, 22, "ASSISTENTE PESSOAL  •  J.A.R.V.I.S BR", 13, _alpha(CLARO, .75))
        p.setPen(_caneta(_alpha(ROSA, .6), 1))
        p.drawLine(QPointF(36, 118), QPointF(364, 118))
        for i, (nome, rot, ic) in enumerate(MENU):
            y = MENU_Y + i * MENU_PASSO
            ativo = self._hover == nome
            self._cartao(p, MENU_X, y, MENU_W, MENU_H, ROSA if ativo else CIANO, .9 if ativo else .5,
                         .75 if ativo else .5)
            if ativo:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                g = QLinearGradient(MENU_X, 0, MENU_X + MENU_W, 0)
                g.setColorAt(0, _alpha(ROSA, .30)); g.setColorAt(1, _alpha(ROSA, 0))
                p.fillRect(QRectF(MENU_X + 2, y + 2, MENU_W - 4, MENU_H - 4), QBrush(g))
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            self._txt(p, MENU_X + 20, y, 40, MENU_H, ic, 22, ROSA if ativo else CIANO)
            self._txt(p, MENU_X + 64, y, 200, MENU_H, rot, 20, CLARO, negrito=ativo)
            self._txt(p, MENU_X + MENU_W - 52, y, 34, MENU_H, "›", 22, _alpha(ROSA if ativo else CLARO, .6),
                      Qt.AlignmentFlag.AlignRight)
        # relógio
        agora = datetime.now()
        self._txt(p, 34, 618, 340, 80, agora.strftime("%H:%M"), 72, CLARO, negrito=True)
        self._txt(p, 238, 640, 120, 30, agora.strftime(":%S"), 22, _alpha(ROSA, .9))
        saud = "Bom dia" if 5 <= agora.hour < 12 else ("Boa tarde" if agora.hour < 18 else "Boa noite")
        self._txt(p, 36, 696, 340, 26, f"{DIAS[agora.weekday()]}, {agora:%d/%m/%Y}  •  {saud}", 16, _alpha(CLARO, .8))

    def _anel_medidor(self, p, cx, cy, r, v, rot, cor):
        v = max(0.0, min(100.0, float(v or 0)))
        p.setPen(_caneta(_alpha(cor, .18), 9))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)
        quente = VERM if v >= 90 else cor
        pen = _caneta(quente, 9, redonda=True)
        p.setPen(pen)
        p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 90 * 16, -int(v / 100 * 360 * 16))
        self._txt(p, cx - r, cy - 18, 2 * r, 32, f"{round(v)}%", 26, CLARO, Qt.AlignmentFlag.AlignHCenter, True)
        self._txt(p, cx - r, cy + 12, 2 * r, 20, rot, 12, _alpha(CLARO, .7), Qt.AlignmentFlag.AlignHCenter)

    def _medidores(self, p, t):
        d = self._dados
        x0, w = 1214.0, 352.0
        # CPU e RAM
        self._cartao(p, x0, 34, w, 182)
        self._anel_medidor(p, x0 + 92, 125, 62, d.get("cpu"), "CPU", CIANO)
        self._anel_medidor(p, x0 + 262, 125, 62, d.get("ram"), "RAM", ROSA)
        # disco e rede
        self._cartao(p, x0, 226, w, 120)
        self._txt(p, x0 + 20, 238, 150, 22, "DISCO", 13, _alpha(CLARO, .7))
        self._txt(p, x0 + 200, 238, 130, 22, _pct(d.get("disco")), 18, CLARO, Qt.AlignmentFlag.AlignRight)
        self._barra(p, x0 + 20, 264, w - 40, 7, d.get("disco"))
        tot = (d.get("down") or 0) + (d.get("up") or 0)
        self._txt(p, x0 + 20, 284, 150, 22, "REDE", 13, _alpha(CLARO, .7))
        self._txt(p, x0 + 120, 284, 210, 22, f"↓ {_vel(d.get('down'))}   ↑ {_vel(d.get('up'))}" if d else "--", 15,
                  CLARO, Qt.AlignmentFlag.AlignRight)
        self._barra(p, x0 + 20, 312, w - 40, 7, min(100.0, math.log10(1 + tot / 1024) / 5 * 100))
        # GPU e temperatura
        self._cartao(p, x0, 356, w, 70)
        gpu = d.get("gpu") if isinstance(d.get("gpu"), dict) else None
        temp = d.get("temp") if d.get("temp") is not None else (gpu or {}).get("temp")
        self._txt(p, x0 + 20, 364, 230, 24, (gpu.get("nome") or "GPU")[:26] if gpu else "GPU não informada", 15)
        self._txt(p, x0 + 20, 390, 200, 28, f"uso {_pct(gpu.get('uso'))}" if gpu else "--", 18, CIANO)
        self._txt(p, x0 + 220, 376, 112, 36, "N/D" if temp is None else f"{round(temp)}°C", 26, CORAL,
                  Qt.AlignmentFlag.AlignRight, True)
        # processos
        self._cartao(p, x0, 436, w, 196)
        self._txt(p, x0 + 20, 444, 200, 22, "PROCESSOS", 13, _alpha(CLARO, .7))
        procs = d.get("procs") or []
        if not procs:
            self._txt(p, x0 + 24, 480, 300, 26, "lendo os processos…", 15, _alpha(CLARO, .5))
        maxc = max([10.0] + [pr["cpu"] for pr in procs])
        for i, pr in enumerate(procs[:6]):
            y = 470 + i * 26
            gw = (w - 40) * pr["cpu"] / maxc
            if gw > 1:
                g = QLinearGradient(x0 + 20, 0, x0 + 20 + gw, 0)
                g.setColorAt(0, _alpha(ROSA, 0)); g.setColorAt(1, _alpha(ROSA, .25))
                p.fillRect(QRectF(x0 + 20, y + 4, gw, 18), QBrush(g))
            self._txt(p, x0 + 24, y, 220, 26, pr["nome"][:26], 15)
            self._txt(p, x0 + 240, y, 92, 26, f"{pr['cpu']:.1f}%", 15, CLARO, Qt.AlignmentFlag.AlignRight)
        # internet
        self._cartao(p, x0, 642, w, 120)
        ping = d.get("ping")
        online = d.get("internet") is not False
        self._txt(p, x0 + 20, 650, 200, 22, "INTERNET", 13, _alpha(CLARO, .7))
        self._txt(p, x0 + 150, 650, 182, 22, ("● online" if online else "● sem internet") +
                  (f"  {round(ping)} ms" if ping is not None else ""), 15, VERDE if online else VERM,
                  Qt.AlignmentFlag.AlignRight)
        self._grafico(p, x0 + 20, 680, w - 40, 70, (self._hist.get("down") or [])[-60:])

    def _topo(self, p, t, estado, falando, mudo):
        nomes = {"LISTENING": "Ouvindo…", "SPEAKING": "Falando…", "THINKING": "Pensando…",
                 "PROCESSING": "Processando…", "SLEEPING": "Em repouso", "INITIALISING": "Iniciando…"}
        txt = "Falando…" if falando else nomes.get(estado, "Pronta para ajudar")
        if mudo:
            voz, cor = "Microfone mudo  •  toque em ATIVAR MICROFONE para falar comigo", VERM
        else:
            voz, cor = f"Comando por voz ativado  •  {txt}", CLARO
        p.setFont(_fonte(16))
        larg = len(voz) * 8.4 + 48
        caixa = QRectF(VW / 2 - larg / 2, 860, larg, 30)
        p.fillRect(caixa, QColor(4, 8, 18, 215))
        p.setPen(_caneta(_alpha(VERM if mudo else ROSA, .55), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(caixa)
        self._txt(p, caixa.x(), 860, larg, 30, voz, 16, cor, Qt.AlignmentFlag.AlignHCenter)
        # selo de estado no alto da imagem
        caixa = QRectF(VW / 2 - 130, 16, 260, 30)
        p.fillRect(caixa, QColor(4, 10, 20, 190))
        p.setPen(_caneta(_alpha(VERM if mudo else ROSA, .8), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(caixa)
        piscar = .5 + .5 * math.sin(t * 4)
        self._brilho(p, caixa.x() + 18, caixa.y() + 15, 7, .6 + .4 * piscar, VERM if mudo else VERDE)
        self._txt(p, caixa.x() + 30, caixa.y(), 226, 30, "SISTEMA ONLINE  •  " + ("MICROFONE MUDO" if mudo else txt.upper().rstrip("…")), 13,
                  CLARO, Qt.AlignmentFlag.AlignHCenter)

    def _destaque(self, p):
        # o menu já tem o próprio destaque; o resto usa o do HUD 3.9 (em rosa)
        if self._hover_rect and self._hover_rect[0] == "r":
            _, x, y, _w, _h = self._hover_rect
            if x == MENU_X and MENU_Y <= y <= MENU_Y + 7 * MENU_PASSO:
                return
        super()._destaque(p)
