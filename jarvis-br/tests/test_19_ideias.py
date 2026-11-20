"""
Testes da 1.9 — as 14 ideias (gestos, memória por projeto, aula, snapshots,
vigia do servidor, ditado, testes comemorados, loja, holograma, DJ, XP Stark,
pausa quando sai, resumo de vídeo). Sem câmera, microfone, internet ou WhatsApp.
"""
import json
import shutil
import sqlite3
import subprocess
import textwrap
import time
import unittest
from datetime import datetime
from unittest import mock

import tests
from plugins import (_midia, _whatsapp as W, ditado, gamificacao as gm, gestos as G, guarda_vps as gv, jarvis_dj,
                     memoria_projeto as mp, modo_aula, pausa_ausente as pa, relatorio_loja as rl, resumo_video as rv,
                     snapshots as sn, testes_vivos as tv)


# ── mãos de mentira (21 pontos do MediaPipe) ─────────────────────────────────
def mao(estendidos=("polegar", "indicador", "medio", "anelar", "minimo"), dx=0.0, dy=0.0, pinca=False):
    pts = [(0.5, 0.8)] + [(0, 0)] * 20
    for i, (nome, x) in enumerate([("indicador", 0.45), ("medio", 0.5), ("anelar", 0.55), ("minimo", 0.6)]):
        base = 5 + i * 4
        pts[base] = (x, 0.6)
        if nome in estendidos:
            pts[base + 1], pts[base + 2], pts[base + 3] = (x, 0.5), (x, 0.42), (x, 0.35)
        else:
            pts[base + 1], pts[base + 2], pts[base + 3] = (x, 0.55), (x, 0.6), (x, 0.65)
    pts[1], pts[2] = (0.42, 0.72), (0.38, 0.66)
    if pinca:
        pts[3], pts[4] = (0.42, 0.45), (0.46, 0.37)
    elif "polegar" in estendidos:
        pts[3], pts[4] = (0.32, 0.6), (0.25, 0.55)
    else:
        pts[3], pts[4] = (0.42, 0.65), (0.5, 0.62)
    return [(x + dx, y + dy) for x, y in pts]


class TestGestos(unittest.TestCase):
    def test_gestos_parados(self):
        self.assertEqual(G.gesto(mao()), "aberta")
        self.assertEqual(G.gesto(mao(("indicador", "medio"))), "paz")
        self.assertEqual(G.gesto(mao(())), "punho")
        self.assertEqual(G.gesto(mao(("indicador",), pinca=True)), "pinca")

    def test_interpretador(self):
        it = G.Interpretador(espelhar=True)
        acoes = []
        for k in range(10):                                   # mão aberta parada ~0,7 s
            acoes += it.alimentar(mao(), k * 0.08)
        self.assertEqual(acoes, [("play_pause",)])
        self.assertEqual(it.alimentar(mao(), 0.9), [])        # não repete
        it = G.Interpretador(espelhar=True)
        acoes = []
        for k in range(6):                                    # desliza na imagem da esquerda para a direita
            acoes += it.alimentar(mao(dx=-0.2 + k * 0.08), k * 0.08)
        self.assertEqual(acoes, [("trocar_janela", True)])    # espelhado: na vida real foi para a esquerda
        it = G.Interpretador()
        vol = []
        for k in range(8):                                    # pinça subindo
            vol += [a[1] for a in it.alimentar(mao(("indicador",), pinca=True, dy=-k * 0.02), k * 0.08) if a[0] == "volume"]
        self.assertGreater(sum(vol), 10)
        it = G.Interpretador()
        acoes = []
        for k in range(10):
            acoes += it.alimentar(mao(("indicador", "medio")), k * 0.08)
        self.assertEqual(acoes, [("chamar",)])
        self.assertEqual(it.alimentar(None, 1.0), [])


