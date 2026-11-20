"""
MINER AI no JARVIS (fork PT-BR 3.9) — mineração real de cripto com energia, segurança e honestidade em primeiro lugar.

    "Jarvis, o miner ai compensa?"                        "Jarvis, configura o miner ai: carteira bitcoin bc1q…"
    "Jarvis, inicia o miner ai no bitcoin"                "Jarvis, inicia o miner ai na monero"
    "Jarvis, abre o painel do miner ai"                   "Jarvis, como está o miner ai?"
    "Jarvis, pausa o miner ai" / "retoma" / "para o miner ai"
    "Jarvis, miner ai no modo econômico, só das 22h às 7h, CPU 30%, temperatura máxima 75"

Bitcoin: Python puro, sem instalar nada, numa pool solo de verdade (cada share é trabalho real; só um bloco paga).
Monero: pelo XMRig que você baixou (o mais eficiente no processador). Detalhes e regras: miner_ai/__init__.py.
Iniciar sempre pede confirmação na tela mostrando a simulação do cérebro. Nunca no celular, nunca escondido,
nunca liga sozinho, nunca guarda chave privada. Liga e desliga ficam no livro-razão.
"""
from __future__ import annotations

import re

from plugins import _comum
from plugins._lote2 import P, norm, rodar

PLUGIN = P("miner_ai", "MINER AI: real crypto mining (BTC pure Python, XMR via XMRig) with energy limits, honest profit brain and dashboard.",
           "estado | calcular | iniciar | pausar | retomar | parar | painel | configurar | recomendar | sessoes",
           "iniciar: moeda (btc or xmr) — shows the brain's simulation and asks on-screen confirmation. calcular: is it worth it "
           "(simulation). configurar: ajustes as text 'key=value, key=value' with keys carteira_btc, carteira_xmr (PUBLIC addresses only), "
           "xmrig (path), tarifa (R$/kWh), cpu_max (%), temperatura_max (°C), economico (sim/nao), horarios (22:00-07:00), threads, "
           "horas_max, watts_medidos, tdp_watts, pool_btc, pool_xmr. painel: opens the dashboard. estado: live numbers with labels "
           "(real, confirmado, pendente, simulacao, custos). Never accept private keys or seed phrases.",
           "moeda ajustes")

APELIDOS = {"cpu": "cpu_max", "temperatura": "temperatura_max", "temperatura maxima": "temperatura_max", "luz": "tarifa",
            "carteira bitcoin": "carteira_btc", "carteira btc": "carteira_btc", "carteira monero": "carteira_xmr",
            "carteira xmr": "carteira_xmr", "horas": "horas_max", "modo economico": "economico", "horario": "horarios"}


def _ctl():
    from miner_ai.controlador import controlador
    return controlador(avisar=lambda t: _comum.avisar(None, t, "miner_ai"))


def _livro(acao: str, dados: dict) -> None:
    try:
        from core import livro_razao
        livro_razao.registrar("miner_ai", {"acao": acao, **dados})
    except Exception:
        pass


def moeda_de(texto) -> str | None:
    t = norm(texto)
    if re.search(r"\b(xmr|monero)\b", t):
        return "xmr"
    if re.search(r"\b(btc|bitcoin|bitcoins|bicoin|biticoin)\b", t):
        return "btc"
    return None


def ler_ajustes(texto) -> dict:
    """'carteira_btc=bc1q..., tarifa=0,98; economico=sim' → dict. Pura."""
    out = {}
    for parte in re.split(r"[;\n]|,\s*(?=[a-z_ ]+\s*[=:])", str(texto or "")):
        if "=" in parte or ":" in parte:
            k, v = re.split(r"[=:]", parte, maxsplit=1)
            k = norm(k).strip().replace("-", " ")
            out[APELIDOS.get(k, k.replace(" ", "_"))] = v.strip()
    return out


def _estado(p, pl):
    e = _ctl().estado()
    if not e["rodando"]:
        s = (e["sessoes"] or [None])[-1]
        return "O MINER AI está parado." + (f" Última sessão: {s['moeda'].upper()}, {s['horas']:.1f} h, {s['shares']} share(s), "
                                           f"luz ≈ R$ {s['custo']:.2f}." if s else "") + " Diga 'o miner ai compensa?' para ver as contas."
    d = e["desempenho"]
    t = (f"MINER AI minerando {e['nome_moeda']}: {d['hashrate']:,.0f} H/s, {d['threads']} núcleo(s). "
         f"Real: {e['real']['shares_aceitos']} share(s) aceitos. Luz estimada: R$ {e['custos']['reais']:.2f} "
         f"({e['custos']['kwh']:.3f} kWh).").replace(",", ".")
    if d["pausado"]:
        t += f" Pausado: {d['motivo_pausa']}."
    if d["temperatura"] is not None:
        t += f" {d['temperatura']:.0f} °C."
    if e["confirmado"]["valor"] is not None:
        t += f" Confirmado: {e['confirmado']['valor']} {e['moeda'].upper()} ({e['confirmado']['o_que_e']})."
    return t


