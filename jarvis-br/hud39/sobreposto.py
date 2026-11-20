"""
Painéis por cima da interface, barra de música e botão de troca (fork PT-BR 3.9.3).

Tudo desenhado pelo Qt DENTRO da janela principal: nada abre aba nem janela nova. É um "mixin" usado
pelo HUD 3.9 (J.A.R.V.I.S) e pela F.R.I.D.A.Y (SEXTA-FEIRA), em coordenadas virtuais de cada um.

O que um clique pode fazer:
  • abrir/fechar um painel aqui mesmo (Sistema, Internet, Música, Vídeos, Arquivos, Jogos, Config,
    Processos, GPU, Discos, Diagnóstico, Sobre);
  • ações locais, numa thread (abrir pasta, teclas de mídia, navegador, Steam, ping) — as mesmas de
    hud39/servidor.py, chamadas direto, sem servidor;
  • pedir algo à janela, devolvendo um dict: {"tipo": "comando"|"focar"|"estilo"|"janela", ...}.
"""
from __future__ import annotations

import threading
import time

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPolygonF

NOMES = {"friday": "SEXTA-FEIRA", "hud39": "J.A.R.V.I.S"}
ICONES = ("@ant", "@play", "@prox", "@menos", "@mais", "@yt", "@salvos")
PAINEL_DO_ICONE = {"@yt": "youtube", "@salvos": "salvos"}
TECLAS = {"@ant": "anterior", "@play": "tocar", "@prox": "proxima", "@menos": "vol_menos", "@mais": "vol_mais",
          "@mudo": "mudo"}


def _tam(b) -> str:
    if not b:
        return "--"
    u = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    b = float(b)
    while b >= 1024 and i < 4:
        b /= 1024
        i += 1
    return f"{b:.1f} {u[i]}" if i > 2 else f"{b:.0f} {u[i]}"


def _dur(s) -> str:
    s = int(s or 0)
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return (f"{d}d " if d else "") + f"{h}h {m:02d}min"


def quebrar(texto: str, limite: int) -> tuple[str, str]:
    """Duas linhas sem cortar palavra no meio (a 2ª pode terminar em …). Pura."""
    texto = " ".join(str(texto or "").split())
    if len(texto) <= limite:
        return texto, ""
    corte = texto.rfind(" ", 0, limite + 1)
    if corte <= 0:
        corte = limite
    return texto[:corte].rstrip(), texto[corte:].strip()


