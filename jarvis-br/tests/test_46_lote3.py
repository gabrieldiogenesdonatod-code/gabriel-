"""Testes da 2.19 — lote 3: catálogo sob demanda, base comum melhor, 59 plugins novos (toda ação responde) e funções puras."""
import importlib
import json
import random
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from core import orcamento_ferramentas as O
from plugins import (_lote2, abnt, algebra, analise_csv, backup_dados, banner_ascii, bingo, bits_bytes, caca_palavras, caixa_loja,
                     calculadora_ia, calculadora_ip, calculadora_obra, calculos_trabalhistas, catalogo, churrascometro, corrida,
                     cupons_loja, diario_treino_ia, eletronica_pro, env_arquivo, etiquetas, explorar_json, festa, geometria,
                     impressao_3d, investimentos, jwt_decodificar, lista_espera, log_analisador, metricas_marketing, notas_escola,
                     ponto, precos_mercado, qualidade_codigo, quitar_dividas, resumo_do_dia, revisao_espacada, segredos_codigo,
                     texto_estilizado, timestamp)

LOTE3 = ("catalogo lixeira backup_dados resumo_do_dia autodiagnostico caixa_loja lista_espera fornecedores cupons_loja "
         "cartao_fidelidade metricas_marketing etiquetas investimentos quitar_dividas precos_mercado ponto calculos_trabalhistas "
         "vencimentos despensa onde_guardei calculadora_obra churrascometro festa metas_pessoais corrida telefones_uteis bingo "
         "revisao_espacada notas_escola abnt diario_classe algebra geometria diff_texto jwt_decodificar timestamp http_teste "
         "sqlite_ajuda env_arquivo segredos_codigo qualidade_codigo log_analisador explorar_json calculadora_ip bits_bytes "
         "analise_csv eletronica_pro impressao_3d calculadora_ia diario_treino_ia banner_ascii texto_estilizado forca mini_jogos "
         "jogos_de_festa caca_palavras trava_linguas curiosidades frase_do_dia").split()
BUG = r"NoneType|object|attribute|unsupported|index out|KeyError|not callable|positional|unexpected keyword|referenced|not defined"


def decl(nome, props=("action",)):
    return {"name": nome, "description": f"Faz {nome}: " + "descrição longa de exemplo " * 5, "parameters": {"type": "OBJECT", "properties": {p: {"type": "STRING"} for p in props}}}


class TestBase(unittest.TestCase):
    def test_catalogo_sob_demanda(self):
        extras = [decl(f"p{i}") for i in range(60)]
        d = O.declaracao_apoio(extras, {"p50": 9}, completas=5)
        self.assertIn("p50(action)", d["description"])                 # a mais usada mantém a assinatura
        self.assertNotIn("p59(action)", d["description"])              # as outras entram só pelo nome
        self.assertIn("p59", d["description"])
        self.assertLess(len(d["description"]), len(O.declaracao_apoio(extras, completas=-1)["description"]) / 2)
        self.assertEqual(O.desembrulhar(O.NOME_APOIO, {"buscar": "fase da lua"}), ("catalogo", {"action": "buscar", "texto": "fase da lua"}))
        self.assertEqual(O.desembrulhar(O.NOME_APOIO, {"nome": "juros", "parametros": "?"}), ("catalogo", {"action": "ajuda", "nome": "juros"}))
        self.assertEqual(O.desembrulhar(O.NOME_APOIO, {"nome": "juros", "parametros": '{"action": "sac"}'}), ("juros", {"action": "sac"}))
        achadas = catalogo.buscar([decl("astronomia"), decl("lista_compras"), decl("juros")], "preciso da lista de compras")
        self.assertEqual(achadas[0]["name"], "lista_compras")

    def test_acoes_e_colecao(self):
        acoes = ["salvar", "ver", "listar", "apagar"]
        self.assertEqual(_lote2.escolher_acao("add", acoes), "salvar")           # sinônimo
        self.assertEqual(_lote2.escolher_acao("delete", acoes), "apagar")
        self.assertEqual(_lote2.escolher_acao("lista", acoes), "listar")         # começo
        self.assertEqual(_lote2.escolher_acao("apagr", acoes), "apagar")         # erro de digitação
        self.assertIsNone(_lote2.escolher_acao("voar", acoes))
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())):
            c = _lote2.Colecao("t")
            c.por("O Hobbit", {"x": 1})
            c.por("Duna", {"x": 2})
            self.assertEqual(c.pegar("hobbit")["x"], 1)                         # nome aproximado
            self.assertEqual(c.pegar("dunna")["x"], 2)
            self.assertIsNone(c.pegar("xyz"))
            self.assertTrue(c.tirar("hobbit"))
            lix = importlib.import_module("plugins.lixeira")
            self.assertIn("O Hobbit", lix.run({"action": "listar"}))
            self.assertIn("voltou", lix.run({"action": "restaurar", "nome": "hobbit"}))
            self.assertEqual(c.pegar("O Hobbit")["x"], 1)
            self.assertIn("Ações", importlib.import_module("plugins.onde_guardei").run({"action": "ajuda"}))

    def test_backup_e_resumo(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "mem" / "lote2").mkdir(parents=True)
        (tmp / "mem" / "lote2" / "a.json").write_text("{}")
        (tmp / "mem" / "codigo.py").write_text("x = 1")
        z = backup_dados.fazer(tmp, tmp / "mem")
        (tmp / "mem" / "lote2" / "a.json").unlink()
        self.assertEqual(backup_dados.restaurar(z, tmp / "mem"), 1)             # .py fica de fora
        self.assertTrue((tmp / "mem" / "lote2" / "a.json").exists())
        linhas = resumo_do_dia.montar(lambda n, a: {"sequencias": "Falta hoje: ler.", "pets": "Nada vencendo."}.get(n, "Nenhum."))
        self.assertEqual(linhas, ["Hábitos: Falta hoje: ler."])


