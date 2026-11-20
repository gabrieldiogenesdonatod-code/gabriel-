"""
Testes da 1.6 — ferramentas de desenvolvimento e do "Homem de Ferro".
"""
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import tests
from plugins import (_analise_codigo as ac, _projetos as pj, armadura, changelog_falado as cf, explica_repo as er,
                     gerador_projetos as gp, gerador_testes as gt, modo_carro, painel_dev as pd, turno_noite as tn)


class TestAnalise(unittest.TestCase):
    CODIGO = textwrap.dedent('''
        def soma(a, b):
            return a + b

        class Conta:
            def depositar(self, valor):
                self.saldo = valor
            def _interno(self): pass

        def f(): return 1
    ''')

    def test_funcoes(self):
        self.assertEqual([x["qual"] for x in ac.funcoes(self.CODIGO)], ["soma", "Conta.depositar", "Conta._interno", "f"])

    def test_docstrings_sem_quebrar(self):
        novo = ac.inserir_docstrings(self.CODIGO, {"soma": "Soma dois números.", "Conta.depositar": "Guarda.\nNada.",
                                                   "f": "não cabe"})
        self.assertIn('    """Soma dois números."""', novo)
        self.assertIn('        """Guarda.', novo)
        self.assertIn("def f(): return 1", novo)                       # corpo na mesma linha: não mexe
        docs = {x["qual"]: x["doc"] for x in ac.funcoes(novo)}
        self.assertEqual(docs["soma"], "Soma dois números.")

    def test_estrutura(self):
        e = ac.estrutura(tests.RAIZ / "agente_pc")
        self.assertIn("Python", e["linguagens"])
        self.assertIn("arquivos", ac.resumo_texto(e))


class TestProjetos(unittest.TestCase):
    def test_log_e_requisitos(self):
        cs = pj.ler_log("@@abcdef1234|1700000000|Fulano|primeiro\n10\t2\tapp.py\n-\t-\timg.png\n@@ff|1700000100|F|seg\n1\t0\tb.js")
        self.assertEqual([c["msg"] for c in cs], ["primeiro", "seg"])
        self.assertEqual(cs[0]["arquivos"][0], ("app.py", 10, 2))
        self.assertEqual(pj.ler_requisitos("flask==3.0.0\nrequests>=2\nuvicorn[standard]==0.30.1 # x\n"),
                         [("flask", "3.0.0"), ("uvicorn", "0.30.1")])
        self.assertEqual(pj.linguagem("x/y.tsx"), "TypeScript")

    def test_github_e_changelog(self):
        self.assertEqual(er.repo_github("https://github.com/FatihMakes/Mark-LVI.git"), ("FatihMakes", "Mark-LVI"))
        self.assertEqual(er.repo_github("dono/projeto"), ("dono", "projeto"))
        self.assertIsNone(er.repo_github("oi"))
        v, d, itens = cf.ultima_versao("# H\n\n## [1.6] — 2026-11-02\n\n### A\n- `x` novo\n- y\n\n## [1.5] — 2026-11-01\n- z\n")
        self.assertEqual((v, d, itens), ("1.6", "2026-11-02", ["x novo", "y"]))
        self.assertEqual((cf.dias_de("hoje"), cf.dias_de("mês"), cf.dias_de("3")), (1, 30, 3))

    def test_painel(self):
        dia, proj = pd.horas([{"inicio": 1.7e9, "fim": 1.7e9 + 3600, "app": "VS Code", "projeto": "jarvis"},
                              {"inicio": 1.7e9, "fim": 1.7e9 + 60, "app": "Chrome"}])
        self.assertEqual(proj, {"jarvis": 3600.0})
        self.assertEqual(sum(dia.values()), 3600.0)
        self.assertTrue(pd.barras_svg([("a", 1.0)]).startswith("<svg"))
        self.assertIn("Sem dados", pd.barras_svg([]))

    def test_turno_texto(self):
        fala, painel = tn.texto({"quando": 1.7e9, "testes": [{"pasta": "/x/jarvis", "rodou": True, "ok": False,
                                                             "resumo": "10 testes, 1 falha(s)", "fim": "FAIL: a"}],
                                 "vulneraveis": {"requests==2.0": ["GHSA-1"]}, "desatualizados": ["a 1 → 2"]})
        self.assertIn("1 com falha", fala)
        self.assertIn("1 pacote(s) com vulnerabilidade", fala)
        self.assertIn("GHSA-1", painel)


class TestGeradores(unittest.TestCase):
    def test_projeto_cli_roda(self):
        raiz = Path(tempfile.mkdtemp(dir=tests.TMP)) / "cli"
        self.assertEqual(gp.tipo_de("um projeto Flask com login"), "flask_login")
        self.assertIsNone(gp.tipo_de("bot de discord"))
        n = gp.escrever(raiz, gp.arquivos_do_modelo("cli", "Renomeador X"))
        self.assertGreaterEqual(n, 5)
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=raiz, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr.decode())
        self.assertEqual(gp.escrever(raiz, {"../fora.txt": "x"}), 0)       # nada fora da pasta do projeto

    def test_modelos_compilam(self):
        for tipo in gp.MODELOS:
            for nome, conteudo in gp.arquivos_do_modelo(tipo, "teste").items():
                if nome.endswith(".py"):
                    compile(conteudo, nome, "exec")

    def test_testes_de_esqueleto_rodam(self):
        pasta = Path(tempfile.mkdtemp(dir=tests.TMP))
        arq = pasta / "calc.py"
        arq.write_text("def dobro(x):\n    return 2 * x\n", encoding="utf-8")
        ok, saida = gt.rodar(arq.read_text(), gt.esqueleto("calc", ac.funcoes(arq.read_text())), "calc", pasta)
        self.assertTrue(ok, saida)


class TestPainelCarro(unittest.TestCase):
    def test_armadura_texto(self):
        t = armadura.texto_traje({"hora": "10:00", "cpu": 40, "ram": 60, "gpu": None, "temp": 70, "internet": True,
                                  "saude": 88, "clima": "Goiânia 30°C", "celular": {"bateria": 50, "carregando": True}})
        self.assertIn("50% carregando", t)
        self.assertIn("88/100", t)

    def test_notificacoes_do_celular(self):
        dump = ("Notification List:\n  NotificationRecord(0x1 pkg=com.whatsapp user=UserHandle{0} id=1)\n"
                "        android.title=String (Pedro)\n        android.text=String (tô chegando)\n"
                "  NotificationRecord(0x2 pkg=com.android.systemui user=UserHandle{0} id=2)\n"
                "        android.title=String (USB)\n        android.text=String (Carregando)\n"
                "  NotificationRecord(0x3 pkg=com.whatsapp user=UserHandle{0} id=3)\n"
                "        android.title=String (WhatsApp)\n        android.text=String (3 mensagens novas)\n")
        self.assertEqual(modo_carro.ler_notificacoes(dump), [{"app": "WhatsApp", "titulo": "Pedro", "texto": "tô chegando"}])


class TestFishAudio(unittest.TestCase):
    def test_provedor(self):
        from providers import base, tts_fishaudio as f
        self.assertEqual(base.validate(f.PROVIDER), "")
        corpo = f.FishAudioTTS({"api_key": "x", "voice_id": "abc"}).payload("Olá")
        self.assertEqual((corpo["format"], corpo["sample_rate"], corpo["reference_id"]), ("pcm", 24000, "abc"))



if __name__ == "__main__":
    unittest.main()
