"""
Ditado de código (fork PT-BR 1.5).

Você EXPLICA a lógica falando — em quantas frases quiser — e o JARVIS
escreve o arquivo Python, escreve os TESTES, roda tudo numa pasta isolada e
mostra o resultado. Se um teste falha, ele tenta corrigir sozinho (uma vez).

    "Jarvis, vou ditar um código: calculadora de troco"
    "a função recebe o valor da compra e o valor pago…"   (várias falas)
    "e se o pago for menor, devolve erro"
    "Jarvis, pronto"                → escreve, testa, mostra
    "Jarvis, muda para aceitar centavos"   → corrige e testa de novo
    "Jarvis, abre no VS Code"

Os arquivos vão para Documentos\\JARVIS\\codigo\\. Antes de rodar, o código passa
pela mesma inspeção do criador de plugins (nada de apagar arquivos, shell=True,
eval…); se tiver algo assim, ele mostra e não roda sem você confirmar.
Precisa da chave de IA (escrever código a partir da fala é trabalho do modelo).
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

from plugins._comum import abrir_no_sistema, confirmar, iniciar, mostrar, pasta_usuario

PLUGIN = {
    "name": "ditado_codigo",
    "brief": "Dictate program logic by voice; JARVIS writes Python + tests, runs them in a sandbox, shows results.",
    "description": (
        "Code dictation: the user explains logic by voice over several turns. action='comecar' with nome; "
        "'adicionar' with texto (each new explanation, verbatim); 'pronto' writes the Python file and unittest "
        "tests, runs them in an isolated folder and fixes once if needed; 'corrigir' with texto (change request); "
        "'abrir' opens the file in the editor; 'status'; 'cancelar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "comecar | adicionar | pronto | corrigir | abrir | status | cancelar"},
            "nome": {"type": "STRING"}, "texto": {"type": "STRING"},
        },
        "required": [],
    },
}

_sessao = {"nome": "", "partes": [], "arquivo": None, "testes": None}


def _pasta() -> Path:
    p = pasta_usuario("Documents") / "JARVIS" / "codigo"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nome_arquivo(nome: str) -> str:
    from plugins.criador_ferramentas import slug
    return slug(nome or "programa", 40) or "programa"


def extrair_blocos(texto: str) -> tuple[str, str]:
    """(código, testes) de uma resposta com dois blocos ```python (pura)."""
    blocos = re.findall(r"```(?:python|py)?\s*\n(.*?)```", texto or "", re.S)
    if len(blocos) >= 2:
        return blocos[0].strip() + "\n", blocos[1].strip() + "\n"
    return (blocos[0].strip() + "\n" if blocos else ""), ""


def rodar_testes(codigo: str, testes: str, modulo: str, timeout: float = 40) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="jarvis_ditado_") as tmp:
        (Path(tmp) / f"{modulo}.py").write_text(codigo, encoding="utf-8")
        (Path(tmp) / f"test_{modulo}.py").write_text(testes, encoding="utf-8")
        from plugins.laboratorio import rodar_uma
        r = rodar_uma(Path(tmp), [sys.executable, "-m", "unittest", "-v", f"test_{modulo}"], timeout)
        return r["ok"], r["fim"]


def _gerar(pedido: str, modulo: str, anterior: str = "", erro: str = "") -> tuple[str, str]:
    from plugins import _ia
    prompt = ("Você é um programador Python experiente. Escreva um módulo Python 3 limpo, com docstrings e comentários "
              f"em português do Brasil, chamado {modulo}.py, e um arquivo de testes unittest test_{modulo}.py que "
              f"importa de {modulo} e cobre os casos descritos (inclusive erros). Sem dependências fora da "
              "biblioteca padrão, sem acessar rede nem apagar arquivos.\n\n"
              f"O QUE O USUÁRIO DITOU:\n{pedido}\n")
    if anterior:
        prompt += f"\nCÓDIGO ATUAL:\n```python\n{anterior[:9000]}\n```\n"
    if erro:
        prompt += f"\nOS TESTES FALHARAM ASSIM — corrija o código (ou o teste, se o teste estiver errado):\n{erro[-3000:]}\n"
    prompt += "\nResponda com DOIS blocos ```python: primeiro o módulo, depois os testes. Nada além disso."
    resp = _ia.perguntar(prompt, inteligente=True, segundos=90)
    return extrair_blocos(resp or "")


