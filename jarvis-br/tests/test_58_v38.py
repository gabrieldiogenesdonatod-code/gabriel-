"""Testes da 3.8 — modos mineração, cripto e garagem; plugins veiculo (garagem) e mapa_mental."""
import importlib
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from tests.test_52_v33 import trocar


class Base(unittest.TestCase):
    def setUp(self):
        global V, MM
        V = importlib.import_module("plugins.veiculo")
        MM = importlib.import_module("plugins.mapa_mental")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.falas, self.abertos = [], []
        for nome, attr, valor in (("plugins._lote2", "PASTA", self.tmp / "lote2"),
                                  ("plugins._comum", "avisar", lambda pl, t, e="": self.falas.append(t)),
                                  ("plugins._comum", "mostrar", lambda *a, **k: None),
                                  ("plugins._comum", "abrir_no_sistema", lambda alvo: self.abertos.append(alvo) or True),
                                  ("plugins._comum", "pasta_jarvis", lambda n: (self.tmp / n).mkdir(exist_ok=True) or self.tmp / n)):
            trocar(self, nome, attr, valor)


# ─────────────────────────────────────────────────────────── garagem ───
class TestGaragemPuras(unittest.TestCase):
    def setUp(self):
        global V
        V = importlib.import_module("plugins.veiculo")

    def test_km_e_itens_falados(self):
        self.assertEqual([V.km_de(x) for x in ("85 mil", "86.400 km", "86400", "1,5 mil", "")], [85000, 86400, 86400, 1500, None])
        casos = {"troquei o óleo": "oleo", "filtro de óleo": "filtro_oleo", "filtro do ar-condicionado": "filtro_cabine",
                 "filtro de ar": "filtro_ar", "pneus novos": "pneus", "pastilha de freio": "pastilhas", "fluido de freio": "fluido_freio",
                 "correia dentada": "correia", "água do radiador": "arrefecimento", "revisão": "revisao"}
        self.assertEqual({k: V.item_de(k) for k in casos}, casos)
        self.assertEqual(V.item_de("corrente", "moto"), "corrente")
        self.assertIsNone(V.item_de("corrente", "carro"))                     # carro não tem corrente
        self.assertIsNone(V.item_de("correia", "moto"))

    def test_vence_pelo_que_chegar_primeiro(self):
        hoje = date(2026, 11, 18)
        ok = V.situacao("oleo", "carro", {"km": 80000, "d": "2026-10-01"}, 82000, hoje)
        self.assertEqual((ok["vencido"], ok["perto"], ok["falta_km"]), (False, False, 8000))
        por_km = V.situacao("oleo", "carro", {"km": 80000, "d": "2026-10-01"}, 90500, hoje)
        self.assertTrue(por_km["vencido"])
        self.assertIn("passou 500 km", V.texto_situacao(por_km))
        por_data = V.situacao("oleo", "carro", {"km": 80000, "d": "2025-10-01"}, 81000, hoje)
        self.assertTrue(por_data["vencido"])
        self.assertIn("venceu há", V.texto_situacao(por_data))
        perto = V.situacao("oleo", "carro", {"km": 80000, "d": "2026-10-01"}, 89200, hoje)
        self.assertTrue(perto["perto"])
        self.assertTrue(V.situacao("bateria", "carro", {"km": 0, "d": "2026-11-01"}, 1, hoje)["falta_km"] is None)
        sem = V.situacao("correia", "carro", None, 60000, hoje)
        self.assertTrue(sem["vencido"] and sem["sem_registro"])
        self.assertIn("sem registro", V.texto_situacao(sem))