class TestPresencaEMidia(unittest.TestCase):
    def test_presenca(self):
        p = pa.Presenca(10)
        p.visto = 0
        self.assertEqual(p.atualizar(False, True, 5), "")
        self.assertEqual(p.atualizar(False, False, 11), "")      # nada tocando: não pausa
        self.assertEqual(p.atualizar(False, True, 12), "pausar")
        self.assertEqual(p.atualizar(False, True, 13), "")       # o som ainda está parando
        self.assertEqual(p.atualizar(True, None, 20), "")
        self.assertEqual(p.atualizar(True, None, 21), "retomar")
        p2 = pa.Presenca(10)
        p2.visto = 0
        p2.atualizar(False, True, 12)
        p2.atualizar(False, True, 30)                              # deu play de longe
        self.assertFalse(p2.pausei)

    def test_faixa(self):
        self.assertEqual(_midia.faixa_do_titulo("Racionais MC's - Negro Drama", "Spotify.exe"), "Racionais MC's - Negro Drama")
        self.assertEqual(_midia.faixa_do_titulo("Spotify Premium", "Spotify.exe"), "")
        self.assertEqual(_midia.faixa_do_titulo("(2) Música Boa - YouTube — Google Chrome", "chrome.exe"), "Música Boa")
        self.assertEqual(_midia.faixa_do_titulo("Documento - Word", "WINWORD.EXE"), "")

    def test_dj(self):
        d = jarvis_dj.Detector(a_cada=2)
        self.assertEqual(d.ver("A - 1", 0), "")
        self.assertEqual(d.ver("A - 1", 7), "")                   # a que já tocava não é anunciada
        self.assertEqual(d.ver("B - 2", 10), "")
        self.assertEqual(d.ver("B - 2", 17), "")                  # 1ª troca: a_cada=2 pula
        d.ver("C - 3", 20)
        self.assertEqual(d.ver("C - 3", 27), "C - 3")
        self.assertIn("só se tiver CERTEZA", jarvis_dj.instrucao("C - 3", "21:00"))


class TestMemoriaProjeto(unittest.TestCase):
    def test_titulos(self):
        self.assertEqual(mp.ler_titulo("● rosto_flutuante.py - jarvis-br - Visual Studio Code"),
                         ("jarvis-br", "rosto_flutuante.py"))
        self.assertEqual(mp.ler_titulo("loja (Workspace) - Visual Studio Code"), ("loja", ""))
        self.assertEqual(mp.ler_titulo("app.ts - site - [Trabalho] - Cursor"), ("site", "app.ts"))
        self.assertEqual(mp.ler_titulo("Welcome - Visual Studio Code"), ("", ""))
        self.assertEqual(mp.ler_titulo("YouTube - Google Chrome"), ("", ""))
        uris = ["file:///c%3A/Users/x/Desktop/jarvis-br", "file:///home/x/loja"]
        self.assertTrue(mp.caminho_do_projeto("jarvis-br", uris).lower().replace("\\", "/").endswith("desktop/jarvis-br"))
        self.assertEqual(mp.caminho_do_projeto("nada", uris), "")

    def test_sessao(self):
        d = {"projetos": {}, "abertos": {}, "ultimo": ""}
        jan = [{"titulo": "ui.py - jarvis-br - Visual Studio Code"}]
        for k in range(10):
            mp.tick(d, jan, jan[0], 1000 + k * mp.TICK_S)
        outra = {"titulo": "● rosto.py - jarvis-br - Visual Studio Code"}
        for k in range(4):
            mp.tick(d, [outra], outra, 1150 + k * mp.TICK_S)
        fechados = []
        for k in range(mp.FECHADO_TICKS):
            fechados += mp.tick(d, [], None, 1300 + k * mp.TICK_S)
        self.assertEqual(fechados, ["jarvis-br"])
        s = d["projetos"]["jarvis-br"]["sessoes"][-1]
        self.assertEqual(list(s["arquivos"])[0], "ui.py")
        d["projetos"]["jarvis-br"]["notas"].append({"ts": 1, "texto": "falta o menu de transparência"})
        frase = mp.frase_onde_parei("jarvis-br", d["projetos"]["jarvis-br"])
        self.assertIn("mexendo no ui.py", frase)
        self.assertIn("deixou anotado: falta o menu de transparência", frase)
        self.assertEqual(mp.achar_nome(d, "jarvis"), "jarvis-br")


