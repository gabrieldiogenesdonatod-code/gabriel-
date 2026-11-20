"""Testes da 3.7 — mineração (calculadora honesta + controle seguro do XMRig) e carteira de cripto."""
import importlib
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests.test_52_v33 import trocar

CARTEIRA = "4" + "A" * 94


class Base(unittest.TestCase):
    def setUp(self):
        global M, C, L
        M = importlib.import_module("plugins.mineracao")
        C = importlib.import_module("plugins.carteira_cripto")
        L = importlib.import_module("core.livro_razao")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(L.fechar)
        L.fechar()
        self.falas = []
        for nome, attr, valor in (("plugins._lote2", "PASTA", self.tmp / "lote2"),
                                  ("core.livro_razao", "ARQ", self.tmp / "livro.db"), ("core.livro_razao", "CHAVE", self.tmp / "livro.key"),
                                  ("plugins._comum", "avisar", lambda pl, t, e="": self.falas.append(t)),
                                  ("plugins._comum", "mostrar", lambda *a, **k: None),
                                  ("plugins.mineracao", "precos", lambda ids: {i: {"monero": 1500.0, "bitcoin": 500000.0}.get(i, 10.0) for i in ids}),
                                  ("plugins.mineracao", "dificuldade", lambda k: ((1.3e14 if k == "btc" else 6e11), False)),
                                  ("plugins.mineracao", "na_tomada", lambda: True),
                                  ("plugins.mineracao", "temperatura", lambda: None),
                                  ("plugins.mineracao", "no_celular", lambda: False)):
            trocar(self, nome, attr, valor)
        M._proc.update(p=None)
        self.addCleanup(M._proc.update, {"p": None})


class TestContas(unittest.TestCase):
    def setUp(self):
        global M
        M = importlib.import_module("plugins.mineracao")

    def test_formulas(self):
        self.assertAlmostEqual(M.ganho_dia(1200, 6e11, 0.6), 1200 * 86400 / 6e11 * 0.6)
        self.assertEqual(M.ganho_dia(0, 6e11, 0.6), 0.0)
        self.assertAlmostEqual(M.custo_dia(30, 0.95), 0.684)
        self.assertGreater(M.anos_por_bloco(1e7, 1.3e14, 2 ** 32), 1e9)        # bitcoin no processador: bilhões de anos
        self.assertEqual(M.fmt_anos(float("inf")), "nunca")
        self.assertEqual((M.threads_padrao(8), M.threads_padrao(1), M.threads_padrao(None)), (4, 1, 1))

    def test_carteira_e_comando(self):
        self.assertTrue(M.carteira_valida(CARTEIRA))
        self.assertTrue(M.carteira_valida("8" + "b" * 94 + "c" * 11))
        for ruim in ("", "4" + "A" * 93, "1" + "A" * 94, "4" + "0" * 94, "bc1qxyz"):
            self.assertFalse(M.carteira_valida(ruim), ruim)
        cmd = M.comando_xmrig({"xmrig": "C:/x/xmrig.exe", "pool": "pool.supportxmr.com:443", "carteira": CARTEIRA, "threads": 2, "tls": True}, "tok")
        texto = " ".join(cmd)
        for trecho in ("-t 2", "--cpu-priority 0", "--http-host 127.0.0.1", "--http-access-token tok", "--tls", "--coin monero"):
            self.assertIn(trecho, texto)
        self.assertNotIn("--background", texto)                                  # nunca escondido
        self.assertNotIn("--tls", " ".join(M.comando_xmrig({"xmrig": "x", "pool": "p:3333", "carteira": CARTEIRA}, "t")))

    def test_analise_diz_a_verdade(self):
        btc = M.analise("btc", 1e7, 1.3e14, 500000, 30, 0.95, False)
        self.assertFalse(btc["compensa"])
        self.assertLess(btc["reais_dia"], 0.01)
        f = M.frase(btc, False)
        self.assertIn("não compensa", f)
        self.assertIn("anos para achar um bloco", f)
        xmr = M.analise("xmr", 1200, 6e11, 1500, 30, 0.95, True)
        self.assertAlmostEqual(xmr["reais_dia"], M.ganho_dia(1200, 6e11, 0.6) * 1500)
        self.assertIn("medido", M.frase(xmr, True))
        self.assertIn("aproximada", M.frase(xmr, True))
        sonho = M.analise("xmr", 1e9, 6e11, 1500, 30, 0.95, False)               # se fosse uma fazenda inteira, compensaria
        self.assertTrue(sonho["compensa"])
        self.assertIn("Sobra", M.frase(sonho, False))


