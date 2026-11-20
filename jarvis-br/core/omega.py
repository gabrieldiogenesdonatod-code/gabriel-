"""
OMEGA (fork PT-BR 3.6) — os 8 sistemas do JARVIS funcionando como UM só.

Até a 3.5 cada sistema vivia sozinho. O OMEGA é a camada que junta:

    BRAIN      raciocínio e hipóteses     cérebro local, hipóteses, probabilidades, cérebro do organismo
    HEART      núcleo de gerenciamento    coração do organismo, relógio central, vigia anti-travamento
    IMMUNE     proteção e recuperação     sistema imune, DNA, regeneração, verificação do dono, livro-razão
    MEMORY     memória associativa        grafo com busca por significado, memória que esquece, caixa-preta
    COUNCIL    12 agentes                 conselho (5 especialistas), multiverso (5), revisor cético, FRIDAY
    EVOLUTION  melhoria controlada        metacognição, evolução do jeito de falar, auto-melhoria
    DREAM      revisão e descobertas      sonhos (padrões nos seus números), serendipidade
    LAB        experimentos e invenções   experimentos sorteados na sua vida, laboratório de código, criador

O CICLO OMEGA liga um no outro (uma vez por dia, ou quando você pedir):

    DREAM acha um padrão → BRAIN transforma em hipótese que dá para testar → LAB propõe o experimento
    sorteado (só começa com o seu sim) → EVOLUTION confere o placar e propõe ou desfaz evoluções →
    IMMUNE confere a integridade do livro-razão e a saúde → MEMORY guarda o resumo do ciclo.
    O COUNCIL entra quando você convoca, para decidir sobre o que o ciclo trouxe.

Não é uma "consciência": é uma rotina que conecta módulos que já funcionam, com tudo medido e nada
escondido. O painel mostra dados reais deste PC; sistema sem dado aparece como "ainda sem dados".
Arquivo: memory/omega.json.
"""

from __future__ import annotations

import html as _html
import json
import math
import threading
import time
from datetime import date
from pathlib import Path

ARQ = Path(__file__).resolve().parent.parent / "memory" / "omega.json"
_lock = threading.Lock()

SISTEMAS = (("brain", "BRAIN", "Raciocínio e hipóteses"), ("heart", "HEART", "Núcleo de gerenciamento"),
            ("immune", "IMMUNE", "Proteção e recuperação"), ("memory", "MEMORY", "Memória associativa"),
            ("council", "COUNCIL", "12 agentes"), ("evolution", "EVOLUTION", "Melhoria controlada"),
            ("dream", "DREAM", "Revisão e descobertas"), ("lab", "LAB", "Experimentos e invenções"))
CONSELHEIROS = ("Planejador", "Programador", "Pesquisador", "Revisor", "Gestor de Memória",            # plugin conselho
                "Stark", "Empresário", "Sábio", "Rapper", "Cientista",                                 # plugin multiverso
                "Revisor cético",                                                                       # segunda_opiniao
                "FRIDAY")                                                                               # duelo_ia


def _ler() -> dict:
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _gravar(d: dict) -> None:
    try:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        tmp = ARQ.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ARQ)
    except OSError:
        pass


def _org():
    try:
        import biological_core
        org = biological_core.atual()
        return org if org and org.ligado else None
    except Exception:
        return None


def _lote2(nome: str, padrao):
    try:
        from plugins._lote2 import carregar
        return carregar(nome, padrao)
    except Exception:
        return padrao


def _s(estado: str, frase: str, numeros: list[tuple[str, str]], pecas: str) -> dict:
    return {"estado": estado, "frase": frase, "numeros": numeros, "pecas": pecas.split()}


# ─────────────────────────────────────────────────────────── os 8 sistemas ───
def _brain() -> dict:
    from core import cerebro, metacognicao
    e, pc = cerebro.estado(), metacognicao.placar_cerebro()
    nums = [("comandos aprendidos", str(e["aprendidos"])), ("reflexos", str(e["reflexos"])),
            ("frases de exemplo", str(e["sementes"]))]
    if pc["top1"] is not None:
        nums.append(("acerto medido", f"{pc['top1']:.0%} em {pc['sabia']}"))
    org = _org()
    if org:
        nums.append(("decisões do organismo", str(org.cerebro.metricas.get("decisoes", 0))))
    frase = (f"{e['aprendidos']} comando(s) aprendido(s) com você, {e['reflexos']} já viraram reflexo"
             + (f"; acerto medido de {pc['top1']:.0%}" if pc["top1"] is not None else f"; nasce sabendo {e['sementes']} frases de exemplo") + ".")
    return _s("ok" if e["aprendidos"] or pc["n"] or e["sementes"] else "parado", frase, nums, "cerebro hipoteses probabilidades organismo")


