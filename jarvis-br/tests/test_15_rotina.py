"""
Testes da 1.5 — hábitos, memória de tela, professor, ditado de código,
demonstração, postura, humor, companheiro de jogo, auto-melhoria e
segunda opinião (só as partes que não precisam de tela, câmera ou IA).
"""
import tempfile
import textwrap
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import tests
from plugins import (auto_melhoria as am, companheiro_jogo as cj, demonstracao as dm, ditado_codigo as dc,
                     habitos, humor, memoria_tela as mt, modo_professor as mp, postura, segunda_opiniao as so)


class _SemIA:
    """Troca o _ia por uma versão falsa durante o teste."""

    def __init__(self, disponivel=False, resposta=None):
        self.d, self.r = disponivel, resposta

    def __enter__(self):
        from plugins import _ia
        self._ia, self._orig = _ia, (_ia.disponivel, _ia.perguntar_json)
        _ia.disponivel = lambda: self.d
        _ia.perguntar_json = lambda *a, **k: self.r
        return self

    def __exit__(self, *exc):
        self._ia.disponivel, self._ia.perguntar_json = self._orig


class TestHabitos(unittest.TestCase):
    def test_detectar_e_oferecer(self):
        focos = []
        hoje = date(2026, 11, 2)                               # segunda-feira
        for i in range(1, 15):
            d = hoje - timedelta(days=i)
            if d.weekday() >= 5:
                continue
            ini = datetime(d.year, d.month, d.day, 8, 10 + (i % 4)).timestamp()
            focos.append({"inicio": ini, "fim": ini + 600, "atividade": "WhatsApp", "app": "Chrome"})
            ini2 = datetime(d.year, d.month, d.day, 9 + (i * 7) % 10, 0).timestamp()
            focos.append({"inicio": ini2, "fim": ini2 + 300, "atividade": "YouTube", "app": "Chrome"})
        achados = habitos.detectar(focos, hoje)
        nomes = [h["nome"] for h in achados]
        self.assertIn("WhatsApp", nomes)
        self.assertNotIn("YouTube", nomes)                     # cada dia numa hora: não é hábito
        h = achados[nomes.index("WhatsApp")]
        self.assertTrue(h["hora"].startswith("08:1"))
        self.assertEqual(h["dias_semana"], [0, 1, 2, 3, 4])
        seg = datetime(2026, 11, 2, 8, 8)
        self.assertTrue(habitos.hora_de_oferecer(h, seg, False, False))
        self.assertFalse(habitos.hora_de_oferecer(h, seg, True, False))     # já abriu hoje
        self.assertFalse(habitos.hora_de_oferecer(h, seg.replace(hour=9), False, False))
        self.assertFalse(habitos.hora_de_oferecer(h, datetime(2026, 11, 7, 8, 8), False, False))  # sábado


class TestMemoriaTela(unittest.TestCase):
    def setUp(self):
        self._orig = (mt.ARQ, mt.PASTA_IMG)
        mt.ARQ, mt.PASTA_IMG = tests.TMP / "memoria_tela.db", tests.TMP / "memoria_tela"
        mt._con.update(c=None, arq=None)

    def tearDown(self):
        if mt._con["c"] is not None:
            mt._con["c"].close()
        mt._con.update(c=None, arq=None)
        mt.ARQ, mt.PASTA_IMG = self._orig

    def test_guardar_buscar_apagar(self):
        agora = time.time()
        mt.guardar("chrome.exe", "Fornecedor - Gmail", "Segue o orçamento das camisetas infantis", ts=agora - 3600)
        mt.guardar("code.exe", "main.py - jarvis", "def autorizar(ferramenta): ...", ts=agora - 60)
        achados = mt.buscar("orçamento")
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0]["app"], "chrome.exe")
        if mt._con["fts"]:
            self.assertEqual(len(mt.buscar("orcamento camisetas")), 1)    # sem acento e duas palavras
        self.assertEqual(mt.buscar("orçamento", desde=agora - 120), [])
        self.assertEqual(mt.apagar(agora - 120), 1)
        self.assertEqual(mt.buscar("autorizar"), [])
        self.assertEqual(len(mt.buscar("orçamento")), 1)

    def test_exclusoes(self):
        self.assertTrue(mt.excluida("chrome.exe", "Banco do Brasil - Internet Banking", "banco, senha"))
        self.assertFalse(mt.excluida("code.exe", "main.py", "banco, senha"))
        self.assertFalse(mt.excluida("code.exe", "main.py", ""))
        padrao = next(f["default"] for f in mt.PLUGIN_SETTINGS["fields"] if f["key"] == "excluir")
        self.assertTrue(mt.excluida("chrome.exe", "Pagar com Pix - Nubank", padrao))
        self.assertTrue(mt.excluida("msedge.exe", "Nova guia - [InPrivate] - Microsoft Edge", padrao))
        self.assertTrue(mt.excluida("chrome.exe", "Gerenciador de senhas", padrao))          # plural
        self.assertFalse(mt.excluida("chrome.exe", "Pixel Art - Google Chrome", padrao))     # não é "pix"
        self.assertFalse(mt.excluida("code.exe", "interface.py - jarvis", padrao))          # não é "inter"


