"""Biological Core (3.1) — DNA, detecção, isolamento, defesa, memória imunológica, prevenção, anomalias e evolução."""
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import tests  # noqa: F401
from tests.bio_comum import ERRO_REDE, organismo, projeto

from biological_core.autorizacao import Autorizacoes
from biological_core.config import ESSENCIAIS
from biological_core.dna.digital_dna import DNA, classe_de, listar_arquivos
from biological_core.dna.integrity_checker import BancoCelulasTronco, VerificadorIntegridade
from biological_core.immune_system.anomaly_detector import DetectorAnomalias, tendencia
from biological_core.immune_system.defense_engine import BLOQUEAR, CONFIRMAR, PERMITIR, MotorDefesa
from biological_core.immune_system.immune_memory import MemoriaImune, impressao_digital, normalizar_mensagem
from biological_core.immune_system.isolation_manager import GerenciadorIsolamento
from biological_core.immune_system.prevention_engine import Prevencao
from biological_core.immune_system.threat_detector import DetectorAmeacas, classificar_por_regras, gravidade, sintoma


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jarvis_bio_"))
        self.raiz = projeto(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestDNA(Base):
    def test_arquivos_e_classes(self):
        arqs = listar_arquivos(self.raiz)
        self.assertIn("plugins/bioteste_clima.py", arqs)
        self.assertNotIn("memory/lista.json", arqs)                     # dados não são DNA
        self.assertNotIn("config/app.json", arqs)
        self.assertEqual(classe_de("biological_core/config.py"), "vital")
        self.assertEqual(classe_de("core/vigia.py"), "vital")
        self.assertEqual(classe_de("plugins/x.py"), "plugin")
        self.assertEqual(classe_de("core/tts.py"), "nucleo")

    def test_deteccao_de_arquivo_modificado(self):
        dna = DNA(self.raiz, self.tmp / "bio")
        dna.genese()
        ver = VerificadorIntegridade(dna)
        self.assertEqual(ver.verificar()["integridade"], 100.0)
        (self.raiz / "plugins" / "bioteste_clima.py").write_text("# mexeram\n", encoding="utf-8")
        (self.raiz / "biological_core" / "config.py").write_text("X = 2\n", encoding="utf-8")
        (self.raiz / "plugins" / "novo.py").write_text("PLUGIN = {}\n", encoding="utf-8")
        r = ver.verificar()
        self.assertEqual(sorted(r["modificados"]), ["biological_core/config.py", "plugins/bioteste_clima.py"])
        self.assertEqual(r["novos"], ["plugins/novo.py"])
        sint = {s["acao"]: s for s in ver.sintomas(r)}
        self.assertEqual(sint["modificado_vital"]["gravidade"], "critica")
        self.assertTrue(sint["modificado_vital"]["ameaca"])
        self.assertEqual(sint["modificado_plugin"]["gravidade"], "baixa")
        self.assertEqual(sint["novo_plugin"]["gravidade"], "baixa")

    def test_genoma_adulterado_e_mutacao_so_com_autorizacao(self):
        dna = DNA(self.raiz, self.tmp / "bio")
        dna.genese()
        aut = Autorizacoes(self.tmp / "bio" / "aut.json")
        self.assertTrue(dna.mutar(None, aut, "sem ficha").startswith("Recusado"))
        self.assertTrue(dna.mutar("inventada", aut, "ficha falsa").startswith("Recusado"))
        p = aut.pedir("dna_mutar", "Atualizar DNA", "teste", lambda ficha: dna.mutar(ficha, aut, "autorizado"), alvo="tudo")
        self.assertEqual(p["tela"], "sem_tela")                          # sem HUD nos testes
        self.assertTrue(aut.conceder(p["id"]).startswith("DNA atualizado"))
        g = json.loads(dna.arquivo.read_text(encoding="utf-8"))
        g["arquivos"]["plugins/bioteste_clima.py"]["sha256"] = "0" * 64  # alguém editou o genoma na mão
        dna.arquivo.write_text(json.dumps(g), encoding="utf-8")
        self.assertEqual(DNA(self.raiz, self.tmp / "bio").carregar(), "adulterado")

    def test_versao_nova_vira_um_aviso_so(self):
        dna = DNA(self.raiz, self.tmp / "bio")
        dna.genese()
        for i in range(25):
            (self.raiz / "plugins" / f"p{i}.py").write_text("x = 1\n", encoding="utf-8")
        (self.raiz / "ui.py").write_text('APP_VERSION  = "J.A.R.V.I.S BR 3.2"\n', encoding="utf-8")
        s = VerificadorIntegridade(dna).sintomas()
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["acao"], "versao_nova")

    def test_celulas_tronco_restauram_com_conferencia(self):
        dna = DNA(self.raiz, self.tmp / "bio")
        dna.genese()
        banco = BancoCelulasTronco(self.tmp / "bio" / "ct.zip", self.raiz)
        banco.criar(list(dna.genoma["arquivos"]))
        alvo = self.raiz / "plugins" / "bioteste_clima.py"
        original = alvo.read_text(encoding="utf-8")
        alvo.write_text("def quebrado(:\n", encoding="utf-8")
        aut = Autorizacoes(self.tmp / "bio" / "aut.json")
        ok, msg = banco.restaurar("plugins/bioteste_clima.py", None, aut, dna.genoma)
        self.assertFalse(ok)
        ficha = aut._emitir("restaurar_codigo:plugins/bioteste_clima.py")
        ok, msg = banco.restaurar("plugins/bioteste_clima.py", ficha, aut, dna.genoma)
        self.assertTrue(ok, msg)
        self.assertEqual(alvo.read_text(encoding="utf-8"), original)
        self.assertTrue(any(".mutante-" in p.name for p in alvo.parent.iterdir()))   # o quebrado não foi apagado
        self.assertFalse(aut.validar(ficha, "restaurar_codigo:plugins/bioteste_clima.py"))   # ficha é de uso único


