"""
Livro-razão (3.6): a prova, à prova de adulteração, de tudo que o JARVIS fez — e o seu cartório pessoal.

    "Jarvis, prova o que você fez hoje"                 "Jarvis, o que você fez ontem às 15h?"
    "Jarvis, verifica o livro-razão"                    → confere a corrente inteira, bloco por bloco
    "Jarvis, sela o livro"                              → um código curto para guardar FORA do PC
    "Jarvis, confere o selo 1532-9f3a1c7b22d4"          → nada antes daquele ponto foi mexido?
    "Jarvis, registra no livro: combinei com o fornecedor a entrega para o dia 20"
    "Jarvis, demonstra a prova de adulteração"          → altera uma CÓPIA e mostra que ele percebe
    "Jarvis, relatório de auditoria de hoje"

Cada ação vira um bloco ligado ao anterior por hash e assinado com uma chave que só existe no seu PC.
Mudou, apagou ou trocou a ordem de um registro: a conta não fecha e ele aponta o bloco. Como funciona
e os limites: core/livro_razao.py. No modo anônimo nada é registrado. O texto dos resultados não é
guardado (só a impressão digital), e parâmetro com nome de segredo vira "***".
"""

from __future__ import annotations

import html as _html
import re
import time
from datetime import date, datetime, timedelta

from core import livro_razao as L
from plugins._lote2 import P, norm, pagina, rodar

PLUGIN = P("livro_razao", "Tamper-evident ledger of everything JARVIS did (hash chain + signature): prove actions, verify integrity, "
                          "seals, notarized notes, tampering demo.",
           "estado | provar | verificar | selar | conferir_selo | anotar | demonstrar | relatorio",
           "provar/relatorio: periodo ('hoje', 'ontem', 'ontem 15h', 'semana', 'dd/mm'), texto (optional filter: tool or word). "
           "verificar: checks the whole chain. selar: returns a short code to keep outside the PC. conferir_selo: codigo. "
           "anotar: texto — a note/agreement the user dictates, sealed in the ledger. demonstrar: tampers a COPY to show detection.",
           "periodo texto codigo")

TIPOS = {"ferramenta": "ferramenta", "confirmacao": "confirmação na tela", "autorizacao": "autorização do organismo",
         "selo": "selo", "nota": "nota sua", "anonimo": "modo anônimo", "experimento.plano": "plano de experimento",
         "experimento.resultado": "resultado de experimento", "evolucao": "evolução do cérebro", "omega.ciclo": "ciclo OMEGA"}


def janela(periodo: str, agora: datetime | None = None) -> tuple[float, float, str]:
    """(início, fim, nome) do período pedido. Pura."""
    agora = agora or datetime.now()
    t = norm(periodo)
    hoje = agora.date()
    dia, nome = hoje, "hoje"
    if "anteontem" in t:
        dia, nome = hoje - timedelta(2), "anteontem"
    elif "ontem" in t:
        dia, nome = hoje - timedelta(1), "ontem"
    elif "semana" in t:
        ini = datetime.combine(hoje - timedelta(6), datetime.min.time())
        return ini.timestamp(), agora.timestamp(), "nos últimos 7 dias"
    elif "tudo" in t or "sempre" in t:
        return 0.0, agora.timestamp(), "desde o começo"
    else:
        m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
        if m:
            ano = int(m.group(3)) if m.group(3) else hoje.year
            try:
                dia = date(ano + (2000 if ano < 100 else 0), int(m.group(2)), int(m.group(1)))
                nome = f"em {dia:%d/%m}"
            except ValueError:
                pass
    ini = datetime.combine(dia, datetime.min.time())
    fim = min(agora, ini + timedelta(days=1))
    h = re.search(r"\b(\d{1,2})\s*(?:h|hora|horas|:)", t)
    if h and 0 <= int(h.group(1)) <= 23:
        ini = ini.replace(hour=int(h.group(1)))
        fim, nome = min(agora, ini + timedelta(hours=1)), f"{nome} às {int(h.group(1))}h"
    return ini.timestamp(), max(fim.timestamp(), ini.timestamp()), nome


