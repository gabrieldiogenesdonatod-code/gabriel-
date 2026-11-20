"""Biological Core (3.1) — regeneração (10 passos), recuperação de configuração e de código, reinício e integração com o JARVIS."""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests import RAIZ
from tests.bio_comum import ERRO_REDE, RegistroVazio, organismo, projeto, vitais

import biological_core
from biological_core.organismo import Organismo
from core import relogio, vigia
from core.plugin_loader import PluginRecord, PluginRegistry


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jarvis_bio_"))
        self.raiz = projeto(self.tmp)
        self.rede = {"ok": False}

    def tearDown(self):
        biological_core.encerrar()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def corromper(self):
        (self.raiz / "memory" / "lista.json").write_text('{"itens": [1, 2', encoding="utf-8")


class TestRecuperacaoDeConfiguracao(Base):
    def test_json_corrompido_so_volta_com_o_seu_sim(self):
        org = organismo(self.raiz, self.rede)
        try:
            self.corromper()
            self.assertEqual(org.sentinela.ronda(), 1)
            inc = org.memoria.abertos()[0]
            self.assertEqual((inc["categoria"], inc["causa"], inc["estado"]), ("json_corrompido", "dados_corrompidos", "aguardando_autorizacao"))
            pend = org.autorizacoes.pendentes()
            self.assertEqual([p["acao"] for p in pend], ["restaurar_json"])
            self.assertIn('"itens": [1, 2', (self.raiz / "memory" / "lista.json").read_text())   # nada mudou sem você
            r = org.autorizacoes.conceder(pend[0]["id"], "teste")
            self.assertIn("voltou para a versão", r)
            self.assertEqual((self.raiz / "memory" / "lista.json").read_text(), '{"itens": [1, 2, 3]}')
            guardados = [p.name for p in (self.raiz / "memory").iterdir() if ".corrompido-" in p.name]
            self.assertEqual(len(guardados), 1)                              # o quebrado foi guardado, não apagado
            inc = org.memoria.incidente(inc["id"])
            self.assertEqual((inc["estado"], inc["humano"]), ("resolvido", 1))
            prot = inc["detalhes"]["protocolo"]["passos"]
            self.assertTrue(prot[0]["passo"].startswith("7 aplicar"))
            from core import undo
            self.assertIn("voltou a ser o arquivo de antes", undo.undo_last())   # "Jarvis, desfaz" também desfaz reparo
            self.assertIn('"itens": [1, 2', (self.raiz / "memory" / "lista.json").read_text())
        finally:
            org.encerrar()

    def test_pre_autorizado_restaura_sozinho(self):
        with mock.patch("biological_core.autorizacao.cfg", lambda k, d=None: ["restaurar_json"] if k == "bio_pre_autorizados" else d):
            org = organismo(self.raiz, self.rede)
            try:
                self.corromper()
                org.sentinela.ronda()
                self.assertEqual(org.autorizacoes.pendentes(), [])
                self.assertEqual((self.raiz / "memory" / "lista.json").read_text(), '{"itens": [1, 2, 3]}')
            finally:
                org.encerrar()


class TestProtocolo10Passos(Base):
    def test_passos_registrados(self):
        org = organismo(self.raiz, self.rede)
        try:
            for _ in range(3):
                org.sentinela.resultado("bioteste_clima", {"action": "agora"}, 100, False, ConnectionError(ERRO_REDE))
            inc = org.memoria.incidente(org.memoria.incidentes(limite=1)[0]["id"])
            passos = [p["passo"] for p in inc["detalhes"]["protocolo"]["passos"]]
            self.assertEqual([p.split()[0] for p in passos], [str(i) for i in range(1, 11)])
            self.assertIn("ponto de recuperação", passos[5])
        finally:
            org.encerrar()


