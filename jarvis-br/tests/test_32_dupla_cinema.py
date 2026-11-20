"""
Testes da 2.7 — JARVIS + FRIDAY (motor de cenas, divisão, turno, placar), cinema
(catálogo, maratona, quiz, "o que eu perdi" sem spoiler), radionovela, talk show,
"neste dia" e campanha de herói. Sem Gemini, sem voz e sem placa de som: a IA e a
fala são trocadas por versões falsas.
"""
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from plugins import _dupla as D
from plugins import campanha_heroi as CH
from plugins import cinema as C
from plugins import jarvis_friday as JF
from plugins import neste_dia as ND
from plugins import radionovela as RN
from plugins import talk_show as TS
from tests import RAIZ


class TestDupla(unittest.TestCase):
    def setUp(self):
        D.ARQ_PERSONAGENS.unlink(missing_ok=True)

    def test_roteiro_filtra_e_limpa(self):
        falso = {"falas": [{"quem": "jarvis", "texto": "Olá, FRIDAY (sorrindo)."}, {"quem": "BOB", "texto": "x"},
                           {"quem": "FRIDAY", "texto": "Oi, JARVIS!"}]}
        with mock.patch("plugins._ia.perguntar_json", lambda *a, **k: falso):
            r = D.roteiro("teste", ["JARVIS", "FRIDAY"], 4)
        self.assertEqual([f["quem"] for f in r], ["JARVIS", "FRIDAY"])
        self.assertEqual(r[0]["texto"], "Olá, FRIDAY.")

    def test_encenar_toca_todas_e_palco_mostra(self):
        faladas = []
        with mock.patch.object(D, "falar", lambda q, t: faladas.append((q, t)) or True), \
                mock.patch.object(D, "abrir", lambda: True), mock.patch("time.sleep", lambda s: None):
            ok = D.encenar([{"quem": "JARVIS", "texto": "a"}, {"quem": "FRIDAY", "texto": "b"}], "T",
                           opcoes=["x", "y"], pausar_microfone=False)
            self.assertTrue(ok)
            t0 = time.monotonic()
            while D.rodando() and time.monotonic() - t0 < 3:
                pass
        self.assertEqual(faladas, [("JARVIS", "a"), ("FRIDAY", "b")])
        e = D.estado_palco()
        self.assertEqual(e["opcoes"], ["x", "y"])
        self.assertEqual([p["id"] for p in e["personagens"]], ["JARVIS", "FRIDAY"])

    def test_personagem_novo_e_envelope(self):
        self.assertIn("criei", D.criar_personagem("Mestre", "sábio", False).lower())
        self.assertIn("MESTRE", D.personagens())
        self.assertEqual(D.nome_visivel("VILAO"), "VILÃO")
        import numpy as np
        env = D.envelope(np.ones(24000, dtype="float32") * 0.5, 24000)
        self.assertTrue(env and max(env) <= 1.0)

    def test_palco_existe(self):
        pagina = (RAIZ / "dashboard" / "static" / "palco.html").read_text(encoding="utf-8")
        self.assertIn("/api/palco", pagina)


