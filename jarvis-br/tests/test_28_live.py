"""
Testes da 2.5 — conversa em grupo (quem está falando), avatar de live,
holograma na mão e intérprete presencial. Vozes sintéticas, sessão do Gemini
simulada; nada de microfone, câmera ou rede (fora 127.0.0.1).
"""
import asyncio
import json
import time
import types as T
import unittest
import urllib.request
from unittest import mock

import numpy as np

from plugins import _vozes as V
from tests import TMP

VOGAIS = [(700, 1200, 2500), (300, 2300, 3000), (500, 900, 2400), (450, 1800, 2600), (350, 800, 2300)]


def vogal(t, f0, formantes, amp=3000.0):
    s = np.zeros_like(t)
    for h in range(1, int(4000 / f0)):
        f = h * f0
        s += (sum(np.exp(-((f - F) / 110.0) ** 2) for F in formantes) + 0.03) * np.sin(2 * np.pi * f * t + h)
    return amp * s / (np.sqrt(np.mean(s ** 2)) + 1e-9)


def fala(f0, escala, seed, dur=2.0):
    """Uma "voz" sintética: vogais com formantes, tom (f0) e tamanho de trato (escala) da pessoa."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * 16000)) / 16000
    out = np.zeros_like(t)
    for k, i in enumerate(rng.integers(0, len(VOGAIS), 8)):
        m = (t >= k * dur / 8) & (t < (k + 1) * dur / 8)
        out[m] = vogal(t[m], f0 * (1 + 0.03 * rng.standard_normal()), [F * escala for F in VOGAIS[i]])
    return np.clip(out + rng.normal(0, 60, t.size), -32000, 32000).astype(np.int16)


class TestQuemFala(unittest.TestCase):
    def setUp(self):
        V.PASTA = TMP / "vozes"

    def test_separador_entrega_um_trecho_por_fala(self):
        sep = V.Separador()
        ts, saidas = 0.0, []
        for sinal in (fala(115, 1.0, 5, 3.0), fala(215, 1.18, 6, 1.0)):
            for i in range(0, len(sinal) - 1024, 1024):
                r = sep.bloco(ts, sinal[i:i + 1024])
                ts += 0.064
                if r is not None:
                    saidas.append(round(len(r) / 16000, 1))
            for _ in range(15):
                r = sep.bloco(ts, np.zeros(1024, np.int16))
                ts += 0.064
                if r is not None:
                    saidas.append(round(len(r) / 16000, 1))
        self.assertEqual(len(saidas), 2)                  # a fala longa (assim que tem 1,2 s) e a curta (no fim)
        self.assertIsNone(sep.bloco(ts, fala(115, 1.0, 7, 0.5)[:1024], jarvis_falando=True))

    def test_reconhece_pelo_timbre(self):
        with mock.patch.object(V, "motor", lambda: "timbre"):
            V.salvar("Rafael", [V.timbre(fala(115, 1.0, s)) for s in (1, 2, 3)], "timbre")
            V.salvar("Maria", [V.timbre(fala(215, 1.18, s)) for s in (1, 2, 3)], "timbre")
            perfis, raios = V.perfis("timbre"), V.raios("timbre")
        self.assertEqual(V.identificar(V.timbre(fala(118, 1.0, 20)), perfis, "timbre", raios)[0], "Rafael")
        self.assertEqual(V.identificar(V.timbre(fala(210, 1.18, 21)), perfis, "timbre", raios)[0], "Maria")
        self.assertIsNone(V.identificar(None, perfis, "timbre")[0])
        self.assertTrue(V.esquecer("Maria"))
        self.assertEqual(V.nomes(), ["Rafael"])

    def test_resemblyzer_por_semelhanca(self):
        a, b = np.eye(4)[0], np.eye(4)[1]
        self.assertEqual(V.identificar(a * 0.9 + b * 0.1, {"A": a, "B": b}, "resemblyzer")[0], "A")
        self.assertIsNone(V.identificar(a + b, {"A": a, "B": b}, "resemblyzer")[0])      # empate: não chuta

    def test_notas_na_conversa(self):
        from plugins import conversa_grupo as G
        self.assertTrue(G.decidir_nota("Maria", "Rafael", 5, 999))
        self.assertFalse(G.decidir_nota("Maria", "Maria", 30, 999))
        self.assertTrue(G.decidir_nota("Maria", "Maria", 120, 999))
        self.assertFalse(G.decidir_nota(None, "Maria", 5, 10))
        self.assertIn("Maria", G.frase_nota("Maria"))
        with mock.patch.object(V, "motor", lambda: "timbre"):
            V.salvar("Rafael", [V.timbre(fala(115, 1.0, s)) for s in (1, 2, 3)], "timbre")
            V.salvar("Maria", [V.timbre(fala(215, 1.18, s)) for s in (1, 2, 3)], "timbre")
            notas = []

            class App:
                def nota_contexto(self, t):
                    notas.append(t)
                    return True
            with mock.patch.object(G, "_app", lambda: App()), mock.patch("core.escuta.inscrever", lambda f: None), \
                    mock.patch("core.escuta.desinscrever", lambda f: None):
                self.assertIn("ligado", G.run({"action": "ligar"}))
                ts = 0.0
                for f0, esc, seed in ((115, 1.0, 30), (115, 1.0, 31), (215, 1.18, 32)):
                    sinal = fala(f0, esc, seed, 2.0)
                    for i in range(0, len(sinal) - 1024, 1024):
                        G._ouvir(ts, sinal[i:i + 1024], False, False)
                        ts += 0.064
                    for _ in range(15):
                        G._ouvir(ts, np.zeros(1024, np.int16), False, False)
                        ts += 0.064
                    for _ in range(40):
                        if G._fila.empty():
                            break
                        time.sleep(0.05)
                    time.sleep(0.3)
                G.run({"action": "desligar"})
        falas = [n for n in notas if n.startswith("[Conversa em grupo] Quem")]
        self.assertEqual(falas, ["[Conversa em grupo] Quem está falando agora: Rafael.",
                                 "[Conversa em grupo] Quem está falando agora: Maria."])


class TestAvatar(unittest.TestCase):
    def test_expressoes(self):
        from plugins import avatar_live as A
        self.assertEqual(A.expressao_do_texto("Parabéns, bateu a meta!"), "comemorar")
        self.assertEqual(A.expressao_do_texto("kkkkk que isso"), "rir")
        self.assertEqual(A.expressao_do_texto("Nossa, sério?"), "surpresa")
        self.assertIsNone(A.expressao_do_texto("A conta de luz vence sexta."))
        self.assertEqual(A.reacao_do_chat(["KEKW", "kkkkk", "oi"]), "rir")
        self.assertIsNone(A.reacao_do_chat(["kkkk", "boa noite"]))
        self.assertEqual(A.ler_irc(":fulano!fulano@fulano.tmi.twitch.tv PRIVMSG #canal :kkkk"), ("msg", "fulano", "kkkk"))
        sub = "@display-name=Ana;msg-id=sub :tmi.twitch.tv USERNOTICE #canal :valeu"
        self.assertEqual(A.ler_irc(sub)[:2], ("sub", "Ana"))

    def test_servidor_e_eventos(self):
        from plugins import avatar_live as A
        A.ARQ_CHAVE = TMP / "avatar.json"
        with mock.patch.object(A, "porta", lambda: 0), mock.patch.object(A, "_c", lambda: {"legenda": True,
                                                                                            "vendas": False}):
            self.assertEqual(A.ligar(), "")
            try:
                porta = A._estado["servidor"].server_address[1]
                A.reagir("comemorar", "Venda!")
                with urllib.request.urlopen(f"http://127.0.0.1:{porta}/avatar?k={A.chave()}", timeout=5) as r:
                    self.assertIn(b"EventSource", r.read())
                with urllib.request.urlopen(f"http://127.0.0.1:{porta}/avatar/eventos?k={A.chave()}", timeout=5) as r:
                    linha = r.readline().decode()
                e = json.loads(linha.split("data: ", 1)[1])
                self.assertEqual((e["expressao"], e["texto"]), ("comemorar", "Venda!"))
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(f"http://127.0.0.1:{porta}/avatar?k=errada", timeout=5)
            finally:
                A.desligar()


class TestHolograma(unittest.TestCase):
    def test_cartoes(self):
        from PIL import Image

        from plugins import holograma_mao as M
        foto = TMP / "colecao.jpg"
        Image.new("RGB", (64, 40), (30, 60, 90)).save(foto)
        c = M.montar_cartao("imagem", "Coleção nova", "12 peças", str(foto))
        self.assertTrue(c["imagem"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(M.montar_cartao("imagem", imagem=str(TMP / "nao_existe.jpg"))["imagem"], "")
        with mock.patch("plugins.briefing_br.clima", lambda *a: "28 °C"):
            self.assertEqual(M.montar_cartao("clima")["texto"], "28 °C")
        with mock.patch.object(M, "abrir", lambda: True):
            M.run({"action": "limpar"})
            self.assertIn("Coleção nova", M.run({"action": "mostrar", "tipo": "imagem", "titulo": "Coleção nova",
                                                 "imagem": str(foto)}))
        e = M.estado_tela()
        self.assertTrue(e["novo"])
        self.assertFalse(M.estado_tela()["novo"])
        self.assertEqual(len(e["cartoes"]), 1)


class TestInterprete(unittest.TestCase):
    def test_idioma_e_rota(self):
        from plugins import interprete as I
        self.assertEqual(I.idioma_do_texto("Quanto custa essa camiseta?")[0], "pt")
        self.assertEqual(I.idioma_do_texto("How much is this shirt?")[0], "en")
        self.assertEqual(I.idioma_do_texto("¿Cuánto cuesta esta camiseta?")[0], "es")
        self.assertEqual(I.decidir_rota("Quanto custa?", "How much is it"), "caixa")     # tradução em inglês → convidado
        self.assertEqual(I.decidir_rota("", "Eu quero duas, por favor"), "fone")         # português → seu fone
        self.assertIsNone(I.decidir_rota("", "ok"))
        self.assertEqual(I.decidir_rota("", "ok", forcar=True), "fone")
        devs = [{"name": "Alto-falantes (Realtek(R) Audio)", "max_output_channels": 2, "hostapi": 0},
                {"name": "Fones de ouvido (JBL Tune 510BT)", "max_output_channels": 2, "hostapi": 0},
                {"name": "Alto-falantes (Realtek(R) Audio)", "max_output_channels": 2, "hostapi": 2},
                {"name": "Microfone (Realtek)", "max_output_channels": 0, "hostapi": 0}]
        self.assertEqual(I.achar_saida(devs, "realtek", 2), 2)
        self.assertEqual(I.achar_saida(devs, "jbl", 0), 1)
        self.assertIsNone(I.achar_saida(devs, "microfone", 0))

    def test_sessao_manda_cada_fala_para_o_lugar_certo(self):
        from plugins import interprete as I

        def msg(data=None, ent=None, sai=None, fim=False):
            sc = T.SimpleNamespace(input_transcription=T.SimpleNamespace(text=ent) if ent else None,
                                   output_transcription=T.SimpleNamespace(text=sai) if sai else None,
                                   interrupted=False, turn_complete=fim)
            return T.SimpleNamespace(data=data, server_content=sc)
        turnos = [[msg(ent="Quanto custa essa camiseta?"), msg(data=b"\x01\x00" * 50), msg(sai="How much is"),
                   msg(data=b"\x02\x00" * 50), msg(sai=" this shirt?"), msg(fim=True)],
                  [msg(ent="It's fifty"), msg(data=b"\x03\x00" * 50), msg(sai="Custa cinquenta reais, por favor."),
                   msg(fim=True)]]
        sessao = I.Sessao("inglês", 0, 1)

        class Falsa:
            def __init__(self):
                self.i = 0

            async def receive(self):
                if self.i >= len(turnos):
                    sessao.parar.set()
                    return
                self.i += 1
                for m in turnos[self.i - 1]:
                    yield m
        with mock.patch.object(I, "registrar", lambda *a: None):
            asyncio.run(sessao._receber(Falsa()))
        self.assertEqual((sessao.filas["caixa"].qsize(), sessao.filas["fone"].qsize()), (2, 1))
        self.assertEqual([h[3] for h in sessao.historico], ["How much is this shirt?", "Custa cinquenta reais, por favor."])


if __name__ == "__main__":
    unittest.main()
