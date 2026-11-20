"""
Relatório de saúde do PC — plugin do J.A.R.V.I.S BR.

"Jarvis, como está a saúde do PC?" → nota de 0 a 100, os problemas em ordem
de gravidade e o que fazer com cada um. "Jarvis, gera o relatório de saúde" →
também salva uma página HTML em memory/ e abre no navegador.

O que entra na nota
    espaço em disco · saúde SMART dos discos · temperatura (CPU e GPU) · uso de
    RAM · quantidade de programas na inicialização · dias sem reiniciar ·
    lixo acumulado (temporários e lixeira) · e, no Windows: dias desde a última
    atualização, reinício pendente, dispositivos com erro de driver e o estado
    do antivírus (Defender).

A nota é calculada por `calcular_nota(dados)`, uma função pura (está nos
testes), então dá para conferir exatamente por que o PC tirou aquela nota.
"""

from __future__ import annotations

import html
import time
from datetime import datetime

from plugins._comum import (MEMORIA, WIN, abrir_no_sistema, br, mostrar, powershell_json,
                            tamanho)

PLUGIN = {
    "name": "saude_pc",
    "brief": "PC health score 0-100 with suggestions; HTML report.",
    "description": (
        "PC health check with a 0-100 score and suggestions (disk space, disk SMART, "
        "temperatures, RAM, startup programs, uptime, junk files, Windows Update, pending "
        "restart, driver problems, antivirus). action='verificar' for 'como está a saúde do "
        "PC' / 'nota do PC'; action='relatorio' also saves an HTML report; 'abrir' opens "
        "the last report."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "verificar | relatorio | abrir"}},
        "required": [],
    },
}

_ultimo_html: list[str] = []


# ── nota ───────────────────────────────────────────────────────────────────────
def calcular_nota(d: dict) -> tuple[int, list[dict]]:
    """(nota 0–100, problemas). Cada problema: {pontos, titulo, sugestao}."""
    probs: list[dict] = []

    def menos(pontos: int, titulo: str, sugestao: str):
        probs.append({"pontos": pontos, "titulo": titulo, "sugestao": sugestao})

    for p in d.get("particoes", []):
        livre = 100 - float(p.get("pct", 0))
        if livre < 5:
            menos(25, f"Disco {p['ponto']} quase cheio ({br(livre, 0)}% livre)",
                  "Rode a limpeza ('Jarvis, limpa o PC') e veja os maiores arquivos.")
        elif livre < 10:
            menos(15, f"Pouco espaço em {p['ponto']} ({br(livre, 0)}% livre)",
                  "Rode a limpeza e apague ou mova arquivos grandes.")
        elif livre < 20:
            menos(5, f"Espaço apertado em {p['ponto']} ({br(livre, 0)}% livre)",
                  "Vale uma limpeza de temporários.")

    for disco in d.get("smart", []):
        if disco.get("saude") not in (None, "saudável"):
            menos(30, f"Disco {disco['disco']} com SMART '{disco['saude']}'",
                  "Faça BACKUP agora e planeje trocar esse disco.")

    t = d.get("temp_cpu")
    if t is not None:
        if t >= 90:
            menos(15, f"CPU muito quente ({br(t, 0)} °C)",
                  "Limpe a poeira, confira a ventoinha e troque a pasta térmica.")
        elif t >= 80:
            menos(8, f"CPU quente ({br(t, 0)} °C)", "Melhore a ventilação e limpe a poeira.")
    tg = d.get("temp_gpu")
    if tg is not None and tg >= 85:
        menos(8, f"Placa de vídeo quente ({br(tg, 0)} °C)", "Limpe a placa e melhore o fluxo de ar.")

    ram = d.get("ram_media")
    if ram is not None:
        if ram >= 90:
            menos(10, f"RAM quase sempre cheia (média {br(ram, 0)}%)",
                  "Feche abas e apps em segundo plano; considere mais memória.")
        elif ram >= 80:
            menos(5, f"RAM alta (média {br(ram, 0)}%)", "Feche o que não estiver usando.")

    n = d.get("inicializacao_ativos")
    if n is not None:
        if n > 15:
            menos(10, f"{n} programas abrem com o PC", "Desative os que não precisa ('Jarvis, mostra a inicialização').")
        elif n > 10:
            menos(6, f"{n} programas abrem com o PC", "Desative alguns para o PC ligar mais rápido.")
        elif n > 6:
            menos(3, f"{n} programas abrem com o PC", "Dá para enxugar a inicialização.")

    dias = d.get("uptime_dias")
    if dias is not None:
        if dias >= 14:
            menos(6, f"Ligado há {int(dias)} dias sem reiniciar", "Reinicie: libera memória e aplica atualizações.")
        elif dias >= 7:
            menos(3, f"Ligado há {int(dias)} dias sem reiniciar", "Um reinício faz bem de vez em quando.")

    lixo = d.get("lixo_bytes")
    if lixo is not None:
        if lixo > 10 * 1024 ** 3:
            menos(5, f"{tamanho(lixo)} em temporários e lixeira", "Rode a limpeza.")
        elif lixo > 2 * 1024 ** 3:
            menos(2, f"{tamanho(lixo)} em temporários e lixeira", "Uma limpeza libera esse espaço.")

    upd = d.get("dias_sem_update")
    if upd is not None:
        if upd >= 60:
            menos(12, f"Windows sem atualizar há {int(upd)} dias", "Abra o Windows Update e instale o que estiver pendente.")
        elif upd >= 30:
            menos(6, f"Windows sem atualizar há {int(upd)} dias", "Confira o Windows Update.")
    if d.get("reinicio_pendente"):
        menos(5, "Há um reinício pendente para concluir atualizações", "Reinicie quando puder.")
    prob_disp = int(d.get("dispositivos_com_erro") or 0)
    if prob_disp:
        menos(min(15, 5 * prob_disp), f"{prob_disp} dispositivo(s) com erro de driver",
              "Abra o Gerenciador de Dispositivos e atualize/reinstale os drivers marcados.")
    if d.get("antivirus") is False:
        menos(20, "Antivírus desligado", "Ligue o Windows Defender (Segurança do Windows).")
    elif d.get("tempo_real") is False:
        menos(10, "Proteção em tempo real desligada", "Ligue em Segurança do Windows → Proteção contra vírus.")

    probs.sort(key=lambda p: -p["pontos"])
    nota = max(0, min(100, 100 - sum(p["pontos"] for p in probs)))
    return nota, probs


