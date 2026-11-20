"""Testes da 3.4 — cérebro local de comandos (aprende, reflexo, sem internet, busca, celular, segurança)."""
import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests import RAIZ
from tests.test_52_v33 import trocar, versoes


class BaseCerebro(unittest.TestCase):
    def setUp(self):
        global C, P
        C = importlib.import_module("core.cerebro")
        P = importlib.import_module("plugins.cerebro")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        trocar(self, "core.cerebro", "ARQ", self.tmp / "cerebro.json")
        C._cache.pop("modelo", None)
        C._turno.clear()
        C._anterior["chave"] = None

    def usar(self, frase, ferramenta, args, resultado="Feito.", vezes=1):
        for _ in range(vezes):
            C.anotar_chamada(ferramenta, args, resultado)
            C.turno(frase)


class TestTexto(unittest.TestCase):
    def test_normaliza_e_chave(self):
        from core import cerebro as C
        self.assertEqual(C.chave("Jarvis, ABRE a loja por favor!"), "abre loja")
        self.assertEqual(C.chave("ei jarvis abre a loja"), C.chave("abre a loja"))
        self.assertIn("abre_loja", C.atributos("abre a loja"))
        self.assertTrue(C.args_simples({"action": "abrir"}))
        self.assertFalse(C.args_simples({"action": "ativar", "modo": "estudo"}))

    def test_sementes_dos_plugins(self):
        from core import cerebro as C
        s = C.sementes()
        self.assertGreater(len(s), 300)
        self.assertIn(("mostra a caixa-preta", "caixa_preta"), s)
        self.assertFalse(any(f.startswith("_") for _, f in s))


class TestAprender(BaseCerebro):
    def test_aprende_e_vira_reflexo_na_segunda(self):
        self.usar("Jarvis, abre a loja", "cristal_malhas", {"action": "abrir"})
        r = C.entender("abre a loja")
        self.assertEqual((r["ferramenta"], r["args"], r["reflexo"]), ("cristal_malhas", {"action": "abrir"}, False))
        self.usar("abre a loja por favor", "cristal_malhas", {"action": "abrir"})
        r = C.entender("ei jarvis, abre a loja")
        self.assertTrue(r["reflexo"])

    def test_nao_aprende_falha_varias_ferramentas_ou_buscas(self):
        self.usar("abre a loja", "cristal_malhas", {"action": "abrir"}, resultado="Erro: planilha não encontrada")
        C.anotar_chamada("musica", {"action": "tocar"}, "ok")
        C.anotar_chamada("modos", {"action": "ativar"}, "ok")
        C.turno("toca música e liga o modo")
        self.usar("procura uma ferramenta de juros", "catalogo", {"action": "buscar"})
        self.assertEqual(C.exemplos(), [])

    def test_correcao_desfaz_o_aprendizado(self):
        self.usar("abre a loja", "cristal_malhas", {"action": "abrir"}, vezes=2)
        self.usar("abre o caixa", "cristal_malhas", {"action": "abrir"})
        C.turno("não, não foi isso, é o caixa da loja")
        ruim = next(e for e in C.exemplos() if e["k"] == "abre caixa")
        self.assertEqual(ruim["ruim"], 1)
        self.assertFalse(C.entender("abre o caixa")["reflexo"])
        self.assertTrue(C.entender("abre a loja")["reflexo"])

    def test_anonimo_e_convidado_nao_aprendem(self):
        with mock.patch("core.anonimo.ativo", return_value=True):
            self.usar("abre a loja", "cristal_malhas", {"action": "abrir"})
        trocas = [mock.patch.object(m, "ativo", return_value=True) for m in versoes("plugins.modo_convidado")]
        for t in trocas:
            t.start()
        try:
            self.usar("abre a loja", "cristal_malhas", {"action": "abrir"})
        finally:
            for t in trocas:
                t.stop()
        self.assertEqual(C.exemplos(), [])

    def test_ferramenta_critica_nunca_vira_reflexo(self):
        with mock.patch("core.verificacao.nivel_de", return_value="critico"):
            self.usar("formata o pendrive", "limpeza", {"action": "formatar"}, vezes=3)
            r = C.entender("formata o pendrive")
        self.assertFalse(r["reflexo"])
        self.assertIn("crítica", r["motivo"])

    def test_desligar_reflexos(self):
        self.usar("abre a loja", "cristal_malhas", {"action": "abrir"}, vezes=2)
        C.ligar_reflexos(False)
        self.assertFalse(C.entender("abre a loja")["reflexo"])
        C.ligar_reflexos(True)
        self.assertTrue(C.entender("abre a loja")["reflexo"])

    def test_limite_de_exemplos(self):
        with mock.patch.object(C, "MAX_EXEMPLOS", 5):
            for k in range(9):
                self.usar(f"comando numero {k} diferente", "musica", {"action": "tocar"})
            C.ensinar("frase ensinada especial", "musica", {"action": "tocar"})
            self.assertEqual(len(C.exemplos()), 5)
            self.assertTrue(any(e["origem"] == "ensinado" for e in C.exemplos()))


