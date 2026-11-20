"""Interpretadores de comando e funções puras dos plugins."""
import unittest

import tests  # noqa: F401
from plugins import _comum as c
from plugins import _indice_apps as apps


class TestNumeros(unittest.TestCase):
    def test_num(self):
        self.assertEqual(c.num("40"), 40)
        self.assertEqual(c.num("40,5"), 40.5)
        self.assertEqual(c.num("1.234,56"), 1234.56)
        self.assertEqual(c.num("85%"), 85)
        self.assertEqual(c.num("R$ 12,90"), 12.9)
        self.assertEqual(c.num("abc", 7), 7)
        self.assertEqual(c.num(None, 3), 3)

    def test_formatos_brasileiros(self):
        self.assertEqual(c.br(1234.5), "1.234,5")
        self.assertEqual(c.tamanho(3.4 * 1024 ** 3), "3,4 GB")
        self.assertEqual(c.tamanho(512), "512 B")
        self.assertEqual(c.velocidade(1_250_000), "1,2 MB/s")
        self.assertEqual(c.duracao(59), "59s")
        self.assertEqual(c.duracao(3600 + 5 * 60), "1h 05min")
        self.assertEqual(c.duracao(2 * 86400 + 3 * 3600), "2d 3h")

    def test_sim(self):
        for v in ("sim", "SIM", "true", "1", "ligado", True):
            self.assertTrue(c.sim(v))
        for v in ("nao", "não", "false", "", None, False):
            self.assertFalse(c.sim(v))


class TestBuscaDeApps(unittest.TestCase):
    ENTRADAS = [{"nome": n, "tipo": t} for n, t in [
        ("WhatsApp", "store"), ("Visual Studio Code", "atalho"), ("Uninstall Visual Studio Code", "atalho"),
        ("Google Chrome", "atalho"), ("Spotify", "store"), ("League of Legends", "atalho"),
        ("Counter-Strike 2", "steam"), ("Configurações", "store"), ("Microsoft Teams", "store"),
        ("Steam", "atalho"), ("Python 3.12 Manuals (64-bit)", "atalho"), ("Python 3.12 (64-bit)", "atalho")]]

    def melhor(self, consulta):
        r = apps.melhores(consulta, self.ENTRADAS, 1)
        return r[0]["nome"] if r else None

    def test_nomes_e_apelidos(self):
        self.assertEqual(self.melhor("vs code"), "Visual Studio Code")
        self.assertEqual(self.melhor("chrome"), "Google Chrome")
        self.assertEqual(self.melhor("configuracoes"), "Configurações")
        self.assertEqual(self.melhor("teams"), "Microsoft Teams")
        self.assertEqual(self.melhor("python"), "Python 3.12 (64-bit)")     # manual penalizado
        self.assertEqual(self.melhor(apps.APELIDOS_PADRAO["zap"]), "WhatsApp")
        self.assertEqual(self.melhor(apps.APELIDOS_PADRAO["lol"]), "League of Legends")

    def test_iniciais_e_abreviacoes(self):
        self.assertEqual(self.melhor("vsc"), "Visual Studio Code")
        self.assertEqual(self.melhor("ms teams"), "Microsoft Teams")     # e não o Steam
        self.assertEqual(self.melhor("teams"), "Microsoft Teams")

    def test_nome_dentro_do_pedido(self):
        self.assertEqual(apps.pontuar("estudos", "estudo"), 74)
        self.assertEqual(apps.pontuar("spotify premium", "Spotify"), 74)
        self.assertLess(apps.pontuar("ms teams", "Steam"), 55)          # "steam" no meio de "msteams"

    def test_erros_de_digitacao(self):
        self.assertEqual(self.melhor("spotfy"), "Spotify")
        self.assertEqual(self.melhor("counter strike"), "Counter-Strike 2")

    def test_desinstalador_nunca_ganha(self):
        self.assertEqual(self.melhor("visual studio code"), "Visual Studio Code")

    def test_nada_parecido(self):
        self.assertIsNone(self.melhor("xyzabc"))

    def test_normalizar(self):
        self.assertEqual(apps.normalizar("Abre o App do WhatsApp!"), "abre whatsapp")
        self.assertEqual(apps.normalizar("Configurações"), "configuracoes")


