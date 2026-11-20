"""
Testes da 2.5 — casa e contas: boletos, contas a vencer, rastreio de
encomendas, garantias e manuais, chuva ("recolhe a roupa!") e caixinha de ideias.
Nada vai para a internet: 17TRACK, Gemini, radar e e-mail são simulados.
"""
import email.mime.application
import email.mime.multipart
import email.mime.text
import time
import unittest
from datetime import date, datetime
from unittest import mock

import numpy as np

from plugins import _boleto as B
from plugins import _rastreio as R
from tests import TMP


def boleto_banco(venc: date, centavos: int, banco: str = "341") -> tuple[str, str]:
    """(barras, linha) de um boleto de banco válido."""
    fator = (venc - B.BASE_2).days + 1000
    corpo = banco + "9" + f"{fator:04d}" + f"{centavos:010d}" + "1234567890123456789012345"
    barras = corpo[:4] + str(B.mod11_banco(corpo)) + corpo[4:]
    return barras, B.barras_para_linha(barras)


def conta_consumo(centavos: int, segmento: str = "3") -> str:
    """Linha de 48 dígitos de uma conta de consumo (ident 6 = mod 10)."""
    sem_dv = "8" + segmento + "6" + f"{centavos:011d}" + "0123" + "4567890123456789012345678"
    barras = sem_dv[:3] + str(B.mod10(sem_dv)) + sem_dv[3:]
    blocos = [barras[i:i + 11] for i in range(0, 44, 11)]
    return "".join(b + str(B.mod10(b)) for b in blocos)


def s10(prefixo: str, serial: str, pais: str = "BR") -> str:
    soma = sum(int(d) * p for d, p in zip(serial, (8, 6, 4, 2, 3, 5, 9, 7)))
    dv = 11 - soma % 11
    return f"{prefixo}{serial}{0 if dv == 10 else 5 if dv == 11 else dv}{pais}"


class TestBoleto(unittest.TestCase):
    def test_boleto_de_banco_ciclo_novo(self):
        barras, linha = boleto_banco(date(2026, 11, 13), 14200)
        info = B.ler_codigo(linha, hoje=date(2026, 11, 6))
        self.assertEqual(info["valor"], 142.0)
        self.assertEqual(info["vencimento"], date(2026, 11, 13))
        self.assertEqual(info["barras"], barras)
        self.assertEqual(B.linha_para_barras(linha), barras)

    def test_digito_trocado_nao_vira_conta(self):
        _barras, linha = boleto_banco(date(2026, 11, 13), 14200)
        errado = linha[:5] + str((int(linha[5]) + 1) % 10) + linha[6:]
        self.assertIsNone(B.ler_codigo(errado))

    def test_conta_de_luz(self):
        info = B.ler_codigo(conta_consumo(14237))
        self.assertEqual(info["tipo_codigo"], "arrecadacao")
        self.assertEqual(info["segmento"], "luz/gás")
        self.assertAlmostEqual(info["valor"], 142.37)

    def test_texto_do_pdf_e_frase(self):
        texto = (f"EQUATORIAL GOIAS DISTRIBUIDORA DE ENERGIA\nBeneficiário: EQUATORIAL GOIAS\n"
                 f"Vencimento: 13/11/2026   Total a pagar R$ 142,37\n{conta_consumo(14237)}")
        info = B.ler_texto(texto)
        self.assertEqual((info["tipo"], info["vencimento"]), ("luz", date(2026, 11, 13)))
        conta = {"descricao": "conta de luz", "vencimento": "2026-11-13", "valor": 142.0}
        self.assertEqual(B.frase_aviso(conta, date(2026, 11, 10)), "A conta de luz vence sexta, R$ 142.")
        self.assertEqual(B.reais(1234.5), "R$ 1.234,50")
        self.assertEqual(B.nome_da_conta({"descricao": "boleto da escola"}), "O boleto da escola")