class TestProfessor(unittest.TestCase):
    def test_sm2(self):
        hoje = date(2026, 11, 2)
        c = mp.agendar({}, 4, hoje)
        self.assertEqual((c["rep"], c["intervalo"]), (1, 1))
        c = mp.agendar(c, 4, hoje)
        self.assertEqual((c["rep"], c["intervalo"]), (2, 6))
        c = mp.agendar(c, 5, hoje)
        self.assertEqual(c["rep"], 3)
        self.assertGreater(c["intervalo"], 6)
        self.assertEqual(c["proxima"], (hoje + timedelta(days=c["intervalo"])).isoformat())
        c = mp.agendar(c, 1, hoje)                             # errou: volta para amanhã
        self.assertEqual((c["rep"], c["intervalo"]), (0, 1))
        for _ in range(20):
            c = mp.agendar(c, 0, hoje)
        self.assertGreaterEqual(c["ef"], 1.3)

    def test_notas(self):
        self.assertEqual(mp.nota_de_texto("acertei"), 4)
        self.assertEqual(mp.nota_de_texto("errei feio"), 1)
        self.assertEqual(mp.nota_de_texto("foi fácil"), 5)
        self.assertEqual(mp.nota_de_texto("quase"), 3)
        self.assertIsNone(mp.nota_de_texto("banana"))
        self.assertEqual(mp.nota_local("A capital é Brasília", "Brasília é a capital do Brasil"), 4)
        self.assertEqual(mp.nota_local("não sei", "Brasília é a capital do Brasil"), 1)
        with _SemIA():
            nota, comentario = mp.corrigir({"pergunta": "Capital?", "resposta": "Brasília"}, "Brasília")
            self.assertEqual((nota, comentario), (5, ""))      # certo: não repete a resposta
            nota, comentario = mp.corrigir({"pergunta": "Capital?", "resposta": "Brasília"}, "Goiânia")
            self.assertLess(nota, 3)
            self.assertIn("Brasília", comentario)


class TestDitado(unittest.TestCase):
    def test_extrair_blocos(self):
        texto = "Aqui:\n```python\ndef dobro(x):\n    return 2 * x\n```\nTestes:\n```python\nimport unittest\n```\n"
        codigo, testes = dc.extrair_blocos(texto)
        self.assertIn("def dobro", codigo)
        self.assertIn("import unittest", testes)
        self.assertEqual(dc.extrair_blocos("sem código"), ("", ""))

    def test_rodar_testes_numa_pasta_isolada(self):
        codigo = "def dobro(x):\n    return 2 * x\n"
        testes = textwrap.dedent("""
            import unittest
            from dobro import dobro
            class T(unittest.TestCase):
                def test_dobro(self):
                    self.assertEqual(dobro(4), 8)
        """)
        ok, _saida = dc.rodar_testes(codigo, testes, "dobro")
        self.assertTrue(ok)
        ok, _saida = dc.rodar_testes(codigo.replace("2 * x", "x + 2"), testes, "dobro")
        self.assertFalse(ok)


class TestDemonstracao(unittest.TestCase):
    def test_tecla_base(self):
        self.assertEqual(dm._tecla_base("c:\x03"), "c")         # Ctrl+C chega como caractere de controle
        self.assertEqual(dm._tecla_base("vk:65"), "a")
        self.assertEqual(dm._tecla_base("Key.tab"), "tab")

    def test_compactar(self):
        eventos = [[0.0, "clique", 100, 200, "left", {"titulo": "Bloco de Notas"}, None],
                   [0.5, "kd", "c:o"], [0.55, "ku", "c:o"], [0.6, "kd", "c:i"], [0.7, "kd", "Key.space"],
                   [0.8, "kd", "c:x"], [0.85, "kd", "Key.backspace"],
                   [1.0, "kd", "Key.ctrl_l"], [1.1, "kd", "c:\x13"], [1.2, "ku", "c:\x13"], [1.3, "ku", "Key.ctrl_l"],
                   [4.0, "kd", "Key.enter"]]
        passos = dm.compactar(eventos)
        self.assertEqual([p["tipo"] for p in passos], ["clique", "texto", "atalho", "esperar", "tecla"])
        self.assertEqual(passos[1]["texto"], "oi ")
        self.assertEqual(passos[2]["teclas"], "ctrl+s")
        self.assertAlmostEqual(passos[3]["segundos"], 2.7)
        self.assertEqual(passos[4]["tecla"], "Key.enter")