@unittest.skipUnless(shutil.which("git"), "sem git")
class TestSnapshots(unittest.TestCase):
    def test_hora(self):
        agora = datetime(2026, 11, 3, 16, 0)
        self.assertEqual(sn.alvo_hora("às 15h", agora), datetime(2026, 11, 3, 15, 0))
        self.assertEqual(sn.alvo_hora("ontem 18:30", agora), datetime(2026, 11, 2, 18, 30))
        self.assertEqual(sn.alvo_hora("20h", agora), datetime(2026, 11, 2, 20, 0))      # ainda não chegou: ontem
        self.assertEqual(sn.alvo_hora("há 2 horas", agora), datetime(2026, 11, 3, 14, 0))
        self.assertIsNone(sn.alvo_hora("quando der", agora))
        self.assertEqual(sn.escolher([(100, "a"), (200, "b"), (300, "c")], 250), (200, "b"))
        self.assertIsNone(sn.escolher([(100, "a")], 50))

    def test_git_sem_mexer_no_branch(self):
        repo = tests.TMP / "repo_snap"
        shutil.rmtree(repo, ignore_errors=True)
        repo.mkdir()
        git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)  # noqa: E731
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (repo / "a.py").write_text("v1\n")
        git("add", ".")
        git("commit", "-qm", "inicio")
        (repo / "a.py").write_text("v2 não commitado\n")
        (repo / "novo.py").write_text("novo\n")
        c1 = sn.snapshot_git(repo)
        self.assertTrue(c1)
        self.assertEqual(sn.snapshot_git(repo), "")                 # nada mudou
        self.assertEqual(git("log", "--oneline").stdout.count("\n"), 1)   # o branch continua com 1 commit
        self.assertIn("M a.py", git("status", "--porcelain").stdout)      # o stage não foi tocado
        (repo / "a.py").write_text("v3 estragado\n")
        snaps = sn.snaps_git(repo)
        self.assertEqual(len(snaps), 1)
        git("restore", f"--source={snaps[0][1]}", "--worktree", "--", ".")
        self.assertEqual((repo / "a.py").read_text(), "v2 não commitado\n")

    def test_zip(self):
        pasta = tests.TMP / "proj_zip"
        (pasta / "node_modules").mkdir(parents=True, exist_ok=True)
        (pasta / "main.py").write_text("ok")
        (pasta / "node_modules" / "lixo.js").write_text("x")
        with mock.patch.object(sn, "config", lambda: {"manter": "3"}):
            arq = sn.zipar(pasta, tests.TMP / "zips", "proj")
        import zipfile
        self.assertEqual(zipfile.ZipFile(arq).namelist(), ["main.py"])


class TestAulaServidorDitado(unittest.TestCase):
    def test_escolher_aula(self):
        lista = [{"quando": datetime(2026, 11, 1, 19), "titulo": "banco de dados", "arquivo": "a"},
                 {"quando": datetime(2026, 11, 2, 19), "titulo": "redes", "arquivo": "b"},
                 {"quando": datetime(2026, 11, 3, 8), "titulo": "", "arquivo": "c"}]
        hoje = datetime(2026, 11, 3, 12)
        self.assertEqual(modo_aula.escolher_aula(lista, "ontem", hoje)["arquivo"], "b")
        self.assertEqual(modo_aula.escolher_aula(lista, "a de banco de dados", hoje)["arquivo"], "a")
        self.assertEqual(modo_aula.escolher_aula(lista, "última", hoje)["arquivo"], "c")
        self.assertIsNone(modo_aula.escolher_aula(lista, "anteontem às 3", datetime(2026, 11, 10)))
        pasta = tests.TMP / "aulas"
        (pasta / "2026-11-02_1900_redes").mkdir(parents=True, exist_ok=True)
        (pasta / "2026-11-02_1900_redes" / "aula.md").write_text("# Aula")
        self.assertEqual(modo_aula.aulas(pasta)[0]["titulo"], "redes")

    def test_recursos_vps(self):
        saida = textwrap.dedent("""\
            @@LOAD
            3.50 3.80 2.10 2/300 1234
            @@CPUS
            4
            @@MEM
            3900 300
            @@DISCO
            /dev/vda1 41152736 38000000 3152736 93% /
            /dev/vdb1 1000 100 900 10% /dados
            @@UP
            864000.5 1000.2
            """)
        r = gv.analisar_recursos(saida)
        self.assertEqual((r["cpu_pct"], r["mem_pct"], r["dias_ligado"]), (95.0, 92.3, 10.0))
        self.assertEqual(r["discos"], [("/", 93), ("/dados", 10)])
        self.assertEqual(gv.alertas_recursos(r), ["CPU em 95%", "memória em 92%", "disco / em 93%"])
        self.assertEqual(gv.analisar_recursos("lixo")["cpu_pct"], None)

    def test_ditado(self):
        self.assertEqual(ditado.formatar_fala("bom dia vírgula tudo certo ponto de interrogação"), "Bom dia, tudo certo?")
        self.assertEqual(ditado.formatar_fala("oi ponto nova linha até amanhã ponto"), "Oi.\nAté amanhã.")
        self.assertEqual(ditado.contexto({"titulo": "● cpf.py - loja - Visual Studio Code", "processo": "Code.exe"}),
                         {"tipo": "codigo", "linguagem": "Python", "app": "● cpf.py - loja - Visual Studio Code"})
        self.assertEqual(ditado.contexto({"titulo": "Caixa de entrada - Gmail — Google Chrome"})["tipo"], "email")
        self.assertEqual(ditado.contexto({"titulo": "WhatsApp"})["tipo"], "chat")
        self.assertEqual(ditado.limpar_saida("```python\ndef f():\n    pass\n```"), "def f():\n    pass")
        self.assertIn("SOMENTE o código", ditado.montar_prompt("valida cpf", {"tipo": "codigo", "linguagem": "Python"}))