class TestDeteccao(Base):
    def test_dependencias_ausentes(self):
        d = DetectorAmeacas(self.raiz).dependencias_ausentes(["json", "pacote_que_nao_existe_xyz", "outro_falso_abc"],
                                                             essenciais=("outro_falso_abc",))
        self.assertEqual(d["essenciais"], ["outro_falso_abc"])
        self.assertEqual(d["opcionais"], ["pacote_que_nao_existe_xyz"])

    def test_modulos_indisponiveis(self):
        class Registro:
            def list_for_ui(self):
                return [{"name": "quebrado", "valid": False, "error": "No module named 'cv2'"},
                        {"name": "bom", "valid": True, "error": ""}]
        s = DetectorAmeacas(self.raiz).plugins_quebrados(Registro())
        self.assertEqual([(x["modulo"], x["categoria"]) for x in s], [("quebrado", "pacote")])

    def test_classificacao_e_gravidade(self):
        self.assertEqual(classificar_por_regras("JSONDecodeError", "Expecting value"), "json_corrompido")
        self.assertEqual(classificar_por_regras("ConnectionError", ERRO_REDE), "rede")
        self.assertEqual(classificar_por_regras("", "No module named 'cv2'"), "pacote")
        self.assertIsNone(classificar_por_regras("KeyError", "'x'"))
        self.assertEqual(gravidade("rede", "clima"), "baixa")
        self.assertEqual(gravidade("rede", "clima", 12), "media")
        self.assertEqual(gravidade("rede", sorted(ESSENCIAIS)[0]), "media")

    def test_sintoma_tem_arquivo_e_linha_do_projeto(self):
        try:
            {}["x"]
        except KeyError as e:
            s = sintoma("plug", "acao", erro=e, raiz=Path(tests.RAIZ))
        self.assertEqual(s["tipo"], "KeyError")
        self.assertEqual(s["arquivo"], "tests/test_50_bio_immune.py")
        self.assertGreater(s["linha"], 0)


class TestIsolamento(Base):
    def setUp(self):
        super().setUp()
        self.t = [1000.0]
        self.g = GerenciadorIsolamento(self.tmp / "q.json", essenciais={"organismo"}, agora=lambda: self.t[0])

    def test_disjuntor_isola_testa_e_cura(self):
        self.assertFalse(self.g.falha("clima", "agora", "erro"))
        self.assertFalse(self.g.falha("clima", "agora", "erro"))
        self.assertTrue(self.g.falha("clima", "agora", "erro"))           # 3ª seguida: abre
        self.assertIn("[DESCANSANDO]", self.g.bloqueio("clima", "agora"))
        self.assertIsNone(self.g.bloqueio("clima", "semana"))            # só o pedaço doente
        self.t[0] += 61
        self.assertIsNone(self.g.bloqueio("clima", "agora"))             # chamada de teste
        self.assertIn("[TESTANDO]", self.g.bloqueio("clima", "agora"))   # só uma por vez
        self.assertTrue(self.g.falha("clima", "agora", "erro"))           # teste falhou: abre de novo
        d = self.g.disjuntores["clima|agora"]
        self.assertEqual(d["aberto_ate"] - self.t[0], 300)               # descanso maior
        self.t[0] += 301
        self.assertIsNone(self.g.bloqueio("clima", "agora"))
        self.assertTrue(self.g.sucesso("clima", "agora"))                 # curou
        self.assertIsNone(self.g.bloqueio("clima", "agora"))

    def test_essenciais_nunca_sao_isolados(self):
        for _ in range(5):
            self.assertFalse(self.g.falha("organismo", "saude", "erro"))
        self.assertFalse(self.g.isolar("organismo", None, "teste"))
        self.assertIsNone(self.g.bloqueio("organismo", "saude"))

    def test_quarentena_liberar_e_alarme_falso(self):
        self.assertTrue(self.g.isolar("rastreio", None, "ameaça"))
        self.assertIn("[ISOLADO]", self.g.bloqueio("rastreio", "qualquer"))
        self.t[0] += 30
        self.assertEqual(self.g.liberar("rastreio"), ["rastreio|*"])
        self.assertEqual(self.g.alarmes_falsos("rastreio"), 1)
        self.assertEqual(self.g.ajustar_limiar("rastreio", alarme_falso=True), 4)
        g2 = GerenciadorIsolamento(self.tmp / "q.json", essenciais=set(), agora=lambda: self.t[0])
        self.assertEqual(g2.limiares["rastreio"], 4)                      # salvo em disco

    def test_falhas_espalhadas_nao_contam_como_seguidas(self):
        self.g.falha("clima", "agora", "erro")
        self.g.falha("clima", "agora", "erro")
        self.t[0] += 3600
        self.assertFalse(self.g.falha("clima", "agora", "erro"))


