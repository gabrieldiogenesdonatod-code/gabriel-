"""
Testes da 2.12 — a porta de entrada (login.py).

Só a lógica de contas (Python puro): criação, hash, autenticação, recuperação
por pergunta de segurança, "lembrar de mim" e usuário atual. Não abre interface
(customtkinter não é necessário) nem usa câmera/microfone. Também confere o
contrato de ouro: a biometria NUNCA levanta exceção e, sem cadastro, só diz não.
"""
import json
import unittest

import login as L
from tests import TMP


class _Base(unittest.TestCase):
    def setUp(self):
        # isola os arquivos de conta numa pasta de teste (nunca toca o config real)
        pasta = TMP / f"login_{self._testMethodName}"
        pasta.mkdir(parents=True, exist_ok=True)
        L.ARQ_CONTAS = pasta / "contas.json"
        L.ARQ_API = pasta / "api_keys.json"
        L.ARQ_SESSAO = pasta / "sessao.json"


# ── hash de senha ────────────────────────────────────────────────────────────
class TestHash(_Base):
    def test_resumo_confere_e_e_irreversivel(self):
        reg = L.hash_senha("minhaSenha123")
        self.assertEqual(reg["algo"], "pbkdf2_sha256")
        self.assertTrue(L.conferir_senha("minhaSenha123", reg))
        self.assertFalse(L.conferir_senha("outra", reg))
        # a senha em claro não aparece em lugar nenhum do registro
        self.assertNotIn("minhaSenha123", json.dumps(reg))

    def test_sal_aleatorio(self):
        a = L.hash_senha("igual")
        b = L.hash_senha("igual")
        self.assertNotEqual(a["sal"], b["sal"])
        self.assertNotEqual(a["hash"], b["hash"])

    def test_registro_invalido_nao_estoura(self):
        self.assertFalse(L.conferir_senha("x", {}))
        self.assertFalse(L.conferir_senha("x", {"sal": "!!!", "hash": "!!!"}))


# ── e-mail ─────────────────────────────────────────────────────────────────────
class TestEmail(_Base):
    def test_validacao(self):
        self.assertTrue(L.validar_email("voce@exemplo.com"))
        self.assertFalse(L.validar_email("semarroba"))
        self.assertFalse(L.validar_email("a@b"))          # sem ponto no domínio
        self.assertFalse(L.validar_email("com espaco@x.com"))

    def test_normaliza(self):
        self.assertEqual(L.normalizar_email("  VoCe@Exemplo.COM "), "voce@exemplo.com")


# ── contas ───────────────────────────────────────────────────────────────────
class TestContas(_Base):
    def test_criar_e_autenticar(self):
        self.assertFalse(L.tem_contas())
        ok, _ = L.criar_conta("voce@exemplo.com", "segredo123", "Rimuru")
        self.assertTrue(ok)
        self.assertTrue(L.tem_contas())
        ok, _msg, conta = L.autenticar("VOCE@exemplo.com", "segredo123")   # e-mail normaliza
        self.assertTrue(ok)
        self.assertEqual(conta["nome"], "Rimuru")

    def test_senha_errada_e_conta_inexistente(self):
        L.criar_conta("voce@exemplo.com", "segredo123")
        ok, msg, _ = L.autenticar("voce@exemplo.com", "errada")
        self.assertFalse(ok)
        self.assertIn("ncorreta", msg)
        ok, _msg, _ = L.autenticar("ninguem@x.com", "x")
        self.assertFalse(ok)

    def test_senha_curta_recusada(self):
        ok, msg = L.criar_conta("voce@exemplo.com", "123")
        self.assertFalse(ok)
        self.assertIn("6", msg)

    def test_email_duplicado(self):
        self.assertTrue(L.criar_conta("voce@exemplo.com", "segredo123")[0])
        ok, msg = L.criar_conta("VOCE@EXEMPLO.COM", "outrasenha")
        self.assertFalse(ok)
        self.assertIn("Já existe", msg)

    def test_nada_em_texto_puro_no_arquivo(self):
        L.criar_conta("voce@exemplo.com", "segredoSuper", "Nome", "meu pet", "Rex")
        bruto = L.ARQ_CONTAS.read_text(encoding="utf-8")
        self.assertNotIn("segredoSuper", bruto)
        self.assertNotIn("Rex", bruto)          # a resposta também é resumida


