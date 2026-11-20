"""
Resumo de grupo lotado (fork PT-BR 1.6) — "o que rolou no grupo enquanto eu estava fora?"

Lê a conversa exportada do WhatsApp (conversa → ⋮ → Mais → Exportar conversa →
sem mídia; salve na pasta Downloads) e resume só o período que você quer:
quem mais falou, o que decidiram, perguntas para você, datas/horários
combinados e links. Com a chave do Gemini, o resumo vira um texto de verdade.

    "Jarvis, o que rolou no grupo da família desde ontem?"
    "Jarvis, resume o grupo da faculdade das últimas 6 horas"

Sem dizer o arquivo, ele usa o export mais novo da pasta Downloads (ou o que
tiver o nome do grupo).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from plugins._comum import mostrar, nome_usuario, pasta_usuario

PLUGIN = {
    "name": "resumo_grupo",
    "brief": "Summarizes a busy WhatsApp group from an exported chat for a period (who, decisions, questions, links).",
    "description": (
        "Summary of a busy group chat from a WhatsApp export (.txt or .zip): grupo = part of the group name (finds the "
        "newest export in Downloads), or arquivo = path; desde = 'ontem', '6 horas', '2 dias', 'hoje' (default: since "
        "the user's own last message)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"grupo": {"type": "STRING"}, "arquivo": {"type": "STRING"}, "desde": {"type": "STRING"}},
        "required": [],
    },
}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def quando(m: dict) -> datetime | None:
    d = m["data"]
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%m/%d/%y %H:%M"):
        try:
            return datetime.strptime(f"{d} {m['hora']}", fmt)
        except ValueError:
            continue
    return None


def corte(desde: str, msgs: list[dict], eu: str, agora: datetime | None = None) -> datetime:
    """Desde quando resumir (pura)."""
    agora = agora or datetime.now()
    t = _dobrar(desde)
    m = re.search(r"(\d+)\s*(h|hora|min|dia|semana)", t)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return agora - (timedelta(hours=n) if u.startswith("h") else timedelta(minutes=n) if u.startswith("min")
                        else timedelta(days=7 * n) if u.startswith("semana") else timedelta(days=n))
    if "ontem" in t:
        return datetime.combine((agora - timedelta(days=1)).date(), datetime.min.time())
    if "hoje" in t:
        return datetime.combine(agora.date(), datetime.min.time())
    minhas = [quando(x) for x in msgs if eu and eu in _dobrar(x["autor"])]
    minhas = [x for x in minhas if x]
    return max(minhas) if minhas else agora - timedelta(hours=24)


def analisar(msgs: list[dict], eu: str = "") -> dict:
    """Quem falou, perguntas, menções a você, datas e links (pura)."""
    autores = Counter(m["autor"] for m in msgs)
    perguntas = [m for m in msgs if "?" in m["texto"]]
    mencoes = [m for m in msgs if eu and (f"@{eu}" in _dobrar(m["texto"]) or re.search(rf"\b{re.escape(eu)}\b", _dobrar(m["texto"])))]
    datas = [m for m in msgs if re.search(r"\b(\d{1,2}/\d{1,2}|\d{1,2}h\d{0,2}|\d{1,2}:\d{2}|amanha|sabado|domingo|"
                                          r"segunda|terca|quarta|quinta|sexta)\b", _dobrar(m["texto"]))]
    links = [u for m in msgs for u in re.findall(r"https?://\S+", m["texto"])]
    return {"total": len(msgs), "autores": autores.most_common(8), "perguntas": perguntas[-8:], "mencoes": mencoes[-8:],
            "datas": datas[-8:], "links": links[-8:]}


def achar_export(grupo: str) -> Path | None:
    pastas = [pasta_usuario("Downloads"), pasta_usuario("Documents"), pasta_usuario("Desktop")]
    candidatos = []
    for p in pastas:
        if p.is_dir():
            candidatos += [x for x in p.glob("*.txt") if re.search(r"whatsapp|conversa", x.name, re.I)]
            candidatos += [x for x in p.glob("*.zip") if re.search(r"whatsapp|conversa", x.name, re.I)]
    if grupo:
        candidatos = [x for x in candidatos if _dobrar(grupo) in _dobrar(x.name)] or candidatos
    return max(candidatos, key=lambda x: x.stat().st_mtime) if candidatos else None


def ler(arq: Path) -> str:
    if arq.suffix.lower() == ".zip":
        import zipfile
        with zipfile.ZipFile(arq) as z:
            nome = next((n for n in z.namelist() if n.lower().endswith(".txt")), None)
            return z.read(nome).decode("utf-8", "replace") if nome else ""
    return arq.read_text(encoding="utf-8", errors="replace")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    try:
        from plugins.estilo_escrita import ler_whatsapp
        arq = Path(str(p["arquivo"]).strip().strip('"')).expanduser() if p.get("arquivo") else \
            achar_export(str(p.get("grupo") or ""))
        if not arq or not arq.is_file():
            return ("Não achei a conversa exportada. No WhatsApp: abra o grupo → ⋮ → Mais → Exportar conversa → "
                    "sem mídia, e salve na pasta Downloads do PC.")
        todas = ler_whatsapp(ler(arq))
        eu = _dobrar(nome_usuario().split()[0]) if nome_usuario() else ""
        inicio = corte(str(p.get("desde") or ""), todas, eu)
        msgs = [m for m in todas if (quando(m) or datetime.min) >= inicio]
        if not msgs:
            return f"Nada novo no {arq.stem} desde {inicio:%d/%m %H:%M}."
        a = analisar(msgs, eu)
        painel = [f"{arq.stem} — desde {inicio:%d/%m %H:%M}: {a['total']} mensagens", "",
                  "Quem mais falou: " + ", ".join(f"{n} ({q})" for n, q in a["autores"])]
        for titulo, chave in (("Mencionaram você", "mencoes"), ("Perguntas", "perguntas"), ("Datas e horários", "datas")):
            if a[chave]:
                painel += ["", titulo + ":"] + [f"  {m['hora']} {m['autor']}: {m['texto'][:140]}" for m in a[chave]]
        if a["links"]:
            painel += ["", "Links:"] + [f"  {u}" for u in a["links"]]
        from plugins import _ia
        resumo = ""
        if _ia.disponivel():
            conversa = "\n".join(f"{m['hora']} {m['autor']}: {m['texto'][:300]}" for m in msgs[-600:])
            resumo = _ia.perguntar(
                f"Resuma esta conversa de grupo de WhatsApp para alguém que esteve fora, em até 6 frases faladas em "
                f"português do Brasil: os assuntos, o que foi decidido, datas/horários combinados e o que perguntaram "
                f"para {nome_usuario() or 'o usuário'}. Sem markdown.\n\n{conversa[-40000:]}", True, 90) or ""
        mostrar(player, "RESUMO DO GRUPO", (resumo + "\n\n" if resumo else "") + "\n".join(painel))
        if resumo:
            return f"[RESUMO DO GRUPO {arq.stem}] {resumo}"
        quem = ", ".join(n for n, _q in a["autores"][:3])
        return (f"{a['total']} mensagens no {arq.stem} desde {inicio:%d/%m %H:%M}, mais de {quem}. "
                f"{len(a['mencoes'])} menção(ões) a você, {len(a['perguntas'])} pergunta(s) e {len(a['datas'])} mensagem(ns) "
                "com data ou horário. O detalhe está no painel (com a chave do Gemini eu faço um resumo de verdade).")
    except Exception as e:
        return f"O resumo do grupo falhou: {e}"