class TestRecuperacaoDeCodigo(Base):
    def test_codigo_quebrado_volta_para_a_copia_do_dna(self):
        org = organismo(self.raiz, self.rede)
        try:
            alvo = self.raiz / "plugins" / "bioteste_clima.py"
            original = alvo.read_text(encoding="utf-8")
            alvo.write_text("def quebrado(:\n", encoding="utf-8")

            class Registro:
                def list_for_ui(self):
                    return [{"name": "bioteste_clima", "valid": False, "error": "SyntaxError: invalid syntax (linha 1)"}]
            org.sentinela.ronda_inicial(Registro())
            inc = next(i for i in org.memoria.abertos() if i["modulo"] == "bioteste_clima")
            self.assertEqual((inc["causa"], inc["tratamento"]), ("codigo_quebrado", "restaurar_codigo"))
            pend = [p for p in org.autorizacoes.pendentes() if p["acao"] == "restaurar_codigo"]
            self.assertEqual(len(pend), 1)
            org.autorizacoes.conceder(pend[0]["id"], "teste")
            self.assertEqual(alvo.read_text(encoding="utf-8"), original)
            self.assertTrue(any(".mutante-" in p.name for p in alvo.parent.iterdir()))
            self.assertEqual(org.memoria.incidente(inc["id"])["estado"], "resolvido")
        finally:
            org.encerrar()


class TestReinicio(Base):
    def test_tudo_sobrevive_a_reinicio(self):
        org = organismo(self.raiz, self.rede)
        for _ in range(3):
            org.sentinela.resultado("bioteste_clima", {"action": "agora"}, 100, False, ConnectionError(ERRO_REDE))
        org.imune.isolamento.isolar("bioteste_outro", None, "teste de reinício")
        self.corromper()
        org.sentinela.ronda()
        org.cerebro.classificador.aprender("Erro Zorblax no portal", "externo")
        org.cerebro.salvar()
        placar = dict(org.cerebro.decisao.placar)
        pend = org.autorizacoes.pendentes()
        self.assertTrue(pend)
        org.encerrar()

        org2 = Organismo(self.raiz, self.raiz.parent / "bio", sincrono=True, automatico=False, semente=2,
                         conectividade=lambda: True, fonte_vitais=vitais())
        org2.iniciar(RegistroVazio())
        try:
            self.assertIn("bioteste_outro|*", org2.imune.isolamento.quarentena)
            self.assertIn("bioteste_clima|agora", org2.imune.isolamento.disjuntores)
            self.assertEqual([p["id"] for p in org2.autorizacoes.pendentes()], [p["id"] for p in pend])
            self.assertTrue(org2.memoria.abertos())
            self.assertEqual(org2.cerebro.decisao.placar, placar)
            self.assertGreaterEqual(org2.cerebro.classificador.estado()["aprendidos_com_voce"], 1)
            r = org2.autorizacoes.conceder(pend[0]["id"], "teste")           # a ação é refeita depois do reinício
            self.assertIn("voltou para a versão", r)
            self.assertEqual(org2.estado["inicios"], 2)
        finally:
            org2.encerrar()


