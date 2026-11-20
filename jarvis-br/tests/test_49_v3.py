"""Testes da 3.0 — vigia de travamento, relógio central, busca do catálogo e as 20 ideias."""
import asyncio
import importlib
import json
import random
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import tests  # noqa: F401
from core import relogio, vigia
from plugins import (_lote2, antecipacao, cacador_promessas, clientes_loja, cofre_condicional, commit_mentiroso, conferir_pagamento,
                     crescimento_criancas, detector_cansaco, dojo_debug, duelo_ia, e_se, jornal_vida, livro_vo, mapa_calor, oraculo, rap_semana,
                     serendipidade, trilha_produtiva)

NOVOS = ("oraculo antecipacao pre_mortem detector_cansaco cofre_condicional cacador_promessas serendipidade e_se crescimento_criancas "
         "conferir_pagamento commit_mentiroso arqueologo_codigo dojo_debug livro_vo jornal_vida rap_semana mapa_calor trilha_produtiva "
         "duelo_ia").split()
BUG = r"NoneType|object|attribute|unsupported|index out|KeyError|not callable|positional|unexpected keyword|referenced|not defined"
HOJE = date(2026, 11, 13)                                   # sexta-feira


class TestVigia(unittest.TestCase):
    def test_rapido_lento_e_erro(self):
        tarde = []

        async def cenario():
            r1 = await vigia.executar(lambda: "ok", "rapida", limite=1)
            r2 = await vigia.executar(lambda: time.sleep(0.6) or "terminei", "lenta", limite=0.2,
                                      ao_terminar_tarde=lambda n, r, s: tarde.append((n, r)))
            await asyncio.sleep(0.8)                        # a lenta termina em segundo plano
            with self.assertRaises(ValueError):
                await vigia.executar(lambda: (_ for _ in ()).throw(ValueError("x")), "quebra", limite=1)
            return r1, r2
        r1, r2 = asyncio.run(cenario())
        self.assertEqual(r1, ("ok", False))
        self.assertTrue(r2[1] and "AINDA TRABALHANDO" in r2[0])
        self.assertEqual(tarde, [("lenta", "terminei")])
        self.assertEqual(vigia.ocupadas(), 0)

    def test_lotado_nao_trava(self):
        trava = threading.Event()
        with mock.patch.object(vigia, "MAX_THREADS", 3):
            vigia.executar_sync(trava.wait, "presa1", limite=0.05)
            vigia.executar_sync(trava.wait, "presa2", limite=0.05)
            r, atrasou = vigia.executar_sync(lambda: "x", "nova", limite=0.5)
            self.assertTrue(atrasou and "OCUPADO" in r)
            trava.set()
            time.sleep(0.2)
            self.assertEqual(vigia.executar_sync(lambda: "x", "nova", limite=0.5), ("x", False))


class TestRelogio(unittest.TestCase):
    def test_uma_thread_para_todos(self):
        feitos = []
        with mock.patch.object(relogio, "_tarefas", {}), mock.patch("threading.Thread.start", lambda self: None):
            relogio.agendar("a", lambda: feitos.append("a"), a_cada_s=60, primeira_em_s=0)
            relogio.agendar("b", lambda: 1 / 0, a_cada_s=60, primeira_em_s=0)
            relogio.agendar("c", lambda: feitos.append("c"), a_cada_s=60, primeira_em_s=500)
            agora = time.time() + 1
            self.assertEqual(sorted(relogio.rodar_vencidas(agora)), ["a", "b"])
            self.assertEqual(relogio.rodar_vencidas(agora + 1), [])                  # só de novo daqui a 60 s
            self.assertEqual(relogio.rodar_vencidas(agora + 61), ["a", "b"])
            erros = {t["nome"]: t["erros"] for t in relogio.tarefas()}
            self.assertEqual((feitos, erros["b"]), (["a", "a"], 2))


