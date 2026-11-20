"""
Testes da 1.5 — verificação sem ficar provando quem você é.

Sem câmera, sem microfone, sem Windows: o rosto/voz são simulados e os
arquivos da sessão vão para uma pasta temporária.
"""
import time
import unittest

import numpy as np

import tests
from core import escuta, registro_uso
from core import verificacao as v


class _Base(unittest.TestCase):
    def setUp(self):
        pasta = tests.TMP / f"verificacao_{id(self)}"
        pasta.mkdir(parents=True, exist_ok=True)
        self._orig = {k: getattr(v, k) for k in ("ARQ_CFG", "ARQ_SESSAO", "ARQ_LOG", "config", "metodos",
                                                 "provar_agora", "_avisar")}
        self._estado = dict(v._estado)
        v.ARQ_CFG, v.ARQ_SESSAO, v.ARQ_LOG = pasta / "c.json", pasta / "s.json", pasta / "l.json"
        self.cfg = {"ligado": True, "horas_sessao": 8.0, "rosto_ao_abrir": True, "confiar_desbloqueio": True,
                    "critico_minutos": 15.0, "desconfiar_desconhecido": True}
        v.config = lambda: dict(self.cfg)
        v.metodos = lambda: ["rosto"]
        self.prova = (False, "não vi o rosto")
        v.provar_agora = lambda player=None: self.prova
        self.eventos = []
        v._avisar = lambda e, d: self.eventos.append((e, d))
        v._estado.update(confiavel=False, desde=0.0, ate=0.0, fonte="", ultima_prova=0.0, ultima_prova_fonte="",
                         remoto_ate=0.0, carregado=True, travado=False, salvo=0.0)
        v._externo.update(desde=0.0, ate=0.0, fonte="")

    def tearDown(self):
        for k, val in self._orig.items():
            setattr(v, k, val)
        v._estado.clear()
        v._estado.update(self._estado)
        v._externo.update(desde=0.0, ate=0.0, fonte="")


class TestNiveis(_Base):
    def test_padroes(self):
        self.assertEqual(v.nivel_de("weather_report"), v.LIVRE)
        self.assertEqual(v.nivel_de("companheiro_jogo", {"action": "chat"}), v.LIVRE)
        self.assertEqual(v.nivel_de("send_message", {"action": "enviar"}), v.SENSIVEL)
        self.assertEqual(v.nivel_de("controle_pc", {"action": "desligar"}), v.CRITICO)
        self.assertEqual(v.nivel_de("sentinela", {"action": "desativar"}), v.CRITICO)
        self.assertEqual(v.nivel_de("auto_melhoria", {"action": "aplicar"}), v.CRITICO)
        self.assertEqual(v.nivel_de("verificacao", {"action": "status"}), v.LIVRE)
        self.assertEqual(v.nivel_de("verificacao", {"action": "desligar"}), v.CRITICO)

    def test_palavras_e_guardiao(self):
        self.assertEqual(v.nivel_de("ferramenta_x", {"alvo": "minha VPS"}), v.SENSIVEL)
        self.assertEqual(v.nivel_de("ferramenta_x", {"texto": "manda um e-mail"}), v.SENSIVEL)
        self.assertEqual(v.nivel_de("ferramenta_x", {"action": "apagar_tudo"}), v.SENSIVEL)

    def test_personalizado_vence_o_padrao(self):
        v.definir_nivel("weather_report", v.SENSIVEL)
        self.assertEqual(v.nivel_de("weather_report"), v.SENSIVEL)
        v.definir_nivel("controle_pc.desligar", v.LIVRE)
        self.assertEqual(v.nivel_de("controle_pc", {"action": "desligar"}), v.LIVRE)


class TestSessao(_Base):
    def test_confiar_e_expirar(self):
        self.assertFalse(v.confiavel())
        v.confiar("rosto")
        self.assertTrue(v.confiavel())
        self.assertIn(("confiou", "rosto"), self.eventos)
        self.assertTrue(v.prova_recente(1))
        v._estado["ate"] = time.time() - 1                    # passaram as 8 h
        self.assertFalse(v.confiavel())

    def test_encerrar_e_suspeitar(self):
        v.confiar("windows")
        v.encerrar("teste")
        self.assertFalse(v.confiavel())
        v.confiar("rosto")
        v.suspeitar("um desconhecido")
        self.assertFalse(v.confiavel())
        self.cfg["desconfiar_desconhecido"] = False
        v.confiar("rosto")
        v.suspeitar("um desconhecido")
        self.assertTrue(v.confiavel())

    def test_windows_bloqueado_so_reabre_pelo_desbloqueio(self):
        v._estado["travado"] = True
        v.confiar("rosto")
        self.assertFalse(v.confiavel())
        v.confiar("windows")
        self.assertTrue(v.confiavel())

    def test_celular_abre_sessao_mas_nao_e_prova_forte(self):
        v.confiar("celular")
        self.assertTrue(v.confiavel())
        self.assertFalse(v.prova_recente(15))


