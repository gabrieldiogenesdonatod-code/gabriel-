"""
Modo aula (fork PT-BR 1.9).

    "Jarvis, grava essa aula de banco de dados"   ...   "Jarvis, termina a aula"
    "Jarvis, me faz 5 perguntas sobre a aula de ontem"
    "Jarvis, abre o resumo da última aula"         "Jarvis, quais aulas eu gravei?"

Grava o som do PC (aula online, vídeo) e o microfone (aula presencial),
transcreve com o Whisper (faster-whisper no PC; sem ele, a chave do Gemini) e
entrega em Markdown: resumo, tópicos principais, conceitos, tarefas e dúvidas.
Fica tudo em Documentos\\JARVIS\\aulas. Usa a mesma gravação da ata de chamadas.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from plugins._comum import abrir_no_sistema, mostrar, pasta_usuario

PLUGIN = {
    "name": "modo_aula",
    "brief": "Class mode: records a lecture (PC audio + mic), transcribes, writes summary/topics/tasks in Markdown, "
             "and quizzes the user about past classes.",
    "description": (
        "Class/lecture mode. action='gravar' (optional titulo) starts recording; 'parar' stops, transcribes and writes "
        "summary, main topics, concepts and tasks; 'perguntas' with quando ('ontem', 'hoje', 'última', a title word) "
        "+ optional quantas makes quiz questions about that class (ask them one at a time, wait for the answer, then "
        "correct); 'listar'; 'abrir' with quando."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "gravar | parar | perguntas | listar | abrir | status"},
                       "titulo": {"type": "STRING"}, "quando": {"type": "STRING"}, "quantas": {"type": "INTEGER"}},
        "required": [],
    },
}


def pasta_aulas() -> Path:
    return pasta_usuario("Documents") / "JARVIS" / "aulas"


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode().strip()


def aulas(base: Path | None = None) -> list[dict]:
    base = base or pasta_aulas()
    saida = []
    for arq in sorted(base.glob("*/aula.md")) if base.exists() else []:
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{4})_?(.*)", arq.parent.name)
        if not m:
            continue
        quando = datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M")
        saida.append({"arquivo": arq, "quando": quando, "titulo": m.group(3).replace("-", " ")})
    return saida


def escolher_aula(lista: list[dict], quando: str, hoje: datetime | None = None) -> dict | None:
    """'ontem', 'hoje', 'anteontem', 'última', 'de banco de dados', '03/11' → aula (pura)."""
    if not lista:
        return None
    hoje = hoje or datetime.now()
    t = _dobrar(quando)
    dia = None
    if "anteontem" in t:
        dia = (hoje - timedelta(days=2)).date()
    elif "ontem" in t:
        dia = (hoje - timedelta(days=1)).date()
    elif "hoje" in t:
        dia = hoje.date()
    else:
        m = re.search(r"(\d{1,2})/(\d{1,2})", t)
        if m:
            try:
                dia = hoje.replace(day=int(m.group(1)), month=int(m.group(2))).date()
            except ValueError:
                dia = None
    if dia:
        do_dia = [a for a in lista if a["quando"].date() == dia]
        return do_dia[-1] if do_dia else None
    palavras = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2 and w not in ("aula", "ultima", "sobre", "das", "dos")]
    if palavras:
        achadas = [a for a in lista if any(w in _dobrar(a["titulo"]) for w in palavras)]
        if achadas:
            return achadas[-1]
    return lista[-1]


def perguntas(aula: dict, quantas: int = 5) -> str:
    from plugins import _ia
    if not _ia.disponivel():
        return "Para criar perguntas eu preciso da chave do Gemini."
    texto = Path(aula["arquivo"]).read_text(encoding="utf-8", errors="replace")
    r = _ia.perguntar_json(
        f"Crie {quantas} perguntas de revisão (de múltipla escolha ou abertas curtas) sobre esta aula, em português, "
        "só com o que está no texto. Responda JSON: [{\"pergunta\": \"…\", \"resposta\": \"…\"}].\n\n" + texto[:40000])
    if not isinstance(r, list) or not r:
        return "Não consegui montar as perguntas agora."
    return json.dumps(r[:quantas], ensure_ascii=False)


def run(parameters: dict, player=None, session_memory=None) -> str:
    from plugins import ata_chamada as ata
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "gravar":
            return ata.iniciar("aula", str(p.get("titulo") or "").strip())
        if acao == "parar":
            if ata._estado.get("gravando") and ata._estado.get("tipo") != "aula":
                return "O que está gravando agora é uma ata de reunião; diga 'termina a ata'."
            return ata.parar(player)
        lista = aulas()
        if acao == "listar":
            if not lista:
                return "Ainda não gravei nenhuma aula. Diga 'grava essa aula'."
            mostrar(player, "AULAS GRAVADAS", "\n".join(f"{a['quando']:%d/%m %H:%M}  {a['titulo'] or '(sem título)'}"
                                                       for a in lista[-30:]))
            return f"{len(lista)} aulas gravadas; a lista está na tela."
        if acao in ("abrir", "perguntas"):
            aula = escolher_aula(lista, str(p.get("quando") or "última"))
            if not aula:
                return "Não achei essa aula." if lista else "Ainda não gravei nenhuma aula."
            nome = f"a aula de {aula['quando']:%d/%m}" + (f" ({aula['titulo']})" if aula["titulo"] else "")
            if acao == "abrir":
                abrir_no_sistema(str(aula["arquivo"]))
                return f"Abri {nome}."
            q = max(1, min(15, int(p.get("quantas") or 5)))
            js = perguntas(aula, q)
            if not js.startswith("["):
                return js
            return (f"[QUIZ sobre {nome}] Faça estas perguntas UMA de cada vez, espere a resposta do usuário, diga se "
                    f"acertou e explique em uma frase antes da próxima. No fim, diga quantas ele acertou: {js}")
        if ata._estado.get("gravando") and ata._estado.get("tipo") == "aula":
            return f"Gravando a aula há {(time.time() - ata._estado['inicio']) / 60:.0f} min."
        return f"Não estou gravando aula. {len(lista)} aulas guardadas."
    except Exception as e:
        return f"O modo aula falhou: {e}"