class TestCalculadora(Base):
    def test_calcular_moedas_e_tarifa(self):
        r = M.run({"action": "calcular", "moeda": "todas"})
        self.assertIn("Monero (XMR)", r)
        self.assertIn("Bitcoin (BTC)", r)
        self.assertIn("não compensa", r)
        self.assertIn("estimado", r)
        self.assertIn("Luz considerada: 30 W a R$ 0,95", r)
        r = M.run({"action": "calcular", "moeda": "ethereum e dogecoin"})
        self.assertIn("não se minera mais", r)
        self.assertIn("ASIC", r)
        self.assertNotIn("Monero", r)
        self.assertIn("R$ 1,10", M.run({"action": "calcular", "moeda": "monero", "tarifa": "1,10"}))
        self.assertIn("1,1", M.run({"action": "configurar"}).replace("R$ 1,10", "1,1"))
        self.assertIn("só ASIC", M.run({"action": "moedas"}))

    def test_sem_preco_avisa(self):
        trocar(self, "plugins.mineracao", "precos", lambda ids: {})
        self.assertIn("não consegui o preço", M.run({"action": "calcular", "moeda": "bitcoin"}))


class TestControle(Base):
    def configurar(self):
        exe = self.tmp / "xmrig.exe"
        exe.write_text("x")
        return M.run({"action": "configurar", "xmrig": str(exe), "carteira": CARTEIRA, "horas": "2"})

    def test_recusa_sem_configurar_no_celular_e_na_bateria(self):
        r = M.run({"action": "ligar"})
        self.assertIn("falta o caminho do xmrig.exe", r)
        self.assertIn("carteira Monero", r)
        self.assertIn("parece Monero", M.run({"action": "configurar", "carteira": "bc1qabc"}))
        self.assertIn("Guardei: horas, xmrig, carteira", self.configurar())
        trocar(self, "plugins.mineracao", "na_tomada", lambda: False)
        self.assertIn("ligue na tomada", M.run({"action": "ligar"}))
        trocar(self, "plugins.mineracao", "no_celular", lambda: True)
        self.assertIn("no celular eu não minero", M.run({"action": "ligar"}))

    def test_liga_so_com_confirmacao_vigia_e_desliga(self):
        self.configurar()
        pedidos = []
        with mock.patch("core.confirm.request", lambda k, t, d, run: pedidos.append((t, d, run)) or "Peça confirmação."):
            self.assertEqual(M.run({"action": "ligar"}), "Peça confirmação.")
        titulo, detalhe, run = pedidos[0]
        self.assertIn("Monero", titulo)
        self.assertIn("prejuízo", detalhe)                                       # a tela mostra a verdade antes de ligar

        class Proc:
            vivo = True
            def poll(self): return None if self.vivo else 0
            def terminate(self): self.vivo = False
            def wait(self, t=None): return 0
            def kill(self): self.vivo = False
        proc = Proc()
        with mock.patch("subprocess.Popen", return_value=proc) as popen, mock.patch("core.relogio.agendar") as agendar:
            r = run()
        self.assertIn("Mineração de Monero ligada", r)
        self.assertIn("-o", popen.call_args[0][0])
        agendar.assert_called_once()
        self.assertIn("já está ligada", M.run({"action": "ligar"}))
        trocar(self, "plugins.mineracao", "resumo_api", lambda: {"hashrate": {"total": [1000.0, 990.0, None]}, "results": {"shares_good": 7}})
        M._proc["inicio"] -= 3600
        M._proc["ultima"] -= 3600
        self.assertIn("1000 H/s, 7 share(s)", M.run({"action": "status"}))
        with mock.patch("core.relogio.cancelar"):
            r = M.run({"action": "desligar"})
        self.assertIn("Mineração desligada (você pediu)", r)
        self.assertFalse(proc.vivo)
        c = M._cfg()
        self.assertEqual(len(c["sessoes"]), 1)
        self.assertAlmostEqual(c["hashrate_medido"], 1000.0, delta=5)           # o próximo cálculo usa o real
        self.assertIn("medido", M.run({"action": "calcular", "moeda": "xmr"}))
        self.assertEqual([b["dados"]["acao"] for b in L.consultar(tipo="mineracao")], ["ligou", "desligou"])
        self.assertIn("1 sessão(ões)", M.run({"action": "relatorio"}))
        self.assertIn("não está ligada", M.run({"action": "desligar"}))

    def _rodando(self):
        class Proc:
            vivo = True
            def poll(self): return None if self.vivo else 0
            def terminate(self): self.vivo = False
            def wait(self, t=None): return 0
            def kill(self): self.vivo = False
        p = Proc()
        M._proc.update(p=p, token="t", inicio=time.time(), ultima=time.time(), hashes=0.0, hs=800.0, shares=0, temp=None, temp_ts=time.time())
        trocar(self, "plugins.mineracao", "resumo_api", lambda: None)
        return p

    def test_para_sozinho(self):
        self.configurar()
        with mock.patch("core.relogio.cancelar"):
            p = self._rodando()
            trocar(self, "plugins.mineracao", "na_tomada", lambda: False)
            M.vigiar()
            self.assertFalse(p.vivo)
            self.assertIn("saiu da tomada", self.falas[-1])
            trocar(self, "plugins.mineracao", "na_tomada", lambda: True)
            p = self._rodando()
            M._proc["inicio"] -= 3 * 3600
            M.vigiar()
            self.assertIn("limite de 2 h", self.falas[-1])
            p = self._rodando()
            M._proc["temp_ts"] = 0
            trocar(self, "plugins.mineracao", "temperatura", lambda: 91.0)
            M.vigiar()
            self.assertIn("esquentou (91 °C)", self.falas[-1])
            p = self._rodando()
            p.vivo = False
            M.vigiar()
            self.assertIn("o XMRig fechou", M._cfg()["sessoes"][-1]["motivo"])
        self.assertEqual(len(M._cfg()["sessoes"]), 4)

    def test_nunca_liga_sozinho_nem_baixa_nada(self):
        src = (Path(M.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("urlretrieve", src)
        self.assertNotIn("Add-MpPreference", src)                               # nunca mexe no antivírus
        self.assertNotIn("Set-MpPreference", src)
        with mock.patch("subprocess.Popen") as popen:
            M.on_session_start(None)
        popen.assert_not_called()



class TestSemBase(unittest.TestCase):
    """Funções de verdade (sem as trocas da classe Base)."""
    def test_dificuldade_sem_internet_usa_aproximada(self):
        m = importlib.import_module("plugins.mineracao")
        with mock.patch.object(m._web, "get_json", side_effect=Exception("sem rede")):
            self.assertEqual(m.dificuldade("xmr"), (m.DIF_XMR_APROX, True))
            self.assertEqual(m.dificuldade("btc"), (m.DIF_BTC_APROX, True))
        with mock.patch.object(m._web, "get_json", return_value={"data": {"difficulty": 5e11}}):
            self.assertEqual(m.dificuldade("xmr"), (5e11, False))

    def test_celular_e_detectado(self):
        m = importlib.import_module("plugins.mineracao")
        for var in ("JARVIS_ANDROID", "TERMUX_VERSION", "ANDROID_ROOT"):
            with mock.patch.dict(os.environ, {var: "1"}):
                self.assertTrue(m.no_celular(), var)


class TestCarteira(Base):
    def test_compra_venda_custo_medio(self):
        self.assertIn("Agora tem 0,002", C.run({"action": "comprar", "moeda": "bitcoin", "quantidade": "0,002", "valor": "1.200"}))
        r = C.run({"action": "comprar", "moeda": "BTC", "quantidade": "0,002", "valor": "1.000,00"})
        self.assertIn("custo médio R$ 550.000,00", r)
        r = C.run({"action": "vender", "moeda": "btc", "quantidade": "0,001", "valor": "700"})
        self.assertIn("Lucro de R$ 150,00", r)
        self.assertIn("Sobrou 0,003", r)
        self.assertIn("você só tem 0,003", C.run({"action": "vender", "moeda": "btc", "quantidade": "1", "valor": "1"}))
        v = C.run({"action": "ver"})
        self.assertIn("Bitcoin: 0,003 = R$ 1.500,00 (−R$ 150,00, -9.1%)", v)
        self.assertIn("já realizou lucro de R$ 150,00", v)
        self.assertIn("não é recomendação", v)
        self.assertIn("vendeu 0,001 Bitcoin por R$ 700,00", C.run({"action": "historico"}))

    def test_protecoes_e_remover(self):
        self.assertIn("Nunca me diga frase de recuperação",
                      C.run({"action": "comprar", "moeda": "bitcoin minha seed é abandon abandon", "quantidade": "1", "valor": "1"}))
        self.assertIn("Qual moeda", C.run({"action": "comprar", "moeda": "banana", "quantidade": "1", "valor": "1"}))
        self.assertIn("Quanto de Ethereum", C.run({"action": "comprar", "moeda": "eth"}))
        self.assertIn("Por quanto", C.run({"action": "comprar", "moeda": "eth", "quantidade": "1"}))
        self.assertIn("vazia", C.run({"action": "ver"}))
        C.run({"action": "comprar", "moeda": "sol", "quantidade": "2", "valor": "800"})
        self.assertIn("Tirei Solana", C.run({"action": "remover", "moeda": "solana"}))
        self.assertIn("Não tem Solana", C.run({"action": "remover", "moeda": "solana"}))

    def test_mineracao_aparece_na_carteira(self):
        guardar = importlib.import_module("plugins._lote2").guardar
        guardar("mineracao", {"sessoes": [{"xmr": 0.001, "horas": 1, "luz": 0.1, "motivo": "x"}]})
        v = C.run({"action": "ver"})
        self.assertIn("Minerado (estimado): 0,001 XMR ≈ R$ 1,50", v)


class TestRegistro(unittest.TestCase):
    def test_niveis_busca_e_resumo(self):
        from core import registro_ferramentas, verificacao as V
        from plugins import catalogo
        self.assertEqual(V.nivel_de("mineracao", {"action": "ligar"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("mineracao", {"action": "calcular"}), V.LIVRE)
        self.assertEqual(V.nivel_de("carteira_cripto", {"action": "ver"}), V.SENSIVEL)
        for nome in ("mineracao", "carteira_cripto"):
            self.assertLessEqual(len(importlib.import_module(f"plugins.{nome}").PLUGIN["brief"]), 150)
        decls = registro_ferramentas.declaracoes()
        casos = {"compensa minerar bitcoin no meu pc": "mineracao", "liga a mineração": "mineracao",
                 "como está minha carteira de cripto": "carteira_cripto", "comprei bitcoin": "carteira_cripto"}
        erros = [q for q, alvo in casos.items() if alvo not in [d["name"] for d in catalogo.buscar(decls, q, 3)]]
        self.assertEqual(erros, [])


if __name__ == "__main__":
    unittest.main()