class TestGaragem(Base):
    def test_fluxo_completo(self):
        self.assertIn("Nenhum veículo", V.run({"action": "proximas"}))
        self.assertIn("Cadastrei o carro Gol com 85.000 km", V.run({"action": "cadastrar", "nome": "meu carro Gol", "km": "85 mil"}))
        self.assertIn("Já tenho", V.run({"action": "cadastrar", "nome": "Gol"}))
        r = V.run({"action": "proximas"})
        self.assertIn("Ainda não sei quando foi feito: troca de óleo", r)
        self.assertNotIn("VENCIDO", r)                                       # sem registro não vira alarme falso
        r = V.run({"action": "fiz", "item": "troquei o óleo e o filtro", "km": "84 mil", "valor": "180"})
        self.assertIn("troca de óleo no Gol com 84.000 km, R$ 180,00", r)
        self.assertIn("Próxima: com 94.000 km ou em 12 meses", r)
        self.assertIn("filtro_oleo", V._est()["veiculos"][0]["itens"])     # "óleo e o filtro" anota os dois
        self.assertIn("o odômetro não volta", V.run({"action": "km", "km": "50000"}))
        r = V.run({"action": "km", "km": "93.500"})
        self.assertIn("Atenção: troca de óleo: perto, faltam 500 km", r)
        self.assertIn("Qual serviço?", V.run({"action": "fiz", "item": "lavei"}))
        V.run({"action": "fiz", "item": "alinhamento", "valor": "1.200,50"})
        self.assertIn("R$ 1.380,50 em manutenção", V.run({"action": "gastos"}))
        self.assertIn("alinhamento e balanceamento com 93.500 km (R$ 1.200,50)", V.run({"action": "historico", "veiculo": "gol"}))
        V.run({"action": "cadastrar", "nome": "moto Titan", "tipo": "moto", "km": "32 mil"})
        self.assertIn("Em qual veículo?", V.run({"action": "fiz", "item": "revisão"}))
        self.assertIn("lubrificar a corrente no Titan", V.run({"action": "fiz", "veiculo": "titan", "item": "corrente"}))
        r = V.run({"action": "proximas"})
        self.assertIn("Titan (32.000 km)", r)
        self.assertIn("Gol (93.500 km): troca de óleo: perto", r)
        self.assertIn("kit relação", V.run({"action": "itens", "tipo": "moto"}))
        self.assertIn("Tirei o Titan", V.run({"action": "remover", "veiculo": "Titan"}))

    def test_km_do_combustivel_e_aviso_diario(self):
        V.run({"action": "cadastrar", "nome": "Gol", "km": "80000"})
        V.run({"action": "fiz", "item": "óleo", "km": "80000"})
        lote2 = importlib.import_module("plugins._lote2")
        lote2.gravar_json(lote2.PASTA / "combustivel.json", [{"d": "2026-11-10", "l": 40, "p": 6, "km": 89500}])
        self.assertIn("89.500 km", V.run({"action": "proximas"}))            # pegou o km anotado no abastecimento
        V.passo(None)
        V.passo(None)
        self.assertEqual(len(self.falas), 1)                                 # um aviso por dia
        self.assertIn("Garagem: Gol: troca de óleo: perto", self.falas[0])
        e = V._est()
        e["avisado_em"] = "2000-01-01"
        lote2.guardar("veiculo", e)
        V.passo(None)
        self.assertEqual(len(self.falas), 1)                                 # o mesmo item não é repetido
        V.run({"action": "fiz", "item": "óleo"})
        e = V._est()
        e["avisado_em"] = "2000-01-01"
        lote2.guardar("veiculo", e)
        V.passo(None)
        self.assertEqual(V._est()["ja_avisei"], [])                          # resolvido: sai da lista


