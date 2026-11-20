"""Biological Core (3.1) — cérebro: classificador que aprende, hipóteses bayesianas, decisão e o fluxo completo."""
import shutil
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401
from tests.bio_comum import ERRO_REDE, organismo, projeto

from biological_core.brain.decision_engine import MotorDecisao
from biological_core.brain.reasoning import ClassificadorErros, MotorHipoteses


class TestClassificador(unittest.TestCase):
    def test_regras_e_aprendizado(self):
        c = ClassificadorErros()
        self.assertEqual(c.classificar("Expecting value: line 1 column 1 (char 0)")[:2], ("json_corrompido", 0.95))
        cat, conf, origem = c.classificar("ConnectionAbortedError: o host remoto fechou a conexão")
        self.assertEqual((cat, origem), ("rede", "aprendido"))              # nenhuma regra conhecia: o modelo acertou
        self.assertEqual(c.classificar("'list' object has no attribute 'items'")[0], "bug")
        novo = "Erro Zorblax: o portal intergaláctico recusou a requisição"
        self.assertNotEqual(c.classificar(novo)[0], "externo")
        for _ in range(3):
            c.aprender(novo, "externo")
        self.assertEqual(c.classificar("Erro Zorblax: o portal recusou de novo")[0], "externo")
        c2 = ClassificadorErros(c.exportar())                              # sobrevive a salvar/carregar
        self.assertEqual(c2.classificar("Erro Zorblax no portal")[0], "externo")
        self.assertEqual(c2.estado()["aprendidos_com_voce"], 3)


class TestHipoteses(unittest.TestCase):
    def setUp(self):
        self.m = MotorHipoteses()

    def test_internet_caiu_x_servico_fora(self):
        h = self.m.avaliar({"categoria": "rede", "modulos_com_rede_5min": 3, "conectividade": False})
        self.assertEqual(h[0]["causa"], "internet_caiu")
        self.assertGreater(h[0]["prob"], 0.9)
        self.assertTrue(any("teste de conexão" in e for e in h[0]["evidencias"]))
        h = self.m.avaliar({"categoria": "rede", "modulos_com_rede_5min": 1, "conectividade": True})
        self.assertEqual(h[0]["causa"], "servico_externo_fora")

    def test_codigo_mudou_e_dados(self):
        h = self.m.avaliar({"categoria": "bug", "arquivo_modificado_h": 2.0})
        self.assertEqual(h[0]["causa"], "mudanca_no_codigo")
        self.assertEqual(self.m.avaliar({"categoria": "json_corrompido"})[0]["causa"], "dados_corrompidos")
        self.assertEqual(self.m.avaliar({"categoria": "bug", "falha_so_com_params": True})[0]["causa"], "parametro_ruim")

    def test_historico_do_modulo_pesa(self):
        sem = self.m.avaliar({"categoria": "timeout"})
        com = self.m.avaliar({"categoria": "timeout", "causas_anteriores": {"sobrecarga": 5}})
        p = lambda hs, c: next(x["prob"] for x in hs if x["causa"] == c)   # noqa: E731
        self.assertGreater(p(com, "sobrecarga"), p(sem, "sobrecarga"))


class TestDecisao(unittest.TestCase):
    HIP_REDE = [{"causa": "internet_caiu", "prob": 0.9, "descricao": "a internet caiu", "evidencias": []},
                {"causa": "servico_externo_fora", "prob": 0.1, "descricao": "serviço fora", "evidencias": []}]

    def test_sem_experiencia_segue_a_causa(self):
        escolhas = [MotorDecisao(semente=s).decidir({"categoria": "rede"}, self.HIP_REDE).tratamento for s in range(20)]
        self.assertGreaterEqual(escolhas.count("esperar_rede"), 17)

    def test_experiencia_muda_a_escolha(self):
        m = MotorDecisao(semente=1)
        for _ in range(8):
            m.aprender("rede", "esperar_rede", False)
            m.aprender("rede", "isolar_temporario", True)
        d = m.decidir({"categoria": "rede"}, self.HIP_REDE)
        self.assertEqual(d.tratamento, "isolar_temporario")
        self.assertIn("funcionou 8 de 8", d.explicacao)
        self.assertIn("90%", d.explicacao)

    def test_permissao_exclusao_e_anticorpo(self):
        m = MotorDecisao(semente=1)
        hip = [{"causa": "bug_no_plugin", "prob": 1.0, "descricao": "bug", "evidencias": []}]
        self.assertNotEqual(m.decidir({"categoria": "bug"}, hip, autonomia="observar").tratamento, "recarregar_modulo")
        d = m.decidir({"categoria": "rede"}, self.HIP_REDE, excluir={"esperar_rede", "isolar_temporario", "observar"})
        self.assertEqual(d.tratamento, "pedir_intervencao")
        d = m.decidir({"categoria": "rede"}, self.HIP_REDE, conhecido="isolar_temporario")
        self.assertEqual(d.tratamento, "isolar_temporario")
        self.assertIn("anticorpo", d.explicacao)


