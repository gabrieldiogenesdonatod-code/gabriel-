"""
Testes da 2.0 — música (Spotify/YouTube Music), perfil de gosto, Telegram,
Discord, canais, companheiro que oferece coisas, treinador de jogo, macros em
modo jogo e o app do celular. Sem internet: as APIs são simuladas.
"""
import base64
import hashlib
import json
import random
import time
import unittest
from unittest import mock

import tests
from plugins import (_canais, _conversa_remota as CR, _discord, _gosto, _spotify as S, _telegram as TG, _tunel,
                     app_celular, companheiro as C, companheiro_jogo as CJ, macros, musica as M)


class _Temp(unittest.TestCase):
    def setUp(self):
        self._orig = (_gosto.ARQ, C.ARQ, TG.ARQ)
        _gosto.ARQ, C.ARQ, TG.ARQ = tests.TMP / "gosto_t.json", tests.TMP / "comp_t.json", tests.TMP / "tg_t.json"
        for a in (_gosto.ARQ, C.ARQ, TG.ARQ):
            a.unlink(missing_ok=True)

    def tearDown(self):
        _gosto.ARQ, C.ARQ, TG.ARQ = self._orig


class TestGosto(_Temp):
    def test_ranking_e_esquecimento(self):
        agora = time.time()
        evs = [{"ts": agora, "tipo": "musica", "item": "Kaiser - Impossível", "acao": "curtiu"},
               {"ts": agora, "tipo": "musica", "item": "Kaiser - Artista", "acao": "tocou"},
               {"ts": agora - 120 * 86400, "tipo": "musica", "item": "Antigo - Música", "acao": "curtiu"},
               {"ts": agora, "tipo": "musica", "item": "Chato - Faixa", "acao": "pulou"},
               {"ts": agora, "tipo": "video", "item": "Como fazer pão", "acao": "viu"}]
        rank = _gosto.ranking(evs, "musica", _gosto.artista_de, agora)
        self.assertEqual(rank[0], ("Kaiser", 6.0))
        self.assertAlmostEqual(dict(rank)["Antigo"], 1.25)                     # 2 meias-vidas: 5 → 1,25
        self.assertNotIn("Chato", dict(rank))
        self.assertEqual(_gosto.artista_de("Sem artista"), "")

    def test_registrar_e_resumo(self):
        _gosto.registrar("musica", "Kaiser - Impossível", "pediu")
        _gosto.registrar("jogo", "Roblox", "jogou")
        _gosto.nao_gosto("Sertanejo X")
        r = _gosto.resumo()
        self.assertIn("artistas: Kaiser", r)
        self.assertIn("jogos: Roblox", r)
        self.assertIn("NÃO gosta de: Sertanejo X", r)
        _gosto.registrar("oferta", "Kaiser - Novo", "ofereceu")
        self.assertTrue(_gosto.ja_ofereceu("kaiser - novo"))


class TestSpotifyEMusica(_Temp):
    def test_pkce_e_pedidos(self):
        v, c = S.par_pkce()
        self.assertEqual(c, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).decode().rstrip("="))
        self.assertTrue(43 <= len(v) <= 128)
        url = S.url_login("abc", c, "xyz")
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback", url)
        self.assertEqual((S.tipo_do_pedido("toca a playlist de treino"), S.limpar_pedido("toca a playlist de treino")),
                         ("playlist", "treino"))
        self.assertEqual(S.tipo_do_pedido("músicas do Kaiser"), "artist")
        self.assertEqual(S.tipo_do_pedido("Impossível"), "track")
        self.assertEqual(M.servico_do_pedido("Impossível no YouTube Music", "", True), ("youtube", "Impossível"))
        self.assertEqual(M.servico_do_pedido("Kaiser", "", False), ("youtube", "Kaiser"))
        self.assertEqual(M.servico_do_pedido("Kaiser", "", True, "youtube"), ("youtube", "Kaiser"))

    def test_sem_premium_abre_no_app(self):
        item = {"uri": "spotify:track:1", "_tipo": "track", "name": "Impossível", "artists": [{"name": "Kaiser"}]}
        abertos = []
        with mock.patch.object(S, "api", side_effect=S.ErroSpotify(403, "premium")), \
                mock.patch.object(S, "abrir_no_sistema", abertos.append):
            r = S.tocar_item(item)
        self.assertEqual(abertos, ["spotify:track:1"])
        self.assertIn("Kaiser - Impossível", r)

    def test_tocar_no_youtube_sem_spotify(self):
        abertos = []
        with mock.patch.object(S, "conectado", lambda: False), mock.patch.object(M, "abrir_no_sistema", abertos.append), \
                mock.patch.object(M, "url_youtube_music", lambda q: "https://music.youtube.com/search?q=" + q):
            r = M.run({"action": "tocar", "pedido": "Kaiser - Impossível"})
        self.assertEqual(r, "Tocando Kaiser - Impossível (YouTube Music).")
        self.assertEqual(abertos, ["https://music.youtube.com/search?q=Kaiser - Impossível"])
        self.assertEqual(_gosto.top_artistas(1), ["Kaiser"])