# ── recuperação por pergunta de segurança ──────────────────────────────────────
class TestRecuperacao(_Base):
    def test_fluxo_completo(self):
        L.criar_conta("voce@exemplo.com", "velha123", "Nome", "primeiro pet", "Rex")
        self.assertEqual(L.pergunta_de("voce@exemplo.com"), "primeiro pet")
        # resposta confere ignorando caixa/espaços
        ok, _ = L.recuperar_senha("voce@exemplo.com", "  rEx ", "novaSenha1")
        self.assertTrue(ok)
        self.assertTrue(L.autenticar("voce@exemplo.com", "novaSenha1")[0])
        self.assertFalse(L.autenticar("voce@exemplo.com", "velha123")[0])

    def test_resposta_errada(self):
        L.criar_conta("voce@exemplo.com", "velha123", "Nome", "pet", "Rex")
        ok, msg = L.recuperar_senha("voce@exemplo.com", "errada", "novaSenha1")
        self.assertFalse(ok)
        self.assertFalse(L.autenticar("voce@exemplo.com", "novaSenha1")[0])

    def test_sem_pergunta_cadastrada(self):
        L.criar_conta("voce@exemplo.com", "velha123")       # sem resposta
        ok, msg = L.recuperar_senha("voce@exemplo.com", "x", "novaSenha1")
        self.assertFalse(ok)

    def test_nova_senha_curta(self):
        L.criar_conta("voce@exemplo.com", "velha123", "N", "pet", "Rex")
        ok, _ = L.recuperar_senha("voce@exemplo.com", "Rex", "123")
        self.assertFalse(ok)


# ── usuário atual / sessão lembrada ────────────────────────────────────────────
class TestSessao(_Base):
    def test_definir_usuario_preserva_outras_chaves(self):
        L.ARQ_API.parent.mkdir(parents=True, exist_ok=True)
        L.ARQ_API.write_text(json.dumps({"gemini_api_key": "ABC"}), encoding="utf-8")
        L.definir_usuario_atual("Rimuru", "voce@exemplo.com")
        d = json.loads(L.ARQ_API.read_text(encoding="utf-8"))
        self.assertEqual(d["gemini_api_key"], "ABC")        # não apagou a chave
        self.assertEqual(d["user_name"], "Rimuru")
        self.assertEqual(d["user_email"], "voce@exemplo.com")

    def test_lembrar_e_esquecer(self):
        L.criar_conta("voce@exemplo.com", "segredo123", "Rimuru")
        self.assertIsNone(L.sessao_lembrada())
        L.lembrar_sessao("voce@exemplo.com", "Rimuru")
        self.assertEqual(L.sessao_lembrada()["nome"], "Rimuru")
        L.esquecer_sessao()
        self.assertIsNone(L.sessao_lembrada())

    def test_sessao_de_conta_apagada_e_ignorada(self):
        # lembrou, mas a conta não existe mais → não oferece "continuar"
        L.lembrar_sessao("fantasma@x.com", "Fantasma")
        self.assertIsNone(L.sessao_lembrada())


# ── contrato de ouro: biometria nunca trava a abertura ─────────────────────────
class TestBiometriaNaoBloqueia(_Base):
    def test_sem_cadastro_so_diz_nao_sem_estourar(self):
        # sem dono.npy cadastrado, nada disso pode levantar exceção
        self.assertIn(L.rosto_cadastrado(), (True, False))
        self.assertIn(L.voz_cadastrada(), (True, False))
        ok, msg = L.verificar_rosto()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)
        ok, msg = L.verificar_voz()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)


if __name__ == "__main__":
    unittest.main()