class TestContas(unittest.TestCase):
    def setUp(self):
        from plugins import contas
        self.c = contas
        contas.ARQ.unlink(missing_ok=True)

    def test_anotar_avisar_e_pagar(self):
        _b, linha = boleto_banco(date(2026, 11, 13), 14200)
        self.assertIn("R$ 142", self.c.run({"action": "ler", "linha": linha, "descricao": "conta de luz"}))
        self.assertIn("já tinha", self.c.run({"action": "ler", "linha": linha}))
        falas = []
        with mock.patch.object(self.c, "_avisar", lambda t, u=False: falas.append(t)):
            self.c.verificar(date(2026, 11, 10))
            self.c.verificar(date(2026, 11, 10))               # não repete
            self.c.verificar(date(2026, 11, 13))
        self.assertEqual(falas, ["A conta de luz vence sexta, R$ 142.", "A conta de luz vence hoje, R$ 142."])
        self.assertIn("paga", self.c.run({"action": "pagar", "descricao": "luz"}))
        self.assertIn("Nenhuma", self.c.run({"action": "listar"}))

    def test_data_falada(self):
        self.assertEqual(self.c.data_falada("14/11", date(2026, 11, 6)), date(2026, 11, 14))
        self.assertEqual(self.c.data_falada("05/01", date(2026, 11, 6)), date(2027, 1, 5))

    @unittest.skipUnless(__import__("importlib").util.find_spec("reportlab") and
                         __import__("importlib").util.find_spec("pdfplumber"), "precisa de reportlab e pdfplumber")
    def test_pdf_e_email(self):
        from reportlab.pdfgen import canvas
        pdf = TMP / "fatura_luz.pdf"
        cv = canvas.Canvas(str(pdf))
        for k, linha in enumerate(["EQUATORIAL GOIAS DISTRIBUIDORA", "Vencimento: 13/11/2026",
                                   "Total a pagar R$ 142,37", conta_consumo(14237)]):
            cv.drawString(40, 800 - 20 * k, linha)
        cv.save()
        self.assertIn("142,37", self.c.ler_arquivo(pdf))
        self.c.ARQ.unlink()
        msg = email.mime.multipart.MIMEMultipart()
        msg["Subject"], msg["Message-ID"] = "Sua fatura chegou", "<1@teste>"
        msg.attach(email.mime.text.MIMEText("Segue a fatura."))
        anexo = email.mime.application.MIMEApplication(pdf.read_bytes(), Name="fatura.pdf")
        anexo["Content-Disposition"] = 'attachment; filename="fatura.pdf"'
        msg.attach(anexo)

        class Imap:
            def __init__(self, servidor):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def login(self, u, s):
                pass

            def select(self, *a, **k):
                return "OK", [b"1"]

            def search(self, *a):
                return "OK", [b"1"]

            def fetch(self, n, q):
                return "OK", [(b"1", msg.as_bytes())]
        conf = {"email": "eu@exemplo.com", "senha_app": "x", "imap": "imap.exemplo.com", "dias_antes": "3"}
        with mock.patch("imaplib.IMAP4_SSL", Imap), mock.patch.object(self.c, "_c", lambda: conf), \
                mock.patch.object(self.c, "pasta", lambda: TMP / "contas_email"):
            novos = self.c.ler_email()
            self.assertEqual(len(novos), 1)
            self.assertIn("142,37", novos[0])
            self.assertEqual(self.c.ler_email(), [])            # o mesmo e-mail não é lido duas vezes


