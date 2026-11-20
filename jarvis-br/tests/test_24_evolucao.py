"""
Testes da 2.4 — estado do mundo, central de avisos, evolução sozinho, memória
em grafo com rede neural, missões, estúdio de rap, cápsula com áudio, diário
e segurança adaptativa. Nada usa microfone, internet ou os seus dados.
"""
import random
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import tests
from core import central_avisos as CA
from core import estado_mundo as EM
from core import evolucao as EV
from core import memoria_grafo as G
from core import microfone as MIC
from core import missoes as MS
from core.rede_neural import RedeNeural, subpalavras, tokenizar


def estado(atividade="livre", fala="normal", falando=False):
    return {"atividade": atividade, "fala": fala, "jarvis_falando": falando}


class TestEstadoMundo(unittest.TestCase):
    H = datetime(2026, 11, 5, 15, 0)

    def test_inferir(self):
        self.assertEqual(EM.inferir(self.H, "RobloxPlayerBeta.exe", "Roblox", 0, set(), jogo="Roblox")["atividade"], "jogando")
        e = EM.inferir(self.H, "Code.exe", "main.py - jarvis", 3, {"code.exe"})
        self.assertEqual((e["atividade"], e["fala"], e["ocupado"]), ("programando", "curto", True))
        self.assertEqual(EM.inferir(self.H, "chrome.exe", "Meet - abc", 0, set())["atividade"], "em_chamada")
        self.assertEqual(EM.inferir(self.H, "chrome.exe", "x", 0, {"obs64.exe"})["atividade"], "live")
        self.assertEqual(EM.inferir(self.H, "CapCut.exe", "CapCut", 0, set())["atividade"], "editando")
        self.assertEqual(EM.inferir(self.H, "chrome.exe", "Vídeo - YouTube", 900, set(), som=True)["atividade"], "assistindo")
        self.assertEqual(EM.inferir(self.H, "explorer.exe", "", 900, set())["fala"], "guardar")
        e = EM.inferir(self.H, "spotify.exe", "Kaiser - Impossível", 5, {"spotify.exe"}, som=True)
        self.assertTrue(e["musica"])
        self.assertEqual(e["periodo"], "tarde")
        self.assertIn("Você está usando o PC", EM.descrever(e))

    def test_permite(self):
        self.assertTrue(EM.permite(estado("jogando", "silencio"), "urgente"))
        self.assertFalse(EM.permite(estado("jogando", "silencio"), "normal"))
        self.assertTrue(EM.permite(estado("programando", "curto"), "normal"))
        self.assertFalse(EM.permite(estado(falando=True), "normal"))
        self.assertFalse(EM.permite(estado(), "baixa"))


class TestCentralAvisos(unittest.TestCase):
    def setUp(self):
        self.falas = []
        CA._estado["falar"] = self.falas.append
        CA._fila.clear()
        CA._resumo.clear()
        CA._estado["atividade_resumo"] = ""

    def tearDown(self):
        CA._estado["falar"] = None

    def test_prioridades(self):
        self.assertEqual(CA.prioridade_de("ALERTA DO SISTEMA", "", "Temperatura crítica na CPU"), "urgente")
        self.assertEqual(CA.prioridade_de("DOWNLOADS"), "baixa")
        self.assertEqual(CA.prioridade_de("PREÇO", "high"), "normal")
        self.assertEqual(CA.prioridade_de("", "urgent"), "urgente")

    def test_jogo_segura_e_resume(self):
        jogando = {"atividade": "jogando", "fala": "silencio", "jarvis_falando": False}
        with mock.patch.object(EM, "agora", lambda forcar=False: jogando):
            self.assertEqual(CA.avisar("A internet caiu na live.", "urgente"), "falado")
            self.assertEqual(CA.avisar("Download concluído: a.zip.", "baixa", "DOWNLOADS"), "resumo")
            self.assertEqual(CA.avisar("Download concluído: b.zip.", "baixa", "DOWNLOADS"), "resumo")
            self.assertEqual(CA.avisar("RAM em 92%.", "normal"), "na_fila")
        self.assertEqual(self.falas, ["A internet caiu na live."])
        self.assertEqual(CA.passo(jogando), [])                               # ainda jogando: nada
        livre = {"atividade": "livre", "fala": "normal", "jarvis_falando": False}
        falados = CA.passo(livre)
        self.assertEqual(falados[0], "RAM em 92%.")
        self.assertEqual(falados[1], "Enquanto você jogava: 2 downloads terminaram.")
        self.assertEqual(CA.pendentes(), {"fila": [], "resumo": []})

    def test_velhos_viram_resumo_e_o_que_perdi(self):
        CA._fila.append({"texto": "Preço caiu.", "etiqueta": "PREÇO", "ts": 0, "prioridade": "normal"})
        CA.passo({"atividade": "live", "fala": "silencio", "jarvis_falando": False}, agora=3 * 3600)
        self.assertEqual(len(CA._resumo), 1)
        CA._estado["atividade_resumo"] = "live"
        self.assertEqual(CA.o_que_perdi(), "Durante a live: Preço caiu.")
        self.assertIn("Nada guardado", CA.o_que_perdi())

    def test_resumo_texto(self):
        itens = [{"texto": "Download concluído: x", "etiqueta": "DOWNLOADS"},
                 {"texto": "RAM em 95%", "etiqueta": "ALERTA"}]
        self.assertEqual(CA.montar_resumo(itens, "jogando"),
                         "Enquanto você jogava: 1 download terminou e 1 alerta de RAM.")