def construir(pedido: str, nome: str, player, anterior: str = "") -> str:
    from plugins import _ia
    from plugins.criador_ferramentas import analisar_seguranca
    if not _ia.disponivel():
        return "Para escrever código a partir da fala eu preciso da chave de IA configurada."
    modulo = _nome_arquivo(nome)
    codigo, testes = _gerar(pedido, modulo, anterior)
    if not codigo:
        return "O modelo não devolveu código. Tente explicar de novo."
    destino = _pasta() / f"{modulo}.py"
    destino_t = _pasta() / f"test_{modulo}.py"
    seg = analisar_seguranca(codigo)

    def testar_e_salvar() -> str:
        nonlocal codigo, testes
        ok, saida = rodar_testes(codigo, testes, modulo) if testes else (True, "(sem testes)")
        tentativas = 0
        while not ok and tentativas < 1:
            tentativas += 1
            novo_c, novo_t = _gerar(pedido, modulo, codigo, saida)
            if novo_c:
                codigo, testes = novo_c, novo_t or testes
                ok, saida = rodar_testes(codigo, testes, modulo)
        destino.write_text(codigo, encoding="utf-8")
        destino_t.write_text(testes, encoding="utf-8")
        _sessao.update(arquivo=str(destino), testes=str(destino_t))
        mostrar(player, f"DITADO — {modulo}.py", f"{'✔ TESTES PASSARAM' if ok else '✖ TESTES FALHARAM'}\n\n"
                + saida[-1500:] + "\n\n" + "─" * 60 + f"\n{codigo}\n" + "─" * 60 + f"\n{testes}")
        n = len(re.findall(r"\bdef test", testes))
        return (f"Escrevi {modulo}.py com {n} teste(s): " + ("todos passaram." if ok else "ainda há falha; está no painel.")
                + f" Salvei em {destino.parent}.")

    if seg["bloqueios"]:
        mostrar(player, f"DITADO — {modulo}.py (não rodei)", "\n".join(seg["bloqueios"]) + "\n\n" + codigo)
        return confirmar(f"ditado:{modulo}", f"Rodar os testes de {modulo}.py?",
                         "O código faz coisas que eu não rodo sem você ver:\n" + "\n".join(seg["bloqueios"][:5]),
                         testar_e_salvar)
    return testar_e_salvar()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    texto = str(p.get("texto") or "").strip()
    try:
        if acao == "comecar":
            _sessao.update(nome=str(p.get("nome") or "programa"), partes=[texto] if texto else [], arquivo=None)
            return "Pode ditar: explique a lógica em quantas frases quiser. Quando terminar, diga 'pronto'."
        if acao == "adicionar":
            if not texto:
                return "Não ouvi a explicação."
            _sessao["partes"].append(texto)
            return f"Anotado ({len(_sessao['partes'])} parte(s)). Continue, ou diga 'pronto'."
        if acao == "pronto":
            if texto:
                _sessao["partes"].append(texto)
            if not _sessao["partes"]:
                return "Ainda não ditou nada. Comece explicando o que o programa deve fazer."
            return construir("\n".join(f"- {x}" for x in _sessao["partes"]), _sessao["nome"], player)
        if acao == "corrigir":
            if not _sessao.get("arquivo"):
                return "Ainda não escrevi nenhum código nesta sessão."
            _sessao["partes"].append(f"MUDANÇA PEDIDA: {texto}")
            atual = Path(_sessao["arquivo"]).read_text(encoding="utf-8")
            return construir("\n".join(f"- {x}" for x in _sessao["partes"]), _sessao["nome"], player, atual)
        if acao == "abrir":
            if not _sessao.get("arquivo"):
                return "Ainda não há arquivo."
            vscode = shutil.which("code")                     # no Windows é o code.cmd: precisa do caminho inteiro
            if not (vscode and iniciar([vscode, _sessao["arquivo"]])) and not abrir_no_sistema(_sessao["arquivo"]):
                return f"Não consegui abrir; o arquivo está em {_sessao['arquivo']}."
            return "Abri o arquivo."
        if acao == "cancelar":
            _sessao.update(nome="", partes=[], arquivo=None)
            return "Ditado cancelado."
        if _sessao["partes"]:
            return f"Ditando '{_sessao['nome']}': {len(_sessao['partes'])} parte(s). Diga 'pronto' para eu escrever."
        if _sessao["nome"]:
            return f"Ditado de '{_sessao['nome']}' começou, mas ainda sem explicação. Pode falar a lógica."
        return "Nenhum ditado em andamento. Diga 'vou ditar um código' e o nome dele."
    except Exception as e:
        return f"O ditado falhou: {e}"
