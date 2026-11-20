"""
Testes da 2.11 — os 9 plugins novos. Sem Gemini, sem rede, sem pyautogui e sem
apagar nada de verdade (a faxina roda numa pasta de teste).
"""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from plugins import acompanhar as AC
from plugins import assistente_viagem as V
from plugins import clone_estudo as CE
from plugins import modo_apresentacao as MA
from plugins import modo_faxina as FX
from plugins import organizador_abas as OA
from plugins import palpite_humor as PH
from plugins import preencher_form as PF
from plugins import renomear_fotos as RF
from tests import RAIZ, TMP


# ── renomeador de fotos ──────────────────────────────────────────────────────
class TestRenomearFotos(unittest.TestCase):
    def test_puras(self):
        self.assertEqual(RF.slug("Praia de Salvador!"), "praia_de_salvador")
        self.assertEqual(RF.ano_de("2019:07:12 10:00:00", 2026), 2019)
        self.assertEqual(RF.ano_de(None, 2026), 2026)
        self.assertEqual(RF.ano_de("lixo", 2024), 2024)
        self.assertEqual(RF.montar_nome("praia", 2026, "amigos"), "praia_2026_amigos.jpg")
        self.assertEqual(RF.montar_nome("praia", 2026, "praia"), "praia_2026.jpg")   # não repete
        self.assertTrue(RF.eh_generico("IMG_1234.jpg"))
        self.assertTrue(RF.eh_generico("WhatsApp Image 2026.jpeg"))
        self.assertFalse(RF.eh_generico("festa-junina.jpg"))

    def test_resolver_conflitos(self, ):
        pasta = TMP / "fts"
        pasta.mkdir(exist_ok=True)
        planos = [(pasta / "a.jpg", "praia_2026.jpg"), (pasta / "b.jpg", "praia_2026.jpg")]
        r = RF.resolver_conflitos(planos)
        self.assertEqual([n for _o, n in r], ["praia_2026.jpg", "praia_2026_2.jpg"])

    def test_planejar_com_visao_falsa(self):
        pasta = TMP / "fotos_t"
        pasta.mkdir(exist_ok=True)
        for p in pasta.iterdir():
            p.unlink()
        (pasta / "IMG_1.jpg").write_bytes(b"x")
        (pasta / "ferias-boas.jpg").write_bytes(b"x")       # já tem nome bom → pulada
        with mock.patch.object(RF, "_ver", lambda c: ("praia", "salvador")), \
                mock.patch.object(RF, "_ano_arquivo", lambda c: 2026):
            planos, puladas = RF.planejar(pasta, 30)
        self.assertEqual(puladas, 1)
        self.assertEqual(planos, [(pasta / "IMG_1.jpg", "praia_2026_salvador.jpg")])


# ── organizador de abas ──────────────────────────────────────────────────────
class TestAbas(unittest.TestCase):
    def setUp(self):
        OA.ARQ = TMP / "sessoes_abas.json"
        OA.ARQ.unlink(missing_ok=True)

    def test_links_puros(self):
        self.assertEqual(OA.normalizar_url("github.com"), "https://github.com")
        self.assertEqual(OA.normalizar_url("gmail"), "https://mail.google.com")
        self.assertEqual(OA.normalizar_url("https://x.com/a"), "https://x.com/a")
        self.assertEqual(OA.normalizar_url("meu almoço"), "")
        self.assertEqual(OA.separar_links("github.com, gmail e claude.ai"),
                         ["https://github.com", "https://mail.google.com", "https://claude.ai"])
        self.assertEqual(OA.url_do_titulo("Caixa de entrada - exemplo@gmail.com - Gmail"), "https://mail.google.com")

    def test_fluxo(self):
        self.assertIn("2 link", OA.run({"action": "salvar", "nome": "trabalho", "links": "github.com e gmail"}))
        abertos = []
        with mock.patch.object(OA.webbrowser, "open", lambda u: abertos.append(u) or True):
            r = OA.run({"action": "abrir", "nome": "trabalho"})
        self.assertEqual(len(abertos), 2)
        self.assertIn("2 aba", r)
        self.assertIn("1 sessão", OA.run({"action": "listar"}))
        self.assertIn("Apaguei", OA.run({"action": "remover", "nome": "trabalho"}))

    def test_capturar_abas(self):
        janelas = [{"processo": "chrome.exe", "titulo": "GitHub - meu repo"},
                   {"processo": "notepad.exe", "titulo": "sem graça"}]
        with mock.patch("plugins._janelas.listar", lambda: janelas):
            r = OA.run({"action": "capturar", "nome": "estudo"})
        self.assertIn("1 aba", r)
        self.assertEqual(OA.dados()["sessoes"]["estudo"]["links"], ["https://github.com"])