class TestRastreio(unittest.TestCase):
    def test_codigo(self):
        cod = s10("QB", "12345678")
        self.assertTrue(R.s10_valido(cod))
        self.assertFalse(R.s10_valido(cod[:10] + str((int(cod[10]) + 1) % 10) + "BR"))
        self.assertIsNone(R.s10_valido("ABC123"))
        self.assertEqual(R.achar_codigos(f"Código: {cod[:2]} {cod[2:5]} {cod[5:8]} {cod[8:11]} {cod[11:]}, "
                                         "fone 62999998888"), [cod])
        self.assertEqual(R.transportadora_provavel(cod), "Correios")

    def test_mudancas_e_frases(self):
        e = {"codigo": "X", "loja": "Shopee", "apelido": "fone", "categoria": "pessoal"}
        antes = {"status": "InTransit", "evento": "Em trânsito", "quando": "1"}
        self.assertEqual(R.mudanca(antes, {"status": "OutForDelivery", "evento": "Saiu", "quando": "2"}),
                         ("saiu", "normal"))
        self.assertIsNone(R.mudanca(antes, {"status": "InTransit", "evento": "Outro centro", "quando": "2"}))
        self.assertEqual(R.mudanca(antes, {"status": "InTransit", "evento": "Outro", "quando": "2"}, True)[0],
                         "movimento")
        self.assertEqual(R.mudanca(antes, {"status": "InTransit", "evento": "Aguardando pagamento", "quando": "3"}),
                         ("taxa", "normal"))
        self.assertEqual(R.frase(e, "saiu", {}), "Senhor, sua encomenda da Shopee (fone) saiu pra entrega.")
        loja = {"codigo": "Y", "categoria": "loja", "fornecedor": "Malhas Sul"}
        self.assertEqual(R.frase(loja, "problema", {"sub_status": "Exception_Lost"}),
                         "Senhor, o pedido do fornecedor Malhas Sul foi extraviado.")
        self.assertEqual(R.preposicao("Mercado Livre"), "do")

    def test_normalizar(self):
        item = {"number": "X", "track_info": {
            "latest_status": {"status": "OutForDelivery", "sub_status": "OutForDelivery_Other"},
            "latest_event": {"time_iso": "2026-11-06T08:10:00-03:00", "description": "Saiu para entrega",
                             "location": "GOIANIA - GO"},
            "tracking": {"providers": [{"provider": {"name": "Brazil Correios"}, "events": [
                {"time_iso": "2026-11-04T09:00:00-03:00", "description": "Postado"},
                {"time_iso": "2026-11-06T08:10:00-03:00", "description": "Saiu para entrega"}]}]}}}
        n = R.normalizar(item)
        self.assertEqual((n["status"], n["transportadora"], n["eventos"][0]["texto"]),
                         ("OutForDelivery", "Brazil Correios", "Saiu para entrega"))

    def test_plugin_com_17track_simulado(self):
        from plugins import rastreio as P
        P.ARQ.unlink(missing_ok=True)
        cod = s10("QB", "87654321")
        estado = {"s": ("InTransit", "Objeto em trânsito")}

        def post(caminho, corpo, chave, timeout=20):
            if caminho == "register":
                return {"accepted": [{"number": c["number"]} for c in corpo]}
            st, desc = estado["s"]
            return {"accepted": [{"number": c["number"], "track_info": {
                "latest_status": {"status": st}, "latest_event": {"description": desc, "time_iso": st}}}
                for c in corpo]}
        falas = []
        with mock.patch.object(R, "_post", post), mock.patch.object(P, "_chave", lambda: "k"), \
                mock.patch.object(P, "_avisar", lambda t, p: falas.append(t)), mock.patch("threading.Thread"):
            self.assertIn("acompanhando", P.run({"action": "adicionar", "codigo": cod, "apelido": "fone"}))
            P.atualizar()
            estado["s"] = ("OutForDelivery", "Saiu para entrega")
            P.atualizar()
            P.atualizar()
        self.assertEqual(falas[-1], "Senhor, sua encomenda (fone) saiu pra entrega.")
        self.assertEqual(sum("saiu pra entrega" in f for f in falas), 1)
        self.assertIn("fone", P.run({"action": "listar"}))

    def test_sem_chave_abre_a_pagina(self):
        from plugins import rastreio as P
        P.ARQ.unlink(missing_ok=True)
        abertos = []
        with mock.patch.object(P, "_chave", lambda: ""), mock.patch.object(P, "abrir_no_sistema", abertos.append):
            r = P.run({"action": "adicionar", "codigo": s10("AB", "11112222")})
        self.assertIn("17track", r)
        self.assertTrue(abertos and "17track.net" in abertos[0])