class TestCanaisTelegramDiscord(_Temp):
    def test_ordem(self):
        self.assertEqual(_canais.ordem("telegram, whatsapp", ["whatsapp", "telegram", "discord", "ligacao"]),
                         ["telegram", "whatsapp", "discord"])
        self.assertEqual(_canais.ordem("", ["ligacao"]), [])                          # ligação nunca entra sozinha

    def test_mandar(self):
        enviados = []
        with mock.patch.object(_canais, "ativos", lambda: ["telegram", "discord"]), \
                mock.patch.object(TG, "para_donos", lambda t, a=None, b=None: enviados.append(("tg", t, b)) or 1):
            self.assertEqual(_canais.mandar("oi", botoes=[[("👍", "oferta:1:sim")]], preferidos="telegram"), ["telegram"])
        self.assertEqual(enviados, [("tg", "oi", [[("👍", "oferta:1:sim")]])])

    def test_telegram_pareamento_e_conversa(self):
        self.assertEqual(TG.decidir({"chat": {"id": 1, "type": "group"}, "text": "J"}, [1], "J"), "ignorar")
        enviados = []
        with mock.patch.object(TG, "enviar", lambda c, t, b=None: enviados.append((c, t)) or True), \
                mock.patch.object(TG, "chamar", lambda *a, **k: {}):
            cod = TG.novo_codigo()
            TG.tratar({"message": {"chat": {"id": 77, "type": "private"}, "text": "oi"}})
            self.assertEqual(enviados, [])
            TG.tratar({"message": {"chat": {"id": 77, "type": "private"}, "text": cod.lower()}})
            self.assertIn(77, TG.dados()["chats"])
            TG.tratar({"message": {"chat": {"id": 77, "type": "private"}, "text": "/start"}})
            self.assertIn("Atalhos", enviados[-1][1])

    def test_discord(self):
        msgs = [{"id": "30", "author": {"id": "9"}, "content": "c"}, {"id": "10", "author": {"id": "5"}, "content": "a"},
                {"id": "20", "author": {"id": "5"}, "content": "b"}]
        self.assertEqual([m["content"] for m in _discord.mensagens_do_dono(msgs, "5")], ["a", "b"])
        self.assertEqual(_discord.link_convite("123"), "https://discord.com/oauth2/authorize?client_id=123&scope=bot&permissions=0")

    def test_atender_igual_em_todo_canal(self):
        saida = []
        with mock.patch("core.resposta_remota.pedir", lambda texto, resp, fonte="", silencio=True: resp("feito") or True):
            CR.atender("liga a TV", saida.append, lambda l, a: None, "discord")
        self.assertEqual(saida, ["feito"])
        self.assertIn("[Mensagem do dono pelo Discord] liga a TV", CR.instrucao("liga a TV", "discord"))