class TestSapiTexto(unittest.TestCase):
    def test_sapi_le_o_texto_em_utf8_de_arquivo(self):
        import wave
        chamadas = {}

        def falso_run(args, **k):
            ps = args[-1]
            chamadas["ps"], chamadas["k"] = ps, k
            origem = ps.split("ReadAllText('")[1].split("'")[0]
            chamadas["texto"] = Path(origem).read_text(encoding="utf-8")
            destino = ps.split("SetOutputToWaveFile('")[1].split("'")[0]
            with wave.open(destino, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\x00\x10" * 800)
        with mock.patch.object(D, "WIN", True), mock.patch("subprocess.run", falso_run):
            x, sr = D._sapi("Ação, coração — São Paulo", {"sapi": "female"})
        self.assertEqual(chamadas["texto"], "Ação, coração — São Paulo")
        self.assertNotIn("input", chamadas["k"])
        self.assertEqual((sr, len(x)), (16000, 800))
        self.assertFalse(list(D.MEMORIA.glob("_fala_*")))            # não sobra arquivo temporário


class TestJarvisFriday(unittest.TestCase):
    def setUp(self):
        JF.ARQ.unlink(missing_ok=True)

    def test_divisao_e_passe(self):
        self.assertEqual(JF.quem_cuida("a música"), "FRIDAY")
        self.assertEqual(JF.quem_cuida("compilar o projeto"), "JARVIS")
        falas = JF.passe("a música", "estou compilando o projeto")
        self.assertEqual([f["quem"] for f in falas], ["JARVIS", "FRIDAY"])

    def test_turno_devido(self):
        feitos = {}
        self.assertEqual(JF.turno_devido(datetime(2026, 11, 7, 19, 5), "19:00", "08:00", feitos), "noite")
        self.assertIsNone(JF.turno_devido(datetime(2026, 11, 7, 14, 0), "19:00", "08:00", feitos))
        self.assertEqual(JF.turno_devido(datetime(2026, 11, 7, 8, 10), "19:00", "08:00", feitos), "dia")

    def test_placar(self):
        with mock.patch.object(D, "encenar", lambda *a, **k: True):
            JF.vencedor("FRIDAY")
            JF.vencedor("friday")
        self.assertEqual(JF.dados()["placar"]["FRIDAY"], 2)
        self.assertIn("Quem ganhou", JF.vencedor(""))
        self.assertEqual(JF.dados()["placar"]["JARVIS"], 0)
        self.assertIn("FRIDAY 2", JF.run({"action": "placar"}))


class TestCinema(unittest.TestCase):
    def setUp(self):
        C.ARQ.unlink(missing_ok=True)

    def test_catalogo_e_onde_parei(self):
        cat = []
        C.registrar_assistido(cat, "Dark", 9, "série", 2, 5)
        C.registrar_assistido(cat, "dark", None, "", 2, 6)
        self.assertEqual(len(cat), 1)
        self.assertEqual(cat[0]["nota"], 9)
        self.assertIn("episódio 6", C.onde_parei(cat, "DARK"))
        self.assertIn("Não tenho", C.onde_parei(cat, "Lost"))
        r = C.run({"action": "assisti", "titulo": "Duna", "nota": 8})
        self.assertIn("Duna", r)
        self.assertIn("Duna", C.run({"action": "catalogo"}))

    def test_maratona(self):
        p = C.plano_maratona([{"titulo": "A", "minutos": 120}, {"titulo": "B", "minutos": 100},
                              {"titulo": "C", "minutos": 90}], a_cada=2, intervalo_min=15)
        self.assertEqual(p["total_min"], 325)
        self.assertEqual(sum(1 for x in p["itens"] if x.get("intervalo")), 1)
        self.assertEqual(C.horas(325), "5h25")
        lista = [{"titulo": "Capitão América", "minutos": 124}, {"titulo": "Capitã Marvel", "minutos": 123}]
        with mock.patch("plugins._ia.perguntar_json", lambda *a, **k: lista):
            self.assertIn("2 títulos", C.maratona("Marvel"))
        self.assertIn("Capitã Marvel", C.maratona_proximo())
        self.assertIn("concluída", C.maratona_proximo())

    def test_perdi_sem_spoiler(self):
        linha = [{"min": 5, "texto": "a"}, {"min": 30, "texto": "b"}, {"min": 80, "texto": "FUTURO"}]
        self.assertEqual([x["texto"] for x in C.linha_ate(linha, 40)], ["a", "b"])
        self.assertEqual([x["texto"] for x in C.linha_ate(linha, 40, 20)], ["b"])
        d = C.dados()
        d["sessao"] = {"ativa": True, "titulo": "X", "inicio": time.time() - 40 * 60, "pausado_s": 0, "linha": linha}
        C._salvar(d)
        visto = {}
        with mock.patch("plugins._ia.perguntar", lambda p, **k: visto.setdefault("p", p) and "resumo"):
            self.assertEqual(C.perdi(), "resumo")
        self.assertNotIn("FUTURO", visto["p"])

    def test_quiz(self):
        q = {"pergunta": "?", "opcoes": ["Azul", "Verde", "Roxo", "Preto"], "certa": 1}
        self.assertTrue(C.conferir("b", q))
        self.assertTrue(C.conferir("2", q))
        self.assertTrue(C.conferir("verde", q))
        self.assertFalse(C.conferir("a", q))
        qs = [dict(q) for _ in range(5)]
        with mock.patch("plugins._ia.perguntar_json", lambda *a, **k: qs):
            self.assertIn("Pergunta 1", C.quiz())
        for _ in range(4):
            self.assertIn("Pergunta", C.responder("B"))
        self.assertIn("Fim do quiz: você 5", C.responder("verde"))

    def test_sessao_esquecida_expira(self):
        d = C.dados()
        d["sessao"] = {"ativa": True, "titulo": "X", "inicio": time.time() - 7 * 3600}
        C._salvar(d)
        self.assertFalse(C.dados()["sessao"]["ativa"])            # JARVIS fechado no meio: não perturbe não fica preso

    def test_sessao_e_fim(self):
        cenas = []
        with mock.patch.object(C, "_brilho", lambda v=None: None), \
                mock.patch("plugins._janelas.minimizar_tudo", lambda *a: ""), \
                mock.patch("threading.Thread.start", lambda self: None), \
                mock.patch.object(D, "encenar", lambda falas, *a, **k: cenas.append(falas) or True), \
                mock.patch("plugins._comum.cfg", lambda *a, **k: {"ouvir": False, "brilho": "", "minimizar": True}):
            self.assertIn("Sessão de cinema", C.sessao("Interestelar"))
        self.assertTrue(C.dados()["sessao"]["ativa"])
        self.assertIn("três", cenas[0][-1]["texto"])                 # abertura passa pelo encenar (microfone pausa)
        r = C.fim(9, conversar=False)
        self.assertIn("encerrada", r)
        self.assertEqual(C.achar(C.dados()["catalogo"], "interestelar")["nota"], 9)


class TestDiversao(unittest.TestCase):
    def setUp(self):
        for a in (RN.ARQ, CH.ARQ, ND.ARQ, C.ARQ):
            a.unlink(missing_ok=True)

    def test_radionovela(self):
        self.assertEqual(RN.escolha_de("opção 2", ["a", "b"]), 1)
        self.assertEqual(RN.escolha_de("a primeira", ["a", "b"]), 0)
        self.assertIsNone(RN.escolha_de("9", ["a", "b"]))
        cap = {"titulo": "Início", "falas": [{"quem": "narrador", "texto": "Era uma vez", "efeito": "trovao"},
                                             {"quem": "JARVIS", "texto": "Senhor."}, {"quem": "X", "texto": "?"}],
               "opcoes": ["Ir", "Ficar"], "resumo": "Começou."}
        v = RN.validar(cap)
        self.assertEqual([f["quem"] for f in v["falas"]], ["NARRADOR", "JARVIS", "NARRADOR"])
        cenas = []
        with mock.patch("plugins._ia.perguntar_json", lambda *a, **k: cap), \
                mock.patch.object(D, "encenar", lambda falas, *a, **k: cenas.append(falas) or True):
            self.assertIn("capítulo 1", RN.nova("mistério"))
            self.assertIn("escolha", RN.capitulo())                 # tem que escolher antes
            self.assertIn("capítulo 2", RN.escolher("2"))
        self.assertEqual(RN.dados()["capitulos"][0]["escolha"], "Ficar")
        self.assertIn("Ficar", RN.prompt_capitulo(RN.dados()))
        self.assertEqual(len(cenas), 2)

    def test_talk_show_md_e_mixagem(self):
        import numpy as np
        md = TS.roteiro_md("música", [{"quem": "JARVIS", "texto": "Bem-vindo!"}, {"quem": "Convidado", "texto": "Oi"}],
                           {"titulo": "Ep 1", "momentos": ["risos"]}, datetime(2026, 11, 7, 21, 0))
        self.assertIn("# Ep 1", md)
        self.assertIn("**Convidado:** Oi", md)
        x = TS.mixar(np.ones(10, dtype="float32") * 0.8, np.ones(5, dtype="float32") * 0.8)
        self.assertEqual(len(x), 10)
        self.assertLessEqual(float(np.abs(x).max()), 0.951)

    def test_neste_dia(self):
        alvo = dict((r, d) for r, d in ND.datas_alvo(date(2026, 3, 31)))
        self.assertEqual(alvo["há um mês"], date(2026, 2, 28))
        self.assertEqual(alvo["há um ano"], date(2025, 3, 31))
        self.assertEqual(ND.ler_data("28/10/2026"), date(2026, 10, 28))
        self.assertEqual(ND.ler_data("28 de outubro", date(2026, 11, 7)), date(2026, 10, 28))
        self.assertEqual(ND.ler_data("ontem", date(2026, 11, 7)), date(2026, 11, 6))
        self.assertIsNone(ND.ler_data("31/02/2026"))                # data impossível não derruba
        self.assertIn("Não entendi", ND.run({"action": "data", "data": "31/02"}))
        cl = "## [1.0] — 2026-10-28\n\n### Novo\n- Primeira versão **PT-BR**\n\n## [1.1] — 2026-10-28\n- x\n"
        v = ND.versoes_changelog(cl)
        self.assertEqual([x[0] for x in v["2026-10-28"]], ["1.0", "1.1"])
        self.assertEqual(v["2026-10-28"][0][1], "Primeira versão PT-BR")
        self.assertTrue(any(a["fonte"] == "projeto" for a in ND.do_dia(date(2026, 10, 28))))
        txt = ND.montar([("há um mês", date(2026, 10, 7), [{"fonte": "projeto", "texto": "lançou a versão 1.0"}])])
        self.assertTrue(txt.startswith("Há um mês, o senhor lançou a versão 1.0"))

    def test_campanha(self):
        self.assertEqual(CH.missao_de("limpeza", "limpar")[0], "Derrotar o vírus Hydra no disco")
        self.assertIsNone(CH.missao_de("xyz"))
        self.assertEqual(CH.vilao_da_semana(date(2026, 11, 2)), CH.vilao_da_semana(date(2026, 11, 8)))
        ts = datetime(2026, 11, 7, 10).timestamp()
        ms = CH.missoes_entre([{"ts": ts, "ferramenta": "pomodoro", "acao": "iniciar", "ok": 1}] * 5 +
                              [{"ts": ts, "ferramenta": "limpeza", "acao": "", "ok": 0}],
                              [{"ts": ts, "ferramenta": "commit", "ok": 1}])
        self.assertEqual(len(ms), 4)                                # 3 pomodoros (limite) + 1 commit; falha não conta
        self.assertEqual(CH.barra(150, 300), "█████░░░░░")
        with mock.patch.object(CH, "cfg", lambda *a, **k: {"vida": "muita"}), mock.patch.object(CH, "_coletar",
                                                                                              lambda d: []):
            self.assertEqual(CH.status()["total"], 300)              # valor inválido nas configurações
        with mock.patch.object(CH, "_coletar", lambda desde: ms):
            self.assertIn("Vida 230/300", CH.texto_vilao())


if __name__ == "__main__":
    unittest.main()