def _calcular(p, pl):
    ctl = _ctl()
    ctl.atualizar_mercado()
    sims = ctl.simulacoes()
    m = moeda_de(p.get("moeda"))
    partes = [sims[k]["veredito"] for k in ([m] if m else sims)]
    return "Simulação do cérebro (não é dinheiro): " + " ".join(partes)


def _recomendar(p, pl):
    from miner_ai import cerebro, config
    ctl = _ctl()
    ctl.atualizar_mercado()
    dicas = cerebro.recomendar(config.carregar(), config.ler_json("historico.json", []) or [], ctl.simulacoes())
    return "O cérebro do MINER AI recomenda: " + " ".join(f"({i}) {d}" for i, d in enumerate(dicas, 1))


def _iniciar(p, pl):
    ctl = _ctl()
    moeda = moeda_de(p.get("moeda")) or "btc"
    erros = ctl.problemas(moeda)
    if erros:
        return "Ainda não dá para iniciar: " + "; ".join(erros) + ". Configure com 'configura o miner ai: carteira_btc=…'."
    if ctl.motor:
        return f"O MINER AI já está minerando {ctl.moeda.upper()}."
    ctl.atualizar_mercado()
    sim = ctl.simulacoes()[moeda]

    def ligar():
        ok, msg = ctl.iniciar(moeda)
        if ok:
            _livro("iniciou", {"moeda": moeda})
            try:
                from miner_ai import painel
                _comum.abrir_no_sistema(painel.iniciar(ctl))
            except Exception:
                pass
        return msg
    from core import confirm
    return confirm.request("miner-ai-iniciar", f"Minerar {'Bitcoin' if moeda == 'btc' else 'Monero'} de verdade no seu PC?",
                           sim["veredito"] + " A luz é sua; pode parar quando quiser.", ligar)


def _parar(p, pl):
    r = _ctl().parar("você pediu")
    if "parado (" in r:
        _livro("parou", {})
    return r


def _painel(p, pl):
    from miner_ai import painel
    url = painel.iniciar(_ctl())
    _comum.abrir_no_sistema(url)
    return f"Painel do MINER AI aberto ({url})."


def _configurar(p, pl):
    from miner_ai import config, seguranca
    texto = p.get("ajustes") or ""
    segredo = seguranca.parece_segredo(texto)
    if segredo:
        return (f"Isso parece {segredo}. NUNCA me diga isso: quem tem leva o seu dinheiro. "
                "Eu só preciso do endereço PÚBLICO de receber. Não guardei nada.")
    mud = ler_ajustes(texto)
    if not mud:
        cfg = config.carregar()
        return ("MINER AI: " + ", ".join(f"{k}={seguranca.mascarar(v) if k.startswith('carteira') else v}" for k, v in cfg.items()
                                          if k in ("carteira_btc", "carteira_xmr", "xmrig", "tarifa", "cpu_max", "temperatura_max",
                                                   "economico", "horarios", "horas_max")) + ".")
    cfg, erros = config.alterar(mud)
    feitos = [k for k in mud if k in cfg and not any(e.startswith(k) for e in erros)]
    return (("Guardei: " + ", ".join(feitos) + ". ") if feitos else "") + ("Problemas: " + "; ".join(erros) + "." if erros else "")


def _sessoes(p, pl):
    from miner_ai import config
    ss = config.ler_json("sessoes.json", []) or []
    if not ss:
        return "O MINER AI ainda não minerou."
    horas = sum(s["horas"] for s in ss)
    custo = sum(s["custo"] for s in ss)
    shares = sum(s["shares"] for s in ss)
    blocos = sum(s["blocos"] for s in ss)
    return (f"{len(ss)} sessão(ões), {horas:.1f} h, {shares} share(s) aceitos, {blocos} bloco(s), luz estimada R$ {custo:.2f}. "
            "Dinheiro de verdade só aparece como 'confirmado' no painel (blockchain ou pagamento da pool).")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"estado": _estado, "calcular": _calcular, "iniciar": _iniciar, "pausar": lambda p, pl: _ctl().pausar(),
                              "retomar": lambda p, pl: _ctl().retomar(), "parar": _parar, "painel": _painel,
                              "configurar": _configurar, "recomendar": _recomendar, "sessoes": _sessoes}, player)