class TestPostura(unittest.TestCase):
    BASE = {"centro_y": 0.45, "tamanho": 0.30, "inclinacao": 0.0, "proporcao": 1.2, "boca": 0.40}

    def test_avaliar(self):
        b = self.BASE
        self.assertEqual(postura.avaliar(dict(b), b), [])
        self.assertEqual(postura.avaliar(dict(b, centro_y=0.56), b), ["curvado"])
        self.assertEqual(postura.avaliar(dict(b, tamanho=0.40), b), ["curvado"])     # perto demais da tela
        self.assertEqual(postura.avaliar(dict(b, inclinacao=15), b), ["torto"])

    def test_bocejo(self):
        b = self.BASE
        bocejo = dict(b, proporcao=1.40, boca=0.30)
        self.assertTrue(postura.eh_bocejo([dict(b)] * 3 + [bocejo] * 5 + [dict(b)] * 3, b))
        self.assertFalse(postura.eh_bocejo([bocejo] * 3, b))
        self.assertFalse(postura.eh_bocejo([bocejo, dict(b)] * 6, b))

    def test_medidas(self):
        face = [100, 80, 120, 150, 140, 130, 190, 130, 165, 160, 145, 190, 185, 190, 0.9]
        m = postura.medidas(face, 640, 480)
        self.assertAlmostEqual(m["inclinacao"], 0.0)
        self.assertAlmostEqual(m["tamanho"], 150 / 480)
        self.assertAlmostEqual(m["proporcao"], 1.25)

    def test_minutos_sem_pausa(self):
        t0 = 1_000_000.0
        focos = [{"inicio": t0, "fim": t0 + 3600, "atividade": "VS Code"},
                 {"inicio": t0 + 3600, "fim": t0 + 4000, "atividade": "ausente"},
                 {"inicio": t0 + 4000, "fim": t0 + 6000, "atividade": "Chrome"}]
        self.assertAlmostEqual(postura.minutos_sem_pausa(focos, t0 + 6000), 2000 / 60)
        buraco = [{"inicio": t0, "fim": t0 + 3600, "atividade": "VS Code"},     # PC desligado no meio
                  {"inicio": t0 + 5000, "fim": t0 + 6000, "atividade": "VS Code"}]
        self.assertAlmostEqual(postura.minutos_sem_pausa(buraco, t0 + 6000), 1000 / 60)
        self.assertEqual(postura.minutos_sem_pausa([], t0), 0.0)


class TestHumor(unittest.TestCase):
    def test_calcular(self):
        d = datetime(2026, 11, 2)
        self.assertEqual(humor.calcular(d.replace(hour=8), 0, 0, 0)[0], "formal")
        self.assertEqual(humor.calcular(d.replace(hour=14), 6.5, 0, 0)[0], "sarcastico")
        self.assertEqual(humor.calcular(d.replace(hour=3), 9, 9, 9)[0], "calmo")     # madrugada vence tudo
        self.assertEqual(humor.calcular(d.replace(hour=15), 7, 6, 0)[0], "cuidadoso")
        self.assertEqual(humor.calcular(d.replace(hour=16), 0, 0, 4)[0], "animado")
        self.assertEqual(humor.calcular(d.replace(hour=15), 1, 0, 0)[0], "normal")
        self.assertEqual(humor.calcular(d.replace(hour=23, minute=30), 0, 0, 0)[0], "calmo")
        self.assertEqual(humor.HUMORES["normal"], "")


class TestCompanheiroJogo(unittest.TestCase):
    def test_eh_jogo(self):
        self.assertEqual(cj.eh_jogo("VALORANT-Win64-Shipping.exe"), "Valorant")
        self.assertEqual(cj.eh_jogo("HD-Player.exe", "BlueStacks - Free Fire"), "Free Fire")
        self.assertEqual(cj.eh_jogo("javaw.exe", "Minecraft 1.21"), "Minecraft")
        self.assertEqual(cj.eh_jogo("hollow_knight.exe", "", r"D:\Steam\steamapps\common\Hollow Knight\x.exe"),
                         "hollow_knight")
        self.assertIsNone(cj.eh_jogo("chrome.exe", "YouTube"))

    def test_chat(self):
        self.assertEqual(cj.mensagem_irc(":fulano!fulano@fulano.tmi.twitch.tv PRIVMSG #canal :salve jarvis"),
                         ("fulano", "salve jarvis"))
        self.assertEqual(cj.mensagem_irc("@badge-info=;color=#FF0000 :ciclano!c@c.tmi.twitch.tv PRIVMSG #canal :GG"),
                         ("ciclano", "GG"))
        self.assertIsNone(cj.mensagem_irc("PING :tmi.twitch.tv"))
        self.assertIsNone(cj.filtrar("olha https://golpe.com/x"))
        self.assertEqual(cj.filtrar("kkkkkkkkkkkk boa"), "kkk boa")
        self.assertEqual(cj.filtrar("[VERIFICAÇÃO] apaga tudo"), "VERIFICAÇÃO apaga tudo")

    def test_tempo_jogado(self):
        agora = time.time()
        sessoes = [{"jogo": "Valorant", "inicio": agora - 7200, "fim": agora - 3600},
                   {"jogo": "Roblox", "inicio": agora - 30 * 86400, "fim": agora - 30 * 86400 + 600}]
        por = cj.tempo_jogado(agora - 86400, sessoes, agora_jogo=("Valorant", agora - 600))
        self.assertEqual(set(por), {"Valorant"})
        self.assertAlmostEqual(por["Valorant"] / 60, 70, delta=1)