def _heart() -> dict:
    from core import relogio
    tarefas = relogio.tarefas()
    org = _org()
    nums = [("rotinas no relógio central", str(len(tarefas)))]
    if not org:
        return _s("ok" if tarefas else "parado", f"{len(tarefas)} rotina(s) no relógio central; o organismo não está ligado nesta janela.",
                  nums, "organismo relogio vigia")
    s = org.saude.ultimo
    orgs = org.estado_orgaos()
    nums += [("saúde", f"{s.get('nota', '—')}/100"), ("tendência", str(org.saude.tendencia())), ("coração", orgs["coracao"]["detalhe"])]
    cor = s.get("cor", "azul")
    return _s("atencao" if cor in ("amarelo", "vermelho") else "ok",
              f"Saúde {s.get('nota', '—')}/100, tendência {org.saude.tendencia()}; {len(tarefas)} rotina(s) batendo no relógio central.",
              nums, "organismo relogio vigia")


def _immune() -> dict:
    from core import livro_razao
    e, v = livro_razao.estado(), livro_razao.verificar()
    nums = [("blocos no livro-razão", str(e["blocos"])), ("corrente", "íntegra" if v["ok"] else f"VIOLADA no bloco {v['erro']['n']}"),
            ("selos", str(e["selos"]))]
    org, abertos, isol, pend = _org(), [], [], []
    if org:
        abertos, isol, pend = org.memoria.abertos(), org.imune.isolamento.listar(), org.autorizacoes.pendentes()
        nums += [("incidentes abertos", str(len(abertos))), ("em quarentena", str(len(isol))), ("pedidos esperando você", str(len(pend)))]
    ruim = (not v["ok"]) or abertos or pend
    frase = ("O livro-razão foi mexido: " + v["erro"]["motivo"] + "." if not v["ok"] else
             f"Livro-razão íntegro com {e['blocos']} bloco(s)"
             + (f"; {len(abertos)} incidente(s) aberto(s), {len(isol)} parte(s) em quarentena, {len(pend)} pedido(s) esperando o seu sim."
                if org else "; o organismo não está ligado nesta janela."))
    return _s("atencao" if ruim else "ok", frase, nums, "organismo livro_razao verificacao guardiao_decisoes")


def _memory() -> dict:
    nums, total = [], 0
    try:
        from core import memoria_grafo
        st = memoria_grafo.estatisticas()
        nos = sum(st["tipos"].values())
        total += nos
        nums += [("nós no grafo", str(nos)), ("ligações", str(st["arestas"]))]
    except Exception:
        pass
    try:
        from plugins import memoria_inteligente
        n = len(memoria_inteligente.todas())
        total += n
        nums.append(("lembranças com validade", str(n)))
    except Exception:
        pass
    try:
        from core import caixa_preta
        n = len(caixa_preta.erros())
        total += n
        nums.append(("lições da caixa-preta", str(n)))
    except Exception:
        pass
    return _s("ok" if total else "parado", f"{total} item(ns) guardado(s) entre grafo, lembranças e lições." if total else
              "Ainda sem lembranças guardadas.", nums, "memoria_grafo memoria_inteligente caixa_preta segundo_cerebro")


def _council() -> dict:
    reunioes, duelos = len(_lote2("multiverso", []) or []), len((_lote2("duelo", {}) or {}).get("historico", []))
    nums = [("conselheiros", str(len(CONSELHEIROS))), ("reuniões do multiverso", str(reunioes)), ("duelos com a FRIDAY", str(duelos))]
    return _s("ok", f"{len(CONSELHEIROS)} conselheiros de prontidão: 5 especialistas, 5 do multiverso, o revisor cético e a FRIDAY. "
                    "Entram quando você convoca.", nums, "conselho multiverso segunda_opiniao duelo_ia")


