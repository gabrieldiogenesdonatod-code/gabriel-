"""Testes da 3.9 — MINER AI: segurança, economia, cérebro, Stratum/SHA-256d (conferido com o bloco gênese e com uma
pool de mentira que confere cada share), controlador, painel e plugin do JARVIS."""
import hashlib
import importlib
import json
import os
import random
import shutil
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests.pool_falsa import PoolFalsa

from miner_ai import cerebro, config, economia, painel, seguranca as SEG, stratum_btc as S
from miner_ai import controlador as CT
from miner_ai.motor_btc import MotorBTC

BTC = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
XMR = "4" + "A" * 94


class Pasta(unittest.TestCase):
    """Cada teste com a sua pasta de dados do MINER AI."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch.object(config, "PASTA", self.tmp)
        p.start()
        self.addCleanup(p.stop)


# ─────────────────────────────────────────────────────────── segurança ───
class TestSeguranca(unittest.TestCase):
    def test_enderecos(self):
        for ok in ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", BTC, BTC.upper(),
                   "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"):
            self.assertTrue(SEG.btc_valido(ok), ok)
        for ruim in ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb", BTC[:-1] + "5", "bc1qW508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", "tb1qxyz",
                     "", XMR):
            self.assertFalse(SEG.btc_valido(ruim), ruim)
        self.assertTrue(SEG.xmr_valido(XMR))
        self.assertFalse(SEG.xmr_valido(BTC))

    def test_segredos_nunca(self):
        casos = {"5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ": "WIF", "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn": "WIF",
                 "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi": "xprv",
                 "a" * 64: "64 hexadecimais", "abandon ability able about above absent absorb abstract absurd abuse access accident": "frase",
                 "minha seed é tal": "frase"}
        for t, tipo in casos.items():
            self.assertIn(tipo, SEG.parece_segredo(t) or "", t)
        for limpo in (BTC, XMR, "tarifa 0,98", "22:00-07:00", "", "o bitcoin está caro hoje"):
            self.assertIsNone(SEG.parece_segredo(limpo), limpo)

    def test_celular_nao_minera(self):
        for var in ("JARVIS_ANDROID", "TERMUX_VERSION", "ANDROID_ROOT"):
            with mock.patch.dict(os.environ, {var: "1"}):
                self.assertFalse(SEG.pode_minerar()[0])
        self.assertEqual(SEG.mascarar(BTC), "bc1qw5…v8f3t4")


class TestConfig(Pasta):
    def test_valida_converte_e_nunca_guarda_segredo(self):
        cfg, erros = config.alterar({"carteira_btc": BTC, "tarifa": "0,98", "economico": "não", "horarios": "22:00-07:00; 12:00-13:00",
                                     "cpu_max": "40", "xyz": "1"})
        self.assertEqual((cfg["carteira_btc"], cfg["tarifa"], cfg["economico"], cfg["horarios"], cfg["cpu_max"]),
                         (BTC, 0.98, False, ["22:00-07:00", "12:00-13:00"], 40))
        self.assertEqual(erros, ["não conheço o ajuste 'xyz'"])
        _, erros = config.alterar({"carteira_btc": "KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn"})
        self.assertIn("NUNCA guardo", erros[0])
        _, erros = config.alterar({"carteira_xmr": "4abc"})
        self.assertIn("endereço inválido", erros[0])
        bruto = (self.tmp / "config.json").read_text(encoding="utf-8")
        self.assertNotIn("KwDiBf89", bruto)
        self.assertEqual(config.carregar()["carteira_btc"], BTC)


# ─────────────────────────────────────────────────────────── economia ───
class TestEconomia(unittest.TestCase):
    def test_horarios(self):
        h = lambda hh, mm=0: datetime(2026, 11, 18, hh, mm)                  # noqa: E731
        self.assertTrue(economia.no_horario([], h(15)))
        self.assertTrue(economia.no_horario(["22:00-07:00"], h(23)))
        self.assertTrue(economia.no_horario(["22:00-07:00"], h(6, 59)))
        self.assertFalse(economia.no_horario(["22:00-07:00"], h(7)))
        self.assertFalse(economia.no_horario(["22:00-07:00"], h(12)))
        self.assertTrue(economia.no_horario(["lixo", "12:00-13:30"], h(13, 15)))

    def test_regulagem_pela_temperatura(self):
        self.assertEqual(economia.regular(40, None, 80, 50), (40, ""))
        self.assertEqual(economia.regular(40, 81, 80, 50)[0], 0.0)
        c, aviso = economia.regular(40, 76, 80, 50)
        self.assertEqual(c, 30.0)
        self.assertIn("reduzi", aviso)
        self.assertEqual(economia.regular(30, 60, 80, 50)[0], 35.0)
        self.assertEqual(economia.regular(48, 60, 80, 50)[0], 50.0)               # nunca passa do limite de CPU
        self.assertEqual(economia.regular(40, 72, 80, 50)[0], 40)                 # zona neutra

    def test_decidir_e_watts(self):
        base = {"horas_max": 8, "parar_na_bateria": True, "horarios": [], "economico": True, "ocioso_min": 5}
        agora = datetime(2026, 11, 18, 23)
        self.assertEqual(economia.decidir(base, agora, True, 999, 1), (True, ""))
        self.assertEqual(economia.decidir(base, agora, False, 999, 1)[1], "na bateria")
        self.assertIn("usando o PC", economia.decidir(base, agora, True, 10, 1)[1])
        self.assertTrue(economia.decidir(base, agora, True, None, 1)[0])            # Linux não sabe: não bloqueia
        self.assertIn("fora do horário", economia.decidir({**base, "horarios": ["01:00-05:00"]}, agora, True, 999, 1)[1])
        self.assertIn("limite de 8 h", economia.decidir(base, agora, True, 999, 8)[1])
        self.assertEqual(economia.threads_padrao(8, True), 1)
        self.assertEqual(economia.threads_padrao(8, False), 4)
        self.assertEqual(economia.carga_padrao({"economico": True, "cpu_max": 80}), 30.0)
        w = economia.watts_estimados({"tdp_watts": 15}, 2, 50, 8)
        self.assertAlmostEqual(w, 15 * 2 / 8 * 0.5 * 1.6)
        self.assertAlmostEqual(economia.watts_estimados({"watts_medidos": 20}, 2, 50, 8), 10.0)    # medido vale mais
        self.assertAlmostEqual(economia.kwh(1000, 3600), 1.0)


# ─────────────────────────────────────────────────────────── cérebro ───
class TestCerebro(unittest.TestCase):
    def test_bitcoin_e_loteria_e_monero_nao_compensa(self):
        btc = cerebro.rentabilidade("btc", 1.5e6, 1.3e14, 520000, 5, 0.95)
        self.assertEqual(btc["tipo"], "simulacao")
        self.assertFalse(btc["compensa"])
        self.assertGreater(btc["anos_por_bloco"], 1e9)
        self.assertIn("LOTERIA", cerebro.veredito(btc))
        self.assertIn("bilhões de anos", cerebro.veredito(btc))
        xmr = cerebro.rentabilidade("xmr", 1200, 6e11, 1650, 30, 0.95)
        self.assertAlmostEqual(xmr["moedas_dia"], 1200 * 86400 / 6e11 * 0.6)
        self.assertIn("NÃO compensa", cerebro.veredito(xmr))
        farm = cerebro.rentabilidade("xmr", 5e6, 6e11, 1650, 30, 0.95)
        self.assertTrue(farm["compensa"])
        self.assertIn("Pode mudar", cerebro.veredito(farm))
        sem = cerebro.rentabilidade("xmr", 1200, 6e11, None, 30, 0.95)
        self.assertIsNone(sem["compensa"])
        self.assertIn("sem preço", cerebro.veredito(sem))

    def test_aprende_com_o_historico(self):
        h = [{"motor": "btc", "threads": 2, "carga": 50, "hs": 700000 + i, "watts": 6, "temp": 60} for i in range(3)]
        self.assertAlmostEqual(cerebro.hashrate_aprendido(h, "btc", 2, 100), 1400001, delta=2)
        self.assertIsNone(cerebro.hashrate_aprendido(h[:2], "btc", 2, 50))               # pouca prova
        h += [{"motor": "btc", "threads": 4, "carga": 100, "hs": 4.0e6, "watts": 30, "temp": 78} for _ in range(3)]   # quente
        h += [{"motor": "btc", "threads": 1, "carga": 100, "hs": 1.4e6, "watts": 6, "temp": 65} for _ in range(3)]
        m = cerebro.melhor_configuracao(h, "btc", 80)
        self.assertEqual((m["threads"], m["carga"]), (1, 100))
        self.assertEqual(cerebro.hashrate_para("btc", {}, h, 1, 100), (1.4e6, True))
        self.assertEqual(cerebro.hashrate_para("xmr", {}, h, 2, 100), (600.0, False))

    def test_recomendacoes(self):
        sims = {"btc": cerebro.rentabilidade("btc", 1e6, 1.3e14, 520000, 5, 0.95),
                "xmr": cerebro.rentabilidade("xmr", 1200, 6e11, 1650, 30, 0.95)}
        d = " ".join(cerebro.recomendar({"temperatura_max": 90}, [], sims))
        for trecho in ("nenhuma moeda compensa", "Monero (pelo XMRig) rende", "medidor de tomada", "22:00-07:00", "85 °C"):
            self.assertIn(trecho, d)
        sem_preco = {"btc": cerebro.rentabilidade("btc", 1e6, 1.3e14, None, 5, 0.95)}
        d = " ".join(cerebro.recomendar({}, [], sem_preco))
        self.assertIn("Sem preço agora", d)
        self.assertNotIn("nenhuma moeda compensa", d)                         # sem dado, não conclui nada


# ─────────────────────────────────────────────────────────── Stratum e SHA-256d ───
class TestStratum(unittest.TestCase):
    def test_bloco_genese(self):
        raiz = bytes.fromhex("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b")[::-1]
        pref = S.prefixo_cabecalho("00000001", S.trocar_palavras("00" * 32).hex(), raiz, format(1231006505, "08x"), "1d00ffff")
        h = S.hash_do_nonce(pref, 2083236893)
        self.assertEqual(S.hash_exibicao(h), "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")
        self.assertLessEqual(S.valor(h), S.alvo_do_nbits("1d00ffff"))
        achados, n = S.procurar(pref, 2083236893 - 50, 100, S.alvo_do_nbits("1d00ffff"))
        self.assertEqual(([a for a, _ in achados], n), ([2083236893], 100))
        self.assertEqual(S.procurar(pref, 0xFFFFFFF0, 100, 0)[1], 16)              # não passa do último nonce

    def test_merkle_igual_a_arvore_inteira(self):
        rnd = random.Random(5)
        for qtd in (1, 2, 3, 5, 8):
            coinb1, ex1, ex2, coinb2 = "01" * 40, "f000000f", "00000007", "02" * 30
            txs = [S.sha256d(bytes.fromhex(coinb1 + ex1 + ex2 + coinb2))] + [rnd.randbytes(32) for _ in range(qtd - 1)]
            nivel, ramos, idx = list(txs), [], 0
            while len(nivel) > 1:                                                     # caminho da coinbase (índice 0)
                if len(nivel) % 2:
                    nivel.append(nivel[-1])
                ramos.append(nivel[1].hex())
                nivel = [S.sha256d(nivel[i] + nivel[i + 1]) for i in range(0, len(nivel), 2)]
            self.assertEqual(S.raiz_merkle(coinb1, ex1, ex2, coinb2, ramos), nivel[0], qtd)

    def test_alvos_e_nonce(self):
        self.assertEqual(S.alvo_da_dificuldade(1), S.DIF1)
        self.assertEqual(S.alvo_da_dificuldade(0), S.MAX_ALVO)
        self.assertEqual(S.alvo_da_dificuldade(2), S.DIF1 // 2)
        self.assertEqual(S.alvo_do_nbits("1d00ffff"), S.DIF1)
        self.assertEqual(S.nonce_hex(1), "00000001")
        self.assertEqual(S.trocar_palavras("0011223344556677").hex(), "3322110077665544")


class TestMotorBTCNaPool(unittest.TestCase):
    def test_minera_de_verdade_e_a_pool_confere(self):
        pool = PoolFalsa(0.0002)
        self.addCleanup(pool.fechar)
        m = MotorBTC({"pool_btc": f"127.0.0.1:{pool.porta}", "carteira_btc": BTC, "nome_maquina": "teste"})
        self.addCleanup(m.parar)
        m.iniciar(2, 60)
        fim = time.time() + 40
        while time.time() < fim and len(pool.aceitos) < 3:
            time.sleep(0.5)
        self.assertGreaterEqual(len(pool.aceitos), 3)
        self.assertEqual(pool.recusados, [])                                     # cada share conferido de forma independente
        self.assertEqual(pool.usuarios, [f"{BTC}.teste"])                        # o seu endereço público é o usuário
        time.sleep(1)
        self.assertEqual(m.metricas()["shares_aceitos"], len(pool.aceitos))
        self.assertTrue(m.metricas()["conectado"])
        m.pausar()
        time.sleep(4)
        antes = m.hashes_total
        time.sleep(4.5)
        self.assertEqual(m.hashes_total, antes)                                  # pausado = zero conta

    def test_limite_de_cpu_funciona(self):
        pool = PoolFalsa(1e6)                                        # dificuldade alta: sem shares, só conta hash
        self.addCleanup(pool.fechar)
        m = MotorBTC({"pool_btc": f"127.0.0.1:{pool.porta}", "carteira_btc": BTC})
        self.addCleanup(m.parar)
        m.iniciar(1, 100)
        time.sleep(3)
        a = m.hashes_total
        time.sleep(6.2)
        cheio = m.hashes_total - a
        m.definir_carga(20)
        time.sleep(2.5)
        b = m.hashes_total
        time.sleep(6.2)
        leve = m.hashes_total - b
        self.assertGreater(cheio, 0)
        self.assertLess(leve, cheio * 0.5)                                        # 20% de CPU faz bem menos conta

    def test_pool_recusa_usuario(self):
        pool = PoolFalsa(0.0002, usuario_ok=lambda u: False)
        self.addCleanup(pool.fechar)
        logs = []
        m = MotorBTC({"pool_btc": f"127.0.0.1:{pool.porta}", "carteira_btc": BTC}, log=logs.append)
        self.addCleanup(m.parar)
        m.iniciar(1, 30)
        time.sleep(2)
        self.assertFalse(m.metricas()["autorizado"])
        self.assertTrue(any("recusou" in x for x in logs))


# ─────────────────────────────────────────────────────────── controlador ───
class MotorFalso:
    nome, moeda = "btc", "btc"

    def __init__(self, cfg, log=print):
        self.pausado, self.cargas, self.threads, self.carga, self.morto = False, [], 1, 30, False
        self.hashes_total = 0

    def iniciar(self, threads, carga):
        self.threads, self.carga = threads, carga

    def pausar(self):
        self.pausado = True

    def retomar(self):
        self.pausado = False

    def definir_carga(self, c):
        self.carga = c
        self.cargas.append(c)

    def parar(self):
        pass

    def vivo(self):
        return not self.morto

    def hashrate(self):
        return 0.0 if self.pausado else 1.0e6

    def metricas(self):
        return {"motor": "btc", "moeda": "btc", "hashrate": self.hashrate(), "threads": self.threads, "carga": self.carga,
                "pausado": self.pausado, "conectado": True, "autorizado": True, "dificuldade_pool": 1.0, "shares_aceitos": 4,
                "shares_rejeitados": 0, "blocos": 0, "candidatos_bloco": 0, "ultimo_share": None, "hashes_total": self.hashes_total,
                "erros": [], "vivo": self.vivo()}


class TestControlador(Pasta):
    def novo(self, **sens):
        self.relogio = [1_800_000_000.0]
        self.sens = {"temperatura": lambda: self.temp, "na_tomada": lambda: self.tomada, "ocioso": lambda: None,
                     "agora": lambda: self.relogio[0]}
        self.temp, self.tomada, self.avisos = 60.0, True, []
        ctl = CT.Controlador(log=lambda *a: None, avisar=self.avisos.append, motores={"btc": MotorFalso}, sensores=self.sens)
        ctl._laco = lambda: None
        mock.patch.object(CT.rede, "precos_brl", return_value={"bitcoin": 520000.0, "monero": 1650.0}).start()
        mock.patch.object(CT.rede, "dificuldade", return_value={"valor": 1.3e14, "fonte": "t", "ts": 0}).start()
        mock.patch.object(CT.rede, "saldo_btc", return_value={"confirmado": 0.0001, "pendente": 0.0, "fonte": "blockstream.info", "ts": 1}).start()
        self.addCleanup(mock.patch.stopall)
        return ctl

    def passar(self, ctl, s):
        self.relogio[0] += s
        ctl.ultimo_temp = 0
        ctl.tick()

    def test_recusa_sem_endereco_no_celular_e_duplicado(self):
        ctl = self.novo()
        self.assertIn("endereço PÚBLICO de Bitcoin", ctl.iniciar("btc")[1])
        config.alterar({"carteira_btc": BTC})
        with mock.patch.dict(os.environ, {"JARVIS_ANDROID": "1"}):
            self.assertIn("no celular", ctl.iniciar("btc")[1])
        self.tomada = False
        self.assertIn("na bateria", ctl.iniciar("btc")[1])
        self.tomada = True
        self.assertTrue(ctl.iniciar("btc")[0])
        self.assertIn("já está minerando", ctl.iniciar("btc")[1])

    def test_regras_de_economia_energia_e_estado_rotulado(self):
        ctl = self.novo()
        config.alterar({"carteira_btc": BTC, "economico": "nao", "cpu_max": "60", "tarifa": "1", "tdp_watts": "15", "horas_max": "2"})
        with mock.patch.object(CT.cerebro, "nucleos", return_value=4):
            self.assertTrue(ctl.iniciar("btc")[0])
            ctl.atualizar_mercado()
            self.passar(ctl, 5)
            w = ctl.watts
            self.assertAlmostEqual(w, 15 * 2 / 4 * 0.6 * 1.6)
            self.passar(ctl, 3600)
            self.assertAlmostEqual(ctl.kwh, w / 1000, places=6)                   # 1 h com w watts
            self.assertAlmostEqual(ctl.custo, ctl.kwh * 1.0)
            self.temp = 77                                                          # perto do limite: reduz
            self.passar(ctl, 5)
            self.assertEqual(ctl.motor.cargas[-1], 45.0)
            self.temp = 81                                                          # passou: pausa
            self.passar(ctl, 5)
            self.assertTrue(ctl.motor.pausado)
            self.assertIn("81 °C", self.avisos[-1])
            self.temp = 60
            self.passar(ctl, 5)
            self.assertFalse(ctl.motor.pausado)
            self.tomada = False
            self.passar(ctl, 5)
            self.assertIn("na bateria", ctl.estado()["desempenho"]["motivo_pausa"])
            kwh = ctl.kwh
            self.passar(ctl, 600)
            self.passar(ctl, 600)
            self.assertAlmostEqual(ctl.kwh, kwh, places=9)                          # pausado não gasta
            self.tomada = True
            self.passar(ctl, 5)
            e = ctl.estado()
            self.assertEqual(set(e) >= {"real", "confirmado", "pendente", "simulacao", "custos", "resultado_estimado"}, True)
            self.assertEqual(e["real"]["shares_aceitos"], 4)
            self.assertEqual((e["confirmado"]["valor"], e["confirmado"]["fonte"]), (0.0001, "blockstream.info"))
            self.assertIn("não é dinheiro", e["simulacao"]["aviso"])
            self.assertIn("ESPERADO", e["resultado_estimado"]["o_que_e"])
            self.assertEqual(e["endereco"], "bc1qw5…v8f3t4")
            self.assertTrue(config.ler_json("historico.json", []))                 # aprendeu com o tempo minerando

    def test_limite_de_horas_e_sessao(self):
        ctl = self.novo()
        config.alterar({"carteira_btc": BTC, "horas_max": "1"})
        ctl.iniciar("btc")
        with mock.patch.object(CT.threading, "Thread") as th:
            self.passar(ctl, 3700)
        alvo = th.call_args.kwargs.get("target") or th.call_args[1].get("target")
        self.assertEqual(alvo, ctl._parar_e_avisar)
        ctl._parar_e_avisar("limite de 1 h")
        self.assertIn("MINER AI parado (limite de 1 h)", self.avisos[-1])
        s = config.ler_json("sessoes.json", [])[-1]
        self.assertEqual((s["moeda"], s["shares"], s["motivo"]), ("btc", 4, "limite de 1 h"))
        self.assertIn("não está minerando", ctl.parar())


# ─────────────────────────────────────────────────────────── painel ───
class TestPainel(Pasta):
    def test_pagina_api_e_token(self):
        ctl = CT.Controlador(log=lambda *a: None, motores={"btc": MotorFalso})
        with mock.patch.object(CT.rede, "precos_brl", return_value={}), mock.patch.object(CT.rede, "dificuldade", return_value=None):
            painel.parar()
            url = painel.iniciar(ctl, porta=0)
            self.addCleanup(painel.parar)
            h = urllib.request.urlopen(url).read().decode()
            self.assertIn(painel.TOKEN, h)
            self.assertIn("SIMULAÇÃO", h)
            e = json.loads(urllib.request.urlopen(url + "api/estado").read())     # JSON válido (sem infinito)
            self.assertFalse(e["rodando"])
            self.assertIsNone(e["confirmado"]["valor"])
            with self.assertRaises(urllib.error.HTTPError) as erro:
                urllib.request.urlopen(urllib.request.Request(url + "api/acao", data=b'{"acao":"parar"}', method="POST"))
            self.assertEqual(erro.exception.code, 403)
            r = urllib.request.urlopen(urllib.request.Request(url + "api/acao", data=b'{"acao":"pausar"}', method="POST",
                                                              headers={"X-Token": painel.TOKEN}))
            self.assertIn("não está minerando", json.loads(r.read())["resposta"])


# ─────────────────────────────────────────────────────────── plugin do JARVIS ───
class TestPluginMinerAI(Pasta):
    def setUp(self):
        super().setUp()
        global PM
        PM = importlib.import_module("plugins.miner_ai")
        self.ctl = CT.Controlador(log=lambda *a: None, motores={"btc": MotorFalso})
        self.ctl._laco = lambda: None
        for m in (mock.patch.object(PM, "_ctl", return_value=self.ctl), mock.patch.object(CT.rede, "precos_brl", return_value={"bitcoin": 5e5}),
                  mock.patch.object(CT.rede, "dificuldade", return_value=None), mock.patch.object(CT.rede, "saldo_btc", return_value=None),
                  mock.patch.object(CT.Controlador, "problemas", lambda s, m: [] if config.carregar().get("carteira_btc") else ["falta"])):
            m.start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(lambda: self.ctl.motor and self.ctl.parar())

    def test_ajustes_e_moedas(self):
        self.assertEqual(PM.ler_ajustes("carteira bitcoin = bc1qabc, tarifa=0,98; modo econômico: sim, cpu=30"),
                         {"carteira_btc": "bc1qabc", "tarifa": "0,98", "economico": "sim", "cpu_max": "30"})
        self.assertEqual([PM.moeda_de(x) for x in ("no bitcoin", "monero", "XMR", "biticoin", "nada")], ["btc", "xmr", "xmr", "btc", None])

    def test_fluxo(self):
        self.assertIn("NUNCA me diga", PM.run({"action": "configurar", "ajustes": "minha seed é abandon ability"}))
        self.assertFalse((self.tmp / "config.json").exists() and "abandon" in (self.tmp / "config.json").read_text())
        self.assertIn("Guardei: carteira_btc, tarifa", PM.run({"action": "configurar", "ajustes": f"carteira_btc={BTC}, tarifa=0,98"}))
        self.assertIn("bc1qw5…v8f3t4", PM.run({"action": "configurar"}))
        self.assertIn("LOTERIA", PM.run({"action": "calcular", "moeda": "bitcoin"}))
        pedidos = []
        with mock.patch("core.confirm.request", lambda k, t, d, run: pedidos.append((t, d, run)) or "confirme na tela"):
            self.assertEqual(PM.run({"action": "iniciar", "moeda": "bitcoin"}), "confirme na tela")
        titulo, detalhe, ligar = pedidos[0]
        self.assertIn("Bitcoin de verdade", titulo)
        self.assertIn("LOTERIA", detalhe)                                           # a tela mostra a verdade antes de ligar
        self.assertIsNone(self.ctl.motor)                                          # só liga com o sim
        with mock.patch.object(PM._comum, "abrir_no_sistema", lambda *a: True):
            self.assertIn("minerando Bitcoin de verdade", ligar())
        self.assertIn("Real: 4 share(s)", PM.run({"action": "estado"}))
        self.assertIn("Pausado", PM.run({"action": "pausar"}))
        self.assertIn("MINER AI parado", PM.run({"action": "parar"}))
        self.assertIn("1 sessão(ões)", PM.run({"action": "sessoes"}))

    def test_niveis_e_busca(self):
        from core import registro_ferramentas, verificacao as V
        from plugins import catalogo
        self.assertEqual(V.nivel_de("miner_ai", {"action": "iniciar"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("miner_ai", {"action": "calcular"}), V.LIVRE)
        self.assertLessEqual(len(PM.PLUGIN["brief"]), 150)
        decls = registro_ferramentas.declaracoes()
        erros = [q for q in ("inicia o miner ai no bitcoin", "abre o painel do miner ai", "o miner ai compensa")
                 if "miner_ai" not in [d["name"] for d in catalogo.buscar(decls, q, 3)]]
        self.assertEqual(erros, [])


class TestSemDependencias(unittest.TestCase):
    def test_so_biblioteca_padrao(self):
        import ast
        import sys
        for arq in (Path(cerebro.__file__).parent).glob("*.py"):
            for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
                if isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
                    raiz = no.module.split(".")[0]
                elif isinstance(no, ast.Import):
                    raiz = no.names[0].name.split(".")[0]
                else:
                    continue
                self.assertTrue(raiz in sys.stdlib_module_names or raiz in ("miner_ai", "psutil"), f"{arq.name}: {raiz}")
        self.assertNotIn("hashlib.new", Path(S.__file__).read_text(encoding="utf-8"))
        self.assertTrue(hashlib.sha256)


if __name__ == "__main__":
    unittest.main()
