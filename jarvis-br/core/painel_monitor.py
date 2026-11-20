"""
core/painel_monitor.py — o painel 📊 MONITOR do HUD (fork PT-BR 1.2).

Abas: VISÃO GERAL (cartões com mini gráficos), PROCESSOS (tabela ordenável
estilo Gerenciador de Tarefas, com ações), REDE, DISCOS e HISTÓRICO.

DESEMPENHO
    O painel não mede nada: lê a fotografia de core/telemetria.py (a mesma
    fonte do HUD e dos alertas) a cada 2 s com um QTimer. Tudo que demora —
    teste de velocidade, varredura da rede, conexões, SMART, finalizar
    processo — roda numa thread, e o resultado volta por sinal. A thread da
    interface nunca espera nada.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QGridLayout,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QTabWidget, QTextEdit,
                             QVBoxLayout, QWidget)

from core import telemetria

_MONO = "Courier New"


def _tam(n) -> str:
    try:
        from plugins._comum import tamanho
        return tamanho(n)
    except Exception:
        return f"{n}"


def _vel(n) -> str:
    return _tam(n) + "/s"


def _dur(s) -> str:
    try:
        from plugins._comum import duracao
        return duracao(s)
    except Exception:
        return f"{int(s)}s"


# ── mini gráfico ───────────────────────────────────────────────────────────────
class Sparkline(QWidget):
    """Linha simples dos últimos valores. Escala fixa (0–100) ou automática."""

    def __init__(self, cor: str, maximo: float | None = 100.0, parent=None):
        super().__init__(parent)
        self._cor = QColor(cor)
        self._max = maximo
        self._valores: list[float] = []
        self.setMinimumHeight(34)

    def set_valores(self, valores):
        self._valores = [float(v or 0) for v in valores][-150:]
        self.update()

    def paintEvent(self, _e):
        if len(self._valores) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        topo = self._max if self._max else max(max(self._valores), 1e-9) * 1.15
        passo = w / (len(self._valores) - 1)
        caminho = QPainterPath()
        for i, v in enumerate(self._valores):
            ponto = QPointF(i * passo, h - 2 - (h - 4) * min(1.0, v / topo))
            if i == 0:
                caminho.moveTo(ponto)
            else:
                caminho.lineTo(ponto)
        area = QPainterPath(caminho)
        area.lineTo(QPointF(w, h))
        area.lineTo(QPointF(0, h))
        area.closeSubpath()
        fundo = QColor(self._cor)
        fundo.setAlpha(40)
        p.fillPath(area, QBrush(fundo))
        p.setPen(QPen(self._cor, 1.5))
        p.drawPath(caminho)
        p.end()


class Barras(QWidget):
    """Barras horizontais com rótulo e valor (fork PT-BR 1.4, aba MEU DIA)."""

    def __init__(self, cor: str, parent=None):
        super().__init__(parent)
        self._cor = QColor(cor)
        self._itens: list[tuple[str, float, str]] = []
        self.setMinimumHeight(120)

    def set_itens(self, itens):
        self._itens = [(str(n), float(v or 0), str(t)) for n, v, t in itens][:14]
        self.setMinimumHeight(max(120, 22 * len(self._itens) + 8))
        self.update()

    def paintEvent(self, _e):
        if not self._itens:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(QFont(_MONO, 8))
        w = self.width()
        rotulo_w, valor_w = min(200, int(w * 0.32)), 70
        maior = max(v for _n, v, _t in self._itens) or 1.0
        for i, (nome, v, texto) in enumerate(self._itens):
            y = 4 + i * 22
            p.setPen(QPen(QColor("#9fd8ef")))
            p.drawText(0, y, rotulo_w - 8, 18, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       nome[:28])
            largura = max(2.0, (w - rotulo_w - valor_w) * v / maior)
            cor = QColor(self._cor)
            cor.setAlpha(200 - min(120, i * 10))
            p.fillRect(rotulo_w, y + 3, int(largura), 12, QBrush(cor))
            p.setPen(QPen(QColor("#d8f3ff")))
            p.drawText(rotulo_w + int(largura) + 6, y, valor_w, 18,
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)
        p.end()


class _Item(QTableWidgetItem):
    """Célula que ordena pelo valor numérico guardado, não pelo texto."""

    def __init__(self, texto: str, valor=None):
        super().__init__(texto)
        self._valor = valor if valor is not None else texto

    def __lt__(self, outro):
        try:
            return self._valor < outro._valor
        except Exception:
            return str(self.text()) < str(outro.text())


# ── o painel ───────────────────────────────────────────────────────────────────
class PainelMonitor(QFrame):
    _resultado = pyqtSignal(str, object)

    _COLS = ("PID", "NOME", "CPU %", "RAM", "DISCO/s", "CONEXÕES", "THREADS",
             "USUÁRIO", "TEMPO")

    def __init__(self, cores, parent=None):
        super().__init__(parent)
        self.C = cores
        self._tel = telemetria.get()
        self._ocupado: set[str] = set()
        self._ultimo_proc = 0.0
        self._status_ate = 0.0
        self.setObjectName("PainelMonitor")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Fechar destrói o painel (e o timer dele); reabrir cria um novo.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        C = cores
        self.setStyleSheet(f"""
            #PainelMonitor {{ background: rgba(0, 6, 10, 248);
                border: 1px solid {C.BORDER_B}; border-radius: 6px; }}
            QLabel {{ color: {C.TEXT}; background: transparent; }}
            QTabWidget::pane {{ border: 1px solid {C.BORDER}; top: -1px; }}
            QTabBar::tab {{ background: #000d12; color: {C.TEXT_DIM}; padding: 5px 12px;
                border: 1px solid {C.BORDER}; font-family: '{_MONO}'; font-size: 8pt; }}
            QTabBar::tab:selected {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}
            QTableWidget {{ background: #000a10; color: {C.TEXT}; gridline-color: {C.BORDER};
                border: 1px solid {C.BORDER}; font-family: '{_MONO}'; font-size: 8pt;
                selection-background-color: {C.PRI_GHO}; selection-color: {C.PRI}; }}
            QHeaderView::section {{ background: #00131c; color: {C.PRI_DIM};
                border: 1px solid {C.BORDER}; padding: 3px; font-family: '{_MONO}';
                font-size: 7pt; }}
            QLineEdit, QComboBox, QTextEdit {{ background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 6px;
                font-family: '{_MONO}'; font-size: 8pt; }}
            QPushButton {{ background: #00091a; color: {C.PRI}; border: 1px solid {C.PRI_DIM};
                border-radius: 3px; padding: 4px 10px; font-family: '{_MONO}'; font-size: 8pt; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)

        topo = QHBoxLayout()
        titulo = QLabel("📊  MONITOR DO SISTEMA")
        titulo.setFont(QFont(_MONO, 10, QFont.Weight.Bold))
        titulo.setStyleSheet(f"color: {C.PRI};")
        topo.addWidget(titulo)
        topo.addStretch(1)
        self._status = QLabel("")
        self._status.setFont(QFont(_MONO, 8))
        self._status.setStyleSheet(f"color: {C.TEXT_DIM};")
        topo.addWidget(self._status)
        fechar = QPushButton("✕  FECHAR")
        fechar.clicked.connect(self.close)
        topo.addWidget(fechar)
        lay.addLayout(topo)

        self._abas = QTabWidget()
        lay.addWidget(self._abas, 1)
        self._abas.addTab(self._aba_geral(), "VISÃO GERAL")
        self._abas.addTab(self._aba_processos(), "PROCESSOS")
        self._abas.addTab(self._aba_rede(), "REDE")
        self._abas.addTab(self._aba_discos(), "DISCOS")
        self._abas.addTab(self._aba_historico(), "HISTÓRICO")
        self._abas.addTab(self._aba_meu_dia(), "MEU DIA")      # fork PT-BR 1.4
        self._abas.currentChanged.connect(lambda _i: self._atualizar(forcar=True))

        self._resultado.connect(self._ao_resultado)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar)
        self._timer.start(2000)
        self._atualizar(forcar=True)

    # -- ciclo de vida ------------------------------------------------------------
    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        self._timer.stop()
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)

    # -- utilidades ----------------------------------------------------------------
    def _msg(self, texto: str) -> None:
        """Mensagem na linha de status, que fica 8 s antes do relógio voltar."""
        self._status.setText(texto)
        self._status_ate = time.monotonic() + 8
    def _lbl(self, texto="", tam=8, cor=None, negrito=False) -> QLabel:
        l = QLabel(texto)
        l.setFont(QFont(_MONO, tam, QFont.Weight.Bold if negrito else QFont.Weight.Normal))
        if cor:
            l.setStyleSheet(f"color: {cor};")
        l.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return l

    def _tabela(self, colunas) -> QTableWidget:
        t = QTableWidget(0, len(colunas))
        t.setHorizontalHeaderLabels(list(colunas))
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def _em_thread(self, chave: str, funcao, *args):
        """Roda `funcao(*args)` fora da interface; o resultado volta em
        _ao_resultado(chave, valor). Ignora um segundo pedido igual em curso."""
        if chave in self._ocupado:
            return
        self._ocupado.add(chave)

        def trabalho():
            try:
                valor = funcao(*args)
            except Exception as e:
                valor = e
            self._resultado.emit(chave, valor)

        threading.Thread(target=trabalho, daemon=True, name=f"painel-{chave}").start()

    def _ao_resultado(self, chave: str, valor):
        self._ocupado.discard(chave)
        if isinstance(valor, Exception):
            self._msg(f"Erro: {valor}")
            return
        if chave == "velocidade":
            self._btn_vel.setEnabled(True)
            if valor.get("down_mbps") is None:
                self._lbl_vel.setText(f"Falhou: {valor.get('erro')}")
            else:
                from plugins._comum import br
                self._lbl_vel.setText(f"↓ {br(valor['down_mbps'])} Mbps   ↑ {br(valor['up_mbps'] or 0)} Mbps   "
                                      f"ping {br(valor['ping_ms'], 0) if valor.get('ping_ms') else '—'} ms")
        elif chave == "dispositivos":
            self._btn_disp.setEnabled(True)
            self._preencher(self._tab_disp, [
                (d["ip"], d["mac"] or "—", d["nome"] or "—", d["papel"]) for d in valor])
            self._msg(f"{len(valor)} aparelho(s) na rede local")
        elif chave == "conexoes":
            self._preencher(self._tab_conex, [
                (c["processo"], c["pid"], c["tipo"], c["local"], c["remoto"] or "—", c["estado"])
                for c in valor])
        elif chave == "smart":
            self._lbl_smart.setText("\n".join(f"{d['disco']}: {d['saude']}  {d['detalhe']}"
                                              for d in valor) or "SMART não disponível neste sistema.")
        elif chave == "historico":
            self._mostrar_historico(*valor)
        elif chave == "meudia":
            self._mostrar_meu_dia(valor)
        elif chave.startswith("acao"):
            self._msg(str(valor)[:160])
            self._ultimo_proc = 0
        elif chave == "ping":
            self._atualizar(forcar=True)

    def _preencher(self, tabela: QTableWidget, linhas, numericas=()):
        tabela.setSortingEnabled(False)
        tabela.setRowCount(len(linhas))
        for i, linha in enumerate(linhas):
            for j, v in enumerate(linha):
                tabela.setItem(i, j, _Item(str(v), v if j in numericas else None))
        tabela.setSortingEnabled(True)

    # -- VISÃO GERAL ----------------------------------------------------------------
    def _aba_geral(self) -> QWidget:
        C = self.C
        w = QWidget()
        g = QGridLayout(w)
        g.setSpacing(8)
        self._cards = {}
        definicoes = [("cpu", "CPU", C.PRI, 100.0), ("ram", "RAM", C.GREEN, 100.0),
                      ("gpu", "GPU", C.ACC2, 100.0), ("temp", "TEMPERATURA", C.ACC, 100.0),
                      ("down", "DOWNLOAD", C.PRI, None), ("up", "UPLOAD", C.GREEN, None),
                      ("leitura", "DISCO LEITURA", C.TEXT_MED, None),
                      ("escrita", "DISCO ESCRITA", C.ACC2, None)]
        for i, (chave, nome, cor, maximo) in enumerate(definicoes):
            caixa = QFrame()
            caixa.setStyleSheet(f"QFrame {{ border: 1px solid {C.BORDER}; border-radius: 4px; }}")
            v = QVBoxLayout(caixa)
            v.setContentsMargins(8, 6, 8, 6)
            v.setSpacing(2)
            v.addWidget(self._lbl(nome, 7, C.TEXT_DIM))
            valor = self._lbl("—", 13, cor, True)
            detalhe = self._lbl("", 7, C.TEXT_MED)
            graf = Sparkline(cor, maximo)
            v.addWidget(valor)
            v.addWidget(detalhe)
            v.addWidget(graf)
            g.addWidget(caixa, i // 4, i % 4)
            self._cards[chave] = (valor, detalhe, graf)
        self._lbl_nucleos = self._lbl("", 8, C.TEXT_MED)
        self._lbl_nucleos.setWordWrap(True)
        self._lbl_extra = self._lbl("", 8, C.TEXT)
        self._lbl_extra.setWordWrap(True)
        g.addWidget(self._lbl_nucleos, 2, 0, 1, 4)
        g.addWidget(self._lbl_extra, 3, 0, 1, 4)
        g.setRowStretch(4, 1)
        return w

    def _atualizar_geral(self, s: dict):
        ram, gpu, io, rede = s["ram"], s.get("gpu"), s["disco_io"], s["rede"]
        valores = {
            "cpu": (f"{s['cpu']:.0f}%", f"{s.get('cpu_freq_mhz') or '—'} MHz · "
                    f"{s['cpu_nucleos_fisicos']}N/{s['cpu_nucleos_logicos']}T"),
            "ram": (f"{ram.get('pct', 0):.0f}%", f"{_tam(ram.get('usada', 0))} de {_tam(ram.get('total', 0))}"
                    f" · swap {(s.get('swap') or {}).get('pct', 0):.0f}%"),
            "gpu": ((f"{gpu['uso']:.0f}%", f"VRAM {_tam(gpu.get('vram_usada', 0))}/"
                     f"{_tam(gpu.get('vram_total', 0))} · {gpu.get('clock_mhz') or '—'} MHz")
                    if gpu else ("—", "sem GPU NVIDIA")),
            "temp": ((f"{s['cpu_temp']:.0f} °C" if s.get("cpu_temp") is not None else "—"),
                     (f"GPU {gpu['temp']:.0f} °C" if gpu and gpu.get("temp") is not None
                      else "sensor não disponível" if s.get("cpu_temp") is None else "")),
            "down": (_vel(rede.get("down", 0)), f"hoje {_tam(s['rede_hoje']['down'])}"),
            "up": (_vel(rede.get("up", 0)), f"hoje {_tam(s['rede_hoje']['up'])}"),
            "leitura": (_vel(io.get("leitura", 0)), ""),
            "escrita": (_vel(io.get("escrita", 0)), ""),
        }
        for chave, (valor, detalhe) in valores.items():
            lv, ld, graf = self._cards[chave]
            lv.setText(valor)
            ld.setText(detalhe)
            graf.set_valores(self._tel.historico(chave))
        self._lbl_nucleos.setText("NÚCLEOS  " + "  ".join(f"{i}:{v:.0f}%"
                                                         for i, v in enumerate(s.get("cpu_nucleos", []))))
        extra = [f"Ligado há {_dur(s.get('uptime', 0))}", f"{s.get('total_processos')} processos"]
        b = s.get("bateria")
        if b:
            extra.append(f"Bateria {b['pct']:.0f}%{' na tomada' if b['na_tomada'] else ''}")
        for v in s.get("ventoinhas", [])[:3]:
            extra.append(f"{v['nome']} {v['rpm']} RPM")
        procs = s.get("processos") or []
        if procs:
            extra.append(f"Mais CPU: {procs[0]['nome']} ({procs[0]['cpu']:.0f}%)")
        if s.get("internet") is False:
            extra.append("⚠ SEM INTERNET")
        self._lbl_extra.setText("   ·   ".join(extra))

    # -- PROCESSOS ------------------------------------------------------------------
    def _aba_processos(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        barra = QHBoxLayout()
        self._filtro = QLineEdit()
        self._filtro.setPlaceholderText("filtrar por nome ou PID…")
        self._filtro.textChanged.connect(lambda _t: self._atualizar_processos(self._tel.snapshot(), True))
        barra.addWidget(self._filtro, 1)
        for texto, op in (("FINALIZAR", "finalizar"), ("SUSPENDER", "suspender"),
                          ("RETOMAR", "retomar"), ("ABRIR LOCAL", "abrir_local")):
            b = QPushButton(texto)
            b.clicked.connect(lambda _c=False, o=op: self._acao_processo(o))
            barra.addWidget(b)
        self._prio = QComboBox()
        self._prio.addItems(["prioridade…", "baixa", "abaixo", "normal", "acima", "alta"])
        self._prio.activated.connect(self._mudar_prioridade)
        barra.addWidget(self._prio)
        v.addLayout(barra)
        self._tab_proc = self._tabela(self._COLS)
        self._tab_proc.setSortingEnabled(True)
        self._tab_proc.sortItems(2, Qt.SortOrder.DescendingOrder)
        v.addWidget(self._tab_proc, 1)
        v.addWidget(self._lbl("Conexões = conexões de rede abertas pelo processo. O Windows não "
                              "informa bytes de rede por processo sem um driver.", 7, self.C.TEXT_DIM))
        return w

    def _pids_selecionados(self) -> list[int]:
        pids = []
        for idx in self._tab_proc.selectionModel().selectedRows():
            item = self._tab_proc.item(idx.row(), 0)
            if item and item.text().isdigit():
                pids.append(int(item.text()))
        return pids

    def _atualizar_processos(self, s: dict, forcar=False):
        if not forcar and time.monotonic() - self._ultimo_proc < 5.5:
            return
        self._ultimo_proc = time.monotonic()
        filtro = self._filtro.text().strip().lower()
        procs = s.get("processos") or []
        if filtro:
            procs = [p for p in procs if filtro in p["nome"].lower() or filtro == str(p["pid"])]
        procs = procs[:250]
        selecionados = set(self._pids_selecionados())
        agora = time.time()
        t = self._tab_proc
        t.setUpdatesEnabled(False)
        t.setSortingEnabled(False)
        t.setRowCount(len(procs))
        for i, p in enumerate(procs):
            idade = agora - p["inicio"] if p["inicio"] else 0
            celulas = [(str(p["pid"]), p["pid"]), (p["nome"], p["nome"].lower()),
                       (f"{p['cpu']:.1f}", p["cpu"]), (_tam(p["ram"]), p["ram"]),
                       (_vel(p["disco"]), p["disco"]), (str(p.get("conexoes", 0)), p.get("conexoes", 0)),
                       (str(p["threads"]), p["threads"]), (p["usuario"], p["usuario"]),
                       (_dur(idade) if idade else "—", idade)]
            for j, (texto, valor) in enumerate(celulas):
                t.setItem(i, j, _Item(texto, valor))
        t.setSortingEnabled(True)
        if selecionados:
            t.clearSelection()
            for i in range(t.rowCount()):
                item = t.item(i, 0)
                if item and item.text().isdigit() and int(item.text()) in selecionados:
                    t.selectRow(i)
        t.setUpdatesEnabled(True)

    def _acao_processo(self, operacao: str):
        pids = self._pids_selecionados()
        if not pids:
            self._msg("Selecione um processo na tabela.")
            return
        from plugins import _processos as po
        if operacao == "finalizar":
            nomes = ", ".join(self._tab_proc.item(i.row(), 1).text()
                              for i in self._tab_proc.selectionModel().selectedRows())
            resp = QMessageBox.question(self, "Finalizar processo",
                                        f"Finalizar {nomes}?\nO que não foi salvo será perdido.")
            if resp != QMessageBox.StandardButton.Yes:
                return
            self._em_thread("acao-finalizar", lambda: po.finalizar(po.achar_pids(pids)))
        elif operacao == "suspender":
            self._em_thread("acao-suspender", lambda: po.suspender(po.achar_pids(pids)))
        elif operacao == "retomar":
            self._em_thread("acao-retomar", lambda: po.retomar_pids(pids))
        elif operacao == "abrir_local":
            procs = po.achar_pids(pids[:1])
            if procs:
                self._em_thread("acao-local", lambda: po.abrir_local(procs[0]))

    def _mudar_prioridade(self, indice: int):
        if indice <= 0:
            return
        nivel = self._prio.itemText(indice)
        self._prio.setCurrentIndex(0)
        pids = self._pids_selecionados()
        if not pids:
            self._msg("Selecione um processo na tabela.")
            return
        from plugins import _processos as po
        self._em_thread("acao-prioridade", lambda: po.prioridade(po.achar_pids(pids), nivel))

    # -- REDE -------------------------------------------------------------------------
    def _aba_rede(self) -> QWidget:
        C = self.C
        w = QWidget()
        v = QVBoxLayout(w)
        self._lbl_rede = self._lbl("", 8, C.TEXT)
        self._lbl_rede.setWordWrap(True)
        v.addWidget(self._lbl_rede)
        botoes = QHBoxLayout()
        self._btn_vel = QPushButton("⚡ TESTE DE VELOCIDADE")
        self._btn_vel.clicked.connect(self._testar_velocidade)
        self._btn_disp = QPushButton("📡 QUEM ESTÁ NA MINHA REDE")
        self._btn_disp.clicked.connect(self._procurar_dispositivos)
        b_conex = QPushButton("🔗 CONEXÕES ATIVAS")
        b_conex.clicked.connect(lambda: self._em_thread("conexoes", telemetria.conexoes_ativas, 300))
        b_ping = QPushButton("↻ PING AGORA")
        b_ping.clicked.connect(lambda: self._em_thread("ping", self._tel.medir_ping_agora))
        for b in (self._btn_vel, self._btn_disp, b_conex, b_ping):
            botoes.addWidget(b)
        botoes.addStretch(1)
        v.addLayout(botoes)
        self._lbl_vel = self._lbl("Teste de velocidade: ainda não rodou.", 8, C.ACC2)
        v.addWidget(self._lbl_vel)
        self._tab_if = self._tabela(("INTERFACE", "↓ AGORA", "↑ AGORA", "↓ TOTAL", "↑ TOTAL"))
        self._tab_if.setMaximumHeight(130)
        v.addWidget(self._tab_if)
        abas = QTabWidget()
        self._tab_disp = self._tabela(("IP", "MAC", "NOME", "PAPEL"))
        self._tab_conex = self._tabela(("PROCESSO", "PID", "TIPO", "LOCAL", "REMOTO", "ESTADO"))
        self._tab_conex.setSortingEnabled(True)
        abas.addTab(self._tab_disp, "DISPOSITIVOS DA REDE")
        abas.addTab(self._tab_conex, "CONEXÕES")
        v.addWidget(abas, 1)
        return w

    def _testar_velocidade(self):
        self._btn_vel.setEnabled(False)
        self._lbl_vel.setText("Testando… (uns 15 segundos)")
        self._em_thread("velocidade", telemetria.teste_velocidade)

    def _procurar_dispositivos(self):
        self._btn_disp.setEnabled(False)
        self._msg("Procurando aparelhos na sua rede local…")
        self._em_thread("dispositivos", telemetria.dispositivos_rede, True)

    def _atualizar_rede(self, s: dict):
        ping, wifi = s.get("ping") or {}, s.get("wifi") or {}

        def pg(k):
            p = ping.get(k) or {}
            if p.get("ms") is None:
                return "sem resposta"
            return f"{p['ms']:.0f} ms" + (f" · {p['perda']:.0f}% perda" if p.get("perda") else "")

        estado = {True: "CONECTADA", False: "⚠ SEM INTERNET", None: "verificando…"}[s.get("internet")]
        self._lbl_rede.setText(
            f"Internet: {estado}    IP local {s.get('ip_local') or '—'}    "
            f"IP público {s.get('ip_publico') or '—'}\n"
            f"Gateway {s.get('gateway') or '—'} ({pg('gateway')})    "
            f"DNS {', '.join(s.get('dns') or []) or '—'}\n"
            f"Ping Google {pg('8.8.8.8')}    Cloudflare {pg('1.1.1.1')}    "
            f"Wi-Fi {wifi.get('ssid') or '—'}"
            + (f" · sinal {wifi['sinal']}%" if wifi.get("sinal") is not None else "")
            + f"\nHoje: ↓ {_tam(s['rede_hoje']['down'])}   ↑ {_tam(s['rede_hoje']['up'])}")
        ifs = sorted(s["rede"]["interfaces"].items(), key=lambda kv: -(kv[1]["down"] + kv[1]["up"]))
        self._preencher(self._tab_if, [(n, _vel(i["down"]), _vel(i["up"]), _tam(i["total_down"]),
                                        _tam(i["total_up"])) for n, i in ifs])

    # -- DISCOS -----------------------------------------------------------------------
    def _aba_discos(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self._tab_disc = self._tabela(("UNIDADE", "TIPO", "USADO", "LIVRE", "TOTAL", "USO"))
        v.addWidget(self._tab_disc, 1)
        self._lbl_io = self._lbl("", 8, self.C.TEXT)
        v.addWidget(self._lbl_io)
        b = QPushButton("🩺 VERIFICAR SAÚDE (SMART)")
        b.clicked.connect(lambda: self._em_thread("smart", telemetria.saude_discos, True))
        v.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        self._lbl_smart = self._lbl("", 8, self.C.TEXT_MED)
        v.addWidget(self._lbl_smart)
        return w

    def _atualizar_discos(self, s: dict):
        linhas = []
        for p in s.get("particoes", []):
            barra = "█" * int(p["pct"] / 10) + "░" * (10 - int(p["pct"] / 10))
            alerta = "  ⚠" if 100 - p["pct"] < 10 else ""
            linhas.append((p["ponto"], p["tipo"], _tam(p["usado"]), _tam(p["livre"]),
                           _tam(p["total"]), f"{barra} {p['pct']:.0f}%{alerta}"))
        self._preencher(self._tab_disc, linhas)
        io = s["disco_io"]
        self._lbl_io.setText(f"Leitura {_vel(io['leitura'])}    Escrita {_vel(io['escrita'])}")

    # -- HISTÓRICO --------------------------------------------------------------------
    def _aba_historico(self) -> QWidget:
        C = self.C
        w = QWidget()
        v = QVBoxLayout(w)
        barra = QHBoxLayout()
        self._periodo = QComboBox()
        self._periodo.addItems(["Últimas 24 horas", "Últimos 7 dias"])
        self._periodo.activated.connect(lambda _i: self._carregar_historico())
        barra.addWidget(self._periodo)
        b = QPushButton("↻ ATUALIZAR")
        b.clicked.connect(self._carregar_historico)
        barra.addWidget(b)
        barra.addStretch(1)
        v.addLayout(barra)
        self._hist_graf = {}
        grade = QGridLayout()
        for i, (chave, nome, cor, maximo) in enumerate((("cpu", "CPU %", C.PRI, 100.0),
                                                        ("ram", "RAM %", C.GREEN, 100.0),
                                                        ("temp", "TEMPERATURA", C.ACC, None),
                                                        ("down", "DOWNLOAD", C.ACC2, None))):
            grade.addWidget(self._lbl(nome, 7, C.TEXT_DIM), (i // 2) * 2, i % 2)
            g = Sparkline(cor, maximo)
            g.setMinimumHeight(60)
            grade.addWidget(g, (i // 2) * 2 + 1, i % 2)
            self._hist_graf[chave] = g
        v.addLayout(grade)
        self._hist_txt = QTextEdit()
        self._hist_txt.setReadOnly(True)
        v.addWidget(self._hist_txt, 1)
        return w

    def _carregar_historico(self):
        dias = 7 if self._periodo.currentIndex() == 1 else 1

        def ler():
            from plugins import _monitor_db as db
            desde = (datetime.now() - timedelta(days=dias)).timestamp()
            return db.amostras(desde), db.resumo(desde)

        self._em_thread("historico", ler)

    def _mostrar_historico(self, amostras, resumo):
        passo = max(1, len(amostras) // 300)
        reduzidas = amostras[::passo]
        for chave, g in self._hist_graf.items():
            g.set_valores([a.get(chave) or 0 for a in reduzidas])
        if not resumo.get("amostras"):
            self._hist_txt.setPlainText("Ainda não há histórico. Com o plugin monitor_sistema "
                                        "ligado, é gravada uma amostra por minuto.")
            return

        def f(v, suf="%"):
            return "—" if v is None else f"{v:.0f}{suf}"

        linhas = [f"{resumo['minutos_ligado']} minutos registrados",
                  f"CPU média {f(resumo['cpu_media'])} · pico {f(resumo['cpu_max'])}",
                  f"RAM média {f(resumo['ram_media'])} · pico {f(resumo['ram_max'])}",
                  f"Temperatura máx {f(resumo['temp_max'], ' °C')}",
                  f"Rede ↓ {_tam(resumo['total_down'])} · ↑ {_tam(resumo['total_up'])}",
                  f"Minutos sem internet: {resumo['minutos_sem_internet']}", "", "EVENTOS"]
        for e in resumo["eventos"][:60]:
            linhas.append(f"{datetime.fromtimestamp(e['ts']).strftime('%d/%m %H:%M')}  {e['mensagem']}")
        self._hist_txt.setPlainText("\n".join(linhas))

    # -- MEU DIA (fork PT-BR 1.4: linha do tempo da janela em foco) -------------------
    def _aba_meu_dia(self) -> QWidget:
        C = self.C
        w = QWidget()
        v = QVBoxLayout(w)
        barra = QHBoxLayout()
        self._md_periodo = QComboBox()
        self._md_periodo.addItems(["Hoje", "Ontem", "Esta semana", "Últimos 7 dias", "Este mês"])
        self._md_periodo.activated.connect(lambda _i: self._carregar_meu_dia())
        barra.addWidget(self._md_periodo)
        self._md_termo = QLineEdit()
        self._md_termo.setPlaceholderText("projeto, site ou app (ex.: jarvis) — vazio = tudo")
        self._md_termo.returnPressed.connect(self._carregar_meu_dia)
        barra.addWidget(self._md_termo, 1)
        b = QPushButton("↻ ATUALIZAR")
        b.clicked.connect(self._carregar_meu_dia)
        barra.addWidget(b)
        v.addLayout(barra)
        self._md_titulo = self._lbl("", 8, C.PRI, True)
        v.addWidget(self._md_titulo)
        self._md_barras = Barras(C.PRI)
        v.addWidget(self._md_barras)
        self._md_txt = QTextEdit()
        self._md_txt.setReadOnly(True)
        v.addWidget(self._md_txt, 1)
        return w

    def mostrar_meu_dia(self, termo: str = "", periodo: int | None = None) -> None:
        self._abas.setCurrentIndex(5)
        self._md_termo.setText(termo or "")
        if periodo is not None:
            self._md_periodo.setCurrentIndex(periodo)
        elif termo:
            self._md_periodo.setCurrentIndex(2)
        self._carregar_meu_dia()

    def _carregar_meu_dia(self):
        rotulos = ["hoje", "ontem", "semana", "7 dias", "mes"]
        periodo = rotulos[max(0, self._md_periodo.currentIndex())]
        termo = self._md_termo.text().strip()

        def ler():
            from plugins import linha_do_tempo as lt
            desde, ate, rot = lt.periodo(periodo)
            r = lt.resumo(desde, ate)
            r["rotulo"], r["termo"] = rot, termo
            if termo:
                r["total_termo"], r["por_dia"] = lt.tempo_em(termo, desde, ate, r["focos"])
            return r

        self._em_thread("meudia", ler)

    def _mostrar_meu_dia(self, r: dict):
        from plugins.linha_do_tempo import dur
        if r.get("termo"):
            self._md_titulo.setText(f"{r['termo'].upper()} — {dur(r['total_termo'])} {r['rotulo']}")
            self._md_barras.set_itens([(datetime.fromisoformat(d).strftime("%a %d/%m"), s, dur(s))
                                       for d, s in sorted(r["por_dia"].items())])
        else:
            self._md_titulo.setText(f"{dur(r['ativo_s'])} no PC {r['rotulo']} · longe: {dur(r['ausente_s'])}")
            self._md_barras.set_itens([(n, s, dur(s)) for n, s in r["atividades"]])
        if not r["focos"]:
            self._md_txt.setPlainText("Ainda não há registro. A linha do tempo conta a janela em foco "
                                      "enquanto o JARVIS está aberto.")
            return
        linhas = []
        if r["projetos"]:
            linhas += ["PROJETOS"] + [f"  {dur(s):>8}  {n}" for n, s in r["projetos"][:8]] + [""]
        linhas.append("LINHA DO TEMPO")
        termo = (r.get("termo") or "").lower()
        from plugins.linha_do_tempo import juntar
        for f in juntar(r["focos"])[-400:]:
            if f["fim"] - f["inicio"] < 60:
                continue
            texto = f"{f['atividade']} {f.get('projeto') or ''} {f.get('titulo') or ''}".lower()
            if termo and termo not in texto and f["atividade"] != "ausente":
                continue
            linhas.append(f"  {datetime.fromtimestamp(f['inicio']):%d/%m %H:%M}–{datetime.fromtimestamp(f['fim']):%H:%M}"
                          f"  {f['atividade']:<16} {('· ' + f['projeto']) if f.get('projeto') else ''}"
                          f"  {(f.get('titulo') or '')[:60]}")
        self._md_txt.setPlainText("\n".join(linhas))

    # -- ciclo ------------------------------------------------------------------------
    def _atualizar(self, forcar: bool = False):
        if not self.isVisible() and not forcar:
            return
        try:
            s = self._tel.snapshot()
            aba = self._abas.currentIndex()
            if aba == 0:
                self._atualizar_geral(s)
            elif aba == 1:
                self._atualizar_processos(s, forcar)
            elif aba == 2:
                self._atualizar_rede(s)
            elif aba == 3:
                self._atualizar_discos(s)
            elif aba == 4 and forcar:
                self._carregar_historico()
            elif aba == 5 and forcar:
                self._carregar_meu_dia()
            if not self._ocupado and time.monotonic() > self._status_ate:
                self._status.setText(datetime.now().strftime("atualizado %H:%M:%S"))
        except Exception as e:
            self._msg(f"Erro ao atualizar: {e}")