def _evolution() -> dict:
    from core import cerebro, metacognicao
    nums, prop = [], metacognicao.proposta()
    try:
        from core import evolucao
        d = evolucao.dados()
        nums += [("conversas avaliadas", str(d.get("turnos", 0))), ("testes de jeito de falar", "ligados" if d.get("ativo") else "pausados")]
    except Exception:
        pass
    medidos = [x for x in metacognicao.placar() if x["n"] >= 3]
    nums += [("sistemas com placar", str(len(medidos))),
             ("reflexo por semelhança", "ligado" if cerebro.semelhanca_ligada() else "desligado")]
    if prop:
        return _s("atencao", f"Há uma evolução esperando o seu sim: em {prop['n']} casos parecidos o cérebro teria acertado "
                             f"{prop['acertos']}.", nums, "metacognicao evolucao auto_melhoria")
    return _s("ok" if medidos or nums else "parado",
              (f"{len(medidos)} sistema(s) com acerto medido; nada muda sem prova e sem o seu sim." if medidos else
               "Medindo; ainda sem base para propor evoluções."), nums, "metacognicao evolucao auto_melhoria")


def _dream() -> dict:
    diario = _lote2("sonhos", []) or []
    ser = len((_lote2("serendipidade", {}) or {}).get("historico", []))
    if not diario:
        return _s("parado", "Ainda não sonhei: os sonhos rodam de madrugada, com umas 3 semanas de dados.",
                  [("sonhos", "0"), ("ideias cruzadas", str(ser))], "sonhos serendipidade")
    ult = diario[-1]
    achados = sum(len(s.get("achados", [])) for s in diario[-30:])
    return _s("ok", f"Último sonho em {ult.get('dia', '?')}: {len(ult.get('achados', []))} descoberta(s). "
                    f"{achados} nos últimos 30 sonhos.",
              [("sonhos", str(len(diario))), ("descobertas (30 últimos)", str(achados)), ("ideias cruzadas", str(ser))], "sonhos serendipidade")


def _lab() -> dict:
    exps = (_lote2("experimento_vida", {}) or {}).get("experimentos", [])
    ativos = [e for e in exps if e["estado"] == "ativo"]
    provados = [e for e in exps if (e.get("resultado") or {}).get("p", 1) <= 0.05]
    nums = [("experimentos rodando", str(len(ativos))), ("terminados", str(len(exps) - len(ativos))), ("com efeito comprovado", str(len(provados)))]
    try:
        from plugins import laboratorio
        from plugins._comum import ler_json
        nums.append(("testes de código", str(len(ler_json(laboratorio._HIST, []) or []))))
    except Exception:
        pass
    try:
        from plugins import criador_ferramentas
        nums.append(("ferramentas criadas", str(len(criador_ferramentas.criados()))))
    except Exception:
        pass
    propostas = len(_ler().get("propostas", []))
    frase = (f"{len(ativos)} experimento(s) rodando, {len(provados)} efeito(s) comprovado(s)"
             + (f"; {propostas} proposta(s) de experimento esperando você." if propostas else "."))
    return _s("ok" if exps or propostas else "parado", frase if exps or propostas else
              "Nenhum experimento ainda: peça 'que experimentos você sugere?'.", nums, "experimento_vida laboratorio criador_ferramentas")


_FUNCOES = {"brain": _brain, "heart": _heart, "immune": _immune, "memory": _memory, "council": _council,
            "evolution": _evolution, "dream": _dream, "lab": _lab}


def sistemas() -> list[dict]:
    """O estado REAL de cada um dos 8 sistemas agora. Sistema que falhar ao responder aparece como 'sem resposta'."""
    out = []
    for sid, nome, papel in SISTEMAS:
        try:
            s = _FUNCOES[sid]()
        except Exception as e:
            s = _s("parado", f"Sem resposta agora ({type(e).__name__}).", [], "")
        out.append({"id": sid, "nome": nome, "papel": papel, **s})
    return out


def consciencia(ss: list[dict] | None = None) -> str:
    """Uma frase com o estado do conjunto. Pura quando recebe a lista."""
    ss = ss if ss is not None else sistemas()
    ok = [s for s in ss if s["estado"] == "ok"]
    at = [s for s in ss if s["estado"] == "atencao"]
    pa = [s for s in ss if s["estado"] == "parado"]
    partes = [f"OMEGA: {len(ok)} de {len(ss)} sistemas em ordem"]
    if at:
        partes.append("pedem atenção " + ", ".join(s["nome"] for s in at))
    if pa:
        partes.append("ainda sem dados " + ", ".join(s["nome"] for s in pa))
    return "; ".join(partes) + "."


