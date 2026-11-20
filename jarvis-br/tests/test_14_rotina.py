"""1.4 — rotina e memória do dia: linha do tempo, quando voltar, reconstrução,
prioridades, radar de anomalias, memória contrafactual e oportunidades.

Tudo puro ou com os arquivos redirecionados para uma pasta temporária.
"""
import json
import tempfile
import time
import unittest
from datetime import date, datetime
from pathlib import Path

import tests  # noqa: F401


class TestLinhaDoTempo(unittest.TestCase):
    def test_classificar(self):
        from plugins import linha_do_tempo as lt
        regras = {"Cristal Malhas": ["cristal", "malhas"]}
        self.assertEqual(lt.classificar("Code.exe", "main.py - jarvis-br - Visual Studio Code", regras),
                         ("VS Code", "VS Code", "jarvis-br"))
        self.assertEqual(lt.classificar("chrome.exe", "Lofi - YouTube - Google Chrome", regras)[1], "YouTube")
        self.assertEqual(lt.classificar("msedge.exe", "Pedidos | Cristal Malhas", regras)[1], "Cristal Malhas")

    def test_rastreador_ausencia_e_video(self):
        from plugins import linha_do_tempo as lt
        r = lt.Rastreador(regras={})
        t0 = 1_000_000.0
        fechados = []
        for k in range(0, 600, 5):
            f, v = r.passo(t0 + k, "Code.exe", "a.py - proj - Visual Studio Code", 1)
            fechados += f
        for k in range(600, 1800, 5):             # vídeo sem mexer no mouse: NÃO é ausência
            f, v = r.passo(t0 + k, "chrome.exe", "Aula - YouTube", 900)
            fechados += f
            self.assertIsNone(v)
        for k in range(1800, 5800, 30):           # tela bloqueada: ausência
            f, v = r.passo(t0 + k, "LockApp.exe", "", 50)
            fechados += f
        f, v = r.passo(t0 + 5800, "Code.exe", "a.py - proj - Visual Studio Code", 0)
        fechados += f
        self.assertGreater(v, 3900)
        res = lt.resumo(0, None, fechados)
        self.assertAlmostEqual(dict(res["atividades"])["YouTube"], 1200, delta=10)
        self.assertAlmostEqual(res["ausente_s"], 4000, delta=40)
        self.assertEqual(lt.frase(res), "20 min no YouTube e 10 min no VS Code")

    def test_periodos(self):
        from plugins import linha_do_tempo as lt
        agora = datetime(2026, 10, 29, 15, 0)       # quinta
        ini, _fim, rot = lt.periodo("semana", agora)
        self.assertEqual(datetime.fromtimestamp(ini).date(), date(2026, 10, 26))
        self.assertEqual(rot, "nesta semana")
        self.assertEqual(lt.dur(4 * 3600 + 120), "4h02")


class TestQuandoVoltar(unittest.TestCase):
    def test_frases(self):
        from plugins import quando_voltar as qv
        f = {"downloads": ["a.zip", "b.pdf"], "internet_min": 3, "quedas": 1,
             "seguranca": ["Aparelho novo na rede: 192.168.0.9"], "alertas": [], "agendadas": [],
             "anomalias": [], "celular": 0, "vigias": []}
        self.assertEqual(qv.frases(f), ["um aparelho novo entrou na rede", "2 downloads terminaram",
                                        "a internet caiu 3 minutos"])


