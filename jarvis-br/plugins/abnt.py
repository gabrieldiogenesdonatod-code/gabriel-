"""ABNT (2.19): monta referências de livro, site e artigo e a citação no texto, no padrão das normas NBR 6023 e 10520."""
from __future__ import annotations

from datetime import date

from plugins._lote2 import P, rodar

PLUGIN = P("abnt", "ABNT formatting (NBR 6023/10520): reference for book, website or journal article, and in-text citation.",
           "livro | site | artigo | citacao",
           "autor ('Nome Sobrenome; Outro Autor'), titulo, subtitulo, edicao, local, editora, ano; site: site (site name), url; "
           "artigo: revista, volume, numero, paginas; citacao: autor, ano, pagina.",
           "autor titulo subtitulo edicao local editora ano site url revista volume numero paginas pagina")

MESES = "jan. fev. mar. abr. maio jun. jul. ago. set. out. nov. dez.".split()
PARTICULAS = {"da", "de", "do", "das", "dos", "e"}
SUFIXOS = {"filho", "junior", "júnior", "neto", "sobrinho"}


def sobrenome(nome: str) -> tuple[str, str]:
    """'João da Silva Filho' → ('SILVA FILHO', 'João da'). Pura."""
    ps = nome.strip().split()
    if len(ps) < 2:
        return nome.strip().upper(), ""
    corte = len(ps) - (2 if ps[-1].lower() in SUFIXOS and len(ps) > 2 else 1)
    return " ".join(ps[corte:]).upper(), " ".join(ps[:corte])


def autores(texto: str) -> str:
    nomes = [n for n in str(texto or "").replace(" e ", ";").split(";") if n.strip()]
    if not nomes:
        return ""
    fmt = [", ".join(x for x in sobrenome(n) if x) for n in nomes]
    return (fmt[0] + " et al" if len(fmt) > 3 else "; ".join(fmt)) + "."


def acesso(d: date) -> str:
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def _go(p, pl):
    a = p["action"]
    g = lambda k: str(p.get(k) or "").strip()  # noqa: E731
    if a == "citacao":
        sn = sobrenome(g("autor").split(";")[0])[0].title()
        return f"({sn}, {g('ano') or 's.d.'}" + (f", p. {g('pagina')}" if g("pagina") else "") + ")"
    titulo = g("titulo") + (f": {g('subtitulo')}" if g("subtitulo") else "")
    aut = autores(g("autor"))
    if a == "livro":
        ed = f" {g('edicao').rstrip('.ªa ')}. ed." if g("edicao") and g("edicao").strip(" .ªa") not in ("1", "") else ""
        return f"{aut} {titulo}.{ed} {g('local') or '[S. l.]'}: {g('editora') or '[s. n.]'}, {g('ano') or '[s. d.]'}.".strip() + " (título em negrito)"
    if a == "artigo":
        partes = [g("local"), f"v. {g('volume')}" if g("volume") else "", f"n. {g('numero')}" if g("numero") else "",
                  f"p. {g('paginas')}" if g("paginas") else "", g("ano")]
        return f"{aut} {titulo}. {g('revista')}, " + ", ".join(x for x in partes if x) + ". (nome da revista em negrito)"
    return (f"{aut} {titulo}. {g('site')}".strip() + (f", {g('ano')}" if g("ano") else "") +
            f". Disponível em: {g('url')}. Acesso em: {acesso(date.today())}.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("livro site artigo citacao".split(), _go), player)