# ─────────────────────────────────────────────────────────── mapa mental ───
class TestMapaMental(Base):
    def test_ler_e_juntar(self):
        r = MM.ler_ramos("Problema: luz cara, internet lenta; Solução: JARVIS\nDemonstração")
        self.assertEqual(r, [{"nome": "Problema", "itens": ["luz cara", "internet lenta"]}, {"nome": "Solução", "itens": ["JARVIS"]},
                             {"nome": "Demonstração", "itens": []}])
        j = MM.juntar(r, [{"nome": "problema", "itens": ["Luz cara", "barulho"]}, {"nome": "Custos", "itens": ["zero"]}])
        self.assertEqual(j[0]["itens"], ["luz cara", "internet lenta", "barulho"])
        self.assertEqual(j[-1]["nome"], "Custos")
        self.assertEqual(MM.chave("mapa mental da apresentação do SENAI"), "apresentacao senai")

    def test_criar_adicionar_abrir(self):
        self.assertIn("Qual o assunto", MM.run({"action": "criar"}))
        self.assertIn("escreva você 4 a 7 ramos", MM.run({"action": "criar", "tema": "Redes"}))
        r = MM.run({"action": "criar", "tema": "Apresentação do SENAI", "ramos": "Problema: a, b; Solução: c; Demo: d, e, f"})
        self.assertIn("3 ramos e 6 itens", r)
        arq = Path(self.abertos[-1])
        h = arq.read_text(encoding="utf-8")
        self.assertIn('"tema": "Apresentação do SENAI"', h)
        self.assertIn("prefers-color-scheme:dark", h)
        self.assertNotIn("http", h.split("<script>")[1].split("NS =")[0])  # nada de internet
        self.assertIn("Adicionei no mapa 'Apresentação do SENAI': Custos (luz, internet)",
                      MM.run({"action": "adicionar", "tema": "senai", "ramos": "Custos: luz, internet"}))
        self.assertIn("4 ramos", MM.run({"action": "listar"}))
        self.assertIn("aberto", MM.run({"action": "abrir", "tema": "o mapa do senai"}))
        self.assertIn("Em qual mapa?", MM.run({"action": "adicionar", "tema": "xadrez", "ramos": "a: b"}))
        self.assertIn("Apaguei", MM.run({"action": "apagar", "tema": "senai"}))
        self.assertIn("Nenhum mapa", MM.run({"action": "listar"}))

    def test_texto_perigoso_nao_quebra_a_pagina(self):
        h = MM.html_mapa("<b>x</b>", [{"nome": "</script><script>alert(1)</script>", "itens": []}])
        self.assertNotIn("</script><script>alert", h)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", h)

    def test_pagina_funciona_no_navegador(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self.skipTest("sem playwright")
        arq = self.tmp / "m.html"
        arq.write_text(MM.html_mapa("Teste", MM.ler_ramos("A: 1, 2; B: 3; C: 4, 5, 6")), encoding="utf-8")
        try:
            with sync_playwright() as p:
                b = p.chromium.launch()
                pg = b.new_page()
                erros = []
                pg.on("pageerror", lambda e: erros.append(str(e)))
                pg.goto(arq.as_uri())
                n = pg.evaluate("document.querySelectorAll('.no').length")
                pg.click(".ramo >> nth=0")
                n2 = pg.evaluate("document.querySelectorAll('.no').length")
                b.close()
        except Exception as e:
            self.skipTest(f"navegador indisponível: {e}")
        self.assertEqual(erros, [])
        self.assertEqual(n, 1 + 3 + 6)                                       # centro + ramos + itens
        self.assertEqual(n2, n - 2)                                          # clicar no ramo A esconde os 2 itens


# ─────────────────────────────────────────────────────────── modos ───
class TestModosLote5(unittest.TestCase):
    def test_tres_modos_validos_e_aditivos(self):
        from core import registro_ferramentas
        modos = importlib.import_module("plugins.modos")
        l5 = importlib.import_module("plugins._modos_lote5")
        self.assertEqual(list(l5.MODOS_LOTE5), ["mineracao", "cripto", "garagem"])
        self.assertEqual(modos.CATEGORIAS["dinheiro_e_garagem"], ["mineracao", "cripto", "garagem"])
        decls = {d["name"]: d for d in registro_ferramentas.declaracoes()}
        for k, m in l5.MODOS_LOTE5.items():
            for passo in m["entrar"] + m["sair"]:
                acoes = [a.strip() for a in decls[passo["nome"]]["parameters"]["properties"]["action"]["description"].split("|")]
                self.assertIn(passo["params"]["action"], acoes, k)
        entrar = [(p["nome"], p["params"]["action"]) for p in l5.MODOS_LOTE5["mineracao"]["entrar"]]
        self.assertNotIn(("mineracao", "ligar"), entrar)                     # entrar no modo nunca liga o minerador
        casos = {"modo mineração": "mineracao", "modo minerar": "mineracao", "modo cripto": "cripto", "modo bitcoin": "cripto",
                 "modo garagem": "garagem", "modo oficina": "garagem", "modo mecânico": "garagem",
                 "modo brainstorm": "brainstorm", "modo sem internet": "apagao", "modo impossível": "tira_teima"}
        self.assertEqual({f: modos.achar(f) for f in casos}, casos)

    def test_sair_do_modo_mineracao_desliga(self):
        modos = importlib.import_module("plugins.modos")
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        trocar(self, "plugins.modos", "ARQ_ESTADO", tmp / "modo.json")
        trocar(self, "plugins.modos", "ARQ_MEUS", tmp / "meus.json")
        chamadas = []
        with mock.patch("core.registro_ferramentas.executar", lambda n, p, pl=None: chamadas.append((n, p["action"])) or "ok"):
            modos.entrar("modo mineração")
            modos.sair()
        self.assertEqual(chamadas, [("mineracao", "calcular"), ("mineracao", "status"), ("mineracao", "desligar")])


class TestRegistro38(unittest.TestCase):
    def test_niveis_e_busca(self):
        from core import registro_ferramentas, verificacao as Vf
        from plugins import catalogo
        self.assertEqual(Vf.nivel_de("veiculo", {"action": "fiz"}), Vf.SENSIVEL)
        self.assertEqual(Vf.nivel_de("veiculo", {"action": "proximas"}), Vf.LIVRE)
        self.assertEqual(Vf.nivel_de("mapa_mental", {"action": "criar"}), Vf.LIVRE)
        self.assertEqual(Vf.nivel_de("mapa_mental", {"action": "apagar"}), Vf.SENSIVEL)
        for n in ("veiculo", "mapa_mental"):
            self.assertLessEqual(len(importlib.import_module(f"plugins.{n}").PLUGIN["brief"]), 150)
        decls = registro_ferramentas.declaracoes()
        casos = {"troquei o óleo do carro": "veiculo", "o que está vencendo na moto": "veiculo",
                 "faz um mapa mental de redes": "mapa_mental", "abre o mapa mental do senai": "mapa_mental"}
        erros = [q for q, alvo in casos.items() if alvo not in [d["name"] for d in catalogo.buscar(decls, q, 3)]]
        self.assertEqual(erros, [])


if __name__ == "__main__":
    unittest.main()