class TestReconstrucao(unittest.TestCase):
    def test_periodo(self):
        from plugins import reconstrucao as rc
        agora = datetime(2026, 10, 31, 16, 30)
        ini, fim, rot = rc.periodo("ontem à tarde", agora)
        self.assertEqual((ini.day, ini.hour, fim.hour), (30, 12, 18))
        ini, fim, _ = rc.periodo("hoje às 15h", agora)
        self.assertEqual((ini.hour, ini.minute, fim.hour, fim.minute), (14, 20, 15, 20))
        ini, fim, _ = rc.periodo("das 14h às 16h", agora)
        self.assertEqual((ini.hour, fim.hour), (14, 16))
        self.assertEqual(rc.periodo("última hora", agora)[2], "última hora")

    def test_hipoteses(self):
        from plugins import reconstrucao as rc
        itens = [{"ts": 1000, "fonte": "monitor/amostra", "texto": "internet fora por 3 min", "ok": False},
                 {"ts": 1100, "fonte": "ferramenta", "texto": "web_search → FALHOU (12.0 s)", "ok": False}]
        h = rc.hipoteses(itens)
        self.assertTrue(any("internet" in x for x in h))


class TestPrioridades(unittest.TestCase):
    def test_prazo(self):
        from plugins.prioridades import _prazo
        agora = datetime(2026, 10, 31, 16, 30)      # sábado
        self.assertEqual(_prazo("amanhã 18h", agora), "2026-11-01T18:00")
        self.assertEqual(_prazo("sexta", agora), "2026-11-06T23:59")
        self.assertEqual(_prazo("20/11 às 9h", agora), "2026-11-20T09:00")
        self.assertEqual(_prazo("", agora), "")

    def test_ranking_respeita_bloqueio_dependencia_e_tempo(self):
        from plugins import prioridades as pr
        agora = datetime(2026, 10, 31, 10, 0)
        criada = "2026-10-30T10:00"
        d = {"fator": 1.0, "tarefas": [
            {"id": "1", "titulo": "clientes", "importancia": 5, "urgencia": 3, "prazo": "2026-10-31T18:00",
             "duracao_min": 20, "depende_de": [], "recurso": "", "status": "pendente", "criada": criada},
            {"id": "2", "titulo": "deploy", "importancia": 4, "urgencia": 4, "prazo": "", "duracao_min": 60,
             "depende_de": [], "recurso": "internet", "status": "pendente", "criada": criada},
            {"id": "3", "titulo": "testar deploy", "importancia": 3, "urgencia": 3, "prazo": "", "duracao_min": 15,
             "depende_de": ["2"], "recurso": "", "status": "pendente", "criada": criada},
            {"id": "4", "titulo": "fotos", "importancia": 2, "urgencia": 2, "prazo": "", "duracao_min": 90,
             "depende_de": [], "recurso": "", "status": "bloqueada", "motivo_bloqueio": "câmera", "criada": criada}]}
        podem, nao = pr.ranking(d, agora, {"minutos": None, "internet": True})
        self.assertEqual(podem[0][1]["titulo"], "clientes")
        self.assertEqual({t["titulo"] for _n, t, _m in nao}, {"testar deploy", "fotos"})
        podem, nao = pr.ranking(d, agora, {"minutos": 30, "internet": False})
        self.assertEqual([t["titulo"] for _n, t, _m in podem], ["clientes"])

    def test_aprende_estimativa(self):
        from plugins.prioridades import aprender_fator
        d = {"fator": 1.0}
        aprender_fator(d, 20, 40)
        self.assertAlmostEqual(d["fator"], 1.3, places=3)