class TestPuras(unittest.TestCase):
    def test_loja(self):
        d = {"abertura": 100, "vendas": [[50, "dinheiro"], [80, "pix"]], "sangrias": [30], "suprimentos": [10]}
        self.assertEqual(caixa_loja.gaveta(d), 130)
        self.assertEqual(caixa_loja.totais(d), {"dinheiro": 50, "pix": 80})
        fila = [{"cliente": "Ana", "produto": "Body azul", "tamanho": "P", "fone": ""}, {"cliente": "Bia", "produto": "body azul", "tamanho": "M", "fone": ""}]
        self.assertEqual([x["cliente"] for x in lista_espera.interessados(fila, "body azul", "p")], ["Ana"])
        c = {"tipo": "%", "valor": 10, "usos": 1, "usados": 0, "minimo": 50, "validade": "2026-12-31"}
        self.assertEqual(cupons_loja.desconto(c, 200, date(2026, 11, 12)), (True, 20.0, ""))
        self.assertFalse(cupons_loja.desconto(c, 200, date(2027, 1, 1))[0])
        self.assertFalse(cupons_loja.desconto(c, 40, date(2026, 11, 12))[0])
        self.assertEqual(etiquetas.ler_item("3x Body azul P 39,90"), (3, "Body azul", "P", 39.9))
        self.assertEqual(etiquetas.ler_item("Conjunto moletom 4 89,90"), (1, "Conjunto moletom", "4", 89.9))
        self.assertAlmostEqual(metricas_marketing.roas_equilibrio(40), 2.5)

    def test_dinheiro_trabalho(self):
        self.assertEqual([investimentos.ir_regressivo(d) for d in (30, 200, 400, 800)], [22.5, 20.0, 17.5, 15.0])
        b, ir, liq = investimentos.cdb_liquido(1000, 12, 365)
        self.assertAlmostEqual(b, 120, 1)
        self.assertAlmostEqual(liq, 120 * 0.825, 1)
        ds = [{"nome": "cartão", "saldo": 1000, "juros": 10, "minimo": 50}, {"nome": "loja", "saldo": 300, "juros": 2, "minimo": 30}]
        av, bn = quitar_dividas.simular(ds, 400), quitar_dividas.simular(ds, 400, "bola_de_neve")
        self.assertLessEqual(av[1], bn[1])                                      # avalanche paga menos juros
        self.assertEqual(bn[2][0], "loja")
        self.assertIsNone(quitar_dividas.simular(ds, 50))
        self.assertAlmostEqual(precos_mercado.ler_opcao("500 g 8,90")[0], 17.8)
        self.assertEqual(precos_mercado.ler_opcao("1 kg 16,50")[:2], (16.5, "kg"))
        self.assertAlmostEqual(ponto.horas(["08:00", "12:00", "13:00", "17:30"]), 8.5)
        self.assertEqual(ponto.hm(-1.25), "-1h15")
        self.assertAlmostEqual(calculos_trabalhistas.decimo(3000, 6), 1500)
        self.assertAlmostEqual(calculos_trabalhistas.ferias(3000)[0], 4000)
        self.assertAlmostEqual(calculos_trabalhistas.hora_extra(2200, 10), 150)

    def test_casa(self):
        self.assertEqual(calculadora_obra.latas(20), "1 de 18 L + 1 de 3,6 L")
        self.assertEqual(calculadora_obra.pecas(10, 60, 60, 10), 31)
        self.assertEqual(calculadora_obra.area({"comprimento": "4", "altura": "2,5"}), 10)
        q = churrascometro.quantidades(10, 4)
        self.assertAlmostEqual(q["_carne_total"], 4.8)
        self.assertEqual(festa.quantidades(20)["salgados"], 240)
        self.assertAlmostEqual(corrida.minutos("1:02:30"), 62.5)
        self.assertEqual(corrida.ritmo(5, 28.5), "5:42/km")
        self.assertAlmostEqual(corrida.riegel(25, 5, 10), 52.1, 1)
        cart = bingo.cartela(random.Random(1))
        self.assertTrue(all(1 <= cart[l][0] <= 15 and 61 <= cart[l][4] <= 75 for l in range(5)) and cart[2][2] == "★")
        self.assertEqual([bingo.letra(n) for n in (1, 16, 31, 46, 75)], list("BINGO"))

    def test_estudo(self):
        self.assertEqual(revisao_espacada.proxima(0, date(2026, 11, 12)), "2026-11-13")
        self.assertIsNone(revisao_espacada.proxima(6, date(2026, 11, 12)))
        self.assertAlmostEqual(notas_escola.media([7, 9], [1, 3]), 8.5)
        self.assertAlmostEqual(notas_escola.preciso([5, 6], [1, 1], 2, 6), 6.5)
        self.assertEqual(notas_escola.faltas_permitidas(80), 20)
        self.assertEqual(abnt.sobrenome("João da Silva Filho"), ("SILVA FILHO", "João da"))
        self.assertEqual(abnt.autores("Ana Souza; Bruno Lima"), "SOUZA, Ana; LIMA, Bruno.")
        self.assertIn("SILVA, João. O livro. 2. ed. Goiânia: Editora X, 2020.", abnt.run(
            {"action": "livro", "autor": "João Silva", "titulo": "O livro", "edicao": "2", "local": "Goiânia", "editora": "Editora X", "ano": "2020"}))
        self.assertEqual(abnt.run({"action": "citacao", "autor": "João Silva", "ano": "2020", "pagina": "15"}), "(Silva, 2020, p. 15)")
        self.assertEqual(algebra.bhaskara(1, -5, 6), (1, [2.0, 3.0]))
        self.assertEqual(algebra.fatores(360), [2, 2, 2, 3, 3, 5])
        self.assertEqual(str(algebra.fracao("3/4 + 2/5")), "23/20")
        t = geometria.triangulo(3, 4, 5)
        self.assertAlmostEqual(t["area"], 6)
        self.assertIn("retângulo", t["tipo"])

    def test_dev(self):
        tok = "eyJhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxIiwiZXhwIjoxfQ" + ".x"
        self.assertEqual(jwt_decodificar.partes(tok), ({"alg": "HS256"}, {"sub": "1", "exp": 1}))
        self.assertIn("EXPIRADO", jwt_decodificar.validade({"exp": 1}, 1000))
        self.assertEqual(timestamp.de_epoch(1700000000000), timestamp.de_epoch(1700000000))
        self.assertEqual(timestamp.de_epoch(timestamp.para_epoch("12/11/2026 14:30")).strftime("%d/%m/%Y %H:%M"), "12/11/2026 14:30")
        self.assertEqual(env_arquivo.ler_env("# c\nA=1\nexport B='x y'\n"), {"A": "1", "B": "x y"})
        self.assertTrue(env_arquivo.ignorado("node_modules/\n.env\n"))
        achou = segredos_codigo.achar('x = 1\napi_key = "abcdefgh12345678"\nurl = "https://exemplo.com"\n')
        self.assertEqual([(a[0], a[1]) for a in achou], [(2, "segredo em atribuição")])
        src = "def f(a, b=[]):\n    try:\n        print(a)\n    except:\n        pass\n"
        self.assertEqual({t for _, t, _ in qualidade_codigo.analisar_codigo(src)}, {"default mutável", "print esquecido", "except genérico"})
        r = log_analisador.resumir(["2026-11-12 10:00 INFO ok", "2026-11-12 10:01 ERROR falhou 12", "2026-11-12 10:02 ERROR falhou 99"])
        self.assertEqual((r["niveis"], r["top"][0][1], r["inicio"]), ({"INFO": 1, "ERROR": 2}, 2, "2026-11-12 10:00"))
        d = {"usuarios": [{"nome": "Ana", "idade": 30}]}
        self.assertEqual(explorar_json.pegar(d, "usuarios[0].nome"), "Ana")
        self.assertEqual(explorar_json.achar(d, "ana"), ["usuarios[0].nome = Ana"])
        i = calculadora_ip.info("192.168.1.10/24")
        self.assertEqual((i["rede"], i["broadcast"], i["hosts"], i["privada"]), ("192.168.1.0/24", "192.168.1.255", 254, True))
        self.assertEqual(bits_bytes.bitwise("0xF0 & 0x3C"), 0x30)
        self.assertEqual(bits_bytes.humano(1536), "1.50 KB")
        self.assertEqual(bits_bytes.tipo_por_assinatura(b"\x89PNG\r\n"), "PNG")
        self.assertEqual(analise_csv.numero_br("R$ 1.234,56"), 1234.56)
        linhas = [{"mes": "jan", "valor": "10,50"}, {"mes": "jan", "valor": "5"}, {"mes": "fev", "valor": "20"}]
        self.assertEqual(analise_csv.somar_por(linhas, "valor", "mes"), [("fev", 20.0), ("jan", 15.5)])

    def test_maker_ia_texto(self):
        self.assertEqual(eletronica_pro.capacitor("104"), 100000)
        self.assertEqual(eletronica_pro.farad(100000), "100 nF")
        self.assertAlmostEqual(eletronica_pro.fita_led(60, 50), 1.8)
        self.assertAlmostEqual(impressao_3d.metros(1000, "pla"), 335.3, 0)
        self.assertEqual(calculadora_ia.parametros_gpt(50257, 768, 12, 1024), 124_439_808)     # GPT-2 pequeno
        self.assertEqual(calculadora_ia.grande("124M"), 124e6)
        self.assertAlmostEqual(calculadora_ia.lr_cosseno(0, 100, 1000, 1.0), 0.01)
        self.assertAlmostEqual(calculadora_ia.lr_cosseno(550, 100, 1000, 1.0), 0.5)
        pts = [[1, 3.0, 3.1], [2, 2.5, 3.2], [3, 2.0, 3.4]]
        self.assertTrue(diario_treino_ia.overfitting(pts))
        self.assertEqual(diario_treino_ia.tendencia(pts), "caindo bem")
        self.assertEqual(diario_treino_ia.melhor(pts)[0], 1)
        self.assertEqual(len(banner_ascii.banner("OI").splitlines()), 5)
        self.assertEqual(texto_estilizado.estilizar("Ab1", "negrito"), "𝗔𝗯𝟭")
        self.assertEqual(texto_estilizado.estilizar("ab", "invertido"), "qɐ")
        grade, postas = caca_palavras.gerar(["gato", "pato", "tucano"], 10, rng=random.Random(2))
        self.assertEqual(sorted(postas), ["GATO", "PATO", "TUCANO"])
        self.assertTrue(any("GATO" in "".join(l) for l in grade) or any("GATO" in "".join(c) for c in zip(*grade)))


