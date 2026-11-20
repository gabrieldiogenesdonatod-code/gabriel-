"""
Testes da 2.15 — emoções do rosto (core/emocoes.py), as deformações e o rosto
da SEXTA (core/avatar_expressoes.py, só numpy) e as emoções no palco. Não abre
interface nem precisa do PyQt6.
"""
import time
import unittest

import numpy as np

import tests  # noqa: F401
from core import avatar_expressoes as AX
from core import emocoes as E
from core.avatar_mesh import get_head_mesh


class TestEmocoes(unittest.TestCase):
    def test_normalizar_e_detectar(self):
        self.assertEqual(E.normalizar("Surpreso"), "surpresa")
        self.assertEqual(E.normalizar("brava"), "raiva")
        self.assertIsNone(E.normalizar("xyz"))
        self.assertEqual(E.detectar("Infelizmente não consegui abrir"), "triste")
        self.assertEqual(E.detectar("Uau, isso é novo"), "surpresa")
        self.assertEqual(E.detectar("Perfeito, senhor, deu certo"), "feliz")
        self.assertEqual(E.detectar("Senhor, as chances de sucesso são de 14%"), "triste")
        self.assertEqual(E.detectar("Senhor, as chances de sucesso são de 92%"), "feliz")
        self.assertEqual(E.detectar("Cuidado, isso é um golpe"), "serio")
        self.assertIsNone(E.detectar("Abrindo o Chrome."))

    def test_estado_e_tempo(self):
        E.definir("surpresa", 0.05, quem="TESTE")
        self.assertEqual(E.atual("TESTE")[0], "surpresa")
        a = E.alvos("TESTE")
        self.assertGreater(a["olhos"], 1.2)
        time.sleep(0.08)
        self.assertEqual(E.atual("TESTE")[0], "neutro")          # volta sozinho

    def test_automatico(self):
        E.AUTOMATICO["ligado"] = False
        try:
            self.assertIsNone(E.ao_falar("Uau!"))
        finally:
            E.AUTOMATICO["ligado"] = True


class TestRosto3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.M = get_head_mesh()
        cls.G = AX.geometria(cls.M)

    def _boca(self, v):
        lm = self.M["landmarks"]["lips_out"]
        pts = v[lm]
        cantos = pts[np.argsort(np.abs(pts[:, 0]))[-4:], 1].mean()
        meio = pts[np.argsort(np.abs(pts[:, 0]))[:4], 1].mean()
        return cantos - meio

    def test_sorriso_e_tristeza(self):
        base = self._boca(self.M["verts"])
        feliz = self.M["verts"].copy()
        AX.aplicar(feliz, self.M, self.G, {"sorriso": 1.0})
        triste = self.M["verts"].copy()
        AX.aplicar(triste, self.M, self.G, {"sorriso": -1.0})
        self.assertGreater(self._boca(feliz), base + 0.02)     # cantos sobem
        self.assertLess(self._boca(triste), base - 0.02)       # cantos descem

    def test_sobrancelhas(self):
        lm = self.M["landmarks"]["brow_l"]
        v = self.M["verts"].copy()
        AX.aplicar(v, self.M, self.G, {"sobr_dentro": 1.0})
        dentro = np.argmin(np.abs(self.M["verts"][lm, 0]))
        self.assertGreater(v[lm][dentro, 1], self.M["verts"][lm][dentro, 1])

    def test_rosto_da_sexta(self):
        vf = AX.rosto_friday(self.M["verts"], self.M, self.G)
        self.assertEqual(vf.shape, self.M["verts"].shape)
        self.assertLess(np.ptp(vf[:, 0]), np.ptp(self.M["verts"][:, 0]))     # rosto mais fino
        xs, ys = 200 + vf[:, 0] * 90, 200 - vf[:, 1] * 90
        cab = AX.cabelo(AX.lados_do_rosto(xs, ys, vf), 90, 0.3)
        self.assertGreater(len(cab["tras"]), 10)
        self.assertTrue(all(np.isfinite(np.array(f)).all() for f in cab["tras"] + cab["franja"]))
        lm = self.M["landmarks"]["eye_l"]
        self.assertGreater(len(AX.cilios(xs[lm], ys[lm], 90)), 3)


class TestPalco(unittest.TestCase):
    def test_estado_tem_emocao_e_rosto(self):
        from plugins import _dupla as D
        antes = list(D._estado["personagens"])
        try:
            D._estado["personagens"] = ["JARVIS", "FRIDAY"]
            E.definir("feliz", 5, quem="FRIDAY")
            st = D.estado_palco()
            f = next(p for p in st["personagens"] if p["id"] == "FRIDAY")
            j = next(p for p in st["personagens"] if p["id"] == "JARVIS")
            self.assertEqual((f["emocao"], f["rosto"]), ("feliz", "friday"))
            self.assertEqual(j["rosto"], "jarvis")
        finally:
            D._estado["personagens"] = antes

    def test_plugin(self):
        from plugins import expressoes as X
        self.assertIn("feliz", X.run({"action": "listar"}))
        self.assertIn("surpresa", X.run({"action": "mostrar", "emocao": "surpreso", "segundos": 2}))
        self.assertEqual(E.atual()[0], "surpresa")
        self.assertIn("Não conheço", X.run({"action": "mostrar", "emocao": "xyz"}))


if __name__ == "__main__":
    unittest.main()