# ── modo apresentação ────────────────────────────────────────────────────────
class TestApresentacao(unittest.TestCase):
    def setUp(self):
        MA.ARQ = TMP / "apresentacao.json"
        MA.ARQ.unlink(missing_ok=True)
        self._p = [mock.patch.object(MA, "manter_tela_acesa", lambda on: True),
                   mock.patch.object(MA, "_tecla", lambda n: True)]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()

    def test_normalizar_acao(self):
        self.assertEqual(MA.normalizar_acao("passa o slide"), "proximo")
        self.assertEqual(MA.normalizar_acao("volta um slide"), "anterior")
        self.assertEqual(MA.normalizar_acao("tela preta"), "preto")
        self.assertEqual(MA.normalizar_acao("sair da apresentação"), "desligar")
        self.assertEqual(MA.normalizar_acao("modo apresentação"), "ligar")

    def test_liga_passa_desliga(self):
        self.assertIn("ligado", MA.run({"action": "ligar"}))
        self.assertTrue(MA.ativa())
        self.assertIn("Próximo", MA.run({"action": "proximo"}))
        self.assertIn("desligado", MA.run({"action": "desligar"}))
        self.assertFalse(MA.ativa())
        self.assertIn("não está ligado", MA.run({"action": "proximo"}))


# ── assistente de viagem ─────────────────────────────────────────────────────
class TestViagem(unittest.TestCase):
    def test_puras(self):
        self.assertEqual(V.tipo_de("5 dias em Salvador na praia"), "praia")
        self.assertEqual(V.tipo_de("congresso em São Paulo"), "trabalho")
        self.assertEqual(V.tipo_de("passeio pela cidade"), "cidade")
        self.assertIn("protetor solar", V.lista_mala("praia", 5))
        self.assertIn("casaco pesado", V.lista_mala("frio", 3))
        self.assertEqual(V.offset_de("Lisboa"), 0)
        self.assertEqual(V.offset_de("Tóquio"), 9)
        self.assertIsNone(V.offset_de("Narnia"))

    def test_converter(self):
        r = V.converter(100, "dolar", "real", {"USD": 5.0})
        self.assertAlmostEqual(r[0], 500.0)
        self.assertEqual((r[1], r[2]), ("USD", "BRL"))
        self.assertIsNone(V.converter(1, "xpto", "real"))

    def test_fuso_e_cambio_run(self):
        self.assertIn("Lisboa", V.run({"action": "fuso", "lugar": "Lisboa"}))
        with mock.patch.object(V, "_cotacoes_reais", lambda: {"USD": 5.0}):
            r = V.run({"action": "cambio", "valor": 100, "de": "dolar", "para": "real"})
        self.assertIn("500", r)


