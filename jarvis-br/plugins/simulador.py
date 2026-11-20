"""
Simulador de futuros — ideia 3 (fork PT-BR 1.4).

Antes de mexer em arquivos ou no sistema, o JARVIS calcula o que vai acontecer,
SEM fazer nada ainda, em três cenários:

    melhor     tudo dá certo
    provável   o que normalmente acontece (arquivos em uso, apps que demoram…)
    pior       o que pode dar errado, e se dá para desfazer

    "Jarvis, simula a limpeza"
    "Jarvis, o que acontece se eu organizar os downloads?"
    "Jarvis, simula o modo jogo"           (quais apps fecham, se há trabalho sem salvar)
    "Jarvis, simula desligar o PC"         (janelas com trabalho não salvo)
    "Jarvis, simula o protocolo foco"      (o que abre, o que fecha, quanto demora)
    "Jarvis, simula mover a pasta Projetos para D:"
    "Jarvis, compara limpar só os temporários com limpar tudo"

Toda simulação termina com a avaliação do guardião de decisões. Nada é
alterado: são só leituras.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from plugins._comum import duracao, mostrar, tamanho

PLUGIN = {
    "name": "simulador",
    "brief": "Dry-run an action: best / likely / worst case before doing it.",
    "description": (
        "Future simulator: dry-runs an action WITHOUT doing it and returns best, likely and worst "
        "case, plus success chance %, time, feasibility and danger (2.14; any other task goes to the "
        "probability engine). action='simular' with alvo = limpeza | organizar_downloads | modo_jogo | desligar | "
        "reiniciar | fechar (nome) | protocolo (nome) | mover | copiar; for mover/copiar give origem "
        "and destino; categorias for limpeza. action='comparar' with planos = two or more alvos "
        "separated by ' vs ' (e.g. 'limpeza temporarios vs limpeza tudo'). Use for 'o que acontece "
        "se…', 'simula…', 'compara…'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "simular | comparar"},
            "alvo": {"type": "STRING"}, "nome": {"type": "STRING"},
            "origem": {"type": "STRING"}, "destino": {"type": "STRING"},
            "categorias": {"type": "STRING"}, "planos": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_NAO_SALVO = re.compile(r"(^\*|\*\s|•|●|\bsem t[ií]tulo\b|\buntitled\b|n[aã]o salvo|unsaved|\(modificado\))", re.I)


def _cenarios(nome, melhor, provavel, pior, reversivel, guardiao=None, extra=None) -> dict:
    return {"nome": nome, "melhor": melhor, "provavel": provavel, "pior": pior,
            "reversivel": reversivel, "guardiao": guardiao, "detalhes": extra or []}


def _janelas_nao_salvas(processos: set[str] | None = None) -> list[dict]:
    try:
        from plugins import _janelas
        js = _janelas.listar()
    except Exception:
        return []
    from plugins._protecao import nome_base
    return [j for j in js if _NAO_SALVO.search(j["titulo"])
            and (processos is None or nome_base(j["processo"]) in processos)]


# ── simulações ─────────────────────────────────────────────────────────────────
def sim_limpeza(categorias: str = "") -> dict:
    from plugins import limpeza
    cats = limpeza.categorias_de(categorias)
    prev = limpeza.previa(cats, 3600)
    total = sum(prev.values())
    # arquivos mexidos no último dia costumam estar em uso: estimativa do que fica
    em_uso = 0
    for cat in cats:
        if cat == "lixeira":
            continue
        dia = sum(limpeza.medir(limpeza.raizes(cat), 3600, segundos=4).values()) - \
            sum(limpeza.medir(limpeza.raizes(cat), 86400, segundos=4).values())
        em_uso += max(0, dia) * 0.5
    provavel = max(0, total - em_uso)
    from plugins._guardiao import avaliar
    return _cenarios(
        f"limpeza ({', '.join(limpeza.NOMES[c] for c in cats)})",
        f"libera {tamanho(total)}",
        f"libera uns {tamanho(provavel)}; arquivos em uso ficam para depois",
        "algum programa aberto perde o cache e fica mais lento na primeira vez; nenhum documento é "
        "apagado (só temporários, caches e lixeira)" + (" — a lixeira esvaziada não volta" if "lixeira" in cats else ""),
        False, avaliar("limpeza", {"action": "executar"}).texto(),
        [f"{limpeza.NOMES[k]}: {tamanho(v)}" for k, v in prev.items()])


def sim_organizar() -> dict:
    from plugins import downloads as dl
    raiz = dl.pasta()
    movimentos, conflitos, recentes = [], 0, 0
    for nome, (_t, mtime) in dl._listar(raiz).items():
        cat = dl.categoria(nome)
        if not cat or dl.eh_parcial(nome):
            continue
        if time.time() - mtime < 120:
            recentes += 1
            continue
        destino = raiz / cat / nome
        if destino.exists():
            conflitos += 1
        movimentos.append(f"{nome} → {cat}/")
    if not movimentos:
        return _cenarios("organizar downloads", "nada a mover", "nada a mover", "nada", True)
    return _cenarios(
        "organizar downloads", f"{len(movimentos)} arquivos vão para as pastas por tipo",
        f"{len(movimentos)} movidos" + (f"; {conflitos} ganham '(2)' no nome por já existir igual" if conflitos else "")
        + (f"; {recentes} recém-baixados ficam para depois" if recentes else ""),
        "um atalho ou programa que apontava para o arquivo em Downloads deixa de achar — 'Jarvis, desfaz' "
        "põe tudo de volta", True, None, movimentos[:40])


def sim_modo_jogo() -> dict:
    import psutil

    from plugins import modo_jogo
    from plugins._protecao import nome_base, proteger_processo
    c = modo_jogo._cfg()
    alvos = {nome_base(n) for n in modo_jogo.lista_fechar(c)}
    fechar, ram = {}, 0
    for p in psutil.process_iter(["name", "memory_info"]):
        n = nome_base(p.info.get("name") or "")
        if n in alvos and not proteger_processo(p):
            fechar[n] = fechar.get(n, 0) + (p.info["memory_info"].rss if p.info.get("memory_info") else 0)
            ram += p.info["memory_info"].rss if p.info.get("memory_info") else 0
    nao_salvos = _janelas_nao_salvas(set(fechar))
    pior = ("perde o que não foi salvo em: " + ", ".join(j["titulo"][:40] for j in nao_salvos)) if nao_salvos \
        else "nenhuma janela com trabalho não salvo nos apps que fecham"
    return _cenarios(
        "modo jogo", f"fecha {len(fechar)} app(s) e libera {tamanho(ram)} de RAM, alto desempenho, sem notificações",
        "o jogo ganha um pouco de folga; o ganho maior é com pouca RAM", pior, True, None,
        [f"fecha {n} ({tamanho(r)})" for n, r in fechar.items()] or ["nenhum app da lista está aberto"])


def sim_energia(op: str) -> dict:
    nao_salvos = _janelas_nao_salvas()
    from plugins._guardiao import avaliar
    try:
        from plugins import _janelas
        abertas = len(_janelas.listar())
    except Exception:
        abertas = 0
    pior = ("perde o trabalho não salvo em: " + "; ".join(j["titulo"][:50] for j in nao_salvos[:6])) \
        if nao_salvos else "programas que não salvam sozinhos perdem o estado"
    return _cenarios(
        f"{op} o PC", f"fecha {abertas} janela(s) e {'desliga' if op == 'desligar' else 'volta em ~1 minuto'}",
        "alguns programas perguntam se querem salvar e seguram o desligamento", pior, False,
        avaliar("controle_pc", {"action": op}).texto(),
        [f"NÃO SALVO: {j['titulo']}" for j in nao_salvos] or ["nenhuma janela com sinal de trabalho não salvo"])


def sim_fechar(nome: str) -> dict:
    from core import appidentity
    from plugins._protecao import motivo_protecao
    achados = appidentity.running(nome)
    if not achados:
        return _cenarios(f"fechar {nome}", f"{nome} não está aberto", "nada acontece", "nada", True)
    m = achados[0]
    prot = motivo_protecao(m.name, m.pid)
    if prot:
        return _cenarios(f"fechar {nome}", "não será fechado", "não será fechado", f"bloqueado: {prot}", True)
    nao = [t for t in m.titles if _NAO_SALVO.search(t)]
    return _cenarios(f"fechar {m.label}", "fecha normalmente", "fecha; apps com documentos abertos podem perguntar se salvam",
                     ("perde: " + "; ".join(nao)) if nao else "perde o estado (abas, posição) se o app não guardar",
                     False, None, m.titles[:10])


def sim_protocolo(nome: str) -> dict:
    from plugins import protocolos
    from plugins._indice_apps import procurar
    dados = protocolos._load()
    chave = protocolos._norm(nome)
    proto = dados.get(chave)
    if not proto:
        return _cenarios(f"protocolo {nome}", "não existe", "não existe", "não existe", True)
    detalhes, faltam = [], []
    for p in proto.get("passos", []):
        detalhes.append(protocolos.descrever_passo(p))
        if p.get("tipo") == "abrir":
            for app in protocolos._split(p.get("alvo")):
                if not procurar(app, 1):
                    faltam.append(app)
    tempo = None
    try:
        from core import registro_uso
        execs = registro_uso.tarefas(time.time() - 60 * 86400, "protocolo")
        tempos = [t["ms"] for t in execs if t["nome"] == chave]
        if tempos:
            tempo = sum(tempos) / len(tempos) / 1000
    except Exception:
        pass
    return _cenarios(
        f"protocolo {chave}", f"{len(detalhes)} passos em ordem" + (f", ~{duracao(tempo)}" if tempo else ""),
        ("igual ao melhor" if not faltam else f"{', '.join(faltam)} pode(m) não abrir (não achei na lista de apps)")
        + (f"; costuma levar {duracao(tempo)}" if tempo else ""),
        "um app fechado pelo protocolo com trabalho não salvo perde esse trabalho" if any(
            p.get("tipo") == "fechar" for p in proto.get("passos", [])) else "nada grave: o protocolo só abre coisas",
        True, None, detalhes)


def _contar(origem: Path, prazo: float) -> tuple[int, int]:
    if origem.is_file():
        return 1, origem.stat().st_size
    n = tam = 0
    for dirpath, _d, arqs in os.walk(origem):
        if time.monotonic() > prazo:
            break
        for a in arqs:
            try:
                tam += os.path.getsize(os.path.join(dirpath, a))
                n += 1
            except OSError:
                pass
    return n, tam


def sim_mover(origem: str, destino: str, copiar: bool) -> dict:
    o = Path(os.path.expanduser(origem or ""))
    d = Path(os.path.expanduser(destino or ""))
    verbo = "copiar" if copiar else "mover"
    if not o.exists():
        return _cenarios(f"{verbo} {origem}", "origem não existe", "nada acontece", "nada", True)
    n, tam = _contar(o, time.monotonic() + 15)
    base = d if d.exists() and d.is_dir() else d.parent
    try:
        livre = shutil.disk_usage(base if base.exists() else Path(d.anchor or "/")).free
    except Exception:
        livre = None
    mesmo_disco = (o.resolve().anchor.lower() == (d.resolve().anchor.lower() if d.anchor else o.resolve().anchor.lower()))
    alvo = d / o.name if d.is_dir() else d
    conflito = alvo.exists()
    espaco_ok = livre is None or livre > tam * 1.05 or (mesmo_disco and not copiar)
    from plugins._guardiao import avaliar
    pior = []
    if not espaco_ok:
        pior.append(f"falta espaço: precisa de {tamanho(tam)} e há {tamanho(livre)} livres — a operação para no meio")
    if conflito:
        pior.append(f"já existe {alvo.name} no destino e pode ser sobrescrito")
    if not copiar and not mesmo_disco:
        pior.append("entre discos, mover = copiar + apagar; se algo falhar no meio, parte fica em cada lugar")
    velocidade = 400e6 if mesmo_disco else 80e6
    tempo = 1 if (mesmo_disco and not copiar) else tam / velocidade
    return _cenarios(
        f"{verbo} {o.name} → {d}", f"{n} arquivo(s), {tamanho(tam)}, em ~{duracao(tempo)}",
        f"~{duracao(tempo * 1.5)}" + ("; arquivos abertos em outro programa podem falhar" if n > 1 else ""),
        "; ".join(pior) or "nada grave", not conflito,
        avaliar("", {"origem": str(o), "destino": str(d)}, f"{verbo} {o} para {d}").texto(),
        [f"espaço livre no destino: {tamanho(livre) if livre is not None else '?'}"])


def simular(alvo: str, p: dict) -> dict:
    a = str(alvo or "").lower().strip()
    if a.startswith("limp"):
        return sim_limpeza(p.get("categorias") or a.replace("limpeza", "").replace("limpar", ""))
    if "download" in a or a.startswith("organiz"):
        return sim_organizar()
    if "jogo" in a:
        return sim_modo_jogo()
    if a.startswith(("deslig", "reinic")):
        return sim_energia("desligar" if a.startswith("deslig") else "reiniciar")
    if a.startswith("fech"):
        return sim_fechar(str(p.get("nome") or a.replace("fechar", "").strip()))
    if a.startswith("protocolo"):
        return sim_protocolo(str(p.get("nome") or a.replace("protocolo", "").strip()))
    if a.startswith(("mov", "copi")):
        return sim_mover(str(p.get("origem") or ""), str(p.get("destino") or ""), a.startswith("copi"))
    return _generico(alvo)


# ── 2.14: probabilidades em toda simulação ─────────────────────────────────────
def _generico(alvo: str) -> dict:
    """Qualquer tarefa fora da lista: o motor de probabilidades monta os três cenários."""
    try:
        from plugins import probabilidades as pb
        r = pb.calcular(alvo)
    except Exception as e:
        return _cenarios(alvo, "não sei simular isso", "", f"(motor de probabilidades falhou: {e})", True)
    t = r["tempo"]
    c = _cenarios(alvo, f"dá certo em ~{pb.falar_tempo(t['p10'])}",
                  f"{round(100 * r['chance'])}% de chance de dar certo, ~{pb.falar_tempo(t['p50'])}",
                  ("; ".join(r["impedimentos"]) or f"falha ou passa de {pb.falar_tempo(t['p90'])}")
                  + (f"; perigo {r['perigo']}" if r["perigo_n"] else ""),
                  r["reversivel"], r["guardiao"] or None,
                  [f"{f['lado']}: {f['nome']} ({f['explicacao']})" for f in r["fatores"]])
    c["prob"] = r
    return c


def com_chance(c: dict) -> dict:
    """Acrescenta chance de sucesso, tempo, viabilidade e perigo a uma simulação."""
    if c.get("prob") is not None:
        return c
    try:
        from plugins import probabilidades as pb
        c["prob"] = pb.calcular(c["nome"], usar_ia=False)
    except Exception:
        c["prob"] = None
    return c


def _texto(c: dict) -> str:
    base = (f"Simulei {c['nome']}. Melhor caso: {c['melhor']}. Provável: {c['provavel']}. "
            f"Pior caso: {c['pior']}. {'Dá para desfazer.' if c['reversivel'] else 'Não dá para desfazer.'}")
    r = c.get("prob")
    if r:
        from plugins import probabilidades as pb
        base += " " + pb.texto(r)
    return base


def _painel(c: dict) -> str:
    return "\n".join([f"MELHOR    {c['melhor']}", f"PROVÁVEL  {c['provavel']}", f"PIOR      {c['pior']}",
                      f"REVERSÍVEL: {'sim' if c['reversivel'] else 'NÃO'}"]
                     + ([f"GUARDIÃO: {c['guardiao']}"] if c.get("guardiao") else [])
                     + (["", _painel_prob(c["prob"])] if c.get("prob") else [])
                     + ([""] + [f"• {d}" for d in c["detalhes"]] if c["detalhes"] else []))


def _painel_prob(r: dict) -> str:
    from plugins import probabilidades as pb
    t = r["tempo"]
    return (f"CHANCE    {round(100 * r['chance'])}%   ·   TEMPO ~{pb.falar_tempo(t['p50'])} (até {pb.falar_tempo(t['p90'])})"
            f"\nVIÁVEL    {r['viabilidade']}   ·   PERIGO {r['perigo']} (grave: {round(100 * r['chance_grave'])}%)")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "simular").lower()
    try:
        if a == "comparar":
            planos = [x.strip() for x in re.split(r"\bvs\.?\b|\bversus\b|\bou\b", str(p.get("planos") or "")) if x.strip()]
            if len(planos) < 2:
                return "Diga dois planos para comparar, separados por 'vs'."
            cs = [com_chance(simular(x, {})) for x in planos]
            mostrar(player, "SIMULADOR — COMPARAÇÃO", "\n\n".join(f"### {c['nome']}\n{_painel(c)}" for c in cs))
            texto = " | ".join(f"{c['nome']}: provável {c['provavel']}; pior {c['pior']}"
                               + (f"; chance {round(100 * c['prob']['chance'])}%" if c.get("prob") else "") for c in cs)
            com = [c for c in cs if c.get("prob")]
            if len(com) >= 2:
                melhor = max(com, key=lambda c: c["prob"]["chance"] - .25 * c["prob"]["chance_grave"])
                texto += f". Senhor, eu iria de {melhor['nome']}."
            return texto
        alvo = str(p.get("alvo") or "")
        if not alvo:
            return "O que devo simular?"
        c = com_chance(simular(alvo, p))
        mostrar(player, f"SIMULADOR — {c['nome'][:40].upper()}", _painel(c))
        return _texto(c) + " Nada foi feito ainda."
    except Exception as e:
        return f"O simulador falhou: {e}"



