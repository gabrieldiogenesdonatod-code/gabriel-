"""
core/rosto_flutuante.py — o rosto do JARVIS numa janelinha flutuante (fork PT-BR 1.3).

Para quando você está programando (ou fazendo qualquer coisa) e quer o JARVIS
no canto da tela, conversando, sem a janela grande na frente:

    * sempre no topo, sem borda, fundo transparente;
    * o MESMO rosto animado do HUD (core/avatar.py), com a boca seguindo a fala
      e a aura reagindo à sua voz;
    * uma bolha com a última frase (sua ou dele), que some sozinha;
    * um pontinho de estado: ouvindo, falando, pensando, mutado, dormindo.

Usar
    arrastar ............ move
    rodinha do mouse .... aumenta / diminui
    clique duplo ........ abre a janela grande do JARVIS
    botão direito ....... menu (canto da tela, tamanho, transparência,
                          legenda, mutar, fechar)

O rosto NÃO escuta áudio sozinho: ele lê, a cada quadro, o nível de som e o
estado que o HUD já calculou (mesma fonte, então nunca fica fora de sincronia).
Desenhar uma cabeça pequena em software custa pouco; quando nada acontece, o
ritmo cai para 15 quadros por segundo.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

try:
    from core.avatar import HoloAvatar
except Exception:                         # sem numpy/malha: não há rosto para mostrar
    HoloAvatar = None

NS = "rosto_flutuante"
TAMANHOS = {"pequeno": 150, "médio": 210, "grande": 290}
CANTOS = ("inferior direito", "inferior esquerdo", "superior direito", "superior esquerdo")
_ESTADOS = {"LISTENING": ("OUVINDO", "#00ff88"), "SPEAKING": ("FALANDO", None),
            "THINKING": ("PENSANDO", "#ffcc00"), "PROCESSING": ("PENSANDO", "#ffcc00"),
            "MUTED": ("MUTADO", "#ff3355"), "SLEEPING": ("DORMINDO", "#3a8a9a"),
            "INITIALISING": ("INICIANDO", "#3a8a9a")}
_LEGENDA_S = 9.0          # quanto tempo a bolha fica na tela


def config() -> dict:
    padrao = {"tamanho": "médio", "canto": "inferior direito", "opacidade": 1.0,
              "legenda": True, "auto_minimizar": True, "x": None, "y": None, "lado": None}
    try:
        from memory.config_manager import get_plugin_config
        padrao.update({k: v for k, v in get_plugin_config(NS).items() if v is not None})
    except Exception:
        pass
    return padrao


def salvar(**valores) -> None:
    for k, v in list(valores.items()):
        if v is not None and not isinstance(v, (bool, int, float, str)):
            try:
                valores[k] = int(v)
            except (TypeError, ValueError):
                valores.pop(k)
    try:
        from memory.config_manager import save_plugin_config
        save_plugin_config(NS, valores)
    except Exception as e:
        print(f"[RostoFlutuante] não salvei: {e}")


class RostoFlutuante(QWidget):
    def __init__(self, hud, cores, abrir_principal=None, mutar=None):
        super().__init__(None)
        self._hud = hud                     # HudCanvas: fonte do nível de áudio e do estado
        self.C = cores
        self._abrir_principal = abrir_principal
        self._mutar = mutar
        self._avatar = HoloAvatar() if HoloAvatar is not None else None
        self._t = time.monotonic()
        self._arrasto: QPoint | None = None
        self._moveu = False
        self._legenda = ""
        self._legenda_de = ""
        self._legenda_ate = 0.0
        self._quadro = 0

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle("J.A.R.V.I.S")
        self.setToolTip("Arraste para mover · rodinha muda o tamanho · clique duplo abre o JARVIS · "
                        "botão direito: opções")

        c = config()
        self._lado = int(c["lado"]) if str(c.get("lado") or "").isdigit() else \
            TAMANHOS.get(str(c["tamanho"]), 210)
        self._mostrar_legenda = bool(c["legenda"])
        try:
            self.setWindowOpacity(max(0.3, min(1.0, float(c["opacidade"]))))
        except (TypeError, ValueError):
            pass
        self._aplicar_tamanho()
        if c.get("x") is not None and c.get("y") is not None:
            self.move(int(c["x"]), int(c["y"]))
            self._garantir_na_tela()
        else:
            self.ir_para_canto(str(c["canto"]), salvar_=False)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._passo)
        self._timer.start(33)

    # ── tamanho e posição ──────────────────────────────────────────────────────
    def _altura_legenda(self) -> int:
        return int(self._lado * 0.62) if self._mostrar_legenda else 0

    def _aplicar_tamanho(self):
        largura = max(self._lado, int(self._lado * 1.55)) if self._mostrar_legenda else self._lado
        self.setFixedSize(largura, self._lado + self._altura_legenda())

    def _tela(self):
        tela = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        return tela.availableGeometry()

    def ir_para_canto(self, canto: str, salvar_: bool = True):
        g = self._tela()
        m = 12
        x = g.left() + m if "esquerdo" in canto else g.right() - self.width() - m
        y = g.top() + m if "superior" in canto else g.bottom() - self.height() - m
        self.move(x, y)
        if salvar_:
            salvar(canto=canto, x=None, y=None)

    def _garantir_na_tela(self):
        g = self._tela()
        x = min(max(self.x(), g.left()), g.right() - self.width())
        y = min(max(self.y(), g.top()), g.bottom() - self.height())
        self.move(x, y)

    def mudar_tamanho(self, lado: int):
        centro_baixo = QPoint(self.x() + self.width() // 2, self.y() + self.height())
        self._lado = max(110, min(420, int(lado)))
        self._aplicar_tamanho()
        self.move(centro_baixo.x() - self.width() // 2, centro_baixo.y() - self.height())
        self._garantir_na_tela()
        salvar(lado=str(self._lado), x=self.x(), y=self.y())

    # ── legenda ────────────────────────────────────────────────────────────────
    def mostrar_frase(self, linha: str):
        """Recebe as linhas do registro. Só as falas (Você: / JARVIS:) viram bolha."""
        texto = str(linha or "").strip()
        if not texto or texto.startswith(("SYS:", "ERR:", "NET:")):
            return
        quem, sep, resto = texto.partition(":")
        if not sep or len(quem) > 24 or not resto.strip():
            return
        self._legenda_de = "você" if quem.strip().lower() in ("você", "voce", "you") else quem.strip()
        self._legenda = " ".join(resto.split())
        self._legenda_ate = time.monotonic() + _LEGENDA_S + min(8.0, len(self._legenda) / 25)
        self.update()

    # ── animação ───────────────────────────────────────────────────────────────
    def _entrada(self):
        """Nível, estado e boca do instante — lidos do HUD, sem consumir nada dele."""
        h = self._hud
        amp = float(getattr(h, "_amp_disp", 0.0) or 0.0)
        v_open = v_wide = v_level = None
        sched = getattr(h, "_visemes", None)
        if sched is not None:
            try:
                frames, t0, hop = sched
                i = int((time.time() - t0) / hop)
                if 0 <= i < len(frames):
                    v_level, v_open, v_wide = frames[i]
            except Exception:
                pass
        return amp, bool(getattr(h, "speaking", False)), bool(getattr(h, "muted", False)), \
            str(getattr(h, "state", "")), v_open, v_wide, v_level

    def _passo(self):
        if not self.isVisible():
            return
        agora = time.monotonic()
        amp, falando, mudo, estado, v_open, v_wide, v_level = self._entrada()
        ativo = falando or amp > 0.03 or agora < self._legenda_ate
        self._quadro += 1
        if not ativo and self._quadro % 2:      # parado: metade dos quadros (~15 fps)
            return
        dt = agora - self._t
        self._t = agora
        if self._avatar is not None:
            self._avatar.step(dt, amp, speaking=falando, muted=mudo, state=estado,
                              v_open=v_open, v_wide=v_wide or 0.0, v_level=v_level)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        C = self.C
        primaria, acento, fundo = QColor(C.PRI), QColor(C.ACC), QColor(C.BG)
        lado = self._lado
        cx = self.width() / 2
        topo_cabeca = self._altura_legenda()

        # disco de fundo, para o rosto aparecer em cima de qualquer coisa
        disco = QRectF(cx - lado / 2 + 4, topo_cabeca + 4, lado - 8, lado - 8)
        fundo_disco = QColor(fundo)
        fundo_disco.setAlpha(215)
        p.setPen(QPen(QColor(C.BORDER_B), 1.2))
        p.setBrush(fundo_disco)
        p.drawEllipse(disco)

        if self._avatar is not None:
            span = getattr(self._avatar, "SPAN", 2.2)
            r = (lado * 0.80) / (span + 0.1)
            cy = topo_cabeca + lado / 2 + r * 0.06
            p.save()
            caminho = QPainterPath()
            caminho.addEllipse(disco)
            p.setClipPath(caminho)
            self._avatar.paint(p, cx, cy, r, primaria, acento, fundo)
            p.restore()
        else:
            p.setPen(QPen(primaria, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(disco.adjusted(lado * 0.3, lado * 0.3, -lado * 0.3, -lado * 0.3))

        # pontinho e nome do estado
        estado = str(getattr(self._hud, "state", ""))
        if getattr(self._hud, "muted", False):
            estado = "MUTED"
        nome, cor = _ESTADOS.get(estado, ("", None))
        if nome:
            cor_q = QColor(cor) if cor else primaria
            f = QFont("Consolas", max(6, int(lado / 30)), QFont.Weight.Bold)
            p.setFont(f)
            largura_txt = QFontMetrics(f).horizontalAdvance(nome)
            y = disco.bottom() - lado * 0.05
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(cor_q)
            raio = max(3.0, lado / 60)
            x0 = cx - (largura_txt + raio * 3) / 2
            p.drawEllipse(QRectF(x0, y - raio * 1.6, raio * 2, raio * 2))
            p.setPen(cor_q)
            p.drawText(int(x0 + raio * 3), int(y), nome)

        # bolha com a última frase
        if self._mostrar_legenda and self._legenda and time.monotonic() < self._legenda_ate:
            restante = self._legenda_ate - time.monotonic()
            alfa = 1.0 if restante > 1.0 else max(0.0, restante)
            area = QRectF(4, 2, self.width() - 8, topo_cabeca - 8)
            fundo_bolha = QColor(fundo)
            fundo_bolha.setAlpha(int(230 * alfa))
            borda = QColor(primaria if self._legenda_de != "você" else C.GREEN)
            borda.setAlpha(int(200 * alfa))
            p.setPen(QPen(borda, 1.2))
            p.setBrush(fundo_bolha)
            p.drawRoundedRect(area, 8, 8)
            f = QFont("Segoe UI", max(7, int(lado / 24)))
            p.setFont(f)
            cor_txt = QColor(C.WHITE)
            cor_txt.setAlpha(int(255 * alfa))
            p.setPen(cor_txt)
            dentro = area.adjusted(8, 5, -8, -5)
            fm = QFontMetrics(f)
            texto = f"{self._legenda_de}: {self._legenda}"
            linhas_cabem = max(1, int(dentro.height() // fm.lineSpacing()))
            # corta pelo FIM e mostra o final da frase (o que está sendo dito agora)
            while len(texto) > 20 and fm.boundingRect(dentro.toRect(), Qt.TextFlag.TextWordWrap,
                                                      texto).height() > linhas_cabem * fm.lineSpacing():
                texto = "…" + texto[max(2, len(texto) // 10):]
            p.drawText(dentro, int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignBottom), texto)
        p.end()

    # ── mouse ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._arrasto = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moveu = False

    def mouseMoveEvent(self, e):
        if self._arrasto is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._arrasto)
            self._moveu = True

    def mouseReleaseEvent(self, e):
        if self._arrasto is not None and self._moveu:
            self._garantir_na_tela()
            salvar(x=self.x(), y=self.y())
        self._arrasto = None

    def mouseDoubleClickEvent(self, _e):
        if callable(self._abrir_principal):
            self._abrir_principal()

    def wheelEvent(self, e):
        passo = 20 if e.angleDelta().y() > 0 else -20
        self.mudar_tamanho(self._lado + passo)

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet(f"QMenu {{ background: {self.C.PANEL}; color: {self.C.TEXT}; "
                        f"border: 1px solid {self.C.BORDER_B}; }} "
                        f"QMenu::item:selected {{ background: {self.C.PRI_GHO}; color: {self.C.PRI}; }}")
        m.addAction("Abrir o JARVIS", lambda: self._abrir_principal and self._abrir_principal())
        if callable(self._mutar):
            m.addAction("Mutar / ativar microfone", self._mutar)
        cantos = m.addMenu("Canto da tela")
        for canto in CANTOS:
            cantos.addAction(canto.capitalize(), lambda c=canto: self.ir_para_canto(c))
        tam = m.addMenu("Tamanho")
        for nome, lado in TAMANHOS.items():
            tam.addAction(nome.capitalize(), lambda l=lado: self.mudar_tamanho(l))
        opac = m.addMenu("Transparência")
        for rotulo, valor in (("Sólido", 1.0), ("Um pouco", 0.85), ("Bastante", 0.65), ("Fantasma", 0.45)):
            opac.addAction(rotulo, lambda v=valor: (self.setWindowOpacity(v), salvar(opacidade=v)))
        acao = QAction("Mostrar a legenda", m, checkable=True)
        acao.setChecked(self._mostrar_legenda)
        acao.toggled.connect(self.alternar_legenda)
        m.addAction(acao)
        auto = QAction("Aparecer quando eu minimizar o JARVIS", m, checkable=True)
        auto.setChecked(bool(config().get("auto_minimizar", True)))
        auto.toggled.connect(lambda v: salvar(auto_minimizar=bool(v)))
        m.addAction(auto)
        m.addSeparator()
        m.addAction("Fechar o rosto flutuante", self.close)
        m.exec(e.globalPos())

    def alternar_legenda(self, ligar: bool):
        baixo = self.y() + self.height()
        self._mostrar_legenda = bool(ligar)
        self._aplicar_tamanho()
        self.move(self.x(), baixo - self.height())
        self._garantir_na_tela()
        salvar(legenda=bool(ligar), x=self.x(), y=self.y())

    def closeEvent(self, e):
        self._timer.stop()
        super().closeEvent(e)

    def showEvent(self, e):
        self._t = time.monotonic()
        if not self._timer.isActive():
            self._timer.start(33)
        super().showEvent(e)