class TestBusca(unittest.TestCase):
    CASOS = {"quanto vou pagar de parcela num financiamento": "juros", "abrir o caixa da loja com 100 de troco": "caixa_loja",
             "cliente quer um tamanho que acabou": "lista_espera", "qual a fase da lua hoje": "astronomia",
             "onde eu guardei o passaporte": "onde_guardei", "quanto de tinta para pintar o quarto": "calculadora_obra",
             "converte 5 libras em quilos": "conversor_unidades", "põe um timer de 10 minutos": "cronometros",
             "o leite da geladeira vence quando": "despensa", "lista de convidados do aniversário": "festa",
             "escrever o nome da loja com letra bonita": "texto_estilizado", "brincadeira de stop": "jogos_de_festa",
             "o que você sonhou": "sonhos", "isso é golpe? me pediram um pix": "detector_golpe", "conferir para quem vai esse pix antes de pagar": "conferir_pagamento",
             "a criança cresceu e mudou de tamanho": "crescimento_criancas", "pergunta da semana para a vó": "livro_vo",
             "quanto a loja vai vender semana que vem": "oraculo", "faz o rap da semana": "rap_semana",
             "duelo entre jarvis e friday": "duelo_ia", "guardar mensagem para quando a loja vender 10 mil": "cofre_condicional",
             "eu prometi mandar o orçamento amanhã": "cacador_promessas", "e se eu tivesse guardado dinheiro": "e_se",
             "colocar bugs no meu código para treinar": "dojo_debug", "por que existe essa linha do código": "arqueologo_codigo",
             "a mensagem do commit está mentindo": "commit_mentiroso", "eu estou cansado": "detector_cansaco"}

    def test_acha_o_plugin_certo(self):
        from core import registro_ferramentas
        from plugins import catalogo
        decls = registro_ferramentas.declaracoes()
        erros = [q for q, alvo in self.CASOS.items() if alvo not in [d["name"] for d in catalogo.buscar(decls, q, 3)]]
        self.assertLessEqual(len(erros), 1, erros)
        self.assertEqual(catalogo.raizes("Sorteia os times")[0], ("sorte", "sort"))