def conceito(nota: int) -> str:
    return ("excelente" if nota >= 90 else "boa" if nota >= 75 else "regular" if nota >= 55
            else "precisa de atenção")


# ── coleta ─────────────────────────────────────────────────────────────────────
def _windows() -> dict:
    dados = powershell_json(
        "$h = Get-HotFix | Where-Object {$_.InstalledOn} | Sort-Object InstalledOn -Descending |"
        " Select-Object -First 1;"
        "$p = @(Get-CimInstance Win32_PnPEntity | Where-Object {$_.ConfigManagerErrorCode -ne 0}).Count;"
        "$r = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired')"
        " -or (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending');"
        "$m = Get-MpComputerStatus;"
        "@{ultimo=if($h){$h.InstalledOn.ToString('yyyy-MM-dd')}else{''}; erros=$p; reinicio=$r;"
        " av=if($m){$m.AntivirusEnabled}else{$null}; rt=if($m){$m.RealTimeProtectionEnabled}else{$null}}",
        timeout=45) or {}
    saida = {"reinicio_pendente": bool(dados.get("reinicio")),
             "dispositivos_com_erro": int(dados.get("erros") or 0)}
    if dados.get("ultimo"):
        try:
            saida["dias_sem_update"] = (datetime.now() - datetime.strptime(dados["ultimo"], "%Y-%m-%d")).days
        except ValueError:
            pass
    if dados.get("av") is not None:
        saida["antivirus"] = bool(dados["av"])
    if dados.get("rt") is not None:
        saida["tempo_real"] = bool(dados["rt"])
    return saida


def coletar() -> dict:
    from core import telemetria
    s = telemetria.get().snapshot()
    d: dict = {"particoes": s.get("particoes", []), "temp_cpu": s.get("cpu_temp"),
               "temp_gpu": (s.get("gpu") or {}).get("temp"), "uptime_dias": s.get("uptime", 0) / 86400,
               "ram_media": (s.get("ram") or {}).get("pct")}
    try:
        from plugins import _monitor_db
        r = _monitor_db.resumo(time.time() - 86400)
        if r.get("amostras", 0) >= 30:
            d["ram_media"] = r.get("ram_media")
            if r.get("temp_max") is not None:
                d["temp_cpu"] = r["temp_max"]
    except Exception:
        pass
    try:
        d["smart"] = telemetria.saude_discos()
    except Exception:
        d["smart"] = []
    try:
        from plugins.controle_sistema import listar_inicializacao
        d["inicializacao_ativos"] = sum(1 for i in listar_inicializacao() if i["ativo"])
    except Exception:
        pass
    try:
        from plugins.limpeza import medir, raizes, tamanho_lixeira
        d["lixo_bytes"] = sum(medir(raizes("temporarios"), 3600, segundos=6).values()) + tamanho_lixeira()
    except Exception:
        pass
    if WIN:
        d.update(_windows())
    return d