class TestEvolucao(unittest.TestCase):
    def setUp(self):
        self._arq = EV.ARQ
        EV.ARQ = tests.TMP / "evolucao_t.json"
        EV.zerar()

    def tearDown(self):
        EV.ARQ = self._arq

    def test_sinais(self):
        self.assertEqual(EV.sinal("repete por favor"), "repetir")
        self.assertEqual(EV.sinal("o quê?"), "repetir")
        self.assertEqual(EV.sinal("Não, não foi isso que eu pedi"), "corrigir")
        self.assertEqual(EV.sinal("não"), "")                                 # resposta a uma pergunta
        self.assertEqual(EV.sinal("não, obrigado"), "elogio")
        self.assertEqual(EV.sinal("resume isso"), "mais_curto")
        self.assertEqual(EV.sinal("explica melhor"), "mais_longo")
        self.assertEqual(EV.sinal("valeu jarvis"), "elogio")
        self.assertEqual(EV.sinal("liga a luz da sala"), "")

    def test_recompensas(self):
        atual = {"tamanho": "completa", "tom": "formal", "ordem": "passos_antes"}
        self.assertEqual(EV.recompensas("", atual, interrompido=True)["tamanho"], (0.0, 1.0))
        self.assertEqual(EV.recompensas("mais_curto", atual), {"tamanho": (0.0, 1.0)})
        self.assertEqual(EV.recompensas("corrigir", atual)["tom"], (0.0, 1.0))
        self.assertEqual(EV.recompensas("", atual)["ordem"], (1.0, 0.3))

    def test_selecao_natural(self):
        """Simula um usuário que sempre corta respostas longas: a curta tem que vencer."""
        rng = random.Random(3)
        placar = {}
        usos = {"curta": 0, "completa": 0}
        for _ in range(300):
            atual = EV.sortear(placar, rng)
            usos[atual["tamanho"]] += 1
            longa = atual["tamanho"] == "completa"
            EV.aplicar(placar, atual, EV.recompensas("", atual, interrompido=longa and rng.random() < 0.7))
        self.assertEqual(EV.melhores(placar)["tamanho"], "curta")
        self.assertGreater(usos["curta"], usos["completa"] * 2)

    def test_turnos_e_instrucao(self):
        atual = EV.combinacao_atual()
        self.assertEqual(set(atual), set(EV.DIMENSOES))
        self.assertIn("[ESTILO DESTA CONVERSA]", EV.instrucao())
        EV.turno("que horas são?", "São três horas.")
        EV.turno("valeu", "De nada.")
        p = EV.dados()["placar"]
        self.assertTrue(all(p[d][atual[d]]["a"] > 1.5 for d in atual))
        self.assertIn("Fixado: respostas curtas", EV.fixar("curta"))
        self.assertEqual(EV.combinacao_atual()["tamanho"], "curta")
        self.assertIn("ainda testando", EV.relatorio())


