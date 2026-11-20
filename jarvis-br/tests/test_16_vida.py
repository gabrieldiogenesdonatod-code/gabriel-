"""
Testes da 1.6 — segurança, comunicação, carreira, criatividade, vida e diversão
(as partes puras; nada usa rede, microfone ou alto-falante).
"""
import random
import unittest
from datetime import date, datetime

import tests
from plugins import (aniversarios as an, cacador_vagas as cv, capsula_tempo as ct, conselheiro_decisao as cd,
                     cuidador as cu, detector_golpe as dg, ensina_errado as ens, entrevista as en, estilo_escrita as ee,
                     gamificacao as ga, gerador_beats as gb, guarda_vps as gv, mestre_rpg as rpg, parceiro_rima as pr,
                     quiz_geek as qz, resumo_grupo as rg, retrospectiva as rt, roleta as ro, senha_vazada as sv,
                     xadrez as xd)


class TestSeguranca(unittest.TestCase):
    def test_golpes(self):
        self.assertEqual(dg.avaliar("Oi mãe, troquei de número. Preciso de um pix urgente")["nivel"], "ALTO")
        self.assertEqual(dg.avaliar("Seu Nubank foi bloqueado: https://nubank-seguranca.com/desbloqueio")["nivel"], "ALTO")
        self.assertEqual(dg.avaliar("Fatura em https://www.nubank.com.br/app")["nivel"], "BAIXO")
        self.assertEqual(dg.avaliar("vamos almoçar amanhã?")["nota"], 0)
        self.assertTrue(any("punycode" in m for _p, m in [(0, x) for _s, x in dg.avaliar_link("http://xn--nbank-xxx.com")]))

    def test_senha_k_anonimato(self):
        prefixo, sufixo = sv.partes_hash("password")
        self.assertEqual(prefixo, "5BAA6")
        self.assertEqual(sv.contar(f"{sufixo}:3861493\nABC:1", sufixo), 3861493)
        self.assertEqual(sv.contar("ABC:1", sufixo), 0)

    def test_registro_ssh(self):
        log = ("2026-11-02T10:00:00 srv sshd[1]: Failed password for root from 45.1.2.3 port 1 ssh2\n"
               "2026-11-02T10:00:01 srv sshd[1]: Failed password for invalid user admin from 45.1.2.3 port 2 ssh2\n"
               "2026-11-02T10:00:02 srv sshd[1]: Invalid user test from 9.9.9.9 port 3\n"
               "2026-11-02T10:00:03 srv sshd[1]: Accepted publickey for root from 189.1.1.1 port 4 ssh2\n@@F2B\nactive")
        r = gv.analisar(log)
        self.assertEqual((r["falhas"], r["ips"][0], r["fail2ban"]), (3, ("45.1.2.3", 2), True))
        self.assertEqual(gv.novos_ips(r, ["189.1.1.1"]), [])
        self.assertEqual(len(gv.novos_ips(r, [])), 1)

    def test_modo_convidado_no_portao(self):
        from core import verificacao as v
        from plugins import modo_convidado
        antes, log = modo_convidado._estado["ativo"], v.ARQ_LOG
        modo_convidado._estado["ativo"] = True
        v.ARQ_LOG = tests.TMP / "verificacao_log_16.json"
        try:
            self.assertIsNone(v.autorizar("weather_report", {}))
            self.assertIn("MODO CONVIDADO", v.autorizar("save_memory", {}))
            self.assertIn("MODO CONVIDADO", v.autorizar("cristal_malhas", {"action": "vendas"}))
        finally:
            modo_convidado._estado["ativo"] = antes
            v.ARQ_LOG = log


