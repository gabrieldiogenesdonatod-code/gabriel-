"""
Ajudante dos lotes 2 e 3 (fork PT-BR 2.18/2.19): base comum dos plugins pequenos e econômicos.

Começa com "_": o carregador pula este arquivo.

Economia de token: todo plugin daqui declara tier="extra" e um "brief" curto. Desde a 2.19 as
ferramentas extras entram no catálogo só pelo NOME (core/orcamento_ferramentas.py); a descrição
só é enviada quando o modelo pede (plugin `catalogo`). Todos os parâmetros são STRING.

    P(...)        monta o dicionário PLUGIN
    rodar(...)    despacha a 'action': aceita sinônimos ("add" → adicionar), erro de digitação
                  e 'ajuda' em qualquer plugin; nunca levanta exceção
    Colecao       itens com nome em memory/lote2/<arquivo>.json; acha por nome aproximado e
                  manda o que foi apagado para a lixeira (plugin `lixeira`)
    carregar/guardar, num1, pagina, dias_ate   utilidades
"""

from __future__ import annotations

import difflib
import html as _html
import re
import sys
import time
import unicodedata
from datetime import date

from plugins._comum import MEMORIA, avisar, gravar_json, ler_json, mostrar, num  # noqa: F401

PASTA = MEMORIA / "lote2"          # os testes trocam por uma pasta temporária

# Palavras que querem dizer a mesma ação. A primeira que o plugin tiver é a usada.
GRUPOS = (
    ("adicionar", "add", "novo", "nova", "criar", "cadastrar", "salvar", "incluir", "registrar", "anotar", "guardar"),
    ("listar", "lista", "list", "ver", "mostrar", "todos", "todas", "show", "status", "resumo"),
    ("apagar", "remover", "excluir", "deletar", "delete", "remove"),
    ("buscar", "procurar", "search", "find", "achar", "pesquisar"),
    ("iniciar", "comecar", "start"),
    ("parar", "stop", "encerrar", "terminar"),
)
PEDIR_AJUDA = ("ajuda", "help", "?", "como_usar", "como_usa")


def P(nome: str, brief: str, acoes: str, desc: str, props: str = "") -> dict:
    """PLUGIN compacto. acoes='a | b | c'; props='texto valor' (todos STRING)."""
    propriedades = {"action": {"type": "STRING", "description": acoes}}
    for k in props.split():
        propriedades[k] = {"type": "STRING"}
    return {"name": nome, "tier": "extra", "brief": brief, "description": desc,
            "parameters": {"type": "OBJECT", "properties": propriedades, "required": ["action"]}}