class TestSemInternet(BaseCerebro):
    def test_frase_parecida_so_com_acao_simples(self):
        self.usar("como está o pc", "monitor_sistema", {"action": "status"}, vezes=2)
        self.usar("liga o modo estudo", "modos", {"action": "ativar", "modo": "estudo"}, vezes=2)
        self.assertTrue(C.entender("como está o meu pc", sem_ia=True)["reflexo"])
        r = C.entender("liga o modo leitura", sem_ia=True)
        self.assertFalse(r["reflexo"])                         # não liga o modo estudo no lugar do leitura
        self.assertFalse(C.entender("qual a capital da França", sem_ia=True)["reflexo"])

    def test_resposta_curta(self):
        self.assertEqual(C.resposta_curta("status=done action=send_message to=Ana verified=true"), "Feito.")
        self.assertTrue(C.resposta_curta("x " * 500).endswith("…"))


class TestPluginCerebro(BaseCerebro):
    def test_acoes(self):
        self.assertIn("frases de exemplo", P.run({"action": "estado"}))
        self.assertIn("Ainda não tenho reflexos", P.run({"action": "reflexos"}))
        with mock.patch("core.registro_ferramentas.declaracoes", return_value=[{"name": "protocolos"}, {"name": "musica"}]):
            r = P.run({"action": "ensinar", "frase": "boa noite, chefe", "ferramenta": "protocolos",
                       "parametros": '{"action": "rodar", "nome": "dormir"}'})
            self.assertIn("Aprendido", r)
            self.assertIn("Não conheço", P.run({"action": "ensinar", "frase": "x y", "ferramenta": "inventada"}))
            self.assertIn("JSON", P.run({"action": "ensinar", "frase": "x y", "ferramenta": "musica", "parametros": "{quebrado"}))
        self.assertTrue(C.entender("boa noite chefe")["reflexo"])
        self.assertIn("faço na hora", P.run({"action": "testar", "frase": "boa noite chefe"}))
        self.assertIn("protocolos (rodar)", P.run({"action": "reflexos"}))
        self.assertIn("Esqueci 1", P.run({"action": "esquecer", "frase": "boa noite chefe"}))
        self.assertIn("desligados", P.run({"action": "desligar"}))
        self.assertIn("ligados", P.run({"action": "ligar"}))

    def test_nivel(self):
        from core import verificacao as V
        self.assertEqual(V.nivel_de("cerebro", {"action": "ensinar"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("cerebro", {"action": "testar"}), V.LIVRE)


class TestBuscaComCerebro(BaseCerebro):
    def test_o_que_voce_usa_vem_primeiro(self):
        decls = [{"name": n, "description": d} for n, d in (("musica", "toca música"), ("radio", "rádio e música ao vivo"),
                                                              ("trilha_produtiva", "música para focar"))]
        self.usar("bota um som pra mim", "radio", {"action": "tocar"}, vezes=3)
        catalogo = importlib.import_module("plugins.catalogo")
        self.assertEqual(catalogo.com_cerebro(decls, "bota um som pra mim", 3)[0]["name"], "radio")
        self.assertEqual(len(catalogo.com_cerebro(decls, "toca música", 3)), len({d["name"] for d in catalogo.com_cerebro(decls, "toca música", 3)}))


class TestCelular(BaseCerebro):
    def _motor(self):
        sys.path.insert(0, str(RAIZ / "celular"))
        import jarvis_celular as jc
        m = jc.Motor.__new__(jc.Motor)
        m.lock = __import__("threading").Lock()
        m.historico = []
        m.reg = mock.MagicMock()
        m.reg.has.return_value = True
        m.reg.run.return_value = "Planilha da loja aberta."
        m.declaracoes = lambda: []
        return m

    def test_reflexo_sem_gastar_o_gemini(self):
        self.usar("abre a loja", "cristal_malhas", {"action": "abrir"}, vezes=2)
        m = self._motor()
        with mock.patch.object(type(m), "_gerar", side_effect=AssertionError("não devia chamar o Gemini")):
            r = m.conversar("Jarvis, abre a loja")
        self.assertEqual(r, {"resposta": "Planilha da loja aberta.", "ferramentas": ["cristal_malhas"], "cerebro": True})
        m.reg.run.assert_called_once()

    def test_sem_chave_tenta_o_cerebro(self):
        self.usar("como está o pc", "monitor_sistema", {"action": "status"}, vezes=1)
        m = self._motor()
        m.sistema = lambda: ""
        m.ferramentas = lambda: []
        with mock.patch.object(type(m), "_gerar", side_effect=Exception("SEM_CHAVE")):
            r = m.conversar("como está o meu pc")       # 1 vez só: não é reflexo, mas sem Gemini vale o parecido
            self.assertIn("cérebro local", r["resposta"])
            r2 = m.conversar("qual a capital da França")
            self.assertEqual(r2.get("erro"), "chave")


class TestLigacoes(unittest.TestCase):
    def test_pc_e_ganchos(self):
        main = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn("_cerebro.anotar_chamada(name, args, str(result)", main)
        self.assertIn("self._cerebro_offline", main)
        self.assertIn("cerebro.turno(entrada, saida)", (RAIZ / "core" / "ganchos_turno.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