class TestTestesVivos(unittest.TestCase):
    UNIT_FALHA = textwrap.dedent("""\
        ..F.
        ======================================================================
        FAIL: test_soma (tests.test_conta.TestConta.test_soma)
        ----------------------------------------------------------------------
        Traceback (most recent call last):
          File "C:\\p\\tests\\test_conta.py", line 9, in test_soma
            self.assertEqual(soma(1, 1), 3)
        AssertionError: 2 != 3

        ----------------------------------------------------------------------
        Ran 4 tests in 0.001s

        FAILED (failures=1)
        """)

    def test_ler(self):
        r = tv.ler_resultado(self.UNIT_FALHA)
        self.assertEqual((r["ok"], r["total"]), (False, 4))
        self.assertEqual(r["falhas"][0]["teste"], "TestConta.test_soma")
        self.assertEqual(r["falhas"][0]["erro"], "AssertionError: 2 != 3")
        self.assertEqual(r["falhas"][0]["linha"], "test_conta.py:9")
        self.assertIn("1 de 4 testes do loja falharam", tv.frase(r, "loja"))
        ok = tv.ler_resultado("....\n------\nRan 4 tests in 0.01s\n\nOK\n")
        self.assertTrue(ok["ok"])
        py = tv.ler_resultado("FAILED tests/test_a.py::test_x - assert 1 == 2\n==== 1 failed, 5 passed in 0.12s ====")
        self.assertEqual((py["ferramenta"], py["ok"], py["total"], py["falhas"][0]["teste"]), ("pytest", False, 6, "test_x"))

    def test_rodar_de_verdade(self):
        proj = tests.TMP / "proj_testes"
        (proj / "tests").mkdir(parents=True, exist_ok=True)
        (proj / "tests" / "__init__.py").write_text("")
        (proj / "tests" / "test_a.py").write_text("import unittest\nclass T(unittest.TestCase):\n"
                                                   "    def test_ok(self):\n        self.assertTrue(True)\n")
        r = tv.rodar(proj, timeout=120)
        self.assertTrue(r["ok"], r.get("saida"))
        self.assertEqual(r["total"], 1)