class TestIdeias(unittest.TestCase):
    def test_oraculo(self):
        serie = {}
        for k in range(1, 36):
            d = HOJE - timedelta(k)
            serie[d.isoformat()] = 900 if d.weekday() == 4 else 500
        prev = oraculo.prever_semana(serie, oraculo.segunda_que_vem(HOJE))
        self.assertEqual(len(prev), 7)
        self.assertEqual(prev["2026-11-20"], 900)                                    # a sexta
        self.assertEqual(prev["2026-11-16"], 500)
        tot, dia, n = oraculo.erro({"a": 100, "b": 100, "c": 100}, {"a": 110, "b": 90, "c": 100})
        self.assertEqual((tot, n), (0.0, 3))
        self.assertAlmostEqual(dia, (10 / 110 * 100 + 10 / 90 * 100) / 3)

    def test_antecipacao(self):
        base = time.mktime((2026, 11, 2, 8, 5, 0, 0, 0, -1))
        ch = [{"ts": base + d * 86400, "ferramenta": "resumo_do_dia", "params": '{"action": "agora"}', "ok": 1} for d in range(5)]
        ch += [{"ts": base + d * 86400, "ferramenta": "musica", "params": '{"action": "tocar"}', "ok": 1} for d in range(5)]
        ch += [{"ts": base + d * 86400, "ferramenta": "whatsapp", "params": '{"action": "ver"}', "ok": 1} for d in range(5)]
        h = antecipacao.habitos(ch)
        self.assertEqual(sorted(f for f, _, _ in h[8]), ["musica", "resumo_do_dia"])   # whatsapp nunca
        self.assertTrue(antecipacao.so_leitura('{"action": "agora"}'))
        self.assertFalse(antecipacao.so_leitura('{"action": "tocar"}'))

    def test_cansaco(self):
        agora = 100_000.0
        tempos = [agora - 6 * 3600 + i * 600 for i in range(37)]                    # 6 h sem pausa de 20 min
        self.assertAlmostEqual(detector_cansaco.sessao_continua(tempos, agora), 6 * 3600, delta=1)
        self.assertEqual(detector_cansaco.sessao_continua([agora - 3000], agora), 0)
        pts, motivos = detector_cansaco.avaliar(2, 6 * 3600, 2)
        self.assertEqual((detector_cansaco.nivel(pts), len(motivos)), ("cansado", 3))
        self.assertEqual(detector_cansaco.nivel(detector_cansaco.avaliar(15, 600, 0)[0]), "descansado")

    def test_cofre(self):
        self.assertEqual(cofre_condicional.entender("loja vender 10 mil no mês"), {"tipo": "vendas", "periodo": "mes", "alvo": 10000.0})
        self.assertEqual(cofre_condicional.entender("30 dias seguidos de ler"), {"tipo": "habito", "nome": "ler", "alvo": 30})
        self.assertIsNone(cofre_condicional.entender("quando eu ficar rico"))
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())):
            cofre_condicional.run({"action": "guardar", "mensagem": "Parabéns, você!", "condicao": "01/01/2026"})
            cofre_condicional.run({"action": "guardar", "mensagem": "Ainda não", "condicao": "200 km"})
            self.assertNotIn("Parabéns", cofre_condicional.run({"action": "listar"}))        # não mostra o conteúdo
            self.assertIn("Parabéns, você!", cofre_condicional.run({"action": "checar"}))
            self.assertIn("0 de 200 km", cofre_condicional.run({"action": "listar"}))

    def test_promessas(self):
        self.assertEqual(cacador_promessas.prazo("amanhã eu mando o orçamento", HOJE), HOJE + timedelta(1))
        self.assertEqual(cacador_promessas.prazo("vou te passar na segunda", HOJE), date(2026, 11, 16))
        self.assertEqual(cacador_promessas.prazo("eu pago dia 30", date(2027, 1, 31)), date(2027, 3, 30))
        self.assertTrue(cacador_promessas.eh_promessa("fico de entregar as peças semana que vem"))
        self.assertFalse(cacador_promessas.eh_promessa("vou dormir"))
        self.assertFalse(cacador_promessas.eh_promessa("vou ter que pagar?"))
        linhas = [{"ts": 1, "linha": "Você: amanhã eu mando o orçamento para a Ana"}, {"ts": 2, "linha": "JARVIS: Anotado."}]
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), mock.patch("core.registro_uso.linhas_registro", lambda **k: linhas):
            self.assertEqual(len(cacador_promessas.varrer(0)), 1)
            self.assertEqual(cacador_promessas.varrer(0), [])                           # não duplica
            self.assertIn("orçamento", cacador_promessas.run({"action": "listar"}))
            self.assertIn("cumprida", cacador_promessas.run({"action": "cumpri", "numero": "1"}))

    def test_serendipidade_e_e_se(self):
        itens = [{"texto": f"ideia {i}", "origem": "ideia" if i % 2 else "anotação", "quando": i * 86400 * 40} for i in range(4)]
        a, b = serendipidade.escolher_par(itens, set(), random.Random(1))
        self.assertNotEqual(a["texto"], b["texto"])
        self.assertIsNone(serendipidade.escolher_par(itens[:1], set()))
        self.assertEqual(e_se.guardado(50, "semana", date(2026, 1, 1), HOJE), (2300, 2300))
        self.assertIn("R$ 2.300,00", e_se.calcular("guardado 50 por semana desde janeiro", HOJE))
        self.assertIn("Desde quando", e_se.calcular("e se eu fosse rico", HOJE))

    def test_criancas_e_clientes(self):
        c = {"nome": "Miguel", "nascimento": "2023-09-10", "tamanho": "1"}
        self.assertEqual(crescimento_criancas.tamanho_esperado(date(2023, 9, 10), HOJE), "4")
        self.assertEqual(crescimento_criancas.pulou(c, HOJE), "4")
        self.assertIsNone(crescimento_criancas.pulou({**c, "tamanho": "4"}, HOJE))
        self.assertIn("Miguel já deve estar usando o tamanho 4", crescimento_criancas.mensagem(c, HOJE))
        cli = {"nome": "Ana", "compras": [{"data": d, "valor": 50} for d in ("2026-09-01", "2026-09-15", "2026-09-29", "2026-10-13")]}
        self.assertEqual(clientes_loja.ritmo(cli, HOJE), (14.0, 31))
        self.assertTrue(clientes_loja.fora_do_ritmo(cli, HOJE))
        self.assertFalse(clientes_loja.fora_do_ritmo(cli, date(2026, 10, 30)))

    def test_conferir_pagamento(self):
        pix = "00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-4266554400005204000053039865802BR5913Fulano de Tal6008BRASILIA6304ABCD"
        self.assertEqual(conferir_pagamento.pix_destino(pix), "Fulano de Tal (BRASILIA)")
        self.assertIsNone(conferir_pagamento.boleto_ok("oi, tudo bem?"))
        self.assertEqual(conferir_pagamento.conferir("CNPJ 11.111.111/1111-11")[0], ["o CNPJ 11.111.111/1111-11 é inválido"])
        r = conferir_pagamento.run({"action": "conferir", "texto": "Oi mãe, troquei de número, me faz um pix urgente " + pix})
        self.assertIn("risco ALTO", r)                                  # usa o detector_golpe original
        self.assertIn("Fulano de Tal", r)                               # Pix achado no meio da mensagem
        self.assertNotIn("gov", r.split("Este Pix")[0])                 # o código Pix não conta como link falso
        from plugins import _boleto
        barras = "2379" + "0" + "1000" + "0000015000" + "3381260082677139700000300"
        barras = barras[:4] + str(_boleto.mod11_banco(barras[:4] + barras[5:])) + barras[5:]
        ln = _boleto.barras_para_linha(barras)
        linha = f"{ln[:5]}.{ln[5:10]} {ln[10:15]}.{ln[15:21]} {ln[21:26]}.{ln[26:32]} {ln[32]} {ln[33:]}"
        r = conferir_pagamento.run({"action": "conferir", "texto": "boleto de R$ 150,00 da escola, vence dia 10: " + linha})
        self.assertIn("dígitos certos (valor R$ 150", r)
        self.assertNotIn("CNPJ", r)                                     # o último bloco da linha não é CNPJ
        adulterada = linha[:3] + str((int(linha[3]) + 1) % 10) + linha[4:]
        self.assertIs(conferir_pagamento.boleto_ok(adulterada), False)
        self.assertIn("dígito errado", conferir_pagamento.run({"action": "conferir", "texto": adulterada}))

    def test_git(self):
        pasta = Path(tempfile.mkdtemp())
        g = lambda *a: subprocess.run(["git", "-C", str(pasta), *a], capture_output=True, check=True)  # noqa: E731
        g("init", "-q")
        g("config", "user.email", "t@t")
        g("config", "user.name", "Teste")
        (pasta / "app.py").write_text("def soma(a, b):\n    return a + b\n")
        g("add", ".")
        g("commit", "-qm", "feat: soma")
        (pasta / "app.py").write_text("def soma(a, b):\n    return a + b\n" + "".join(f"x{i} = {i}\n" for i in range(80)))
        (pasta / "README.md").write_text("oi\n")
        g("add", ".")
        g("commit", "-qm", "docs: pequeno ajuste no readme")
        ruins = {c["assunto"]: commit_mentiroso.julgar_rapido(c) for c in commit_mentiroso.commits(pasta, 5)}
        self.assertEqual(ruins["feat: soma"], [])
        self.assertEqual(len(ruins["docs: pequeno ajuste no readme"]), 2)                # "pequeno" e "docs" mentem
        self.assertIn("1 de 2 commits", commit_mentiroso.run({"action": "verificar", "pasta": str(pasta)}))
        arq = importlib.import_module("plugins.arqueologo_codigo")
        self.assertIn('"feat: soma"', arq.run({"action": "linha", "arquivo": str(pasta / "app.py"), "linha": "2"}))
        self.assertIn("soma() tem 2 linhas vindas de 1 commit", arq.run({"action": "funcao", "arquivo": str(pasta / "app.py"), "nome": "soma"}))

    def test_dojo(self):
        src = "def f(xs):\n    if len(xs) < 2:\n        return True\n    return xs[0] == xs[-1] and len(xs) > 3\n"
        novo, bugs = dojo_debug.plantar(src, 3, random.Random(3))
        self.assertEqual(len(bugs), 3)
        compile(novo, "x", "exec")
        self.assertEqual(len({b["linha"] for b in bugs}), 3)                              # um por linha
        pasta = Path(tempfile.mkdtemp())
        (pasta / "f.py").write_text(src)
        with mock.patch.object(_lote2, "PASTA", pasta / "dados"):
            self.assertIn("bug(s) escondido(s)", dojo_debug.run({"action": "novo", "arquivo": str(pasta / "f.py"), "bugs": "2"}))
            self.assertEqual((pasta / "f.py").read_text(), src)                           # original intacto
            linhas = [b["linha"] for b in _lote2.carregar("dojo", {})["atual"]["bugs"]]
            self.assertIn("Achou", dojo_debug.run({"action": "chute", "linha": str(linhas[0])}))
            self.assertIn("Mestre do debug", dojo_debug.run({"action": "chute", "linha": str(linhas[1])}))
            self.assertIn("2 bug(s)", dojo_debug.run({"action": "placar"}))

    def test_livro_vo(self):
        prim = livro_vo.proxima(set())
        self.assertEqual(prim, ("Infância", livro_vo.CAPITULOS["Infância"][0]))
        self.assertEqual(livro_vo.proxima({prim[1]})[0], "Família")                      # alterna capítulos
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), mock.patch("plugins._comum.pasta_jarvis", lambda n: Path(tempfile.mkdtemp())), \
                mock.patch("plugins._comum.abrir_no_sistema", lambda *a: True):
            livro_vo.run({"action": "pergunta"})
            self.assertIn("Infância", livro_vo.run({"action": "responder", "texto": "Eu morava num sítio perto de Trindade."}))
            self.assertIn("1 memória", livro_vo.run({"action": "livro"}))
            self.assertIn("1 de ", livro_vo.run({"action": "progresso"}))

    def test_jornal_rap_mapa_trilha_duelo(self):
        self.assertEqual(jornal_vida.manchete({"vendas": {"variacao": 42.0}}), "LOJA VENDE 42% ACIMA DO NORMAL")
        self.assertIn("PÁGINA EM BRANCO", jornal_vida.manchete({}))
        versos = rap_semana.offline(["a loja vendeu R$ 3.000"], random.Random(1))
        self.assertTrue(len(versos) >= 6 and "Essa semana a loja vendeu R$ 3.000," in versos)
        self.assertEqual(mapa_calor.maior_sequencia({"2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05"}), 3)
        self.assertEqual(mapa_calor.nivel(0, [1, 2, 3]), 0)
        self.assertEqual(mapa_calor.nivel(10, [1, 2, 3]), 4)
        self.assertEqual(mapa_calor.svg({"2026-03-01": 2}, 2026).count("<rect"), 365)
        t0 = 1_000_000.0
        eventos = [(t0 + k * 86400, "lofi") for k in range(4)]
        trabalho = [t0 + k * 86400 + m * 600 for k in range(4) for m in range(6)]           # 6 sinais nas 2 h depois do lofi
        trabalho += [t0 + k * 86400 + 30000 + m * 3000 for k in range(4) for m in range(2)]  # pouco trabalho sem música
        efe = trilha_produtiva.efeitos(eventos, trabalho, t0 + 4 * 86400)
        self.assertEqual(efe[0][0], "lofi")
        self.assertGreater(efe[0][1], 50)
        self.assertEqual(duelo_ia.categoria("como vender mais na loja"), "loja")
        ra, rb = duelo_ia.elo(1000, 1000, 1.0)
        self.assertEqual((round(ra), round(rb)), (1012, 988))
        with mock.patch.object(_lote2, "PASTA", Path(tempfile.mkdtemp())), mock.patch("core.gemini.text", lambda p, **k: "Resposta X."):
            self.assertIn("A e B", duelo_ia.run({"action": "duelar", "pergunta": "como vender mais na loja?"}))
            r = duelo_ia.run({"action": "votar", "voto": "a"})
            self.assertIn("Placar em loja", r)
            self.assertIn("loja:", duelo_ia.run({"action": "placar"}))