class TestPortao(_Base):
    def test_livre_passa(self):
        self.assertIsNone(v.autorizar("weather_report", {}))

    def test_sem_cadastro_vale_o_windows(self):
        v.metodos = lambda: []
        self.assertIsNone(v.autorizar("send_message", {}))

    def test_verificacao_desligada(self):
        self.cfg["ligado"] = False
        self.assertIsNone(v.autorizar("controle_pc", {"action": "desligar"}))

    def test_sensivel_tenta_provar_na_hora(self):
        self.assertIn("[VERIFICAÇÃO]", v.autorizar("send_message", {}))
        self.prova = (True, "rosto")
        self.assertIsNone(v.autorizar("send_message", {}))
        self.assertTrue(v.confiavel())

    def test_critico_pede_prova_recente(self):
        v.confiar("celular")                                   # sessão aberta, mas sem prova forte
        self.assertIsNone(v.autorizar("send_message", {}))
        self.assertIn("[VERIFICAÇÃO]", v.autorizar("controle_pc", {"action": "desligar"}))
        v.confiar("voz")
        self.assertIsNone(v.autorizar("controle_pc", {"action": "desligar"}))

    def test_origem_remota(self):
        v.marcar_origem_remota(30)
        self.assertIsNone(v.autorizar("send_message", {}))

    def test_texto_de_fora_nunca_vira_acao(self):
        v.confiar("rosto")
        v.marcar_conteudo_externo("chat da live", 10)
        self.assertIn("texto de fora", v.autorizar("send_message", {}))
        self.cfg["ligado"] = False                             # vale mesmo com a verificação desligada
        self.assertIn("texto de fora", v.autorizar("send_message", {}))
        self.assertIsNone(v.autorizar("weather_report", {}))   # o livre continua livre
        time.sleep(0.01)
        escuta.marcar_entrada("digitado")                      # o usuário pediu depois do chat
        self.assertIsNone(v.autorizar("send_message", {}))


class _Relogio:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


class TestEscuta(unittest.TestCase):
    def test_trecho_de_fala_e_ultima_entrada(self):
        relogio = _Relogio()
        original, entrada = escuta.time, dict(escuta._entrada)
        escuta.time = relogio
        escuta._entrada.update(ts=0.0, origem="")
        escuta._trechos.clear()
        escuta._atual.update(blocos=[], inicio=0.0, ultimo_som=0.0)
        try:
            alto = (np.sin(np.arange(1024) / 3) * 3000).astype("int16").reshape(-1, 1)
            baixo = np.zeros((1024, 1), dtype="int16")
            for _ in range(10):                                # a voz do próprio JARVIS não conta
                relogio.t += 1024 / 16000
                escuta.alimentar(alto, jarvis_falando=True)
            self.assertEqual(len(escuta._trechos), 0)
            for _ in range(30):                                # ~1,9 s de fala
                relogio.t += 1024 / 16000
                escuta.alimentar(alto)
            fim_fala = relogio.t
            for _ in range(15):                                # silêncio fecha o trecho
                relogio.t += 1024 / 16000
                escuta.alimentar(baixo)
            self.assertEqual(len(escuta._trechos), 1)
            trecho = escuta.ultimo_trecho(max_idade_s=25, minimo_s=1.2)
            self.assertIsNotNone(trecho)
            self.assertGreaterEqual(len(trecho) / 16000, 1.2)
            # som no microfone não conta como "o usuário pediu" (pode ser jogo ou vídeo)
            self.assertLess(escuta.ultima_entrada(), fim_fala)
            escuta.marcar_entrada("voz")                       # fala reconhecida pelo modelo
            self.assertEqual(escuta.ultima_entrada(), relogio.t)
            relogio.t += 60
            self.assertIsNone(escuta.ultimo_trecho(max_idade_s=25))
        finally:
            escuta.time = original
            escuta._entrada.update(entrada)


class TestChaveCelular(unittest.TestCase):
    def test_presente(self):
        from plugins import chave_celular as cc
        bt = [{"nome": "Mi Band 8", "endereco": "AA:BB:CC:DD:EE:FF", "rssi": -60},
              {"nome": "Fone JBL", "endereco": "11:22:33:44:55:66", "rssi": -95}]
        self.assertEqual(cc.presente({"tipo": "bluetooth", "alvo": "mi band"}, bt, None), (True, -60))
        self.assertEqual(cc.presente({"tipo": "bluetooth", "alvo": "aa-bb-cc-dd-ee-ff"}, bt, None), (True, -60))
        self.assertFalse(cc.presente({"tipo": "bluetooth", "alvo": "Fone JBL"}, bt, None)[0])    # longe demais
        self.assertFalse(cc.presente({"tipo": "bluetooth", "alvo": "mi band"}, None, None)[0])   # sem bleak
        wifi = [{"ip": "192.168.0.5", "mac": "AA:BB:CC:DD:EE:01"}]
        self.assertTrue(cc.presente({"tipo": "wifi", "alvo": "aa-bb-cc-dd-ee-01"}, None, wifi)[0])
        self.assertFalse(cc.presente({"tipo": "wifi", "alvo": "aa-bb-cc-dd-ee-02"}, None, wifi)[0])


class TestErros(unittest.TestCase):
    def test_registrar_erro_aponta_o_arquivo_do_projeto(self):
        try:
            {}["chave"]
        except KeyError as e:
            registro_uso.registrar_erro("teste", e)
        ultimo = registro_uso.erros(time.time() - 60)[-1]
        self.assertEqual(ultimo["tipo"], "KeyError")
        self.assertEqual(ultimo["origem"], "teste")
        self.assertEqual(ultimo["arquivo"], "tests/test_15_verificacao.py")
        self.assertGreater(ultimo["linha"], 0)
        self.assertIn("Traceback", ultimo["traceback"])


if __name__ == "__main__":
    unittest.main()
