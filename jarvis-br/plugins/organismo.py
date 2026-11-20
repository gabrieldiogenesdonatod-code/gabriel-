"""
Organismo (3.1): converse com o JARVIS BIOLOGICAL CORE — o corpo digital do JARVIS.

O JARVIS tem cérebro (IA básica local que aprende), coração, sistema nervoso, circulação, DNA digital,
sistema imunológico de 8 camadas e regeneração. Ele vigia a si mesmo, isola o que adoece, conserta o
que é seguro sozinho e pede o seu SIM para o resto.

    "Jarvis, como está a sua saúde?"          "Jarvis, abre o painel do organismo"
    "Jarvis, mostra os incidentes"            "Jarvis, por que você isolou o clima?"
    "Jarvis, o que está em quarentena?"       "Jarvis, libera o rastreio"
    "Jarvis, mostra os reparos pendentes"     "Jarvis, faz um exame completo"
    "Jarvis, roda as vacinas"                 "Jarvis, o que você aprendeu se consertando?"
    "Jarvis, relatório da defesa"             "Jarvis, reconhece as mudanças no DNA"
    "Jarvis, boletim de saúde"

Aprovar reparo, mudar o DNA, aumentar a autonomia ou desligar as proteções: só pelo botão da tela
(banner CONFIRMAR do PC ou aba Corpo do celular). Esta ferramenta pede, mas nunca aprova sozinha.
"""

from __future__ import annotations

from plugins._lote2 import P, rodar

PLUGIN = P("organismo", "JARVIS's digital body (Biological Core): health, immune system, quarantine, repairs, DNA integrity, "
                        "self-healing report and dashboard.",
           "saude | painel | incidentes | explicar | quarentena | liberar | reparos | mostrar | exame | vacinas | aprendizado | "
           "evolucao | dna | reconhecer | autonomia | boletim | desligar",
           "JARVIS self-monitoring organism. saude: health summary. painel: open the visual dashboard. incidentes: open problems. "
           "explicar: incidente (id) — why the brain decided. quarentena: isolated parts. liberar: modulo (and optional acao) — "
           "release from quarantine. reparos: repairs waiting for the user's on-screen approval; mostrar: id — show that request "
           "on screen again. exame: full checkup now. vacinas: run security self-tests. aprendizado: what the brain learned. "
           "evolucao: defense report and recommendations. dna: integrity. reconhecer: ask the user (on screen) to accept current "
           "files as the new DNA. autonomia: valor (observar|normal). boletim: health bulletin. desligar: ask on screen to turn "
           "the organism off. You can NEVER approve anything yourself; approvals happen only on the screen.",
           "incidente modulo acao id valor")


def _org(player=None):
    import biological_core
    return biological_core.iniciar(player)


def _sem(org) -> str | None:
    return None if org is not None else "O organismo está desligado (\"bio_desligado\" em config/api_keys.json)."