class TestAutodiagnostico(unittest.TestCase):
    def test_lentos_e_fundo(self):
        from plugins import autodiagnostico
        ch = [{"ferramenta": "lenta", "ms": 9000}] * 3 + [{"ferramenta": "rapida", "ms": 50}] * 5 + [{"ferramenta": "rara", "ms": 99999}]
        self.assertEqual([x[0] for x in autodiagnostico.lentos(ch)], ["lenta", "rapida"])          # 'rara' tem poucas chamadas
        self.assertIn("relógio central", autodiagnostico.run({"action": "fundo"}))


class TestTodasAsAcoes(unittest.TestCase):
    def test_rodar_tudo(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "f.py").write_text("def f(x):\n    return x < 2 and x == 1\n")
        exemplo = {"texto": "amanhã eu mando o orçamento para a Ana", "nome": "Miguel", "responsavel": "Márcia", "idade": "3 anos",
                   "tamanho": "2", "mensagem": "oi futuro", "condicao": "01/01/2027", "projeto": "loja online", "prazo": "4",
                   "numeros": "1", "numero": "1", "arquivo": str(tmp / "f.py"), "linha": "1", "bugs": "1", "pasta": str(tmp),
                   "pergunta": "como vender mais?", "voto": "a", "ano": "2026", "estilo": "trap", "capitulo": "Família"}
        vazio = lambda **k: []  # noqa: E731
        from core import registro_ferramentas
        registro_ferramentas._plugins_reg()
        with mock.patch.object(_lote2, "PASTA", tmp / "dados"), mock.patch("plugins._comum.pasta_jarvis", lambda n: tmp), \
                mock.patch("plugins._comum.abrir_no_sistema", lambda *_: True), mock.patch("core.gemini.as_json", lambda *a, **k: None), \
                mock.patch("core.gemini.text", lambda *a, **k: ""), mock.patch("core.registro_uso.chamadas", vazio), \
                mock.patch("core.registro_uso.linhas_registro", vazio), mock.patch("core.registro_ferramentas.executar", lambda *a, **k: "ok"):
            falhas = []
            for nome in NOVOS:
                mod = importlib.import_module(f"plugins.{nome}")
                self.assertEqual(mod.PLUGIN["tier"], "extra", nome)
                self.assertLessEqual(len(mod.PLUGIN["brief"]), 190, nome)
                for a in mod.PLUGIN["parameters"]["properties"]["action"]["description"].split(" | "):
                    r = mod.run({**exemplo, "action": a})
                    self.assertIsInstance(r, str, f"{nome}.{a}")
                    if "falhou: " in r:
                        self.assertNotRegex(r, BUG, f"{nome}.{a}: {r}")
                        falhas.append(f"{nome}.{a}: {r}")
                self.assertIn("não existe", mod.run({"action": "xyzw"}), nome)
            print("\n".join(falhas))

    def test_rotinas_de_fundo_usam_o_relogio(self):
        with mock.patch.object(relogio, "_tarefas", {}), mock.patch("threading.Thread.start", lambda self: None):
            antes = threading.active_count()
            for nome in NOVOS + ["sonhos", "sentido_aranha", "eu_do_passado"]:
                mod = importlib.import_module(f"plugins.{nome}")
                if hasattr(mod, "on_session_start"):
                    mod.on_session_start(None)
            self.assertEqual(threading.active_count(), antes)                               # nenhuma thread nova
            self.assertGreaterEqual(len(relogio.tarefas()), 12)


if __name__ == "__main__":
    unittest.main()