class TestComunicacao(unittest.TestCase):
    EXPORT = ("02/11/2026 14:31 - Pedro: bora no cinema amanhã?\n02/11/2026 14:32 - Você: bora sim kkkk\nque horas?\n"
              "[02/11/2026, 14:35:10] Ana: 19h no shopping\n02/11/2026 14:40 - Pedro: <Mídia oculta>")

    def test_whatsapp_e_estilo(self):
        msgs = ee.ler_whatsapp(self.EXPORT)
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[1]["texto"], "bora sim kkkk\nque horas?")
        p = ee.perfil_de(["bora sim kkkk", "vc vem tbm?", "blz mano", "Ok."])
        self.assertIn("vc", p["girias"])
        self.assertIn("palavras", ee.descrever(p))

    def test_resumo_de_grupo(self):
        msgs = ee.ler_whatsapp(self.EXPORT)
        self.assertEqual(rg.corte("6 horas", msgs, "", datetime(2026, 11, 2, 18)), datetime(2026, 11, 2, 12))
        a = rg.analisar(msgs, "ana")
        self.assertEqual((a["total"], len(a["perguntas"])), (3, 2))

    def test_aniversarios(self):
        self.assertEqual(an.ler_data("12 de março"), (12, 3, None))
        self.assertEqual(an.ler_data("05/09/1990"), (5, 9, 1990))
        self.assertEqual(an.proximo(29, 2, date(2027, 1, 1)), date(2027, 2, 28))
        self.assertEqual(an.proximo(1, 11, date(2026, 11, 2)), date(2027, 11, 1))
        self.assertEqual(an.ler_vcf("BEGIN:VCARD\nFN:Vó Maria\nBDAY:1950-03-12\nEND:VCARD")[0]["mes"], 3)


class TestCarreira(unittest.TestCase):
    def test_entrevista(self):
        perguntas = en.roteiro("desenvolvedor python", "junior", 1)
        self.assertEqual(len(perguntas), 7)
        self.assertEqual(perguntas[0], en.COMPORTAMENTAIS[0])
        self.assertEqual(en.vicios("tipo, né, eu fiz tipo isso aí"), {"tipo": 2, "né": 1, "aí": 1})
        self.assertLess(en.feedback_local([{"pergunta": "x", "resposta": "sim"}])["nota"], 8)

    def test_ensina_errado_e_vagas(self):
        self.assertTrue(ens.acertou("o primeiro é o zero", ["0", "zero"]))
        self.assertFalse(ens.acertou("não sei", ["0", "zero"]))
        self.assertEqual(cv.consultas("python junior", "Goiânia", True), ["vaga python junior Goiânia", "vaga python junior remoto"])
        self.assertTrue(cv.eh_vaga("Vaga Desenvolvedor Python Jr - Goiânia", "https://x.gupy.io/jobs/1"))
        self.assertFalse(cv.eh_vaga("Quanto ganha um programador", "https://blog.x"))


class TestCriatividade(unittest.TestCase):
    def test_rimas(self):
        self.assertEqual(pr.terminacao("caminho"), "inho")
        self.assertEqual(pr.rimam("amor", "dor"), "perfeita")
        self.assertEqual(pr.rimam("vida", "rima"), "toante")
        self.assertEqual(pr.esquema(["no meu caminho", "nunca sozinho", "na minha quebrada", "no fim da estrada"]), "AABB")
        self.assertIn("sozinho", pr.sugerir("caminho", [])[0])
        self.assertEqual(len(pr.silabas("coração")), 3)

    def test_dados_e_ficha(self):
        r = rpg.rolar("2d6+3", random.Random(1))
        self.assertEqual(r["total"], sum(r["jogadas"]) + 3)
        self.assertEqual(len(rpg.rolar("4d6kh3", random.Random(2))["usadas"]), 3)
        with self.assertRaises(ValueError):
            rpg.rolar("abc")
        f = rpg.criar_personagem("Kael", "ladino", random.Random(3))
        self.assertEqual(f["atributos"]["Destreza"], max(f["atributos"].values()))

    def test_beats(self):
        self.assertEqual(gb.estilo_de("lo-fi para estudar"), "lofi")
        self.assertAlmostEqual(gb.freq_tom("Am"), 55.0)
        pad = gb.padrao("boom bap", 4, 7)
        self.assertEqual(len(pad["bumbo"]), 4)
        self.assertIn(4, pad["caixa"][0])
        audio = gb.renderizar("trap", 140, 2, "Em", 3)
        self.assertGreater(len(audio), 44100 * 3)
        self.assertLessEqual(float(abs(audio).max()), 0.93)