class TestRedeNeural(unittest.TestCase):
    def test_subpalavras_e_tokens(self):
        self.assertEqual(tokenizar("Eu decidi usar o ESP32 no capacete!"), ["decidi", "usar", "esp32", "capacete"])
        self.assertIn("<de", subpalavras("decidi"))
        self.assertIn("cidi", subpalavras("decidi"))

    def test_aprende_vizinhas(self):
        frases = [tokenizar(t) for t in ["capacete esp32 placa led", "capacete led azul olhos", "esp32 placa camera wifi",
                                         "loja roupa infantil venda", "loja venda cliente roupa"]] * 6
        r = RedeNeural(dim=24, baldes=4096)
        self.assertGreater(r.treinar(frases, epocas=25), 1000)
        viz = [w for w, _s in r.parecidas("capacete", 4)]
        self.assertTrue({"led", "esp32", "placa"} & set(viz))
        self.assertFalse({"cliente", "infantil"} & set(viz[:2]))
        arq = tests.TMP / "rede_t.npz"
        r.salvar(arq)
        r2 = RedeNeural.carregar(arq)
        self.assertEqual(r2.vocab, r.vocab)


class TestMemoriaGrafo(unittest.TestCase):
    def setUp(self):
        self._a = (G.ARQ, G.ARQ_REDE)
        G.ARQ = tests.TMP / f"grafo_{self.id()}.db"
        G.ARQ_REDE = tests.TMP / f"rede_{self.id()}.npz"
        G._rede.update(r=None, arq=None)
        self.p = mock.patch("plugins._ia.disponivel", lambda: False)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        G.ARQ, G.ARQ_REDE = self._a

    def test_extrair_e_buscar(self):
        ents = G.extrair_local("Combinei com a Ana de gravar o vídeo da Cristal Malhas no sábado.")
        self.assertIn(("Ana", "pessoa"), ents)
        self.assertIn("Cristal Malhas", [n for n, _t in ents])
        textos = ["Decidi usar o ESP32-S3 no capacete do Mark porque tem câmera e Wi-Fi.",
                  "O capacete vai ter LED azul nos olhos.",
                  "Combinei com a Ana de gravar o vídeo da Cristal Malhas no sábado.",
                  "Escolhi a placa ESP32-S3 porque a comum esquentava com a câmera.",
                  "O projeto Gravyz usa Flask no servidor."]
        for i, t in enumerate(textos):
            G.lembrar(t, ts=1_700_000_000 + i * 86400)
        self.assertTrue(G.lembrar(textos[0]).get("repetida"))
        self.assertGreater(G.ligar_assuntos(), 0)                           # 'capacete', 'esp32' viram assunto
        r = G.buscar("o que eu decidi sobre o capacete?", 3)
        self.assertIn("ESP32-S3 no capacete", r[0]["texto"])
        r = G.buscar("qual placa eu escolhi", 2)
        self.assertIn("placa", r[0]["texto"])
        c = G.conexoes("Cristal Malhas")
        self.assertEqual(c["fatos"][0]["texto"], textos[2])
        self.assertIn("Ana", [x["nome"] for x in c["ligados"]])
        self.assertEqual(G.buscar("capacete", 5, desde=1_700_000_000 + 86400, ate=1_700_000_000 + 2 * 86400)[0]["texto"],
                         textos[1])                                           # janela de tempo (diário)
        g = G.grafo_json()
        self.assertTrue(g["nos"] and g["arestas"])

    def test_rede_e_significado(self):
        base = ["Decidi usar o ESP32-S3 no capacete por causa do Wi-Fi", "O capacete vai ter LED azul e ventilador",
                "A placa ESP32-S3 esquentava menos que a comum", "O LED do capacete pisca quando o Jarvis fala",
                "A Cristal Malhas vende roupa infantil", "A loja Cristal Malhas faz vídeo de produto toda semana"]
        for i, t in enumerate(base * 3):
            G.lembrar(f"{t} ({i})", ts=1_700_000_000 + i)
        self.assertIn("Rede treinada", G.treinar_rede(epocas=8))
        self.assertIsNotNone(G.rede())
        e = G.estatisticas()
        self.assertEqual(e["vetores"]["local"], 18)
        r = G.buscar("o que vai ter no LED do capacete", 3)
        self.assertTrue(all("capacete" in x["texto"] or "LED" in x["texto"] for x in r[:2]))

    def test_gemini_quando_ha_chave(self):
        def falso(textos):
            return "gemini-embedding-001", [[1.0, 0.0] if "capacete" in t or "Mark" in t else [0.0, 1.0] for t in textos]
        with mock.patch.object(G, "embed_gemini", falso):
            G.lembrar("Escolhi o ESP32 para o Mark", ts=1)
            G.lembrar("A loja vende roupa infantil", ts=2)
            r = G.buscar("e o capacete?", 1)
        self.assertEqual(r[0]["texto"], "Escolhi o ESP32 para o Mark")             # sem nenhuma palavra em comum