class TestControle(unittest.TestCase):
    def test_teclas(self):
        from plugins.controle_pc import teclas_de
        self.assertEqual(teclas_de("Ctrl + Shift + Esc"), ["ctrl", "shift", "esc"])
        self.assertEqual(teclas_de("win+d"), ["win", "d"])
        self.assertEqual(teclas_de("alt-tab"), ["alt", "tab"])
        self.assertEqual(teclas_de("controle+espaço"), ["ctrl", "space"])

    def test_nivel(self):
        from plugins.controle_audio_video import nivel_alvo
        self.assertEqual(nivel_alvo("mais", 40), 50)
        self.assertEqual(nivel_alvo("menos", 5), 0)
        self.assertEqual(nivel_alvo("35", 10), 35)
        self.assertEqual(nivel_alvo("80%", 0), 80)
        self.assertEqual(nivel_alvo("150", 0), 100)
        self.assertIsNone(nivel_alvo("abc", 1))

    def test_escolher_saida(self):
        from plugins.controle_audio_video import escolher_saida
        saidas = [{"id": "1", "nome": "Alto-falantes (Realtek(R) Audio)", "padrao": True},
                  {"id": "2", "nome": "Fones de ouvido (JBL Tune 510BT)", "padrao": False},
                  {"id": "3", "nome": "LG TV (NVIDIA High Definition Audio)", "padrao": False}]
        self.assertEqual(escolher_saida("fone", saidas)["id"], "2")
        self.assertEqual(escolher_saida("caixa", saidas)["id"], "1")
        self.assertEqual(escolher_saida("tv", saidas)["id"], "3")
        self.assertEqual(escolher_saida("hdmi", saidas)["id"], "3")
        self.assertIsNone(escolher_saida("qualquer", saidas))


