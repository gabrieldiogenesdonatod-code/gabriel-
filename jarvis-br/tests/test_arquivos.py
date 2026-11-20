"""Limpeza e organização de downloads: só mexem onde devem, e o desfazer volta tudo."""
import os
import tempfile
import time
import unittest
from pathlib import Path

import tests  # noqa: F401
from plugins import downloads as dl
from plugins import limpeza


def velho(caminho: Path, horas: float = 3):
    t = time.time() - horas * 3600
    os.utime(caminho, (t, t))


class TestLimpeza(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name) / "temp"
        self.fora = Path(self.tmp.name) / "fora"
        (self.raiz / "sub").mkdir(parents=True)
        self.fora.mkdir()
        (self.raiz / "velho.bin").write_bytes(b"x" * 1000)
        (self.raiz / "sub" / "velho2.bin").write_bytes(b"x" * 500)
        (self.raiz / "novo.txt").write_text("em uso")
        (self.fora / "importante.txt").write_text("NÃO APAGAR")
        velho(self.raiz / "velho.bin")
        velho(self.raiz / "sub" / "velho2.bin")
        velho(self.fora / "importante.txt")
        self.link = None
        try:
            os.symlink(self.fora, self.raiz / "atalho_para_fora", target_is_directory=True)
            self.link = self.raiz / "atalho_para_fora"
        except (OSError, NotImplementedError):
            pass                      # Windows sem permissão de criar links

    def tearDown(self):
        self.tmp.cleanup()

    def test_mede_so_os_velhos(self):
        total = sum(limpeza.medir([self.raiz], 3600).values())
        self.assertEqual(total, 1500)

    def test_apaga_so_dentro_e_so_velhos(self):
        liberado, _pulados = limpeza._apagar_raiz(self.raiz, 3600, "apagar")
        self.assertEqual(liberado, 1500)
        self.assertFalse((self.raiz / "velho.bin").exists())
        self.assertFalse((self.raiz / "sub").exists())                # pasta vazia removida
        self.assertTrue((self.raiz / "novo.txt").exists())            # recente fica
        self.assertTrue((self.fora / "importante.txt").exists())      # link nunca é seguido
        self.assertEqual((self.fora / "importante.txt").read_text(), "NÃO APAGAR")


class TestDownloads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.antiga = dl.pasta
        dl.pasta = lambda: self.pasta
        for nome in ("foto.jpg", "nota.pdf", "setup.exe", "filme.mp4", "estranho.xyz",
                     "baixando.zip.crdownload"):
            (self.pasta / nome).write_bytes(b"123")
            velho(self.pasta / nome, 1)
        (self.pasta / "PDFs").mkdir()
        (self.pasta / "PDFs" / "nota.pdf").write_text("já existia")

    def tearDown(self):
        dl.pasta = self.antiga
        self.tmp.cleanup()

    def test_organizar_e_desfazer(self):
        from core import undo
        undo.clear()
        r = dl.organizar()
        self.assertIn("Organizei 4", r)
        self.assertTrue((self.pasta / "Imagens" / "foto.jpg").exists())
        self.assertTrue((self.pasta / "Instaladores" / "setup.exe").exists())
        self.assertTrue((self.pasta / "Vídeos" / "filme.mp4").exists())
        # não sobrescreve: o PDF novo vira "nota (2).pdf"
        self.assertEqual((self.pasta / "PDFs" / "nota.pdf").read_text(), "já existia")
        self.assertTrue((self.pasta / "PDFs" / "nota (2).pdf").exists())
        # sem categoria e download incompleto ficam onde estão
        self.assertTrue((self.pasta / "estranho.xyz").exists())
        self.assertTrue((self.pasta / "baixando.zip.crdownload").exists())
        resultado = undo.undo_last()
        self.assertIn("4 arquivo(s) de volta", resultado)
        self.assertTrue((self.pasta / "foto.jpg").exists())
        self.assertTrue((self.pasta / "nota.pdf").exists())
        self.assertEqual((self.pasta / "PDFs" / "nota.pdf").read_text(), "já existia")

    def test_destino_livre(self):
        (self.pasta / "a.txt").write_text("1")
        (self.pasta / "a (2).txt").write_text("2")
        self.assertEqual(dl.destino_livre(self.pasta / "a.txt").name, "a (3).txt")
        self.assertEqual(dl.destino_livre(self.pasta / "b.txt").name, "b.txt")


if __name__ == "__main__":
    unittest.main()