# ── HTML ───────────────────────────────────────────────────────────────────────
def gerar_html(nota: int, probs: list[dict], d: dict) -> str:
    cor = "#00c853" if nota >= 90 else "#64dd17" if nota >= 75 else "#ffab00" if nota >= 55 else "#ff1744"
    itens = "".join(
        f"<li><b>−{p['pontos']}</b> {html.escape(p['titulo'])}<br><span>{html.escape(p['sugestao'])}</span></li>"
        for p in probs) or "<li>Nenhum problema encontrado. 👏</li>"
    linhas = []
    for p in d.get("particoes", []):
        linhas.append(("Disco " + p["ponto"], f"{br(100 - p['pct'], 0)}% livre ({tamanho(p['livre'])})"))
    for k, rot, fmt in (("temp_cpu", "Temperatura da CPU", lambda v: f"{br(v, 0)} °C"),
                        ("temp_gpu", "Temperatura da GPU", lambda v: f"{br(v, 0)} °C"),
                        ("ram_media", "RAM (média)", lambda v: f"{br(v, 0)}%"),
                        ("inicializacao_ativos", "Programas na inicialização", str),
                        ("uptime_dias", "Dias sem reiniciar", lambda v: br(v, 1)),
                        ("lixo_bytes", "Temporários + lixeira", tamanho),
                        ("dias_sem_update", "Dias desde a última atualização", str),
                        ("dispositivos_com_erro", "Dispositivos com erro", str)):
        if d.get(k) is not None:
            linhas.append((rot, fmt(d[k])))
    for disco in d.get("smart", []):
        linhas.append((f"SMART {disco['disco']}", disco["saude"]))
    if d.get("antivirus") is not None:
        linhas.append(("Antivírus", "ligado" if d["antivirus"] else "DESLIGADO"))
    tabela = "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(str(b))}</td></tr>" for a, b in linhas)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saúde do PC — {datetime.now():%d/%m/%Y %H:%M}</title>
<style>
 body{{font-family:Segoe UI,system-ui,sans-serif;background:#00060a;color:#cdeff7;margin:0;padding:24px}}
 .card{{max-width:760px;margin:auto;background:#011520;border:1px solid #0d3347;border-radius:10px;padding:24px}}
 h1{{color:#00d4ff;font-weight:600;margin:0 0 4px}} .sub{{color:#5ab8cc;margin-bottom:20px}}
 .nota{{width:140px;height:140px;border-radius:50%;border:8px solid {cor};display:flex;align-items:center;
   justify-content:center;font-size:44px;font-weight:700;color:{cor};margin:10px auto}}
 .conc{{text-align:center;color:{cor};font-size:18px;margin-bottom:24px}}
 ul{{padding-left:18px}} li{{margin:10px 0}} li span{{color:#8fb9c4}} h2{{color:#00d4ff;font-size:17px}}
 table{{width:100%;border-collapse:collapse}} td{{padding:6px 8px;border-bottom:1px solid #0d3347}}
 td:last-child{{text-align:right;color:#fff}} .rod{{color:#3a8a9a;font-size:12px;margin-top:20px}}
</style></head><body><div class="card">
<h1>Saúde do PC</h1><div class="sub">J.A.R.V.I.S BR · {datetime.now():%d/%m/%Y às %H:%M}</div>
<div class="nota">{nota}</div><div class="conc">{conceito(nota)}</div>
<h2>O que tirou pontos</h2><ul>{itens}</ul>
<h2>Medições</h2><table>{tabela}</table>
<div class="rod">Gerado localmente; nada foi enviado para a internet.</div>
</div></body></html>"""


def _texto(nota: int, probs: list[dict]) -> str:
    frase = f"Nota {nota} de 100: {conceito(nota)}."
    if probs:
        frase += " Principais pontos: " + "; ".join(
            f"{p['titulo']} — {p['sugestao']}" for p in probs[:3])
    else:
        frase += " Não encontrei nenhum problema."
    return frase


def run(parameters: dict, player=None, session_memory=None) -> str:
    a = str((parameters or {}).get("action") or "verificar").strip().lower()
    try:
        if a == "abrir":
            if _ultimo_html:
                return "Abrindo o relatório." if abrir_no_sistema(_ultimo_html[-1]) else "Não consegui abrir."
            relatorios = sorted(MEMORIA.glob("relatorio_saude_*.html"))
            if not relatorios:
                return "Ainda não gerei nenhum relatório. Peça 'gera o relatório de saúde'."
            abrir_no_sistema(str(relatorios[-1]))
            return "Abrindo o último relatório."
        d = coletar()
        nota, probs = calcular_nota(d)
        detalhes = [f"−{p['pontos']:>2}  {p['titulo']}\n      → {p['sugestao']}" for p in probs]
        mostrar(player, f"SAÚDE DO PC — {nota}/100", "\n".join(
            [f"Nota: {nota} ({conceito(nota)})", ""] + (detalhes or ["Nenhum problema encontrado."])))
        if a == "relatorio":
            caminho = MEMORIA / f"relatorio_saude_{datetime.now():%Y%m%d_%H%M}.html"
            MEMORIA.mkdir(parents=True, exist_ok=True)
            caminho.write_text(gerar_html(nota, probs, d), encoding="utf-8")
            _ultimo_html.append(str(caminho))
            abrir_no_sistema(str(caminho))
            return _texto(nota, probs) + " O relatório completo abriu no navegador."
        return _texto(nota, probs)
    except Exception as e:
        return f"O relatório de saúde falhou: {e}"
