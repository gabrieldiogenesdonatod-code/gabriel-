"""
Testes da 2.1 — o JARVIS só no celular (celular/app): os arquivos existem,
usam caminhos relativos (funcionam no GitHub Pages, numa subpasta) e não
dependem do PC.
"""
import json
import re
import unittest

import tests

APP = tests.RAIZ / "celular" / "app"


class TestAppCelular(unittest.TestCase):
    def test_arquivos_e_caminhos_relativos(self):
        for nome in ("index.html", "manifest.webmanifest", "sw.js", "icone.svg", "LEIA-ME.md"):
            self.assertTrue((APP / nome).exists(), nome)
        man = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual((man["start_url"], man["scope"], man["display"]), ("./", "./", "standalone"))
        html = (APP / "index.html").read_text(encoding="utf-8")
        self.assertFalse(re.search(r'(href|src)="/', html))                    # nada na raiz do site
        self.assertIn('register("sw.js")', html)
        self.assertNotIn("/api/", html)                                          # não fala com o PC
        sw = (APP / "sw.js").read_text(encoding="utf-8")
        self.assertIn('"./index.html"', sw)

    def test_ferramentas_e_memoria(self):
        html = (APP / "index.html").read_text(encoding="utf-8")
        nomes = re.findall(r'\{ name: "(\w+)"', html)
        for n in ("lembrar", "esquecer", "anotar", "pesquisar", "tocar_musica", "mandar_whatsapp", "agenda", "lembrete"):
            self.assertIn(n, nomes)
        for n in nomes:                                                          # toda ferramenta tem execução
            self.assertIn(f'case "{n}"', html)
        self.assertNotRegex(html, r"AIza[0-9A-Za-z_-]{20,}")                    # nenhuma chave no arquivo


if __name__ == "__main__":
    unittest.main()