def _saude(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    if not org.coracao.batimentos:
        org.coracao.bater()
    return org.resumo_texto()


def _painel(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    import time
    from biological_core.dashboard.biological_dashboard import escrever
    org.coracao.bater()
    caminho = escrever(org)
    org.painel_ate = time.time() + 1800
    try:
        from plugins._comum import abrir_no_sistema
        abrir_no_sistema(caminho)
    except Exception:
        pass
    return f"Abri o painel do organismo (nota {org.saude.ultimo['nota']}/100). Ele se atualiza sozinho pelos próximos 30 minutos."


def _incidentes(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    abertos = org.memoria.abertos()
    resolvidos = org.memoria.incidentes("resolvido", limite=5)
    if not abertos and not resolvidos:
        return "Nenhum incidente registrado. O organismo está saudável."
    linhas = [f"#{i['id']} {i['modulo']}" + (f" ({i['arquivo']})" if i.get("arquivo") else "")
              + f" — {i['categoria']} ({i['gravidade']}), {i['estado']}, {i['ocorrencias']}×: "
              f"{i['mensagem'][:100]}" + (f" | tratamento: {i['tratamento']}" if i.get("tratamento") else "") for i in abertos[:8]]
    if resolvidos:
        linhas.append("Curados há pouco: " + "; ".join(f"#{i['id']} {i['modulo']} ({i.get('tratamento') or 'sozinho'})" for i in resolvidos))
    return (f"{len(abertos)} incidente(s) aberto(s).\n" if abertos else "Nenhum aberto.\n") + "\n".join(linhas) + \
        "\nPara entender uma decisão: 'explica o incidente N'."


def _explicar(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    alvo = str(p.get("incidente") or p.get("id") or p.get("modulo") or "").strip().lstrip("#")
    if alvo.isdigit():
        return org.cerebro.explicar(int(alvo))
    incs = [i for i in org.memoria.incidentes(limite=50) if alvo and alvo.lower() in i["modulo"].lower()]
    if not incs:
        incs = org.memoria.incidentes(limite=1)
    return org.cerebro.explicar(incs[0]["id"]) if incs else "Ainda não há decisões para explicar."


def _quarentena(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    iso = org.imune.isolamento.listar()
    if not iso:
        return "Nada isolado: todas as partes estão liberadas."
    return "Isolados:\n" + "\n".join(f"• {i['chave'].replace('|*', '').replace('|', ' → ')} ({i['tipo']}): {i['motivo']}"
                                     + (f" — volta em {i['volta_em']}" if i.get("volta_em") else "") for i in iso) + \
        "\nPara liberar: 'libera o <nome>'."


def _liberar(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    mod = str(p.get("modulo") or "").strip().lower()
    if not mod:
        return "Diga qual parte liberar (ex.: 'libera o rastreio')."
    soltos = org.imune.isolamento.liberar(mod, p.get("acao") or None, por="usuario")
    for inc in org.memoria.abertos():
        if inc["modulo"] == mod:
            org.memoria.fechar(inc["id"], "liberado por você", humano=True, estado="liberado")
    return (f"Liberado: {', '.join(k.replace('|*', '') for k in soltos)}. Se ele voltar a falhar, eu isolo de novo — "
            "e fico mais tolerante com ele, porque você liberou.") if soltos else f"'{mod}' não estava isolado."


def _reparos(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    pend = org.autorizacoes.pendentes()
    if not pend:
        return "Nenhum reparo esperando você."
    org.autorizacoes.mostrar(pend[0]["id"])
    return ("Reparos esperando o seu sim (aprove no banner da tela ou na aba Corpo do celular):\n"
            + "\n".join(f"• {x['id']}: {x['titulo']} — {x['detalhe'][:140]}" for x in pend)
            + "\nColoquei o primeiro na tela agora. Eu não posso aprovar sozinho.")


def _mostrar(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    pid = str(p.get("id") or p.get("incidente") or "").strip().upper()
    r = org.autorizacoes.mostrar(pid)
    return {"na_tela": "Coloquei o pedido na tela: ele precisa apertar CONFIRMAR.",
            "ocupado": "Já tem outra confirmação na tela; quando ela sair eu mostro esta.",
            "sem_tela": "Aqui não há banner de confirmação: aprove pela aba Corpo do celular.",
            "nao_existe": "Esse pedido não existe (já foi respondido ou venceu)."}.get(r, r)


def _exame(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    n = org.sentinela.ronda(completa=True)
    dep = org.imune.detector.dependencias_ausentes()
    org.estado["dependencias"] = dep
    res = org.imune.evolucao.exercitar()
    org.coracao.bater()
    v = org.verificador.ultimo or {}
    partes = [f"Exame completo: DNA {org.dna.situacao}, integridade {v.get('integridade', 0):.0f}% "
              f"({len(v.get('modificados', []))} mudado(s), {len(v.get('novos', []))} novo(s), {len(v.get('ausentes', []))} sumido(s))",
              f"vacinas {sum(r['ok'] for r in res)}/{len(res)}",
              f"{n} sintoma(s) novo(s)"]
    if dep["essenciais"]:
        partes.append("pacotes ESSENCIAIS faltando: " + ", ".join(dep["essenciais"]))
    if dep["opcionais"]:
        partes.append(f"{len(dep['opcionais'])} pacote(s) opcional(is) faltando")
    return "; ".join(partes) + ". " + org.resumo_texto()


def _vacinas(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    res = org.imune.evolucao.exercitar()
    return f"Vacinas: {sum(r['ok'] for r in res)} de {len(res)} defesas passaram.\n" + "\n".join(
        f"{'✓' if r['ok'] else '✗'} {r['nome'].replace('_', ' ')} — {r['detalhe']}" for r in res)


def _aprendizado(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    a = org.cerebro.aprendizado()
    c = a["classificador"]
    linhas = [f"Cérebro: {a['decisoes']} decisão(ões)" + (f", acerto {a['acerto']:.0%}" if a["acerto"] is not None else "")
              + f". Classificador de erros: {c['exemplos']} exemplos ({c['aprendidos_com_voce']} aprendidos com você), {c['palavras']} palavras."]
    for t in a["tratamentos"][:8]:
        linhas.append(f"• {t['categoria']} → {t['tratamento']}: {t['sucessos']} de {t['sucessos'] + t['falhas']} deram certo")
    if a["em_observacao"]:
        linhas.append("Observando agora: " + "; ".join(a["em_observacao"]))
    return "\n".join(linhas)


def _evolucao(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    import time
    pontos = org.imune.prevencao.pontos()
    extra = {"dias_sem_ponto": int((time.time() - pontos[-1]["ts"]) // 86400) if pontos else 99,
             "pacotes_essenciais": (org.estado.get("dependencias") or {}).get("essenciais", [])}
    r = org.imune.evolucao.relatorio(7, org.cerebro.aprendizado(), extra)
    linhas = [f"Defesa nos últimos 7 dias: nota {r['nota_defesa']}/100. {r['total']} problema(s), {r['resolvidos']} curado(s)"
              + (f" ({r['taxa_automatica']:.0%} sozinho)" if r["taxa_automatica"] is not None else "")
              + (f", tempo mediano até curar {int(r['tempo_mediano_s'] // 60)} min" if r.get("tempo_mediano_s") else "") + "."]
    if r["por_modulo"]:
        linhas.append("Quem mais adoece: " + ", ".join(f"{m} ({n})" for m, n in r["por_modulo"][:4]) + ".")
    linhas += [f"• {x}" for x in r["recomendacoes"]] or ["Sem recomendações: a defesa está em dia."]
    return "\n".join(linhas)


def _dna(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    v = org.verificador.verificar()
    g = org.dna.resumo()
    return (f"DNA {g['situacao']}: {g['arquivos']} arquivos, versão {g['versao']}, {g['mutacoes']} mudança(s) autorizada(s). "
            f"Integridade agora {v['integridade']:.0f}%: {len(v['modificados'])} mudado(s), {len(v['novos'])} novo(s), "
            f"{len(v['ausentes'])} sumido(s)." + (" Exemplos: " + ", ".join((v["modificados"] + v["novos"])[:5]) if v["modificados"] or v["novos"] else "")
            + (" Se foi você, diga 'reconhece as mudanças no DNA' e confirme na tela." if v["modificados"] or v["novos"] or v["ausentes"] else ""))


def _reconhecer(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    ped = org.pedir_mutacao("reconhecido por você")
    return (f"Pedi a sua confirmação ({ped['id']}) para aceitar os arquivos atuais como o DNA novo. "
            + ("Está na tela: aperte CONFIRMAR." if ped.get("tela") == "na_tela" else "Aprove na tela (banner do PC ou aba Corpo do celular)."))


def _autonomia(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    from biological_core.config import autonomia
    valor = str(p.get("valor") or "").strip().lower()
    atual = autonomia()
    if valor not in ("observar", "normal"):
        return (f"Autonomia atual: {atual}. 'normal' = conserto sozinho o que é seguro e peço o resto; "
                "'observar' = só detecto, isolo o que trava e aviso.")
    if valor == atual:
        return f"A autonomia já está em '{atual}'."
    if valor == "observar":                                 # diminuir autonomia é sempre seguro
        return "Autonomia agora: observar. " + org.gravar_config("bio_autonomia", "observar")
    ped = org.pedir_config("bio_autonomia", "normal", "Aumentar a autonomia do organismo",
                           "Deixar o JARVIS consertar sozinho o que é seguro (isolar, esperar a internet, recarregar plugin)?")
    return f"Aumentar a autonomia precisa do seu sim na tela (pedido {ped['id']})."


def _boletim(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    b = org.boletim()
    return b or "Boletim: tudo tranquilo — nenhum problema nas últimas 24 horas."


def _desligar(p, pl):
    org = _org(pl)
    if org is None:
        return _sem(org)
    ped = org.pedir_config("bio_desligado", True, "Desligar o organismo (sistema imune)",
                           "Desligar o Biological Core? Sem ele não há portão de proteção, isolamento nem regeneração. Vale a partir do próximo início.")
    return f"Desligar as proteções precisa do seu sim na tela (pedido {ped['id']}). Eu não desligo sozinho."


ACOES = {"saude": _saude, "painel": _painel, "incidentes": _incidentes, "explicar": _explicar, "quarentena": _quarentena,
         "liberar": _liberar, "reparos": _reparos, "mostrar": _mostrar, "exame": _exame, "vacinas": _vacinas,
         "aprendizado": _aprendizado, "evolucao": _evolucao, "dna": _dna, "reconhecer": _reconhecer,
         "autonomia": _autonomia, "boletim": _boletim, "desligar": _desligar}


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, ACOES, player, "Organismo")


def on_session_start(player) -> None:
    """Liga o organismo a cada sessão (idempotente) e entrega o boletim da manhã, se houver."""
    org = _org(player)
    if org is None:
        return
    try:
        from plugins import catalogo
        if hasattr(catalogo, "_INDICE"):
            limpar = getattr(catalogo._INDICE, "clear", None)
            if limpar and limpar not in org.coracao.caches:
                org.coracao.caches.append(limpar)
    except Exception:
        pass
    org.entregar_boletim()