class TestTodasAsAcoes(unittest.TestCase):
    """Cada ação de cada plugin do lote 3 devolve uma frase e não levanta exceção."""

    def test_rodar_tudo(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "mem").mkdir()
        (tmp / "mem" / "x.json").write_text("{}")
        db = tmp / "b.db"
        con = sqlite3.connect(db)
        con.execute("create table vendas (id integer primary key, valor real)")
        con.execute("insert into vendas (valor) values (10.5)")
        con.commit()
        con.close()
        (tmp / "a.log").write_text("2026-11-12 10:00 ERROR falhou\n")
        (tmp / "a.csv").write_text("mes;valor\njan;10,5\n")
        (tmp / ".env").write_text("A=1\n")
        (tmp / "m.py").write_text("def f():\n    return 1\n")
        exemplo = {"valor": "10", "nome": "teste", "texto": "abc", "data": "01/01/2027", "cliente": "Ana", "nomes": "A, B",
                   "pasta": str(tmp), "itens": "2x Body P 10", "produto": "body", "tamanho": "P", "total": "100", "codigo": "X10",
                   "salario": "3000", "km": "5", "tempo": "30:00", "objeto": "chave", "lugar": "gaveta", "area": "10",
                   "adultos": "4", "tema": "tema x", "notas": "7 8", "turma": "T1", "alunos": "Ana, Beto", "aluno": "Ana",
                   "autor": "Ana Lima", "titulo": "Livro", "a": "x\ny", "b": "x\nz", "token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.x",
                   "arquivo": str(tmp / "a.log"), "ip": "10.0.0.1/24", "outro": "10.0.0.9", "url": "localhost:1", "sql": "select * from vendas",
                   "tabela": "vendas", "opcoes": "500 g 8; 1 kg 15", "validade": "01/01/2027", "prazo": "01/01/2027", "saldo": "500",
                   "juros": "2", "minimo": "20", "gramas": "100", "horas": "2", "loss": "2", "passos": "1000", "numeros": "1 2",
                   "interacoes": "50", "seguidores": "1000", "receita": "500", "gasto": "100", "vendas": "5", "visitas": "200",
                   "caminho": "a", "coluna": "valor", "por": "mes", "idade": "30", "aulas": "80", "faltei": "3", "passo": "10"}
        especiais = {"sqlite_ajuda": {"arquivo": str(db)}, "analise_csv": {"arquivo": str(tmp / "a.csv")},
                     "explorar_json": {"texto": '{"a": {"b": 1}}'}, "bits_bytes": {"arquivo": str(db), "valor": "255"},
                     "algebra": {"valor": "1 -5 6 2 1 4", "texto": "1/2 + 1/3"}, "geometria": {"valor": "3 4 5", "forma": "caixa"},
                     "eletronica_pro": {"valor": "1000 100 10"}, "segredos_codigo": {"pasta": str(tmp)}, "caca_palavras": {"tema": "frutas"},
                     "texto_estilizado": {"estilo": "negrito"}, "forca": {"valor": "a", "tema": "casa"}, "mini_jogos": {"valor": "par 3 pedra"}}
        falso = {"status": 200, "ms": 5.0, "cabecalhos": {"Content-Type": "application/json"}, "corpo": '{"ok": true}'}
        from core import registro_ferramentas
        registro_ferramentas._plugins_reg()        # o carregador recria os módulos: carregue ANTES de trocar as pastas
        with mock.patch.object(_lote2, "PASTA", tmp / "lote3"), mock.patch("plugins._comum.pasta_jarvis", lambda n: tmp), \
                mock.patch("plugins.backup_dados.pasta_jarvis", lambda n: tmp), mock.patch("plugins.backup_dados.MEMORIA", tmp / "mem"), \
                mock.patch("plugins._comum.abrir_no_sistema", lambda *_: True), mock.patch("plugins.http_teste.pedir", lambda *a, **k: falso), \
                mock.patch("threading.Timer.start", lambda self: None):
            falhas = []
            for nome in LOTE3:
                mod = importlib.import_module(f"plugins.{nome}")
                self.assertEqual(mod.PLUGIN["tier"], "extra", nome)
                self.assertLessEqual(len(mod.PLUGIN["brief"]), 190, nome)
                for a in mod.PLUGIN["parameters"]["properties"]["action"]["description"].split(" | "):
                    r = mod.run({**exemplo, **especiais.get(nome, {}), "action": a})
                    self.assertIsInstance(r, str, f"{nome}.{a}")
                    if "falhou: " in r:
                        self.assertNotRegex(r, BUG, f"{nome}.{a}: {r}")
                        falhas.append(f"{nome}.{a}: {r}")
                self.assertIn("não existe", mod.run({"action": "xyzw"}), nome)
            print("\n".join(falhas))