class TestOutrosPlugins(unittest.TestCase):
    def test_categorias_de_limpeza(self):
        from plugins.limpeza import CATEGORIAS, categorias_de
        self.assertEqual(categorias_de(""), list(CATEGORIAS))
        self.assertEqual(categorias_de("tudo"), list(CATEGORIAS))
        self.assertEqual(categorias_de("só os temporários"), ["temporarios"])
        self.assertEqual(sorted(categorias_de("lixeira e cache do chrome")), ["lixeira", "navegadores"])

    def test_senha_nao_entra_no_historico(self):
        from plugins.historico_clipboard import parece_senha
        for t in ("Senh@Forte2024", "sk-abcdefghijklmnopqrstuvwx123", "AIzaSyA1234567890abcdefghijklmnopqrstu",
                  "ghp_abcdefghijklmnopqrstuvwxyz0123456789", "Xk9#mP2$vL"):
            self.assertTrue(parece_senha(t), t)
        for t in ("bom dia", "https://www.google.com/search?q=Teste123", "joao@email.com",
                  r"C:\Users\Joao\Downloads", "12345", "Rua das Flores, 123", "pedido42"):
            self.assertFalse(parece_senha(t), t)

    def test_site_bloqueado(self):
        from plugins.pomodoro import site_bloqueado
        termos = ["YouTube", "Instagram", "/ X"]
        self.assertEqual(site_bloqueado("Lofi beats - YouTube — Google Chrome", termos), "YouTube")
        self.assertEqual(site_bloqueado("Página inicial / X", termos), "X")
        self.assertIsNone(site_bloqueado("Documentação do Python", termos))

    def test_protocolo_formato_antigo_migra(self):
        from plugins.protocolos import migrar, passo_de
        novo = migrar({"fechar": ["steam"], "abrir": ["Spotify"], "sites": ["https://a.com"], "mensagem": "oi"})
        self.assertEqual([p["tipo"] for p in novo["passos"]], ["fechar", "abrir", "site"])
        self.assertEqual(novo["mensagem"], "oi")
        self.assertEqual(passo_de("esperar", "999"), {"tipo": "esperar", "segundos": 300})
        self.assertEqual(passo_de("modo jogo", "não"), {"tipo": "modo_jogo", "ligar": "nao"})
        self.assertIn("erro", passo_de("fechar", "explorer, csrss"))
        self.assertEqual(passo_de("fechar", "discord, explorer"), {"tipo": "fechar", "alvo": "discord"})
        self.assertIsNone(passo_de("voar", "x"))

    def test_downloads(self):
        from plugins.downloads import categoria, eh_parcial
        self.assertEqual(categoria("foto.JPG"), "Imagens")
        self.assertEqual(categoria("video.mp4"), "Vídeos")
        self.assertEqual(categoria("nota.pdf"), "PDFs")
        self.assertEqual(categoria("setup.exe"), "Instaladores")
        self.assertEqual(categoria("backup.tar.gz"), "Compactados")
        self.assertIsNone(categoria("arquivo.xyz"))
        self.assertTrue(eh_parcial("filme.mp4.crdownload"))
        self.assertTrue(eh_parcial("x.part"))
        self.assertFalse(eh_parcial("x.pdf"))

    def test_recorte_vertical(self):
        from plugins.gravador_tela import recorte_vertical
        self.assertEqual(recorte_vertical(1920, 1080), (657, 0, 606, 1080))
        self.assertEqual(recorte_vertical(1080, 1920), (0, 0, 1080, 1920))
        x, y, w, h = recorte_vertical(1367, 769)
        self.assertEqual((w % 2, h % 2), (0, 0))
        self.assertAlmostEqual(w / h, 9 / 16, places=2)

    def test_fps_presentmon(self):
        from plugins.modo_jogo import fps_de_linhas
        linhas = [{"MsBetweenPresents": "16.667"}] * 120
        self.assertEqual(fps_de_linhas(linhas), 60)
        self.assertEqual(fps_de_linhas([{"FrameTime": "8.333"}] * 200), 120)
        self.assertIsNone(fps_de_linhas([{"Outra": "1"}]))

    def test_ip_suspeito(self):
        from plugins.guarda_seguranca import ip_publico_suspeito
        self.assertTrue(ip_publico_suspeito("45.33.32.156"))
        for ip in ("192.168.0.10", "10.0.0.1", "127.0.0.1", "172.16.5.4", "224.0.0.251", "abc"):
            self.assertFalse(ip_publico_suspeito(ip), ip)

    def test_macros(self):
        from plugins.macros import slug, tecla_para_texto

        class K:
            def __init__(self, char=None, vk=None):
                self.char, self.vk = char, vk

            def __str__(self):
                return "x"
        self.assertEqual(tecla_para_texto(K(char="a")), "c:a")
        self.assertEqual(tecla_para_texto(K(vk=65)), "vk:65")
        self.assertEqual(slug("Relatório da Loja!"), "relatorio_da_loja")


