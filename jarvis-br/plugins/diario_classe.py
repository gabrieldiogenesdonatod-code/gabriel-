"""Diário de classe (2.19): turmas, chamada, notas e boletim com média e frequência de cada aluno — para quem dá aula."""
from __future__ import annotations

from plugins._lote2 import P, carregar, guardar, hoje, lista, norm, num1, rodar

PLUGIN = P("diario_classe", "Teacher's class book: classes and students, roll call (absences), grades per assessment, report with average and attendance %.",
           "turma | chamada | nota | boletim | turmas",
           "turma: turma, alunos (comma list; adds). chamada: turma, faltas (names absent, or 'ninguem'), data. "
           "nota: turma, aluno, avaliacao, valor. boletim: turma, aluno (optional).",
           "turma alunos faltas data aluno avaliacao valor")


def achar(alunos: list[str], q: str) -> str | None:
    q = norm(q)
    return next((a for a in alunos if norm(a) == q), None) or next((a for a in alunos if q and q in norm(a)), None)


def frequencia(chamadas: dict, aluno: str) -> float:
    return 100 * (1 - sum(aluno in f for f in chamadas.values()) / len(chamadas)) if chamadas else 100.0


def media(notas: dict, aluno: str) -> float | None:
    vals = [n[aluno] for n in notas.values() if aluno in n]
    return sum(vals) / len(vals) if vals else None


def _go(p, pl):
    a, d = p["action"], carregar("classe", {})
    if a == "turmas":
        return "; ".join(f"{t['nome']} ({len(t['alunos'])} alunos, {len(t['chamadas'])} aulas)" for t in d.values()) or "Nenhuma turma."
    q = norm(p.get("turma"))
    k = q if q in d or a == "turma" else next((x for x in d if q in x), "") if q else next(iter(d), "")
    if a == "turma":
        t = d.setdefault(k, {"nome": str(p.get("turma")).strip(), "alunos": [], "chamadas": {}, "notas": {}})
        t["alunos"] = sorted(set(t["alunos"]) | set(lista(p.get("alunos"))), key=norm)
        guardar("classe", d)
        return f"Turma {t['nome']}: {len(t['alunos'])} aluno(s)."
    t = d.get(k)
    if not t:
        return "Não achei essa turma. Crie com 'turma'."
    if a == "chamada":
        faltou = [x for x in (achar(t["alunos"], n) for n in lista(p.get("faltas")) if not norm(n).startswith("ningu")) if x]
        t["chamadas"][str(p.get("data") or hoje())] = faltou
        guardar("classe", d)
        return f"Chamada feita: {len(t['alunos']) - len(faltou)} presente(s), faltaram {', '.join(faltou) or 'ninguém'}."
    al = achar(t["alunos"], p.get("aluno")) if p.get("aluno") else None
    if a == "nota":
        if not al:
            return "Não achei esse aluno na turma."
        t["notas"].setdefault(str(p.get("avaliacao") or "prova"), {})[al] = num1(p, "valor")
        guardar("classe", d)
        return f"{al}: {num1(p, 'valor'):g} em {p.get('avaliacao') or 'prova'}. Média {media(t['notas'], al):.1f}."

    def linha(x):
        m = media(t["notas"], x)
        return f"{x}: média {'-' if m is None else f'{m:.1f}'}, frequência {frequencia(t['chamadas'], x):.0f}%"
    return "\n".join(linha(x) for x in ([al] if al else t["alunos"])) or "Turma sem alunos."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("turma chamada nota boletim turmas".split(), _go), player, "Diário de classe")
