"""Testes da 3.6.1 — o app Android (APK): a ponte Python, a voz do Android na página e o projeto Gradle.

O APK em si é montado pelo GitHub Actions (android/ + .github/workflows/apk-android.yml). Aqui roda o mesmo
Python que o app roda, com uma "ponte" falsa no lugar do Java, numa cópia limpa do projeto."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401
from tests import RAIZ

PY_APP = RAIZ / "android" / "app" / "src" / "main" / "python"
JAVA = RAIZ / "android" / "app" / "src" / "main" / "java" / "br" / "jarvis" / "app"

ROTEIRO = r'''
import json, sys, urllib.request
sys.path.insert(0, sys.argv[1])
import jarvis_android as JA
class Ponte:
    def __init__(self): self.log = []
    def comando(self, cmd, args):
        self.log.append([cmd, json.loads(args)])
        if cmd == "termux-battery-status":
            return json.dumps({"percentage": 77, "status": "CHARGING", "temperature": 31.4})
        if cmd == "termux-location":
            return "ERRO: isso ainda não está no app do JARVIS"
        return "ok"
p, raiz, porta = Ponte(), sys.argv[2], int(sys.argv[3])
out = {"inicio": JA.iniciar_seguro(raiz, p, raiz + "/../publico", porta)}
out["de_novo"] = JA.iniciar(raiz, p, raiz + "/../publico", porta)
url = f"http://127.0.0.1:{porta}"
out["html"] = urllib.request.urlopen(url + "/").read().decode()
out["estado"] = json.load(urllib.request.urlopen(url + "/api/estado"))
import jarvis_celular as jc
run = lambda n, a: jc.REG.run(n, a, player=jc.PLAYER, session_memory=None)
out["bateria"] = run("celular_android", {"action": "bateria"})
out["local"] = run("celular_android", {"action": "localizacao"})
out["painel"] = run("omega", {"action": "painel"})
from core import cerebro
cerebro.ensinar("como está a bateria", "celular_android", {"action": "bateria"})
req = urllib.request.Request(url + "/api/chat", data=json.dumps({"texto": "Jarvis, como está a bateria"}).encode(),
                             headers={"Content-Type": "application/json"})
out["chat"] = json.load(urllib.request.urlopen(req))
out["ponte"] = p.log
out["avisos"] = [e for e in jc.EVENTOS.desde(0) if e["tipo"] in ("fala", "cartao")]
print("@@" + json.dumps(out, ensure_ascii=False))
'''


class TestPonteAndroid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        copia = cls.tmp / "jarvis-br"
        shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns("__pycache__", "android", "tests", ".github", "*.zip", ".pytest_cache",
                                                                     "ia_local"))
        for lixo in list((copia / "memory").glob("*.json")) + list((copia / "memory").glob("*.db*")):
            lixo.unlink()
        (cls.tmp / "roteiro.py").write_text(ROTEIRO, encoding="utf-8")
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        r = subprocess.run([sys.executable, "-I", str(cls.tmp / "roteiro.py"), str(PY_APP), str(copia), str(porta)],
                           capture_output=True, text=True, timeout=240, cwd=str(cls.tmp))
        linha = [x for x in r.stdout.splitlines() if x.startswith("@@")]
        if not linha:
            raise AssertionError(r.stdout[-3000:] + r.stderr[-3000:])
        cls.r = json.loads(linha[0][2:])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_sobe_o_jarvis_do_celular_inteiro(self):
        self.assertEqual((self.r["inicio"], self.r["de_novo"]), ("ok", "ja"))
        e = self.r["estado"]
        self.assertGreaterEqual(e["total_plugins"], 340)            # 351 menos os que pedem pacote de PC (psutil)
        self.assertEqual(len(e["modos"]), 158)

    def test_voz_do_android_entra_antes_do_script_da_pagina(self):
        h = self.r["html"]
        self.assertIn("window.JarvisVoz", h)
        self.assertLess(h.index("window.JarvisVoz"), h.index("const SR"))
        self.assertLess(h.index("<head>"), h.index("window.JarvisVoz"))

    def test_celular_android_fala_com_o_java(self):
        self.assertEqual(self.r["bateria"], "Bateria em 77%, carregando, 31 °C.")
        self.assertIn("ainda não está no app", self.r["local"])
        self.assertIn("Painel OMEGA aberto", self.r["painel"])
        cmds = [c for c, _ in self.r["ponte"]]
        self.assertIn("abrir", cmds)                                   # o painel abre dentro do app
        self.assertTrue(any(c == "abrir" and a["a"][0].endswith("omega.html") for c, a in self.r["ponte"]))

    def test_cerebro_both_sem_chave_o_cerebro_local_faz(self):
        c = self.r["chat"]
        self.assertTrue(c.get("cerebro"), c)
        self.assertIn("Bateria em 77%", c["resposta"])
        self.assertGreaterEqual([x for x, _ in self.r["ponte"]].count("termux-battery-status"), 2)

    def test_sem_aviso_de_pip_no_celular(self):
        textos = " ".join(str(a.get("texto", "")) for a in self.r["avisos"])
        self.assertNotIn("pip install", textos)
        self.assertNotIn("Erro de código", textos)


class TestPecasPuras(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(PY_APP))
        self.addCleanup(sys.path.remove, str(PY_APP))
        import jarvis_android
        self.JA = jarvis_android

    def test_html_e_ponte(self):
        self.assertTrue(self.JA.html_android("<html><HEAD><title>x</title>").startswith("<html><HEAD>\n<script>"))
        self.assertTrue(self.JA.html_android("<p>sem head</p>").startswith("<script>"))

        class P:
            def comando(self, c, a):
                return "ERRO: sem lanterna" if c == "termux-torch" else json.dumps(json.loads(a))
        t = self.JA.termux_pela_ponte(P())
        self.assertEqual(json.loads(t("termux-clipboard-set", entrada="oi")), {"a": [], "entrada": "oi"})
        with self.assertRaisesRegex(RuntimeError, "sem lanterna"):
            t("termux-torch", "on")
        self.assertFalse(self.JA.abrir_pela_ponte(P())("x"))                # só "ok" conta como aberto


class TestProjetoAndroid(unittest.TestCase):
    def test_gradle_manifesto_e_java_conversam(self):
        app = (RAIZ / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
        man = (RAIZ / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn('version "3.11"', app)
        self.assertIn('namespace "br.jarvis.app"', app)
        self.assertTrue((RAIZ / "android" / "app" / "jarvis.keystore").is_file())
        self.assertTrue((RAIZ / "android" / "gradle" / "wrapper" / "gradle-wrapper.jar").is_file())
        for cls in ("MainActivity", "JarvisService"):
            self.assertIn(f'android:name=".{cls}"', man)
            self.assertTrue((JAVA / f"{cls}.java").is_file())
        for perm in ("RECORD_AUDIO", "FOREGROUND_SERVICE_SPECIAL_USE", "POST_NOTIFICATIONS"):
            self.assertIn(perm, man)
        java = "".join(p.read_text(encoding="utf-8") for p in JAVA.glob("*.java"))
        self.assertIn('getModule("jarvis_android").callAttr("iniciar_seguro"', java)
        self.assertIn('addJavascriptInterface(voz, "JarvisVoz")', java)
        porta_py = re.search(r"PORTA = (\d+)", (PY_APP / "jarvis_android.py").read_text(encoding="utf-8")).group(1)
        self.assertIn(f"PORTA = {porta_py}", java)
        # cada comando termux-* que o plugin usa tem resposta no Java (ou o aviso honesto de que ainda não tem)
        plugin = (RAIZ / "plugins" / "celular_android.py").read_text(encoding="utf-8")
        usados = set(re.findall(r'"(termux-[\w-]+)"', plugin)) - {"termux-api"}
        tratados = set(re.findall(r'case "(termux-[\w-]+)"', java))
        self.assertEqual(usados - tratados, {"termux-location", "termux-wifi-connectioninfo", "termux-brightness",
                                             "termux-contact-list", "termux-camera-photo"})
        self.assertIn("default: return NAO_TEM", java)

    def test_o_zip_do_app_leva_o_jarvis_e_nao_leva_dados_pessoais(self):
        app = (RAIZ / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
        bloco = app.split("exclude", 1)[1].split("}")[0]
        padroes = re.findall(r'"([^"]+)"', bloco)

        def ant(p):                                  # padrão do Gradle (ant) → regex
            r = re.escape(p).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
            return re.compile("^" + r + "$")
        regras = [ant(p) for p in padroes]
        fora = lambda rel: any(r.match(rel) for r in regras)          # noqa: E731
        for rel in ("memory/livro_razao.key", "memory/cerebro.json", "memory/uso.db", "memory/livro_razao.db-wal",
                    "config/api_keys.json", "tests/test_55_v36.py", "android/app/build.gradle", "plugins/__pycache__/x.pyc",
                    "jarvis-br-3.6-completo.zip", "iniciar.bat", "memory/lote2/a.json", "celular/jarvis_android.html"):
            self.assertTrue(fora(rel), rel)
        for rel in ("celular/jarvis_celular.py", "celular/jarvis_celular.html", "plugins/omega.py", "plugins/_modos_lote4.py",
                    "core/cerebro.py", "biological_core/__init__.py", "memory/config_manager.py", "config/exemplo_api_keys.json",
                    "providers/__init__.py"):
            self.assertFalse(fora(rel), rel)
            self.assertTrue((RAIZ / rel).exists(), rel)

    def test_workflow_do_github(self):
        wf = (RAIZ / ".github" / "workflows" / "apk-android.yml").read_text(encoding="utf-8")
        for trecho in ("python-version: \"3.11\"", "java-version: \"17\"", "./gradlew assembleDebug", "upload-artifact"):
            self.assertIn(trecho, wf)


if __name__ == "__main__":
    unittest.main()