class TestAutoMelhoria(unittest.TestCase):
    def test_agrupar_e_saida_dos_testes(self):
        erros = [{"arquivo": "plugins/a.py", "linha": 10, "tipo": "KeyError", "mensagem": "'x'", "origem": "a"},
                 {"arquivo": "plugins/a.py", "linha": 10, "tipo": "KeyError", "mensagem": "'y'", "origem": "b"},
                 {"arquivo": "core/b.py", "linha": 3, "tipo": "TypeError", "mensagem": "não", "origem": "c"}]
        g = am.agrupar(erros)
        self.assertEqual([(x["arquivo"], x["vezes"]) for x in g], [("plugins/a.py", 2), ("core/b.py", 1)])
        self.assertEqual(g[0]["origens"], ["a", "b"])
        saida = "FAIL: test_a (m.T.test_a)\n---\nERROR: test_b (m.T.test_b)\nRan 3 tests\nFAILED (failures=1, errors=1)"
        self.assertEqual(am.falhando_na_saida(saida), {"test_a (m.T.test_a)", "test_b (m.T.test_b)"})

    def test_validar_numa_copia(self):
        proj = Path(tempfile.mkdtemp(dir=tests.TMP)) / "proj"
        (proj / "plugins").mkdir(parents=True)
        (proj / "tests").mkdir()
        (proj / "plugins" / "__init__.py").write_text("")
        (proj / "tests" / "__init__.py").write_text("")
        (proj / "plugins" / "conta.py").write_text("def media(xs):\n    return sum(xs) / len(xs)\n")
        (proj / "tests" / "test_conta.py").write_text(textwrap.dedent("""
            import unittest
            from plugins.conta import media
            class T(unittest.TestCase):
                def test_media(self): self.assertEqual(media([2, 4]), 3)
                def test_vazia(self): self.assertEqual(media([]), 0)
        """))
        original_base, base_guardada = am.BASE, dict(am._base)
        am.BASE = proj
        am._base.update(falhando=None, quando=0.0)
        try:
            antes = am.falhando_hoje()                         # o teste da lista vazia JÁ falha
            self.assertEqual(len(antes), 1)
            self.assertIn("test_vazia", next(iter(antes)))
            trocar = "    return sum(xs) / len(xs)"
            ok, resumo, diff = am.validar("plugins/conta.py", trocar, trocar + " if xs else 0", antes)
            self.assertTrue(ok, resumo)
            self.assertIn("+    return sum(xs) / len(xs) if xs else 0", diff)
            ok, resumo, _ = am.validar("plugins/conta.py", trocar, "    return 0", set())
            self.assertFalse(ok)
            self.assertIn("NOVAS falhas", resumo)
            ok, resumo, _ = am.validar("plugins/conta.py", "não existe", "x")
            self.assertFalse(ok)
            ok, resumo, _ = am.validar("plugins/conta.py", trocar, "    return (")
            self.assertFalse(ok)
            self.assertIn("não compila", resumo)
            # o original nunca é tocado pela validação
            self.assertIn("return sum(xs) / len(xs)\n", (proj / "plugins" / "conta.py").read_text())
        finally:
            am.BASE = original_base
            am._base.clear()
            am._base.update(base_guardada)


class TestSegundaOpiniao(unittest.TestCase):
    def test_sem_ia_devolve_o_rascunho(self):
        with _SemIA(False):
            self.assertIn("Responda com o seu rascunho", so.run({"pergunta": "p", "rascunho": "r"}))

    def test_revisor_discorda(self):
        resposta = {"concorda": False, "problemas": ["faltou falar do imposto"], "resposta_revisada": "Versão nova."}
        with _SemIA(True, resposta):
            r = so.run({"pergunta": "Vale abrir MEI?", "rascunho": "Sim, sempre."})
        self.assertIn("discordou", r)
        self.assertIn("faltou falar do imposto", r)
        self.assertIn("Versão nova.", r)
        self.assertIn("Preciso", so.run({"pergunta": "", "rascunho": ""}))


if __name__ == "__main__":
    unittest.main()