# ─────────────────────────────────────────────────────────── ciclo ───
def ciclo(agora: float | None = None) -> dict:
    """Uma volta do ciclo OMEGA. Não inicia experimento nem liga evolução: só propõe. Devolve passos e novidades."""
    agora = agora or time.time()
    passos, novidades = [], []

    def passo(sistema: str, texto: str) -> None:
        passos.append({"sistema": sistema, "texto": texto})

    # DREAM → BRAIN → LAB
    diario = _lote2("sonhos", []) or []
    n_achados = len(diario[-1].get("achados", [])) if diario else 0
    passo("DREAM", f"{n_achados} padrão(ões) no último sonho." if diario else "Ainda sem sonhos (rodam de madrugada).")
    propostas = []
    try:
        from plugins import experimento_vida
        desc = experimento_vida.descobertas()
        passo("BRAIN", f"{len(desc)} padrão(ões) viraram hipótese que dá para testar (a causa é algo que você controla)."
              if desc else "Nenhum padrão testável agora.")
        ja = {(norm_(e["tratamento"]), e["medida"]) for e in experimento_vida._est()["experimentos"]}
        propostas = [d for d in desc if (norm_(d["tratamento"]), d["efeito"]) not in ja][:3]
        passo("LAB", (f"{len(propostas)} experimento(s) proposto(s); começam só com o seu sim." if propostas else
                      "Sem experimento novo para propor."))
    except Exception as e:
        passo("LAB", f"Não consegui montar propostas ({type(e).__name__}).")
    # EVOLUTION
    try:
        from core import metacognicao
        feito = metacognicao.avaliar_evolucao(agora)
        prop = metacognicao.proposta()
        if feito:
            novidades.append(metacognicao.texto_de(feito))
        passo("EVOLUTION", metacognicao.texto_de(feito) if feito else
              ("Há uma evolução esperando o seu sim." if prop else "Placar conferido; nenhuma evolução a propor ou desfazer."))
    except Exception as e:
        passo("EVOLUTION", f"Não consegui conferir o placar ({type(e).__name__}).")
    # IMMUNE
    integro = True
    try:
        from core import livro_razao
        v = livro_razao.verificar()
        integro = v["ok"]
        if not integro:
            novidades.append(f"ATENÇÃO: o livro-razão foi mexido no bloco {v['erro']['n']} ({v['erro']['motivo']}).")
        passo("IMMUNE", f"Livro-razão íntegro ({v['blocos']} blocos)." if integro else f"Livro-razão VIOLADO no bloco {v['erro']['n']}.")
    except Exception as e:
        passo("IMMUNE", f"Não consegui conferir o livro-razão ({type(e).__name__}).")
    # MEMORY
    with _lock:
        d = _ler()
        antigas = {(p["tratamento"], p["efeito"]) for p in d.get("propostas", [])}
        for p in propostas:
            if (p["tratamento"], p["efeito"]) not in antigas:
                novidades.append(f"Experimento sugerido: {p['texto']} Para tirar a prova: \"cria um experimento: {p['tratamento']}, "
                                 f"medindo {p['efeito']}\".")
        d["propostas"] = [{k: p[k] for k in ("texto", "tratamento", "efeito", "atraso")} for p in propostas]
        passo("MEMORY", f"Ciclo guardado ({min(60, len(d.get('ciclos', [])) + 1)} no histórico).")
        passo("COUNCIL", "De prontidão: convoque para decidir sobre o que o ciclo trouxe." if novidades else "De prontidão.")
        reg = {"ts": agora, "dia": date.fromtimestamp(agora).isoformat(), "passos": passos, "novidades": novidades, "integro": integro}
        d["ciclos"] = (d.get("ciclos", []) + [reg])[-60:]
        _gravar(d)
    try:
        from core import livro_razao
        livro_razao.registrar("omega.ciclo", {"resumo": f"{len(novidades)} novidade(s)", "integro": integro, "propostas": len(propostas)})
    except Exception:
        pass
    return reg


def norm_(t: str) -> str:
    try:
        from plugins._lote2 import norm
        return norm(t)
    except Exception:
        return str(t).lower().strip()


def ultimo_ciclo() -> dict | None:
    c = _ler().get("ciclos", [])
    return c[-1] if c else None


def propostas() -> list[dict]:
    return list(_ler().get("propostas", []))