def norm(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()


def lista(texto) -> list[str]:
    return [x.strip() for x in re.split(r",|;|\n|\s+e\s+", str(texto or "")) if x.strip()]


def numeros(texto) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", str(texto or ""))]


def num1(p: dict, chave: str, padrao: float = 0.0) -> float:
    """Primeiro número do parâmetro (aceita '1,5', 'R$ 20', '3 kg')."""
    n = numeros(p.get(chave))
    return n[0] if n else padrao


def reais(v: float) -> str:
    s = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def hoje() -> str:
    return time.strftime("%Y-%m-%d")


def dias_ate(iso: str, ref: date | None = None) -> int:
    return (date.fromisoformat(iso) - (ref or date.today())).days


def carregar(nome: str, padrao):
    d = ler_json(PASTA / f"{nome}.json", None)
    return padrao if d is None else d


def guardar(nome: str, dados) -> None:
    gravar_json(PASTA / f"{nome}.json", dados)


def pagina(tipo: str, titulo: str, corpo: str, abrir: bool = True) -> str:
    """Página HTML simples para imprimir (Documentos/JARVIS/<tipo>). Devolve o caminho."""
    from plugins._comum import abrir_no_sistema, pasta_jarvis
    arq = pasta_jarvis(tipo) / f"{re.sub(r'[^a-z0-9]+', '_', norm(titulo))[:40] or 'pagina'}_{time.strftime('%Y%m%d_%H%M%S')}.html"
    arq.write_text("<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>" + _html.escape(titulo) + "</title>"
                   "<style>body{font-family:sans-serif;max-width:800px;margin:24px auto;padding:0 12px}"
                   "table{border-collapse:collapse}td,th{border:1px solid #444;padding:6px 10px;text-align:center}"
                   "@media print{.np{display:none}}</style><h2>" + _html.escape(titulo) + "</h2>" + corpo + "</html>",
                   encoding="utf-8")
    if abrir:
        abrir_no_sistema(str(arq))
    return str(arq)


def escolher_acao(a: str, acoes) -> str | None:
    """Ação pedida → ação que o plugin tem (igual, sinônimo, começo ou erro de digitação). Pura."""
    nomes = list(acoes)
    if a in nomes:
        return a
    for grupo in GRUPOS:
        if a in grupo:
            for candidata in grupo:
                if candidata in nomes:
                    return candidata
    comeco = [n for n in nomes if len(a) >= 3 and (n.startswith(a) or a.startswith(n))]
    if len(comeco) == 1:
        return comeco[0]
    perto = difflib.get_close_matches(a, nomes, n=1, cutoff=0.8)
    return perto[0] if perto else None


def rodar(p: dict, acoes: dict, player=None, titulo: str = "") -> str:
    """Chama acoes[action](p, player). Texto longo também vai para a tela."""
    p = dict(p or {})
    pedido = norm(p.get("action")).replace(" ", "_") or next(iter(acoes))
    a = escolher_acao(pedido, acoes)
    if a is None:
        if pedido in PEDIR_AJUDA:
            plug = sys._getframe(1).f_globals.get("PLUGIN") or {}
            return f"{plug.get('name', titulo)}: {plug.get('description', '')} Ações: {', '.join(acoes)}."
        return f"Ação '{pedido}' não existe. Use: {', '.join(acoes)}."
    p["action"] = a
    try:
        r = str(acoes[a](p, player) or "Feito.")
    except Exception as e:
        return f"{titulo or 'O plugin'} falhou: {e}"
    if titulo and (len(r) > 220 or "\n" in r):
        mostrar(player, titulo.upper(), r)
    return r


class Colecao:
    """Itens com nome (chave sem acento), gravados em JSON."""

    def __init__(self, arquivo: str):
        self.arquivo = arquivo

    @property
    def caminho(self):
        return PASTA / f"{self.arquivo}.json"

    def tudo(self) -> dict:
        d = ler_json(self.caminho, {})
        return d if isinstance(d, dict) else {}

    def salvar(self, d: dict) -> None:
        gravar_json(self.caminho, d)

    def chave(self, nome) -> str | None:
        """Chave do item: nome igual, único que contém o texto, ou o mais parecido (voz erra nomes)."""
        d, k = self.tudo(), norm(nome)
        if k in d:
            return k
        if len(k) < 2:
            return None
        contem = [x for x in d if k in x or x in k]
        if len(contem) == 1:
            return contem[0]
        perto = difflib.get_close_matches(k, list(d), n=1, cutoff=0.8)
        return perto[0] if perto else None

    def pegar(self, nome):
        k = self.chave(nome)
        return self.tudo().get(k) if k is not None else None

    def por(self, nome, dados: dict) -> dict:
        d = self.tudo()
        dados = {**dados, "nome": str(nome).strip()}
        d[norm(nome)] = dados
        self.salvar(d)
        return dados

    def tirar(self, nome) -> bool:
        d, k = self.tudo(), self.chave(nome)
        if k is None:
            return False
        item = d.pop(k)
        self.salvar(d)
        lixo = carregar("_lixeira", [])
        lixo.append({"colecao": self.arquivo, "item": item, "quando": hoje()})
        guardar("_lixeira", lixo[-200:])
        return True

    def nomes(self) -> list[str]:
        return [v.get("nome", k) for k, v in self.tudo().items()]


def falar_ja(player, texto: str) -> None:
    """Fala uma frase exata (guias de respiração, jogos). Sem player: só imprime."""
    from plugins._comum import falar, registrar
    registrar(player, f"JARVIS: {texto}")
    falar(player, f"[GUIA] Diga exatamente, sem chamar ferramenta: {texto}")
