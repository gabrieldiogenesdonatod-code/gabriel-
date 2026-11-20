"""
Testes da 2.8.1 — o JARVIS fechando sozinho.

1. core/placa_som.py: abrir/ligar/parar/fechar a placa de som passam por UMA trava
   (o PortAudio em duas threads ao mesmo tempo derruba o Windows sem mensagem).
2. core/por_que_fechou.py: lê o erros.log, o sinal de vida e o registro de erros do
   Windows e explica em português por que fechou.
3. A linha do tempo (evento) e o sinal de vida (batimento) do protecao_falhas.
"""
import json
import threading
import time
import types
import unittest
from datetime import datetime
from unittest import mock

from core import placa_som, por_que_fechou as P, protecao_falhas as PF
from tests import RAIZ, TMP


class TestPlacaSom(unittest.TestCase):
    def _sd_falso(self):
        dentro = {"agora": 0, "maximo": 0}

        class _StreamBase:
            def _mexe(self):
                dentro["agora"] += 1
                dentro["maximo"] = max(dentro["maximo"], dentro["agora"])
                time.sleep(0.01)
                dentro["agora"] -= 1

            def __init__(self, *a, **k):
                self._mexe()

            def start(self):
                self._mexe()

            def stop(self, ignore_errors=True):
                self._mexe()

            def abort(self, ignore_errors=True):
                self._mexe()

            def close(self, ignore_errors=True):
                self._mexe()

        class RawOutputStream(_StreamBase):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)

        return types.SimpleNamespace(_StreamBase=_StreamBase, RawOutputStream=RawOutputStream), dentro

    def test_nunca_duas_threads_na_placa(self):
        sd, dentro = self._sd_falso()
        placa_som._estado["instalado"] = False
        try:
            self.assertTrue(placa_som.instalar(sd))
            self.assertTrue(placa_som.instalar(sd))                  # de novo: não embrulha duas vezes
            self.assertTrue(getattr(sd._StreamBase.close, "_placa_som", False))

            def ciclo():
                for _ in range(5):
                    s = sd.RawOutputStream()
                    s.start()
                    s.stop()
                    s.close()
            ts = [threading.Thread(target=ciclo) for _ in range(6)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
        finally:
            placa_som._estado["instalado"] = False
        self.assertEqual(dentro["maximo"], 1)

    def test_sem_sounddevice_nao_quebra(self):
        placa_som._estado["instalado"] = False
        self.assertFalse(placa_som.instalar(types.SimpleNamespace()))
        placa_som._estado["instalado"] = False


LOG_EXEMPLO = """
=== 07/11/2026 10:00:00 · JARVIS iniciado ===
versão 2.8 · pasta C:\\jarvis-br · pid 1111
10:00:05 · evento: conectado ao Gemini

=== 07/11/2026 10:30:00 · JARVIS fechado: pedido de fechar ===

=== 07/11/2026 11:00:00 · JARVIS iniciado ===
versão 2.8 · pasta C:\\jarvis-br · pid 2222
11:00:05 · evento: conectado ao Gemini
11:12:40 · evento: a sessão caiu: ConnectionClosedError: 1008 — reconectando
11:12:43 · evento: reconectando (pedido: troca de voz/aparelho/ferramentas ou fim da sessão)
Windows fatal exception: access violation

Thread 0x000011aa (most recent call first):
  File "C:\\jarvis-br\\main.py", line 2200 in _receive_audio

Current thread 0x000022bb (most recent call first):
  File "C:\\Python314\\Lib\\site-packages\\sounddevice.py", line 1180 in close
  File "C:\\jarvis-br\\main.py", line 2440 in _fechar_placa
"""


class TestPorQueFechou(unittest.TestCase):
    def test_le_a_ultima_execucao(self):
        u = P.ultima_execucao(LOG_EXEMPLO)
        self.assertEqual(u["pid"], 2222)
        self.assertEqual(u["saida"], "")
        self.assertIn("access violation", u["queda"])
        self.assertEqual(len(u["eventos"]), 3)
        self.assertEqual(P.ultima_execucao(LOG_EXEMPLO, pular_atual=True)["saida"], "pedido de fechar")
        self.assertEqual(P.ultima_execucao(""), {})

    def test_onde_caiu(self):
        onde = P.onde_caiu(P.ultima_execucao(LOG_EXEMPLO)["queda"])
        self.assertTrue(onde.startswith("o som"), onde)
        self.assertIn("sounddevice.py", onde)
        self.assertEqual(P.onde_caiu(""), "")

    def test_explica_queda_com_o_registro_do_windows(self):
        u = P.ultima_execucao(LOG_EXEMPLO)
        evs = [{"ts": u["inicio"] + 760, "id": 1000, "app": "python.exe", "modulo": "_portaudio.dll",
                "codigo": "c0000005", "pid": 2222},
               {"ts": u["inicio"] + 760, "id": 1000, "app": "chrome.exe", "modulo": "x.dll", "codigo": "1", "pid": 9}]
        sinal = {"ts": u["inicio"] + 755, "pid": 2222, "ram_pc": 91.0, "ram_jarvis_mb": 900, "atividade": "conectado"}
        meus = P.do_jarvis(evs, u, sinal)
        self.assertEqual(len(meus), 1)
        t = P.explicar(u, meus, sinal)
        for parte in ("o som", "_portaudio.dll", "acesso inválido à memória", "Último sinal de vida",
                      "RAM do PC 91%", "reconectando", "O que fazer"):
            self.assertIn(parte, t)

    def test_explica_outros_casos(self):
        self.assertIn("normalmente: pedido de fechar",
                      P.explicar(P.ultima_execucao(LOG_EXEMPLO, pular_atual=True), [], {}))
        sem = {"inicio": time.time(), "pid": 5, "saida": "", "queda": "", "eventos": []}
        self.assertIn("encerrado de fora", P.explicar(sem, [], {}))
        self.assertIn("travou", P.explicar(sem, [{"id": 1002, "ts": time.time(), "app": "python.exe", "pid": 5}], {}))
        self.assertIn("SEM MEMÓRIA", P.explicar(sem, [], {"ts": time.time(), "ram_pc": 98.0}))
        self.assertIn("SEM MEMÓRIA", P.explicar(sem, [{"id": 2004, "ts": time.time(), "app": "memoria"}], {}))
        self.assertIn("Ainda não tenho", P.explicar({}, [], {}))

    def test_modulos_e_codigos(self):
        self.assertIn("Intel", P.explicar_modulo("ig9icd64.dll")[0])
        self.assertIn("janela", P.explicar_modulo("Qt6Gui.dll")[0])
        self.assertIn("vídeo", P.explicar_modulo("avcodec-61.dll")[0])
        self.assertIn("abort", P.explicar_codigo("0xc0000409"))
        self.assertEqual(P.codigo("0xC0000005"), "c0000005")
        self.assertIn("arquivo coisa.dll", P.explicar_modulo("coisa.dll")[0])

    def test_historico(self):
        h = P.historico(LOG_EXEMPLO)
        self.assertEqual(h, ["07/11/2026 10:00 → pedido de fechar", "07/11/2026 11:00 → caiu (queda do Windows/driver)"])

    def test_diagnosticar_sem_windows(self):
        with mock.patch.object(P, "SINAL", TMP / "sinal_inexistente.json"), \
                mock.patch.object(P, "eventos_windows", lambda minutos=1440: []):
            t = P.diagnosticar(LOG_EXEMPLO)
        self.assertIn("o som", t)

    def test_plugin(self):
        from plugins import por_que_fechou as PQ
        with mock.patch.object(P, "LOG", TMP / "erros_pqf.log"), \
                mock.patch.object(P, "eventos_windows", lambda minutos=1440: []):
            (TMP / "erros_pqf.log").write_text(LOG_EXEMPLO, encoding="utf-8")
            self.assertIn("2 aberturas", PQ.run({"action": "historico"}))
            r = PQ.run({})
        self.assertIn("normalmente", r)                               # a execução de agora é ignorada


class TestLinhaDoTempo(unittest.TestCase):
    def test_evento_e_batimento(self):
        arq = TMP / "erros_evento.log"
        f = open(arq, "w", encoding="utf-8")
        antigo = PF._estado.get("nativo")
        PF._estado["nativo"] = f
        try:
            PF.evento("conectado ao Gemini")
            PF.evento("conectado ao Gemini")                          # repetido logo em seguida: uma linha só
            PF.evento("a sessão caiu")
        finally:
            PF._estado["nativo"] = antigo
            f.close()
        linhas = [x for x in arq.read_text(encoding="utf-8").splitlines() if "evento" in x]
        self.assertEqual(len(linhas), 2)
        self.assertEqual(P.ultima_execucao("=== 07/11/2026 10:00:00 · JARVIS iniciado ===\nversão x · pid 1\n"
                                           + "\n".join(linhas))["eventos"][-1][9:], "a sessão caiu")

    def test_batimento_grava_o_sinal(self):
        sinal = TMP / "ultimo_sinal.json"
        sinal.unlink(missing_ok=True)
        PF._estado["batimento"] = False
        try:
            with mock.patch.object(PF, "SINAL", sinal):
                PF.batimento(lambda: "testando", a_cada_s=0.05)
                t0 = time.time()
                while not sinal.exists() and time.time() - t0 < 3:
                    time.sleep(0.05)
                time.sleep(0.15)
                d = json.loads(sinal.read_text(encoding="utf-8"))
        finally:
            PF._estado["parar_batimento"] = True
            time.sleep(0.2)
            PF._estado["batimento"] = False
        self.assertEqual(d["atividade"], "testando")
        self.assertGreater(d["ts"], time.time() - 5)


class TestBuscaIsolada(unittest.TestCase):
    """2.8.2: o ddgs (biblioteca nativa) roda num processo separado; se ele cair, o JARVIS continua."""

    def test_processo_que_cai_nao_derruba(self):
        import subprocess
        from actions import ddg_isolado as D
        r = subprocess.CompletedProcess([], 3221226505, "", "Fatal: primp panicked")    # 0xC0000409
        with mock.patch.object(D.subprocess, "run", lambda *a, **k: r):
            self.assertEqual(D.buscar("news", "x"), [])
        def lento(*a, **k):
            raise subprocess.TimeoutExpired("python", 1)
        with mock.patch.object(D.subprocess, "run", lento):
            self.assertEqual(D.buscar("text", "x", timeout=1), [])
        ok = subprocess.CompletedProcess([], 0, '[{"title": "A", "body": "b", "href": "u"}]\n', "")
        with mock.patch.object(D.subprocess, "run", lambda *a, **k: ok):
            from actions import web_search as W
            self.assertEqual(W._ddg_search("x"), [{"title": "A", "snippet": "b", "url": "u"}])

    def test_ninguem_usa_o_ddgs_direto(self):
        for arq in list((RAIZ / "plugins").glob("*.py")) + list((RAIZ / "actions").glob("*.py")):
            if arq.name == "ddg_isolado.py":
                continue
            self.assertNotIn("with DDGS()", arq.read_text(encoding="utf-8", errors="replace"), arq.name)


LOG_COM = """
=== 07/11/2026 15:04:10 · JARVIS iniciado ===
versão 2.8.2 · pasta c:\\x · pid 77
Windows fatal exception: access violation

Thread 0x00003f10 [telemetria] (most recent call first):
  File "C:\\Py\\Lib\\threading.py", line 373 in wait
""" + "  File \"C:\\\\Py\\\\x.py\", line 1 in f\n" * 400 + """
Current thread 0x00004c60 (most recent call first):
  Garbage-collecting
  File "C:\\Py\\comtypes\\_post_coinit\\unknwn.py", line 420 in Release
  File "c:\\x\\core\\avatar.py", line 109 in _blend
"""


class TestComUnico(unittest.TestCase):
    """2.8.3: o erro do seu log — objeto COM (pycaw) solto na thread da janela → access violation."""

    def test_o_diagnostico_acha_a_thread_que_caiu(self):
        t = P.explicar(P.ultima_execucao(LOG_COM), [], {})
        self.assertIn("COM do Windows", t)
        self.assertIn("coleta de lixo", t)

    def test_tudo_roda_numa_thread_so(self):
        from core import com_unico as C
        with mock.patch.object(C, "WIN", True), mock.patch.dict("sys.modules", {"comtypes": types.SimpleNamespace(
                CoInitialize=lambda: None)}):
            nomes = set()
            def onde():
                nomes.add(threading.current_thread().name)
                return 42
            ts = [threading.Thread(target=lambda: self.assertEqual(C.executar(onde), 42)) for _ in range(5)]
            for x in ts:
                x.start()
            for x in ts:
                x.join()
            self.assertEqual(nomes, {"com_unico"})
            with self.assertRaises(ZeroDivisionError):
                C.executar(lambda: 1 / 0)
            dentro = C.na_com(lambda: C.executar(lambda: threading.current_thread().name))
            self.assertEqual(dentro(), "com_unico")                 # chamada de dentro não trava

    def test_ninguem_usa_pycaw_fora_da_thread(self):
        from core import com_unico as C
        self.assertEqual(C.comtypes_fora_daqui(RAIZ), [])
        dj = (RAIZ / "plugins" / "jarvis_dj.py").read_text(encoding="utf-8")
        self.assertNotIn('["obj"]', dj)


class TestIntegracao(unittest.TestCase):
    def test_main_ui_e_iniciar(self):
        m = (RAIZ / "main.py").read_text(encoding="utf-8")
        for trecho in ("_placa.instalar(sd)", "_pf.diagnosticar_em_segundo_plano()", "_antiga.join, 3.0",
                       "self._saida_fechando = threading.Thread", "_mic_stream.start()", "_pf.batimento(",
                       '_pf.evento(f"a sessão caiu', "Por que fechei da última vez"):
            self.assertIn(trecho, m)
        self.assertNotIn("with _mic_stream:", m)
        u = (RAIZ / "ui.py").read_text(encoding="utf-8")
        self.assertIn("qt_bridge.na_interface(self._win.notify_phone_connected)", u)
        b = (RAIZ / "iniciar.bat").read_bytes()
        self.assertIn(b"-m core.por_que_fechou", b)
        self.assertEqual(b.count(b"\n"), b.count(b"\r\n"))               # o .bat continua com CRLF
        self.assertIn("pid {os.getpid()}", (RAIZ / "core" / "protecao_falhas.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
