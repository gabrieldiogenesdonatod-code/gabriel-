"""Testes da 3.6 — OMEGA, livro-razão, experimentos sorteados, metacognição, modos impossíveis e as correções da varredura."""
import gc
import importlib
import random
import re
import shutil
import sqlite3
import tempfile
import time
import unittest
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests import RAIZ
from tests.test_52_v33 import trocar, versoes

HOJE = date(2026, 11, 1)                                             # domingo


class _Dia(date):
    hoje = HOJE

    @classmethod
    def today(cls):
        return cls.hoje


class _Agora(datetime):
    hora = 9

    @classmethod
    def now(cls, tz=None):
        return datetime.combine(_Dia.hoje, datetime.min.time()).replace(hour=cls.hora)


class Base(unittest.TestCase):
    def setUp(self):
        global L, PLV, E, M, PM, C, O, PO
        L, PLV, E, M, PM, C, O, PO = (importlib.import_module(m) for m in (
            "core.livro_razao", "plugins.livro_razao", "plugins.experimento_vida", "core.metacognicao", "plugins.metacognicao",
            "core.cerebro", "core.omega", "plugins.omega"))
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(L.fechar)
        L.fechar()
        self.falas = []
        for nome, attr, valor in (
                ("core.livro_razao", "ARQ", self.tmp / "livro.db"), ("core.livro_razao", "CHAVE", self.tmp / "livro.key"),
                ("core.metacognicao", "ARQ", self.tmp / "meta.json"), ("core.cerebro", "ARQ", self.tmp / "cerebro.json"),
                ("core.omega", "ARQ", self.tmp / "omega.json"), ("plugins._lote2", "PASTA", self.tmp / "lote2"),
                ("plugins._comum", "pasta_jarvis", lambda n: (self.tmp / n).mkdir(exist_ok=True) or self.tmp / n),
                ("plugins._comum", "abrir_no_sistema", lambda *a, **k: None),
                ("plugins._comum", "mostrar", lambda *a, **k: None),
                ("plugins._comum", "avisar", lambda pl, t, e="": self.falas.append(t)),
                ("core.anonimo", "ARQ", self.tmp / "anonimo.json"),
                ("plugins.memoria_inteligente", "ARQUIVO", self.tmp / "memoria_inteligente.db")):
            trocar(self, nome, attr, valor)
        anonimo = importlib.import_module("core.anonimo")
        anonimo._estado["ativo"] = None
        self.addCleanup(anonimo._estado.update, {"ativo": None})
        C._cache.pop("modelo", None)
        C._turno.clear()
        C._anterior["chave"] = None
        _Dia.hoje, _Agora.hora = HOJE, 9