class TestVida(unittest.TestCase):
    def test_capsula(self):
        self.assertEqual(ct.data_de("daqui a 1 ano", date(2026, 11, 2)), date(2027, 11, 2))
        self.assertEqual(ct.data_de("em 6 meses", date(2026, 11, 2)), date(2027, 5, 2))
        self.assertEqual(ct.data_de("25/12/2027"), date(2027, 12, 25))
        self.assertIsNone(ct.data_de("29/02/2027"))

    def test_decisao(self):
        c = cd.ler_criterios("preço peso 3, desempenho peso 2, portabilidade 1")
        n = cd.ler_notas("notebook preço 6 desempenho 7 portabilidade 10; PC preço 8 desempenho 9 portabilidade 2", list(c))
        self.assertEqual(cd.ranking(c, n)[0][0], "PC")

    def test_xp(self):
        self.assertEqual(ga.nivel_de(0), (1, 0, 100))
        self.assertEqual(ga.nivel_de(100), (2, 0, 200))
        self.assertEqual(ga.nivel_de(1000)[0], 5)
        self.assertEqual(ga.sequencia(["2026-11-01", "2026-11-02", "2026-10-31", "2026-10-29"], date(2026, 11, 2)), 3)

    def test_retrospectiva(self):
        ini, fim, rotulo = rt.intervalo("outubro", date(2026, 11, 2))
        self.assertEqual((ini, fim), (datetime(2026, 10, 1), datetime(2026, 11, 1)))
        self.assertEqual(rt.intervalo("dezembro", date(2026, 11, 2))[2], "em dezembro de 2025")
        self.assertEqual(rt.intervalo("mês passado", date(2026, 1, 10))[2], "em dezembro de 2025")

    def test_cuidador(self):
        self.assertEqual(cu.ler_horarios("8h e 20h"), ["08:00", "20:00"])
        self.assertEqual(cu.ler_dias("seg a sex"), [0, 1, 2, 3, 4])
        self.assertEqual(cu.ler_dias("sex a seg"), [4, 5, 6, 0])
        d = {"itens": [{"id": "a", "pessoa": "vó", "item": "remédio", "horarios": ["08:00", "20:00"], "dias": list(range(7)),
                        "feitos": ["2026-11-02 08:00"]}], "checklist": []}
        self.assertEqual([x["hora"] for x in cu.pendentes(d, datetime(2026, 11, 2, 21))], ["20:00"])
        self.assertEqual(cu.pendentes(d, datetime(2026, 11, 2, 9)), [])


class TestDiversao(unittest.TestCase):
    def test_damas(self):
        t = xd.damas_inicial()
        self.assertEqual(len(t), 24)
        self.assertEqual(len(xd.damas_lances(t, "b")), 7)
        # lei da maioria: tem que pegar a sequência que come mais
        tab = {"2,2": "b", "3,3": "p", "5,5": "p", "1,3": "p", "6,0": "b"}
        self.assertEqual([[xd._nome(c) for c in s] for s, _c in xd.damas_lances(tab, "b")], [["c3", "e5", "g7"]])
        # dama voadora come de longe
        voos = [[xd._nome(c) for c in s] for s, _c in xd.damas_lances({"0,0": "B", "3,3": "p", "6,6": "p"}, "b")]
        self.assertIn(["a1", "e5", "h8"], voos)
        # peão come para trás e promove ao chegar no fim
        self.assertEqual([[xd._nome(c) for c in s] for s, _c in xd.damas_lances({"3,3": "b", "2,2": "p"}, "b")], [["d4", "b2"]])
        self.assertEqual(list(xd.damas_jogar({"1,6": "b"}, xd.damas_lances({"1,6": "b"}, "b")[0]).values()), ["B"])

    def test_quiz_e_roleta(self):
        opcoes = ["Steve Rogers", "Tony Stark", "Bruce Banner", "Peter Parker"]
        for fala, esperado in (("letra B", 1), ("é a c", 2), ("a", 0), ("a terceira", 2), ("Tony Stark", 1)):
            self.assertEqual(qz.resposta_indice(fala, opcoes), esperado, fala)
        self.assertEqual(ro.categoria_de("o que eu janto"), "comida")
        self.assertEqual(ro.categoria_de("o que eu assisto"), "filme")
        self.assertEqual(ro.sortear(["a", "b", "c", "d"], {}, ["b", "c", "d"], random.Random(1)), "a")


if __name__ == "__main__":
    unittest.main()
