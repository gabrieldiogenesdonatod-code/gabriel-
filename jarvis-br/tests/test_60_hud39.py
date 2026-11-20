"""
Testes da 3.9.1 — HUD 3.9 (painel animado e clicável).

1. Os números do momento e as informações fixas saem com as chaves que a página usa.
2. O servidor só aceita 127.0.0.1/localhost, e ação sem o token é recusada.
3. As ações: comando vai para o JARVIS pelo gancho; sem o JARVIS, avisa; ação desconhecida não faz nada.
4. O plugin carrega e responde.
"""
import json
import time
import unittest
import urllib.error
import urllib.request

import hud39
from hud39 import servidor, sistema


def _pedir(caminho, dados=None, cabecalhos=None):
    req = urllib.request.Request(servidor.endereco().rstrip("/") + caminho,
                                 data=json.dumps(dados).encode() if dados is not None else None,
                                 headers=cabecalhos or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read()


class TestSistema(unittest.TestCase):
    def test_momento_tem_o_que_a_pagina_usa(self):
        m = sistema.momento()
        for k in ("cpu", "ram", "disco", "rede", "processos", "hist", "uptime", "particoes"):
            self.assertIn(k, m)
        self.assertIn("pct", m["ram"])
        self.assertIn("down", m["rede"])

    def test_fixo(self):
        f = sistema.fixo()
        for k in ("so", "build", "arquitetura", "cpu_nome", "jarvis_versao", "plugins"):
            self.assertIn(k, f)
        self.assertGreater(f["plugins"], 100)

    def test_processos_sem_ocioso(self):
        lista = [{"pid": 0, "nome": "System Idle Process", "cpu": 99},
                 {"pid": 4, "nome": "Idle", "cpu": 50},
                 {"pid": 10, "nome": "chrome.exe", "cpu": 3.21, "ram": 100}]
        self.assertEqual(sistema.processos_top(lista), [{"nome": "chrome", "cpu": 3.2, "ram": 100, "pid": 10}])


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        servidor.iniciar(porta=0)

    @classmethod
    def tearDownClass(cls):
        servidor.parar()
        servidor._ganchos.update({"comando": None, "estado": None})

    def test_pagina_e_estado(self):
        st, corpo = _pedir("/")
        self.assertEqual(st, 200)
        self.assertIn(servidor.TOKEN.encode(), corpo)
        st, corpo = _pedir("/api/estado")
        self.assertIn("jarvis", json.loads(corpo))
        st, corpo = _pedir("/hud.jpg")
        self.assertTrue(corpo.startswith(b"\xff\xd8"))

    def test_host_estranho_recusado(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            _pedir("/api/estado", cabecalhos={"Host": "site-malicioso.com"})
        self.assertEqual(c.exception.code, 403)

    def test_acao_sem_token_recusada(self):
        with self.assertRaises(urllib.error.HTTPError) as c:
            _pedir("/api/acao", {"acao": "comando", "texto": "oi"})
        self.assertEqual(c.exception.code, 403)

    def test_comando_vai_para_o_jarvis(self):
        recebidos = []
        servidor._ganchos["comando"] = recebidos.append
        st, corpo = _pedir("/api/acao", {"acao": "comando", "texto": "  que   horas são "},
                           {"X-Token": servidor.TOKEN, "Content-Type": "application/json"})
        self.assertTrue(json.loads(corpo)["ok"])
        for _ in range(50):
            if recebidos:
                break
            time.sleep(0.02)
        self.assertEqual(recebidos, ["que horas são"])
        servidor._ganchos["comando"] = None

    def test_sem_jarvis_avisa(self):
        servidor._ganchos["comando"] = None
        r = servidor.executar({"acao": "comando", "texto": "oi"})
        self.assertFalse(r["ok"])
        self.assertIn("sozinho", r["resposta"])

    def test_acao_desconhecida(self):
        self.assertFalse(servidor.executar({"acao": "apagar_tudo"})["ok"])
        self.assertFalse(servidor.executar({"acao": "midia", "tecla": "formatar"})["ok"])

    def test_estado_da_janela(self):
        class Hud:
            state, speaking = "SPEAKING", True

        class Win:
            hud, _muted, on_text_command = Hud(), False, None

        class Player:
            _win = Win()
        servidor._ganchos["estado"] = None
        orig = servidor.abrir_janela
        servidor.abrir_janela = lambda url, tela_cheia=True: "teste"
        try:
            hud39.abrir_do_jarvis(Player())
            self.assertEqual(servidor.estado_jarvis()["estado"], "FALANDO")
            self.assertTrue(servidor.estado_jarvis()["falando"])
        finally:
            servidor.abrir_janela = orig


class TestPlugin(unittest.TestCase):
    def test_endereco_e_fechar_sem_abrir(self):
        from plugins import hud39 as plug
        servidor.parar()
        self.assertIn("não está aberto", plug.run({"action": "endereco"}))
        self.assertIn("não está aberto", plug.run({"action": "fechar"}))


if __name__ == "__main__":
    unittest.main()


class TestEstiloPadrao(unittest.TestCase):
    """3.9.3: o J.A.R.V.I.S volta a ser a capa, uma vez; depois vale a escolha (⇄ na tela ou ⚙)."""

    def _cfg(self, inicial):
        from unittest import mock
        from memory import config_manager as cm
        dados = dict(inicial)
        return dados, mock.patch.multiple(cm, load_api_keys=lambda: dict(dados),
                                          _save_flag=lambda k, v: dados.__setitem__(k, v))

    def test_qualquer_estilo_antigo_vira_jarvis_uma_vez(self):
        from memory import config_manager as cm
        for antigo in ("face", "friday", "core"):
            dados, patch = self._cfg({"hud_style": antigo, "hud_style_391": True, "hud_style_392": True})
            with patch:
                self.assertEqual(cm.get_hud_style(), "hud39")
                self.assertEqual(dados["hud_style"], "hud39")

    def test_sem_nada_salvo(self):
        from memory import config_manager as cm
        dados, patch = self._cfg({})
        with patch:
            self.assertEqual(cm.get_hud_style(), "hud39")

    def test_escolha_depois_e_respeitada(self):
        from memory import config_manager as cm
        dados, patch = self._cfg({})
        with patch:
            cm.get_hud_style()
            for estilo in ("friday", "face", "core", "hud39"):
                cm.save_hud_style(estilo)
                self.assertEqual(cm.get_hud_style(), estilo)

    def test_escolha_feita_depois_da_393_continua(self):
        from memory import config_manager as cm
        dados, patch = self._cfg({"hud_style": "friday", "hud_style_393": True})
        with patch:
            self.assertEqual(cm.get_hud_style(), "friday")


class TestAlvosDoHudNativo(unittest.TestCase):
    def test_areas(self):
        try:
            from hud39.qt_hud import Hud39Painter
        except ImportError:
            self.skipTest("sem PyQt6")
        h = Hud39Painter.__new__(Hud39Painter)
        self.assertEqual(h.alvo_em(150, 145, 1672, 941), "sistema")
        self.assertEqual(h.alvo_em(318, 668, 1672, 941), "comando")
        self.assertIsNone(h.alvo_em(1100, 520, 1672, 941))
        # janela mais alta que larga: a arte fica centralizada e os cliques acompanham
        s, ox, oy = h.encaixe(836, 900)
        self.assertEqual(h.alvo_em(ox + 318 * s, oy + 668 * s, 836, 900), "comando")


class TestFriday(unittest.TestCase):
    def test_imagem_sem_a_parte_de_baixo(self):
        from pathlib import Path
        arte = Path(hud39.__file__).parent / "static" / "friday.jpg"
        self.assertTrue(arte.read_bytes().startswith(b"\xff\xd8"))

    def test_areas_da_friday(self):
        try:
            from hud39.friday_qt import ORBE, FridayPainter
        except ImportError:
            self.skipTest("sem PyQt6")
        f = FridayPainter.__new__(FridayPainter)
        self.assertEqual(f.alvo_em(ORBE[0], ORBE[1], 1600, 900), "comando")     # o orbe do dedo
        self.assertEqual(f.alvo_em(100, 175, 1600, 900), "sistema")            # 1º botão do menu
        self.assertEqual(f.alvo_em(100, 175 + 64 * 3, 1600, 900), "musica")
        self.assertEqual(f.alvo_em(1300, 120, 1600, 900), "diagnostico")       # medidores
        self.assertIsNone(f.alvo_em(800, 600, 1600, 900))                      # o vestido não abre nada

    def test_tema_na_janela_de_painel(self):
        abertos = []
        orig = servidor.abrir_janela
        servidor.abrir_janela = lambda url, tela_cheia=True: abertos.append(url)
        try:
            servidor.abrir(painel="musica", tema="friday", tela_cheia=False)
            servidor.abrir(painel="x<script>", tema="hackear", tela_cheia=False)
        finally:
            servidor.abrir_janela = orig
            servidor.parar()
        self.assertTrue(abertos[0].endswith("/?tema=friday#musica"))
        self.assertTrue(abertos[1].endswith("/#xscript"))


class TestSalvos(unittest.TestCase):
    """3.9.3: ★ SALVOS — guardar o que o usuário quiser."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from hud39 import salvos
        self.s = salvos
        self._orig = salvos.ARQUIVO
        self._tmp = tempfile.TemporaryDirectory()
        salvos.ARQUIVO = Path(self._tmp.name) / "salvos.json"

    def tearDown(self):
        self.s.ARQUIVO = self._orig
        self._tmp.cleanup()

    def test_prefixo(self):
        self.assertEqual(self.s.pedido_de_salvar("salvar: comprar tecido"), "comprar tecido")
        self.assertEqual(self.s.pedido_de_salvar("Salva:  senha na gaveta "), "senha na gaveta")
        self.assertEqual(self.s.pedido_de_salvar("salvar:"), "")
        self.assertIsNone(self.s.pedido_de_salvar("como salvar um arquivo?"))

    def test_adicionar_sem_duplicar_e_apagar(self):
        a = self.s.adicionar("comprar tecido")
        self.s.adicionar("ligar para o fornecedor")
        self.s.adicionar("comprar   tecido")              # mesmo texto: só sobe para o topo
        itens = self.s.listar()
        self.assertEqual([i["texto"] for i in itens], ["comprar tecido", "ligar para o fornecedor"])
        self.assertTrue(self.s.apagar(itens[0]["id"]))
        self.assertFalse(self.s.apagar(a["id"]))           # já foi
        self.assertEqual(len(self.s.listar()), 1)

    def test_video_e_procura(self):
        self.s.adicionar("Bolo", "video", "https://www.youtube.com/watch?v=abcdefghijk", "Bolo de cenoura")
        self.assertEqual(self.s.listar()[0]["tipo"], "video")
        self.assertEqual(len(self.s.procurar("cenoura")), 1)
        with self.assertRaises(ValueError):
            self.s.adicionar("   ")

    def test_plugin(self):
        from plugins import salvos as plug
        self.assertIn("Salvo", plug.run({"action": "salvar", "texto": "pagar a luz"}))
        self.assertIn("pagar a luz", plug.run({"action": "listar"}))
        self.assertIn("Apaguei", plug.run({"action": "apagar_ultimo"}))


class TestYoutube(unittest.TestCase):
    """3.9.3: pesquisa no YouTube mostrada por cima da interface, sem abrir o YouTube."""

    def test_prefixo(self):
        from hud39.youtube import pedido_de_busca
        self.assertEqual(pedido_de_busca("youtube: bolo de cenoura"), "bolo de cenoura")
        self.assertEqual(pedido_de_busca("YT:  rap geek"), "rap geek")
        self.assertIsNone(pedido_de_busca("abre o youtube"))

    def test_ler_pagina(self):
        from hud39.youtube import ler_pagina
        dados = {"contents": [{"videoRenderer": {"videoId": "abcdefghijk", "title": {"runs": [{"text": "Bolo"}]},
                                                 "ownerText": {"runs": [{"text": "Vó"}]},
                                                 "lengthText": {"simpleText": "8:41"}}},
                              {"videoRenderer": {"videoId": "curto"}},
                              {"x": [{"videoRenderer": {"videoId": "zyxwvutsrqp", "title": {"runs": [{"text": "B2"}]}}}]}]}
        html = f"<script>var ytInitialData = {json.dumps(dados)};</script>"
        r = ler_pagina(html)
        self.assertEqual([v["id"] for v in r], ["abcdefghijk", "zyxwvutsrqp"])
        self.assertEqual(r[0]["duracao"], "8:41")
        self.assertEqual(r[0]["url"], "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(ler_pagina("<html>nada</html>"), [])

    def test_busca_vazia(self):
        from hud39.youtube import buscar
        self.assertEqual(buscar("  ")[0], [])

    def test_quebrar_titulo(self):
        try:
            from hud39.sobreposto import quebrar
        except ImportError:
            self.skipTest("sem PyQt6")
        self.assertEqual(quebrar("Como fazer cobertura de brigadeiro", 16), ("Como fazer", "cobertura de brigadeiro"))
        self.assertEqual(quebrar("curto", 16), ("curto", ""))


class TestCliquesNaTela(unittest.TestCase):
    """3.9.3: painéis por cima da interface, barra de música e botão ⇄ (sem abrir janela)."""

    def _pintor(self, classe):
        try:
            if classe == "friday":
                from hud39.friday_qt import FridayPainter as C
            else:
                from hud39.qt_hud import Hud39Painter as C
        except ImportError:
            self.skipTest("sem PyQt6")
        p = C.__new__(C)
        p._ondas, p._aviso, p._hover, p._hover_rect, p._dados, p._fixo = [], None, None, None, {}, {}
        p._ini_sobreposto()
        return p

    def _tela(self, p, x, y):
        """Ponto da tela virtual → ponto da janela (janela do mesmo tamanho, sem bordas)."""
        return x, y, p.LW, p.LH

    def test_menu_abre_painel_por_cima(self):
        for estilo in ("hud39", "friday"):
            p = self._pintor(estilo)
            alvo = p.RETANGULOS[3]                       # MÚSICA
            self.assertIsNone(p.clicar(*self._tela(p, alvo[0] + 20, alvo[1] + 20)))
            self.assertEqual(p._painel, "musica")
            self.assertIsNone(p.clicar(*self._tela(p, 5, 5)))     # fora do painel fecha
            self.assertIsNone(p._painel)

    def test_botao_trocar(self):
        p = self._pintor("hud39")
        x, y, w, h = p.TROCA
        self.assertEqual(p.clicar(*self._tela(p, x + w / 2, y + h / 2)), {"tipo": "estilo", "estilo": "friday"})
        f = self._pintor("friday")
        x, y, w, h = f.TROCA
        self.assertEqual(f.clicar(*self._tela(f, x + w / 2, y + h / 2)), {"tipo": "estilo", "estilo": "hud39"})

    def test_barra_youtube_e_salvos(self):
        p = self._pintor("friday")
        botoes = p._botoes_barra()
        r = botoes[5][0]                                 # ▶ YouTube
        self.assertIsNone(p.clicar(*self._tela(p, r.center().x(), r.center().y())))
        self.assertEqual(p._painel, "youtube")
        p.fechar_painel()
        r = botoes[6][0]                                 # ★ Salvos
        p.clicar(*self._tela(p, r.center().x(), r.center().y()))
        self.assertEqual(p._painel, "salvos")

    def test_nenhum_painel_abre_janela(self):
        p = self._pintor("hud39")
        for nome in ("sistema", "internet", "musica", "videos", "arquivos", "jogos", "config", "processos",
                     "gpu", "discos", "diagnostico", "jarvis"):
            for _rot, acao in p._modelo(nome)["botoes"]:
                self.assertNotIn(acao.get("tipo"), ("janela",), nome)
                self.assertNotEqual(acao.get("acao"), "navegador", nome)
