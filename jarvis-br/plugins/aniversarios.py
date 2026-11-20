"""
Aniversários (fork PT-BR 1.6).

Guarda as datas, avisa de manhã no dia (e uma semana antes, para dar tempo
de comprar presente) e sugere uma mensagem personalizada — no seu estilo de
escrita, se o JARVIS já aprendeu como você escreve.

    "Jarvis, o aniversário da minha vó é 12 de março"
    "Jarvis, aniversário do Pedro 05/09, ele é meu primo"
    "Jarvis, quem faz aniversário este mês?"
    "Jarvis, escreve uma mensagem de parabéns para o Pedro"
    "Jarvis, importa os aniversários dos meus contatos"   (arquivo .vcf exportado dos contatos)
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

from plugins._comum import MEMORIA, falar, gravar_json, ler_json, mostrar, pasta_usuario

PLUGIN = {
    "name": "aniversarios",
    "brief": "Birthdays: stores dates, reminds on the day and a week before, suggests a personalized message.",
    "description": (
        "Birthdays. action='adicionar' with nome + data ('12 de março', '05/09', '05/09/1990') + optional relacao "
        "(grandmother, cousin, client...); 'remover' with nome; 'listar' (optional periodo = 'mes', 'semana'); "
        "'mensagem' with nome (writes a birthday message); 'importar' with arquivo (.vcf contacts export)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "adicionar | remover | listar | mensagem | importar"},
                       "nome": {"type": "STRING"}, "data": {"type": "STRING"}, "relacao": {"type": "STRING"},
                       "periodo": {"type": "STRING"}, "arquivo": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "aniversarios.json"
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_iniciado = threading.Event()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode().strip()


def ler_data(texto: str) -> tuple[int, int, int | None] | None:
    """'12 de março', '12/03', '12/03/1990', '1990-03-12' → (dia, mês, ano|None) (pura)."""
    t = _dobrar(texto)
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    m = re.search(r"(\d{1,2})\s*(?:de\s+)?([a-z]{3,})(?:\s+de\s+(\d{4}))?", t)
    if m:
        mes = next((n for nome, n in MESES.items() if nome.startswith(m.group(2)[:3])), None)
        if mes:
            return int(m.group(1)), mes, int(m.group(3)) if m.group(3) else None
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", t)
    if m:
        ano = int(m.group(3)) if m.group(3) else None
        if ano is not None and ano < 100:
            ano += 1900 if ano > 30 else 2000
        return int(m.group(1)), int(m.group(2)), ano
    return None


def proximo(dia: int, mes: int, hoje: date) -> date:
    """Próxima data do aniversário (29/02 vira 28/02 em ano não bissexto) (pura)."""
    for ano in (hoje.year, hoje.year + 1):
        try:
            d = date(ano, mes, dia)
        except ValueError:
            d = date(ano, mes, 28)
        if d >= hoje:
            return d
    return date(hoje.year + 1, mes, min(dia, 28))


def proximos(lista: list[dict], hoje: date, dias: int) -> list[tuple[dict, date]]:
    saida = [(a, proximo(a["dia"], a["mes"], hoje)) for a in lista]
    return sorted([(a, d) for a, d in saida if (d - hoje).days <= dias], key=lambda x: x[1])


def carregar() -> list[dict]:
    return (ler_json(_ARQ, {}) or {}).get("pessoas", [])


def de_hoje() -> list[dict]:
    """Usado pelo boot e pelo aviso da manhã."""
    hoje = date.today()
    return [a for a, d in proximos(carregar(), hoje, 0) if d == hoje]


def idade(a: dict, quando: date) -> int | None:
    return quando.year - int(a["ano"]) if a.get("ano") else None


def ler_vcf(texto: str) -> list[dict]:
    """Contatos .vcf com BDAY → pessoas (pura)."""
    pessoas = []
    for bloco in re.split(r"BEGIN:VCARD", texto or "")[1:]:
        nome = re.search(r"^FN[^:]*:(.+)$", bloco, re.M)
        bday = re.search(r"^BDAY[^:]*:(?:--)?(\d{4})?-?(\d{2})-?(\d{2})", bloco, re.M)
        if nome and bday:
            pessoas.append({"nome": nome.group(1).strip(), "dia": int(bday.group(3)), "mes": int(bday.group(2)),
                            "ano": int(bday.group(1)) if bday.group(1) and bday.group(1) != "1604" else None,
                            "relacao": ""})
    return pessoas


def mensagem(a: dict) -> str:
    from plugins import _ia
    quando = proximo(a["dia"], a["mes"], date.today())
    anos = idade(a, quando)
    if _ia.disponivel():
        try:
            from plugins.estilo_escrita import carregar as estilo, descrever
            meu = estilo()
        except Exception:
            meu = {}
        r = _ia.perguntar(
            f"Escreva uma mensagem de feliz aniversário para {a['nome']}" + (f" ({a['relacao']})" if a.get("relacao") else "")
            + (f", que faz {anos} anos" if anos else "") + ". Calorosa, pessoal, 2 a 4 frases, português do Brasil."
            + (f" Escreva no estilo de quem manda: {descrever(meu)} Exemplos: {' | '.join(meu.get('exemplos', [])[-8:])}"
               if meu else "") + " Responda só a mensagem.", False, 30)
        if r:
            return r.strip()
    return (f"Feliz aniversário, {a['nome'].split()[0]}! 🎉 Que esse novo ano venha cheio de saúde, alegria e "
            "conquistas. Conte sempre comigo!")


def _laco(player) -> None:
    time.sleep(90)
    while True:
        try:
            agora = datetime.now()
            d = ler_json(_ARQ, {}) or {}
            if agora.hour >= 8 and d.get("avisado") != agora.date().isoformat():
                hoje = agora.date()
                lista = d.get("pessoas", [])
                hoje_ = [a for a, q in proximos(lista, hoje, 0)]
                semana = [(a, q) for a, q in proximos(lista, hoje, 7) if (q - hoje).days == 7]
                d["avisado"] = hoje.isoformat()
                gravar_json(_ARQ, d)
                if hoje_ or semana:
                    texto = ("Hoje é aniversário de " + ", ".join(a["nome"] for a in hoje_) + ". ") if hoje_ else ""
                    texto += ("Daqui a uma semana: " + ", ".join(a["nome"] for a, _q in semana) + ".") if semana else ""
                    falar(player, f"[ANIVERSÁRIOS] Avise em 1–2 frases: {texto} Ofereça escrever a mensagem de parabéns. "
                                  "Não chame nenhuma ferramenta.")
        except Exception as e:
            print(f"[Aniversários] {e}")
        time.sleep(900)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="aniversarios").start()


def _achar(nome: str) -> dict | None:
    t = _dobrar(nome)
    return next((a for a in carregar() if _dobrar(a["nome"]) == t), None) or \
        next((a for a in carregar() if t and t in _dobrar(a["nome"])), None)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("pessoas", [])
        if acao == "adicionar":
            nome, data = str(p.get("nome") or "").strip(), ler_data(str(p.get("data") or ""))
            if not nome or not data:
                return "Diga o nome e a data (ex.: 12 de março)."
            dia, mes, ano = data
            d["pessoas"] = [a for a in d["pessoas"] if _dobrar(a["nome"]) != _dobrar(nome)]
            d["pessoas"].append({"nome": nome, "dia": dia, "mes": mes, "ano": ano, "relacao": str(p.get("relacao") or "")})
            gravar_json(_ARQ, d)
            faltam = (proximo(dia, mes, date.today()) - date.today()).days
            return f"Anotado: {nome}, {dia:02d}/{mes:02d}. " + ("É hoje!" if faltam == 0 else f"Faltam {faltam} dia(s).")
        if acao == "remover":
            antes = len(d["pessoas"])
            d["pessoas"] = [a for a in d["pessoas"] if _dobrar(a["nome"]) != _dobrar(str(p.get("nome") or ""))]
            gravar_json(_ARQ, d)
            return "Removido." if len(d["pessoas"]) < antes else "Não achei esse nome."
        if acao == "mensagem":
            a = _achar(str(p.get("nome") or ""))
            if not a:
                return "Não tenho o aniversário dessa pessoa. Diga a data primeiro."
            texto = mensagem(a)
            mostrar(player, f"PARABÉNS — {a['nome']}", texto)
            return f"Sugestão de mensagem: {texto}"
        if acao == "importar":
            arq = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser() if p.get("arquivo") else \
                next(iter(sorted(pasta_usuario("Downloads").glob("*.vcf"), key=lambda x: -x.stat().st_mtime)), None)
            if not arq or not arq.is_file():
                return "Exporte os contatos como .vcf (app Contatos → Exportar) e salve em Downloads."
            novos = ler_vcf(arq.read_text(encoding="utf-8", errors="replace"))
            nomes = {_dobrar(a["nome"]) for a in d["pessoas"]}
            d["pessoas"] += [a for a in novos if _dobrar(a["nome"]) not in nomes]
            gravar_json(_ARQ, d)
            return f"Importei {len(novos)} aniversário(s) de {arq.name}."
        dias = 7 if "semana" in str(p.get("periodo") or "") else 31 if "mes" in _dobrar(str(p.get("periodo") or "")) else 60
        lista = proximos(d["pessoas"], date.today(), dias)
        if not lista:
            return f"Ninguém faz aniversário nos próximos {dias} dias." if d["pessoas"] else \
                "Nenhum aniversário anotado. Diga, por exemplo: o aniversário da minha vó é 12 de março."
        mostrar(player, "ANIVERSÁRIOS", "\n".join(f"{q:%d/%m} ({(q - date.today()).days} d)  {a['nome']}"
                                                   + (f" — {a['relacao']}" if a.get("relacao") else "")
                                                   + (f", {idade(a, q)} anos" if idade(a, q) else "") for a, q in lista))
        return "Próximos: " + ", ".join(f"{a['nome']} em {q:%d/%m}" for a, q in lista[:6]) + "."
    except Exception as e:
        return f"Os aniversários falharam: {e}"
