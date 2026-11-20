"""
Crescimento das crianças (3.0) — para a Cristal Malhas.

O JARVIS guarda a idade e o tamanho que cada criança cliente comprou. Quando ela PROVAVELMENTE já
pulou para o tamanho seguinte, ele avisa e deixa a mensagem pronta para os pais:

    "O Miguel, filho da Dona Márcia, comprou tamanho 2 em março. Hoje, com 3 anos e 2 meses, ele deve
     estar no 3. Mensagem: 'Oi, Márcia! O Miguel já deve estar no 3…'"

    "Jarvis, cadastra o Miguel, filho da Márcia, nasceu 10/09/2023, whats 62 9…, comprou tamanho 2."
    "Jarvis, quais crianças mudaram de tamanho?"     "Jarvis, aniversários das crianças no mês."

A conta usa a tabela média de tamanhos infantis (plugin tabela_tamanhos); cada marca varia.
Todo dia de manhã ele confere e avisa quem mudou (cada criança no máximo uma vez por mês).
"""

from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import Colecao, P, carregar, guardar, numeros, rodar
from plugins.calculadora_datas import ler_data
from plugins.tabela_tamanhos import TAB

PLUGIN = P("crescimento_criancas", "Kids' store: tracks each child's age and last size; flags who probably moved up a size and drafts the parent message.",
           "cadastrar | comprou | alertas | aniversarios | mensagem | listar | apagar",
           "cadastrar: nome (child), responsavel (parent), whats, nascimento (dd/mm/aaaa) or idade ('3 anos', '8 meses'), tamanho. "
           "comprou: nome, tamanho. alertas: who probably changed size. aniversarios: dias (default 30). mensagem: nome.",
           "nome responsavel whats nascimento idade tamanho dias")

C = Colecao("criancas")
ORDEM = [t for t, _, _ in TAB]


def nascimento_de(p: dict, hoje: date) -> date | None:
    if p.get("nascimento"):
        return ler_data(p.get("nascimento"))
    t, n = str(p.get("idade") or "").lower(), numeros(p.get("idade"))
    if not n:
        return None
    meses = int(n[0] if "mes" in t else n[0] * 12 + (n[1] if len(n) > 1 else 0))
    a, m = divmod(hoje.year * 12 + hoje.month - 1 - meses, 12)          # conta de meses exata
    return date(a, m + 1, min(hoje.day, 28))


def meses_de_vida(nasc: date, ref: date) -> int:
    return (ref.year - nasc.year) * 12 + ref.month - nasc.month - (ref.day < nasc.day)


def tamanho_esperado(nasc: date, ref: date) -> str:
    m = max(0, meses_de_vida(nasc, ref))
    return next((t for t, _, mx in TAB if m <= mx), ORDEM[-1])


def pulou(c: dict, ref: date) -> str | None:
    """Tamanho provável hoje, se for MAIOR que o último comprado. Pura."""
    if not c.get("nascimento") or str(c.get("tamanho", "")).upper() not in ORDEM:
        return None
    esperado = tamanho_esperado(date.fromisoformat(c["nascimento"]), ref)
    return esperado if ORDEM.index(esperado) > ORDEM.index(c["tamanho"].upper()) else None


def idade_texto(nasc: date, ref: date) -> str:
    m = meses_de_vida(nasc, ref)
    return f"{m} meses" if m < 24 else f"{m // 12} anos" + (f" e {m % 12} meses" if m % 12 else "")


def mensagem(c: dict, ref: date) -> str:
    novo = pulou(c, ref) or tamanho_esperado(date.fromisoformat(c["nascimento"]), ref)
    pai = (c.get("responsavel") or "").split()[0] if c.get("responsavel") else ""
    return (f"Oi{', ' + pai if pai else ''}! Tudo bem? Pelas minhas contas, {c['nome'].split()[0]} já deve estar usando o tamanho {novo} 😊 "
            f"Chegaram peças lindas nesse tamanho aqui na Cristal Malhas. Quer que eu mande fotos?")


def proximos_aniversarios(cs: list[dict], ref: date, janela: int) -> list[tuple[int, dict, int]]:
    out = []
    for c in cs:
        if not c.get("nascimento"):
            continue
        n = date.fromisoformat(c["nascimento"])
        for ano in (ref.year, ref.year + 1):
            try:
                alvo = date(ano, n.month, n.day)
            except ValueError:
                alvo = date(ano, n.month, 28)
            if alvo >= ref:
                if (alvo - ref).days <= janela:
                    out.append(((alvo - ref).days, c, ano - n.year))
                break
    return sorted(out, key=lambda x: x[0])