class TestAlertas(unittest.TestCase):
    def setUp(self):
        from plugins.monitor_sistema import PLUGIN_SETTINGS, Vigia
        self.v = Vigia()
        self.c = {f["key"]: f["default"] for f in PLUGIN_SETTINGS["fields"]}

    def base(self, **kw):
        s = {"cpu": 10, "ram": {"pct": 40}, "particoes": [], "cpu_temp": 50, "gpu": None,
             "internet": True, "ping": {"8.8.8.8": {"ms": 20}}, "bateria": None, "processos": []}
        s.update(kw)
        return s

    def test_cpu_precisa_durar(self):
        s = self.base(cpu=95, processos=[{"nome": "chrome.exe"}])
        self.assertEqual(self.v.avaliar(s, self.c, 0), [])
        self.assertEqual(self.v.avaliar(s, self.c, 20), [])
        alertas = self.v.avaliar(s, self.c, 31)
        self.assertEqual(alertas[0][0], "alerta_cpu")
        self.assertIn("chrome.exe", alertas[0][1])
        self.assertEqual(self.v.avaliar(s, self.c, 40), [])           # sem repetir logo depois

    def test_cpu_que_cai_zera(self):
        self.v.avaliar(self.base(cpu=95), self.c, 0)
        self.v.avaliar(self.base(cpu=10), self.c, 20)
        self.assertEqual(self.v.avaliar(self.base(cpu=95), self.c, 31), [])

    def test_disco_ram_temp_bateria(self):
        s = self.base(ram={"pct": 90}, cpu_temp=91, bateria={"pct": 9, "na_tomada": False},
                      particoes=[{"ponto": "C:", "pct": 95, "livre": 5e9}])
        tipos = sorted(t for t, _m in self.v.avaliar(s, self.c, 0))
        self.assertEqual(tipos, ["alerta_bateria", "alerta_disco", "alerta_ram", "alerta_temp"])

    def test_internet_caiu_e_voltou(self):
        self.v.avaliar(self.base(), self.c, 0)
        self.assertEqual(self.v.avaliar(self.base(internet=False), self.c, 30), [])   # 1 leitura não basta
        self.assertEqual(self.v.avaliar(self.base(internet=False), self.c, 60)[0][0], "internet_caiu")
        self.v.avaliar(self.base(internet=True), self.c, 90)
        self.assertEqual(self.v.avaliar(self.base(internet=True), self.c, 120)[0][0], "internet_voltou")

    def test_ping_alto_precisa_de_3(self):
        s = self.base(ping={"8.8.8.8": {"ms": 300}})
        self.assertEqual(self.v.avaliar(s, self.c, 0), [])
        self.assertEqual(self.v.avaliar(s, self.c, 30), [])
        self.assertEqual(self.v.avaliar(s, self.c, 60)[0][0], "alerta_ping")


class TestRede(unittest.TestCase):
    def test_sem_conexao(self):
        from plugins.assistente_rede import diagnosticar
        resumo, causas, dicas = diagnosticar({"gateway_ms": None, "internet_ms": None})
        self.assertIn("roteador", resumo)
        resumo, _c, dicas = diagnosticar({"gateway_ms": 2, "internet_ms": None})
        self.assertIn("internet não chega", resumo)
        self.assertTrue(any("modem" in d for d in dicas))

    def test_wifi_fraco_e_dns_lento(self):
        from plugins.assistente_rede import diagnosticar
        d = {"gateway_ms": 45, "gateway_perda": 0, "internet_ms": 60, "internet_perda": 0,
             "wifi_sinal": 30, "dns_sistema_ms": 250, "dns_cloudflare_ms": 20, "dns_servidor": "192.168.0.1"}
        resumo, causas, dicas = diagnosticar(d)
        self.assertTrue(any("roteador" in c for c in causas))
        self.assertTrue(any("sinal" in c for c in causas))
        self.assertTrue(any("DNS" in c for c in causas))
        self.assertTrue(any("1.1.1.1" in x for x in dicas))

    def test_plano_abaixo(self):
        from plugins.assistente_rede import diagnosticar
        d = {"gateway_ms": 2, "internet_ms": 20, "down_mbps": 40}
        _r, causas, _d = diagnosticar(d, plano_mbps=300)
        self.assertTrue(any("13%" in c for c in causas))

    def test_tudo_normal(self):
        from plugins.assistente_rede import diagnosticar
        resumo, causas, _d = diagnosticar({"gateway_ms": 2, "internet_ms": 20, "down_mbps": 300})
        self.assertEqual(causas, [])
        self.assertIn("normal", resumo)


if __name__ == "__main__":
    unittest.main()
