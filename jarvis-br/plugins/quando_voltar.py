"""
Relatório de "quando voltar" (fork PT-BR 1.4).

Quando você volta depois de um tempo fora (1 h por padrão), o JARVIS conta o
que aconteceu enquanto isso:

    "Bem-vindo de volta. Dois downloads terminaram, a internet caiu 3
     minutos e um aparelho novo entrou na rede."

QUEM PERCEBE QUE VOCÊ VOLTOU
    • a câmera (reconhecimento facial com a vigia ligada), ou
    • o teclado/mouse (linha do tempo): sem uso por mais que o limite.
    Os dois juntos não duplicam o relatório.

O QUE ENTRA NO RELATÓRIO
    downloads que terminaram · quedas de internet (minutos sem conexão) ·
    aparelhos novos na rede e outros avisos da guarda de segurança · alertas
    do monitor (CPU, temperatura, disco) · tarefas agendadas que rodaram ·
    anomalias do radar · pedidos feitos pelo celular · avisos de vigias.

    "Jarvis, o que aconteceu enquanto eu estava fora?"   (relatório na hora)
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from plugins._comum import cfg, falar, mostrar, registrar

PLUGIN = {
    "name": "quando_voltar",
    "brief": "Summary of what happened while the user was away from the PC.",
    "description": (
        "'While you were away' report: finished downloads, internet drops, new devices on the network, "
        "security and monitor alerts, scheduled tasks that ran, anomalies, watcher alerts. Spoken "
        "automatically when the user returns after a long absence. action='relatorio' with horas "
        "(default: since the last absence) for 'what happened while I was away?'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "relatorio"},
                       "horas": {"type": "NUMBER"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "quando_voltar",
    "title": "Relatório de quando voltar",
    "fields": [
        {"key": "ligado", "label": "Contar o que aconteceu quando eu voltar", "type": "toggle", "default": True},
        {"key": "minutos", "label": "Ausência mínima (minutos)", "type": "text", "default": "60"},
    ],
}

_ultimo = {"ts": 0.0}
_lock = threading.Lock()


def coletar(desde: float, ate: float | None = None) -> dict:
    ate = ate or time.time()
    fatos: dict = {"downloads": [], "internet_min": 0, "quedas": 0, "seguranca": [], "alertas": [],
                   "agendadas": [], "anomalias": [], "celular": 0, "vigias": []}
    try:
        from plugins import downloads
        pasta = downloads.pasta()
        for a in pasta.iterdir():
            try:
                if a.is_file() and not downloads.eh_parcial(a.name) and desde <= a.stat().st_mtime <= ate:
                    fatos["downloads"].append(a.name)
            except OSError:
                continue
        # arquivos já organizados em subpastas também contam
        for sub in pasta.iterdir():
            if sub.is_dir():
                for a in sub.iterdir():
                    try:
                        if a.is_file() and desde <= a.stat().st_mtime <= ate and a.name not in fatos["downloads"]:
                            fatos["downloads"].append(a.name)
                    except OSError:
                        continue
    except Exception:
        pass
    try:
        from plugins import _monitor_db
        am = _monitor_db.amostras(desde, ate)
        sem = [a for a in am if a.get("internet") == 0]
        fatos["internet_min"] = len(sem)                    # uma amostra por minuto
        fatos["quedas"] = sum(1 for x, y in zip(am, am[1:]) if x.get("internet") != 0 and y.get("internet") == 0) \
            + (1 if am and am[0].get("internet") == 0 else 0)
        for e in _monitor_db.eventos(desde, 300):
            if e["ts"] > ate:
                continue
            msg, tipo = e.get("mensagem") or "", e.get("tipo") or ""
            if msg.lower().startswith("oportunidade"):
                continue
            if tipo == "seguranca":
                fatos["seguranca"].append(msg)
            elif tipo == "celular":
                fatos["celular"] += 1
            elif tipo == "aviso" and msg.lower().startswith(("vigia", "radar")):
                (fatos["anomalias"] if msg.lower().startswith("radar") else fatos["vigias"]).append(msg)
            elif tipo == "aviso":
                fatos["vigias"].append(msg)
            elif tipo in ("alerta", "monitor") and "internet" not in msg.lower():
                fatos["alertas"].append(msg)
    except Exception:
        pass
    try:
        from plugins import agendador
        for t in agendador.carregar():
            u = t.get("ultima")
            if u and desde <= datetime.fromisoformat(u).timestamp() <= ate:
                fatos["agendadas"].append(t.get("descricao") or t.get("acao"))
    except Exception:
        pass
    return fatos


def _plural(n: int, um: str, varios: str) -> str:
    return um if n == 1 else varios.replace("#", str(n))


def frases(f: dict) -> list[str]:
    """Os fatos, do mais importante ao menos, em frases curtas (pura)."""
    out = []
    if f["seguranca"]:
        novos = [m for m in f["seguranca"] if "rede" in m.lower() or "aparelho" in m.lower()]
        if novos:
            out.append(_plural(len(novos), "um aparelho novo entrou na rede", "# aparelhos novos entraram na rede"))
        outros = [m for m in f["seguranca"] if m not in novos]
        if outros:
            out.append(f"a guarda de segurança registrou: {outros[0][:90]}")
    if f["downloads"]:
        out.append(_plural(len(f["downloads"]), f"o download {f['downloads'][0][:40]} terminou",
                           "# downloads terminaram"))
    if f["internet_min"]:
        out.append(f"a internet caiu {f['internet_min']} minuto{'s' if f['internet_min'] > 1 else ''}"
                   + (f" ({f['quedas']} quedas)" if f["quedas"] > 1 else ""))
    if f["alertas"]:
        out.append(f"o monitor deu {len(f['alertas'])} alerta(s), o último: {f['alertas'][-1][:80]}")
    if f["agendadas"]:
        out.append("rodou o agendado: " + ", ".join(f["agendadas"][:3]))
    if f["anomalias"]:
        out.append(f["anomalias"][-1][:100])
    if f["vigias"]:
        out.append(f["vigias"][-1][:100])
    if f["celular"]:
        out.append(_plural(f["celular"], "houve um comando pelo celular", "houve # comandos pelo celular"))
    return out


def _dur(s: float) -> str:
    m = int(s // 60)
    return f"{m} minutos" if m < 60 else (f"{m // 60}h{m % 60:02d}" if m % 60 else f"{m // 60} horas")


def ao_voltar(player, ausente_s: float, fonte: str = "") -> bool:
    """Chamado pela câmera ou pela linha do tempo. True se falou o relatório."""
    c = cfg("quando_voltar", PLUGIN_SETTINGS)
    if str(c.get("ligado", True)).lower() in ("false", "0", "nao", "não"):
        return False
    try:
        minimo = float(str(c.get("minutos") or 60).replace(",", ".")) * 60
    except ValueError:
        minimo = 3600
    if ausente_s < minimo:
        return False
    with _lock:
        if time.time() - _ultimo["ts"] < 600:           # câmera e teclado juntos: um relatório só
            return True
        _ultimo["ts"] = time.time()
    fatos = coletar(time.time() - ausente_s)
    lista = frases(fatos)
    registrar(player, f"Você voltou depois de {_dur(ausente_s)} ({fonte}).")
    if lista:
        mostrar(player, "ENQUANTO VOCÊ ESTAVA FORA", "\n".join(f"• {x}" for x in lista)
                + ("\n\nDownloads:\n  " + "\n  ".join(fatos["downloads"][:15]) if fatos["downloads"] else ""))
        falar(player, f"[QUANDO VOLTAR] O usuário acabou de voltar ao computador depois de {_dur(ausente_s)} fora. "
                      "Dê boas-vindas no estilo J.A.R.V.I.S e resuma, em no máximo 2 frases curtas e no idioma da "
                      f"conversa, o que aconteceu: {'; '.join(lista[:4])}. Não chame nenhuma ferramenta.")
    else:
        falar(player, f"[QUANDO VOLTAR] O usuário voltou depois de {_dur(ausente_s)} fora. Dê boas-vindas em UMA "
                      "frase curta e diga que nada importante aconteceu. Não chame nenhuma ferramenta.")
    return True


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    try:
        horas = float(p.get("horas") or 0)
        if horas <= 0:
            from plugins import _monitor_db
            ausencias = [f for f in _monitor_db.focos(time.time() - 86400) if f["atividade"] == "ausente"]
            desde = ausencias[-1]["inicio"] if ausencias else time.time() - 3 * 3600
        else:
            desde = time.time() - horas * 3600
        lista = frases(coletar(desde))
        quando = datetime.fromtimestamp(desde).strftime("%H:%M")
        if not lista:
            return f"Desde as {quando}, nada importante aconteceu."
        mostrar(player, f"DESDE AS {quando}", "\n".join(f"• {x}" for x in lista))
        return f"Desde as {quando}: " + "; ".join(lista[:5]) + "."
    except Exception as e:
        return f"Não consegui montar o relatório: {e}"