def passo(player) -> None:
    import time
    if not 9 <= time.localtime().tm_hour < 19:
        return
    est, hoje = carregar("criancas_avisos", {}), date.today()
    novas = [c for c in C.tudo().values() if pulou(c, hoje) and est.get(c["nome"], "") < (hoje - timedelta(30)).isoformat()]
    if novas:
        for c in novas:
            est[c["nome"]] = hoje.isoformat()
        guardar("criancas_avisos", est)
        from plugins._comum import avisar
        avisar(player, f"{len(novas)} criança(s) cliente(s) provavelmente mudaram de tamanho: " +
               ", ".join(c["nome"] for c in novas[:5]) + ". As mensagens estão prontas em 'alertas'.", "LOJA")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("crescimento_criancas", lambda: passo(player), a_cada_s=3 * 3600, primeira_em_s=480)


def _go(p, pl):
    a, nome, hoje = p["action"], p.get("nome"), date.today()
    if a == "cadastrar":
        nasc = nascimento_de(p, hoje)
        velho = C.pegar(nome) or {}
        c = C.por(nome, {**velho, "responsavel": str(p.get("responsavel") or velho.get("responsavel", "")),
                         "whats": str(p.get("whats") or velho.get("whats", "")),
                         "nascimento": nasc.isoformat() if nasc else velho.get("nascimento"),
                         "tamanho": str(p.get("tamanho") or velho.get("tamanho", "")).upper(),
                         "comprou_em": hoje.isoformat() if p.get("tamanho") else velho.get("comprou_em")})
        extra = f", {idade_texto(nasc, hoje)}, deve usar {tamanho_esperado(nasc, hoje)}" if nasc else ""
        return f"{c['nome']} cadastrado(a){extra}."
    if a == "listar":
        return "\n".join(f"{c['nome']} ({c.get('responsavel') or '?'}): comprou {c.get('tamanho') or '?'}" +
                         (f", hoje {idade_texto(date.fromisoformat(c['nascimento']), hoje)}" if c.get("nascimento") else "")
                         for c in C.tudo().values()) or "Nenhuma criança cadastrada."
    if a == "alertas":
        mudaram = [c for c in C.tudo().values() if pulou(c, hoje)]
        if not mudaram:
            return "Nenhuma criança mudou de tamanho pelas contas. Tudo em dia."
        from plugins._comum import mostrar
        mostrar(pl, "CRIANÇAS QUE MUDARAM DE TAMANHO", "\n\n".join(
            f"{c['nome']} ({c.get('responsavel') or '?'}, {c.get('whats') or 'sem whats'}): comprou {c['tamanho']}, deve estar no "
            f"{pulou(c, hoje)}\n  \"{mensagem(c, hoje)}\"" for c in mudaram))
        return f"{len(mudaram)} criança(s) provavelmente mudaram de tamanho: " + ", ".join(
            f"{c['nome']} ({c['tamanho']} → {pulou(c, hoje)})" for c in mudaram[:6]) + ". As mensagens estão no painel."
    if a == "aniversarios":
        ans = proximos_aniversarios(list(C.tudo().values()), hoje, int(numeros(p.get("dias"))[0]) if numeros(p.get("dias")) else 30)
        return "; ".join(f"{c['nome']} faz {anos} ano{'s' if anos > 1 else ''} {'hoje' if d == 0 else f'em {d} dia(s)'}" for d, c, anos in ans) or \
            "Nenhum aniversário de criança cliente no período."
    c = C.pegar(nome)
    if not c:
        return "Não achei essa criança."
    if a == "apagar":
        C.tirar(nome)
        return "Apagado(a)."
    if a == "comprou":
        c.update(tamanho=str(p.get("tamanho") or c.get("tamanho", "")).upper(), comprou_em=hoje.isoformat())
        C.por(c["nome"], c)
        return f"Anotado: {c['nome']} agora veste {c['tamanho']}."
    if not c.get("nascimento"):
        return "Preciso da data de nascimento ou da idade dessa criança."
    return mensagem(c, hoje)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("cadastrar comprou alertas aniversarios mensagem listar apagar".split(), _go), player,
                 "Crescimento")
