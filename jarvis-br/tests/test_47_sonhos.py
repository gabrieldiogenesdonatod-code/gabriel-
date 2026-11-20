"""Testes da 2.20 — o JARVIS sonha: acha padrões verdadeiros, fica quieto quando não há padrão e conta de manhã."""
import random
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from plugins import _lote2, sonhos

HOJE = date(2026, 11, 13)


def dados_com_padrao(semanas: int, semente: int) -> dict:
    """Sextas vendem 45% a mais, água acompanha as horas trabalhadas e ontem foi um dia fora da curva."""
    rng, vendas, agua, horas = random.Random(semente), {}, {}, {}
    for k in range(semanas * 7, 0, -1):
        d = HOJE - timedelta(k)
        vendas[d.isoformat()] = 600 * (1.45 if d.weekday() == 4 else 1.0) * rng.uniform(.8, 1.2)
        ml = rng.choice([1200, 1500, 2200, 2600, 3000])
        agua[d.isoformat()], horas[d.isoformat()] = ml, 7 + (2 if ml >= 2200 else 0) + rng.choice([0, 1])
    vendas[(HOJE - timedelta(1)).isoformat()] = 2500
    return {"vendas da loja": vendas, "água bebida": agua, "horas trabalhadas": horas}


def dados_aleatorios(semente: int) -> dict:
    rng = random.Random(semente)
    dias = [(HOJE - timedelta(k)).isoformat() for k in range(60, 0, -1)]
    return {"vendas da loja": {d: rng.uniform(300, 900) for d in dias},
            "água bebida": {d: rng.choice([1200, 1500, 2200, 2600, 3000]) for d in dias},
            "horas trabalhadas": {d: rng.randint(7, 10) for d in dias},
            "km corridos": {d: rng.uniform(3, 8) for d in dias if rng.random() < .4}}


class TestSonhos(unittest.TestCase):
    def test_acha_os_padroes_verdadeiros(self):
        achou = {"sexta": 0, "agua": 0, "ontem": 0}
        for s in range(20):
            ach = sonhos.sonhar_com(dados_com_padrao(8, s), HOJE, rng=random.Random(s))
            for a in ach:
                ok = ("sextas" in a and "vendas" in a) or ("Ontem" in a and "vendas" in a) or \
                     ("horas trabalhadas" in a and "água" in a and "seguinte" not in a)
                self.assertTrue(ok, f"descoberta falsa: {a}")
            achou["sexta"] += any("sextas" in a for a in ach)
            achou["agua"] += any("água" in a for a in ach)
            achou["ontem"] += any(a.startswith("Ontem") for a in ach)
        self.assertGreaterEqual(min(achou.values()), 17, achou)

    def test_fica_quieto_sem_padrao(self):
        falsas = sum(len(sonhos.sonhar_com(dados_aleatorios(1000 + s), HOJE, rng=random.Random(s))) for s in range(40))
        self.assertLessEqual(falsas, 4)                     # alvo: ~5% das noites

    def test_frases_e_estatistica(self):
        self.assertEqual(sonhos._mais(-27.4), "27% a menos")
        self.assertGreater(sonhos.forca([10, 11, 12, 10, 9999], [1, 2, 1, 2, 3]), 3)       # o 9999 não estraga a conta
        self.assertEqual(sonhos.postos([5, 1], [100]), ([1, 0], [2]))
        self.assertTrue(sonhos.acaso([1, 2, 3], [2, 3, 1], 0.01, random.Random(1)))
        self.assertFalse(sonhos.acaso(list(range(100, 120)), list(range(20)), 0.001, random.Random(1)))
        txt = " ".join(sonhos.sonhar_com(dados_com_padrao(10, 3), HOJE, rng=random.Random(3)))
        self.assertNotIn("Nas sábados", txt)
        self.assertNotIn(" fica ", txt)

    def test_plugin_ponta_a_ponta(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(_lote2, "PASTA", tmp), mock.patch.object(sonhos, "date") as d:
            d.today.return_value, d.fromisoformat = HOJE, date.fromisoformat
            self.assertIn("Ainda não sonhei", sonhos.run({"action": "ultimo"}))
            self.assertIn("Ainda não tenho dados", sonhos.run({"action": "dados"}))
            self.assertIn("ainda não achei nenhum padrão", sonhos.run({"action": "sonhar"}))
            caixa = {"dias": {k: {"vendas": [[v, "pix"]]} for k, v in dados_com_padrao(8, 1)["vendas da loja"].items()}}
            _lote2.guardar("caixa", caixa)
            self.assertIn("vendas da loja (56 dias)", sonhos.run({"action": "dados"}))
            r = sonhos.run({"action": "sonhar"})
            self.assertIn("Nas sextas há", r)
            self.assertIn("não certeza de causa", r)
            self.assertEqual(len(_lote2.carregar("sonhos", [])), 2)
            self.assertIn("2026-11-13", sonhos.run({"action": "diario"}))


if __name__ == "__main__":
    unittest.main()