class TestIntegracao(Base):
    def ligar(self):
        return biological_core.iniciar(registro=RegistroVazio(), raiz=self.raiz, pasta=self.tmp / "bio", sincrono=True,
                                       automatico=False, semente=1, conectividade=lambda: self.rede["ok"], fonte_vitais=vitais())

    def registro(self, **plugins):
        return PluginRegistry({n: PluginRecord(name=n, description="teste", run=fn, valid=True) for n, fn in plugins.items()},
                              logger=lambda m: None)

    def test_portao_do_carregador_de_plugins(self):
        chamadas = []

        def quebra(parameters):
            chamadas.append(parameters)
            raise ConnectionError(ERRO_REDE)
        reg = self.registro(bioteste_falho=quebra, terminal=lambda p: chamadas.append(p) or "rodou",
                            organizar_arquivos=lambda p: chamadas.append(p) or "apagou")
        self.assertIn("failed", reg.run("bioteste_falho", {"action": "x"}))    # sem organismo: igual a antes
        org = self.ligar()
        self.assertTrue(biological_core.ativo())
        for _ in range(3):
            reg.run("bioteste_falho", {"action": "x"})
        antes = len(chamadas)
        r = reg.run("bioteste_falho", {"action": "x"})
        self.assertIn("[DESCANSANDO]", r)
        self.assertEqual(len(chamadas), antes)                                 # não chamou o plugin doente
        r = reg.run("terminal", {"comando": "netsh advfirewall set allprofiles state off"})
        self.assertIn("[BLOQUEADO PELO SISTEMA IMUNE]", r)
        r = reg.run("organizar_arquivos", {"action": "apagar", "caminho": r"C:\Windows\System32\x.dll"})
        self.assertIn("not available", r)                                     # sem tela de confirmação: não faz
        self.assertEqual(len(chamadas), antes)
        self.assertEqual(org.memoria.ameacas()[0]["tipo"], "protecao_do_sistema")

    def test_vigia_e_relogio_contam_ao_organismo(self):
        org = self.ligar()
        r, atrasou = vigia.executar_sync(lambda: time.sleep(0.4) or "ok", "bioteste_lento", limite=0.1)
        self.assertTrue(atrasou)
        self.assertIn("bioteste_lento", [m for _t, m, c, _i, _o in org.sentinela.recentes if c == "timeout"])
        rodou = []
        relogio.agendar("bioteste_rotina_ruim", lambda: 1 / 0, 3600, 10_000)
        relogio.agendar("bioteste_rotina_boa", lambda: rodou.append("boa"), 3600, 10_000)
        relogio.agendar("bioteste_essencial", lambda: rodou.append("essencial"), 3600, 10_000, essencial=True)
        try:
            relogio.rodar_vencidas(time.time() + 20_000)
            self.assertIn("rotina:bioteste_rotina_ruim", [m for _t, m, _c, _i, _o in org.sentinela.recentes])
            relogio.pausar_nao_essenciais(True)
            rodou.clear()
            relogio.rodar_vencidas(time.time() + 40_000)
            self.assertEqual(rodou, ["essencial"])                            # febre: só o essencial roda
        finally:
            relogio.pausar_nao_essenciais(False)
            for n in ("bioteste_rotina_ruim", "bioteste_rotina_boa", "bioteste_essencial"):
                relogio.cancelar(n)

    def test_plugin_organismo(self):
        self.ligar()
        from plugins import organismo as plug
        self.assertIn("Saúde do JARVIS", plug.run({"action": "saude"}))
        self.corromper()
        r = plug.run({"action": "exame"})
        self.assertIn("vacinas 7/7", r)
        self.assertIn("lista.json", plug.run({"action": "incidentes"}))
        r = plug.run({"action": "reparos"})
        self.assertIn("Eu não posso aprovar sozinho", r)
        self.assertNotIn("autorizar", plug.ACOES)                             # a ferramenta do modelo não aprova nada
        self.assertIn("aprove", plug.run({"action": "reconhecer"}).lower())
        biological_core.atual().imune.isolamento.isolar("bioteste_x", None, "teste")
        self.assertIn("bioteste_x", plug.run({"action": "quarentena"}))
        self.assertIn("Liberado", plug.run({"action": "liberar", "modulo": "bioteste_x"}))
        self.assertIn("aprendidos com você", plug.run({"action": "aprendizado"}))
        self.assertIn("Defesa nos últimos 7 dias", plug.run({"action": "evolucao"}))
        with mock.patch("memory.config_manager._patch_config") as gravar:
            self.assertIn("observar", plug.run({"action": "autonomia", "valor": "observar"}))
            gravar.assert_called_once_with(bio_autonomia="observar")
        self.assertIn("precisa do seu sim", plug.run({"action": "desligar"}))
        with mock.patch("plugins._comum.abrir_no_sistema") as abrir:
            self.assertIn("painel do organismo", plug.run({"action": "painel"}))
            abrir.assert_called_once()

    def test_aba_corpo_do_celular(self):
        sys.path.insert(0, str(RAIZ / "celular"))
        import jarvis_celular as jc
        self.assertEqual(jc.corpo(), {"ligado": False})
        org = self.ligar()
        d = jc.corpo()
        self.assertTrue(d["ligado"])
        self.assertIn("<svg", d["svg"])
        self.corromper()
        org.sentinela.ronda()
        pid = org.autorizacoes.pendentes()[0]["id"]
        self.assertIn("voltou para a versão", jc.corpo_acao({"acao": "autorizar", "id": pid}))   # o SEU dedo no botão


if __name__ == "__main__":
    unittest.main()