class TestModosLote3(unittest.TestCase):
    def setUp(self):
        from plugins import modos
        self.modos, pasta = modos, Path(tempfile.mkdtemp())
        self.p = [mock.patch.object(modos, "ARQ_ESTADO", pasta / "e.json"), mock.patch.object(modos, "ARQ_MEUS", pasta / "m.json"),
                  mock.patch.object(modos, "_rodar", lambda passos, player: []), mock.patch("threading.Timer.start", lambda self: None)]
        for x in self.p:
            x.start()

    def tearDown(self):
        self.modos._cancelar_tempo()
        for x in self.p:
            x.stop()

    def test_tabela(self):
        from plugins._modos_extras import MODOS_EXTRAS
        from plugins._modos_lote3 import CATEGORIAS, MODOS_LOTE3
        m = self.modos
        self.assertGreaterEqual(len(MODOS_LOTE3), 80)
        self.assertFalse(set(MODOS_LOTE3) & (set(MODOS_EXTRAS) | set(m.MODOS)))
        prontos = set(m.MODOS) | set(MODOS_EXTRAS) | set(MODOS_LOTE3)
        em_categoria = [i for ids in CATEGORIAS.values() for i in ids]
        self.assertEqual(sorted(em_categoria), sorted(prontos))                 # todo modo em exatamente uma categoria
        tipos = {"ferramenta", "abrir", "fechar", "volume", "mudo", "mensagem", "site", "plano_energia", "modo_escuro", "modo_jogo", "minimizar_tudo"}
        for k, modo in MODOS_LOTE3.items():
            self.assertTrue(modo["titulo"] and len(modo["jeito"]) > 30, k)
            self.assertTrue(all(p["tipo"] in tipos for p in modo["entrar"] + modo["sair"]), k)

    def test_nome_aproximado_e_busca(self):
        m = self.modos
        casos = {"modo refatorar": "refatoracao", "modo academia": "treino", "Modo Sextou": "sextou", "modo cozinhar bolo": "cozinha",
                 "modo dia difícil": "dia_dificil", "modo refatoracão": "refatoracao", "modo xyzabc": None}
        self.assertEqual({k: m.achar(k) for k in casos}, casos)
        self.assertEqual(set(m.buscar("estudar para a prova")[:2]), {"estudo", "prova"})
        self.assertIn("[MODO REFATORACAO]", m.entrar("refatorar"))
        self.assertIn("Parecidos", m.entrar("estudar pra prova"))               # ambíguo: sugere em vez de chutar
        self.assertIn("Abertura da loja", m.run({"action": "listar", "modo": "modos de loja"}))
        self.assertIn("158 em 12 categorias", m.run({"action": "listar"}))          # 3.6: +10 "impossíveis"; 3.8: +3

    def test_tempo_sugestao_historico(self):
        import time
        m = self.modos
        r = m.run({"action": "por_tempo", "modo": "foco", "minutos": "50"})
        self.assertIn("desliga sozinho em 50 minutos", r)
        self.assertEqual((m.atual(), len(m._temporizador)), ("foco_profundo", 1))
        m.sair()
        self.assertEqual((m.atual(), len(m._temporizador)), ("", 0))
        self.assertIn("Foco profundo 1x", m.run({"action": "historico"}))
        quinta_9h, domingo_10h = time.struct_time((2026, 11, 12, 9, 0, 0, 3, 316, 0)), time.struct_time((2026, 11, 15, 10, 0, 0, 6, 319, 0))
        self.assertEqual(m.sugerir(quinta_9h, [])[0], "expediente")
        self.assertEqual(m.sugerir(domingo_10h, [])[0], "domingo")
        t = time.mktime(quinta_9h)
        self.assertEqual(m.sugerir(quinta_9h, [{"m": "debug", "t": t}] * 3)[0], "debug")      # o hábito vence o padrão
        self.assertIn("Quer que eu ligue?", m.run({"action": "sugerir"}))