def texto_ciclo(reg: dict) -> str:
    """O ciclo em português. Pura."""
    linhas = [f"{p['sistema']}: {p['texto']}" for p in reg["passos"]]
    return "Ciclo OMEGA:\n" + "\n".join(linhas) + ("\nNovidades:\n- " + "\n- ".join(reg["novidades"]) if reg["novidades"] else
                                                   "\nSem novidades: tudo em ordem.")


# ─────────────────────────────────────────────────────────── painel ───
CORES = {"ok": "#38bdf8", "atencao": "#fbbf24", "parado": "#64748b"}
ROTULO = {"ok": "em ordem", "atencao": "pede atenção", "parado": "ainda sem dados"}


def _anel(ss: list[dict]) -> str:
    """O desenho: o núcleo no centro e os 8 sistemas em volta, ligados a ele e entre si. Pura."""
    cx, cy, r = 210, 150, 112
    pts = [(cx + r * math.cos(-math.pi / 2 + i * math.pi / 4), cy + r * math.sin(-math.pi / 2 + i * math.pi / 4)) for i in range(len(ss))]
    linhas = "".join(f"<line x1='{cx}' y1='{cy}' x2='{x:.1f}' y2='{y:.1f}' stroke='{CORES[s['estado']]}' stroke-opacity='.55' stroke-width='1.6'/>"
                     for (x, y), s in zip(pts, ss))
    aro = "".join(f"<line x1='{a[0]:.1f}' y1='{a[1]:.1f}' x2='{b[0]:.1f}' y2='{b[1]:.1f}' stroke='#38bdf8' stroke-opacity='.22'/>"
                  for a, b in zip(pts, pts[1:] + pts[:1]))
    nos = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='27' fill='#0b1220' stroke='{CORES[s['estado']]}' stroke-width='2.2'/>"
                  f"<text x='{x:.1f}' y='{y + 2.6:.1f}' text-anchor='middle' font-size='7.4' font-weight='700' fill='{CORES[s['estado']]}'>"
                  f"{s['nome']}</text>" for (x, y), s in zip(pts, ss))
    return (f"<svg viewBox='0 -8 420 316' role='img' aria-label='Os 8 sistemas ligados ao núcleo OMEGA' class='anel'>{aro}{linhas}"
            f"<circle cx='{cx}' cy='{cy}' r='34' fill='#0b1220' stroke='#38bdf8' stroke-width='2.4'/>"
            f"<circle cx='{cx}' cy='{cy}' r='43' fill='none' stroke='#38bdf8' stroke-opacity='.25'/>"
            f"<text x='{cx}' y='{cy + 9}' text-anchor='middle' font-size='27' font-weight='700' fill='#38bdf8'>Ω</text>{nos}</svg>")


