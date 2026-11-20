"""Testes da 3.2 — anti-eco (o JARVIS não responde a própria voz), modo anônimo e estudos com quadro."""
import json
import sys
import tempfile
import time
import unittest
import urllib.request
from datetime import date
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests import RAIZ

from core import anonimo, anti_eco, ganchos_turno, registro_uso
from core.interrupcao import EstadoInterrupcao
from plugins import _quadro as Q
from plugins import estudos, modo_anonimo


class TestAntiEco(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.t = [100.0]
        self.ae = anti_eco.AntiEco(self.tmp / "ae.json", agora=lambda: self.t[0])

    def test_reconhece_a_propria_voz_pelo_texto(self):
        self.ae.falou("Claro, senhor. A previsão para amanhã em Goiânia é de sol com máxima de 33 graus.")
        self.assertTrue(self.ae.eh_eco("a previsão para amanhã em goiânia é de sol"))
        self.assertTrue(self.ae.eh_eco("previsão pra amanhã em Goiânia é de sol com máxima de 33"))
        self.assertFalse(self.ae.eh_eco("e depois de amanhã vai chover?"))          # pergunta nova sua
        self.assertFalse(self.ae.eh_eco("sim"))                                      # 1–2 palavras nunca é eco
        self.t[0] += 60
        self.assertFalse(self.ae.eh_eco("a previsão para amanhã em goiânia é de sol"))   # passou da janela

    def test_aprende_a_sala_e_lembra(self):
        base = self.ae.cauda_s(0.3)
        self.assertGreaterEqual(base, 0.6)                                          # nunca menos que a cauda mínima
        self.assertEqual(self.ae.registrar_eco(), ["cauda +0.35 s (agora +0.35 s)"])
        self.assertTrue(self.ae.barge_in_permitido())
        feito = self.ae.registrar_eco()
        self.assertIn("interrupção por voz suspensa por 24 h", feito)
        self.assertFalse(self.ae.barge_in_permitido())
        self.assertAlmostEqual(self.ae.cauda_s(0.3) - base, 0.70)
        de_novo = anti_eco.AntiEco(self.tmp / "ae.json")                             # sobrevive a reinício
        self.assertAlmostEqual(de_novo.extra, 0.70)
        self.assertFalse(de_novo.barge_in_permitido())
        de_novo.zerar()
        self.assertTrue(de_novo.barge_in_permitido())
        self.assertEqual(de_novo.extra, 0.0)

    def test_som_de_plugin_fecha_o_microfone(self):
        self.assertFalse(self.ae.audio_plugin_tocando())
        self.ae.marcar_audio_plugin(2.0)
        self.t[0] += 2.4
        self.assertTrue(self.ae.audio_plugin_tocando())                              # +0,6 s de margem da sala
        self.t[0] += 0.3
        self.assertFalse(self.ae.audio_plugin_tocando())

    def test_sd_play_dos_plugins_e_marcado(self):
        from core import placa_som

        class FakeSD:
            class default:
                samplerate = 48000
            tocou = []

            @staticmethod
            def play(data, samplerate=None, *a, **k):
                FakeSD.tocou.append(len(data))
        sd = FakeSD()
        placa_som._marcar_som_de_plugin(sd)
        with mock.patch.object(anti_eco, "_inst", anti_eco.AntiEco(self.tmp / "x.json")):
            sd.play([0] * 96000, 48000)                                              # 2 s de som
            self.assertTrue(anti_eco.get().audio_plugin_tocando())
        self.assertEqual(FakeSD.tocou, [96000])

    def test_resposta_ao_eco_e_descartada(self):
        e = EstadoInterrupcao()
        e.descartar_proxima()
        self.assertTrue(e.audio_chegou())                                            # a resposta ao eco não toca
        self.assertTrue(e.fim_do_turno())
        self.assertFalse(e.audio_chegou())                                           # a próxima toca normal


class TestModoAnonimo(unittest.TestCase):
    def tearDown(self):
        anonimo.definir(False)

    def test_nada_e_gravado(self):
        anonimo.definir(True)
        self.assertTrue(anonimo.ativo())
        anonimo._estado["ativo"] = None
        self.assertTrue(anonimo.ativo())                                             # lembra depois de reiniciar
        antes = len(registro_uso.chamadas())
        registro_uso.registrar_chamada("teste_anonimo", {"segredo": "x"}, 10, True)
        registro_uso.registrar_linha("Você: algo pessoal")
        self.assertEqual(len(registro_uso.chamadas()), antes)
        self.assertFalse(any("algo pessoal" in l["linha"] for l in registro_uso.linhas_registro()))
        from memory import memory_manager as mm
        with mock.patch.object(mm, "MEMORY_PATH", Path(tempfile.mkdtemp()) / "lt.json") as arq:
            mm.save_memory({"identity": {"nome": "teste"}})
            mm.save_session_summary("conversamos sobre algo secreto")
            self.assertFalse(arq.exists())
        ouviu = []
        ganchos_turno.registrar(lambda *a: ouviu.append(a))
        try:
            ganchos_turno.turno("fala", "resposta", esperar=True)
            self.assertEqual(ouviu, [])
        finally:
            ganchos_turno._ouvintes.clear()
        from biological_core.immune_system.threat_detector import sintoma
        self.assertEqual(sintoma("x", "y", texto="erro", params={"cidade": "Goiânia"})["params"], "")
        anonimo.definir(False)
        registro_uso.registrar_chamada("teste_normal", {}, 10, True)
        self.assertEqual(len(registro_uso.chamadas()), antes + 1)                   # desligado: volta ao normal

    def test_plugin_e_prompt_do_celular(self):
        with mock.patch("core.registro_ferramentas.reconectar") as rec:
            self.assertIn("ligado", modo_anonimo.run({"action": "ligar"}))
            rec.assert_called_once_with("modo anônimo", manter_conversa=False)
            self.assertIn("LIGADO", modo_anonimo.run({"action": "status"}))
            sys.path.insert(0, str(RAIZ / "celular"))
            import jarvis_celular as jc
            with mock.patch("memory.config_manager.get_user_name", return_value="Rimuru"):
                motor = jc.Motor.__new__(jc.Motor)
                motor.declaracoes = lambda: []
                txt = motor.sistema()
            self.assertNotIn("Rimuru", txt)
            self.assertIn("[MODO ANÔNIMO]", txt)
            self.assertIn("desligado", modo_anonimo.run({"action": "desligar"}))


class BaseQuadro(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        Q._estado = None
        self.p_pasta = mock.patch("plugins._lote2.PASTA", self.tmp / "lote2")
        self.p_pasta.start()
        self.p_docs = mock.patch("plugins._comum.pasta_jarvis", lambda n: (self.tmp / n).mkdir(exist_ok=True) or self.tmp / n)
        self.p_docs.start()
        self.p_abrir = mock.patch("plugins._comum.abrir_no_sistema", lambda alvo: True)
        self.p_abrir.start()

    def tearDown(self):
        for p in (self.p_pasta, self.p_docs, self.p_abrir):
            p.stop()
        Q._estado = None


class TestQuadro(BaseQuadro):
    def test_calculadora_segura_do_grafico(self):
        self.assertEqual(Q.preparar("f(x) = 3x² - 2x + 1"), " 3*x**2 - 2*x + 1")
        self.assertAlmostEqual(Q.compilar("x^2 - 3x + 2")(1), 0)
        self.assertAlmostEqual(Q.compilar("2sen(x)")(0), 0)
        for ruim in ("__import__('os').system('dir')", "x.__class__", "open('a')", "y + 1", "[1, 2]"):
            with self.assertRaises((ValueError, SyntaxError), msg=ruim):
                Q.compilar(ruim)
        pts = Q.pontos("1/x", -1, 1, 5)
        self.assertEqual(pts[2], [0.0, None])                                       # divisão por zero vira buraco
        self.assertEqual(Q.pontos("sqrt(x)", -4, 4, 3)[0][1], None)

    def test_blocos_paginas_e_respostas(self):
        Q.nova_pagina("Bhaskara")
        Q.escrever("passos", "Calcule o delta; Aplique a fórmula; Confira")
        Q.escrever("tabela", "x|y; 0|2; 1|0")
        Q.escrever("pergunta", "Quanto é 2+2?", resposta="4")
        Q.escrever("tipo_inventado", "vira texto")
        b = Q.pagina()["blocos"]
        self.assertEqual(b[0]["conteudo"], ["Calcule o delta", "Aplique a fórmula", "Confira"])
        self.assertEqual(b[1]["conteudo"], [["x", "y"], ["0", "2"], ["1", "0"]])
        self.assertEqual(b[3]["tipo"], "texto")
        self.assertEqual(Q.revelar(1), 1)
        self.assertTrue(Q.pagina()["blocos"][2]["revelada"])
        v = Q.estado()["versao"]
        Q.limpar()
        self.assertEqual(Q.pagina()["blocos"], [])
        self.assertGreater(Q.estado()["versao"], v)
        Q._estado = None
        self.assertEqual(Q.pagina()["titulo"], "Bhaskara")                           # salvo em disco

    def test_servidor_local(self):
        url = Q.iniciar_servidor()
        try:
            self.assertTrue(url.startswith("http://127.0.0.1:877"))
            Q.escrever("formula", "x = (-b ± sqrt(delta)) / 2a")
            pagina_html = urllib.request.urlopen(url, timeout=5).read().decode()
            self.assertIn("Quadro do JARVIS", pagina_html)
            e = json.loads(urllib.request.urlopen(url + "/estado", timeout=5).read())
            self.assertEqual(e["pagina"]["blocos"][-1]["tipo"], "formula")
            png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            req = urllib.request.Request(url + "/salvar", data=json.dumps({"desenho": png}).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
            arq = Path(json.loads(urllib.request.urlopen(req, timeout=5).read())["arquivo"])
            self.assertTrue(arq.is_file())
            self.assertIn("data:image/png;base64", arq.read_text(encoding="utf-8"))
        finally:
            Q.parar_servidor()


class TestEstudos(BaseQuadro):
    def tearDown(self):
        Q.parar_servidor()
        super().tearDown()

    def test_sessao_completa(self):
        r = estudos.run({"action": "estudar", "tema": "Equação do 2º grau"})
        self.assertIn("Sessão de estudo", r)
        self.assertIn("Escrevi", estudos.run({"action": "escrever", "tipo": "formula", "conteudo": "delta = b^2 - 4ac"}))
        self.assertIn("y vai de", estudos.run({"action": "grafico", "funcao": "x^2-3x+2", "de": "-2", "ate": "5"}))
        self.assertIn("Não consegui entender", estudos.run({"action": "grafico", "funcao": "import os"}))
        aula = {"titulo": "Bhaskara", "blocos": [{"tipo": "texto", "conteudo": "Resolve equações do 2º grau."},
                                                  {"tipo": "formula", "conteudo": "x = (-b ± √Δ) / 2a"},
                                                  {"tipo": "passos", "conteudo": ["Calcule Δ", "Aplique a fórmula"]},
                                                  {"tipo": "grafico", "funcao": "x^2-1", "de": -3, "ate": 3},
                                                  {"tipo": "exemplo", "conteudo": "x² - 5x + 6 = 0 → x = 2 ou 3"},
                                                  {"tipo": "hack", "conteudo": "<script>"}]}
        with mock.patch("core.gemini.as_json", return_value=aula):
            self.assertIn("5 partes", estudos.run({"action": "explicar", "tema": "Bhaskara"}))
        tipos = [b["tipo"] for b in Q.pagina()["blocos"]]
        self.assertEqual(tipos, ["titulo", "texto", "formula", "passos", "grafico", "destaque"])
        with mock.patch("core.gemini.as_json", return_value={"perguntas": [{"pergunta": "Δ de x²-4?", "resposta": "16"}] * 3}):
            self.assertIn("3 exercícios", estudos.run({"action": "exercicios", "quantidade": "3"}))
        self.assertIn("Revelei 1", estudos.run({"action": "resposta", "numero": "2"}))
        with mock.patch("core.gemini.as_json", return_value=None):
            self.assertIn("Sem a IA", estudos.run({"action": "explicar", "tema": "Logaritmo"}))
        r = estudos.run({"action": "encerrar"})
        self.assertIn("encerrada", r)
        self.assertIn("revisões", r)
        from plugins import revisao_espacada
        self.assertIn("Equação do 2º grau", revisao_espacada.run({"action": "listar"}))
        self.assertIn("estudou", estudos.run({"action": "semana"}))

    def test_semana_e_sequencia(self):
        h = [{"tema": "Bhaskara", "dia": "2026-11-14", "minutos": 40}, {"tema": "Bhaskara", "dia": "2026-11-13", "minutos": 20},
             {"tema": "Redes", "dia": "2026-11-12", "minutos": 30}, {"tema": "Antigo", "dia": "2026-10-01", "minutos": 99}]
        s = estudos.semana(h, date(2026, 11, 14))
        self.assertEqual(s["por_tema"], {"Bhaskara": 60, "Redes": 30})
        self.assertEqual((s["total"], s["sequencia"]), (90, 3))


if __name__ == "__main__":
    unittest.main()
