"""
Testes da 2.10 — explica pra criança, coach de decisões e detector de procrastinação.
Sem Gemini e sem tocar na janela/linha do tempo de verdade.
"""
import time
import unittest
from unittest import mock

from plugins import coach_decisao as D
from plugins import explica_crianca as E
from plugins import procrastinacao as P
from tests import RAIZ, TMP


# ── explica pra criança ──────────────────────────────────────────────────────
class TestExplica(unittest.TestCase):
    def test_idade(self):
        self.assertEqual(E.ler_idade("8"), 8)
        self.assertEqual(E.ler_idade("como se eu tivesse 5 anos"), 5)
        self.assertEqual(E.ler_idade("adulto leigo"), 99)
        self.assertEqual(E.ler_idade("mais simples ainda"), 5)
        self.assertEqual(E.ler_idade("10 anos"), 12)          # arredonda pro nível de cima
        self.assertEqual(E.ler_idade(None), 8)

    def test_limpar_assunto(self):
        r = E.limpar_assunto("Jarvis, me explica o que é blockchain como se eu tivesse 8 anos")
        self.assertIn("blockchain", r)
        self.assertNotIn("8 anos", r)
        self.assertNotIn("Jarvis", r)
        self.assertEqual(E.limpar_assunto("explica pra criança: por que o céu é azul?"), "por que o céu é azul")
        self.assertEqual(E.limpar_assunto("fotossíntese"), "fotossíntese")

    def test_instrucao_muda_com_idade(self):
        self.assertIn("5 anos", E.instrucao("x", 5))
        self.assertIn("adulto leigo", E.instrucao("x", 99))
        self.assertIn("AINDA mais simples", E.instrucao("x", 5, ainda_mais=True))

    def test_run_sem_gemini_avisa(self):
        with mock.patch("plugins._ia.disponivel", lambda: False):
            self.assertIn("Gemini", E.run({"action": "explicar", "assunto": "buracos negros"}))
        with mock.patch("plugins._ia.disponivel", lambda: True):
            r = E.run({"action": "explicar", "assunto": "buracos negros", "idade": "8"})
            self.assertIn("[EXPLICA FÁCIL]", r)
            self.assertIn("buracos negros", r)


# ── coach de decisões ────────────────────────────────────────────────────────
class TestCoach(unittest.TestCase):
    def setUp(self):
        D.ARQ = TMP / "decisoes.json"
        D.ARQ.unlink(missing_ok=True)

    def test_opcoes_e_peso(self):
        self.assertEqual(D._opcoes_de("aceitar o SENAI ou continuar freelancer"),
                         ["aceitar o SENAI", "continuar freelancer"])
        self.assertEqual(D._opcoes_de("A, B e C"), ["A", "B", "C"])
        self.assertEqual(D.ler_peso("peso 4"), 4)
        self.assertEqual(D.ler_peso("decisivo"), 5)
        self.assertEqual(D.ler_peso("detalhe"), 1)
        self.assertEqual(D.ler_peso(None), 3)

    def test_pontuar_e_ranquear(self):
        dec = {"titulo": "t", "opcoes": [
            {"nome": "A", "fatores": [{"texto": "x", "peso": 5, "lado": "pro"},
                                      {"texto": "y", "peso": 2, "lado": "contra"}]},
            {"nome": "B", "fatores": [{"texto": "z", "peso": 4, "lado": "pro"}]}]}
        self.assertEqual(D.pontuar(dec["opcoes"][0]), 3)
        self.assertEqual(D.pontuar(dec["opcoes"][1]), 4)
        self.assertEqual([o["nome"] for o, _s in D.ranquear(dec)], ["B", "A"])

    def test_achar_opcao_fuzzy(self):
        ops = [{"nome": "aceitar o SENAI", "fatores": []}, {"nome": "continuar freelancer", "fatores": []}]
        self.assertEqual(D.achar_opcao(ops, "SENAI")["nome"], "aceitar o SENAI")
        self.assertEqual(D.achar_opcao(ops, "freelancer")["nome"], "continuar freelancer")
        self.assertIsNone(D.achar_opcao(ops, "xyz"))

    def test_fluxo_completo(self):
        self.assertIn("2 opções", D.run({"action": "nova", "titulo": "SENAI ou freela",
                                         "opcoes": "aceitar o SENAI, continuar freelancer"}))
        D.run({"action": "pro", "opcao": "SENAI", "texto": "salário fixo", "peso": 5})
        D.run({"action": "contra", "opcao": "SENAI", "texto": "menos tempo livre", "peso": 3})
        D.run({"action": "pro", "opcao": "freelancer", "texto": "horário livre", "peso": 4})
        dec = D.dados()["decisoes"][0]
        self.assertEqual(D.pontuar(dec["opcoes"][0]), 2)       # +5 -3
        self.assertEqual(D.pontuar(dec["opcoes"][1]), 4)
        self.assertIn("continuar freelancer", D.run({"action": "ver"}))   # está na frente
        D.run({"action": "peso", "opcao": "SENAI", "fator": "salário", "peso": 1})
        self.assertEqual(D.dados()["decisoes"][0]["opcoes"][0]["fatores"][0]["peso"], 1)
        r = D.run({"action": "decidir", "opcao": "SENAI"})
        self.assertIn("SENAI", r)
        self.assertEqual(D.dados()["decisoes"][0]["decidida"], "aceitar o SENAI")

    def test_coach_nao_decide_sozinho(self):
        D.run({"action": "nova", "titulo": "t", "opcoes": "A, B"})
        D.run({"action": "pro", "opcao": "A", "texto": "bom", "peso": 5})
        frase = D.run({"action": "ver"})
        self.assertIn("decisão é sua", frase)                  # mostra o placar mas devolve a escolha


