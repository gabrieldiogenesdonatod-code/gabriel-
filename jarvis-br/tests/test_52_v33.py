"""Testes da 3.3 — caixa-preta, eu do futuro, gêmeo digital da loja, código em rap e o WhatsApp por voz pela ponte."""
import importlib
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests import RAIZ

from core import anonimo, caixa_preta as CP, ganchos_turno
from plugins import caixa_preta, codigo_rap as R, eu_do_futuro as E, oraculo, promocoes_loja as PL

HOJE = date(2026, 11, 15)                                    # domingo


class _Datas(date):
    """date.today() fixo nos plugins que perguntam 'que dia é hoje'."""
    hoje = HOJE

    @classmethod
    def today(cls):
        return cls.hoje


def versoes(nome: str) -> list:
    """O módulo pelo atributo do pacote E pelo sys.modules: o carregador de plugins troca o do sys.modules
    quando descobre os plugins (outros testes fazem isso antes), e o código usa os dois jeitos de importar."""
    import plugins
    out = [m for m in (getattr(plugins, nome.split(".")[-1], None) if nome.startswith("plugins.") else None,
                       sys.modules.get(nome)) if m is not None]
    out = [m for i, m in enumerate(out) if m not in out[:i]]
    return out or [importlib.import_module(nome)]


def trocar(caso: unittest.TestCase, nome: str, attr: str, valor) -> None:
    for m in versoes(nome):
        p = mock.patch.object(m, attr, valor)
        p.start()
        caso.addCleanup(p.stop)


class BaseTmp(unittest.TestCase):
    def setUp(self):
        global CP, caixa_preta, R, E, PL, oraculo, ganchos_turno
        CP, caixa_preta, R, E, PL, oraculo, ganchos_turno = (importlib.import_module(m) for m in (
            "core.caixa_preta", "plugins.caixa_preta", "plugins.codigo_rap", "plugins.eu_do_futuro", "plugins.promocoes_loja",
            "plugins.oraculo", "core.ganchos_turno"))
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for nome, attr, valor in (("plugins._lote2", "PASTA", self.tmp / "lote2"), ("core.caixa_preta", "ARQ", self.tmp / "cp.json"),
                                  ("plugins.capsula_tempo", "_ARQ", self.tmp / "capsulas.json"),
                                  ("plugins._comum", "pasta_jarvis", lambda n: (self.tmp / n).mkdir(exist_ok=True) or self.tmp / n),
                                  ("plugins._comum", "abrir_no_sistema", lambda *a, **k: None),
                                  ("plugins._comum", "mostrar", lambda *a, **k: None),
                                  ("plugins._ia", "disponivel", lambda: False)):
            trocar(self, nome, attr, valor)
        CP._anterior.update(entrada="", saida="")


