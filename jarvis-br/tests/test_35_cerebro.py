"""
Testes da 2.9 — segundo cérebro (plugins/segundo_cerebro.py) e biblioteca de prompts
(plugins/biblioteca_prompts.py). Sem Gemini e sem gravar fora da pasta de teste.
"""
import unittest
from pathlib import Path
from unittest import mock

from plugins import biblioteca_prompts as B
from plugins import segundo_cerebro as C
from tests import RAIZ, TMP


class _Base(unittest.TestCase):
    def setUp(self):
        C.ARQ = TMP / "segundo_cerebro.json"
        C.ARQ.unlink(missing_ok=True)
        B.ARQ = TMP / "prompts.json"
        B.ARQ.unlink(missing_ok=True)
        self._cofre = TMP / "cofre"
        self._p = [mock.patch.object(C, "base_cofre", lambda: self._cofre),
                   mock.patch.object(C, "_c", lambda: {"usar_ia": False, "abrir_ao_criar": False}),
                   mock.patch.object(C, "abrir_no_sistema", lambda *a: True)]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()


# ── segundo cérebro ──────────────────────────────────────────────────────────
class TestCerebroRegras(unittest.TestCase):
    def test_limpar_tira_o_comando(self):
        self.assertEqual(C.limpar("Jarvis, guarda no meu cérebro: o fornecedor fecha às 17h"),
                         "o fornecedor fecha às 17h")
        self.assertEqual(C.limpar("anota que a senha do wifi é 1234"), "a senha do wifi é 1234")
        self.assertEqual(C.limpar("comprar pão"), "comprar pão")       # sem comando: não corta

    def test_pasta_por_regra(self):
        self.assertEqual(C.pasta_por_regra("o fornecedor da loja entrega malha"), "loja")
        self.assertEqual(C.pasta_por_regra("a senha do wifi"), "senhas")
        self.assertEqual(C.pasta_por_regra("comprar presente pra vó"), "pessoal")
        self.assertEqual(C.pasta_por_regra("corrigir o bug no código python"), "programação")
        self.assertEqual(C.pasta_por_regra("coisa aleatória sem tema"), "")

    def test_tags_sem_repetir_nem_stopword(self):
        tags = C.tags_de("o fornecedor de Jaraguá fecha às 17h, fornecedor confiável")
        self.assertIn("fornecedor", tags)
        self.assertEqual(tags[0], "fornecedor")                        # repetido → mais relevante, vem primeiro
        self.assertNotIn("que", tags)
        self.assertLessEqual(len(tags), C.MAX_TAGS)

    def test_busca_ranqueia_tag_acima_do_texto(self):
        notas = [{"id": 1, "texto": "falar com o fornecedor", "pasta": "loja", "tags": [], "criada": 1},
                 {"id": 2, "texto": "pagar a conta", "pasta": "finanças", "tags": ["fornecedor"], "criada": 2}]
        self.assertEqual([n["id"] for n in C.buscar_notas(notas, "fornecedor")], [2, 1])
        self.assertEqual([n["id"] for n in C.buscar_notas(notas, "#1")], [1])
        self.assertEqual(C.buscar_notas(notas, "girafa"), [])

    def test_frontmatter_tem_tags_e_titulo(self):
        fm = C.frontmatter({"titulo": "Teste", "texto": "corpo", "pasta": "loja", "tags": ["a", "b"], "criada": 0})
        self.assertIn("tags: [a, b]", fm)
        self.assertIn("pasta: loja", fm)
        self.assertIn("# Teste", fm)
        self.assertIn("#a #b", fm)


