"""
Testes da 2.5 — Arcade: os 5 jogos novos (caça-palavras, meteoros, labirinto
do Bitinho, sudoku, pong), os nomes por voz e as rotas que os plugins penduram
no servidor local. A lógica dos jogos (sudoku com solução única, labirinto sem
beco) roda no Node, se ele estiver instalado (o mesmo da ponte do WhatsApp).
"""
import json
import re
import shutil
import subprocess
import unittest
import urllib.request

from plugins import _arcade, jogos
from tests import RAIZ

PAGINA = (RAIZ / "dashboard" / "static" / "arcade.html").read_text(encoding="utf-8")


def bloco(nome: str) -> str:
    """O código de `const Nome = {…};` dentro do arcade.html."""
    m = re.search(rf"^const {nome} = \{{.*?^\}};$", PAGINA, re.S | re.M)
    if not m:
        raise AssertionError(f"{nome} não está no arcade.html")
    return m.group(0)


class TestJogosNovos(unittest.TestCase):
    def test_estao_no_menu(self):
        for nome, ident in (("CacaPalavras", "cacapalavras"), ("Meteoros", "meteoros"), ("Labirinto", "labirinto"),
                            ("Sudoku", "sudoku"), ("Pong", "pong")):
            self.assertIn(f'id: "{ident}"', bloco(nome))
            self.assertIn(nome, PAGINA.split("const JOGOS = [", 1)[1].split("];", 1)[0])

    def test_voz(self):
        self.assertEqual(jogos.qual_jogo("abre o caça-palavras"), "cacapalavras")
        self.assertEqual(jogos.qual_jogo("bora jogar pac man"), "labirinto")
        self.assertEqual(jogos.qual_jogo("quero o jogo de asteroides"), "meteoros")
        self.assertEqual(jogos.qual_jogo("um sudoku difícil"), "sudoku")
        self.assertEqual(jogos.qual_jogo("ping pong"), "pong")
        self.assertEqual(jogos.qual_jogo("jogo da forca"), "forca")
        self.assertEqual(jogos.NOMES_PLACAR["labirinto"], "Labirinto do Bitinho")

    def test_personagem_original(self):
        """O labirinto não usa nome nem personagem de jogo famoso."""
        codigo = bloco("Labirinto").lower()
        for proibido in ("pac", "fantasma", "ghost", "blinky", "pinky", "inky", "clyde"):
            self.assertNotIn(proibido, codigo)

    @unittest.skipUnless(shutil.which("node"), "precisa do Node")
    def test_logica_no_node(self):
        js = ("const rnd = n => Math.floor(Math.random() * n);\n"
              "const embaralhar = a => { for (let i = a.length - 1; i > 0; i--) { const j = rnd(i + 1); "
              "[a[i], a[j]] = [a[j], a[i]]; } return a; };\n"
              "const DIRS4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];\n"
              + bloco("Sudoku") + "\n" + bloco("Labirinto") + "\n" + r"""
const out = {};
const g = Array(81).fill(0); Sudoku.resolver(g);
const linhasOk = [...Array(9).keys()].every(r => new Set(g.slice(r * 9, r * 9 + 9)).size === 9);
const p = g.slice(); for (const i of embaralhar([...Array(81).keys()])) { if (p.filter(Boolean).length <= 30) break;
  const v = p[i]; p[i] = 0; if (Sudoku.resolver(p.slice(), true) !== 1) p[i] = v; }
out.sudoku = {linhasOk, dadas: p.filter(Boolean).length, unica: Sudoku.resolver(p.slice(), true)};
Labirinto.C = 21; Labirinto.L = 15;
let becos = 0, desconexo = 0;
for (let k = 0; k < 20; k++) {
  const m = Labirinto.gerar(); Labirinto.m = m;
  for (let y = 1; y < 14; y += 2) for (let x = 1; x < 20; x += 2) if (DIRS4.filter(([dx, dy]) => m[y + dy][x + dx] === 0).length < 2) becos++;
  const visto = new Set(["1,1"]), fila = [[1, 1]];
  while (fila.length) { const [x, y] = fila.pop(); for (const [dx, dy] of DIRS4) { const k2 = (x + dx) + "," + (y + dy);
    if (Labirinto.livre(x + dx, y + dy) && !visto.has(k2)) { visto.add(k2); fila.push([x + dx, y + dy]); } } }
  let livres = 0; for (let y = 0; y < 15; y++) for (let x = 0; x < 21; x++) livres += m[y][x] === 0;
  if (visto.size !== livres) desconexo++;
}
out.labirinto = {becos, desconexo};
console.log(JSON.stringify(out));
""")
        r = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(out["sudoku"]["linhasOk"])
        self.assertEqual(out["sudoku"]["unica"], 1)
        self.assertLessEqual(out["sudoku"]["dadas"], 40)
        self.assertEqual(out["labirinto"], {"becos": 0, "desconexo": 0})


class TestRotasDosPlugins(unittest.TestCase):
    def test_get_e_post(self):
        _arcade.ROTAS_GET["/api/teste25"] = lambda q: {"eco": q.get("x")}
        _arcade.ROTAS_POST["/api/teste25/cmd"] = lambda b: {"dobro": 2 * int(b["n"])}
        base = _arcade.iniciar().split("/?")[0]
        try:
            with urllib.request.urlopen(f"{base}/api/teste25?t={_arcade.TOKEN}&x=oi", timeout=5) as r:
                self.assertEqual(json.loads(r.read()), {"eco": "oi"})
            req = urllib.request.Request(f"{base}/api/teste25/cmd?t={_arcade.TOKEN}", data=b'{"n": 21}',
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as r:
                self.assertEqual(json.loads(r.read()), {"dobro": 42})
            for pagina in ("/encomendas", "/mao"):
                with urllib.request.urlopen(f"{base}{pagina}?t={_arcade.TOKEN}", timeout=5) as r:
                    self.assertIn(b"<!DOCTYPE html>", r.read())
        finally:
            _arcade.ROTAS_GET.pop("/api/teste25", None)
            _arcade.ROTAS_POST.pop("/api/teste25/cmd", None)
            _arcade.parar()


if __name__ == "__main__":
    unittest.main()