# ─────────────────────────────────────────────────────────── caixa-preta ───
class TestCaixaPreta(BaseTmp):
    def test_correcao_vira_licao_e_soma_quando_repete(self):
        self.assertIsNone(CP.turno("abre a loja", "Abrindo a Loja do Windows"))
        e = CP.turno("não, não foi isso, é a planilha da Cristal Malhas", "Abrindo a planilha")
        self.assertEqual((e["pergunta"], e["resposta"], e["vezes"]), ("abre a loja", "Abrindo a Loja do Windows", 1))
        CP.turno("abre a loja de novo", "Abrindo a Loja do Windows")
        e2 = CP.turno("errado, a loja é a planilha da Cristal Malhas", "ok")
        self.assertEqual((e2["id"], e2["vezes"]), (e["id"], 2))                    # mesmo assunto: soma
        self.assertEqual(len(CP.erros()), 1)
        txt = CP.instrucao()
        self.assertIn("[CAIXA-PRETA]", txt)
        self.assertIn("planilha da Cristal Malhas", txt)
        self.assertIn("(2×)", txt)

    def test_conversa_normal_nao_registra(self):
        for a, b in (("que horas são", "São 10h"), ("obrigado", "De nada"), ("toca uma música", "Tocando")):
            self.assertIsNone(CP.turno(a, b))
        self.assertEqual(CP.erros(), [])
        self.assertEqual(CP.instrucao(), "")

    def test_assuntos_diferentes_ficam_separados_e_limite(self):
        CP.registrar("abre a loja", "x", "é a planilha da Cristal Malhas")
        CP.registrar("liga pra vó", "y", "a vó é a Dona Maria, não a Marta")
        self.assertEqual(len(CP.erros()), 2)
        self.assertEqual(len(CP.parecidos("planilha da loja")), 1)
        with mock.patch.object(CP, "MAXIMO", 3):
            for k in range(6):
                CP.registrar(f"assunto{k} numero{k}", "", f"correcao{k} diferente{k}")
            self.assertEqual(len(CP.erros()), 3)
        self.assertGreater(CP.limpar(), 0)
        self.assertEqual(CP.erros(), [])

    def test_instrucao_cabe_no_limite(self):
        for k in range(10):
            CP.registrar(f"pedido{k} " + "palavra " * 30, "resposta " * 20, f"correcao{k} " + "texto " * 30)
        self.assertLessEqual(len(CP.instrucao(limite=900)), 900)

    def test_modo_anonimo_e_convidado_nao_registram_nem_mostram(self):
        CP.registrar("abre a loja", "x", "é a planilha")
        with mock.patch.object(anonimo, "ativo", return_value=True):
            self.assertIsNone(CP.registrar("outro", "y", "correção"))
            self.assertEqual(CP.instrucao(), "")
        convidado = mock.MagicMock()
        convidado.trocas = [mock.patch.object(m, "ativo", return_value=True) for m in versoes("plugins.modo_convidado")]
        for t in convidado.trocas:
            t.start()
        try:
            self.assertIsNone(CP.registrar("outro", "y", "correção"))
            self.assertEqual(CP.instrucao(), "")
        finally:
            for t in convidado.trocas:
                t.stop()
        self.assertEqual(len(CP.erros()), 1)

    def test_ganchos_de_turno_alimentam_a_caixa(self):
        ganchos_turno._rodar("abre a loja", "Abrindo a Loja do Windows", False)
        ganchos_turno._rodar("não era isso, é a planilha", "Ah, abrindo a planilha", False)
        self.assertEqual(CP.erros()[0]["pergunta"], "abre a loja")

    def test_plugin(self):
        self.assertIn("vazia", caixa_preta.run({"action": "listar"}))
        r = caixa_preta.run({"action": "anotar", "pergunta": "a vó", "correcao": "é a minha avó, Dona Maria"})
        self.assertIn("#1", r)
        self.assertIn("Dona Maria", caixa_preta.run({"action": "listar"}))
        self.assertIn("Dona Maria", caixa_preta.run({"action": "consultar", "tema": "dona maria"}))
        self.assertIn("Não tenho", caixa_preta.run({"action": "consultar", "tema": "futebol"}))
        self.assertIn("Esqueci", caixa_preta.run({"action": "esquecer", "numero": "1"}))
        self.assertIn("Não achei", caixa_preta.run({"action": "esquecer", "numero": "1"}))

    def test_prompt_do_celular_leva_as_licoes(self):
        CP.registrar("abre a loja", "x", "é a planilha da Cristal Malhas")
        sys.path.insert(0, str(RAIZ / "celular"))
        import jarvis_celular as jc
        with mock.patch("memory.config_manager.get_user_name", return_value="Rimuru"):
            motor = jc.Motor.__new__(jc.Motor)
            motor.declaracoes = lambda: []
            self.assertIn("[CAIXA-PRETA]", motor.sistema())
            with mock.patch.object(anonimo, "ativo", return_value=True):
                self.assertNotIn("[CAIXA-PRETA]", motor.sistema())

    def test_prompt_do_pc_tem_o_gancho(self):
        src = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertIn("_cp.instrucao()", src)
        self.assertIn("caixa_preta.turno(entrada, saida)", (RAIZ / "core" / "ganchos_turno.py").read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────── eu do futuro ───
def _serie(f, dias=120, passo=1, pular_domingo=False):
    ini = HOJE - timedelta(days=dias)
    return {(ini + timedelta(k)).isoformat(): f(k) for k in range(0, dias, passo)
            if not (pular_domingo and (ini + timedelta(k)).weekday() == 6)}


class TestEuDoFuturo(BaseTmp):
    def setUp(self):
        super().setUp()
        random.seed(7)
        self.S = {"vendas da loja": _serie(lambda k: 400 + 3 * k, pular_domingo=True),
                  "tempo de estudo": _serie(lambda k: max(0.0, 90 - 0.7 * k), passo=2),
                  "km corridos": _serie(lambda k: 5.0, passo=3),
                  "hábito ler": _serie(lambda k: 1.0)}
        trocar(self, "plugins.eu_do_futuro", "_series", lambda: self.S)
        trocar(self, "plugins.eu_do_futuro", "date", _Datas)
        _Datas.hoje = HOJE

    def test_semanas_completas_e_semana_sem_registro(self):
        serie = {"2026-10-14": 10.0, "2026-10-20": 5.0, "2026-11-04": 7.0}          # começou numa quarta
        km = E.semanas(serie, HOJE, "km corridos")
        self.assertEqual(km[0][0], date(2026, 10, 19))                              # pula a 1ª semana pela metade
        self.assertEqual([v for _, v in km], [5.0, 0.0, 7.0, ])                     # semana sem corrida = 0
        vendas = E.semanas(serie, HOJE, "vendas da loja")
        self.assertEqual([v for _, v in vendas], [5.0, None, 7.0])                  # semana sem caixa = não anotou
        self.assertEqual(E.semanas({}, HOJE), [])

    def test_rumos(self):
        self.assertEqual(E.analisar(self.S["vendas da loja"], "vendas da loja", HOJE, 6)["rumo"], "subindo")
        self.assertEqual(E.analisar(self.S["tempo de estudo"], "tempo de estudo", HOJE, 6)["rumo"], "caindo")
        km = E.analisar(self.S["km corridos"], "km corridos", HOJE, 6)
        self.assertEqual(km["rumo"], "estável")                                    # 2 ou 3 corridas por semana é ruído
        hab = E.analisar(self.S["hábito ler"], "hábito ler", HOJE, 12)
        self.assertLessEqual(max(hab["cam"]), 7.0)
        self.assertIsNone(E.analisar({"2026-11-10": 5}, "km corridos", HOJE, 6))
        constante = E.analisar(_serie(lambda k: 100.0), "km corridos", HOJE, 6)
        self.assertAlmostEqual(constante["fim"], constante["agora"], places=6)
        self.assertEqual(constante["rumo"], "estável")

    def test_tendencia_amortecida_nao_promete_milagre(self):
        a = E.analisar(_serie(lambda k: 10 + 0.5 * k), "km corridos", HOJE, 24)
        linear = a["agora"] + (a["agora"] - E.analisar(_serie(lambda k: 10 + 0.5 * k, dias=92), "km corridos",
                                                       HOJE - timedelta(28), 1)["agora"]) / 4 * 104
        self.assertLess(a["fim"], linear)                                           # sobe, mas perde força
        self.assertGreater(a["fim"], a["agora"])

    def test_unidades(self):
        self.assertEqual(E.ritmo("água bebida", 14000), "2.000 ml por dia")
        self.assertEqual(E.ritmo("tempo de estudo", 240), "4 h por semana")
        self.assertEqual(E.valor("hábito ler", 7), "7 dias")
        self.assertEqual(E.valor("hábito ler", 1), "1 dia")
        self.assertEqual(E.total("vendas da loja", 130976.71), "R$ 130.977")
        self.assertEqual(E.total("água bebida", 321000), "321 litros")

    def test_projecao_e_conversa_sem_ia(self):
        r = E.run({"action": "projecao", "meses": "6"})
        self.assertIn("vendas da loja: agora", r)
        self.assertIn("não destino", r)
        c = E.run({"action": "conversar", "pergunta": "a loja vai melhorar?"})
        self.assertIn("aqui é você, daqui a 6 meses", c)
        self.assertIn("a loja vai melhorar?", c)
        self.assertIn("conselho para esta semana", c)

    def test_conversa_com_ia_e_sem_dados(self):
        with mock.patch.object(importlib.import_module("plugins._ia"), "perguntar", return_value="Oi, sou você em 2027. Estuda mais.") as ia:
            self.assertIn("sou você em 2027", E.run({"action": "conversar"}))
            self.assertIn("SOMENTE", ia.call_args[0][0])                            # não inventar
        self.S.clear()
        self.assertIn("4 semanas", E.run({"action": "projecao"}))

    def test_e_se(self):
        r = E.run({"action": "e_se", "serie": "vendas", "mudanca": "10"})
        self.assertIn("a mais", r)
        r2 = E.run({"action": "e_se", "serie": "estudar", "ritmo": "4", "meses": "6"})
        self.assertIn("4 h por semana", r2)
        self.assertIn("104 h", r2)                                                  # 4 h × 26 semanas
        self.assertIn("De qual número?", E.run({"action": "e_se", "serie": "xadrez", "mudanca": "10"}))

    def test_selar_vira_capsula_e_conferir(self):
        abre = importlib.import_module("plugins.capsula_tempo").data_de("em 3 meses")   # a cápsula conta do dia de verdade
        r = E.run({"action": "selar", "meses": "3"})
        self.assertIn(f"cápsula do tempo que abre em {abre:%d/%m/%Y}", r)
        caps = json.loads((self.tmp / "capsulas.json").read_text(encoding="utf-8"))["capsulas"]
        self.assertEqual(caps[0]["abre"], abre.isoformat())
        self.assertIn("confere o eu do futuro", caps[0]["mensagem"])
        self.assertIn("ainda não fechou", E.run({"action": "conferir"}))
        for k in range(1, 23):                                                      # 3 semanas depois
            d = HOJE + timedelta(k)
            if d.weekday() != 6:
                self.S["vendas da loja"][d.isoformat()] = 760.0
        _Datas.hoje = HOJE + timedelta(22)
        c = E.run({"action": "conferir"})
        self.assertIn("vendas da loja: previ", c)
        self.assertIn("em 4 semana(s)", c)

    def test_grafico(self):
        r = E.run({"action": "grafico"})
        self.assertIn("Gráfico aberto", r)
        html = next((self.tmp / "Eu do futuro").glob("*.html")).read_text(encoding="utf-8")
        self.assertEqual(html.count("<svg"), 4)
        self.assertNotIn("nan", html.lower().replace("nana", ""))


# ─────────────────────────────────────────────────────────── gêmeo da loja ───
class TestGemeoLoja(BaseTmp):
    def setUp(self):
        super().setUp()
        random.seed(3)
        self.serie = {}
        hoje = date.today()
        for k in range(1, 50):
            d = hoje - timedelta(k)
            if d.weekday() != 6:                                                    # domingo a loja fecha
                self.serie[d.isoformat()] = (900 if d.weekday() == 5 else 500) + random.uniform(-50, 50)
        p = mock.patch.object(PL, "_vendas_serie", lambda: self.serie)
        p.start()
        self.addCleanup(p.stop)

    def test_contas(self):
        s = PL.simular(1000, 0.2, 2.0, 1.0, 0.5)
        self.assertAlmostEqual(s["pecas"], 1.5625)
        self.assertAlmostEqual(s["receita"], 1250)
        self.assertAlmostEqual(s["lucro"], 1250 - 500 * 1.5625)
        self.assertAlmostEqual(s["empate"], 0.5 / 0.3)                              # precisa vender +67% para empatar
        self.assertTrue(math.isinf(PL.simular(1000, 0.6, 2.0, 1.0, 0.5)["empate"]))
        self.assertAlmostEqual(PL.desconto_efetivo("leve_pague", [3, 2]), 1 / 3)
        self.assertAlmostEqual(PL.desconto_efetivo("desconto", [20]), 0.2)
        self.assertEqual(PL.melhor_desconto(2.0, 0.6), 0.2)                         # d* = (1 − e·m)/(1 − e)
        self.assertEqual(PL.melhor_desconto(1.5, 0.5), 0.0)
        for e, d, c in ((2.3, 0.15, 0.6), (1.2, 0.3, 1.0), (3.0, 0.1, 0.25)):     # a conta volta: simular ↔ aprender
            razao = PL.simular(1.0, d, e, c)["receita"]
            self.assertAlmostEqual(PL.elasticidade_vista(razao, d, c), e, places=6)

    def test_oraculo_nao_inventa_venda_com_a_loja_fechada(self):
        prev = oraculo.prever_semana(self.serie, oraculo.segunda_que_vem(date.today()))
        self.assertEqual(len(prev), 6)
        self.assertNotIn(6, {date.fromisoformat(d).weekday() for d in prev})
        curto = {(date.today() - timedelta(k)).isoformat(): 100.0 for k in range(1, 11) if (date.today() - timedelta(k)).weekday() != 6}   # 8 ou 9 dias, em qualquer dia da semana
        self.assertEqual(len(oraculo.prever_semana(curto, date.today())), 7)        # pouco histórico: não assume fechado

    def test_prever_registrar_conferir_aprender(self):
        r = PL.run({"action": "prever", "valor": "20"})
        for trecho in ("Gêmeo da loja: 20% de desconto por 7 dia(s)", "Sem promoção", "Para o lucro empatar", "+67%",
                       "chute inicial", "margem de 50%"):
            self.assertIn(trecho, r)
        self.assertIn("leve 3 pague 2", PL.run({"action": "prever", "valor": "leve 3 pague 2", "margem": "60"}))
        self.assertIn("registrada: leve 3 pague 2", PL.run({"action": "registrar"}))
        self.assertIn("acaba em", PL.run({"action": "conferir"}))
        ini = date.today() - timedelta(10)
        for k in range(7):
            d = (ini + timedelta(k)).isoformat()
            if d in self.serie:
                self.serie[d] *= 1.3
        self.assertIn("já acabou", PL.run({"action": "registrar", "valor": "20", "inicio": ini.strftime("%d/%m/%Y")}))
        c = PL.run({"action": "conferir"})
        self.assertIn("sobre o normal", c)
        e, n = PL.elasticidade("desconto")
        self.assertEqual(n, 1)
        self.assertNotEqual(e, PL.E0["desconto"])
        a = PL.run({"action": "aprendizado"})
        self.assertIn("aprendido com 1 promoção", a)
        self.assertIn("Margem da loja que eu uso: 60%", a)
        self.assertIn(ini.isoformat(), PL.dias_de_promocao(PL._gemeo()))

    def test_sem_historico_usa_o_que_voce_disse(self):
        self.serie.clear()
        self.assertIn("histórico do caixa", PL.run({"action": "prever", "valor": "20"}))
        self.assertIn("pelo que você me disse", PL.run({"action": "prever", "valor": "20", "vendas": "3000"}))
        self.assertIn("PREJUÍZO", PL.run({"action": "prever", "valor": "60", "vendas": "3000", "margem": "50"}))

    def test_acoes_antigas_iguais(self):
        self.assertEqual(PL.run({"action": "desconto", "preco": "60", "custo": "30", "valor": "20"}),
                         "Preço efetivo R$ 48,00 por peça (20% de desconto); margem cai para 37.5%.")
        self.assertEqual(PL.run({"action": "leve_pague", "preco": "50", "custo": "20", "valor": "3 2"}),
                         "Preço efetivo R$ 33,33 por peça (33% de desconto); margem cai para 40.0%.")
        self.assertEqual(PL.run({"action": "progressivo", "preco": "100", "valor": "5 10 15"}),
                         "1 peça(s): R$ 95,00 cada; 2 peça(s): R$ 90,00 cada; 3 peça(s): R$ 85,00 cada")
        self.assertIn("Cristal Malhas", PL.run({"action": "texto", "produto": "moletom", "valor": "20% off"}))
        self.assertEqual(PL.run({"action": "desconto", "valor": "20"}), "Qual o preço da peça?")   # antes: divisão por zero


# ─────────────────────────────────────────────────────────── código em rap ───
CODIGO = '''
import json
from pathlib import Path

def carregar(caminho, padrao=None):
    """Lê um JSON do disco. Pura."""
    if not caminho:
        return padrao
    for tentativa in range(3):
        try:
            return json.loads(Path(caminho).read_text())
        except OSError:
            continue
    return padrao
'''


class TestCodigoRap(BaseTmp):
    def test_estrutura_python_e_outras_linguagens(self):
        e = R.estrutura(CODIGO)
        self.assertEqual((e["params"], e["ifs"], e["loops"], e["trys"], e["returns"]), (["caminho", "padrao"], 1, 1, 1, 3))
        self.assertIn("json", e["imports"])
        self.assertIn("loads", e["chamadas"])
        self.assertTrue(e["doc"].startswith("Lê um JSON"))
        js = R.estrutura("function soma(a, b) {\n if (a > b) return a;\n for (const x of [a]) {}\n return a + b;\n}")
        self.assertFalse(js["python"])
        self.assertEqual((js["funcoes"], js["ifs"], js["loops"], js["returns"]), (["soma"], 1, 1, 2))

    def test_versos_offline_rimam_em_pares_e_sem_plural_quebrado(self):
        v = R.versos_offline("carregar", R.estrutura(CODIGO), random.Random(1))
        self.assertEqual(len(v) % 2, 0)
        txt = "\n".join(v)
        for trecho in ("caminho e padrao", "Uma decisão", "Um loop", "uma rede de proteção", "return", "Lê um JSON do disco"):
            self.assertIn(trecho, txt)
        self.assertNotIn("(s)", txt)
        self.assertNotIn("Pura", txt)

    def test_tira_segredos_antes_da_ia(self):
        src = 'KEY = "AIzaSyA1234567890abcdefghijklmnopqrstuv"\npassword="minha-senha-123"\ntok = "sk-abcdefghijklmnopqrstuvwx"\nx = 5\n'
        limpo = R.sem_segredos(src)
        for segredo in ("AIzaSy", "minha-senha", "sk-abc"):
            self.assertNotIn(segredo, limpo)
        self.assertIn("x = 5", limpo)

    def test_fontes(self):
        nome, codigo = R.fonte({"funcao": "prever_semana"})
        self.assertIn("prever_semana", nome)
        self.assertTrue(codigo.lstrip().startswith("def prever_semana"))
        nome, codigo = R.fonte({"arquivo": "estudos.py", "funcao": "semana"})
        self.assertTrue(codigo.startswith("def semana"))
        chave = self.tmp / "api_keys.json"
        chave.write_text('{"gemini": "x"}', encoding="utf-8")
        self.assertIn("não vou ler", R.fonte({"arquivo": str(chave)}))
        self.assertIn("Não achei", R.fonte({"arquivo": "nao_existe_mesmo.py"}))
        self.assertIn("Qual código?", R.fonte({}))
        falso = mock.MagicMock(paste=lambda: "def f():\n    return 1\n")
        with mock.patch.dict(sys.modules, {"pyperclip": falso}):
            self.assertEqual(R.fonte({"codigo": "o que eu copiei"})[0], "o código que você copiou")

    def test_rap_salva_e_vai_para_o_quadro(self):
        with mock.patch.object(R, "_no_quadro", return_value=" Está no quadro: http://x.") as q:
            r = R.run({"action": "rap", "codigo": CODIGO, "quadro": "sim"})
            q.assert_called_once()
        self.assertIn("Rap desse código", r)
        self.assertIn("sem IA", r)
        self.assertEqual(len(list((self.tmp / "Rap").glob("codigo_*.txt"))), 1)
        self.assertIn("Rap desse código", R.run({"action": "ultimo"}))

    def test_rap_com_ia_recebe_codigo_sem_segredo(self):
        resposta = {"titulo": "JSON no beat", "resumo": "lê JSON", "versos": ["a", "b", "c", "d"], "bpm": 95}
        with mock.patch.object(importlib.import_module("plugins._ia"), "perguntar_json", return_value=resposta) as ia:
            r = R.run({"action": "rap", "codigo": 'TOKEN = "AIzaSyA1234567890abcdefghijklmnopqrstuv"\n' + CODIGO})
        self.assertIn("JSON no beat (BPM 95)", r)
        self.assertNotIn("AIzaSy", ia.call_args[0][0])
        self.assertIn("NÃO copie", ia.call_args[0][0])

    def test_desafio_esconde_o_nome_e_confere_palpite(self):
        cand = [("prever_semana", "plugins/oraculo.py", "def prever_semana(serie, inicio):\n    return {}\n")]
        resposta = {"titulo": "x", "versos": ["Sou a prever_semana, rimando aqui", "prever semana no beat", "c", "d"]}
        with mock.patch.object(R, "candidatas", lambda: cand), \
                mock.patch.object(importlib.import_module("plugins._ia"), "perguntar_json", return_value=resposta):
            r = R.run({"action": "desafio"})
        self.assertNotIn("prever_semana", r)
        self.assertNotIn("prever semana", r.lower())
        self.assertIn("███", r)
        self.assertIn("Dica: ela mora em plugins/oraculo.py", R.run({"action": "palpite", "palpite": "caixa"}))
        self.assertIn("Acertou! Era a prever_semana", R.run({"action": "palpite", "palpite": "prever semana"}))
        self.assertIn("Não tem desafio", R.run({"action": "palpite", "palpite": "x"}))
        with mock.patch.object(R, "candidatas", lambda: cand):
            R.run({"action": "desafio"})
        R.run({"action": "palpite", "palpite": "a"})
        R.run({"action": "palpite", "palpite": "b"})
        self.assertIn("Era a prever_semana", R.run({"action": "palpite", "palpite": "c"}))  # 3 erros: revela

    def test_candidatas_sao_funcoes_publicas_do_jarvis(self):
        cs = R.candidatas(random.Random(2))
        self.assertTrue(cs)
        for nome, arq, codigo in cs:
            self.assertFalse(nome.startswith("_"))
            self.assertTrue(arq.startswith(("plugins/", "core/")))
            self.assertIn(f"def {nome}", codigo)

    @unittest.skipUnless(shutil.which("git"), "sem git")
    def test_rap_do_commit(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
        g("init", "-q")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        (repo / "m.py").write_text("def soma(a, b):\n    return a + b\n", encoding="utf-8")
        g("add", ".")
        g("commit", "-qm", "soma aceita None")
        r = R.run({"action": "commit", "pasta": str(repo)})
        self.assertIn("soma aceita None", r)
        self.assertIn("m.py", r)
        self.assertIn("não é um repositório Git", R.run({"action": "commit", "pasta": str(self.tmp)}))


# ─────────────────────────────────────────────────────────── WhatsApp por voz ───
class TestWhatsappPelaPonte(unittest.TestCase):
    def setUp(self):
        from actions import send_message
        self.sm = send_message

    def _ponte(self, pronto=True, achados=(), enviou=True):
        """Troca a ponte do WhatsApp por uma de mentira (no sys.modules E no pacote plugins)."""
        import contextlib

        import plugins
        W = mock.MagicMock(pronto=lambda: pronto)
        WP = mock.MagicMock(achar=lambda nome: list(achados))
        WP.mandar_como_dono.return_value = enviou
        pilha = contextlib.ExitStack()
        pilha.enter_context(mock.patch.dict(sys.modules, {"plugins._whatsapp": W, "plugins._whatsapp_pessoal": WP}))
        pilha.enter_context(mock.patch.object(plugins, "_whatsapp", W, create=True))
        pilha.enter_context(mock.patch.object(plugins, "_whatsapp_pessoal", WP, create=True))
        return pilha, WP

    def test_envia_pela_ponte_e_confirma(self):
        ctx, WP = self._ponte(achados=[{"id": "5562999@c.us", "nome": "Ana", "numero": "5562999"}])
        with ctx:
            r = self.sm._send_whatsapp_ponte("Ana", "Oi, Ana!")
        self.assertIn("status=done", r)
        self.assertIn("verified=true", r)
        WP.mandar_como_dono.assert_called_once_with("5562999@c.us", "Oi, Ana!")

    def test_pergunta_quando_tem_mais_de_um_e_falha_honesta(self):
        ctx, _ = self._ponte(achados=[{"id": "1", "nome": "Ana Paula"}, {"id": "2", "nome": "Ana Clara"}])
        with ctx:
            self.assertIn("status=ask", self.sm._send_whatsapp_ponte("Ana", "oi"))
        ctx, _ = self._ponte(achados=[])
        with ctx:
            self.assertIn("status=failed", self.sm._send_whatsapp_ponte("Zé", "oi"))
        ctx, _ = self._ponte(achados=[{"id": "1", "nome": "Ana"}], enviou=False)
        with ctx:
            self.assertIn("não confirmou", self.sm._send_whatsapp_ponte("Ana", "oi"))

    def test_sem_ponte_volta_para_o_caminho_antigo(self):
        ctx, _ = self._ponte(pronto=False)
        with ctx:
            self.assertIsNone(self.sm._send_whatsapp_ponte("Ana", "oi"))

    def test_send_whatsapp_usa_a_ponte_primeiro(self):
        with mock.patch.object(self.sm, "_send_whatsapp_ponte", return_value="status=done action=send_message") as p:
            self.assertEqual(self.sm._send_whatsapp("Ana", "oi"), "status=done action=send_message")
            p.assert_called_once_with("Ana", "oi")


# ─────────────────────────────────────────────────────────── quem pode usar ───
class TestNiveis33(unittest.TestCase):
    def test_visita_nao_ve_os_seus_dados_mas_joga_o_desafio(self):
        from core import verificacao as V
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for nome in ("caixa_preta", "eu_do_futuro"):
            self.assertEqual(V.nivel_de(nome, {"action": "listar"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("promocoes_loja", {"action": "prever"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("codigo_rap", {"action": "rap"}), V.SENSIVEL)
        self.assertEqual(V.nivel_de("codigo_rap", {"action": "desafio"}), V.LIVRE)
        with mock.patch.object(V, "ARQ_LOG", tmp / "log.json"):
            trocas = [mock.patch.object(m, "ativo", return_value=True) for m in versoes("plugins.modo_convidado")]
            for t in trocas:
                t.start()
            try:
                self.assertIn("MODO CONVIDADO", V.autorizar("caixa_preta", {"action": "listar"}))
                self.assertIn("MODO CONVIDADO", V.autorizar("promocoes_loja", {"action": "prever"}))
                self.assertIsNone(V.autorizar("codigo_rap", {"action": "desafio"}))
            finally:
                for t in trocas:
                    t.stop()


# ─────────────────────────────────────────────────────────── busca de ferramentas ───
class TestBusca33(unittest.TestCase):
    CASOS = {"mostra a caixa-preta dos seus erros": "caixa_preta", "você já errou alguma coisa comigo": "caixa_preta",
             "como eu vou estar daqui a 6 meses": "eu_do_futuro", "fala com o meu eu do futuro": "eu_do_futuro",
             "simula 20% de desconto na loja e vê se dá lucro": "promocoes_loja",
             "o que você aprendeu das minhas promoções": "promocoes_loja", "faz um rap explicando esse código": "codigo_rap",
             "rap do último commit": "codigo_rap", "me desafia a adivinhar a função": "codigo_rap"}

    def test_acha_os_novos(self):
        from core import registro_ferramentas
        from plugins import catalogo
        decls = registro_ferramentas.declaracoes()
        erros = [q for q, alvo in self.CASOS.items() if alvo not in [d["name"] for d in catalogo.buscar(decls, q, 3)]]
        self.assertEqual(erros, [])


if __name__ == "__main__":
    unittest.main()