class TestUpgradesDoLote2(unittest.TestCase):
    def test_contas(self):
        from plugins import astronomia, conversor_unidades, juros, validador_documentos
        pri, ult, js = juros.sac(12000, 0.01, 12)
        self.assertEqual((round(pri, 2), round(ult, 2), round(js, 2)), (1120.0, 1010.0, 780.0))
        self.assertLess(js, juros.parcela_price(12000, 0.01, 12) * 12 - 12000)       # SAC paga menos juros que a Price
        self.assertAlmostEqual(conversor_unidades.converter(32, "psi", "bar"), 2.206, 2)
        self.assertAlmostEqual(conversor_unidades.converter(10, "km/l", "l/100km"), 10)
        self.assertAlmostEqual(conversor_unidades.converter(100, "cv", "kw"), 73.55, 1)
        self.assertEqual(validador_documentos.formatar("62999990000"), "(62) 99999-0000")
        self.assertEqual(validador_documentos.formatar("74000000"), "74000-000")
        self.assertEqual([astronomia.estacao(date(2026, m, 15)) for m in (1, 4, 7, 10)], ["verão", "outono", "inverno", "primavera"])
        self.assertEqual(astronomia.estacao(date(2026, 1, 15), 40), "inverno")
        (n, po), (m6, t6) = astronomia.sol(date(2026, 11, 13), -16.68, -49.25, -3), astronomia.sol(date(2026, 11, 13), -16.68, -49.25, -3, 84)
        self.assertTrue(n < m6 < t6 < po, (n, m6, t6, po))                           # hora dourada fica dentro do dia

    def test_amigo_secreto_guarda_segredo(self):
        sorteio = importlib.import_module("plugins.sorteio")
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())):
            r = sorteio.run({"action": "amigo_secreto", "nomes": "Ana, Beto, Caio"})
            self.assertNotIn("→", r)                                                 # não mostra mais os pares
            ana = sorteio.run({"action": "quem_tirei", "nomes": "ana"})
            self.assertTrue(ana.startswith("Ana, você tirou ") and "Ana." not in ana.split("tirou")[1])
            self.assertIn("Não achei", sorteio.run({"action": "quem_tirei", "nomes": "Zeca"}))

    def test_timers_voltam_depois_de_reiniciar(self):
        import time
        cron = importlib.import_module("plugins.cronometros")
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), mock.patch("threading.Timer.start", lambda self: None):
            cron._TIMERS.clear()
            cron.run({"action": "timer", "nome": "bolo", "tempo": "10 min"})
            self.assertAlmostEqual(_lote2.carregar("timers", {})["bolo"], time.time() + 600, delta=5)
            cron._TIMERS.clear()                                                     # "fechou o JARVIS"
            _lote2._timers_restaurados = False
            self.assertEqual(cron.restaurar(), 1)
            self.assertIn("bolo", cron._TIMERS)
            self.assertEqual(cron.restaurar(), 0)                                    # só restaura uma vez
            cron.run({"action": "cancelar", "nome": "bolo"})
            self.assertEqual(_lote2.carregar("timers", {}), {})

    def test_outros(self):
        from plugins import celular_android, modelos_dev
        self.assertIn("pytest -q", modelos_dev.conteudo("ci")[1])
        with mock.patch("shutil.which", lambda _: None):
            for a in ("brilho", "falar", "discar", "contato"):
                self.assertIn("só funciona no celular", celular_android.run({"action": a, "texto": "62 99999-0000", "valor": "50"}))
        hid = importlib.import_module("plugins.hidratacao")
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())):
            hid.run({"action": "bebi", "valor": "700"})
            self.assertIn("média de 100 ml", hid.run({"action": "semana"}))


if __name__ == "__main__":
    unittest.main()
