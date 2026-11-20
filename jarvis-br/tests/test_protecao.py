"""Lista de proteção de processos (plugins/_protecao.py)."""
import os
import subprocess
import sys
import unittest

import tests  # noqa: F401  (ajusta o sys.path)
from plugins import _protecao as pr


class TestNomes(unittest.TestCase):
    def test_nome_base(self):
        self.assertEqual(pr.nome_base("Explorer.EXE"), "explorer")
        self.assertEqual(pr.nome_base(r"C:\Windows\System32\svchost.exe"), "svchost")
        self.assertEqual(pr.nome_base("Spotify.app"), "spotify")
        self.assertEqual(pr.nome_base(""), "")

    def test_processos_do_sistema_protegidos(self):
        for nome in ("explorer.exe", "svchost", "CSRSS.EXE", "winlogon", "lsass", "services",
                     "dwm", "python", "pythonw.exe", "systemd", "launchd", "WindowServer"):
            self.assertTrue(pr.eh_protegido(nome), nome)

    def test_apps_comuns_liberados(self):
        for nome in ("chrome.exe", "Discord", "steam", "Spotify.exe", "notepad", "Code.exe"):
            self.assertFalse(pr.eh_protegido(nome), nome)

    def test_filtrar_nomes(self):
        ok, bloq = pr.filtrar_nomes(["discord", "explorer", "steam", "csrss.exe"])
        self.assertEqual(ok, ["discord", "steam"])
        self.assertEqual(bloq, ["explorer", "csrss.exe"])


class TestPids(unittest.TestCase):
    def test_o_proprio_processo_e_protegido(self):
        self.assertIn("JARVIS", pr.motivo_protecao("qualquer", os.getpid()))

    def test_pid_do_kernel(self):
        self.assertTrue(pr.eh_protegido("algo", 4))
        self.assertTrue(pr.eh_protegido("algo", 0))

    def test_o_python_que_roda_e_protegido(self):
        self.assertTrue(pr.eh_protegido("qualquer", exe=sys.executable))

    def test_filho_do_jarvis_pode_ser_fechado(self):
        """Programas que o JARVIS abre são filhos dele e precisam poder ser
        fechados depois (por isso a proteção NÃO inclui os descendentes)."""
        # Um filho que NÃO é Python: outro Python seria "irmão" (mesmo
        # executável) e ficaria protegido, de propósito.
        if os.name == "nt":
            nome = "ping"
            filho = subprocess.Popen(["ping", "-n", "30", "127.0.0.1"], stdout=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            nome = "sleep"
            filho = subprocess.Popen(["sleep", "30"])
        try:
            pr._cache_pids = (0.0, set())          # sem cache entre testes
            self.assertEqual(pr.motivo_protecao(nome, filho.pid), "")
        finally:
            filho.kill()
            filho.wait()


if __name__ == "__main__":
    unittest.main()