class TestMissoes(unittest.TestCase):
    def setUp(self):
        self._a = (MS.ARQ, MS.PASTA_LISTAS)
        MS.ARQ = tests.TMP / f"missoes_{self.id()}.json"
        MS.PASTA_LISTAS = tests.TMP / f"listas_{self.id()}"
        self.avisos = []
        MS._avisar["fn"] = self.avisos.append

    def tearDown(self):
        MS._avisar["fn"] = None
        MS.ARQ, MS.PASTA_LISTAS = self._a

    def esperar(self, mid, estados=("concluida", "erro", "cancelada", "pausada")):
        for _ in range(100):
            if MS.obter(mid)["estado"] in estados:
                return MS.obter(mid)
            time.sleep(0.05)
        return MS.obter(mid)

    def test_puras(self):
        self.assertEqual(MS.destino_foto(Path("R"), datetime(2024, 3, 9), "a.jpg"), Path("R/2024/03 - Março/a.jpg"))
        foto = tests.TMP / "IMG_20230105_101010.jpg"
        foto.write_bytes(b"x")
        self.assertEqual(MS.data_da_foto(foto), datetime(2023, 1, 5))
        a = MS.args_ffmpeg("ff", "a.mov", "b.mp4")
        self.assertIn("veryfast", a)
        self.assertEqual(a[-1], "b.mp4")

    def test_fotos_copiar_e_retomar(self):
        pasta = tests.TMP / f"fotos_{self.id()}"
        pasta.mkdir()
        for n in ("IMG_20240131_1.jpg", "IMG-20231225-WA1.jpg", "foto.png"):
            (pasta / n).write_bytes(b"x")
        m = MS.criar("organizar_fotos", {"pasta": str(pasta), "modo": "copiar"})
        m = self.esperar(m["id"])
        self.assertEqual(m["estado"], "concluida")
        self.assertTrue((pasta / "Organizadas" / "2024" / "01 - Janeiro" / "IMG_20240131_1.jpg").exists())
        self.assertTrue((pasta / "IMG_20240131_1.jpg").exists())                 # copiar: o original fica
        self.assertIn("concluída", self.avisos[0])
        # missão "rodando" no arquivo (o PC desligou no meio): retomar continua do ponto salvo
        lista = MS._todas()
        lista[0].update(estado="rodando", checkpoint={"i": 2})
        MS._gravar(lista)
        self.assertEqual(MS.retomar(), 1)
        self.assertEqual(self.esperar(m["id"])["feito"], 3)

    def test_mover_e_desfazer(self):
        pasta = tests.TMP / f"mover_{self.id()}"
        pasta.mkdir()
        (pasta / "IMG_20220202_1.jpg").write_bytes(b"x")
        m = self.esperar(MS.criar("organizar_fotos", {"pasta": str(pasta), "modo": "mover"})["id"])
        self.assertFalse((pasta / "IMG_20220202_1.jpg").exists())
        self.assertIn("Voltei 1", MS.desfazer_fotos(m["id"]))
        self.assertTrue((pasta / "IMG_20220202_1.jpg").exists())
        self.assertFalse((pasta / "Organizadas").exists())

    def test_preco_pausar_cancelar(self):
        precos = iter([100.0, 90.0, 80.0])
        with mock.patch.object(MS, "_consultar_preco", lambda p: next(precos)), \
                mock.patch.object(MS, "proxima_consulta", lambda u, i: u + 0.05):
            m = MS.criar("monitorar_preco", {"produto": "PS5", "dias": 7, "alvo": 85, "intervalo_h": 1})
            for _ in range(60):
                if len(MS.obter(m["id"])["checkpoint"].get("historico", [])) >= 3:
                    break
                time.sleep(0.05)
            self.assertTrue(MS.comando("pausar", m["id"])["ok"])
            self.assertEqual(self.esperar(m["id"], ("pausada",))["estado"], "pausada")
        self.assertTrue(any("caiu para R$ 90.00" in a for a in self.avisos))
        self.assertTrue(any("chegou a R$ 80.00" in a for a in self.avisos))
        self.assertTrue(MS.comando("cancelar", m["id"])["ok"])
        self.assertFalse(MS.comando("pausar", m["id"])["ok"])
        self.assertTrue(MS.comando("apagar", m["id"])["ok"])
        self.assertIsNone(MS.obter(m["id"]))


