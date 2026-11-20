"""Testes da 3.5 — IA local (instalar, servidor, troca automática sem internet, atalho do cérebro)."""
import asyncio
import importlib
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests import RAIZ
from tests.test_52_v33 import trocar


class Base(unittest.TestCase):
    def setUp(self):
        global L, PL, CM
        L = importlib.import_module("core.ia_local")
        PL = importlib.import_module("plugins.ia_local")
        CM = importlib.import_module("memory.config_manager")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        trocar(self, "core.ia_local", "PASTA", self.tmp / "ia_local")
        trocar(self, "core.ia_local", "ARQ", self.tmp / "ia_local" / "ia_local.json")
        self.addCleanup(CM.definir_temporario, None, None)
        self.addCleanup(L._temporario.update, {"ativo": False, "vigia": None})

    def instalar_falso(self):
        (L.exe_servidor()).parent.mkdir(parents=True, exist_ok=True)
        L.exe_servidor().write_bytes(b"exe")
        L.arquivo_modelo("leve").parent.mkdir(parents=True, exist_ok=True)
        L.arquivo_modelo("leve").write_bytes(b"gguf")
        L.salvar(instalado=True, modelo="leve")


class TestPuras(Base):
    def test_escolhe_o_zip_certo_do_llama_cpp(self):
        rel = {"assets": [{"name": "llama-b5200-bin-win-cuda-12.4-x64.zip", "browser_download_url": "u1"},
                          {"name": "llama-b5200-bin-ubuntu-x64.zip", "browser_download_url": "u2"},
                          {"name": "llama-b5200-bin-win-cpu-x64.zip", "browser_download_url": "u3"}]}
        self.assertEqual(L.escolher_asset(rel), ("llama-b5200-bin-win-cpu-x64.zip", "u3"))
        velho = {"assets": [{"name": "llama-b4000-bin-win-avx2-x64.zip", "browser_download_url": "u4"}]}
        self.assertEqual(L.escolher_asset(velho)[1], "u4")
        self.assertIsNone(L.escolher_asset({"assets": []}))

    def test_comando_e_espaco(self):
        cmd = L.comando_servidor(Path("llama-server.exe"), Path("m.gguf"), nucleos=4)
        for x in ("-m", "m.gguf", "127.0.0.1", str(L.PORTA), "--jinja"):
            self.assertIn(x, cmd)
        self.assertEqual(cmd[cmd.index("-t") + 1], "3")
        self.assertEqual(L.mb_necessarios("leve", True, True), 808 + 200)
        self.assertGreater(L.mb_necessarios("esperto", False, False), 2020 + 500)

    def test_pipeline_temporario_nao_muda_o_que_esta_salvo(self):
        antes_pipe, antes_cfg = CM.get_pipeline(), CM.get_provider_config("openai_compat")
        pipe, creds = L.pipeline_local()
        CM.definir_temporario(pipe, creds)
        self.assertEqual(CM.get_pipeline()["llm"], "openai_compat")
        self.assertIn(str(L.PORTA), CM.get_provider_config("openai_compat")["base_url"])
        self.assertEqual(CM.get_provider_config("whisper")["language"], "pt")
        CM.definir_temporario(None, None)
        self.assertEqual((CM.get_pipeline(), CM.get_provider_config("openai_compat")), (antes_pipe, antes_cfg))


class TestTroca(Base):
    def test_sem_internet_usa_o_local_e_com_internet_volta(self):
        self.instalar_falso()
        with mock.patch.object(L, "internet_ok", return_value=False), \
                mock.patch.object(L, "ligar_servidor", return_value="ok") as ligar:
            self.assertTrue(L.usar_local_agora())
            ligar.assert_called_once()
        self.assertTrue(L.no_local())
        self.assertEqual(CM.get_pipeline()["stt"], "whisper")
        with mock.patch.object(L, "internet_ok", return_value=True):
            self.assertFalse(L.usar_local_agora())
        self.assertFalse(L.no_local())
        self.assertIsNone(CM._TEMPORARIO["pipeline"])                  # as suas configurações voltam a valer

    def test_sem_instalar_ou_sem_automatico_fica_no_gemini(self):
        with mock.patch.object(L, "internet_ok", return_value=False):
            self.assertFalse(L.usar_local_agora())
            self.instalar_falso()
            L.salvar(auto=False)
            self.assertFalse(L.usar_local_agora())

    def test_vigia_chama_quando_a_internet_volta_e_so_um(self):
        L._temporario["ativo"] = True
        voltou = threading.Event()
        rede = {"ok": False}
        with mock.patch.object(L, "internet_ok", side_effect=lambda: rede["ok"]):
            t = L.vigiar_volta(voltou.set, intervalo_s=0.02)
            self.assertIs(L.vigiar_volta(voltou.set, intervalo_s=0.02), t)
            time.sleep(0.08)
            self.assertFalse(voltou.is_set())
            rede["ok"] = True
            self.assertTrue(voltou.wait(1))


