"""
Testes da 2.16 — as 20 ideias práticas, o jogar junto e as mensagens.
Só funções puras e a internet trocada por respostas falsas: não usa rede,
teclado, câmera, WhatsApp nem IA.
"""
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from plugins import (_web, agenda, alerta_cotacao, alerta_nome, atalhos_texto, cofre_senhas, consulta_brasil,
                     controle_mei, duplicados, feriados, jogar_junto, pesquisa_profunda, planilha_viva, racha_conta,
                     verificador_link)
from plugins import _mensagens_midia as MM
from plugins import _atalhos_globais as G


class TestBrasil(unittest.TestCase):
    def test_cnpj_e_consulta(self):
        self.assertTrue(consulta_brasil.cnpj_valido("19.131.243/0001-97"))
        self.assertFalse(consulta_brasil.cnpj_valido("11111111111111"))
        falso = {"razao_social": "LOJA X LTDA", "nome_fantasia": "Loja X", "descricao_situacao_cadastral": "ATIVA",
                 "municipio": "GOIANIA", "uf": "GO", "cnae_fiscal_descricao": "Comércio varejista", "qsa": []}
        with mock.patch.object(_web, "get_json", return_value=falso):
            r = consulta_brasil.run({"action": "cnpj", "valor": "19.131.243/0001-97"})
        self.assertIn("Loja X", r)

    def test_frete(self):
        ops = consulta_brasil.opcoes_frete([{"name": "PAC", "price": "22.50", "delivery_time": 7,
                                             "company": {"name": "Correios"}}, {"name": "Y", "error": "x"}])
        self.assertEqual(ops[0]["preco"], 22.5)
        self.assertIn("22,50", consulta_brasil.texto_cliente(ops, "01001-000", "Ana Souza"))

    def test_feriados(self):
        self.assertEqual(feriados.pascoa(2026), date(2026, 4, 5))
        self.assertEqual(feriados.pascoa(2027), date(2027, 3, 28))
        lista = feriados.feriados(2027)
        self.assertIn(date(2027, 11, 20), [f["data"] for f in lista])
        es = [e for e in feriados.emendas(2027, lista) if e["emenda"]]
        corpus = next(e for e in es if e["feriado"]["nome"] == "Corpus Christi")
        self.assertEqual((corpus["emenda"]["custo"], corpus["emenda"]["dias"]), (1, 4))

    def test_cotacao(self):
        a = {"condicao": "acima", "valor": 5.8, "armado": True}
        self.assertEqual([alerta_cotacao.disparou(a, v) for v in (5.9, 6.0, 5.5, 5.9)], [True, False, False, True])
        self.assertEqual(alerta_cotacao.ativo_de("bitcoin"), ("moeda", "BTC"))

    def test_racha_e_pix(self):
        self.assertEqual(racha_conta.crc16("123456789"), "29B1")
        parte, t = racha_conta.dividir({"João": 200, "Maria": 50}, ["eu", "Ana", "Pedro"])
        self.assertEqual(parte, 50.0)
        self.assertEqual(sum(v for _d, p, v in t if p == "João"), 150.0)
        codigo = racha_conta.pix_copia_cola("joao@email.com", "João", 50, "Goiânia")
        self.assertTrue(codigo.startswith("000201") and racha_conta.crc16(codigo[:-4]) == codigo[-4:])
        self.assertEqual(racha_conta.ler_pagamentos("João pagou 200, Maria pagou 50,5"), {"João": 200.0, "Maria": 50.5})

    def test_mei(self):
        self.assertEqual(controle_mei.limite_do_ano(2026, 81000, "03/2026"), 67500)
        r = controle_mei.analise(70000, 81000, date(2026, 11, 9), 2026)
        self.assertIn("85%", r["aviso"])
        self.assertIn("20%", controle_mei.analise(90000, 81000, date(2026, 11, 9), 2026)["aviso"])

    def test_planilha(self):
        import openpyxl
        pasta = Path(tempfile.mkdtemp())
        arq = pasta / "vendas.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Relatório"])
        ws.append(["Data", "Produto", "Qtd", "Valor (R$)", "Forma de pagamento"])
        ws.append([datetime(2026, 11, 1), "Body", 1, 39.9, "Pix"])
        wb.save(arq)
        with mock.patch.object(planilha_viva, "MEMORIA", pasta):
            r = planilha_viva.run({"action": "adicionar", "arquivo": str(arq),
                                   "campos": "valor: 89; produto: moletom; quantidade: 2; pagamento: pix"})
        self.assertIn("linha 4", r)
        linha = [c.value for c in openpyxl.load_workbook(arq).active[4]]
        self.assertEqual(linha[1:], ["moletom", 2, 89, "pix"])
        self.assertIn("128,90", planilha_viva.run({"action": "total", "arquivo": str(arq), "coluna": "valor"}))