# ── procrastinação ───────────────────────────────────────────────────────────
class TestProcrastinacao(unittest.TestCase):
    def setUp(self):
        D_cfg = {"ligado": True, "distracoes": "YouTube, Instagram, TikTok", "vezes": "3", "janela_min": "10",
                 "descanso_min": "30", "so_trabalhando": False}
        self._p = mock.patch.object(P, "_c", lambda: D_cfg)
        self._p.start()
        P._estado.update(ultima_ativ="", aberturas=[], ultimo_cutucao=0.0, silencio_ate=0.0, ultimo_trabalho="",
                         distracao_s_hoje=0.0, dia="", ultimo_poll=0.0)

    def tearDown(self):
        self._p.stop()

    def test_lista_e_deteccao(self):
        d = P.lista_distracoes("YouTube, Instagram")
        self.assertTrue(P.eh_distracao("YouTube", d))
        self.assertTrue(P.eh_distracao("youtube", d))
        self.assertFalse(P.eh_distracao("VS Code", d))

    def test_so_conta_entradas_novas(self):
        d = {"youtube"}
        ab, ent1 = P.registrar_troca([], "VS Code", "YouTube", 1000, d, 600)
        self.assertTrue(ent1)
        ab, ent2 = P.registrar_troca(ab, "YouTube", "YouTube", 1010, d, 600)   # continua no YouTube: não conta
        self.assertFalse(ent2)
        ab, _ = P.registrar_troca(ab, "YouTube", "VS Code", 1020, d, 600)
        ab, _ = P.registrar_troca(ab, "VS Code", "YouTube", 1030, d, 600)      # voltou: conta
        self.assertEqual(P.contar(ab, "YouTube", 1030, 600), 2)

    def test_janela_poda_antigos(self):
        d = {"youtube"}
        ab = []
        for t in (0, 100, 1000):                               # 0 e 100 ficam fora da janela de 600 em t=1000
            ab, _ = P.registrar_troca(ab, "VS Code", "YouTube", t, d, 600)
            ab, _ = P.registrar_troca(ab, "YouTube", "VS Code", t + 1, d, 600)
        self.assertEqual(P.contar(ab, "YouTube", 1000, 600), 1)

    def test_deve_cutucar_com_tempo_real(self):
        agora = time.time()
        self.assertTrue(P.deve_cutucar(3, 3, agora, 0.0, 1800, 0.0))           # início: ultimo_cutucao=0 → ok
        self.assertFalse(P.deve_cutucar(2, 3, agora, 0.0, 1800, 0.0))          # abriu pouco
        self.assertFalse(P.deve_cutucar(3, 3, agora, agora - 60, 1800, 0.0))   # cutucou há 1 min
        self.assertFalse(P.deve_cutucar(3, 3, agora, 0.0, 1800, agora + 100))  # em modo foco

    def test_poll_cutuca_na_terceira(self):
        # leitura injetada (atividade, projeto, ocioso) — sem depender de foco_atual nem de mocks de módulo
        foco = ["VS Code", "YouTube", "VS Code", "YouTube", "VS Code", "YouTube"]
        base = 1_700_000_000.0                              # relógio explícito
        saidas = [P._poll(agora=base + i * 60, leitura=(ativ, "", 0.0)) for i, ativ in enumerate(foco)]
        cutucadas = [s for s in saidas if s]
        self.assertEqual(len(cutucadas), 1)
        self.assertIn("3ª vez no YouTube", cutucadas[0])

    def test_poll_calado_quando_ocioso(self):
        base = 1_700_000_000.0
        foco = ["VS Code", "YouTube", "VS Code", "YouTube", "VS Code", "YouTube"]
        saidas = [P._poll(agora=base + i * 60, leitura=(ativ, "", 120.0)) for i, ativ in enumerate(foco)]
        self.assertEqual([s for s in saidas if s], [])     # ocioso (saiu do PC): não cutuca

    def test_focar_silencia(self):
        self.assertIn("60 minutos", P.run({"action": "focar"}))
        self.assertGreater(P._estado["silencio_ate"], time.time())
        self.assertIn("de olho", P.run({"action": "retomar"}))
        self.assertEqual(P._estado["silencio_ate"], 0.0)

    def test_registro_de_seguranca(self):
        from core import verificacao
        for nome in ("explica_crianca", "coach_decisao", "procrastinacao"):
            self.assertEqual(verificacao.nivel_de(nome, {"action": "x"}), verificacao.LIVRE)
            self.assertIn("def run(", (RAIZ / "plugins" / f"{nome}.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