class TestRadar(unittest.TestCase):
    def test_ferramenta_lenta_e_falhando(self):
        from plugins import radar_anomalias as ra
        agora = time.time()
        hist = [{"ts": agora - 86400 - i * 600, "ferramenta": "briefing_br", "ms": 800 + (i % 5) * 10, "ok": 1}
                for i in range(20)]
        hist += [{"ts": agora - 86400 - i * 600, "ferramenta": "downloads", "ms": 300, "ok": 1} for i in range(10)]
        base = ra.linha_base_ferramentas(hist, agora - 3600)
        recentes = [{"ts": agora - 600 + i, "ferramenta": "briefing_br", "ms": 5000, "ok": 1} for i in range(3)]
        recentes += [{"ts": agora - 500 + i, "ferramenta": "downloads", "ms": 50, "ok": 0, "resumo": "erro"} for i in range(3)]
        tipos = {a["tipo"] for a in ra.anomalias_ferramentas(base, recentes)}
        self.assertEqual(tipos, {"ferramenta lenta", "ferramenta falhando"})

    def test_vazamento_e_perfil_por_hora(self):
        from plugins import radar_anomalias as ra
        subindo = [{"ts": i * 600.0, "rss_mb": 300 + i * 60} for i in range(13)]
        self.assertIsNotNone(ra.vazamento(subindo))
        estavel = [{"ts": i * 600.0, "rss_mb": 600 + (i % 2) * 5} for i in range(13)]
        self.assertIsNone(ra.vazamento(estavel))
        agora = time.time()
        amostras = [{"ts": agora - d * 86400 - m * 60, "cpu": 20, "ram": 50} for d in range(1, 8) for m in range(30)]
        perfil = ra.perfil_por_hora(amostras)
        recentes = [{"ts": agora - m * 60, "cpu": 95, "ram": 52} for m in range(10, 0, -1)]
        achou = ra.anomalia_hora(perfil, recentes)
        self.assertTrue(achou and achou[0]["chave"] == "hora:cpu")


class TestContrafactual(unittest.TestCase):
    def test_paralelo_e_troca_de_parametro(self):
        from plugins import memoria_contrafactual as mc
        passos = [{"descricao": "fechar steam", "tipo": "fechar", "ms": 2500, "ok": True},
                  {"descricao": "abrir code", "tipo": "abrir", "ms": 4200, "ok": True},
                  {"descricao": "abrir spotify", "tipo": "abrir", "ms": 3800, "ok": True},
                  {"descricao": "mensagem oi", "tipo": "mensagem", "ms": 10, "ok": True}]
        self.assertEqual(mc.tempo_paralelo(passos), (10.51, 4.21))
        l = mc.licoes_de_tarefas([{"tipo": "protocolo", "nome": "trabalho", "passos": passos}])
        self.assertEqual(l[0]["tipo"], "paralelizar")
        cham = [{"ts": 10, "ferramenta": "controle_pc", "acao": "abrir", "params": json.dumps({"alvo": "vscode"}), "ok": 0},
                {"ts": 30, "ferramenta": "controle_pc", "acao": "abrir", "params": json.dumps({"alvo": "Visual Studio Code"}), "ok": 1}]
        l = mc.licoes_de_chamadas(cham)
        self.assertEqual((l[0]["antes"], l[0]["depois"], l[0].get("aplicavel")), ("vscode", "Visual Studio Code", "apelido"))


class TestOportunidades(unittest.TestCase):
    def test_mesmo_pedido_mesma_hora(self):
        from plugins import oportunidades as op
        cham = []
        for d in range(5):
            dia = datetime(2026, 10, 19 + d, 8, 40 + d)          # segunda a sexta
            cham.append({"ts": dia.timestamp(), "ferramenta": "controle_pc", "acao": "abrir", "ok": 1,
                         "params": json.dumps({"alvo": "vs code"})})
        r = op.pedidos_no_mesmo_horario(cham)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["hora"], r[0]["dias_semana"]), ("08:42", [0, 1, 2, 3, 4]))

    def test_aceitar_e_recusar(self):
        from plugins import oportunidades as op
        with tempfile.TemporaryDirectory() as tmp:
            antigo, op._ARQ = op._ARQ, Path(tmp) / "op.json"
            try:
                op._ARQ.write_text(json.dumps({"sugestoes": [{"id": "1", "chave": "x", "tipo": "desconhecido",
                                                              "texto": "t", "status": "nova", "dados": {}}],
                                               "recusadas": [], "proximo_id": 2}))
                self.assertIn("não sugiro", op.recusar("1"))
                self.assertIn("x", op._estado()["recusadas"])
            finally:
                op._ARQ = antigo


if __name__ == "__main__":
    unittest.main()