class TestAgendaEComunicacao(unittest.TestCase):
    ICS = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20261110T140000\nDTEND:20261110T150000\nSUMMARY:Dentista\n"
           "LOCATION:Rua 10\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART:20261102T090000\nDTEND:20261102T100000\n"
           "RRULE:FREQ=WEEKLY;BYDAY=MO,WE\nSUMMARY:Academia\nEND:VEVENT\nEND:VCALENDAR")

    def test_ics_e_livre(self):
        ev = agenda.ler_ics(self.ICS, datetime(2026, 11, 9), datetime(2026, 11, 12))
        self.assertEqual([e["titulo"] for e in ev], ["Academia", "Dentista", "Academia"])
        livres = agenda.livres(ev, date(2026, 11, 10), 60, ("08:00", "20:00"), "tarde")
        self.assertEqual(livres[0][1].hour, 14)
        self.assertGreater(agenda.fator_transito(datetime(2026, 11, 10, 18)), 1.3)

    def test_alerta_nome(self):
        self.assertEqual(alerta_nome.citou("Gabriel, você pode responder?", ["Gabriel"]), "Gabriel")
        self.assertIsNone(alerta_nome.citou("a Gabriela chegou", ["Gabriel"]))

    def test_midia(self):
        self.assertFalse(MM.precisa_resumo("oi tudo bem"))
        self.assertEqual(MM.resumo_local("Chego às 8. Depois te ligo."), "Chego às 8.")


class TestEscritaEPC(unittest.TestCase):
    def test_atalhos(self):
        self.assertEqual(atalhos_texto.casou("meu endereço //end", {"//end": "x"}), "//end")
        self.assertIsNone(atalhos_texto.casou("abc//end", {"//end": "x"}))
        self.assertEqual(atalhos_texto.expandir("//data", {}, datetime(2026, 11, 9)), "09/11/2026")
        self.assertIsNotNone(G.interpretar("ctrl+alt+c"))
        self.assertIsNone(G.interpretar("c"))

    def test_pesquisa(self):
        links = pesquisa_profunda.juntar_links([[{"href": "https://a.com/1"}, {"href": "https://b.com/2"}],
                                                [{"href": "https://a.com/3"}, {"href": "https://youtube.com/x"}]])
        self.assertEqual([x["url"] for x in links], ["https://a.com/1", "https://b.com/2"])

    def test_duplicados(self):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "a.bin").write_bytes(b"x" * 5000)
        (pasta / "b.bin").write_bytes(b"x" * 5000)
        (pasta / "c.bin").write_bytes(b"y" * 5000)
        grupos = duplicados.achar_duplicados(pasta.iterdir())
        self.assertEqual(len(grupos), 1)
        self.assertEqual(len(grupos[0]), 2)
        notas = {Path(f"f{i}.jpg"): v for i, v in enumerate([300, 280, 310, 20, 290])}
        self.assertEqual([p.name for p, _v in duplicados.borradas(notas)], ["f3.jpg"])

    def test_cofre(self):
        sal = b"1" * 16
        blob = cofre_senhas.selar({"senhas": {"x": {"senha": "s3gr3d0"}}}, cofre_senhas.derivar("mestra-123", sal), sal)
        self.assertEqual(cofre_senhas.abrir(blob, "mestra-123")[0]["senhas"]["x"]["senha"], "s3gr3d0")
        with self.assertRaises(ValueError):
            cofre_senhas.abrir(blob, "errada")
        self.assertNotIn(b"s3gr3d0", blob)
        s = cofre_senhas.gerar_senha(16)
        self.assertEqual(len(s), 16)

    def test_verificador(self):
        self.assertTrue(verificador_link.sinais_locais("https://itau-seguranca.xyz/login"))
        self.assertEqual(verificador_link.sinais_locais("https://www.itau.com.br/"), [])
        self.assertEqual(verificador_link.veredito({"malicious": 5, "harmless": 60})[0], "perigoso")
        self.assertTrue(verificador_link.sinais_arquivo(Path("foto.jpg.exe")))


class TestJogarJunto(unittest.TestCase):
    def test_comandos(self):
        p = jogar_junto.PERFIS["roblox"]
        self.assertEqual(jogar_junto.interpretar("anda pra frente 3 segundos e pula", p),
                         [("segurar", "w", 3.0), ("tocar", "space", 1)])
        self.assertEqual(jogar_junto.interpretar("pula 5 vezes", p), [("tocar", "space", 5)])
        self.assertEqual(jogar_junto.interpretar("escreve no chat: gg", p), [("chat", "gg")])
        self.assertEqual(jogar_junto.jogo_da_janela({"processo": "RobloxPlayerBeta.exe", "titulo": "Roblox"}), "roblox")
        d = jogar_junto.decisao('{"acao": "pular_frente", "segundos": 9}')
        self.assertEqual((d["acao"], d["segundos"]), ("pular_frente", 3.0))
        self.assertIsNone(jogar_junto.decisao('{"acao": "formatar"}'))


if __name__ == "__main__":
    unittest.main()