# ── clone de estudo ──────────────────────────────────────────────────────────
class TestEstudo(unittest.TestCase):
    def setUp(self):
        CE.ARQ = TMP / "estudo.json"
        CE.ARQ.unlink(missing_ok=True)

    def test_puras(self):
        self.assertEqual(CE.ler_letra("letra B"), "B")
        self.assertEqual(CE.ler_letra("a segunda"), "B")
        self.assertEqual(CE.ler_letra("nada"), "")
        q = {"enunciado": "2+2?", "alternativas": ["3", "4"], "correta": "B"}
        self.assertTrue(CE.corrigir(q, "b"))
        self.assertFalse(CE.corrigir(q, "A"))
        self.assertIn("2. ", CE.formatar_questao(q, 2))

    def test_prova_e_desempenho(self):
        prova = {"questoes": [{"enunciado": "q1", "alternativas": ["a", "b", "c", "d", "e"], "correta": "B"},
                              {"enunciado": "q2", "alternativas": ["a", "b", "c", "d", "e"], "correta": "A"}]}
        with mock.patch("plugins._ia.disponivel", lambda: True), \
                mock.patch("plugins._ia.perguntar_json", lambda *a, **k: prova):
            self.assertIn("2 questões", CE.run({"action": "prova", "materia": "lógica", "quantas": 2}))
        self.assertIn("Acertou", CE.run({"action": "responder", "questao": 1, "letra": "B"}))
        self.assertIn("era a letra A", CE.run({"action": "responder", "questao": 2, "letra": "C"}))
        d = CE.dados()
        self.assertIsNone(d["prova"])                       # acabou
        self.assertEqual(d["materias"]["logica"]["acertos"], 1)
        self.assertEqual(d["materias"]["logica"]["erros"], 1)
        self.assertIn("logica", CE.run({"action": "desempenho"}).lower() + str(d))

    def test_resumo_aponta_fraco(self):
        materias = {"mat": {"acertos": 2, "erros": 8, "nome": "mat"}, "port": {"acertos": 9, "erros": 1, "nome": "port"}}
        r = CE.resumo_desempenho(materias)
        self.assertIn("Treinar mais", r)
        self.assertIn("mat", r)


# ── modo faxina ──────────────────────────────────────────────────────────────
class TestFaxina(unittest.TestCase):
    def test_seguro_recusa_raiz_e_home(self):
        self.assertFalse(FX._seguro(Path.home()))
        self.assertFalse(FX._seguro(Path(Path.home().anchor)))
        d = TMP / "faxina_temp"
        d.mkdir(exist_ok=True)
        self.assertTrue(FX._seguro(d))                      # tem "temp" no nome
        self.assertFalse(FX._seguro(TMP / "documentos"))    # não parece descarte

    def test_modo_de(self):
        self.assertEqual(FX.modo_de("limpa meus rastros e histórico"), "anonimo")
        self.assertEqual(FX.modo_de("faz uma faxina"), "rapida")

    def test_executar_so_apaga_o_lixo(self):
        lixo = TMP / "faxina_temp"
        lixo.mkdir(exist_ok=True)
        (lixo / "a.tmp").write_bytes(b"x" * 100)
        (lixo / "sub").mkdir(exist_ok=True)
        (lixo / "sub" / "b.tmp").write_bytes(b"y" * 50)
        with mock.patch.object(FX, "_temp_dirs", lambda: [lixo]), \
                mock.patch.object(FX, "_recent_dir", lambda: None), \
                mock.patch.object(FX, "_browser_dirs", lambda h: []), \
                mock.patch.object(FX, "_esvaziar_lixeira", lambda: False):
            r = FX.executar("rapida")
        self.assertIn("Faxina feita", r)
        self.assertEqual(list(lixo.iterdir()), [])          # esvaziou
        self.assertTrue(lixo.exists())                      # mas não apagou a pasta


