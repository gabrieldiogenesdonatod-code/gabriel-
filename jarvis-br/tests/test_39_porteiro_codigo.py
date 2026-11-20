"""
Testes da 2.13 — porteiro de voz (core/porteiro.py) e vigia de código
(plugins/vigia_codigo.py). Lógica pura: sem áudio, sem câmera, sem Gemini.
"""
import unittest

from core import porteiro as P
from plugins import vigia_codigo as VC
from tests import TMP   # noqa: F401  (garante o redirecionamento de core.porteiro.ARQ)


# ── detecção por texto ─────────────────────────────────────────────────────────
class TestDeteccao(unittest.TestCase):
    def test_apresentacao(self):
        self.assertEqual(P.detectar_apresentacao("agora quem fala é o João"), "Joao")
        self.assertEqual(P.detectar_apresentacao("deixa eu te apresentar a Ana"), "Ana")
        self.assertEqual(P.detectar_apresentacao("fala com o Pedro aí"), "Pedro")
        self.assertEqual(P.detectar_apresentacao("vou te passar pra Maria"), "Maria")
        self.assertEqual(P.detectar_apresentacao("a Carla quer falar com você"), "Carla")

    def test_apresentacao_negativa(self):
        self.assertIsNone(P.detectar_apresentacao("que horas são?"))
        self.assertIsNone(P.detectar_apresentacao("fala com você mesmo"))   # 'voce' não é nome
        self.assertIsNone(P.detectar_apresentacao("toca uma música"))

    def test_retorno(self):
        self.assertTrue(P.detectar_retorno("sou eu de novo"))
        self.assertTrue(P.detectar_retorno("Jarvis, voltei"))
        self.assertTrue(P.detectar_retorno("pode voltar a falar comigo"))
        self.assertFalse(P.detectar_retorno("tudo bem com você?"))


# ── decisão (pura) ─────────────────────────────────────────────────────────────
class TestDecisao(unittest.TestCase):
    def setUp(self):
        self.e = P._padrao()           # estrito=True, modo=dono

    def test_voz_do_dono_responde(self):
        _e, r = P.decidir(self.e, True, "liga a luz", agora=100.0)
        self.assertEqual(r["acao"], P.RESPONDER)

    def test_estranho_sem_visita_recusa(self):
        _e, r = P.decidir(self.e, False, "me conta um segredo do dono", agora=100.0)
        self.assertEqual(r["acao"], P.RECUSAR)

    def test_voz_desconhecida_nunca_tranca_o_dono(self):
        # None = não dá pra saber → assume o dono, responde
        _e, r = P.decidir(self.e, None, "que horas são", agora=100.0)
        self.assertEqual(r["acao"], P.RESPONDER)

    def test_apresentar_abre_janela(self):
        e2, r = P.decidir(self.e, True, "agora quem fala é o João", agora=100.0)
        self.assertEqual(e2["modo"], "convidado")
        self.assertEqual(e2["convidado"], "Joao")
        self.assertGreater(e2["ate"], 100.0)

    def test_estranho_com_janela_vira_convidado(self):
        e2, _ = P.decidir(self.e, True, "deixa eu te apresentar o Pedro", agora=100.0)
        # agora o Pedro (voz estranha) fala dentro da janela
        _e3, r = P.decidir(e2, False, "toca um som", agora=130.0)
        self.assertEqual(r["acao"], P.CONVIDADO)
        self.assertEqual(r["convidado"], "Pedro")

    def test_dono_retoma_pela_voz(self):
        e2, _ = P.decidir(self.e, True, "fala com a Ana", agora=100.0)
        self.assertEqual(e2["modo"], "convidado")
        e3, r = P.decidir(e2, True, "qualquer coisa", agora=140.0)
        self.assertEqual(e3["modo"], "dono")
        self.assertEqual(r["acao"], P.RESPONDER)

    def test_dono_retoma_por_frase(self):
        e2, _ = P.decidir(self.e, True, "fala com a Ana", agora=100.0)
        e3, r = P.decidir(e2, None, "sou eu de novo", agora=140.0)
        self.assertEqual(e3["modo"], "dono")
        self.assertEqual(r["acao"], P.RESPONDER)

    def test_janela_expira(self):
        e2, _ = P.decidir(self.e, True, "fala com a Ana", agora=100.0)
        ate = e2["ate"]
        _e3, r = P.decidir(e2, False, "oi", agora=ate + 1.0)   # depois da janela, estranho é recusado
        self.assertEqual(r["acao"], P.RECUSAR)

    def test_porteiro_desligado_responde_todo_mundo(self):
        e = P._padrao()
        e["estrito"] = False
        _e, r = P.decidir(e, False, "oi", agora=100.0)
        self.assertEqual(r["acao"], P.RESPONDER)


