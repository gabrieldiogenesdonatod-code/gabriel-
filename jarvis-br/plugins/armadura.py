"""
Modo armadura (fork PT-BR 1.6) — o "status do traje".

Junta numa tela só: bateria e sinal do celular, CPU/RAM/GPU e temperatura do
PC, internet, nota de saúde do PC e o clima.

    "Jarvis, modo armadura"  /  "status do traje"
    No celular: o botão 🦾 do painel abre a tela da armadura (atualiza sozinha).

A bateria do celular vem do próprio navegador do celular (na tela 🦾) ou, no
PC, pelo ADB se o celular estiver conectado em "aparelhos".
"""

from __future__ import annotations

import threading
import time

from plugins._comum import mostrar

PLUGIN = {
    "name": "armadura",
    "brief": "Iron Man 'suit status': phone battery/signal, PC CPU/RAM/GPU/temperature, internet, health score, weather.",
    "description": (
        "Armor mode / suit status: shows phone battery and signal (via ADB if paired), PC CPU, RAM, GPU, temperature, "
        "internet, PC health score and weather in one panel ('modo armadura', 'status do traje'). No parameters."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}}, "required": []},
}

_cache = {"clima": ("", 0.0), "nota": (None, 0.0)}


def _clima() -> str:
    texto, quando = _cache["clima"]
    if time.time() - quando < 1800 and texto:
        return texto
    caixa = {}

    def ler():
        try:
            from plugins import briefing_br
            caixa["c"] = briefing_br.clima()
        except Exception:
            caixa["c"] = ""
    t = threading.Thread(target=ler, daemon=True)
    t.start()
    t.join(8)
    texto = caixa.get("c") or ""
    if texto.startswith(("Não ", "Nao ")):                    # "Não sei sua cidade…" não é clima
        texto = ""
    _cache["clima"] = (texto, time.time())
    return _cache["clima"][0]


def _nota():
    nota, quando = _cache["nota"]
    if time.time() - quando < 600 and nota is not None:
        return nota
    try:
        from plugins import saude_pc
        nota = saude_pc.calcular_nota(saude_pc.coletar())[0]
    except Exception:
        nota = None
    _cache["nota"] = (nota, time.time())
    return nota


def celular_adb() -> dict:
    try:
        from plugins import aparelhos
        cel = next((a for a in aparelhos.carregar()["aparelhos"] if a.get("tipo") in ("celular", "android")), None)
        if not cel or not aparelhos.adb_exe():
            return {}
        cod, bat = aparelhos.adb(cel, "shell", "dumpsys", "battery", timeout=6)
        if cod != 0:
            return {}
        import re
        nivel = re.search(r"level: (\d+)", bat)
        return {"bateria": int(nivel.group(1)) if nivel else None,
                "carregando": bool(re.search(r"(AC|USB|Wireless) powered: true", bat)), "nome": cel["nome"]}
    except Exception:
        return {}


def status_traje(com_celular: bool = True) -> dict:
    d = {"hora": time.strftime("%H:%M")}
    try:
        from core import telemetria
        s = telemetria.get().snapshot()
        g = s.get("gpu") if isinstance(s.get("gpu"), dict) else {}
        d.update(cpu=round(s.get("cpu") or 0), ram=round((s.get("ram") or {}).get("pct") or 0),
                 gpu=next((round(g[k]) for k in ("uso", "util", "pct", "carga") if isinstance(g.get(k), (int, float))), None),
                 temp=round(s["cpu_temp"]) if isinstance(s.get("cpu_temp"), (int, float)) else
                 (round(g["temp"]) if isinstance(g.get("temp"), (int, float)) else None),
                 internet=s.get("internet") is not False)
    except Exception:
        pass
    d["saude"] = _nota()
    d["clima"] = _clima()
    if com_celular:
        d["celular"] = celular_adb()
    return d


def texto_traje(d: dict) -> str:
    """Painel em texto (puro)."""
    def barra(v):
        return "█" * int((v or 0) / 10) + "░" * (10 - int((v or 0) / 10)) if v is not None else "—"
    cel = d.get("celular") or {}
    linhas = [f"STATUS DO TRAJE — {d.get('hora', '')}", "",
              f"REATOR (CPU)   {barra(d.get('cpu'))} {d.get('cpu', '—')}%",
              f"MEMÓRIA (RAM)  {barra(d.get('ram'))} {d.get('ram', '—')}%",
              f"GPU            {barra(d.get('gpu'))} {d.get('gpu') if d.get('gpu') is not None else '—'}%",
              f"TEMPERATURA    {d['temp']}°C" if d.get("temp") is not None else "TEMPERATURA    sem sensor",
              f"COMUNICAÇÃO    {'online' if d.get('internet', True) else 'SEM INTERNET'}",
              f"INTEGRIDADE    {d['saude']}/100" if d.get("saude") is not None else "INTEGRIDADE    —",
              f"CELULAR        {cel['bateria']}%{' carregando' if cel.get('carregando') else ''}"
              if cel.get("bateria") is not None else "CELULAR        abra 🦾 no celular (ou conecte o ADB)",
              "", f"AMBIENTE       {d.get('clima') or '—'}"]
    return "\n".join(linhas)


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        d = status_traje()
        mostrar(player, "MODO ARMADURA", texto_traje(d))
        partes = [f"CPU {d['cpu']}%" if "cpu" in d else "", f"RAM {d['ram']}%" if "ram" in d else "",
                  f"{d['temp']} graus" if d.get("temp") is not None else "",
                  f"integridade {d['saude']} de 100" if d.get("saude") is not None else "",
                  f"celular com {d['celular']['bateria']}%" if (d.get("celular") or {}).get("bateria") is not None else ""]
        return ("[ARMADURA] Leia como o status do traje do Homem de Ferro, em 2 frases: "
                + ", ".join(x for x in partes if x) + (f". Clima: {d['clima']}" if d.get("clima") else "") + ".")
    except Exception as e:
        return f"O modo armadura falhou: {e}"