class TestLoja(unittest.TestCase):
    def setUp(self):
        self._arq = W.ARQ
        W.ARQ = tests.TMP / "whatsapp_loja.json"
        W.ARQ.unlink(missing_ok=True)
        self.enviadas, self.donos = [], []
        self.p = [mock.patch.object(W, "enviar", lambda c, t="", a=None, sem_prefixo=False:
                                    self.enviadas.append((c, t, sem_prefixo)) or True),
                  mock.patch.object(W, "para_donos", lambda t, a=None: self.donos.append(t) or 1),
                  mock.patch.object(W, "enviar_donos_para_ponte", lambda: None),
                  mock.patch.object(W, "numeros_dono", lambda: []),
                  mock.patch.object(W, "estoque_para_ia", lambda limite=150: "- Conjunto moletom azul tam 4: 3 un.")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        W.ARQ = self._arq

    def test_comandos(self):
        self.assertEqual(W.ler_comando_loja("aprovar 3"), ("aprovar", 3, ""))
        self.assertEqual(W.ler_comando_loja("OK #12"), ("aprovar", 12, ""))
        self.assertEqual(W.ler_comando_loja("editar 3: Temos sim!"), ("editar", 3, "Temos sim!"))
        self.assertEqual(W.ler_comando_loja("ignorar 2"), ("ignorar", 2, ""))
        self.assertEqual(W.ler_comando_loja("rascunhos"), ("listar", 0, ""))
        self.assertEqual(W.ler_comando_loja("aprova tudo isso aí"), ("", 0, ""))
        self.assertEqual(W.decidir({"chat": "x@c.us", "cliente": True}, [], [], ""), "cliente")
        self.assertIn("Conjunto moletom azul", W.montar_prompt_cliente("Ana", "tem tam 4?", W.estoque_para_ia(), "carinhoso", "Loja"))

    def test_fluxo_rascunho(self):
        with mock.patch("plugins._ia.disponivel", lambda: True), \
                mock.patch("plugins._ia.perguntar", lambda *a, **k: "Oi, Ana! Temos sim o tamanho 4 💙"):
            W.tratar({"chat": "ana@c.us", "cliente": True, "nome": "Ana", "texto": "tem tamanho 4?"})
        self.assertEqual(self.enviadas, [])                              # nunca responde sozinho
        self.assertIn("Rascunho #1", self.donos[-1])
        W.tratar({"chat": "eu@c.us", "eu": True, "texto": "aprovar 1"})
        self.assertIn(("ana@c.us", "Oi, Ana! Temos sim o tamanho 4 💙", True), self.enviadas)
        self.assertIn("Enviado para Ana", self.enviadas[-1][1])
        W.tratar({"chat": "eu@c.us", "eu": True, "texto": "aprovar 1"})
        self.assertIn("Não achei o rascunho #1", self.enviadas[-1][1])  # não manda duas vezes


@unittest.skipUnless(shutil.which("node"), "sem Node.js")
class TestPonteLoja(unittest.TestCase):
    def test_loja_e_numero_do_dono(self):
        from tests.test_18_remoto import TestPonteNode
        pasta = tests.TMP / "ponte_loja"
        for mod, codigo in (("whatsapp-web.js", TestPonteNode.FALSO), ("qrcode", TestPonteNode.QR)):
            (pasta / "node_modules" / mod).mkdir(parents=True, exist_ok=True)
            (pasta / "node_modules" / mod / "index.js").write_text(codigo, encoding="utf-8")
        shutil.copy(tests.RAIZ / "whatsapp_ponte" / "ponte.js", pasta / "ponte.js")
        roteiro = [{"evento": "message", "id": "a", "from": "cli@c.us", "to": "x", "body": "tem tam 4?", "fromMe": False,
                    "numero": "5511911112222"},
                   {"evento": "message", "id": "b", "from": "dono@lid", "to": "x", "body": "status", "fromMe": False,
                    "numero": "5562988887777"},
                   {"evento": "message_create", "id": "c", "from": "5562900000000@c.us", "to": "cli@c.us",
                    "body": "resposta minha", "fromMe": True}]
        (pasta / "roteiro.json").write_text(json.dumps(roteiro), encoding="utf-8")
        import os
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        env = dict(os.environ, JARVIS_WA_PORTA=str(porta), JARVIS_WA_TOKEN="t" * 24, JARVIS_WA_SESSAO=str(pasta / "s"),
                   ROTEIRO=str(pasta / "roteiro.json"), SAIDA=str(pasta / "saida.jsonl"))
        # o roteiro dispara 300 ms depois de "pronto": configura loja + número antes disso
        proc = subprocess.Popen(["node", "ponte.js"], cwd=pasta, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        antigo = dict(W._p)
        try:
            W._p.update(porta=porta, token="t" * 24, proc=proc)
            for _ in range(100):
                if W._http("POST", "/donos", {"ids": [], "codigo": "", "numeros": ["62988887777"], "loja": True},
                           timeout=1).get("ok"):
                    break
                time.sleep(0.02)
            time.sleep(1.2)
            evs = W._http("GET", "/eventos?desde=0")["eventos"]
            self.assertEqual([(e["chat"], bool(e.get("cliente"))) for e in evs], [("cli@c.us", True), ("dono@lid", False)])
        finally:
            proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            W._p.clear()
            W._p.update(antigo)


class TestRelatorioXPVideo(unittest.TestCase):
    def test_relatorio(self):
        vendas = [{"data": "2026-11-01 10:00", "produto": "Body bebê", "quantidade": "3", "total": "90,00"},
                  {"data": "2026-10-30 10:00", "produto": "Conjunto moletom", "quantidade": "1", "total": "89,90"},
                  {"data": "2026-10-28 15:00", "produto": "Body bebê", "quantidade": "1", "total": "30,00"},
                  {"data": "2026-10-20 10:00", "produto": "Vestido", "quantidade": "1", "total": "50,00"}]
        estoque = [{"produto": "Body bebê", "quantidade": "5"}, {"produto": "Vestido", "quantidade": "4"},
                   {"produto": "Jaqueta jeans", "quantidade": "2"}, {"produto": "Conjunto moletom", "quantidade": "0"}]
        r = rl.calcular(vendas, estoque, datetime(2026, 11, 2, 9), dias_parado=7)
        self.assertEqual((r["vendas"], r["pecas"], round(r["total"], 2)), (3, 5, 209.9))
        self.assertEqual(r["top"][0]["produto"], "Body bebê")
        self.assertEqual([p["produto"] for p in r["parados"]], ["Jaqueta jeans", "Vestido"])
        self.assertEqual(r["sugestao"], "Jaqueta jeans")
        t = rl.texto(r)
        self.assertIn("Mais vendido: Body bebê (4)", t)
        self.assertIn("Jaqueta jeans (2 un., nunca vendeu)", t)
        self.assertTrue(rl.deve_rodar(datetime(2026, 11, 2, 9), ""))
        self.assertFalse(rl.deve_rodar(datetime(2026, 11, 2, 7), ""))
        self.assertFalse(rl.deve_rodar(datetime(2026, 11, 2, 9), "2026-45"))
        self.assertFalse(rl.deve_rodar(datetime(2026, 11, 3, 9), ""))

    def test_xp_stark(self):
        self.assertEqual(gm.titulo_de(1), "Recruta")
        self.assertEqual(gm.titulo_de(12), "Engenheiro Chefe")
        self.assertEqual(gm.frase_nivel(11, 12), "Parabéns, senhor. Nível 12 alcançado. Novo título desbloqueado: Engenheiro Chefe.")
        self.assertEqual(gm.frase_nivel(12, 13), "Parabéns, senhor. Nível 13 alcançado.")
        self.assertEqual(gm.frase_nivel(5, 5), "")
        self.assertEqual(gm.REGRAS[("cristal_video", None)], 30)

    def test_video(self):
        self.assertEqual(rv.id_do_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10"), "dQw4w9WgXcQ")
        self.assertEqual(rv.id_do_video("veja https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(rv.id_do_video("https://youtube.com/shorts/abcdefghijk"), "abcdefghijk")
        self.assertEqual(rv.titulo_da_aba("(3) Como fazer pão - YouTube — Google Chrome"), "Como fazer pão")
        hist = tests.TMP / "History"
        hist.unlink(missing_ok=True)
        con = sqlite3.connect(str(hist))
        con.execute("CREATE TABLE urls (url TEXT, title TEXT, last_visit_time INTEGER)")
        con.executemany("INSERT INTO urls VALUES (?, ?, ?)", [
            ("https://www.youtube.com/watch?v=AAAAAAAAAAA", "Como fazer pão - YouTube", 100),
            ("https://www.youtube.com/watch?v=BBBBBBBBBBB", "Outro vídeo - YouTube", 200),
            ("https://site.com", "Site", 300)])
        con.commit()
        con.close()
        with mock.patch.object(rv, "historicos", lambda: [hist]):
            vids = rv.videos_recentes()
        self.assertEqual([v[1][-11:] for v in vids], ["BBBBBBBBBBB", "AAAAAAAAAAA"])
        self.assertTrue(rv.escolher(vids, "Como fazer pão").endswith("AAAAAAAAAAA"))
        self.assertTrue(rv.escolher(vids, "").endswith("BBBBBBBBBBB"))


if __name__ == "__main__":
    unittest.main()

