"""
Jornal da sua vida (3.0): uma capa de jornal de verdade, todo dia, só sobre o SEU mundo — vendas de
ontem, o sonho da noite, as ofensivas dos hábitos, o tempo em Goiânia, as promessas do dia e a
frase do dia. Abre no navegador como um jornal impresso.

    "Jarvis, me mostra o jornal de hoje."      "Jarvis, qual a manchete?"
    "Jarvis, assina o jornal" (ele monta sozinho toda manhã, às 7h, e fala a manchete).
"""

from __future__ import annotations

import html
import time
from datetime import date, timedelta

from plugins import _fatos
from plugins._lote2 import P, carregar, guardar, pagina, rodar

PLUGIN = P("jornal_vida", "Newspaper of your life: daily front page with yesterday's sales, the dream, streaks, weather, promises; spoken headline.",
           "edicao | manchete | assinar | cancelar",
           "edicao: build and open today's front page. manchete: just the spoken headline. assinar/cancelar: automatic edition at 7h.", "")

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _ferramenta(nome: str, params: dict, pl=None) -> str:
    try:
        from core import registro_ferramentas
        r = str(registro_ferramentas.executar(nome, params, pl))
        return "" if "não existe" in r or r.lower().startswith(("nenhum", "ainda n", "nada")) else r
    except Exception:
        return ""


def manchete(fatos_ontem: dict) -> str:
    """A notícia mais forte vira manchete. Pura."""
    v = fatos_ontem.get("vendas")
    if v and v.get("variacao") is not None and abs(v["variacao"]) >= 20:
        return f"LOJA VENDE {abs(v['variacao']):.0f}% {'ACIMA' if v['variacao'] > 0 else 'ABAIXO'} DO NORMAL"
    if fatos_ontem.get("sonho"):
        return "JARVIS FAZ DESCOBERTA DURANTE A MADRUGADA"
    ofs = fatos_ontem.get("ofensivas") or {}
    if ofs and max(ofs.values()) >= 7:
        nome, n = max(ofs.items(), key=lambda x: x[1])
        return f"OFENSIVA DE {nome.upper()} CHEGA A {n} DIAS"
    if fatos_ontem.get("ia"):
        return f"IA '{fatos_ontem['ia']['nome'].upper()}' ATINGE LOSS {fatos_ontem['ia']['loss']:.2f}"
    return "DIA NOVO, PÁGINA EM BRANCO: O QUE VAI SER NOTÍCIA HOJE?"


def montar(hoje: date, pl=None) -> tuple[str, str]:
    ontem = hoje - timedelta(1)
    f = _fatos.periodo(ontem, ontem)
    titulo = manchete(f)
    est = carregar("jornal", {"edicao": 0, "assinado": False, "ultima": ""})
    est["edicao"] += 1
    guardar("jornal", est)
    blocos = [("Ontem em números", "; ".join(_fatos.frases(f)).capitalize() or "Dia tranquilo, sem números novos."),
              ("Tempo", _ferramenta("chuva", {"action": "agora"}, pl)),
              ("Promessas de hoje", _ferramenta("cacador_promessas", {"action": "listar"}, pl)),
              ("Pendências", _ferramenta("resumo_do_dia", {"action": "agora"}, pl)),
              ("Frase do dia", _ferramenta("frase_do_dia", {"action": "hoje"}, pl)),
              ("Você sabia?", _ferramenta("curiosidades", {"action": "contar"}, pl))]
    colunas = "".join(f"<div class='col'><h3>{html.escape(t)}</h3><p>{html.escape(x[:700]).replace(chr(10), '<br>')}</p></div>"
                      for t, x in blocos if x)
    data = f"{SEMANA[hoje.weekday()].capitalize()}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}"
    corpo = ("<style>body{font-family:Georgia,serif;max-width:900px}.topo{text-align:center;border-bottom:3px double #222}"
             ".topo h1{font-size:46px;letter-spacing:4px;margin:6px 0}.meta{display:flex;justify-content:space-between;font-size:13px;"
             "border-bottom:1px solid #222;padding:4px 0}.manchete{font-size:34px;text-align:center;margin:18px 0;font-weight:bold}"
             ".cols{column-count:2;column-gap:28px}.col{break-inside:avoid;margin-bottom:12px}.col h3{border-bottom:1px solid #999;"
             "font-variant:small-caps}</style>"
             f"<div class='topo'><h1>O DIÁRIO DO SENHOR</h1></div><div class='meta'><span>{data}</span><span>Goiânia</span>"
             f"<span>Edição nº {est['edicao']}</span></div><div class='manchete'>{html.escape(titulo)}</div><div class='cols'>{colunas}</div>")
    return titulo, pagina("Jornal", f"Jornal {hoje.isoformat()}", corpo)


def passo(player) -> None:
    est = carregar("jornal", {"edicao": 0, "assinado": False, "ultima": ""})
    if est.get("assinado") and est.get("ultima") != date.today().isoformat() and 7 <= time.localtime().tm_hour < 11:
        titulo, _ = montar(date.today(), player)
        est = carregar("jornal", est)
        est["ultima"] = date.today().isoformat()
        guardar("jornal", est)
        from plugins._comum import avisar
        avisar(player, f"Saiu o jornal de hoje. Manchete: {titulo.capitalize()}.", "JORNAL")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("jornal_vida", lambda: passo(player), a_cada_s=1800, primeira_em_s=150)


def _go(p, pl):
    a = p["action"]
    est = carregar("jornal", {"edicao": 0, "assinado": False, "ultima": ""})
    if a in ("assinar", "cancelar"):
        est["assinado"] = a == "assinar"
        guardar("jornal", est)
        return "Assinado: toda manhã, às 7h, o jornal sai sozinho." if est["assinado"] else "Assinatura do jornal cancelada."
    if a == "manchete":
        return manchete(_fatos.periodo(date.today() - timedelta(1), date.today() - timedelta(1))).capitalize() + "."
    titulo, arq = montar(date.today(), pl)
    return f"Saiu a edição de hoje. Manchete: {titulo.capitalize()}. Abri no navegador: {arq}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("edicao manchete assinar cancelar".split(), _go), player)