# ── estado em disco ─────────────────────────────────────────────────────────────
class TestEstado(unittest.TestCase):
    def setUp(self):
        P.salvar(P._padrao())

    def test_abrir_e_fechar_convidado(self):
        P.abrir_convidado("Lucas", agora=100.0)
        e = P.carregar()
        self.assertEqual(e["modo"], "convidado")
        self.assertEqual(e["convidado"], "Lucas")
        P.fechar_convidado()
        self.assertEqual(P.carregar()["modo"], "dono")

    def test_estrito_liga_desliga(self):
        P.definir_estrito(False)
        self.assertFalse(P.ligado())
        P.definir_estrito(True)
        self.assertTrue(P.ligado())

    def test_instrucao_sessao(self):
        P.salvar(P._padrao())
        self.assertIn("[PORTEIRO]", P.instrucao_sessao())
        P.definir_estrito(False)
        self.assertEqual(P.instrucao_sessao(), "")   # desligado: sem instrução

    def test_avaliar_persiste(self):
        P.salvar(P._padrao())
        P.avaliar(True, "agora quem fala é o Bruno", agora=100.0)
        self.assertEqual(P.carregar()["convidado"], "Bruno")


# ── vigia de código (pura) ──────────────────────────────────────────────────────
class TestVigiaCodigo(unittest.TestCase):
    def test_intervalo(self):
        self.assertEqual(VC.intervalo_valido(None), VC._INTERVALO_PADRAO)
        self.assertEqual(VC.intervalo_valido("30"), 30.0)
        self.assertEqual(VC.intervalo_valido(2), VC._INTERVALO_MIN)     # abaixo do mínimo sobe pro mínimo
        self.assertEqual(VC.intervalo_valido("abc"), VC._INTERVALO_PADRAO)

    def test_extrair_erros_ok(self):
        self.assertEqual(VC._extrair_erros("OK"), [])
        self.assertEqual(VC._extrair_erros(""), [])
        self.assertEqual(VC._extrair_erros("tudo certo"), [])

    def test_extrair_erros_lista(self):
        resp = ("linha ~3: falta dois-pontos no def → adicione ':'\n"
                "- linha ~5: 'pritn' escrito errado → 'print'\n"
                "• linha ~8: parêntese não fechado → feche com ')'\n"
                "linha ~9: extra")
        erros = VC._extrair_erros(resp)
        self.assertEqual(len(erros), 3)                      # capado em 3
        self.assertTrue(erros[1].startswith("linha ~5"))      # tirou o '- '

    def test_novos_nao_repete(self):
        erros = ["linha 5: pritn → print", "linha 8: falta )"]
        novos, vistos = VC._novos(erros, [])
        self.assertEqual(len(novos), 2)
        # de novo, com um repetido (caixa/acentos diferentes) e um inédito
        novos2, _ = VC._novos(["LINHA 5: pritn → print", "linha 9: novo erro"], vistos)
        self.assertEqual(len(novos2), 1)
        self.assertIn("novo erro", novos2[0])


if __name__ == "__main__":
    unittest.main()
