"""Testes da 2.17 — lote 1: 6 modos e 9 plugins (funções puras, sem rede nem teclado)."""
import random
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from plugins import (adivinha, apps_winget, clientes_loja, fiado, git_assistente, lista_compras, manutencao_casa,
                     meta_vendas, modos, torneio)


class TestLote1(unittest.TestCase):
    def test_modos(self):
        self.assertEqual(len(modos.MODOS), 6)
        self.assertEqual(modos.chave("modo vovó"), "vo")
        self.assertEqual(modos.ler_passos("abrir notion; volume 20; fechar discord")[1], {"tipo": "volume", "nivel": 20})
        pasta = Path(tempfile.mkdtemp())
        with mock.patch.object(modos, "ARQ_ESTADO", pasta / "e.json"), mock.patch.object(modos, "ARQ_MEUS", pasta / "m.json"), \
                mock.patch.object(modos, "_rodar", lambda passos, player: []):
            self.assertIn("[MODO LOJA]", modos.entrar("loja"))
            self.assertEqual(modos.atual(), "loja")
            modos.entrar("reunião")
            self.assertEqual(modos.atual(), "reuniao")
            self.assertIn("Saí", modos.sair())

    def test_loja(self):
        self.assertEqual(clientes_loja.aniversario_em("12/11", date(2026, 11, 9), 7), 3)
        movs = [{"data": "2026-09-01", "tipo": "compra", "valor": 100}, {"data": "2026-10-01", "tipo": "compra", "valor": 50},
                {"data": "2026-10-05", "tipo": "pagamento", "valor": 100}]
        self.assertEqual(fiado.saldo(movs), 50)
        self.assertEqual(fiado.dias_devendo(movs, date(2026, 11, 9)), 39)
        r = meta_vendas.progresso(3000, 6000, date(2026, 11, 10))
        self.assertAlmostEqual(r["por_dia"], 3000 / 21)

    def test_diversao(self):
        c = torneio.chaveamento(["A", "B", "C"], random.Random(1))
        self.assertEqual(sum(1 for j in c for x in j if x is None), 1)
        prox = torneio.avancar([["A", "B"], ["C", None]], {"A|B": "A"})
        self.assertEqual(prox, [["A", "C"]])
        self.assertEqual(torneio.avancar([["A", "C"]], {"A|C": "C"}), [["C", "CAMPEÃO"]])
        self.assertTrue(adivinha.acertou("homem aranha", "Homem-Aranha"))
        self.assertFalse(adivinha.acertou("batman", "Hulk"))

    def test_pc(self):
        s = git_assistente.resumo_status("## main...origin/main [ahead 2]\n M a.py\n?? b.py\n")
        self.assertEqual((s["branch"], s["mudados"], s["novos"], s["frente"]), ("main", 1, 1, 2))
        saida = ("Nome              Id                 Versão   Disponível Origem\n"
                 "-----------------------------------------------------------\n"
                 "Google Chrome     Google.Chrome      120.0    121.0      winget\n")
        self.assertEqual(apps_winget.tabela(saida)[0]["id"], "Google.Chrome")

    def test_casa(self):
        self.assertEqual(lista_compras.secao("leite"), "Laticínios")
        self.assertEqual(lista_compras.separar("leite, ovos e sabão"), ["leite", "ovos", "sabão"])
        self.assertEqual(manutencao_casa.dias_de("45 dias"), 45)
        self.assertEqual(manutencao_casa.dias_de("1 ano"), 365)


if __name__ == "__main__":
    unittest.main()
