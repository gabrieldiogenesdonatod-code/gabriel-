"""Testes da 2.18 — lote 2: 58 modos e 53 plugins (funções puras + toda ação responde com frase, sem levantar)."""
import random
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from plugins import (_lote2, _modos_extras, astronomia, calculadora, calculadora_datas, calculadora_musical, codificador,
                     cofrinho, combustivel, conversor_dados, conversor_unidades, cores, cron_explica, cronometros, eletronica,
                     juros, modos, precificacao, recibos, regex_ajuda, receitas, rodizio_tarefas, semver, sequencias,
                     sorteio, tabela_tamanhos, treino, validador_documentos)

LOTE2 = ['anagramas', 'assinaturas', 'astronomia', 'calculadora', 'calculadora_datas', 'calculadora_musical', 'cardapio',
         'checklists', 'codificador', 'codigos_hash', 'cofrinho', 'colinha_dev', 'combustivel', 'conta_luz', 'conversor_dados',
         'conversor_unidades', 'cores', 'cron_explica', 'cronometros', 'dados_falsos', 'eletronica', 'emprestimos', 'enigmas',
         'ferramentas_texto', 'hidratacao', 'horas_freela', 'juros', 'leitura_livros', 'matematica_rapida', 'modelos_dev',
         'pets', 'piadas', 'placar', 'portas_locais', 'precificacao', 'presentes', 'promocoes_loja', 'raio_x_projeto',
         'receitas', 'recibos', 'regex_ajuda', 'requisitos_python', 'respiracao', 'rodizio_tarefas', 'semver', 'sequencias',
         'snippets', 'sorteio', 'tabela_tamanhos', 'treino', 'trocas_loja', 'validador_documentos', 'watchlist']