class TestGarantias(unittest.TestCase):
    def setUp(self):
        from plugins import garantias
        self.g = garantias
        garantias.ARQ.unlink(missing_ok=True)

    def test_datas_e_avisos(self):
        self.assertEqual(self.g.somar_meses(date(2026, 1, 31), 1), date(2026, 2, 28))
        it = {"tipo": "geladeira", "fim": "2026-11-20", "avisos": {}}
        self.assertEqual(self.g.avisos_devidos([it], date(2026, 11, 6)), [(it, "30")])
        it["avisos"]["30"] = 1
        self.assertEqual(self.g.avisos_devidos([it], date(2026, 11, 15)), [(it, "7")])
        self.assertEqual(self.g.frase_aviso(it, "7", date(2026, 11, 15)),
                         "A garantia da geladeira acaba em 5 dias, dia 20/11. Se tiver algum defeito, é hora de acionar.")

    def test_nota_por_foto(self):
        foto = TMP / "nota.jpg"
        foto.write_bytes(b"\xff\xd8 foto")
        info = {"produto": "Roteador TP-Link Archer C6", "tipo": "roteador", "marca": "TP-Link", "modelo": "Archer C6",
                "loja": "KaBuM", "data_compra": "10/12/2025", "garantia_meses": None}
        with mock.patch("plugins._ia.ver_imagem_json", lambda *a, **k: dict(info)):
            r = self.g.run({"action": "nota", "arquivo": str(foto)})
        self.assertIn("até 10/12/2026", r)
        self.assertIn("vai até 10/12/2026", self.g.run({"action": "quando", "produto": "roteador"}))

    def test_manual(self):
        paginas = ["Especificações.", "Restaurar o padrão de fábrica\n1. Pressione RESET por 6 segundos.\n"
                                      "2. Solte quando o LED piscar."]
        self.assertEqual(self.g.trechos_relevantes(paginas, "como reseto?", 1)[0][0], 2)
        self.assertFalse(self.g.nome_bom("lava-louças"))
        self.assertTrue(self.g.nome_bom("TP-Link Archer C6"))
        pdf = TMP / "manual.pdf"
        pdf.write_bytes(b"%PDF fake")
        with mock.patch.object(self.g, "buscar_manual", lambda n: (pdf, "u")), \
                mock.patch.object(self.g, "_paginas_do_pdf", lambda p: paginas), \
                mock.patch("plugins._ia.perguntar", lambda *a, **k: None):
            r = self.g.run({"action": "manual", "pergunta": "como reseto o roteador", "produto": "TP-Link Archer C6"})
        self.assertIn("página 2", r)
        self.assertIn("RESET", r)


class TestChuva(unittest.TestCase):
    @staticmethod
    def bolha(cx, cy, r=4, n=256):
        yy, xx = np.mgrid[0:n, 0:n]
        return np.hypot(yy - cy, xx - cx) <= r

    def test_chuva_chegando_pelo_oeste(self):
        from plugins import chuva as C
        km = C.km_por_pixel(-16.68)
        c = 127.5
        r = C.prever_chegada(self.bolha(c - 35 / km, c), self.bolha(c - 25 / km, c), 20, km)
        self.assertEqual(r["vindo_de"], "do oeste")
        self.assertTrue(25 <= r["minutos"] <= 45)
        de_lado = C.prever_chegada(self.bolha(c - 30 / km, c + 10 / km), self.bolha(c - 30 / km, c), 20, km)
        self.assertIsNone(de_lado["minutos"])
        self.assertTrue(C.prever_chegada(None, self.bolha(c, c), 20, km)["chovendo"])

    def test_previsao_e_frase(self):
        from plugins import chuva as C
        d = {"minutely_15": {"time": ["2026-11-06T14:15", "2026-11-06T14:30", "2026-11-06T14:45"],
                             "precipitation": [0.0, 0.8, 1.2]}, "hourly": {"precipitation_probability": [80]}}
        p = C.chuva_na_previsao(d, datetime(2026, 11, 6, 14, 5))
        self.assertEqual(p["minutos"], 10)
        dec = C.decidir({"chovendo": False, "minutos": 20, "vindo_de": ""}, p)
        self.assertEqual(dec["fonte"], "radar")
        self.assertEqual(C.frase(dec, True), "Vai chover em uns 20 minutos, melhor tirar a roupa do varal.")
        self.assertIsNone(C.decidir(None, {"minutos": 10, "prob": 20}))
        self.assertEqual(C.ler_coordenadas("-16,6869 -49,2648"), (-16.6869, -49.2648))


class TestIdeias(unittest.TestCase):
    def test_caixinha(self):
        from plugins import ideias as I
        I.ARQ.unlink(missing_ok=True)
        self.assertIn("programação", I.run({"action": "anotar", "texto": "app de estoque pra lojas pequenas."}))
        self.assertIn("música", I.run({"action": "anotar", "texto": "rap sobre a cidade"}))
        self.assertIn("já está", I.run({"action": "anotar", "texto": "App de estoque pra lojas pequenas"}))
        self.assertIn("#1", I.run({"action": "nota", "ideia": "estoque", "texto": "assinatura"}))
        d = I.dados()
        for i in d["ideias"]:
            i["mexida"] = time.time() - 20 * 86400
        I._gravar(d)
        self.assertEqual(len(I.paradas(I.dados()["ideias"], time.time())), 2)
        self.assertIn("Alguma vira projeto", I.run({"action": "revisar"}))


if __name__ == "__main__":
    unittest.main()