def frase(b: dict) -> str:
    """Um bloco em português. Pura."""
    d, hora = b["dados"], time.strftime("%H:%M", time.localtime(b["ts"]))
    if b["tipo"] == "ferramenta":
        acao = (d.get("a") or {}).get("action")
        return f"{hora} #{b['n']} usei {d.get('f')}" + (f" ({acao})" if acao else "") + ("" if d.get("ok", True) else " — falhou")
    if b["tipo"] == "nota":
        return f"{hora} #{b['n']} você registrou: {d.get('texto', '')}"
    if b["tipo"] == "confirmacao":
        return f"{hora} #{b['n']} confirmação na tela ({d.get('resposta', '')}): {d.get('titulo', '')}"
    if b["tipo"] == "autorizacao":
        return f"{hora} #{b['n']} organismo, pedido {d.get('resposta', '')}: {d.get('acao', '')} {d.get('alvo', '')}".rstrip()
    if b["tipo"] == "anonimo":
        return f"{hora} #{b['n']} modo anônimo {'ligado (a partir daqui nada foi registrado)' if d.get('ligado') else 'desligado'}"
    return f"{hora} #{b['n']} {TIPOS.get(b['tipo'], b['tipo'])}" + (f": {d.get('nome') or d.get('resumo') or ''}".rstrip(": ") if d else "")


def _blocos(p) -> tuple[list[dict], str]:
    ini, fim, nome = janela(str(p.get("periodo") or "hoje"))
    filtro = norm(p.get("texto"))
    bs = L.consultar(ini, fim, limite=400)
    if filtro:
        bs = [b for b in bs if filtro in norm(frase(b)) or filtro in norm(str(b["dados"]))]
    return bs, nome


def _selo_txt(v: dict) -> str:
    if v["ok"]:
        return f"Corrente íntegra: {v['blocos']} bloco(s) conferidos, nenhum alterado, apagado ou fora de ordem."
    return f"ATENÇÃO: o livro foi mexido. Problema no bloco {v['erro']['n']}: {v['erro']['motivo']}. Até o bloco {v['blocos']} está íntegro."


def _estado(p, pl):
    e = L.estado()
    if not e["blocos"]:
        return "O livro-razão está vazio: começo a registrar na próxima ação."
    desde = time.strftime("%d/%m/%Y", time.localtime(e["desde"]))
    tipos = ", ".join(f"{n} de {TIPOS.get(t, t)}" for t, n in list(e["tipos"].items())[:5])
    selo = (f" Último selo: {e['ultimo_selo']['codigo']} ({time.strftime('%d/%m %H:%M', time.localtime(e['ultimo_selo']['ts']))})."
            if e["ultimo_selo"] else " Ainda sem selo: diga 'sela o livro' e guarde o código fora do PC.")
    return f"Livro-razão: {e['blocos']} bloco(s) desde {desde} ({tipos}).{selo}"


def _provar(p, pl):
    bs, nome = _blocos(p)
    v = L.verificar()
    if not bs:
        return f"Não tenho nenhum registro {nome}" + (" (no modo anônimo eu não registro)." if L._anonimo() else ".") + " " + _selo_txt(v)
    linhas = [frase(b) for b in bs]
    extra = f" (mostrando as últimas 40 de {len(linhas)})" if len(linhas) > 40 else ""
    return f"O que eu fiz {nome}, {len(linhas)} registro(s){extra}:\n" + "\n".join(linhas[-40:]) + f"\n{_selo_txt(v)}"


def _verificar(p, pl):
    t = time.perf_counter()
    v = L.verificar()
    return _selo_txt(v) + f" (conferido em {time.perf_counter() - t:.2f} s)"


def _selar(p, pl):
    cod = L.selar()
    if not cod:
        return "Não consegui selar agora (no modo anônimo o livro fica parado)."
    return (f"Livro selado. Código: {cod}. Guarde FORA do PC (no celular, num papel). Depois, 'confere o selo {cod}' prova que "
            "nada antes deste ponto foi mexido.")