class TestPuras(unittest.TestCase):
    def test_contas(self):
        self.assertEqual(calculadora.calcular("2^10 + raiz(16)"), 1028)
        self.assertRaises(Exception, calculadora.calcular, "__import__('os')")
        self.assertEqual(calculadora.regra3(2, 10, 5), 25)
        self.assertIn("30", calculadora.porcentagem("15% de 200"))
        self.assertAlmostEqual(conversor_unidades.converter(100, "f", "c"), 37.777, 2)
        self.assertEqual(conversor_unidades.converter(2, "xicaras", "ml"), 480)
        self.assertAlmostEqual(juros.parcela_price(1000, 0.02, 12), 94.56, 2)
        self.assertAlmostEqual(juros.composto(1000, .01, 12), 1126.83, 2)

    def test_datas_e_docs(self):
        self.assertEqual(calculadora_datas.ler_data("09/11/2026"), date(2026, 11, 9))
        self.assertEqual(calculadora_datas.dias_uteis(date(2026, 11, 9), date(2026, 11, 16)), 5)
        self.assertEqual(calculadora_datas.idade(date(2000, 12, 1), date(2026, 11, 9)), 25)
        rng = random.Random(3)
        self.assertTrue(validador_documentos.cpf_ok(validador_documentos.gerar_cpf(rng)))
        self.assertTrue(validador_documentos.cnpj_ok(validador_documentos.gerar_cnpj(rng)))
        self.assertFalse(validador_documentos.cpf_ok("111.111.111-11"))
        self.assertTrue(validador_documentos.luhn_ok("4111 1111 1111 1111"))
        self.assertIn("Mercosul", validador_documentos.validar("ABC1D23"))

    def test_extenso(self):
        self.assertEqual(recibos.extenso(1001), "mil e um")
        self.assertEqual(recibos.extenso(1250), "mil duzentos e cinquenta")
        self.assertEqual(recibos.reais_extenso(21.5), "vinte e um reais e cinquenta centavos")
        self.assertEqual(recibos.reais_extenso(1), "um real")

    def test_codigos(self):
        self.assertEqual(codificador.desmorse(codificador.morse("sos jarvis")), "sos jarvis")
        self.assertEqual(codificador.para_romano(2026), "MMXXVI")
        self.assertEqual(codificador.de_romano("XLIV"), 44)
        self.assertEqual(codificador.cesar(codificador.cesar("Jarvis", 3), -3), "Jarvis")
        self.assertEqual(codificador.base("255", 10, 16), "ff")
        self.assertEqual(cores.rgb("#f80"), (255, 136, 0))
        self.assertAlmostEqual(cores.contraste((0, 0, 0), (255, 255, 255)), 21, 1)
        self.assertEqual(regex_ajuda.testar(r"\d+", "a1b22")[1][0], "22")
        self.assertEqual(semver.proxima("1.4.2", ["fix: x", "feat(loja): y"]), "1.5.0")
        self.assertEqual(semver.proxima("1.4.2", ["feat!: muda api"]), "2.0.0")
        self.assertTrue(semver.validar("feat(loja): adiciona fiado")[0])
        self.assertFalse(semver.validar("arrumei coisas")[0])

    def test_cron(self):
        self.assertEqual(cron_explica.expandir("*/15", 0, 59), {0, 15, 30, 45})
        prox = cron_explica.proximas("30 9 * * 1-5", 2, datetime(2026, 11, 7, 10, 0))   # sábado
        self.assertEqual(prox[0], datetime(2026, 11, 9, 9, 30))

    def test_loja(self):
        self.assertAlmostEqual(precificacao.preco_ideal(50, 40, 5, 5), 100)
        self.assertAlmostEqual(precificacao.margem_real(50, 100, 5, 5), 40)
        self.assertEqual(tabela_tamanhos.por_idade("6 meses"), "M")
        self.assertEqual(tabela_tamanhos.por_altura(100), "4")
        self.assertEqual(rodizio_tarefas.divisao(["A", "B"], ["louça", "lixo", "varrer"], 0),
                         {"A": ["louça", "varrer"], "B": ["lixo"]})

    def test_vida(self):
        self.assertEqual(receitas.escalar(["2 xícaras de farinha"], 1.5), ["3 xícaras de farinha"])
        self.assertEqual(receitas.combina(["ovo", "farinha"], [{"nome": "bolo", "ingredientes": ["2 ovo", "1 xicara farinha"]}])[0][0], 1)
        self.assertEqual(treino.ler_serie("4x10 40kg"), (4, 10, 40))
        self.assertEqual(sequencias.ofensiva(["2026-11-07", "2026-11-08"], date(2026, 11, 9)), 2)
        self.assertEqual(sequencias.melhor(["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-05"]), 3)
        self.assertEqual(cofrinho.meses_ate(date(2026, 11, 9), date(2027, 5, 1)), 6)
        ok, _ = combustivel.compensa_etanol(3.9, 6.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(combustivel.media([{"km": 1000, "l": 40, "p": 6}, {"km": 1400, "l": 40, "p": 6}])[0], 10)
        par = sorteio.amigo_secreto(list("ABCDE"), random.Random(1))
        self.assertTrue(all(k != v for k, v in par.items()) and sorted(par.values()) == list("ABCDE"))
        self.assertEqual(cronometros.segundos("1h30"), 5400)
        self.assertEqual(cronometros.segundos("45 s"), 45)

    def test_tecnicos(self):
        self.assertEqual(eletronica.cores_para_ohm("amarelo violeta vermelho"), 4700)
        self.assertTrue(eletronica.ohm_para_cores(4700).startswith("amarelo violeta vermelho"))
        self.assertAlmostEqual(eletronica.led(5, 2, 20), 150)
        self.assertIn("flash", eletronica.esp32("gpio 7"))
        self.assertAlmostEqual(calculadora_musical.frequencia("A4"), 440)
        self.assertEqual(calculadora_musical.transpor("Am F C G", 2), "Bm G D A")
        self.assertEqual(calculadora_musical.acorde("Cm7"), ["C", "D#", "G", "A#"])
        self.assertAlmostEqual(calculadora_musical.delay(120)["1/4"], 500)
        nome, _ = astronomia.fase(datetime(2026, 11, 24, 15, tzinfo=timezone.utc))
        self.assertIn("cheia", nome.lower())
        nasce, poe = astronomia.sol(date(2026, 11, 9), -16.68, -49.25, -3)
        self.assertTrue("05:20" <= nasce <= "05:45" and "18:15" <= poe <= "18:40", (nasce, poe))
        d = conversor_dados.csv_para_lista("a;b\n1;2\n")
        self.assertEqual(d, [{"a": "1", "b": "2"}])
        self.assertIn("| a | b |", conversor_dados.markdown(d))


class TestTodasAsAcoes(unittest.TestCase):
    """Cada ação de cada plugin do lote 2 devolve uma frase e não levanta exceção."""

    def test_rodar_tudo(self):
        import importlib
        tmp = Path(tempfile.mkdtemp())
        exemplo = {"valor": "10", "nome": "teste", "texto": "abc", "data": "01/01/2027", "cliente": "Ana", "nomes": "A, B, C",
                   "itens": "leite, ovo", "pasta": str(tmp), "expressao": "2+2", "de": "km", "para": "m", "tempo": "1 min",
                   "cor": "#336699", "cor2": "#ffffff", "padrao": r"\d", "porta": "65000", "custo": "20", "preco": "50",
                   "pessoas": "A, B", "tarefas": "louça", "pessoa": "A", "ingredientes": "2 ovos", "codigo": "print(1)",
                   "versao": "1.0.0", "exercicio": "supino", "horas": "2", "watts": "100", "litros": "40", "km": "1000",
                   "paginas": "200", "dias": "30"}
        with mock.patch.object(_lote2, "PASTA", tmp / "lote2"), \
                mock.patch("plugins._comum.pasta_jarvis", lambda n: tmp), \
                mock.patch("plugins._comum.abrir_no_sistema", lambda *_: True), \
                mock.patch("threading.Timer.start", lambda self: None), \
                mock.patch("threading.Thread.start", lambda self: None), \
                mock.patch("core.registro_ferramentas.executar", lambda *a, **k: "ok"):
            falhas = []
            for nome in LOTE2:
                mod = importlib.import_module(f"plugins.{nome}")
                self.assertEqual(mod.PLUGIN["tier"], "extra", nome)
                self.assertLessEqual(len(mod.PLUGIN["brief"]), 150, nome)
                acoes = mod.PLUGIN["parameters"]["properties"]["action"]["description"].split(" | ")
                for a in acoes:
                    r = mod.run({**exemplo, "action": a})
                    self.assertIsInstance(r, str, f"{nome}.{a}")
                    if "falhou: " in r:            # entrada ruim vira frase; erro de programação não
                        self.assertNotRegex(r, BUG, f"{nome}.{a}: {r}")
                        falhas.append(f"{nome}.{a}: {r}")
                self.assertIn("não existe", mod.run({"action": "xyz"}))
            print("\n".join(falhas))


BUG = r"NoneType|object|attribute|unsupported|index out|KeyError|not callable|positional|unexpected keyword|referenced"


class TestModos(unittest.TestCase):
    def test_modos_extras(self):
        self.assertGreaterEqual(len(_modos_extras.MODOS_EXTRAS), 50)
        self.assertFalse(set(_modos_extras.MODOS_EXTRAS) & set(modos.MODOS))
        for k, m in _modos_extras.MODOS_EXTRAS.items():
            self.assertTrue(m["titulo"] and m["jeito"], k)
            for p in m["entrar"] + m["sair"]:
                self.assertIn(p["tipo"], {"ferramenta", "abrir", "fechar", "volume", "mudo", "mensagem", "site", "plano_energia",
                                          "modo_escuro", "modo_jogo", "minimizar_tudo"}, k)
        self.assertEqual(modos.chave("modo academia"), "treino")
        self.assertEqual(modos.chave("Modo Sherlock"), "sherlock")
        pasta = Path(tempfile.mkdtemp())
        with mock.patch.object(modos, "ARQ_ESTADO", pasta / "e.json"), mock.patch.object(modos, "ARQ_MEUS", pasta / "m.json"), \
                mock.patch.object(modos, "_rodar", lambda passos, player: []):
            self.assertIn("[MODO DEBUG]", modos.entrar("bug"))
            modos.entrar("pirata")
            self.assertEqual(modos.atual(), "pirata")
            self.assertIn("Saí", modos.sair())
            self.assertIn("Escolha outro nome", modos.run({"action": "criar", "modo": "estudo"}))


if __name__ == "__main__":
    unittest.main()
