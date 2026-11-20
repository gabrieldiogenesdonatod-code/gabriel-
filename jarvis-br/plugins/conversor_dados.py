"""Conversor de dados (2.18): valida/formata JSON, CSV↔JSON e tabela Markdown, de texto ou de arquivo."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from plugins._lote2 import P, rodar

PLUGIN = P("conversor_dados", "Data formats: validate/pretty-print JSON (error line), CSV to JSON, JSON to CSV, CSV/JSON to Markdown table. Text or file path.",
           "validar_json | csv_para_json | json_para_csv | markdown",
           "texto = data or a file path; saves next to the file when a path is given.", "texto")


def _ler(t: str) -> tuple[str, Path | None]:
    try:
        pth = Path(t.strip().strip('"'))
        if len(t) < 260 and pth.is_file():
            return pth.read_text(encoding="utf-8-sig"), pth
    except OSError:
        pass
    return t, None


def csv_para_lista(t: str) -> list[dict]:
    primeira = t.splitlines()[0] if t.strip() else ""
    delim = max(",;\t", key=primeira.count) if primeira else ","
    return list(csv.DictReader(io.StringIO(t), delimiter=delim))


def lista_para_csv(d: list[dict]) -> str:
    campos = list(dict.fromkeys(k for x in d for k in x))
    s = io.StringIO()
    w = csv.DictWriter(s, campos)
    w.writeheader()
    w.writerows(d)
    return s.getvalue()


def markdown(d: list[dict]) -> str:
    campos = list(dict.fromkeys(k for x in d for k in x))
    linhas = ["| " + " | ".join(campos) + " |", "|" + "---|" * len(campos)]
    linhas += ["| " + " | ".join(str(x.get(c, "")) for c in campos) + " |" for x in d]
    return "\n".join(linhas)


def _go(p, pl):
    a = str(p.get("action")).lower()
    t, pth = _ler(str(p.get("texto") or ""))
    if a == "validar_json":
        try:
            out, ext = json.dumps(json.loads(t), indent=2, ensure_ascii=False), ".json"
        except json.JSONDecodeError as e:
            return f"JSON inválido na linha {e.lineno}, coluna {e.colno}: {e.msg}."
    elif a == "csv_para_json":
        out, ext = json.dumps(csv_para_lista(t), indent=2, ensure_ascii=False), ".json"
    elif a == "json_para_csv":
        out, ext = lista_para_csv(json.loads(t)), ".csv"
    else:
        d = json.loads(t) if t.strip().startswith("[") else csv_para_lista(t)
        out, ext = markdown(d), ".md"
    if pth:
        dest = pth.with_name(pth.stem + "_convertido" + ext)
        dest.write_text(out, encoding="utf-8")
        return f"Salvo em {dest}."
    return out


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("validar_json csv_para_json json_para_csv markdown".split(), _go), player, "Dados")
