"""Nota de saúde do PC (plugins/saude_pc.calcular_nota) e relatório HTML."""
import unittest

import tests  # noqa: F401
from plugins.saude_pc import calcular_nota, conceito, gerar_html

GB = 1024 ** 3


class TestNota(unittest.TestCase):
    def test_pc_perfeito(self):
        d = {"particoes": [{"ponto": "C:", "pct": 40, "livre": 300 * GB}], "temp_cpu": 50,
             "ram_media": 40, "inicializacao_ativos": 4, "uptime_dias": 1, "lixo_bytes": 100 * 1024 ** 2,
             "dias_sem_update": 5, "reinicio_pendente": False, "dispositivos_com_erro": 0,
             "antivirus": True, "tempo_real": True, "smart": [{"disco": "SSD", "saude": "saudável"}]}
        nota, probs = calcular_nota(d)
        self.assertEqual(nota, 100)
        self.assertEqual(probs, [])
        self.assertEqual(conceito(nota), "excelente")

    def test_sem_dados_nao_penaliza(self):
        self.assertEqual(calcular_nota({})[0], 100)

    def test_disco(self):
        for pct, pontos in ((96, 25), (91, 15), (85, 5), (70, 0)):
            nota, _ = calcular_nota({"particoes": [{"ponto": "C:", "pct": pct, "livre": 1}]})
            self.assertEqual(nota, 100 - pontos, pct)

    def test_problemas_somam_e_ordenam(self):
        d = {"particoes": [{"ponto": "C:", "pct": 96, "livre": 1}], "temp_cpu": 92,
             "inicializacao_ativos": 12, "dias_sem_update": 70, "antivirus": False,
             "smart": [{"disco": "SSD", "saude": "ATENÇÃO"}]}
        nota, probs = calcular_nota(d)
        # 30 (SMART) + 25 (disco) + 20 (antivírus) + 15 (temp) + 12 (update) + 6 (inicialização)
        self.assertEqual(nota, 0)
        self.assertEqual([p["pontos"] for p in probs], [30, 25, 20, 15, 12, 6])
        self.assertTrue(all(p["sugestao"] for p in probs))

    def test_limites_intermediarios(self):
        self.assertEqual(calcular_nota({"temp_cpu": 82})[0], 92)
        self.assertEqual(calcular_nota({"ram_media": 92})[0], 90)
        self.assertEqual(calcular_nota({"uptime_dias": 15})[0], 94)
        self.assertEqual(calcular_nota({"lixo_bytes": 12 * GB})[0], 95)
        self.assertEqual(calcular_nota({"dispositivos_com_erro": 5})[0], 85)      # teto de 15
        self.assertEqual(calcular_nota({"antivirus": True, "tempo_real": False})[0], 90)
        self.assertEqual(calcular_nota({"reinicio_pendente": True})[0], 95)

    def test_conceitos(self):
        self.assertEqual(conceito(95), "excelente")
        self.assertEqual(conceito(80), "boa")
        self.assertEqual(conceito(60), "regular")
        self.assertEqual(conceito(30), "precisa de atenção")

    def test_html_escapa_texto(self):
        d = {"particoes": [{"ponto": "<script>", "pct": 96, "livre": 1}]}
        nota, probs = calcular_nota(d)
        html = gerar_html(nota, probs, d)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