# ─────────────────────────────────────────────────────────── livro-razão ───
class TestLivroRazao(Base):
    def encher(self, n=30):
        for i in range(n):
            L.ferramenta("musica", {"action": "tocar", "nome": f"faixa {i}"}, "Tocando.")

    def mexer(self, sql, *args):
        L.fechar()
        with sqlite3.connect(str(L.ARQ)) as c:
            c.execute(sql, args)
        c.close()

    def test_corrente_integra_e_cada_tipo_de_adulteracao(self):
        self.encher()
        cod = L.selar()
        v = L.verificar()
        self.assertEqual((v["ok"], v["blocos"]), (True, 31))
        self.mexer("UPDATE blocos SET dados = replace(dados, 'faixa 9', 'faixa X') WHERE n = 10")
        self.assertEqual((L.verificar()["erro"]["n"], "alterado" in L.verificar()["erro"]["motivo"]), (10, True))
        self.mexer("UPDATE blocos SET dados = replace(dados, 'faixa X', 'faixa 9') WHERE n = 10")
        self.assertTrue(L.verificar()["ok"])                                 # desfazendo a mudança, volta a fechar
        self.mexer("DELETE FROM blocos WHERE n = 20")
        self.assertIn("apagado", L.verificar()["erro"]["motivo"])
        self.assertFalse(L.conferir_selo(cod)["ok"])

    def test_corte_depois_do_selo_e_chave_falsa(self):
        self.encher(10)
        cod = L.selar()
        self.encher(5)
        self.assertTrue(L.conferir_selo(cod)["ok"])
        self.mexer("DELETE FROM blocos WHERE n >= 11")                       # corta o fim, inclusive o bloco do selo
        self.assertIn("cortado", L.verificar()["erro"]["motivo"])
        self.assertIn("cortado", L.conferir_selo(cod)["motivo"])
        outra = self.tmp / "outra.key"
        outra.write_bytes(b"x" * 32)
        self.assertIn("assinatura", L.verificar(chave=outra)["erro"]["motivo"])
        self.assertFalse(L.conferir_selo("abc")["ok"])
        self.assertIn("não bate", L.conferir_selo("1-ffffffffffff")["motivo"])

    def test_texto_longo_segredos_e_modo_anonimo(self):
        L.ferramenta("contas", {"action": "guardar", "senha": "abc123", "token_api": "zzz", "site": "x" * 400}, "ok")
        d = L.consultar()[0]["dados"]
        self.assertEqual((d["a"]["senha"], d["a"]["token_api"]), ("***", "***"))
        self.assertEqual((d["a"]["site"][:41], len(d["a"]["site"])), ("x" * 40 + "…", 40 + 2 + 16))    # começo + hash do resto
        anonimo = importlib.import_module("core.anonimo")
        anonimo.definir(True)
        L.ferramenta("musica", {"action": "tocar"}, "ok")
        self.assertIn("anônimo", PLV.run({"action": "anotar", "texto": "segredo"}))
        anonimo.definir(False)
        tipos = [b["tipo"] for b in L.consultar()]
        self.assertEqual(tipos, ["ferramenta", "anonimo", "anonimo"])        # só o liga/desliga ficou marcado
        self.assertTrue(L.verificar()["ok"])

    def test_resultado_e_segredo_nao_ficam_guardados(self):
        """O resultado de uma ferramenta pode trazer senha copiada ou mensagem de outra pessoa: só a digital entra."""
        L.ferramenta("historico_clipboard", {"action": "ver"}, "Copiado: MinhaSenhaSecreta123")
        L.ferramenta("cofre_condicional", {"action": "guardar", "mensagem": "o segredo é X9", "condicao": "se eu sumir"}, "Guardado.")
        L.ferramenta("consulta", {"action": "ver", "dados": {"cpf": "123.456", "nome": "Ana"}, "lista": [{"token": "tk-9"}]}, "ok")
        self.assertIn("bloco #4", PLV.run({"action": "anotar", "texto": "combinado " + "b" * 300}))
        b = L.consultar()
        self.assertEqual(b[0]["dados"]["r"], {"letras": 29, "digital": L.digital("Copiado: MinhaSenhaSecreta123")})
        self.assertEqual(b[1]["dados"]["a"], {"action": "guardar"})                          # de cofre, só a ação
        self.assertEqual((b[2]["dados"]["a"]["dados"], b[2]["dados"]["a"]["lista"]), ({"cpf": "***", "nome": "Ana"}, [{"token": "***"}]))
        self.assertEqual(b[3]["dados"]["texto"], "combinado " + "b" * 300)                   # a nota que você dita fica inteira
        L.fechar()
        bruto = b"".join(a.read_bytes() for a in self.tmp.glob("livro.db*"))
        for proibido in (b"MinhaSenhaSecreta123", b"o segredo", b"se eu sumir", b"123.456", b"tk-9"):
            self.assertNotIn(proibido, bruto)
        self.assertTrue(L.verificar()["ok"])
        self.assertIn("usei historico_clipboard (ver)", PLV.run({"action": "provar"}))

    def test_demonstracao_nao_toca_no_livro_de_verdade(self):
        self.assertFalse(L.demonstrar_adulteracao()["ok"])                   # vazio: nada para demonstrar
        self.encher(12)
        antes = L.verificar()["topo"]
        r = L.demonstrar_adulteracao()
        self.assertEqual((r["ok"], r["detectado"], r["original_intacto"], r["bloco_alterado"]), (True, True, True, 6))
        self.assertEqual(L.verificar()["topo"], antes)
        self.assertIn("percebi na hora", PLV.run({"action": "demonstrar"}))

    def test_plugin_provar_anotar_relatorio(self):
        self.assertIn("vazio", PLV.run({"action": "estado"}))
        self.encher(3)
        L.ferramenta("clima", {"action": "agora"}, "Erro: falhou")
        r = PLV.run({"action": "anotar", "texto": "combinei com o fornecedor a entrega para o dia 20"})
        self.assertIn("bloco #5", r)
        p = PLV.run({"action": "provar", "periodo": "hoje"})
        for trecho in ("usei musica (tocar)", "usei clima (agora) — falhou", "você registrou: combinei", "Corrente íntegra: 5"):
            self.assertIn(trecho, p)
        self.assertIn("1 registro(s)", PLV.run({"action": "provar", "periodo": "hoje", "texto": "clima"}))
        self.assertIn("Não tenho nenhum registro ontem", PLV.run({"action": "provar", "periodo": "ontem"}))
        self.assertIn("Relatório de auditoria aberto", PLV.run({"action": "relatorio"}))
        self.assertTrue(list((self.tmp / "Auditoria").glob("*.html")))
        cod = PLV.run({"action": "selar"}).split("Código: ")[1].split(".")[0]
        self.assertIn("Selo confere", PLV.run({"action": "conferir_selo", "codigo": cod}))
        self.assertIn("Último selo", PLV.run({"action": "estado"}))

    def test_janela_do_periodo(self):
        agora = datetime(2026, 11, 16, 15, 30)
        ini, fim, nome = PLV.janela("ontem 15h", agora)
        self.assertEqual((datetime.fromtimestamp(ini), datetime.fromtimestamp(fim), nome),
                         (datetime(2026, 11, 15, 15), datetime(2026, 11, 15, 16), "ontem às 15h"))
        self.assertEqual(datetime.fromtimestamp(PLV.janela("12/11", agora)[0]), datetime(2026, 11, 12))
        self.assertEqual(PLV.janela("", agora)[2], "hoje")
        self.assertEqual(PLV.janela("semana", agora)[2], "nos últimos 7 dias")

    def test_selo_diario_e_confirmacao_na_tela(self):
        self.encher(2)
        PLV.passo(None)
        PLV.passo(None)
        self.assertEqual(L.estado()["selos"], 1)                             # um por dia
        confirm = importlib.import_module("core.confirm")
        feito = []
        with mock.patch.object(confirm, "_show_cb", lambda *a, **k: None, create=True), \
                mock.patch.object(confirm, "_hide_cb", None, create=True):
            confirm.request("teste-livro", "Desligar o PC?", "detalhe", lambda: feito.append(1) or "ok")
            confirm.resolve(False)
        self.assertEqual(feito, [])
        ult = [b for b in L.consultar() if b["tipo"] == "confirmacao"][-1]["dados"]
        self.assertEqual((ult["titulo"], ult["resposta"]), ("Desligar o PC?", "cancelado"))

    def test_ganchos_no_codigo(self):
        main = (RAIZ / "main.py").read_text(encoding="utf-8")
        self.assertEqual(main.count("_livro.ferramenta("), 2)                 # ferramenta normal + cérebro sem internet
        self.assertIn("livro_razao.ferramenta(nome, args, str(r))", (RAIZ / "celular" / "jarvis_celular.py").read_text(encoding="utf-8"))
        self.assertIn("livro_razao.ligar_ao_organismo(org)", (RAIZ / "biological_core" / "__init__.py").read_text(encoding="utf-8"))
        self.assertIn('_livro(p, "autorizado", origem)', (RAIZ / "biological_core" / "autorizacao.py").read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────── experimentos na vida ───
INI = date(2026, 11, 2)                                              # segunda


def _vendas(plano, efeito, seed):
    r, out = random.Random(seed), {}
    for d, cond in plano.items():
        dia = date.fromisoformat(d)
        if dia.weekday() != 6:                                       # domingo a loja fecha
            out[d] = ((900 if dia.weekday() == 5 else 500) + r.uniform(-50, 50)) * (1 + efeito if cond == "com" else 1)
    return out


class TestSorteioEAnalise(unittest.TestCase):
    def setUp(self):
        global E
        E = importlib.import_module("plugins.experimento_vida")

    def test_sorteio_equilibrado_por_dia_da_semana(self):
        for seed in range(20):
            plano = E.sortear(INI, 14, random.Random(seed))
            self.assertEqual(sum(1 for v in plano.values() if v == "com"), 7)
            for k in range(7):                                        # cada dia da semana: um COM e um SEM
                par = {plano[(INI + timedelta(k)).isoformat()], plano[(INI + timedelta(k + 7)).isoformat()]}
                self.assertEqual(par, {"com", "sem"})
        self.assertEqual(E.sortear(INI, 14, random.Random(3)), E.sortear(INI, 14, random.Random(3)))
        g10 = E.estratos(INI, 10)
        self.assertEqual((len(g10), len(g10[-1]), sorted(len(g) for g in g10[:-1])), (4, 4, [2, 2, 2]))
        self.assertLessEqual(abs(sum(1 if v == "com" else -1 for v in E.sortear(INI, 9, random.Random(1)).values())), 1)

    def test_acha_efeito_de_verdade_e_nao_inventa(self):
        plano = E.sortear(INI, 28, random.Random(11))
        grupos = E.estratos(INI, 28)
        sim = E.analisar(plano, _vendas(plano, 0.25, 1), grupos, random.Random(1))
        nao = E.analisar(plano, _vendas(plano, 0.0, 1), grupos, random.Random(1))
        self.assertLess(sim["p"], 0.01)
        self.assertAlmostEqual(sim["pct"], 25, delta=6)
        self.assertGreater(nao["p"], 0.2)
        self.assertLess(nao["enxergaria_pct"], 15)                    # o equilíbrio por dia da semana deixa a lupa fina
        self.assertIn("AUMENTA vendas da loja", E.veredito(sim, "vendas da loja", "postar no status"))
        self.assertIn("não achei diferença", E.veredito(nao, "vendas da loja", "postar no status"))
        self.assertIn("PARCIAL", E.veredito(nao, "vendas da loja", "x", final=False))
        pior = E.analisar(plano, _vendas(plano, -0.25, 1), grupos, random.Random(1))
        self.assertIn("DIMINUI", E.veredito(pior, "vendas da loja", "fechar mais cedo"))

    def test_alarme_falso_fica_no_combinado(self):
        falsos = 0
        for seed in range(120):
            plano = E.sortear(INI, 14, random.Random(seed + 500))
            r = E.analisar(plano, _vendas(plano, 0.0, seed), E.estratos(INI, 14), random.Random(seed), voltas=300)
            falsos += r["p"] <= 0.05
        self.assertLessEqual(falsos, 12)                              # ~5% de 120, com folga para o acaso

    def test_poucos_dias_nao_conclui_e_formatos(self):
        plano = E.sortear(INI, 14, random.Random(2))
        poucos = dict(list(_vendas(plano, 0.2, 1).items())[:4])
        self.assertIsNone(E.analisar(plano, poucos, E.estratos(INI, 14), random.Random(1)))
        self.assertEqual((E.fmt("vendas da loja", 1234.5), E.fmt("nota", 7.25), E.fmt("hábito ler", 0.8), E.fmt("água bebida", 1850.4),
                          E.fmt("km corridos", 5.25)), ("R$ 1.234,50", "7,2", "80% dos dias", "1850 ml", "5,2 km"))
        self.assertEqual(E.achar_serie("as vendas da loja", ["vendas da loja", "água bebida"]), "vendas da loja")
        self.assertEqual(E.achar_serie("ler", ["hábito ler", "água bebida"]), "hábito ler")
        self.assertIsNone(E.achar_serie("futebol", ["vendas da loja"]))


class TestExperimentoVida(Base):
    def setUp(self):
        super().setUp()
        self.S = {"vendas da loja": {(HOJE - timedelta(k)).isoformat(): 500.0 for k in range(1, 30)}}
        trocar(self, "plugins.experimento_vida", "_series", lambda: self.S)
        trocar(self, "plugins.experimento_vida", "date", _Dia)
        trocar(self, "plugins.experimento_vida", "datetime", _Agora)

    def test_do_plano_selado_ao_veredito(self):
        self.assertIn("Nenhum experimento rodando", E.run({"action": "hoje"}))
        r = E.run({"action": "criar", "tratamento": "postar no status da loja", "medida": "vendas", "dias": "14"})
        for trecho in ("Experimento #1 criado", "7 dias COM e 7 SEM", "sozinho, por vendas da loja", "Plano selado no livro-razão", "amanhã é dia"):
            self.assertIn(trecho, r)
        self.assertEqual([b["tipo"] for b in L.consultar()], ["experimento.plano"])       # selado antes de qualquer dado
        exp = E._est()["experimentos"][0]
        self.assertEqual(exp["inicio"], "2026-11-02")
        lembrou = []
        trocar(self, "plugins.memoria_inteligente", "lembrar", lambda *a, **k: lembrou.append(a))
        for k in range(1, 17):
            _Dia.hoje = HOJE + timedelta(k)
            self.S["vendas da loja"].update(_vendas({d: c for d, c in exp["plano"].items() if d == _Dia.hoje.isoformat()}, 0.3, k))
            E.passo(None)
            if k == 2:
                self.assertIn("hoje é dia", E.run({"action": "hoje"}))
                self.assertIn("não seguiu", E.run({"action": "cumpri", "valor": "não"}))
            if k == 5:
                self.assertIn("ainda é cedo", E.run({"action": "resultado"}))
        self.assertEqual(sum("hoje é dia" in f for f in self.falas), 14)                  # avisou o sorteio todo dia, uma vez
        final = E.run({"action": "resultado", "experimento": "status"})
        self.assertIn("terminado", final)
        self.assertIn("AUMENTA vendas da loja", final)
        self.assertIn("funciona", E.run({"action": "listar"}))
        self.assertEqual(len(lembrou), 1)                                                 # o efeito comprovado virou lembrança
        self.assertEqual([b["tipo"] for b in L.consultar()], ["experimento.plano", "experimento.resultado"])
        self.assertTrue(L.verificar()["ok"])

    def test_por_nota_limites_e_medida_desconhecida(self):
        self.assertIn("Ainda não acompanho 'futebol'", E.run({"action": "criar", "tratamento": "x", "medida": "futebol"}))
        self.assertIn("dias COM?", E.run({"action": "criar"}))
        r = E.run({"action": "criar", "tratamento": "dormir antes das 23h", "medida": "nota", "dias": "3"})
        self.assertIn("por 8 dias", r)                                                    # mínimo de 8
        self.assertIn("nota de 0 a 10", r)
        _Dia.hoje = HOJE + timedelta(1)
        self.assertIn("Qual a nota", E.run({"action": "nota"}))
        self.assertIn("Nota 8,0 anotada", E.run({"action": "nota", "valor": "8"}))
        _Agora.hora = 21
        _Dia.hoje = HOJE + timedelta(2)
        E.passo(None)
        E.passo(None)
        self.assertEqual(sum("qual a sua nota" in f for f in self.falas), 1)              # pede a nota à noite, uma vez
        for i in range(2):
            E.run({"action": "criar", "tratamento": f"teste {i}", "medida": "nota"})
        self.assertIn("Já há 3 experimentos", E.run({"action": "criar", "tratamento": "outro", "medida": "nota"}))
        self.assertIn("encerrado sem conclusão", E.run({"action": "encerrar", "experimento": "dormir"}))

    def test_valores_nao_incluem_hoje_e_respeitam_atraso(self):
        plano = {"2026-11-02": "com", "2026-11-03": "sem"}
        series = {"vendas da loja": {"2026-11-02": 10.0, "2026-11-03": 20.0, "2026-11-04": 30.0}}
        exp = {"medida": "vendas da loja", "plano": plano, "atraso": 0}
        self.assertEqual(E.valores_de(exp, series, date(2026, 11, 3)), {"2026-11-02": 10.0})
        self.assertEqual(E.valores_de({**exp, "atraso": 1}, series, date(2026, 11, 5)), {"2026-11-02": 20.0, "2026-11-03": 30.0})
        self.assertEqual(E.valores_de({"medida": "nota", "plano": plano, "notas": {"2026-11-03": 7, "2026-12-01": 9}}, {}, date(2026, 11, 3)),
                         {"2026-11-03": 7.0})

    def test_sugestoes_saem_dos_padroes_que_voce_controla(self):
        r = random.Random(4)
        agua, horas = {}, {}
        for k in range(60):
            d = (HOJE - timedelta(k + 1)).isoformat()
            agua[d] = 2400.0 if k % 2 else 1200.0
            horas[d] = (9.0 if k % 2 else 5.0) + r.uniform(-0.5, 0.5)
        achados = E.descobertas({"água bebida": agua, "horas trabalhadas": horas, "vendas da loja": {d: 500.0 for d in agua}})
        self.assertTrue(achados)
        self.assertEqual((achados[0]["causa"], achados[0]["efeito"]), ("água bebida", "horas trabalhadas"))
        self.assertIn("beber pelo menos", achados[0]["tratamento"])
        self.assertIsNone(E.tratamento_de("vendas da loja", {"a": 1.0}))                   # venda não é alavanca direta
        self.S.update({"água bebida": agua, "horas trabalhadas": horas})
        self.assertIn("cria um experimento: beber pelo menos", E.run({"action": "sugerir"}))


# ─────────────────────────────────────────────────────────── metacognição ───
PALAVRAS = ("banana laranja abacaxi morango melancia goiaba pitanga caju manga uva pera figo kiwi limao tomate cebola batata cenoura "
            "alface couve milho arroz feijao queijo leite cafe suco bolo torta pizza").split()


class TestMetacognicaoPuras(unittest.TestCase):
    def setUp(self):
        global M
        M = importlib.import_module("core.metacognicao")

    def test_wilson_tendencia_e_confianca(self):
        self.assertEqual(M.wilson(0, 0), 0.0)
        self.assertAlmostEqual(M.wilson(20, 20), 0.839, places=3)
        self.assertGreaterEqual(M.wilson(22, 22), 0.85)
        self.assertLess(M.wilson(21, 21), 0.85)
        self.assertLess(M.wilson(18, 20), 0.75)
        self.assertEqual((M.tendencia([20, 18, 10, 8]), M.tendencia([8, 10, 18, 20]), M.tendencia([10, 10, 10, 10]), M.tendencia([1, 2])),
                         ("melhorando", "piorando", "estável", "—"))
        self.assertEqual([M.confianca_de(x) for x in ({"n": 2, "acerto": 1.0}, {"n": 9, "acerto": 0.9}, {"n": 9, "acerto": 0.7},
                                                      {"n": 9, "erro_pct": 30}, {"n": 9, "erro_pct": 9})],
                         ["pouca base", "alta", "média", "baixa", "alta"])

    def test_tipo_placar_e_decisao(self):
        parecido = {"reflexo": True, "semelhanca": True, "ferramenta": "x"}
        self.assertEqual(M.tipo_de({"reflexo": True}, {}), "reflexo")
        self.assertEqual(M.tipo_de({"reflexo": False, "ferramenta": "x"}, parecido), "parecida")
        self.assertEqual(M.tipo_de(parecido, parecido), "parecida")                         # depois de aprovada continua sendo medida
        self.assertEqual((M.tipo_de({"ferramenta": "x"}, {}), M.tipo_de({}, {})), ("palpite", "nada"))
        regs = [[0, "parecida", 0.7, 1, 1]] * 23 + [[0, "palpite", 0.1, 0, 0]] * 4 + [[0, "nada", 0.0, 0, 0]]
        pl = M.placar_de(regs + [[0, M.PROPRIA, 0.6, 1, 1], [0, M.PROPRIA, 0.6, 0, 0]])
        self.assertEqual(pl["sozinho"], {"n": 2, "corrigidos": 1})                           # o que ele fez sozinho não é medição
        self.assertEqual((pl["n"], pl["sabia"], pl["parecida"]["n"], pl["parecida"]["acertos"]), (28, 27, 23, 23))
        self.assertAlmostEqual(pl["top1"], 23 / 27)
        self.assertEqual(M.decisao(pl, False, [], False, False), "propor")
        self.assertEqual(M.decisao(pl, False, [], True, False), "nada")                    # já tem proposta aberta
        self.assertEqual(M.decisao(pl, False, [], False, True), "nada")                    # você recusou há pouco
        self.assertEqual(M.decisao(M.placar_de(regs[:19]), False, [], False, False), "nada")   # prova insuficiente
        self.assertEqual(M.decisao(pl, True, [1, 1, 0, 1, 0, 1, 0], False, False), "rebaixar")
        self.assertEqual(M.decisao(pl, True, [1] * 12 + [0, 0], False, False), "nada")


class TestMetacognicao(Base):
    def usar(self, frase, ferramenta, args=None, vezes=1, proprio=False):
        for _ in range(vezes):
            C.anotar_chamada(ferramenta, args or {"action": "status"}, "ok", proprio=proprio)
            C.turno(frase)

    def test_sombra_mede_antes_de_aprender_e_ignora_reflexo_proprio(self):
        self.usar("como está o pc", "monitor_sistema")                                      # 1ª vez: não sabia
        self.usar("como está o pc", "monitor_sistema")                                      # 2ª: já tinha visto 1 vez
        self.usar("como está o pc", "monitor_sistema")                                      # 3ª: já era reflexo
        regs = M._ler()["cerebro"]
        self.assertEqual([r[1] for r in regs][-1], "reflexo")
        self.assertEqual(len(regs), 3)
        self.usar("como está o pc", "monitor_sistema", proprio=True)                        # o próprio cérebro fez: não conta
        self.assertEqual(len(M._ler()["cerebro"]), 3)
        self.assertIn("medido em 3 pedido(s)", PM.run({"action": "cerebro"}))

    def test_propoe_com_prova_so_liga_com_o_seu_sim_e_se_rebaixa(self):
        with mock.patch("core.verificacao.nivel_de", return_value="livre"):
            self.usar("como está o pc", "monitor_sistema", vezes=3)
            for i, palavra in enumerate(PALAVRAS):                                          # 30 frases novas, todas parecidas
                self.usar(f"como está o pc {palavra}", "monitor_sistema")
                if M.proposta():
                    break
            prop = M.proposta()
            self.assertIsNotNone(prop)
            self.assertEqual((i + 1, prop["n"], prop["acertos"]), (22, 22, 22))            # só com 22 acertos em 22 a prova fecha
            self.assertGreaterEqual(prop["piso"], 0.85)
            self.assertFalse(C.semelhanca_ligada())                                         # propor não liga nada
            self.assertFalse(C.entender("como está o meu pc querido")["reflexo"])
            self.assertTrue(any("Posso passar a fazer esses sozinho" in f for f in self.falas))
            self.assertIn("Proposta esperando o seu sim", PM.run({"action": "evolucao"}))
            self.assertIn("Evolução aprovada", PM.run({"action": "aprovar"}))
            self.assertTrue(C.semelhanca_ligada())
            r = C.entender("como está o pc querido")
            self.assertEqual((r["reflexo"], r["ferramenta"]), (True, "monitor_sistema"))
            for i in range(3):                                                              # 3 erros em frases parecidas
                self.usar(f"como está o pc e{i}", "clima", {"action": "agora"})
            self.assertFalse(C.semelhanca_ligada())                                         # voltou atrás sozinho
            self.assertTrue(any("desliguei sozinho" in f for f in self.falas))
        self.assertEqual([b["dados"]["acao"] for b in L.consultar(tipo="evolucao")], ["proposta", "aprovada", "rebaixado"])
        self.assertIn("Não há evolução esperando", PM.run({"action": "aprovar"}))

    def test_depois_de_aprovada_o_que_ele_faz_sozinho_tambem_e_vigiado(self):
        with mock.patch("core.verificacao.nivel_de", return_value="livre"):
            self.usar("como está o pc", "monitor_sistema", vezes=3)
            M._gravar({**M._ler(), "proposta": {"ts": 1, "n": 22, "acertos": 22, "piso": 0.851}})
            M.aprovar()
            for i, palavra in enumerate(PALAVRAS[:3]):
                r = C.entender(f"como está o pc {palavra}")
                self.assertEqual((r["reflexo"], r["semelhanca"], i), (True, True, i))
                self.usar(f"como está o pc {palavra}", r["ferramenta"], r["args"], proprio=True)    # ele mesmo fez...
                self.assertEqual(M.placar_cerebro()["sozinho"]["n"], i + 1)
                self.assertTrue(C.semelhanca_ligada())
                C.turno("não, não foi isso")                                                        # ...e você corrigiu
            self.assertFalse(C.semelhanca_ligada())                                         # 3 correções: voltou atrás sozinho
            self.assertTrue(any("desliguei sozinho" in f for f in self.falas))
            self.assertEqual(M.placar_cerebro()["sozinho"]["n"], 0)                         # recomeça do zero
            self.assertFalse(C.entender(f"como está o pc {PALAVRAS[5]}")["reflexo"])
        self.assertEqual([b["dados"]["acao"] for b in L.consultar(tipo="evolucao")], ["aprovada", "rebaixado"])

    def test_reflexo_de_frase_conhecida_nao_entra_na_vigilancia(self):
        with mock.patch("core.verificacao.nivel_de", return_value="livre"):
            self.usar("como está o pc", "monitor_sistema", vezes=3)
            C.ligar_semelhanca(True)
            self.usar("como está o pc", "monitor_sistema", proprio=True)                    # frase conhecida: não é "parecida"
            self.assertEqual(M.placar_cerebro()["sozinho"]["n"], 0)
            self.usar("como está o pc manga", "monitor_sistema", proprio=True)
            self.assertEqual(M.placar_cerebro()["sozinho"], {"n": 1, "corrigidos": 0})
            self.assertIn("fiz 1 frase(s) parecida(s) sozinho e você corrigiu 0", PM.run({"action": "cerebro"}))
            self.assertIn("Desligado", M.rebaixar())
            self.assertEqual(M.placar_cerebro()["sozinho"]["n"], 0)

    def test_frase_corrigida_nunca_mais_e_feita_por_parecer(self):
        self.usar("como está o pc", "monitor_sistema", vezes=2)
        r = C.entender("como está o meu pc lento", sem_ia=True)                             # sem Gemini, frase parecida vale
        self.assertEqual((r["reflexo"], r["semelhanca"]), (True, True))
        self.usar("como está o meu pc lento", r["ferramenta"], r["args"], proprio=True)
        C.turno("não, não foi isso")
        r = C.entender("como está o meu pc lento", sem_ia=True)
        self.assertFalse(r["reflexo"])                                                      # antes da 3.6 ele repetia o engano
        self.assertIn("já me corrigiu", r["motivo"])
        self.assertTrue(C.entender("como está o pc", sem_ia=True)["reflexo"])               # o que estava certo continua
        self.assertTrue(C.entender("como está o pc travando", sem_ia=True)["reflexo"])      # e outras parecidas também

    def test_evolucao_so_vale_para_ferramenta_livre(self):
        self.usar("como está o pc", "monitor_sistema", vezes=3)
        C.ligar_semelhanca(True)
        with mock.patch("core.verificacao.nivel_de", return_value="sensivel"):
            self.assertFalse(C.entender("como está o pc querido")["reflexo"])
            self.assertTrue(C.entender("como está o pc querido", sem_ia=True)["reflexo"])   # sem Gemini a regra antiga continua
        with mock.patch("core.verificacao.nivel_de", return_value="critico"):
            self.assertFalse(C.entender("como está o pc querido", sem_ia=True)["reflexo"])
        self.assertIn("Desligado", M.rebaixar())
        self.assertIn("já está desligado", M.rebaixar())

    def test_recusar_segura_novas_propostas(self):
        d = {"cerebro": [[time.time(), "parecida", 0.7, 1, 1]] * 25}
        M._gravar(d)
        self.assertEqual(M.avaliar_evolucao()["acao"], "proposta")
        self.assertIn("Recusado", M.recusar())
        self.assertIsNone(M.avaliar_evolucao())
        self.assertIsNone(M.proposta())

    def test_placar_junta_os_sistemas_que_tem_resultado(self):
        self.assertIn("Ainda não tenho nada medido", PM.run({"action": "placar"}))
        lote2 = importlib.import_module("plugins._lote2")
        lote2.guardar("oraculo", {"previsoes": [{"semana": f"2026-10-{d:02d}", "dias": {}, "erro": [e, e, 6]}
                                               for d, e in ((5, 30.0), (12, 28.0), (19, 12.0), (26, 10.0))] + [{"semana": "x", "erro": None}]})
        lote2.guardar("gemeo_loja", {"promocoes": [{"conferida": True, "razao": 1.25, "d": 0.2, "e_usada": 2.0, "alcance": 1.0, "tipo": "desconto"},
                                                   {"conferida": False}]})
        self.usar("como está o pc", "monitor_sistema", vezes=4)
        linhas = {x["sistema"]: x for x in M.placar()}
        self.assertEqual((linhas["oráculo de vendas"]["n"], linhas["oráculo de vendas"]["tendencia"]), (4, "melhorando"))
        self.assertAlmostEqual(linhas["oráculo de vendas"]["erro_pct"], 20.0)
        self.assertAlmostEqual(linhas["gêmeo da loja"]["erro_pct"], 0.0, places=6)          # previu 1,25× e vendeu 1,25×
        self.assertIn("cérebro local", linhas)
        txt = PM.run({"action": "placar"})
        self.assertIn("oráculo de vendas: erra em média 20% em 4 caso(s), melhorando", txt)


# ─────────────────────────────────────────────────────────── OMEGA ───
class TestOmega(Base):
    def test_oito_sistemas_de_verdade_mesmo_vazio(self):
        ss = O.sistemas()
        self.assertEqual([s["nome"] for s in ss], ["BRAIN", "HEART", "IMMUNE", "MEMORY", "COUNCIL", "EVOLUTION", "DREAM", "LAB"])
        self.assertTrue(all(s["estado"] in O.ROTULO and s["frase"] for s in ss))
        self.assertEqual(len(O.CONSELHEIROS), 12)
        self.assertEqual({s["id"]: s["estado"] for s in ss}["dream"], "parado")             # sem sonho ainda: não finge
        self.assertIn("OMEGA:", PO.run({"action": "estado"}))
        self.assertIn("IMMUNE — Proteção e recuperação", PO.run({"action": "sistema", "nome": "imune"}))
        self.assertIn("Qual sistema?", PO.run({"action": "sistema", "nome": "xyz"}))

    def test_cada_conselheiro_existe_no_codigo(self):
        for plugin, nomes in (("conselho", O.CONSELHEIROS[:5]), ("multiverso", O.CONSELHEIROS[5:10])):
            src = (RAIZ / "plugins" / f"{plugin}.py").read_text(encoding="utf-8")
            for n in nomes:
                self.assertIn(n, src, f"{n} em {plugin}")
        self.assertIn("cético", (RAIZ / "plugins" / "segunda_opiniao.py").read_text(encoding="utf-8"))
        self.assertIn("FRIDAY", (RAIZ / "plugins" / "duelo_ia.py").read_text(encoding="utf-8"))

    def test_estados_mudam_com_a_realidade(self):
        M._gravar({"proposta": {"ts": 1, "n": 25, "acertos": 25, "piso": 0.87}})
        self.assertEqual({s["id"]: s["estado"] for s in O.sistemas()}["evolution"], "atencao")
        L.ferramenta("musica", {}, "ok")
        L.ferramenta("musica", {}, "ok")
        L.fechar()
        with sqlite3.connect(str(L.ARQ)) as c:
            c.execute("UPDATE blocos SET dados = '{}' WHERE n = 1")
        c.close()
        imune = {s["id"]: s for s in O.sistemas()}["immune"]
        self.assertEqual(imune["estado"], "atencao")
        self.assertIn("foi mexido", imune["frase"])
        self.assertIn("pedem atenção IMMUNE, EVOLUTION", O.consciencia())

    def test_ciclo_liga_os_sistemas_e_so_propoe(self):
        achado = {"forca": 50, "texto": "Nos dias com mais água bebida, há 30% a mais de horas trabalhadas.", "causa": "água bebida",
                  "efeito": "horas trabalhadas", "atraso": 0, "tratamento": "beber pelo menos 2000 ml de água"}
        self.assertIn("não tem experimento proposto", PO.run({"action": "propostas"}))
        trocar(self, "plugins.experimento_vida", "descobertas", lambda *a, **k: [achado])
        reg = O.ciclo()
        self.assertEqual([p["sistema"] for p in reg["passos"]], ["DREAM", "BRAIN", "LAB", "EVOLUTION", "IMMUNE", "MEMORY", "COUNCIL"])
        self.assertEqual(len(reg["novidades"]), 1)
        self.assertIn("cria um experimento: beber pelo menos 2000 ml de água, medindo horas trabalhadas", reg["novidades"][0])
        self.assertEqual(O.ciclo()["novidades"], [])                                        # a mesma proposta não vira novidade de novo
        self.assertIn("beber pelo menos 2000 ml", PO.run({"action": "propostas"}))
        self.assertEqual(E._est()["experimentos"], [])                                      # o ciclo não começou nada sozinho
        self.assertFalse(C.semelhanca_ligada())                                             # nem ligou evolução nenhuma
        self.assertEqual(sum(b["tipo"] == "omega.ciclo" for b in L.consultar()), 2)
        self.assertEqual(O.ultimo_ciclo()["passos"][-1]["sistema"], "COUNCIL")
        self.assertIn("Ciclo OMEGA:", PO.run({"action": "ciclo"}))

    def _relogio(self, hora: int):
        """O relógio do plugin numa hora escolhida de hoje (o ciclo em si usa o relógio de verdade)."""
        real = time.localtime()
        falso = time.struct_time(tuple(real[:3]) + (hora, 0, 0) + tuple(real[6:]))
        return mock.patch.object(PO, "time", mock.Mock(localtime=lambda *a: falso, strftime=time.strftime))

    def test_ciclo_uma_vez_por_dia_e_so_fala_com_novidade(self):
        ciclos = lambda: sum(b["tipo"] == "omega.ciclo" for b in L.consultar())             # noqa: E731
        with self._relogio(5):
            PO.passo(None)
        self.assertEqual(ciclos(), 0)                                                       # de madrugada não roda
        with self._relogio(9):
            PO.passo(None)
            PO.passo(None)
            PO.passo(None)
        self.assertEqual(ciclos(), 1)                                                       # um por dia
        self.assertEqual(self.falas, [])                                                    # sem novidade, fica quieto
        d = O._ler()
        d["ciclos"][-1]["dia"] = "2020-01-01"                                               # como se o último fosse de outro dia
        O._gravar(d)
        achado = {"forca": 50, "texto": "Nos dias com mais água, você rende mais.", "causa": "água bebida", "efeito": "horas trabalhadas",
                  "atraso": 0, "tratamento": "beber pelo menos 2000 ml de água"}
        trocar(self, "plugins.experimento_vida", "descobertas", lambda *a, **k: [achado])
        with self._relogio(9):
            PO.passo(None)
            PO.passo(None)
        self.assertEqual(ciclos(), 2)
        self.assertEqual(self.falas, ["O ciclo OMEGA de hoje trouxe 1 novidade(s). Está no painel."])

    def test_painel_real_e_seguro(self):
        ss = O.sistemas()
        ss[0]["frase"] = "<script>alert(1)</script>"
        h = O.painel_html(ss, {"ts": 0, "passos": [{"sistema": "DREAM", "texto": "x < y"}], "novidades": ["a & b"]}, [], 0)
        self.assertEqual(h.count("<section class='c "), 8)
        self.assertNotIn("<script>", h)
        self.assertIn("&lt;script&gt;", h)
        self.assertIn("x &lt; y", h)
        self.assertIn("a &amp; b", h)
        self.assertIn("http-equiv=\"refresh\"", h)
        self.assertEqual(h.count("<circle"), 10)                                            # núcleo (2) + 8 sistemas
        r = PO.run({"action": "painel"})
        self.assertIn("Painel OMEGA aberto", r)
        arq = self.tmp / "Omega" / "omega.html"
        self.assertTrue(arq.is_file())
        self.assertTrue(O.manter_painel())                                                  # aberto há pouco: mantém fresco
        d = O._ler()
        d["painel_ate"] = 0
        O._gravar(d)
        self.assertFalse(O.manter_painel())


# ─────────────────────────────────────────────────────────── modos impossíveis ───
class TestModosImpossiveis(unittest.TestCase):
    def test_dez_modos_novos_com_passos_que_existem(self):
        from core import registro_ferramentas
        modos = importlib.import_module("plugins.modos")
        lote4 = importlib.import_module("plugins._modos_lote4")
        self.assertEqual(len(lote4.MODOS_LOTE4), 10)
        self.assertEqual(len(modos.todos()), 158)
        self.assertEqual(modos.CATEGORIAS["impossiveis"], list(lote4.MODOS_LOTE4))
        from plugins._modos_extras import MODOS_EXTRAS
        from plugins._modos_lote3 import MODOS_LOTE3
        self.assertFalse(set(lote4.MODOS_LOTE4) & (set(modos.MODOS) | set(MODOS_EXTRAS) | set(MODOS_LOTE3)))
        decls = {d["name"]: d for d in registro_ferramentas.declaracoes()}
        for k, modo in lote4.MODOS_LOTE4.items():
            self.assertTrue(modo["titulo"] and len(modo["jeito"]) > 60, k)
            for passo in modo["entrar"] + modo["sair"]:
                self.assertEqual(passo["tipo"], "ferramenta", k)
                self.assertIn(passo["nome"], decls, f"{k}: ferramenta {passo['nome']} não existe")
                acoes = [a.strip() for a in str(decls[passo["nome"]]["parameters"]["properties"]["action"].get("description", "")).split("|")]
                self.assertIn(passo["params"]["action"], acoes, f"{k}: {passo['nome']} não tem a ação {passo['params']['action']}")
        usadas = {(p["nome"], p["params"]["action"]) for m in lote4.MODOS_LOTE4.values() for p in m["entrar"] + m["sair"]}
        self.assertNotIn(("ia_local", "ligar"), usadas)          # o bunker só confere: não ocupa a memória nem derruba a IA ao sair
        self.assertNotIn(("ia_local", "desligar"), usadas)
        seguros = {"estado", "reflexos", "placar", "projecao", "hoje", "incidentes", "listar", "sugerir", "verificar", "selar", "ciclo", "painel", "ligar"}
        self.assertLessEqual({a for _, a in usadas}, seguros)    # entrar num modo só consulta, sela ou liga o porteiro

    def test_nomes_falados(self):
        modos = importlib.import_module("plugins.modos")
        casos = {"modo omega": "omega", "modo bunker": "bunker", "modo offline": "bunker", "modo ia local": "bunker",
                 "modo cartório": "cartorio", "modo testemunha": "cartorio", "modo bastidores": "bastidores", "modo raio x": "bastidores",
                 "modo eu do futuro": "eu_do_futuro", "modo futuro": "eu_do_futuro", "modo cobaia": "cobaia", "modo experimento": "cobaia",
                 "modo autópsia": "autopsia", "modo post mortem": "autopsia", "modo impossível": "tira_teima", "modo tira-teima": "tira_teima",
                 "modo só fatos": "so_fatos", "modo fatos": "so_fatos", "modo fortaleza": "fortaleza", "modo cofre": "fortaleza"}
        self.assertEqual({k: modos.achar(k) for k in casos}, casos)
        self.assertIn("OMEGA (omega)", modos.run({"action": "listar", "modo": "modos impossiveis"}))

    def test_modo_novo_nao_toma_o_lugar_de_nome_que_ja_funcionava(self):
        """A 1ª versão do lote 4 fazia "modo sem internet" virar bunker (era o apagão) e a palavra "possível" puxar o
        modo impossível. A busca agora roda primeiro só nos modos antigos."""
        modos = importlib.import_module("plugins.modos")
        como_era = {"modo sem internet": "apagao", "sem internet": "apagao", "modo sem luz": "apagao", "modo missão impossível": "controle_missao",
                    "o mais detalhado possível": "detalhado", "mais silencioso possível": "biblioteca",
                    "modo estudar o máximo possível": "estudo", "modo prova": "prova", "modo cientista": "cientista",
                    "modo dia difícil": "dia_dificil", "modo segurança": "seguranca", "modo laboratório": "laboratorio_stark",
                    "modo refatorar": "refatoracao", "modo cozinhar bolo": "cozinha", "modo dados": "banco_dados"}
        self.assertEqual({k: modos.achar(k) for k in como_era}, como_era)
        for frase in ("modo mais rápido possível", "o melhor possível", "modo não interrompa", "modo 1", "modo internet caiu"):
            self.assertIsNone(modos.achar(frase), frase)                                    # continua sem adivinhar
        antigos = modos._ate_o_lote3()
        self.assertEqual(len(antigos), 145)
        for k, m in antigos.items():                                                        # todo nome e título antigo: igual
            self.assertEqual((modos.achar(k), modos.achar(k.replace("_", " "))), (k, k), k)
            self.assertEqual(modos.achar("modo " + m["titulo"]), modos._achar_em(modos.APELIDOS3.get(modos.chave(m["titulo"]), modos.chave(m["titulo"])), antigos), k)


class TestModosImpossiveisRodando(Base):
    def test_entrar_e_sair_rodam_os_passos_certos(self):
        modos = importlib.import_module("plugins.modos")
        trocar(self, "plugins.modos", "ARQ_ESTADO", self.tmp / "modo.json")
        trocar(self, "plugins.modos", "ARQ_MEUS", self.tmp / "meus.json")
        chamadas = []
        with mock.patch("core.registro_ferramentas.executar", lambda n, p, pl=None: chamadas.append((n, p["action"])) or "feito"):
            r = modos.entrar("modo fortaleza")
            self.assertIn("[MODO FORTALEZA]", r)
            self.assertIn("confirme que é o dono", r)                                       # o jeito de agir vai para o Gemini
            self.assertEqual(chamadas, [("porteiro_voz", "ligar"), ("livro_razao", "selar")])
            self.assertIn("[MODO BUNKER]", modos.entrar("modo offline"))                    # trocar de modo roda a saída do anterior
            self.assertEqual(chamadas[2:], [("livro_razao", "selar"), ("ia_local", "estado"), ("cerebro", "reflexos")])
            self.assertIn("[MODO TIRA_TEIMA]", modos.entrar("modo impossível"))
            self.assertEqual(chamadas[5:], [("metas_pessoais", "listar"), ("experimento_vida", "sugerir")])
            self.assertIn("Saí do modo Tira-teima", modos.sair())
            self.assertIn("[MODO APAGAO]", modos.entrar("modo sem internet"))               # o de sempre
            modos.sair()

    def test_os_passos_dos_sistemas_novos_respondem_de_verdade(self):
        for nome, acao, trecho in (("omega", "ciclo", "Ciclo OMEGA:"), ("omega", "painel", "Painel OMEGA aberto"),
                                   ("livro_razao", "selar", "Livro selado. Código: "), ("livro_razao", "verificar", "Corrente íntegra"),
                                   ("metacognicao", "placar", "medido"), ("experimento_vida", "hoje", "Nenhum experimento rodando"),
                                   ("experimento_vida", "sugerir", "")):
            r = importlib.import_module(f"plugins.{nome}").run({"action": acao})
            self.assertIn(trecho, r, f"{nome}.{acao}")
            self.assertNotIn("falhou", r, f"{nome}.{acao}")


# ─────────────────────────────────────────────────────────── varredura e ligações ───
class TestAcoesDeclaradas(Base):
    def test_o_que_o_gemini_ve_e_o_que_existe_no_codigo(self):
        for nome in ("omega", "livro_razao", "experimento_vida", "metacognicao"):
            mod = importlib.import_module(f"plugins.{nome}")
            declaradas = [a.strip() for a in mod.PLUGIN["parameters"]["properties"]["action"]["description"].split("|")]
            existem = mod.run({"action": "zzzqqq"}).split("Use: ")[1].rstrip(".").split(", ")
            self.assertEqual(declaradas, existem, nome)                                     # nem ação fantasma, nem ação escondida
            self.assertLessEqual(len(mod.PLUGIN["brief"]), 150, nome)                       # cabe inteiro na linha do catálogo
            src = (RAIZ / "plugins" / f"{nome}.py").read_text(encoding="utf-8")
            lidos = set(re.findall(r'\bp\.get\("(\w+)"|\bnum1\(p, "(\w+)"', src))
            lidos = {a or b for a, b in lidos}
            self.assertEqual(set(mod.PLUGIN["parameters"]["properties"]) - {"action"}, lidos, nome)   # declarado = lido


class TestVarredura36(unittest.TestCase):
    def test_laboratorio_declara_o_parametro_regex(self):
        lab = importlib.import_module("plugins.laboratorio")
        self.assertEqual(lab.PLUGIN["parameters"]["properties"]["regex"]["type"], "BOOLEAN")

    def test_sqlite_ajuda_solta_o_arquivo(self):
        sq = importlib.import_module("plugins.sqlite_ajuda")
        pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pasta, True)
        arq = pasta / "t.db"
        c = sqlite3.connect(str(arq))
        c.execute("create table a (x int)")
        c.commit()
        c.close()
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            self.assertIn("a: 0 linha(s)", sq.run({"action": "tabelas", "arquivo": str(arq)}))
            gc.collect()
        self.assertFalse([a for a in avisos if "unclosed database" in str(a.message)])

    def test_niveis_ferramenta_fixa_e_busca(self):
        from core import orcamento_ferramentas, registro_ferramentas, verificacao as V
        from plugins import catalogo
        self.assertIn("omega", orcamento_ferramentas.FIXAS)
        for nome, acao, nivel in (("livro_razao", "provar", V.SENSIVEL), ("livro_razao", "verificar", V.LIVRE), ("experimento_vida", "criar", V.SENSIVEL),
                                  ("metacognicao", "aprovar", V.SENSIVEL), ("metacognicao", "placar", V.LIVRE), ("omega", "ciclo", V.SENSIVEL),
                                  ("omega", "estado", V.LIVRE)):
            self.assertEqual(V.nivel_de(nome, {"action": acao}), nivel, f"{nome}.{acao}")
        trocas = [mock.patch.object(m, "ativo", return_value=True) for m in versoes("plugins.modo_convidado")]
        for t in trocas:
            t.start()
        try:
            with mock.patch.object(V, "ARQ_LOG", Path(tempfile.mkdtemp()) / "log.json"):
                self.assertIn("MODO CONVIDADO", V.autorizar("metacognicao", {"action": "aprovar"}))
                self.assertIn("MODO CONVIDADO", V.autorizar("livro_razao", {"action": "provar"}))
        finally:
            for t in trocas:
                t.stop()
        decls = registro_ferramentas.declaracoes()
        casos = {"prova o que você fez ontem": "livro_razao", "verifica o livro-razão": "livro_razao",
                 "cria um experimento sorteado na minha vida": "experimento_vida", "que experimentos você sugere": "experimento_vida",
                 "o quanto eu posso confiar em você": "metacognicao", "abre o painel omega": "omega", "roda o ciclo omega": "omega"}
        erros = [q for q, alvo in casos.items() if alvo not in [d["name"] for d in catalogo.buscar(decls, q, 3)]]
        self.assertEqual(erros, [])


if __name__ == "__main__":
    unittest.main()