class TestMicrofoneEstudio(unittest.TestCase):
    def test_reserva(self):
        self.assertFalse(MIC.reservado())
        with MIC.reservado_por("teste", 30):
            self.assertTrue(MIC.reservado())
            self.assertEqual(MIC.motivo(), "teste")
        self.assertFalse(MIC.reservado())

    def test_mixar_e_contagem(self):
        import numpy as np

        from plugins import _som
        from plugins import estudio_rap as ER
        c = ER.contagem(120)
        self.assertEqual(len(c), _som.TAXA * 2)                             # 4 batidas a 120 BPM = 2 s
        beat = np.full(1000, 0.5, "float32")
        voz = np.concatenate([np.zeros(100, "float32"), np.full(1000, 0.2, "float32")])
        mix = ER.mixar(voz, beat, atraso_amostras=100, volume_beat=0.5)
        self.assertEqual(len(mix), 1000)
        self.assertLessEqual(float(np.max(np.abs(mix))), 0.951)
        self.assertIn("incrível", ER.rimas("impossível"))
        _e, bpm, audio = ER._beat("boom bap", 90, 2)
        self.assertEqual(len(audio), int(2 * 16 * (60 / 90 / 4) * _som.TAXA))


class TestDiario(unittest.TestCase):
    def setUp(self):
        from plugins import diario
        self.d = diario
        self._a = diario.ARQ
        diario.ARQ = tests.TMP / f"diario_{self.id()}.json"

    def tearDown(self):
        self.d.ARQ = self._a

    def test_periodo(self):
        hoje = date(2026, 11, 5)
        p = self.d.periodo
        self.assertEqual(p("o que eu estava fazendo em novembro do ano passado?", hoje)[:2],
                         (date(2025, 11, 1), date(2025, 12, 1)))
        self.assertEqual(p("como foi a semana passada", hoje)[:2], (date(2026, 10, 26), date(2026, 11, 2)))
        self.assertEqual(p("dia 12/03", hoje)[0], date(2026, 3, 12))
        self.assertEqual(p("dia 25/12", hoje)[0], date(2025, 12, 25))          # futuro → ano passado
        self.assertEqual(p("em dezembro", hoje)[0], date(2025, 12, 1))
        self.assertEqual(p("ontem", hoje)[0], date(2026, 11, 4))
        self.assertEqual(p("há 2 meses", hoje)[0], date(2026, 9, 1))
        self.assertIsNone(p("como estou?", hoje))
        self.assertTrue(self.d.deve_perguntar(datetime(2026, 11, 5, 22, 0), "21:30", "", ""))
        self.assertFalse(self.d.deve_perguntar(datetime(2026, 11, 5, 21, 0), "21:30", "", ""))
        self.assertFalse(self.d.deve_perguntar(datetime(2026, 11, 5, 22, 0), "21:30", "2026-11-05", ""))

    def test_entrevista(self):
        with mock.patch("plugins._ia.disponivel", lambda: False), mock.patch("core.memoria_grafo.lembrar", lambda *a, **k: {}):
            self.assertIn("[DIÁRIO]", self.d.iniciar_entrevista())
            self.d._ouvir("foi corrido, entreguei o projeto do capacete", "Que bom! E o que foi difícil?", False)
            self.d._ouvir("a loja ficou parada", "", False)
            self.assertIn("Guardei", self.d.encerrar())
            e = self.d.entradas()[-1]
            self.assertIn("projeto do capacete", e["texto"])
            self.d.guardar("Gravei um vídeo novo.", quando=datetime(2025, 11, 20, 22))
            r = self.d.consultar("o que eu estava fazendo em novembro do ano passado?")
        self.assertIn("Gravei um vídeo novo.", r)
        self.assertNotIn("capacete", r)
        self.assertEqual(self.d.encerrar(), "Não ouvi nada para o diário hoje; fica para amanhã.")