class TestCerebroFluxo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jarvis_bio_"))
        self.raiz = projeto(self.tmp)
        self.rede = {"ok": False}
        self.org = organismo(self.raiz, self.rede)

    def tearDown(self):
        self.org.encerrar()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def falhar(self, n=3, erro=None):
        for _ in range(n):
            self.org.sentinela.resultado("bioteste_clima", {"action": "agora"}, 120, False, erro or ConnectionError(ERRO_REDE))

    def test_internet_caiu_esperar_e_aprender(self):
        self.falhar()
        inc = self.org.memoria.incidentes(limite=1)[0]
        self.assertEqual((inc["categoria"], inc["causa"], inc["tratamento"]), ("rede", "internet_caiu", "esperar_rede"))
        self.assertIn("[DESCANSANDO]", self.org.portao("bioteste_clima", {"action": "agora"})[1])
        self.rede["ok"] = True
        self.assertTrue(self.org.verificar_rede())                     # a internet voltou: libera o teste na hora
        self.assertIsNone(self.org.portao("bioteste_clima", {"action": "agora"}))
        self.org.sentinela.resultado("bioteste_clima", {"action": "agora"}, 100, True)
        inc = self.org.memoria.incidente(inc["id"])
        self.assertEqual(inc["estado"], "resolvido")
        self.assertEqual(self.org.cerebro.decisao.placar["rede|esperar_rede"], [1, 0])
        self.assertEqual(self.org.memoria.reconhecer(inc["impressao"])["tratamento_bom"], "esperar_rede")
        self.assertEqual(self.org.saude.avaliar({}, {}, [], [], 0)["cor"], "verde")
        self.assertIn("internet caiu", self.org.cerebro.explicar(inc["id"]))

    def test_recaida_troca_de_tratamento_e_depois_chama_voce(self):
        self.falhar()
        iid = self.org.memoria.incidentes(limite=1)[0]["id"]
        tentados = [self.org.memoria.incidente(iid)["tratamento"]]
        for _ in range(4):
            self.org.cerebro.pendentes = {k: dict(p, ts=p["ts"] - 10) for k, p in self.org.cerebro.pendentes.items()}
            self.org.imune.isolamento.liberar("bioteste_clima", por="teste")
            self.falhar(1)                                              # o mesmo erro voltou
            tentados.append(self.org.memoria.incidente(iid)["tratamento"])
        self.assertGreaterEqual(len(set(tentados)), 2)                  # não repetiu o que falhou
        self.assertEqual(tentados[-1], "pedir_intervencao")
        self.assertEqual(self.org.memoria.incidente(iid)["estado"], "aguardando_humano")
        falhas = [d for d in self.org.memoria.decisoes(20, iid) if (d.get("resultado") or "").startswith("falhou")]
        self.assertGreaterEqual(len(falhas), 2)

    def test_erro_desconhecido_vira_aprendizado(self):
        self.falhar(3, RuntimeError("Erro Zorblax: o portal intergaláctico recusou"))
        inc = self.org.memoria.incidentes(limite=1)[0]
        self.assertIn(inc["categoria"], ("desconhecida", "externo", "bug", "rede"))
        self.assertTrue(self.org.memoria.decisoes(5, inc["id"]))


if __name__ == "__main__":
    unittest.main()