class _Resposta:
    def __init__(self, status, corpo, total=None):
        self.status_code, self.corpo = status, corpo
        self.headers = {"Content-Length": str(total if total is not None else len(corpo))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def iter_content(self, n):
        for i in range(0, len(self.corpo), 3):
            yield self.corpo[i:i + 3]


class TestBaixar(Base):
    def test_baixa_e_retoma(self):
        destino = self.tmp / "m.gguf"
        sessao = mock.MagicMock()
        sessao.get.return_value = _Resposta(200, b"0123456789")
        prog = []
        L.baixar("u", destino, prog.append, sessao=sessao)
        self.assertEqual(destino.read_bytes(), b"0123456789")
        self.assertEqual(prog[-1], 1.0)
        destino.unlink()
        destino.with_suffix(".gguf.part").write_bytes(b"01234")       # a internet caiu no meio
        sessao.get.return_value = _Resposta(206, b"56789")
        L.baixar("u", destino, sessao=sessao)
        self.assertEqual(sessao.get.call_args.kwargs["headers"], {"Range": "bytes=5-"})
        self.assertEqual(destino.read_bytes(), b"0123456789")
        destino.unlink()
        destino.with_suffix(".gguf.part").write_bytes(b"xx")          # servidor não retoma: começa de novo
        sessao.get.return_value = _Resposta(200, b"abc")
        L.baixar("u", destino, sessao=sessao)
        self.assertEqual(destino.read_bytes(), b"abc")


class TestAcharNoGitHub(Base):
    def _sessao(self, api, local="", head=200):
        s = mock.MagicMock()
        def get(url, **kw):
            if "api.github.com" in url:
                if isinstance(api, Exception):
                    raise api
                return mock.Mock(json=lambda: api)
            return mock.Mock(headers={"Location": local}, url="")
        s.get.side_effect = get
        s.head.return_value = mock.Mock(status_code=head)
        return s

    def test_pula_release_que_ainda_esta_subindo(self):
        api = [{"assets": []}, {"assets": [{"name": "llama-b7000-bin-win-cpu-x64.zip", "browser_download_url": "z"}]}]
        self.assertEqual(L.achar_zip_servidor(self._sessao(api)), ("llama-b7000-bin-win-cpu-x64.zip", "z"))

    def test_sem_api_usa_a_pagina_da_ultima_versao(self):
        s = self._sessao({"message": "API rate limit exceeded"}, "https://github.com/ggml-org/llama.cpp/releases/tag/b7001")
        nome, url = L.achar_zip_servidor(s)
        self.assertEqual(nome, "llama-b7001-bin-win-cpu-x64.zip")
        self.assertTrue(url.endswith("/download/b7001/llama-b7001-bin-win-cpu-x64.zip"))
        self.assertEqual(L.tag_da_url("https://github.com/x/releases/tag/b9?a=1"), "b9")

    def test_tudo_falhou_explica_o_jeito_manual(self):
        with self.assertRaises(RuntimeError) as e:
            L.achar_zip_servidor(self._sessao(OSError("bloqueado"), ""))
        self.assertIn("bloqueado", str(e.exception))
        self.assertIn("ia_local\\download", str(e.exception))

    def test_usa_o_zip_que_voce_baixou(self):
        import zipfile
        pasta = L.PASTA / "download"
        pasta.mkdir(parents=True)
        with zipfile.ZipFile(pasta / "llama-b1-bin-win-cpu-x64.zip", "w") as z:
            z.writestr("llama-server.exe", b"exe")
            z.writestr("ggml.dll", b"dll")
            z.writestr("leia.txt", b"x")
        with mock.patch.object(L.os, "name", "nt"), mock.patch.object(L, "achar_zip_servidor", side_effect=AssertionError):
            self.assertEqual(L.instalar_servidor(), "llama-b1-bin-win-cpu-x64.zip")
            self.assertTrue(L.exe_servidor().is_file())
            self.assertTrue((L.exe_servidor().parent / "ggml.dll").is_file())
            self.assertFalse((L.exe_servidor().parent / "leia.txt").exists())


class TestInstalar(Base):
    def test_espaco_e_internet(self):
        with mock.patch("shutil.disk_usage", return_value=mock.Mock(free=100 << 20)):
            self.assertIn("Falta espaço", L.instalar("leve"))
        with mock.patch("shutil.disk_usage", return_value=mock.Mock(free=99 << 30)), \
                mock.patch.object(L, "internet_ok", return_value=False):
            self.assertIn("preciso de internet", L.instalar("leve"))
        self.assertIn("desconhecido", L.instalar("gigante"))

    def test_instala_tudo_e_marca_pronto(self):
        def servidor(prog=None):
            L.exe_servidor().parent.mkdir(parents=True, exist_ok=True)
            L.exe_servidor().write_bytes(b"exe")
            return "zip"

        def baixar(url, destino, prog=None, sessao=None):
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(b"gguf")
            return destino
        avisos = []
        with mock.patch("shutil.disk_usage", return_value=mock.Mock(free=99 << 30)), \
                mock.patch.object(L, "internet_ok", return_value=True), \
                mock.patch.object(L, "instalar_servidor", side_effect=servidor), \
                mock.patch.object(L, "baixar", side_effect=baixar) as b, \
                mock.patch.object(L, "instalar_whisper", return_value="ok"):
            r = L.instalar("leve", avisar=avisos.append)
        self.assertIn("IA local instalada: Llama 3.2 1B", r)
        self.assertTrue(L.pronto())
        self.assertIn("Llama-3.2-1B", b.call_args[0][0])
        self.assertTrue(any("modelo" in a for a in avisos))

    def test_erro_no_meio_avisa_e_libera(self):
        with mock.patch("shutil.disk_usage", return_value=mock.Mock(free=99 << 30)), \
                mock.patch.object(L, "internet_ok", return_value=True), \
                mock.patch.object(L, "instalar_servidor", side_effect=RuntimeError("sem rede")):
            r = L.instalar("leve")
        self.assertIn("continuo de onde parei", r)
        self.assertFalse(L.estado_instalacao()["ativo"])


class _LLMFalso:
    caps = {"tools": True}

    def __init__(self):
        self.chamado = 0

    async def chat(self, messages, tools=None, *, stream=True):
        self.chamado += 1
        yield {"text": "resposta do modelo"}


class TestAtalhoDoCerebro(Base):
    def _rodar(self, llm, msgs):
        async def junta():
            return [ev async for ev in llm.chat(msgs, [])]
        return asyncio.run(junta())

    def test_comando_conhecido_nao_espera_o_modelo(self):
        falso = _LLMFalso()
        w = L.ComReflexo(falso, sem_ia=True)
        r = {"reflexo": True, "ferramenta": "cristal_malhas", "args": {"action": "abrir"}}
        with mock.patch("core.cerebro.entender", return_value=r):
            evs = self._rodar(w, [{"role": "user", "content": "abre a loja"}])
        call = evs[0]["tool_calls"][0]
        self.assertEqual((call.name, call.args), ("cristal_malhas", {"action": "abrir"}))
        self.assertTrue(call.id.startswith("reflexo-"))
        evs = self._rodar(w, [{"role": "user", "content": "abre a loja"},
                              {"role": "tool", "tool_call_id": call.id, "content": "Planilha aberta."}])
        self.assertEqual(evs, [{"text": "Planilha aberta."}])
        self.assertEqual(falso.chamado, 0)
        self.assertEqual(w.caps, {"tools": True})

    def test_pedido_novo_vai_para_o_modelo(self):
        falso = _LLMFalso()
        w = L.ComReflexo(falso)
        with mock.patch("core.cerebro.entender", return_value={"reflexo": False}):
            evs = self._rodar(w, [{"role": "user", "content": [{"type": "text", "text": "me conta uma piada"}]}])
        self.assertEqual(evs, [{"text": "resposta do modelo"}])
        self.assertEqual(falso.chamado, 1)


class TestPlugin(Base):
    def test_estado_automatico_e_testar(self):
        self.assertIn("não está instalada", PL.run({"action": "estado"}))
        self.assertIn("não está instalada", PL.run({"action": "testar", "texto": "oi"}))
        self.instalar_falso()
        with mock.patch.object(L, "servidor_ligado", return_value=False):
            self.assertIn("Llama 3.2 1B", PL.run({"action": "estado"}))
        self.assertIn("desligada", PL.run({"action": "automatico", "valor": "não"}))
        self.assertFalse(L.automatico())
        self.assertIn("ligada", PL.run({"action": "automatico", "valor": "sim"}))
        with mock.patch.object(L, "conversar", return_value="96"):
            self.assertIn("96", PL.run({"action": "testar", "texto": "12 vezes 8"}))

    def test_instalar_pede_o_sim_na_tela(self):
        with mock.patch("core.confirm.request", return_value="aguardando") as conf:
            self.assertEqual(PL.run({"action": "instalar", "modelo": "esperto"}), "aguardando")
        titulo, detalhe, fazer = conf.call_args[0][1:]
        self.assertIn("Llama 3.2 3B", titulo)
        self.assertIn("MB", detalhe)
        with mock.patch.object(L, "instalar", return_value="IA local instalada") as inst, \
                mock.patch("plugins._comum.avisar"), mock.patch("plugins._comum.mostrar"):
            self.assertIn("Comecei a instalar", fazer())
            for _ in range(50):
                if inst.called:
                    break
                time.sleep(0.02)
            self.assertEqual(inst.call_args[0][0], "esperto")

    def test_nivel(self):
        from core import verificacao as V
        self.assertEqual(V.nivel_de("ia_local", {"action": "instalar"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("ia_local", {"action": "estado"}), V.LIVRE)


class TestLigacoes(unittest.TestCase):
    def test_ferramenta_fixa_e_instalador(self):
        from core import orcamento_ferramentas as O
        self.assertIn("ia_local", O.FIXAS)
        self.assertIn("cerebro", O.FIXAS)
        bat = (RAIZ / "instalar_ia_local.bat").read_bytes()
        self.assertIn(b"-m core.ia_local", bat)
        self.assertIn(b"\r\n", bat)

    def test_main(self):
        src = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn("_ial.usar_local_agora()", src)
        self.assertIn("_ial.ComReflexo(_llm", src)
        self.assertIn("a volta da internet", src)


if __name__ == "__main__":
    unittest.main()