class TestCerebroFluxo(_Base):
    def test_anotar_cria_indice_e_arquivo(self):
        r = C.run({"action": "anotar", "texto": "Jarvis, guarda no meu cérebro: o fornecedor de Jaraguá fecha às 17h"})
        self.assertIn("loja", r)
        d = C.dados()
        self.assertEqual(len(d["notas"]), 1)
        nota = d["notas"][0]
        self.assertEqual(nota["pasta"], "loja")
        self.assertTrue(nota["arquivo"] and Path(nota["arquivo"]).exists())
        self.assertIn("fornecedor", Path(nota["arquivo"]).read_text(encoding="utf-8"))

    def test_nao_duplica(self):
        C.run({"action": "anotar", "texto": "comprar leite"})
        self.assertIn("já tinha", C.run({"action": "anotar", "texto": "comprar leite"}))
        self.assertEqual(len(C.dados()["notas"]), 1)

    def test_forcar_pasta_e_tags(self):
        C.run({"action": "anotar", "texto": "a senha do portão é 4210", "pasta": "senhas", "tags": "portao, senha"})
        nota = C.dados()["notas"][0]
        self.assertEqual(nota["pasta"], "senhas")
        self.assertEqual(nota["tags"], ["portao", "senha"])

    def test_buscar_recorda(self):
        C.run({"action": "anotar", "texto": "o fornecedor de Jaraguá fecha às 17h", "pasta": "loja"})
        C.run({"action": "anotar", "texto": "a vó toma o remédio às 8h", "pasta": "pessoal"})
        r = C.run({"action": "buscar", "termo": "o que eu falei sobre o fornecedor"})
        self.assertIn("Jaraguá", r)
        self.assertNotIn("remédio", r)
        self.assertIn("não achei", C.run({"action": "buscar", "termo": "dinossauro"}).lower())

    def test_listar_pastas_e_remover(self):
        C.run({"action": "anotar", "texto": "nota da loja", "pasta": "loja"})
        C.run({"action": "anotar", "texto": "nota pessoal", "pasta": "pessoal"})
        self.assertIn("2 pasta", C.run({"action": "listar"}))
        self.assertIn("loja", C.run({"action": "listar", "pasta": "loja"}))
        arq = Path(C.dados()["notas"][0]["arquivo"])
        self.assertIn("Apaguei", C.run({"action": "remover", "nota": "#1"}))
        self.assertEqual(len(C.dados()["notas"]), 1)
        self.assertFalse(arq.exists())                                 # apagou o .md junto


# ── biblioteca de prompts ────────────────────────────────────────────────────
class TestPrompts(_Base):
    def test_salvar_usar_conta_uso(self):
        self.assertIn("Salvei", B.run({"action": "salvar", "nome": "post de produto",
                                       "texto": "Escreva uma legenda animada, 3 hashtags.", "tags": "loja, instagram"}))
        r = B.run({"action": "usar", "termo": "post de produto"})
        self.assertIn("Escreva uma legenda animada, 3 hashtags.", r)
        self.assertEqual(B.dados()["prompts"][0]["usos"], 1)

    def test_nome_limpo_e_atualizar(self):
        self.assertEqual(B.limpar_nome("o prompt do resumo"), "resumo")
        B.run({"action": "salvar", "nome": "resumo", "texto": "v1"})
        self.assertIn("Atualizei", B.run({"action": "salvar", "nome": "resumo", "texto": "v2"}))
        self.assertEqual(len(B.dados()["prompts"]), 1)
        self.assertIn("v2", B.run({"action": "usar", "termo": "resumo"}))

    def test_busca_por_nome_vence_texto(self):
        B.run({"action": "salvar", "nome": "loja", "texto": "qualquer coisa"})
        B.run({"action": "salvar", "nome": "resumo", "texto": "resuma o texto da loja"})
        r = B.run({"action": "usar", "termo": "loja"})
        self.assertIn("“loja”", r)

    def test_desambigua_quando_vago(self):
        B.run({"action": "salvar", "nome": "post instagram", "texto": "a"})
        B.run({"action": "salvar", "nome": "post blog", "texto": "b"})
        r = B.run({"action": "usar", "termo": "post"})
        self.assertIn("Achei mais de um", r)

    def test_listar_remover_e_tag(self):
        B.run({"action": "salvar", "nome": "alfa", "texto": "x", "tags": "loja"})
        B.run({"action": "salvar", "nome": "beta", "texto": "y"})
        self.assertIn("2 prompt", B.run({"action": "listar"}))
        self.assertIn("1 prompt", B.run({"action": "listar", "tags": "loja"}))
        self.assertIn("Apaguei", B.run({"action": "remover", "termo": "alfa"}))
        self.assertEqual(len(B.dados()["prompts"]), 1)

    def test_vazio(self):
        self.assertIn("vazia", B.run({"action": "listar"}))
        self.assertIn("Não achei", B.run({"action": "usar", "termo": "nada"}))


class TestRegistro(unittest.TestCase):
    def test_niveis_e_carregamento(self):
        from core import verificacao
        self.assertEqual(verificacao.nivel_de("segundo_cerebro", {"action": "anotar"}), verificacao.LIVRE)
        self.assertEqual(verificacao.nivel_de("biblioteca_prompts", {"action": "salvar"}), verificacao.LIVRE)
        for arq in ("segundo_cerebro.py", "biblioteca_prompts.py"):
            self.assertIn("def run(", (RAIZ / "plugins" / arq).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
