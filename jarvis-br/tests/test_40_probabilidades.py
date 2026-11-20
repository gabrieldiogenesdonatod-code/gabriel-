"""
Testes da 2.14 — motor de probabilidades, balança JARVIS × FRIDAY e o gesto
"abrir e fechar a mão". Só funções puras e o estado do PC passado à mão:
não usa câmera, microfone, internet nem IA.
"""
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401  (ajusta o caminho, como os outros testes)
from plugins import gestos as G
from plugins import jarvis_friday as J
from plugins import probabilidades as pb

ESTADO = {"internet": True, "ping": 30, "livre_min": 40, "livre_bytes": 100 * 1024 ** 3, "temp": 60}


class TestProbabilidades(unittest.TestCase):
    def setUp(self):
        self._arq = pb.ARQUIVO
        pb.ARQUIVO = Path(tempfile.mkdtemp()) / "p.json"

    def tearDown(self):
        pb.ARQUIVO = self._arq

    def test_puras(self):
        self.assertEqual(pb.classificar("baixar o jogo"), ["baixar"])
        self.assertEqual(pb.classificar("jogar valorant"), ["jogar"])
        self.assertEqual(len(pb.dividir_passos("baixar o jogo e depois instalar, e abrir")), 3)
        self.assertEqual(pb.extrair_tamanho("20 GB"), 20 * 1024 ** 3)
        t = pb.monte_carlo([(10, 60, 30)])
        self.assertTrue(10 <= t["p10"] <= t["p50"] <= t["p90"] <= 60)
        self.assertAlmostEqual(pb.combinar(0.5, []), 0.5)

    def test_calculos(self):
        r = pb.calcular("abrir o chrome", estado=ESTADO, usar_ia=False)
        self.assertGreater(r["chance"], 0.9)
        self.assertEqual(r["viabilidade"], "possível")
        self.assertIn("%", pb.texto(r))
        sem_net = pb.calcular("baixar 2 GB", estado={**ESTADO, "internet": False}, usar_ia=False)
        self.assertEqual(sem_net["viabilidade"], "impossível agora")
        sem_espaco = pb.calcular("baixar 500 GB", estado=ESTADO, usar_ia=False)
        self.assertEqual(sem_espaco["viabilidade"], "impossível agora")
        dois = pb.calcular("baixar um jogo de 20 GB e depois instalar", estado=ESTADO, usar_ia=False)
        nomes = [f["nome"] for f in dois["fatores"]]
        self.assertEqual(len(nomes), len(set(nomes)))          # fator repetido conta uma vez
        self.assertLess(dois["chance"], r["chance"])

    def test_aprende(self):
        pb.run({"action": "calcular", "tarefa": "compilar o projeto"})
        self.assertIn("deu certo", pb.run({"action": "resultado", "deu_certo": True, "tempo_real": 90}))
        self.assertIn("1 previs", pb.run({"action": "historico"}))


class TestBalanca(unittest.TestCase):
    def test_balanca_fecha_na_chance(self):
        for tarefa in ("baixar um jogo de 20 GB e depois instalar", "abrir o chrome", "formatar o disco D"):
            r = pb.calcular(tarefa, estado=ESTADO, usar_ia=False)
            b = J.balanca(r, 3)
            self.assertAlmostEqual(b["marcha"][-1][2], r["chance"], places=2)
            quem = {f["quem"] for f in b["falas"]}
            self.assertEqual(quem, {"JARVIS", "FRIDAY"})
            self.assertIn(f"{round(100 * r['chance'])}%", b["falas"][-1]["texto"] + b["falas"][-2]["texto"])
        self.assertEqual(J.veredito(pb.calcular("formatar o disco D", estado=ESTADO, usar_ia=False)),
                         "não fazer agora")
        self.assertTrue(J.eh_decisao("vale a pena formatar o pc"))


class TestGestoAbrirFechar(unittest.TestCase):
    def test_abrir_fechar_e_pausa(self):
        from tests.test_19_ideias import mao
        it, acoes = G.Interpretador(), []
        for k in range(4):                                    # aberta ~0,3 s
            acoes += it.alimentar(mao(), k * 0.08)
        for k in range(4, 7):                                 # fecha
            acoes += it.alimentar(mao(()), k * 0.08)
        self.assertEqual(acoes, [("abrir_fechar",)])
        it, acoes = G.Interpretador(), []
        for k in range(10):                                   # aberta parada: continua sendo pausa
            acoes += it.alimentar(mao(), k * 0.08)
        for k in range(10, 13):
            acoes += it.alimentar(mao(()), k * 0.08)
        self.assertEqual(acoes, [("play_pause",)])

    def test_comando(self):
        self.assertEqual(G.normalizar_comando("abre o cromi"), ("abrir", "chrome"))
        self.assertEqual(G.normalizar_comando("site youtube.com"), ("site", "youtube.com"))


if __name__ == "__main__":
    unittest.main()
