"""
Gerador de testes automáticos (fork PT-BR 1.6).

Lê um arquivo .py, acha as funções públicas e escreve testes unittest para
elas. Antes de entregar, RODA os testes numa pasta isolada (com uma cópia do
seu arquivo): só salva os que passam; os que falham vêm marcados para você
olhar (às vezes o teste achou um bug de verdade).

    "Jarvis, gera testes para C:\\projetos\\loja\\calculos.py"
    "Jarvis, gera testes para a função calcular_troco do calculos.py"

Salva em tests/test_<arquivo>_gerado.py ao lado do projeto (nunca sobrescreve).
Sem a chave do Gemini, gera o esqueleto (um teste por função, para você completar).
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from plugins._comum import mostrar

PLUGIN = {
    "name": "gerador_testes",
    "brief": "Generates unittest tests for a Python file's functions, runs them in a sandbox, saves the result.",
    "description": (
        "Automatic test generator: arquivo = path of a .py file (optional funcao = only that function). Finds public "
        "functions, writes unittest tests (AI; without AI a skeleton), runs them in an isolated copy and saves "
        "tests/test_<file>_gerado.py next to the project without overwriting anything."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"arquivo": {"type": "STRING"}, "funcao": {"type": "STRING"}},
        "required": ["arquivo"],
    },
}


def esqueleto(modulo: str, funcs: list[dict]) -> str:
    """Testes de esqueleto: a função existe e é chamável; um TODO por caso (pura)."""
    linhas = ["import unittest", "", f"import {modulo}", "", "",
              f"class Test{modulo.title().replace('_', '')}(unittest.TestCase):"]
    for f in funcs:
        alvo = f"{modulo}.{f['classe']}" if f["classe"] else f"{modulo}.{f['nome']}"
        linhas += [f"    def test_{(f['classe'] + '_' if f['classe'] else '').lower()}{f['nome']}(self):",
                   f"        self.assertTrue(callable({alvo}))",
                   f"        # TODO: chame {f['qual']}({', '.join(f['args'])}) e confira o resultado", ""]
    if not funcs:
        linhas += ["    def test_importa(self):", f"        self.assertIsNotNone({modulo})", ""]
    return "\n".join(linhas) + "\nif __name__ == \"__main__\":\n    unittest.main()\n"


def rodar(codigo_modulo: str, testes: str, modulo: str, pasta_projeto: Path) -> tuple[bool, str]:
    from plugins.laboratorio import rodar_uma
    with tempfile.TemporaryDirectory(prefix="jarvis_testes_") as tmp:
        (Path(tmp) / f"{modulo}.py").write_text(codigo_modulo, encoding="utf-8")
        (Path(tmp) / f"test_{modulo}_gerado.py").write_text(testes, encoding="utf-8")
        import os
        pasta_projeto = Path(pasta_projeto).resolve()
        raiz = pasta_projeto                                   # arquivo dentro de um pacote: a raiz do projeto
        while (raiz / "__init__.py").exists() and raiz.parent != raiz:
            raiz = raiz.parent
        env_extra = os.pathsep.join([tmp, str(pasta_projeto), str(raiz)])
        r = rodar_uma(Path(tmp), [sys.executable, "-c",
                                  f"import sys; sys.path[:0] = {env_extra.split(os.pathsep)!r}; import unittest; "
                                  f"unittest.main(module='test_{modulo}_gerado', argv=['x', '-v'])"], 120)
        return r["ok"], r["fim"]


def gerar(arquivo: Path, funcao: str = "", player=None) -> str:
    from plugins import _ia
    from plugins._analise_codigo import funcoes
    from plugins.ditado_codigo import extrair_blocos
    codigo = arquivo.read_text(encoding="utf-8")
    funcs = [f for f in funcoes(codigo) if f["publica"] and (not funcao or f["nome"] == funcao)]
    if funcao and not funcs:
        return f"Não achei a função {funcao} em {arquivo.name}."
    modulo = arquivo.stem
    if not re.fullmatch(r"[A-Za-z_]\w*", modulo):
        return "O nome do arquivo precisa ser um nome de módulo Python válido."
    testes, origem = esqueleto(modulo, funcs), "esqueleto"
    if _ia.disponivel() and funcs:
        resposta = _ia.perguntar(
            f"Escreva testes unittest (Python) para o módulo '{modulo}' abaixo. Teste comportamento real com casos "
            f"normais, de borda e de erro, para: {', '.join(f['qual'] for f in funcs)}. Use 'import {modulo}'. "
            "Não use rede, arquivos do usuário nem bibliotecas fora da padrão (só o que o módulo já importa). "
            f"Responda SÓ com um bloco ```python.\n\n```python\n{codigo[:30000]}\n```", inteligente=True, segundos=120)
        gerado = extrair_blocos(resposta or "")[0]
        if gerado.strip():
            testes, origem = gerado, "IA"
    ok, saida = rodar(codigo, testes, modulo, arquivo.parent)
    if not ok and origem == "IA":
        falhas = re.findall(r"^(?:FAIL|ERROR): (\w+)", saida, re.M)
        testes = "# ATENÇÃO: estes testes falharam na 1ª execução e podem ter achado um bug:\n#   " + \
            ", ".join(falhas or ["veja a saída"]) + "\n" + testes
    pasta_testes = arquivo.parent / "tests" if (arquivo.parent / "tests").is_dir() else arquivo.parent
    destino = pasta_testes / f"test_{modulo}_gerado.py"
    n = 2
    while destino.exists():
        destino = pasta_testes / f"test_{modulo}_gerado{n}.py"
        n += 1
    destino.write_text(testes, encoding="utf-8")
    qtd = len(re.findall(r"^\s*def test_", testes, re.M))
    mostrar(player, f"TESTES — {arquivo.name}", f"{destino}\n{'passaram' if ok else 'NÃO passaram'}\n\n{saida[-1500:]}\n\n"
            + testes[:4000])
    return (f"Gerei {qtd} teste(s) ({origem}) para {len(funcs)} função(ões) de {arquivo.name}; "
            + ("todos passaram. " if ok else "alguns falharam — podem ser bugs no código ou no teste; veja o painel. ")
            + f"Salvei em {destino}.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    arq = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser()
    try:
        if arq.suffix != ".py" or not arq.is_file():
            return f"Não achei o arquivo Python {arq}."
        return gerar(arq, str(p.get("funcao") or "").strip(), player)
    except SyntaxError as e:
        return f"O arquivo tem erro de sintaxe na linha {e.lineno}; corrija antes de gerar testes."
    except Exception as e:
        return f"O gerador de testes falhou: {e}"