def painel_html(ss: list[dict] | None = None, reg: dict | None = None, placar: list[dict] | None = None,
                agora: float | None = None) -> str:
    """A página do painel, com os dados passados (ou os de agora). Pura quando recebe tudo."""
    ss = ss if ss is not None else sistemas()
    reg = reg if reg is not None else ultimo_ciclo()
    if placar is None:
        try:
            from core import metacognicao
            placar = metacognicao.placar()
        except Exception:
            placar = []
    e = _html.escape
    cartoes = ""
    for s in ss:
        nums = "".join(f"<div class='n'><b>{e(v)}</b><span>{e(k)}</span></div>" for k, v in s["numeros"][:6])
        cartoes += (f"<section class='c {s['estado']}'><header><h2>{e(s['nome'])}</h2><em>{e(ROTULO[s['estado']])}</em></header>"
                    f"<p class='papel'>{e(s['papel'])}</p><p>{e(s['frase'])}</p><div class='nums'>{nums}</div>"
                    f"<p class='pecas'>{e(' · '.join(s['pecas']))}</p></section>")
    if reg:
        passos = "".join(f"<li><b>{e(p['sistema'])}</b> {e(p['texto'])}</li>" for p in reg["passos"])
        novid = ("<ul class='nov'>" + "".join(f"<li>{e(n)}</li>" for n in reg["novidades"]) + "</ul>") if reg["novidades"] else \
            "<p class='papel'>Sem novidades no último ciclo.</p>"
        bloco_ciclo = (f"<h3>Último ciclo — {time.strftime('%d/%m %H:%M', time.localtime(reg['ts']))}</h3><ol>{passos}</ol>{novid}")
    else:
        bloco_ciclo = "<h3>Ciclo OMEGA</h3><p class='papel'>Ainda não rodou. Diga “Jarvis, roda o ciclo OMEGA”.</p>"
    if placar:
        try:
            from core import metacognicao
            linhas = "".join(f"<li>{e(metacognicao.frase_de(x))}</li>" for x in placar)
        except Exception:
            linhas = ""
        bloco_placar = f"<h3>O quanto confiar em mim (medido)</h3><ul>{linhas}</ul>"
    else:
        bloco_placar = "<h3>O quanto confiar em mim (medido)</h3><p class='papel'>Ainda sem previsões conferidas para medir.</p>"
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60"><title>J.A.R.V.I.S OMEGA</title><style>
:root{{--fundo:#050a14;--carta:#0b1220;--borda:#1e293b;--texto:#e2e8f0;--fraco:#94a3b8;--azul:#38bdf8;--ambar:#fbbf24;--cinza:#64748b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--fundo);color:var(--texto);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:20px 16px 40px}}
h1{{margin:0;font-size:clamp(26px,6vw,40px);letter-spacing:.06em;color:var(--azul);text-align:center}}
.sub{{text-align:center;color:var(--fraco);letter-spacing:.14em;font-size:12px;text-transform:uppercase;margin:2px 0 6px}}
.estado{{text-align:center;margin:0 0 4px;font-weight:600}}.anel{{display:block;width:min(420px,100%);margin:0 auto}}
.grade{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:8px}}
.c{{background:var(--carta);border:1px solid var(--borda);border-top:3px solid var(--azul);border-radius:14px;padding:14px}}
.c.atencao{{border-top-color:var(--ambar)}}.c.parado{{border-top-color:var(--cinza)}}
.c header{{display:flex;justify-content:space-between;align-items:baseline;gap:8px}}.c h2{{margin:0;font-size:18px;letter-spacing:.05em}}
.c em{{font-style:normal;font-size:12px;color:var(--azul)}}.c.atencao em{{color:var(--ambar)}}.c.parado em{{color:var(--fraco)}}
.c p{{margin:6px 0}}.papel{{color:var(--fraco);font-size:13px}}
.nums{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:8px}}
.n b{{display:block;font-size:17px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}}.n span{{color:var(--fraco);font-size:12px}}
.pecas{{color:var(--cinza);font-size:11.5px;margin-top:10px;overflow-wrap:anywhere}}
.dupla{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-top:12px}}
.caixa{{background:var(--carta);border:1px solid var(--borda);border-radius:14px;padding:14px}}
h3{{margin:0 0 8px;font-size:15px;color:var(--azul);letter-spacing:.04em}}ol,ul{{margin:0;padding-left:20px}}li{{margin:4px 0}}
.nov li{{color:var(--ambar)}}footer{{color:var(--cinza);font-size:12px;text-align:center;margin-top:18px}}
</style></head><body><main>
<h1>J.A.R.V.I.S OMEGA</h1><p class="sub">Os 8 sistemas funcionando como um só</p>
<p class="estado">{e(consciencia(ss))}</p>{_anel(ss)}
<div class="grade">{cartoes}</div>
<div class="dupla"><div class="caixa">{bloco_ciclo}</div><div class="caixa">{bloco_placar}</div></div>
<footer>Dados reais deste PC às {time.strftime('%H:%M:%S', time.localtime(agora or time.time()))}. A página se atualiza sozinha a cada minuto enquanto o JARVIS estiver aberto.</footer>
</main></body></html>"""


def arquivo_painel() -> Path:
    from plugins._comum import pasta_jarvis
    return pasta_jarvis("Omega") / "omega.html"


def escrever_painel() -> Path:
    arq = arquivo_painel()
    arq.write_text(painel_html(), encoding="utf-8")
    return arq


def abrir_painel(minutos: int = 20) -> Path:
    """Escreve e abre o painel; o relógio central o mantém fresco pelos próximos minutos."""
    arq = escrever_painel()
    with _lock:
        d = _ler()
        d["painel_ate"] = time.time() + minutos * 60
        _gravar(d)
    from plugins._comum import abrir_no_sistema
    abrir_no_sistema(str(arq))
    return arq


def manter_painel() -> bool:
    """Relógio central (1 min): reescreve o painel enquanto ele foi aberto há pouco."""
    if time.time() < (_ler().get("painel_ate") or 0):
        escrever_painel()
        return True
    return False