class TestDefesa(unittest.TestCase):
    def setUp(self):
        self.d = MotorDefesa(rajada_por_min=5)

    def test_protecao_contra_operacoes_nao_autorizadas(self):
        casos = [("executar_comando", {"comando": "powershell Set-MpPreference -DisableRealtimeMonitoring $true"}, BLOQUEAR),
                 ("terminal", {"comando": "netsh advfirewall set allprofiles state off"}, BLOQUEAR),
                 ("controle_pc", {"action": "desativar", "alvo": "antivírus"}, BLOQUEAR),
                 ("terminal", {"comando": "format C: /q"}, BLOQUEAR),
                 ("terminal", {"comando": "rm -rf /"}, BLOQUEAR),
                 ("organizar_arquivos", {"action": "apagar", "caminho": "memory/biological/genoma.json"}, BLOQUEAR),
                 ("organizar_arquivos", {"action": "apagar", "caminho": r"C:\Windows\System32\drivers"}, CONFIRMAR),
                 ("busca_web", {"consulta": "como desativar o firewall do windows"}, PERMITIR),
                 ("abrir_arquivo", {"caminho": "biological_core/config.py"}, PERMITIR),
                 ("clima", {"action": "agora", "cidade": "Goiânia"}, PERMITIR)]
        for nome, params, esperado in casos:
            self.assertEqual(self.d.validar(nome, params).acao, esperado, (nome, params))

    def test_anti_laco(self):
        for _ in range(5):
            self.assertEqual(self.d.validar("piada", {"action": "contar"}).acao, PERMITIR)
        v = self.d.validar("piada", {"action": "contar"})
        self.assertEqual((v.acao, v.regra), (BLOQUEAR, "anti_laco"))
        self.assertEqual(self.d.validar("outra", {}).acao, PERMITIR)

    def test_modulo_comprometido_pede_confirmacao(self):
        self.assertEqual(self.d.validar("arquivos", {"action": "apagar", "nome": "x.txt"}, "comprometido").acao, CONFIRMAR)
        self.assertEqual(self.d.validar("arquivos", {"action": "listar"}, "comprometido").acao, PERMITIR)