def _conferir_selo(p, pl):
    r = L.conferir_selo(str(p.get("codigo") or p.get("texto") or ""))
    if r["ok"]:
        return f"Selo confere: {r['motivo']} (bloco {r['n']}, de {time.strftime('%d/%m/%Y %H:%M', time.localtime(r['ts']))})."
    return f"Selo NÃO confere: {r['motivo']}."


def _anotar(p, pl):
    texto = str(p.get("texto") or "").strip()
    if not texto:
        return "O que eu registro? Dite o combinado, a promessa ou a decisão."
    b = L.registrar("nota", {"texto": texto[:L.MAX_NOTA]}, limite=L.MAX_NOTA)       # a sua nota fica inteira
    if not b:
        return "No modo anônimo eu não registro nada."
    return (f"Registrado no bloco #{b['n']}, {time.strftime('%d/%m/%Y às %H:%M', time.localtime(b['ts']))}: \"{texto[:120]}\". "
            f"Comprovante: {L.codigo_selo(b['n'], b['hash'])}.")


def _demonstrar(p, pl):
    r = L.demonstrar_adulteracao()
    if not r["ok"]:
        return f"Ainda não dá para demonstrar: {r['motivo']}."
    if not r["detectado"]:
        return "A demonstração falhou: alterei a cópia e não percebi. Isso é um defeito meu; me avise."
    return (f"Demonstração: copiei o livro ({r['blocos']} blocos), alterei o bloco {r['bloco_alterado']} NA CÓPIA e conferi. "
            f"Resultado: percebi na hora, no bloco {r['bloco_alterado']} ({r['motivo']}). "
            f"O livro de verdade não foi tocado e continua {'íntegro' if r['original_intacto'] else 'com problema'}.")


def _relatorio(p, pl):
    bs, nome = _blocos(p)
    v = L.verificar()
    if not bs:
        return f"Não tenho registros {nome} para o relatório."
    cor = "#1a7f37" if v["ok"] else "#cf222e"
    linhas = "".join(f"<tr><td>{b['n']}</td><td>{time.strftime('%d/%m %H:%M:%S', time.localtime(b['ts']))}</td>"
                     f"<td>{_html.escape(TIPOS.get(b['tipo'], b['tipo']))}</td><td>{_html.escape(frase(b).split(' ', 2)[-1])}</td>"
                     f"<td><code>{b['hash'][:12]}</code></td></tr>" for b in bs)
    corpo = (f"<p style='color:{cor};font-weight:600'>{_html.escape(_selo_txt(v))}</p>"
             "<p>Cada linha é um bloco. O código da última coluna é o começo do hash; ele depende de todos os blocos anteriores.</p>"
             "<table border='1' cellpadding='6' style='border-collapse:collapse;width:100%;font-size:14px'>"
             f"<tr><th>Bloco</th><th>Quando</th><th>Tipo</th><th>O que foi</th><th>Hash</th></tr>{linhas}</table>")
    arq = pagina("Auditoria", f"Auditoria do JARVIS — {nome}", corpo)
    return f"Relatório de auditoria aberto ({len(bs)} registro(s) {nome}). {_selo_txt(v)} Arquivo: {arq}"


def passo(player) -> None:
    """Relógio central: um selo por dia (para sempre existir um ponto de conferência recente)."""
    e = L.estado()
    if e["blocos"] and (not e["ultimo_selo"] or time.strftime("%Y-%m-%d", time.localtime(e["ultimo_selo"]["ts"])) != time.strftime("%Y-%m-%d")):
        L.selar()


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("livro_razao_selo", lambda: passo(player), a_cada_s=6 * 3600, primeira_em_s=900)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estado": _estado, "provar": _provar, "verificar": _verificar, "selar": _selar,
                              "conferir_selo": _conferir_selo, "anotar": _anotar, "demonstrar": _demonstrar,
                              "relatorio": _relatorio}, player, "Livro-razão")