# ── palpite de humor ─────────────────────────────────────────────────────────
class TestHumor(unittest.TestCase):
    def test_fases_e_estimativa(self):
        self.assertEqual(PH.fase_do_dia(3)[0], "madrugada")
        self.assertEqual(PH.fase_do_dia(10)[0], "manhã")
        leitura, sug = PH.estimar(15, 150, 0)
        self.assertIn("2 horas", leitura)
        self.assertIn("pausa", sug.lower())
        leitura2, _ = PH.estimar(15, 5, 600)
        self.assertIn("voltar", leitura2.lower() + "voltar")

    def test_run_e_palpite(self):
        with mock.patch.object(PH, "_minutos_seguidos", lambda: 10), mock.patch.object(PH, "_ocioso", lambda: 0):
            r = PH.run({"action": "palpite"})
        self.assertIn("[PALPITE]", r)
        self.assertIn("palpite", r.lower())


# ── preenchedor de formulário ────────────────────────────────────────────────
class TestFormulario(unittest.TestCase):
    def setUp(self):
        PF.ARQ = TMP / "meus_dados.json"
        PF.ARQ.unlink(missing_ok=True)

    def test_campos_e_protecao(self):
        self.assertEqual(PF.campo_canonico("e-mail"), "email")
        self.assertEqual(PF.campo_canonico("meu celular"), "telefone")
        self.assertEqual(PF.campo_canonico("CEP"), "cep")
        self.assertTrue(PF.eh_proibido("senha"))
        self.assertTrue(PF.eh_proibido("cartão de crédito"))
        self.assertEqual(PF.mascarar("cpf", "12345678900"), "•••900")

    def test_salvar_preencher_remover(self):
        self.assertIn("Senha e cartão eu não guardo", PF.run({"action": "salvar", "campo": "senha", "valor": "x"}))
        self.assertIn("Guardei", PF.run({"action": "salvar", "campo": "email", "valor": "eu@ex.com"}))
        digitado = []
        with mock.patch.object(PF, "digitar", lambda v: digitado.append(v) or True):
            r = PF.run({"action": "preencher", "campo": "email"})
        self.assertEqual(digitado, ["eu@ex.com"])
        self.assertIn("Preenchi", r)
        self.assertIn("email", PF.run({"action": "ver"}))
        self.assertIn("Esqueci", PF.run({"action": "remover", "campo": "email"}))
        self.assertEqual(PF.dados(), {})


# ── modo acompanhar ──────────────────────────────────────────────────────────
class TestAcompanhar(unittest.TestCase):
    def test_sem_gemini_avisa(self):
        with mock.patch("plugins._ia.disponivel", lambda: False):
            self.assertIn("Gemini", AC.run({"action": "tela"}))

    def test_olha_a_tela(self):
        with mock.patch("plugins._ia.disponivel", lambda: True), \
                mock.patch.object(AC, "_capturar", lambda f: (b"img", "tela")), \
                mock.patch("plugins._ia.ver_imagem", lambda *a, **k: "Tem um erro de Python na linha 10."):
            r = AC.run({"action": "tela", "pergunta": "o que é esse erro?"})
        self.assertIn("erro de Python", r)

    def test_prompt(self):
        self.assertIn("pergunta", AC._prompt("e aí?", "tela"))
        self.assertIn("webcam", AC._prompt("", "câmera"))


# ── registro ─────────────────────────────────────────────────────────────────
class TestRegistro(unittest.TestCase):
    def test_niveis(self):
        from core import verificacao as V2
        self.assertEqual(V2.nivel_de("modo_faxina", {"action": "limpar"}), V2.SENSIVEL)
        self.assertEqual(V2.nivel_de("modo_faxina", {"action": "previa"}), V2.LIVRE)
        self.assertEqual(V2.nivel_de("renomear_fotos", {"action": "renomear"}), V2.SENSIVEL)
        for nome in ("organizador_abas", "modo_apresentacao", "assistente_viagem", "clone_estudo", "palpite_humor",
                     "preencher_form", "acompanhar"):
            self.assertEqual(V2.nivel_de(nome, {"action": "x"}), V2.LIVRE)
            self.assertIn("def run(", (RAIZ / "plugins" / f"{nome}.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
