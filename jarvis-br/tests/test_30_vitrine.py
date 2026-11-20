"""
Testes da 2.6 — modo vitrine ("Jarvis, se apresenta"): roteiro editável,
versão curta, a apresentação passando cena por cena (sem sessão do Gemini, com
tempo acelerado) e a página com todas as cenas do roteiro.
"""
import time
import unittest
from unittest import mock

from plugins import vitrine as V
from tests import RAIZ


class TestVitrine(unittest.TestCase):
    def setUp(self):
        V.ARQ_ROTEIRO.unlink(missing_ok=True)

    def test_roteiro_e_versao_curta(self):
        cenas = V.roteiro()
        self.assertTrue(V.ARQ_ROTEIRO.exists())                       # cria o arquivo editável
        curta = V.escolher(cenas, "curta")
        self.assertLess(len(curta), len(cenas))
        self.assertEqual((curta[0]["visual"], curta[-1]["visual"]), ("abertura", "fim"))
        self.assertEqual(V.escolher(cenas, "completa"), cenas)
        V.gravar_json(V.ARQ_ROTEIRO, [dict(cenas[0], pular=True)] + cenas[1:3])
        self.assertEqual(len(V.roteiro()), 2)                        # "pular": true tira a cena
        self.assertGreater(V.duracao_estimada("x" * 140), 10)

    def test_todas_as_cenas_existem_na_pagina(self):
        pagina = (RAIZ / "dashboard" / "static" / "vitrine.html").read_text(encoding="utf-8")
        for c in V.ROTEIRO_PADRAO:
            self.assertRegex(pagina, rf"(VISUAIS\.|\b){c['visual']}\b")
        self.assertIn("FatihMakes", V.CREDITO)

    def test_apresentacao_passa_por_todas(self):
        vistos = []
        V.gravar_json(V.ARQ_ROTEIRO, V.ROTEIRO_PADRAO[:3])
        with mock.patch.object(V, "duracao_estimada", lambda f: 0.05), mock.patch.object(V, "_app", lambda: None), \
                mock.patch("plugins._arcade.abrir_pagina", lambda *a, **k: True), \
                mock.patch("core.microfone.esperar_jarvis_calar", lambda **k: None), \
                mock.patch.object(V, "_esperar", lambda s: (vistos.append(V.estado_tela()["indice"]) or False)
                                  if s > 1 else V._estado["parar"].is_set()):
            self.assertIn("3 cenas", V.run({"action": "iniciar"}))
            for _ in range(100):
                if not V._estado["ativo"]:
                    break
                time.sleep(0.05)
        self.assertFalse(V._estado["ativo"])
        self.assertEqual(sorted(set(i for i in vistos if i >= 0)), [0, 1, 2, 3])        # 3 cenas + créditos
        self.assertIn("parada", V.run({"action": "status"}))


if __name__ == "__main__":
    unittest.main()