class TestSeguranca(unittest.TestCase):
    def setUp(self):
        from plugins import seguranca_adaptativa as S
        self.S = S

    def amostra(self, hora=15, up=5.0, procs=None, escutando=None, entrada=None, maior=""):
        return {"ts": 0, "hora": hora, "up_mb": up, "procs": procs or {}, "escutando": escutando or {},
                "entrada": entrada or [], "maior_rede": maior}

    def test_aprende_e_avisa_upload(self):
        S = self.S
        agora = 30 * 86400
        m = S.novo_modelo(0)
        for _ in range(60):
            S.aprender(m, self.amostra(hora=3, up=2.0))
        self.assertEqual(S.avaliar(m, self.amostra(hora=3, up=3.0), agora), [])
        av = S.avaliar(m, self.amostra(hora=3, up=2150.0, maior="sync.exe"), agora)
        self.assertEqual(av[0]["prioridade"], "urgente")
        self.assertEqual(av[0]["texto"], "Senhor, um programa enviou 2,1 GB pela internet às 3h da manhã. "
                                         "Isso nunca aconteceu antes. (provável: sync.exe)")
        self.assertEqual(len(S.filtrar_repetidos(m, av, agora)), 1)
        self.assertEqual(S.filtrar_repetidos(m, av, agora + 60), [])           # não repete em 6 h
        m["ignorar"].append("upload:3")
        self.assertEqual(S.avaliar(m, self.amostra(hora=3, up=2150.0), agora), [])

    def test_aprendizado_so_grave(self):
        S = self.S
        m = S.novo_modelo(0)
        self.assertEqual(S.avaliar(m, self.amostra(up=300.0), 3600), [])         # 1º dia: 300 MB não assusta
        entrada = [{"ip": "189.10.20.30", "porta": 3389, "proc": "svchost.exe"}]
        av = S.avaliar(m, self.amostra(entrada=entrada), 3600)
        self.assertEqual(av[0]["prioridade"], "urgente")
        self.assertIn("Área de Trabalho Remota", av[0]["texto"])
        self.assertFalse(S.publico("192.168.0.10"))
        self.assertTrue(S.publico("189.10.20.30"))

    def test_programa_novo_e_horario(self):
        S = self.S
        agora = 30 * 86400
        m = S.novo_modelo(0)
        exe = r"c:\users\x\appdata\local\temp\atualizador.exe"
        av = S.avaliar(m, self.amostra(procs={exe: {"nome": "atualizador.exe", "rede": True}}), agora)
        self.assertIn("nunca vi (atualizador.exe, em temp)", av[0]["texto"])
        obs = r"c:\program files\obs\obs64.exe"
        for _ in range(25):
            S.aprender(m, self.amostra(hora=20, procs={obs: {"nome": "obs64.exe"}}))
        av = S.avaliar(m, self.amostra(hora=4, procs={obs: {"nome": "obs64.exe", "na_frente": True}}), agora)
        self.assertEqual(av, [{"chave": f"hora:{obs}:4", "prioridade": "baixa",
                               "texto": "obs64.exe abriu às 4h; você nunca usa ele nesse horário."}])


if __name__ == "__main__":
    unittest.main()