class TestCompanheiro(_Temp):
    def test_regras(self):
        self.assertTrue(C.em_silencio(23, "23-8"))
        self.assertTrue(C.em_silencio(3, "23-8"))
        self.assertFalse(C.em_silencio(8, "23-8"))
        self.assertTrue(C.em_silencio(13, "12-14"))
        self.assertEqual(C.ler_resposta("Quero!"), "sim")
        self.assertEqual(C.ler_resposta("agora não"), "nao")
        self.assertEqual(C.ler_resposta("oferta:5:sim"), "sim")
        self.assertEqual(C.ler_resposta("ok"), "")                              # ambíguo: não é resposta de oferta
        self.assertEqual(C.ler_resposta("quero saber como está o servidor hoje à noite"), "")
        cfg = {"ligado": True, "por_dia": "2", "intervalo_h": "2", "silencio": "23-8"}
        meio_dia = time.mktime(time.strptime("2026-11-03 12:00", "%Y-%m-%d %H:%M"))
        e = {"enviadas": [], "quieto_ate": 0}
        self.assertTrue(C.pode_oferecer(e, cfg, meio_dia))
        self.assertFalse(C.pode_oferecer({**e, "enviadas": [meio_dia - 3600]}, cfg, meio_dia))      # intervalo
        self.assertFalse(C.pode_oferecer({**e, "enviadas": [meio_dia - 4 * 3600, meio_dia - 3 * 3600]}, cfg, meio_dia))
        self.assertFalse(C.pode_oferecer({**e, "quieto_ate": meio_dia + 60}, cfg, meio_dia))
        self.assertFalse(C.pode_oferecer(e, {**cfg, "ligado": False}, meio_dia))

    def test_aprende_o_que_aceita(self):
        evs = [{"tipo": "oferta", "acao": "aceitou", "extra": "musica"}] * 4 + \
              [{"tipo": "oferta", "acao": "recusou", "extra": "video"}] * 4
        pesos = C.aceite_por_tipo(evs)
        self.assertGreater(pesos["musica"], 0.8)
        self.assertLess(pesos["video"], 0.2)
        rng = random.Random(1)
        sorteio = [C.escolher_tipo(pesos, rng, ("musica", "video")) for _ in range(200)]
        self.assertGreater(sorteio.count("musica"), 140)

    def test_oferta_fora_do_pc_e_resposta(self):
        enviados = []
        oferta = {"tipo": "musica", "texto": "🎵 Saiu coisa nova", "item": "Kaiser - Novo",
                  "link": "https://music.youtube.com/search?q=Kaiser", "acao": {"ferramenta": "musica", "params": {}}}
        with mock.patch.object(C, "ocioso_s", lambda: 3600), \
                mock.patch.object(_canais, "mandar", lambda t, botoes=None, preferidos="", **k: enviados.append((t, botoes)) or ["telegram"]):
            r = C.entregar(oferta)
        self.assertIn("Mandei pelo Telegram", r)
        self.assertEqual(enviados[0][1][0][0][0], "👍 Quero")
        self.assertEqual(C.responder_oferta("bora"), "Aqui está: https://music.youtube.com/search?q=Kaiser")
        self.assertEqual(C.responder_oferta("bora"), "")                        # já respondida
        aceitas = [e for e in _gosto.dados()["eventos"] if e["acao"] == "aceitou"]
        self.assertEqual(aceitas[0]["extra"], "musica")

    def test_ligacao_agendada(self):
        from datetime import datetime
        e = {"ligacoes": [{"hora": "20:00", "texto": "oi", "dia": "2026-11-03"},
                          {"hora": "22:00", "texto": "depois", "dia": "2026-11-03"}]}
        devidas = C._ligacoes_agendadas(e, datetime(2026, 11, 3, 20, 1))
        self.assertEqual([d["texto"] for d in devidas], ["oi"])
        self.assertEqual([d["texto"] for d in e["ligacoes"]], ["depois"])


class TestJogosEApp(unittest.TestCase):
    def test_macro_so_com_o_jogo_em_frente(self):
        self.assertTrue(macros.janela_ok("roblox", {"processo": "RobloxPlayerBeta.exe", "titulo": "Roblox"}))
        self.assertFalse(macros.janela_ok("roblox", {"processo": "chrome.exe", "titulo": "YouTube"}))
        self.assertFalse(macros.janela_ok("roblox", None))
        self.assertTrue(macros.janela_ok("", None))

    def test_treinador(self):
        p = CJ.prompt_dica("Roblox", "passar do obby", ["pule no canto da plataforma"], ["use o shift lock"])
        self.assertIn("você NÃO joga por ele", p)
        self.assertIn("passar do obby", p)
        self.assertIn("pule no canto da plataforma", p)
        self.assertIn("não repita", p)
        self.assertIn("responda só: -", p)
        self.assertIn("Ele perguntou: o que eu faço?", CJ.prompt_dica("Roblox", "", [], [], "o que eu faço?"))

    def test_tailscale_https_e_app(self):
        self.assertEqual(_tunel.alvo_serve("http://localhost:8000"), "http://127.0.0.1:8000")
        self.assertEqual(_tunel.alvo_serve("https://localhost:8001"), "https+insecure://127.0.0.1:8001")
        self.assertTrue(_tunel.serve_ativo('{"TCP": {"443": {"HTTPS": true}}, "Web": {}}'))
        self.assertFalse(_tunel.serve_ativo("{}"))
        with mock.patch.object(app_celular, "cfg", lambda ns, s: {"compartilhar_chave": False}):
            self.assertIn("erro", app_celular.chave_para_celular())

    def test_arquivos_do_app(self):
        base = tests.RAIZ / "dashboard" / "static"
        man = json.loads((base / "movel.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual((man["start_url"], man["display"]), ("/movel", "standalone"))
        html = (base / "movel.html").read_text(encoding="utf-8")
        for nome in ("tocar_musica", "mandar_whatsapp", "pesquisar", "mandar_para_pc", "/api/command", "sw-movel.js"):
            self.assertIn(nome, html)


if __name__ == "__main__":
    unittest.main()
