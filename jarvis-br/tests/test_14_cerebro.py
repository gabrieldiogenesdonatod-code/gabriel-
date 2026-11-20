"""1.4 — o "cérebro": guardião, gêmeo digital, hipóteses, memória inteligente,
habilidades, conselho, mapa de dependências, criador de ferramentas e laboratório.

Tudo puro ou em pasta temporária; nenhum teste usa IA, rede ou os seus dados.
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

import tests  # noqa: F401


class TestGuardiao(unittest.TestCase):
    def setUp(self):
        from plugins import _guardiao
        self.g = _guardiao
        self._pol = _guardiao.politica
        _guardiao.politica = lambda: {"sempre_perguntar": [], "pode_sozinho": [], "nunca": []}

    def tearDown(self):
        self.g.politica = self._pol

    def test_decisoes(self):
        a = self.g.avaliar
        self.assertEqual(a("controle_pc", {"action": "desligar"}).decisao, "confirmar")
        self.assertEqual(a("controle_pc", {"action": "abrir", "alvo": "spotify"}).decisao, "automático")
        self.assertEqual(a("controle_pc", {"action": "fechar", "alvo": "explorer"}).decisao, "bloquear")
        self.assertEqual(a("", {}, "formatar o disco C").decisao, "bloquear")
        self.assertEqual(a("limpeza", {"action": "previa"}).decisao, "automático")      # só leitura
        self.assertEqual(a("casa_inteligente", {"action": "desligar", "aparelho": "luz"}).decisao, "automático")
        self.assertEqual(a("criador_ferramentas", {"action": "instalar"}).decisao, "confirmar")

    def test_pasta_protegida_so_com_verbo_que_muda(self):
        a = self.g.avaliar
        self.assertNotEqual(a("", {}, r"ler C:\Windows\System32\drivers\etc\hosts").decisao, "bloquear")
        self.assertEqual(a("", {}, r"apagar C:\Windows\System32\algo.dll").decisao, "bloquear")


class TestGemeo(unittest.TestCase):
    def test_dividir_e_prever(self):
        from plugins import gemeo_digital as g
        self.assertEqual(g.dividir("gravar a tela e jogar valorant"), ["gravar", "valorant"])
        s = {"ram": {"total": 8 * g.GB, "usada": 6.5 * g.GB}, "cpu": 40, "processos": []}
        r = g.prever(["valorant", "obs"], s, {})
        self.assertGreater(r["ram_pct"], 100)          # 6,5 GB + Valorant + OBS não cabem em 8 GB
        self.assertEqual(r["risco"], "alto")

    def test_aprender_ewma(self):
        from plugins import gemeo_digital as g
        modelo = g.aprender({}, [{"nome": "jogo.exe", "cpu": 50.0, "ram": 2 * g.GB}], ncpu=4)
        modelo = g.aprender(modelo, [{"nome": "jogo.exe", "cpu": 50.0, "ram": 4 * g.GB}], ncpu=4)
        nome, ram, cpu, fonte = g.perfil_de("jogo", modelo)
        self.assertTrue(2 * g.GB < ram < 4 * g.GB)      # média móvel entre as duas observações
        self.assertEqual(cpu, 50.0)
        self.assertIn("aprendido", fonte)


class TestHipoteses(unittest.TestCase):
    def test_dominio_e_ranking(self):
        from plugins import hipoteses as h
        self.assertEqual(h.dominio_de("o pc está muito lento"), "lento")
        self.assertEqual(h.dominio_de("a internet caiu"), "internet")
        r = h.avaliar("lento", {"cpu": 97, "ram_pct": 40, "temp": 60})
        self.assertTrue(r)
        self.assertAlmostEqual(sum(x["confianca"] for x in r), 1.0, places=5)
        self.assertGreaterEqual(r[0]["confianca"], r[-1]["confianca"])


class TestMemoriaInteligente(unittest.TestCase):
    def setUp(self):
        from plugins import memoria_inteligente as mi
        self.mi = mi
        self.tmp = tempfile.TemporaryDirectory()
        self._arq, mi.ARQUIVO = mi.ARQUIVO, Path(self.tmp.name) / "m.db"
        if hasattr(mi, "_con"):
            mi._con = None

    def tearDown(self):
        if hasattr(self.mi, "_con") and self.mi._con is not None:
            self.mi._con.close()
            self.mi._con = None
        self.mi.ARQUIVO = self._arq
        self.tmp.cleanup()

    def test_decaimento_e_confirmacao(self):
        mi = self.mi
        agora = time.time()
        r = {"categoria": "decisao", "base": 1.0, "criada": agora - 200 * 86400, "vezes": 1}
        c = mi.confianca(r, agora)
        self.assertLess(c, mi.LIMIAR_DESATUALIZADA)
        r["confirmada"] = agora
        self.assertAlmostEqual(mi.confianca(r, agora), 1.0, places=3)
        self.assertEqual(mi.confianca({"categoria": "fato", "expira": agora - 1, "base": 1}, agora), 0.0)

    def test_lembrar_repetido_conta_como_confirmacao(self):
        mi = self.mi
        a = mi.lembrar("eu prefiro tema escuro no VS Code", "preferencia", "usuario")
        b = mi.lembrar("prefiro tema escuro no vs code, eu", "preferencia", "usuario")
        self.assertFalse(a["repetida"])
        self.assertTrue(b["repetida"])
        self.assertEqual(mi.inferir_categoria("decidimos usar Flask no site"), "decisao")


class TestHabilidades(unittest.TestCase):
    def test_planejar_local(self):
        from plugins import habilidades as h
        passos = h.planejar_local("procura os arquivos do orçamento, resume e gera um relatório")
        self.assertEqual([p["ferramenta"] for p in passos],
                         ["buscar_arquivos", "ler_arquivos", "resumir", "gerar_relatorio"])
        passos = h.planejar_local("abre o vs code, fecha o discord e volume 30")
        self.assertEqual([p["params"].get("action") for p in passos], ["abrir", "fechar", "volume"])
        self.assertEqual(h.planejar_local("faz um bolo")[0]["ferramenta"], "manual")

    def test_resumo_extrativo(self):
        from plugins import habilidades as h
        texto = ("O JARVIS controla o computador por voz. Ele abre programas e fecha janelas. "
                 "O JARVIS também monitora o computador e avisa quando algo dá errado. "
                 "Hoje choveu um pouco na cidade. O computador do JARVIS fica mais rápido com limpeza.")
        r = h.resumo_extrativo(texto, 2)
        self.assertIn("JARVIS", r)
        self.assertLess(len(r), len(texto))

    def test_cadeia_com_passo_bloqueado_nao_roda(self):
        from plugins import habilidades as h
        r = h.executar([{"ferramenta": "controle_pc", "params": {"action": "fechar", "alvo": "explorer"},
                         "descricao": "fechar explorer"}])
        self.assertIn("bloqueou", r)


class TestMapaDependencias(unittest.TestCase):
    def test_grafo_impacto_e_ciclos(self):
        from plugins import mapa_dependencias as md
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "pacote").mkdir()
            (raiz / "pacote" / "__init__.py").write_text("")
            (raiz / "pacote" / "base.py").write_text("import os\nVALOR = 1\ndef f():\n    return 2\n")
            (raiz / "pacote" / "meio.py").write_text("from pacote.base import f\nfrom . import fim\n")
            (raiz / "pacote" / "fim.py").write_text("from pacote import meio\nimport requests\n")
            (raiz / "test_base.py").write_text("from pacote import meio\n")
            g = md.analisar(raiz)
            self.assertIn("pacote.base", g["modulos"])
            self.assertEqual(g["ciclos"], [["pacote.fim", "pacote.meio"]])
            r = md.impacto(g, "base")
            self.assertEqual(r["alvo"], "pacote.base")
            self.assertIn("pacote.meio", r["diretos"])
            self.assertIn("test_base", r["testes"])
            self.assertEqual(r["usos"]["pacote.meio"], ["f"])
            self.assertIn("requests", g["externos"])


class TestCriador(unittest.TestCase):
    def test_inspecao_de_seguranca(self):
        from plugins.criador_ferramentas import analisar_seguranca
        ruim = ("import os, shutil as sh, subprocess\n"
                "def run(p, player=None, session_memory=None):\n"
                "    os.remove('a'); sh.rmtree('b'); subprocess.run('x', shell=True); eval('1')\n")
        r = analisar_seguranca(ruim)
        self.assertGreaterEqual(len(r["bloqueios"]), 4)
        bom = "import urllib.request\nPLUGIN = {}\ndef run(p, player=None, session_memory=None):\n    return 'ok'\n"
        r = analisar_seguranca(bom)
        self.assertEqual(r["bloqueios"], [])
        self.assertIn("acessa a internet", r["avisos"])

    def test_sequencias_repetidas(self):
        from plugins.criador_ferramentas import sequencias_repetidas
        cham = []
        base = time.time() - 6 * 86400
        for dia in range(4):
            t = base + dia * 86400
            for k, (f, a, alvo) in enumerate([("controle_pc", "abrir", "vs code"), ("controle_pc", "abrir", "terminal"),
                                              ("web_search", "", "docs")]):
                cham.append({"ts": t + k * 20, "ferramenta": f, "acao": a, "ok": 1,
                             "params": json.dumps({"alvo": alvo} if alvo != "docs" else {"query": alvo})})
        s = sequencias_repetidas(cham)
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["vezes"], 4)
        self.assertEqual(len(s[0]["passos"]), 3)

    def test_modelos_locais_geram_codigo_valido(self):
        import ast
        from plugins import criador_ferramentas as cf
        codigo = cf.gerar_vigia("vigia_teste", "me avisa", "https://exemplo.com/x", "", 6, "a página")
        ast.parse(codigo)
        self.assertEqual(cf.analisar_seguranca(codigo)["bloqueios"], [])
        codigo = cf.gerar_sequencia("rotina_teste", "teste", [{"ferramenta": "saude_pc", "params": {"x": True},
                                                               "descricao": "saúde"}])
        ast.parse(codigo)
        self.assertIn("True", codigo)        # booleanos em Python, não JSON


class TestLaboratorio(unittest.TestCase):
    def test_comparacao_e_variante(self):
        from plugins import laboratorio as lab
        base = {"tempo_medio": 1.0, "tempo_desvio": 0.01, "sucessos": 3, "rodadas": 3, "testes": {"falhas": 0}}
        pior = {"tempo_medio": 0.5, "tempo_desvio": 0.01, "sucessos": 0, "rodadas": 3, "testes": {"falhas": 2}}
        c = lab.comparar(base, pior)
        self.assertTrue(any("mais rápido" in x for x in c))
        self.assertTrue(any("PIOROU" in x for x in c))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "cfg.py").write_text("WORKERS = 4\n")
            self.assertIsNone(lab.aplicar_variante(Path(tmp), {"arquivo": "cfg.py", "trocar": "WORKERS=4",
                                                                "por": "WORKERS = 8"}))
            self.assertIn("8", (Path(tmp) / "cfg.py").read_text())
            self.assertIsNotNone(lab.aplicar_variante(Path(tmp), {"arquivo": "cfg.py", "trocar": "NADA", "por": "x"}))


if __name__ == "__main__":
    unittest.main()
