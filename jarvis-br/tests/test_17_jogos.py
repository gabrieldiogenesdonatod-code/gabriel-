"""
Testes da 1.7 — motor de xadrez próprio, jogos por voz e servidor do Arcade.
"""
import json
import random
import unittest
import urllib.error
import urllib.request

import tests
from plugins import _arcade, _jogos as J, _xadrez_motor as M, jogos, xadrez as xd


class _Isolado(unittest.TestCase):
    """Partidas e placar vão para a pasta temporária dos testes."""

    def setUp(self):
        self._orig = (xd.ARQ, jogos.ARQ, _arcade.ARQ_PLACAR)
        xd.ARQ = tests.TMP / "xadrez_t.json"
        jogos.ARQ = tests.TMP / "jogos_t.json"
        _arcade.ARQ_PLACAR = tests.TMP / "placar_t.json"
        for a in (xd.ARQ, jogos.ARQ, _arcade.ARQ_PLACAR):
            a.unlink(missing_ok=True)

    def tearDown(self):
        xd.ARQ, jogos.ARQ, _arcade.ARQ_PLACAR = self._orig


class TestMotor(unittest.TestCase):
    def test_perft(self):
        self.assertEqual([M.perft(M.Posicao(), d) for d in (1, 2, 3)], [20, 400, 8902])
        kiwi = M.Posicao("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        self.assertEqual((M.perft(kiwi, 1), M.perft(kiwi, 2)), (48, 2039))
        self.assertEqual(M.perft(M.Posicao("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"), 3), 2812)

    def test_fen_ida_e_volta(self):
        for fen in (M.INICIAL, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"):
            self.assertEqual(M.Posicao(fen).fen(), fen)
        p = M.Posicao().jogar((M.casa("e2"), M.casa("e4"), ""))
        self.assertEqual(p.fen(), "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")

    def test_ler_lance(self):
        p = M.Posicao()
        self.assertEqual(M.ler_lance(p, "e2 e4")[0], (12, 28, ""))
        self.assertEqual(M.ler_lance(p, "cavalo para f3")[0], (6, 21, ""))
        self.assertEqual(M.ler_lance(p, "peão e4")[0], (12, 28, ""))
        self.assertIsNone(M.ler_lance(p, "torre a5")[0])
        self.assertIn("Não entendi", M.ler_lance(p, "banana")[1])
        roque = M.Posicao("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        self.assertEqual(M.ler_lance(roque, "roque pequeno")[0], (4, 6, ""))
        self.assertEqual(M.ler_lance(roque, "roque grande")[0], (4, 2, ""))
        promo = M.Posicao("8/P7/8/8/8/8/8/k6K w - - 0 1")
        self.assertEqual(M.ler_lance(promo, "a8")[0][2], "Q")
        self.assertEqual(M.ler_lance(promo, "peão a8 vira cavalo")[0][2], "N")
        duas = M.Posicao("k7/8/8/8/8/8/4K3/R6R w - - 0 1")
        self.assertIn("Qual deles", M.ler_lance(duas, "torre d1")[1])

    def test_mate_afogado_e_en_passant(self):
        p = M.Posicao()
        for fala in ("f2 f3", "e7 e5", "g2 g4"):
            p = p.jogar(M.ler_lance(p, fala)[0])
        m = M.ler_lance(p, "dama h4")[0]
        self.assertEqual(M.falar_lance(p, m), "dama para h4, xeque-mate")
        self.assertEqual(p.jogar(m).resultado(), "mate_pretas")
        self.assertEqual(M.Posicao("k7/2Q5/1K6/8/8/8/8/8 b - - 0 1").resultado(), "afogado")
        self.assertEqual(M.Posicao("k7/8/1K6/8/8/8/8/8 w - - 0 1").resultado(), "empate")
        ep = M.Posicao("k7/8/8/3Pp3/8/8/8/K7 w - e6 0 1")
        m = M.ler_lance(ep, "d5 e6")[0]
        self.assertEqual(M.falar_lance(ep, m), "peão captura em e6")
        self.assertEqual(ep.jogar(m).tab[M.casa("e5")], "")

    def test_motor_acha_mate_e_nao_entrega_dama(self):
        pastor = M.Posicao("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 2 3")
        self.assertEqual(M.melhor_lance(pastor, "medio", random.Random(1)), (M.casa("f3"), M.casa("f7"), ""))
        pendurada = M.Posicao("k7/8/8/3q4/8/8/8/K2R4 w - - 0 1")
        self.assertEqual(M.melhor_lance(pendurada, "medio", random.Random(1))[1], M.casa("d5"))
        self.assertIn(M.melhor_lance(M.Posicao(), "facil", random.Random(2)), M.Posicao().legais())


class TestXadrezVoz(_Isolado):
    def test_partida(self):
        r = xd.run({"action": "novo", "jogo": "xadrez", "nivel": "facil"})
        self.assertIn("brancas", r)
        r = xd.run({"action": "lance", "lance": "e2 e4"})
        self.assertTrue(r.startswith("Você: peão para e4. Eu: "), r)
        d = json.loads(xd.ARQ.read_text(encoding="utf-8"))
        self.assertEqual(M.Posicao(d["fen"]).vez, "w")
        self.assertIn("não é permitido", xd.run({"action": "lance", "lance": "rei e8"}))
        self.assertIn("encerrada", xd.run({"action": "desistir"}))

    def test_pretas_e_damas(self):
        self.assertIn("Meu primeiro lance", xd.run({"action": "novo", "jogo": "xadrez", "cor": "pretas"}))
        self.assertIn("Damas", xd.run({"action": "novo", "jogo": "damas"}))
        self.assertTrue(xd.run({"action": "lance", "lance": "c3 d4"}).startswith("Você: c3 d4."))


class TestJogosLogica(unittest.TestCase):
    def test_velha_nunca_perde(self):
        rng = random.Random(3)
        for _ in range(30):                                # jogador aleatório contra o difícil
            t = [""] * 9
            while not J.velha_vencedor(t):
                t[rng.choice([i for i in range(9) if not t[i]])] = "X"
                if J.velha_vencedor(t):
                    break
                t[J.velha_jogada(t, "O", "dificil", rng)] = "O"
            self.assertNotEqual(J.velha_vencedor(t), "X")
        self.assertEqual(J.velha_jogada(["X", "X", "", "O", "O", "", "", "", ""], "O", "dificil"), 5)
        self.assertEqual(J.velha_ler("centro"), 4)
        self.assertEqual(J.velha_ler("canto superior direito"), 2)
        self.assertEqual(J.velha_ler("posição sete"), 6)
        self.assertIsNone(J.velha_ler("dez"))

    def test_lig4(self):
        c = J.lig4_novo()
        for col in (0, 1, 2):
            J.lig4_soltar(c, col, "X")
        self.assertEqual(J.lig4_jogada(c, "O", "medio", random.Random(1)), 3)    # bloqueia
        J.lig4_soltar(c, 3, "X")
        self.assertEqual(J.lig4_vencedor(c), "X")
        v = J.lig4_novo()
        for _ in range(4):
            J.lig4_soltar(v, 5, "O")
        self.assertEqual(J.lig4_vencedor(v), "O")
        self.assertFalse(J.lig4_soltar(v, 5, "X") and J.lig4_soltar(v, 5, "X") and J.lig4_soltar(v, 5, "X"))

    def test_forca(self):
        f = {"tema": "frutas", "palavra": "caju", "letras": [], "erros": 0}
        self.assertEqual(J.forca_chutar(f, "letra a"), "tem 1 A")
        self.assertEqual(J.forca_chutar(f, "é a letra z"), "não tem Z")
        self.assertEqual(J.forca_chutar(f, "a"), "a letra a já foi")
        self.assertEqual(J.forca_mascara(f), "_ a _ _")
        self.assertEqual(J.forca_chutar(f, "caju"), "acertou a palavra")
        self.assertEqual(J.forca_estado(f), "ganhou")
        f2 = J.forca_nova("animal", random.Random(1))
        self.assertEqual(f2["tema"], "animais")
        self.assertIn("lobo guara", J.PALAVRAS["animais"])
        self.assertEqual(J.forca_mascara({"palavra": "pao de", "letras": ["a"]}), "_ a _  /  _ _")

    def test_ppt_aprende(self):
        rng = random.Random(5)
        hist, ganhei = [], 0
        for _ in range(40):
            eu = J.ppt_jogada(hist, rng)
            hist.append("pedra")                              # jogador previsível
            ganhei += J.ppt_resultado("pedra", eu) == "eu"
        self.assertGreater(ganhei, 25)
        self.assertEqual(J.ppt_ler("vou de tesoura"), "tesoura")
        self.assertEqual(J.ler_numero("quarenta e 2"), 2)
        self.assertEqual(J.ler_numero("cinco"), 5)


class TestJogosVoz(_Isolado):
    def test_fluxos(self):
        self.assertIn("você é o X", jogos.run({"action": "novo", "jogo": "jogo da velha"}))
        r = jogos.run({"action": "velha", "posicao": "centro"})
        self.assertIn("Eu joguei na", r)
        self.assertIn("ocupada", jogos.run({"action": "velha", "posicao": "5"}))
        self.assertIn("coluna", jogos.run({"action": "lig4"}))
        self.assertIn("Joguei na coluna", jogos.run({"action": "lig4", "coluna": "4"}))
        self.assertIn("Diga uma letra", jogos.run({"action": "forca", "tema": "frutas"}))
        self.assertIn("vidas", jogos.run({"action": "forca", "chute": "a"}))
        self.assertIn("Pensei", jogos.run({"action": "adivinha", "nivel": "facil"}))
        d = json.loads(jogos.ARQ.read_text(encoding="utf-8"))
        alvo = d["adivinha"]["alvo"]
        self.assertIn("Maior" if alvo > 1 else "Acertou", jogos.run({"action": "adivinha", "numero": "1"}))
        self.assertIn("Acertou", jogos.run({"action": "adivinha", "numero": str(alvo)}))
        self.assertIn("Placar: você", jogos.run({"action": "ppt", "escolha": "papel"}))
        self.assertIn("Adivinha o número", jogos.run({"action": "placar"}))

    def test_qual_jogo(self):
        self.assertEqual(jogos.qual_jogo("abre o campo minado"), "minas")
        self.assertEqual(jogos.qual_jogo("Cobrinha"), "cobrinha")
        self.assertEqual(jogos.qual_jogo("pedra papel e tesoura"), "ppt")
        self.assertEqual(jogos.qual_jogo("nada"), "")


class TestServidorArcade(_Isolado):
    def setUp(self):
        super().setUp()
        self.url = _arcade.iniciar()
        self.base = self.url.split("/?")[0]

    def tearDown(self):
        _arcade.parar()
        super().tearDown()

    def _pedir(self, caminho, corpo=None, token=True):
        url = self.base + caminho + (f"?t={_arcade.TOKEN}" if token else "")
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(url, data=dados, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read()

    def test_pagina_e_token(self):
        self.assertIn(b"ARCADE J.A.R.V.I.S", self._pedir("/"))
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._pedir("/api/xadrez", token=False)
        self.assertEqual(ctx.exception.code, 403)

    def test_xadrez_e_damas_pela_api(self):
        e = json.loads(self._pedir("/api/xadrez/novo", {"nivel": "facil", "voce": "brancas"}))
        self.assertEqual(len(e["legais"]), 20)
        e = json.loads(self._pedir("/api/xadrez/lance", {"de": 12, "para": 28}))
        self.assertNotIn("erro", e)
        self.assertEqual(e["vez"], "w")
        self.assertIn("Você: peão para e4", e["fala"])
        self.assertIn("erro", json.loads(self._pedir("/api/xadrez/lance", {"de": 0, "para": 40})))
        self.assertEqual(xd.run({"action": "tabuleiro"}), "O tabuleiro está no painel.")     # mesma partida por voz
        e = json.loads(self._pedir("/api/damas/novo", {"nivel": "facil"}))
        self.assertEqual(len(e["legais"]), 7)
        e = json.loads(self._pedir("/api/damas/lance", {"casas": [[2, 2], [3, 3]]}))
        self.assertIn("Você: c3 d4", e["fala"])
        self.assertFalse(json.loads(self._pedir("/api/xadrez"))["ativo"])

    def test_placar(self):
        self._pedir("/api/placar", {"jogo": "cobrinha", "pontos": 120})
        self._pedir("/api/placar", {"jogo": "cobrinha", "pontos": 80})
        p = json.loads(self._pedir("/api/placar", {"jogo": "velha", "resultado": "vitoria"}))
        self.assertEqual(p["cobrinha"]["recorde"], 120)
        self.assertEqual(p["velha"]["vitorias"], 1)
        self.assertIn("recorde 120", jogos.texto_placar())


if __name__ == "__main__":
    unittest.main()