class Sobreposto:
    """Precisa de: LW, LH, COR_ONDA, ESTILO, BARRA (x, y, w, h), TROCA (x, y, w, h), _dados, _fixo, _txt,
    _aviso, _ondas e as funções de cor de qt_hud."""

    ESTILO = "hud39"
    BARRA = (0.0, 0.0, 0.0, 0.0)
    TROCA = (0.0, 0.0, 0.0, 0.0)

    def _ini_sobreposto(self):
        self._painel: str | None = None
        self._t_painel = 0.0
        self._botoes: list = []          # [(QRectF, acao)] do painel aberto (refeito a cada pintura)
        self._hover_btn = None           # ("p", i) | ("b", i) | ("x",) | ("t",)
        self._ocupado = False
        self._busca = None               # hud39.youtube.Busca em andamento/pronta
        self._imgs: dict = {}            # id do vídeo → QImage da miniatura

    def buscar_youtube(self, termo: str) -> None:
        """Começa a pesquisa e já abre o painel (os resultados chegam sozinhos)."""
        from hud39.youtube import Busca
        self._busca = Busca(termo)
        self.abrir_painel("youtube")

    # ── geometria ────────────────────────────────────────────────────────────
    def _caixa_painel(self) -> QRectF:
        w, h = self.LW * .58, self.LH * .74
        return QRectF((self.LW - w) / 2, self.LH * .10, w, h)

    def _botoes_barra(self):
        x, y, w, h = self.BARRA
        n = len(ICONES)
        passo = w / n
        return [(QRectF(x + i * passo + 3, y, passo - 6, h), ICONES[i]) for i in range(n)]

    def _virtual(self, x, y, W, H):
        s, ox, oy = self.encaixe(W, H)
        return ((x - ox) / s, (y - oy) / s) if s > 0 else (-1.0, -1.0)

    def _achar(self, ax, ay):
        """O que está sob o ponto (já em coordenadas virtuais)."""
        if self._painel:
            cx = self._caixa_painel()
            if QRectF(cx.x() + cx.width() - 52, cx.y() + 10, 40, 40).contains(QPointF(ax, ay)):
                return ("x",)
            for i, (r, _a) in enumerate(self._botoes):
                if r.contains(QPointF(ax, ay)):
                    return ("p", i)
            return ("dentro",) if cx.contains(QPointF(ax, ay)) else ("fora",)
        for i, (r, _a) in enumerate(self._botoes_barra()):
            if r.contains(QPointF(ax, ay)):
                return ("b", i)
        if QRectF(*self.TROCA).contains(QPointF(ax, ay)):
            return ("t",)
        return None

    # ── eventos ──────────────────────────────────────────────────────────────
    def mover(self, x, y, W, H):
        ax, ay = self._virtual(x, y, W, H)
        alvo = self._achar(ax, ay)
        self._hover_btn = alvo if alvo and alvo[0] in ("p", "b", "x", "t") else None
        if self._painel:
            self._hover = self._hover_rect = None
            return "botao" if self._hover_btn else None
        if self._hover_btn:
            self._hover = self._hover_rect = None
            return "botao"
        return super().mover(x, y, W, H)

    def sair(self):
        self._hover_btn = None
        super().sair()

    def clicar(self, x, y, W, H):
        """Um clique. Devolve um pedido para a janela (dict) ou None (resolvido aqui)."""
        ax, ay = self._virtual(x, y, W, H)
        agora = time.time()
        self._ondas = [o for o in self._ondas if agora - o[2] < 0.8][-5:] + [(ax, ay, agora)]
        alvo = self._achar(ax, ay)
        if self._painel:
            if alvo and alvo[0] == "p":
                return self._executar(self._botoes[alvo[1]][1])
            if alvo and alvo[0] in ("x", "fora"):
                self.fechar_painel()
            return None
        if alvo and alvo[0] == "b":
            ic = self._botoes_barra()[alvo[1]][1]
            if ic in PAINEL_DO_ICONE:
                self.abrir_painel(PAINEL_DO_ICONE[ic])
                return None
            return self._executar({"acao": "midia", "tecla": TECLAS[ic]})
        if alvo and alvo[0] == "t":
            outro = "hud39" if self.ESTILO == "friday" else "friday"
            return {"tipo": "estilo", "estilo": outro}
        nome = self.alvo_em(x, y, W, H)
        if nome == "comando":
            self._aviso = (self.texto_aviso("comando"), agora)
            return {"tipo": "focar", "texto": ""}
        if nome:
            self.abrir_painel(nome)
        return None

    def abrir_painel(self, nome: str):
        self._painel = nome
        self._t_painel = time.time()
        self._hover = self._hover_rect = None

    def fechar_painel(self):
        self._painel = None
        self._botoes = []
        self._hover_btn = None

    @property
    def painel_aberto(self) -> bool:
        return bool(self._painel)

    def _executar(self, acao: dict):
        if "tipo" in acao:
            tipo = acao["tipo"]
            if tipo == "painel":
                self.abrir_painel(acao["nome"])
                return None
            if tipo == "salvar_video":
                from hud39 import salvos
                salvos.adicionar(acao.get("titulo", ""), "video", acao.get("url", ""), acao.get("titulo", ""))
                self._aviso = ("★ Vídeo salvo", time.time())
                return None
            if tipo == "apagar":
                from hud39 import salvos
                salvos.apagar(acao.get("id", ""))
                self._aviso = ("Item apagado", time.time())
                return None
            if tipo in ("comando", "focar", "tocar"):
                self.fechar_painel()
            if tipo == "comando":
                self._aviso = (f"Pedido enviado: “{acao['texto']}”", time.time())
            if tipo == "tocar":
                self._aviso = ("Abrindo o vídeo na tela…", time.time())
            return acao
        if self._ocupado:
            return None
        self._ocupado = True
        rotulos = {"anterior": "⏮ Anterior", "tocar": "⏯ Tocar / pausar", "proxima": "⏭ Próxima",
                   "vol_menos": "Volume −", "vol_mais": "Volume +", "mudo": "Som mudo"}
        if acao.get("acao") == "midia":
            self._aviso = (rotulos.get(acao.get("tecla"), "Mídia"), time.time())

        def trabalho():
            try:
                from hud39.servidor import executar
                r = executar(acao)
                resp = r.get("resposta")
                if isinstance(resp, dict):          # ping
                    ms = [v.get("ms") for v in resp.values() if isinstance(v, dict) and v.get("ms") is not None]
                    resp = f"Ping: {round(ms[0])} ms" if ms else "Sem resposta do ping"
                if acao.get("acao") != "midia" or not r.get("ok"):
                    self._aviso = (str(resp or ("Feito" if r.get("ok") else "Não deu certo")), time.time())
            except Exception as e:
                self._aviso = (f"Falhou: {e}", time.time())
            finally:
                self._ocupado = False
        threading.Thread(target=trabalho, daemon=True, name="hud-acao").start()
        return None

    # ── conteúdo dos painéis ─────────────────────────────────────────────────
    def _modelo(self, nome: str) -> dict:
        d, f = self._dados, self._fixo
        assist = "SEXTA-FEIRA" if self.ESTILO == "friday" else "JARVIS"
        gpu = d.get("gpu") if isinstance(d.get("gpu"), dict) else None
        ping = d.get("ping")
        ping_txt = "--" if ping is None else f"{round(ping)} ms"
        pct = lambda v: "--" if v is None else f"{round(v)}%"  # noqa: E731
        vel = lambda b: "--" if b is None else (f"{b / 1048576:.1f} MB/s" if b >= 1048576 else f"{b / 1024:.1f} KB/s")  # noqa: E731,E501
        m = {"linhas": [], "botoes": [], "lista": []}
        if nome == "sistema":
            m["titulo"] = "SOBRE O SISTEMA"
            m["linhas"] = [("Sistema", f"{f.get('so', '…')} {f.get('versao', '')}".strip()),
                           ("Build", f.get("build", "…")),
                           ("Arquitetura", f.get("arquitetura", "…")),
                           ("Computador", f.get("computador", "…")),
                           ("Processador", f.get("cpu_nome", "…")),
                           ("Núcleos", f"{f.get('nucleos_fisicos', '?')} físicos · {f.get('nucleos_logicos', '?')} lógicos"),
                           ("Memória RAM", _tam(f.get("ram_total"))),
                           ("Placa de vídeo", (gpu or {}).get("nome") or "não informada"),
                           ("Ligado há", _dur(d.get("uptime"))),
                           ("IP local", d.get("ip_local") or "--")]
            m["botoes"] = [("Diagnóstico", {"tipo": "painel", "nome": "diagnostico"}),
                           ("Discos", {"tipo": "painel", "nome": "discos"}),
                           ("Processos", {"tipo": "painel", "nome": "processos"}),
                           (f"Sobre o {assist}" if assist == "JARVIS" else "Sobre a SEXTA-FEIRA", {"tipo": "painel", "nome": "jarvis"})]
        elif nome == "internet":
            m["titulo"] = "INTERNET E REDE"
            m["linhas"] = [("Conexão", "online" if d.get("internet") is not False else "SEM INTERNET"),
                           ("Wi-Fi", (d.get("wifi") or {}).get("ssid") or "cabo / não informado"),
                           ("Ping", ping_txt), ("Download agora", vel(d.get("down"))), ("Upload agora", vel(d.get("up"))),
                           ("IP local", d.get("ip_local") or "--"), ("IP público", d.get("ip_publico") or "--"),
                           ("Roteador", d.get("gateway") or "--")]
            m["botoes"] = [("📡 Medir ping", {"acao": "ping"}),
                           ("▶ Pesquisar no YouTube", {"tipo": "focar", "texto": "youtube: "}),
                           ("⚡ Teste de velocidade", {"tipo": "comando", "texto": "faz um teste de velocidade da internet"}),
                           ("🔎 Pesquisar…", {"tipo": "focar", "texto": "pesquisa na internet: "})]
        elif nome == "musica":
            m["titulo"] = "MÚSICA"
            m["linhas"] = [("Controles", "teclas de mídia do Windows: Spotify, YouTube, players…")]
            m["botoes"] = [("@ant", {"acao": "midia", "tecla": "anterior"}), ("@play", {"acao": "midia", "tecla": "tocar"}),
                           ("@prox", {"acao": "midia", "tecla": "proxima"}), ("@menos", {"acao": "midia", "tecla": "vol_menos"}),
                           ("@mudo", {"acao": "midia", "tecla": "mudo"}), ("@mais", {"acao": "midia", "tecla": "vol_mais"}),
                           ("♫ Tocar uma música", {"tipo": "comando", "texto": "toca uma música"}),
                           ("🔎 Música no YouTube", {"tipo": "focar", "texto": "youtube: "}),
                           ("📁 Pasta Música", {"acao": "pasta", "pasta": "musica"})]
        elif nome == "videos":
            m["titulo"] = "VÍDEOS"
            m["linhas"] = [("Pesquisar", "digite na caixa:  youtube: o que você quer ver"),
                           ("Onde toca", f"aqui na tela do {assist}, sem abrir o YouTube")]
            m["botoes"] = [("🔎 Pesquisar no YouTube", {"tipo": "focar", "texto": "youtube: "}),
                           ("★ Vídeos salvos", {"tipo": "painel", "nome": "salvos"}),
                           ("📁 Pasta Vídeos", {"acao": "pasta", "pasta": "videos"})]
        elif nome == "arquivos":
            m["titulo"] = "ARQUIVOS"
            m["botoes"] = [("📄 Documentos", {"acao": "pasta", "pasta": "documentos"}),
                           ("⬇ Downloads", {"acao": "pasta", "pasta": "downloads"}),
                           ("🖼 Imagens", {"acao": "pasta", "pasta": "imagens"}),
                           ("🖥 Área de trabalho", {"acao": "pasta", "pasta": "area"}),
                           ("🏠 Pasta pessoal", {"acao": "pasta", "pasta": "casa"}),
                           ("🧹 Organizar Downloads", {"tipo": "comando", "texto": "organiza a minha pasta de downloads"})]
        elif nome == "jogos":
            m["titulo"] = "JOGOS"
            m["linhas"] = [("CPU", pct(d.get("cpu"))), ("RAM", pct(d.get("ram"))),
                           ("GPU", pct((gpu or {}).get("uso")) if gpu else "--"), ("Ping", ping_txt)]
            m["botoes"] = [("🎮 Steam", {"acao": "steam"}), ("⚡ Modo jogo", {"tipo": "comando", "texto": "ativa o modo jogo"}),
                           ("👾 Arcade", {"tipo": "comando", "texto": "abre o arcade"})]
        elif nome == "config":
            m["titulo"] = "CONFIGURAÇÕES"
            outro = "hud39" if self.ESTILO == "friday" else "friday"
            m["linhas"] = [("Interface agora", NOMES.get(self.ESTILO, self.ESTILO))]
            m["botoes"] = [(f"⇄ Trocar para {NOMES[outro]}", {"tipo": "estilo", "estilo": outro}),
                           ("🧑 Rosto animado", {"tipo": "estilo", "estilo": "face"}),
                           ("◉ Núcleo reator", {"tipo": "estilo", "estilo": "core"}),
                           ("★ Salvos", {"tipo": "painel", "nome": "salvos"})]
        elif nome == "processos":
            m["titulo"] = "PROCESSOS"
            m["lista"] = [(pr["nome"], f"{pr['cpu']:.1f}%   {_tam(pr.get('ram'))}") for pr in d.get("procs") or []]
            m["botoes"] = [("📊 Monitor completo", {"tipo": "comando", "texto": "abre o monitor do sistema"})]
        elif nome == "gpu":
            m["titulo"] = "PLACA DE VÍDEO"
            if gpu:
                m["linhas"] = [("Modelo", gpu.get("nome") or "--"), ("Uso", pct(gpu.get("uso"))),
                               ("Temperatura", "--" if gpu.get("temp") is None else f"{round(gpu['temp'])}°C"),
                               ("Memória de vídeo", f"{round(gpu.get('vram_usada') or 0)} de {round(gpu.get('vram_total') or 0)} MB"
                                if gpu.get("vram_total") else "--")]
            else:
                m["linhas"] = [("Placa", "não informada (uso e temperatura aparecem em placas NVIDIA)")]
        elif nome == "discos":
            m["titulo"] = "MEMÓRIA E DISCOS"
            m["linhas"] = [("RAM em uso", pct(d.get("ram")))]
            m["lista"] = [(str(p.get("ponto")), f"{_tam(p.get('usado'))} de {_tam(p.get('total'))}  ({pct(p.get('pct'))})")
                          for p in d.get("particoes") or []]
        elif nome == "diagnostico":
            m["titulo"] = "DIAGNÓSTICO"

            def nota(v, a, b):
                if v is None:
                    return "não informado"
                return "ALTO" if v >= b else ("atenção" if v >= a else "normal")
            temp = d.get("temp")
            m["lista"] = [("Processador", f"{pct(d.get('cpu'))} — {nota(d.get('cpu'), 70, 90)}"),
                          ("Memória RAM", f"{pct(d.get('ram'))} — {nota(d.get('ram'), 75, 90)}"),
                          ("Disco principal", f"{pct(d.get('disco'))} — {nota(d.get('disco'), 80, 92)}"),
                          ("Temperatura CPU", ("--" if temp is None else f"{round(temp)}°C") + f" — {nota(temp, 75, 88)}"),
                          ("Internet", "SEM REDE" if d.get("internet") is False else f"{ping_txt} — {nota(ping, 80, 200)}")]
            if gpu:
                m["lista"].append(("Placa de vídeo", f"{pct(gpu.get('uso'))} — {nota(gpu.get('temp'), 75, 85)}"))
            m["botoes"] = [(f"🧠 Pedir análise ao {assist}", {"tipo": "comando", "texto": "analisa a saúde do meu PC"})]
        else:  # "jarvis"
            m["titulo"] = "SOBRE A SEXTA-FEIRA" if self.ESTILO == "friday" else "SOBRE O J.A.R.V.I.S"
            m["linhas"] = [("Assistente", "J.A.R.V.I.S BR"), ("Versão", str(f.get("jarvis_versao", "3.9"))),
                           ("Interface", NOMES.get(self.ESTILO, self.ESTILO)), ("Plugins", str(f.get("plugins", "--"))),
                           ("Python", str(f.get("python", "--")))]
            outro = "hud39" if self.ESTILO == "friday" else "friday"
            m["botoes"] = [(f"⇄ Trocar para {NOMES[outro]}", {"tipo": "estilo", "estilo": outro})]
        return m

    # ── pintura ──────────────────────────────────────────────────────────────
    def _icone(self, p: QPainter, r: QRectF, nome: str, cor: QColor):
        cx, cy, k = r.center().x(), r.center().y(), min(r.width(), r.height()) * .22
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(cor))

        def tri(x, y, d):           # d = +1 aponta para a direita
            p.drawPolygon(QPolygonF([QPointF(x - d * k * .8, y - k), QPointF(x - d * k * .8, y + k),
                                     QPointF(x + d * k * .8, y)]))
        if nome == "@yt":
            caixa = QRectF(cx - k * 1.5, cy - k * 1.05, k * 3, k * 2.1)
            path = QPainterPath()
            path.addRoundedRect(caixa, k * .5, k * .5)
            p.fillPath(path, QBrush(QColor(255, 40, 40)))
            p.setBrush(QBrush(QColor(255, 255, 255)))
            p.drawPolygon(QPolygonF([QPointF(cx - k * .4, cy - k * .55), QPointF(cx - k * .4, cy + k * .55),
                                     QPointF(cx + k * .6, cy)]))
            return
        if nome == "@salvos":
            import math
            pts = []
            for i in range(10):
                r = k * 1.25 if i % 2 == 0 else k * .52
                a = -math.pi / 2 + i * math.pi / 5
                pts.append(QPointF(cx + math.cos(a) * r, cy + math.sin(a) * r))
            p.setBrush(QBrush(QColor(255, 205, 80)))
            p.drawPolygon(QPolygonF(pts))
            return
        if nome == "@play":
            tri(cx - k * .55, cy, 1)
            p.drawRect(QRectF(cx + k * .45, cy - k, k * .32, 2 * k))
            p.drawRect(QRectF(cx + k * .95, cy - k, k * .32, 2 * k))
        elif nome in ("@ant", "@prox"):
            d = 1 if nome == "@prox" else -1
            tri(cx - d * k * .55, cy, d)
            tri(cx + d * k * .45, cy, d)
            p.drawRect(QRectF(cx + d * k * 1.25 - k * .15, cy - k, k * .3, 2 * k))
        else:                       # alto-falante
            x0 = cx - k * 1.1
            p.drawPolygon(QPolygonF([QPointF(x0, cy - k * .45), QPointF(x0 + k * .55, cy - k * .45),
                                     QPointF(x0 + k * 1.2, cy - k), QPointF(x0 + k * 1.2, cy + k),
                                     QPointF(x0 + k * .55, cy + k * .45), QPointF(x0, cy + k * .45)]))
            sx = cx + k * .75
            if nome == "@mudo":
                p.setPen(self._c(cor, k * .28))
                p.drawLine(QPointF(sx - k * .4, cy - k * .4), QPointF(sx + k * .4, cy + k * .4))
                p.drawLine(QPointF(sx - k * .4, cy + k * .4), QPointF(sx + k * .4, cy - k * .4))
            else:
                p.drawRect(QRectF(sx - k * .45, cy - k * .12, k * .9, k * .24))
                if nome == "@mais":
                    p.drawRect(QRectF(sx - k * .12, cy - k * .45, k * .24, k * .9))

    @staticmethod
    def _c(cor, larg):
        from hud39.qt_hud import _caneta
        return _caneta(cor, larg)

    def _botao(self, p, r: QRectF, rotulo: str, quente: bool, cor_destaque: QColor):
        from hud39.qt_hud import CLARO, _alpha, _fonte
        corte = min(10.0, r.height() * .3)
        path = QPainterPath()
        path.moveTo(r.x(), r.y())
        path.lineTo(r.right() - corte, r.y())
        path.lineTo(r.right(), r.y() + corte)
        path.lineTo(r.right(), r.bottom())
        path.lineTo(r.x() + corte, r.bottom())
        path.lineTo(r.x(), r.bottom() - corte)
        path.closeSubpath()
        g = QLinearGradient(r.x(), 0, r.right(), 0)
        g.setColorAt(0, _alpha(cor_destaque, .45 if quente else .16))
        g.setColorAt(1, _alpha(cor_destaque, .18 if quente else .05))
        p.fillPath(path, QBrush(g))
        p.setPen(self._c(_alpha(cor_destaque, .95 if quente else .55), 1.4 if quente else 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        if rotulo.startswith("@"):
            self._icone(p, r, rotulo, CLARO)
        else:
            p.setFont(_fonte(17, quente))
            p.setPen(CLARO)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, rotulo)

    def _pintar_barra(self, p: QPainter, t: float):
        """Os botões de música e o de trocar JARVIS ⇄ SEXTA-FEIRA, sempre na tela."""
        from hud39.qt_hud import CLARO, _alpha, _fonte
        if self._painel:
            return
        x, y, w, h = self.BARRA
        fundo = QRectF(x - 8, y - 6, w + 16, h + 12)
        p.fillRect(fundo, QColor(3, 10, 18, 225))
        p.setPen(self._c(_alpha(self.COR_ONDA, .45), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(fundo)
        for i, (r, ic) in enumerate(self._botoes_barra()):
            self._botao(p, r, ic, self._hover_btn == ("b", i), self.COR_ONDA)
        tx, ty, tw, th = self.TROCA
        r = QRectF(tx, ty, tw, th)
        p.fillRect(QRectF(tx - 6, ty - 6, tw + 12, th + 12), QColor(3, 10, 18, 225))
        outro = "hud39" if self.ESTILO == "friday" else "friday"
        from hud39.qt_hud import CIANO
        rosa = QColor(255, 111, 145)
        self._botao(p, r, "", self._hover_btn == ("t",), rosa if outro == "friday" else CIANO)
        p.setFont(_fonte(12))
        p.setPen(_alpha(CLARO, .7))
        p.drawText(QRectF(tx, ty + 3, tw, th * .42), Qt.AlignmentFlag.AlignCenter, "⇄ TROCAR PARA")
        p.setFont(_fonte(17, True))
        p.setPen(CLARO)
        p.drawText(QRectF(tx, ty + th * .38, tw, th * .58), Qt.AlignmentFlag.AlignCenter, NOMES[outro])

    def _pintar_painel(self, p: QPainter, t: float):
        """O painel aberto, por cima da interface (escurece o fundo e entra com animação)."""
        from hud39.qt_hud import CLARO, _alpha, _fonte
        if not self._painel:
            return
        k = min(1.0, (t - self._t_painel) / .22)
        k = 1 - (1 - k) ** 3
        p.fillRect(QRectF(0, 0, self.LW, self.LH), QColor(0, 4, 10, int(150 * k)))
        cx = self._caixa_painel()
        p.save()
        p.setOpacity(k)
        centro = cx.center()
        p.translate(centro)
        p.scale(.9 + .1 * k, .9 + .1 * k)
        p.translate(-centro.x(), -centro.y())
        cor = self.COR_ONDA
        # moldura
        c = 26.0
        path = QPainterPath()
        path.moveTo(cx.x() + c, cx.y())
        path.lineTo(cx.right(), cx.y())
        path.lineTo(cx.right(), cx.bottom() - c)
        path.lineTo(cx.right() - c, cx.bottom())
        path.lineTo(cx.x(), cx.bottom())
        path.lineTo(cx.x(), cx.y() + c)
        path.closeSubpath()
        g = QLinearGradient(cx.x(), cx.y(), cx.right(), cx.bottom())
        g.setColorAt(0, QColor(6, 28, 44, 245))
        g.setColorAt(1, QColor(2, 10, 20, 248))
        p.fillPath(path, QBrush(g))
        p.setPen(self._c(_alpha(cor, .85), 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        # varredura dentro do painel
        yy = cx.y() + ((t * .25) % 1.0) * cx.height()
        gs = QLinearGradient(0, yy - 40, 0, yy)
        gs.setColorAt(0, _alpha(cor, 0))
        gs.setColorAt(1, _alpha(cor, .08))
        p.fillRect(QRectF(cx.x() + 2, max(cx.y(), yy - 40), cx.width() - 4, min(40.0, yy - cx.y())), QBrush(gs))
        m = self._modelo(self._painel) if self._painel not in ("youtube", "salvos") else \
            {"titulo": "▶ YOUTUBE" if self._painel == "youtube" else "★ SALVOS", "linhas": [], "lista": [], "botoes": []}
        # título
        tb = QRectF(cx.x(), cx.y(), cx.width(), 60)
        gt = QLinearGradient(cx.x(), 0, cx.right(), 0)
        gt.setColorAt(0, _alpha(cor, .25))
        gt.setColorAt(1, _alpha(cor, 0))
        p.fillRect(QRectF(cx.x() + c, cx.y() + 1, cx.width() - c - 1, 59), QBrush(gt))
        p.setFont(_fonte(26, True))
        p.setPen(CLARO)
        p.drawText(QRectF(cx.x() + 34, cx.y(), cx.width() - 120, 60),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, m.get("titulo", ""))
        fx = QRectF(cx.right() - 52, cx.y() + 10, 40, 40)
        quente = self._hover_btn == ("x",)
        p.setPen(self._c(_alpha(QColor(255, 90, 90) if quente else cor, .9), 1.4))
        p.setBrush(QBrush(QColor(255, 60, 60, 70)) if quente else Qt.BrushStyle.NoBrush)
        p.drawEllipse(fx.center(), 19, 19)
        p.setFont(_fonte(20))
        p.setPen(CLARO)
        p.drawText(fx, Qt.AlignmentFlag.AlignCenter, "✕")
        p.setPen(self._c(_alpha(cor, .35), 1))
        p.drawLine(QPointF(cx.x() + 20, tb.bottom()), QPointF(cx.right() - 20, tb.bottom()))
        if self._painel in ("youtube", "salvos"):
            (self._pintar_youtube if self._painel == "youtube" else self._pintar_salvos)(p, cx, tb.bottom() + 16, t)
            p.setFont(_fonte(13))
            p.setPen(_alpha(CLARO, .45))
            p.drawText(QRectF(cx.x(), cx.bottom() - 30, cx.width(), 24), Qt.AlignmentFlag.AlignCenter,
                       "clique fora do painel ou no ✕ para fechar")
            p.restore()
            return
        # linhas (cartões em duas colunas)
        y = tb.bottom() + 18
        x0, larg = cx.x() + 28, (cx.width() - 56 - 14) / 2
        for i, (rot, val) in enumerate(m["linhas"]):
            col, lin = i % 2, i // 2
            if len(m["linhas"]) == 1:
                rr = QRectF(x0, y, cx.width() - 56, 54)
            else:
                rr = QRectF(x0 + col * (larg + 14), y + lin * 62, larg, 54)
            p.fillRect(rr, _alpha(cor, .06))
            p.setPen(self._c(_alpha(cor, .28), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(rr)
            p.setFont(_fonte(12))
            p.setPen(_alpha(CLARO, .6))
            p.drawText(QRectF(rr.x() + 12, rr.y() + 4, rr.width() - 24, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, rot.upper())
            p.setFont(_fonte(18))
            p.setPen(CLARO)
            texto = str(val)
            lim = int(rr.width() / 9.5)
            p.drawText(QRectF(rr.x() + 12, rr.y() + 22, rr.width() - 24, 28),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       texto if len(texto) <= lim else texto[:lim - 1] + "…")
        if m["linhas"]:
            y += (1 if len(m["linhas"]) == 1 else (len(m["linhas"]) + 1) // 2) * 62 + 6
        # lista (processos, discos, diagnóstico)
        for i, (a, b) in enumerate(m["lista"][:9]):
            rr = QRectF(x0, y + i * 34, cx.width() - 56, 32)
            if i % 2 == 0:
                p.fillRect(rr, _alpha(cor, .05))
            p.setFont(_fonte(17))
            p.setPen(CLARO)
            p.drawText(QRectF(rr.x() + 12, rr.y(), rr.width() * .5, rr.height()),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, a[:34])
            ruim = "ALTO" in b or "SEM" in b
            meio = "atenção" in b
            p.setPen(QColor(255, 90, 90) if ruim else (QColor(255, 170, 60) if meio else CLARO))
            p.drawText(QRectF(rr.x() + rr.width() * .45, rr.y(), rr.width() * .55 - 12, rr.height()),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, b)
        if m["lista"]:
            y += min(9, len(m["lista"])) * 34 + 12
        elif self._painel == "processos":
            p.setFont(_fonte(17))
            p.setPen(_alpha(CLARO, .5))
            p.drawText(QRectF(x0, y, 400, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       "lendo os processos…")
            y += 40
        # botões (quebram linha)
        self._botoes = []
        bx, by = x0, max(y, cx.y() + 90)
        limite = cx.right() - 28
        for rot, acao in m["botoes"]:
            w = 74.0 if rot.startswith("@") else max(150.0, len(rot) * 10.5 + 34)
            if bx + w > limite and bx > x0:
                bx, by = x0, by + 62
            r = QRectF(bx, by, w, 52)
            self._botoes.append((r, acao))
            bx += w + 12
        for i, (r, _a) in enumerate(self._botoes):
            rot = m["botoes"][i][0]
            self._botao(p, r, rot, self._hover_btn == ("p", i), cor)
        p.setFont(_fonte(13))
        p.setPen(_alpha(CLARO, .45))
        p.drawText(QRectF(cx.x(), cx.bottom() - 30, cx.width(), 24), Qt.AlignmentFlag.AlignCenter,
                   "clique fora do painel ou no ✕ para fechar")
        p.restore()

    # ── YouTube e Salvos ─────────────────────────────────────────────────────
    def _linha_botoes(self, p, x0, y, botoes, limite):
        """Desenha botões lado a lado e registra os cliques. Devolve o y de baixo."""
        bx = x0
        for rot, acao in botoes:
            w = 64.0 if rot.startswith("@") else max(120.0, len(rot) * 10.0 + 30)
            if bx + w > limite and bx > x0:
                bx, y = x0, y + 54
            r = QRectF(bx, y, w, 44)
            i = len(self._botoes)
            self._botoes.append((r, acao))
            self._botao(p, r, rot, self._hover_btn == ("p", i), self.COR_ONDA)
            bx += w + 10
        return y + 44

    def _texto(self, p, r, texto, px, cor, negrito=False, alinhar=None):
        from hud39.qt_hud import _fonte
        p.setFont(_fonte(px, negrito))
        p.setPen(cor)
        lim = max(4, int(r.width() / (px * .52)))
        texto = str(texto)
        p.drawText(r, alinhar or (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   texto if len(texto) <= lim else texto[:lim - 1] + "…")

    def _pintar_youtube(self, p, cx: QRectF, y: float, t: float):
        from hud39.qt_hud import CLARO, _alpha
        self._botoes = []
        x0, limite = cx.x() + 28, cx.right() - 28
        b = self._busca
        termo = b.termo if b else ""
        self._texto(p, QRectF(x0, y, limite - x0 - 340, 44), f"Pesquisa: {termo}" if termo else
                    "Digite na caixa:  youtube: o que você quer ver", 17, CLARO)
        self._linha_botoes(p, limite - 330, y, [("🔎 Nova pesquisa", {"tipo": "focar", "texto": "youtube: "}),
                                                 ("★ Salvos", {"tipo": "painel", "nome": "salvos"})], limite)
        y += 60
        if not b:
            return
        if not b.pronta:
            pontos = "." * (1 + int(t * 3) % 3)
            self._texto(p, QRectF(x0, y + 40, limite - x0, 40), f"Pesquisando no YouTube{pontos}", 22, CLARO,
                        alinhar=Qt.AlignmentFlag.AlignCenter)
            for i in range(12):                                   # roda de carregando
                import math
                a = t * 6 + i * math.pi / 6
                cxx, cyy = (x0 + limite) / 2, y + 140
                p.fillRect(QRectF(cxx + math.cos(a) * 30 - 3, cyy + math.sin(a) * 30 - 3, 6, 6),
                           _alpha(self.COR_ONDA, (i + 1) / 12))
            return
        if not b.resultados:
            self._texto(p, QRectF(x0, y + 40, limite - x0, 40), b.erro or "Nada encontrado.", 18,
                        QColor(255, 120, 120), alinhar=Qt.AlignmentFlag.AlignCenter)
            return
        colunas = 2
        larg = (limite - x0 - 16) / colunas
        alt = min(150.0, (cx.bottom() - 44 - y) / 3 - 10)
        mini_w, mini_h = alt * 16 / 9 * .78, alt * .78
        for i, r in enumerate(b.resultados[:6]):
            col, lin = i % colunas, i // colunas
            caixa = QRectF(x0 + col * (larg + 16), y + lin * (alt + 10), larg, alt)
            idx = len(self._botoes)
            self._botoes.append((QRectF(caixa.x(), caixa.y(), caixa.width() - 54, caixa.height()),
                                 {"tipo": "tocar", "url": r["url"], "titulo": r["titulo"]}))
            quente = self._hover_btn == ("p", idx)
            p.fillRect(caixa, _alpha(self.COR_ONDA, .16 if quente else .05))
            p.setPen(self._c(_alpha(self.COR_ONDA, .9 if quente else .3), 1.3 if quente else 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(caixa)
            mr = QRectF(caixa.x() + 8, caixa.y() + (alt - mini_h) / 2, mini_w, mini_h)
            img = self._imgs.get(r["id"])
            if img is None and b.miniaturas.get(r["id"]):
                img = QImage.fromData(b.miniaturas[r["id"]])
                self._imgs[r["id"]] = img
            if img is not None and not img.isNull():
                p.drawImage(mr, img)
            else:
                p.fillRect(mr, QColor(20, 20, 28))
                self._icone(p, mr, "@yt", CLARO)
            if quente:                                             # play por cima da miniatura
                p.fillRect(mr, QColor(0, 0, 0, 90))
                self._icone(p, mr, "@play", CLARO)
            if r.get("duracao"):
                dr = QRectF(mr.right() - 52, mr.bottom() - 22, 48, 18)
                p.fillRect(dr, QColor(0, 0, 0, 200))
                self._texto(p, dr, r["duracao"], 12, CLARO, alinhar=Qt.AlignmentFlag.AlignCenter)
            tx = mr.right() + 12
            tw = caixa.right() - 60 - tx
            l1, l2 = quebrar(r["titulo"], int(tw / 8.8))
            self._texto(p, QRectF(tx, caixa.y() + 8, tw, 24), l1, 16, CLARO, True)
            if l2:
                self._texto(p, QRectF(tx, caixa.y() + 32, tw, 24), l2, 16, CLARO, True)
            self._texto(p, QRectF(tx, caixa.bottom() - 32, tw, 24), r.get("canal", ""), 14, _alpha(CLARO, .65))
            sr = QRectF(caixa.right() - 50, caixa.y() + (alt - 44) / 2, 42, 44)
            si = len(self._botoes)
            self._botoes.append((sr, {"tipo": "salvar_video", "url": r["url"], "titulo": r["titulo"]}))
            self._botao(p, sr, "@salvos", self._hover_btn == ("p", si), self.COR_ONDA)

    def _pintar_salvos(self, p, cx: QRectF, y: float, t: float):
        from hud39 import salvos
        from hud39.qt_hud import CLARO, _alpha
        self._botoes = []
        x0, limite = cx.x() + 28, cx.right() - 28
        self._texto(p, QRectF(x0, y, limite - x0 - 330, 44), "Na caixa:  salvar: o que você quer guardar", 17,
                    _alpha(CLARO, .8))
        self._linha_botoes(p, limite - 320, y, [("✎ Salvar algo", {"tipo": "focar", "texto": "salvar: "}),
                                                 ("▶ YouTube", {"tipo": "painel", "nome": "youtube"})], limite)
        y += 60
        itens = salvos.listar()
        if not itens:
            self._texto(p, QRectF(x0, y + 30, limite - x0, 40), "Nada salvo ainda.", 20, _alpha(CLARO, .6),
                        alinhar=Qt.AlignmentFlag.AlignCenter)
            return
        alt = 46.0
        cabem = max(1, int((cx.bottom() - 44 - y) // (alt + 6)))
        for i, it in enumerate(itens[:cabem]):
            linha = QRectF(x0, y + i * (alt + 6), limite - x0, alt)
            video = it.get("tipo") == "video"
            acao = ({"tipo": "tocar", "url": it.get("url"), "titulo": it.get("titulo")} if video
                    else {"tipo": "focar", "texto": it.get("texto", "")})
            idx = len(self._botoes)
            self._botoes.append((QRectF(linha.x(), linha.y(), linha.width() - 60, alt), acao))
            quente = self._hover_btn == ("p", idx)
            p.fillRect(linha, _alpha(self.COR_ONDA, .15 if quente else (.06 if i % 2 == 0 else .02)))
            if video:
                self._icone(p, QRectF(linha.x() + 4, linha.y(), 44, alt), "@yt", CLARO)
            else:
                self._icone(p, QRectF(linha.x() + 4, linha.y(), 44, alt), "@salvos", CLARO)
            self._texto(p, QRectF(linha.x() + 54, linha.y(), linha.width() - 250, alt),
                        it.get("titulo") or it.get("texto"), 17, CLARO)
            self._texto(p, QRectF(linha.right() - 200, linha.y(), 130, alt), it.get("quando", ""), 13,
                        _alpha(CLARO, .55), alinhar=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            ar = QRectF(linha.right() - 52, linha.y() + 4, 46, alt - 8)
            ai = len(self._botoes)
            self._botoes.append((ar, {"tipo": "apagar", "id": it.get("id")}))
            self._botao(p, ar, "✕", self._hover_btn == ("p", ai), QColor(255, 90, 90))
        if len(itens) > cabem:
            self._texto(p, QRectF(x0, cx.bottom() - 56, limite - x0, 22), f"+ {len(itens) - cabem} itens "
                        "(peça por voz: “o que eu salvei?”)", 13, _alpha(CLARO, .5), alinhar=Qt.AlignmentFlag.AlignCenter)