class TestMemoriaImune(Base):
    def setUp(self):
        super().setUp()
        self.m = MemoriaImune(self.tmp / "imunidade.db")

    def tearDown(self):
        self.m.fechar_conexao()
        super().tearDown()

    def test_impressao_ignora_o_que_varia(self):
        a = normalizar_mensagem("Falhou em C:\\Users\\Ana\\x.json linha 12 às 10:31")
        b = normalizar_mensagem("Falhou em C:\\Users\\Bia\\y.json linha 99 às 23:05")
        self.assertEqual(a, b)
        self.assertEqual(impressao_digital("m", "a", "E", "erro 404 em /api/1"), impressao_digital("m", "a", "E", "erro 500 em /api/77"))
        self.assertNotEqual(impressao_digital("m", "a", "E", "x"), impressao_digital("outro", "a", "E", "x"))

    def test_registro_de_incidentes(self):
        i1, novo = self.m.abrir_incidente("clima", "agora", "rede", "baixa", "imp1", "sem rede")
        self.assertTrue(novo)
        i2, novo2 = self.m.abrir_incidente("clima", "agora", "rede", "baixa", "imp1", "sem rede")
        self.assertEqual((i2, novo2), (i1, False))
        self.assertEqual(self.m.incidente(i1)["ocorrencias"], 2)
        self.m.fechar(i1, "curado", causa="internet_caiu", tratamento="esperar_rede")
        self.assertEqual(self.m.abertos(), [])
        i3, novo3 = self.m.abrir_incidente("clima", "agora", "rede", "baixa", "imp1", "sem rede de novo")
        self.assertTrue(novo3 and i3 != i1)                               # fechado não recebe ocorrência nova
        self.assertEqual(self.m.causas_por_modulo("clima")["internet_caiu"], 1)

    def test_anticorpos_lembram_o_que_funciona_e_o_que_falhou(self):
        self.m.registrar_anticorpo("imp", "rede", "clima")
        self.m.registrar_tratamento("imp", "observar", False)
        self.m.registrar_tratamento("imp", "observar", False)
        self.m.registrar_tratamento("imp", "esperar_rede", True)
        a = self.m.reconhecer("imp")
        self.assertEqual(a["tratamento_bom"], "esperar_rede")
        self.assertEqual(self.m.tratamentos_que_falharam("imp"), {"observar"})
        self.assertIsNone(self.m.reconhecer("nunca_vi"))

    def test_estatisticas(self):
        i, _ = self.m.abrir_incidente("a", "*", "bug", "media", "x", "erro")
        self.m.fechar(i, "ok", humano=False)
        e = self.m.estatisticas()
        self.assertEqual((e["total"], e["resolvidos"], e["automaticos"]), (1, 1, 1))
        self.assertTrue(self.m.verificar())


class TestPrevencao(Base):
    def test_pontos_sem_duplicar_e_sem_segredos(self):
        prev = Prevencao(self.raiz, self.tmp / "bio")
        p1 = prev.criar_ponto("primeiro")
        self.assertIsNotNone(p1)
        self.assertIsNone(prev.criar_ponto("igual"))                        # nada mudou
        arquivos = prev.pontos()[-1]["arquivos"]
        self.assertIn("memory/lista.json", arquivos)
        self.assertIn("config/app.json", arquivos)
        self.assertNotIn("config/api_keys.json", arquivos)                  # as suas chaves ficam de fora
        (self.raiz / "memory" / "lista.json").write_text('{"itens": [9]}', encoding="utf-8")
        time.sleep(1.1)
        self.assertIsNotNone(prev.criar_ponto("mudou"))
        self.assertEqual(len(list(prev.blobs.glob("*.json"))), 3)          # versões guardadas uma vez só

    def test_checagem_de_dados_acha_json_quebrado_e_versao_boa(self):
        prev = Prevencao(self.raiz, self.tmp / "bio")
        prev.criar_ponto("bom")
        self.assertEqual(prev.checar_dados(), [])
        (self.raiz / "memory" / "lista.json").write_text('{"itens": [1, 2', encoding="utf-8")
        ruins = prev.checar_dados()
        self.assertEqual(ruins[0]["arquivo"], "memory/lista.json")
        self.assertIsNotNone(ruins[0]["versao_boa"])
        ok, _ = prev.verificar_codigo(self.raiz / "plugins" / "bioteste_clima.py")
        self.assertTrue(ok)


class TestAnomalias(unittest.TestCase):
    def test_lentidao_e_rajada(self):
        a = DetectorAnomalias(minimo_amostras=10)
        for _ in range(30):
            self.assertIsNone(a.latencia("busca", 800))
        r = a.latencia("busca", 9000)
        self.assertEqual(r["tipo"], "lentidao")
        for _ in range(40):
            a.resultado("busca", True)
        achou = [a.resultado("busca", False) for _ in range(8)]
        self.assertTrue(any(x and x["tipo"] == "rajada_de_erros" for x in achou))

    def test_vazamento_de_memoria(self):
        self.assertAlmostEqual(tendencia([(0, 100), (1800, 150), (3600, 200)])[0], 100.0)
        a = DetectorAnomalias()
        alarmes = [a.memoria(i * 60.0, 400 + i * 1.5) for i in range(70)]    # +90 MB/h durante 70 min
        alarme = next(x for x in alarmes if x)
        self.assertEqual(alarme["tipo"], "vazamento_de_memoria")
        self.assertGreater(alarme["mb_por_hora"], 80)


class TestEvolucao(Base):
    def test_vacinas_passam_e_relatorio(self):
        org = organismo(self.raiz)
        try:
            res = org.imune.evolucao.exercitar()
            self.assertEqual([r["nome"] for r in res if not r["ok"]], [])
            self.assertEqual(len(res), 7)
            r = org.imune.evolucao.relatorio(7)
            self.assertIn("nota_defesa", r)
            self.assertEqual(r["exercicios"], res)
        finally:
            org.encerrar()


if __name__ == "__main__":
    unittest.main()
