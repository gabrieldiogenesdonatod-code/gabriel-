"""
Mineração de cripto (fork PT-BR 3.7) — calculadora honesta + controle do XMRig.

    "Jarvis, compensa minerar?"                "Jarvis, quanto dá minerar bitcoin no meu PC?"
    "Jarvis, minha luz é 0,98 o kWh"           "Jarvis, configura a mineração: carteira 4..., xmrig em C:\\xmrig\\xmrig.exe"
    "Jarvis, liga a mineração"                 "Jarvis, como está a mineração?"
    "Jarvis, desliga a mineração"              "Jarvis, relatório da mineração"

A CALCULADORA usa a dificuldade da rede e o preço de agora: quanto o seu PC ganharia por dia em cada moeda,
quanto gasta de luz e se paga a conta. Ela diz a verdade: Bitcoin no processador rende praticamente zero
(só máquinas ASIC ganham); a única moeda que faz sentido no processador é a Monero (XMR, algoritmo RandomX).
LTC e DOGE também são de ASIC; ETH não se minera mais desde 2022.

O CONTROLE liga e desliga o XMRig, o minerador oficial de código aberto (github.com/xmrig/xmrig), que VOCÊ
baixa e cuja carteira é SUA. Regras de segurança:
    • nunca baixa nada sozinho e nunca mexe no antivírus (o Windows Defender costuma marcar o XMRig como
      "potencialmente indesejado" porque vírus usam ele escondido: permitir ou não é decisão sua);
    • só liga com a sua confirmação na tela, mostrando ganho e custo estimados;
    • roda numa janela visível, com prioridade baixa e metade dos núcleos (o PC continua usável);
    • para sozinho se o notebook sair da tomada, se passar do limite de horas ou, quando o Windows informa,
      se a temperatura passar do limite;
    • nunca roda no celular (no app ou no Termux ele recusa: esquenta e estraga a bateria);
    • cada vez que liga e desliga fica registrado no livro-razão.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

from plugins import _comum, _web
from plugins._lote2 import P, carregar, guardar, norm, num1, reais, rodar

PLUGIN = P("mineracao", "Crypto mining: honest profit calculator (BTC, XMR) vs electricity, and safe on/off control of the user's own XMRig.",
           "calcular | moedas | configurar | ligar | desligar | status | relatorio",
           "calcular: profit per day for moeda (btc, xmr or todas) on this PC vs electricity (tarifa R$/kWh, watts optional). "
           "configurar: tarifa, watts, xmrig (path to xmrig.exe), carteira (Monero address), pool, threads, horas (max hours), "
           "temperatura (max °C). ligar: starts the user's XMRig after on-screen confirmation (PC only, plugged in). "
           "desligar: stops it. status: hashrate, shares, cost so far. relatorio: all sessions. moedas: which coins make sense on a CPU.",
           "moeda tarifa watts xmrig carteira pool threads horas temperatura")

PORTA_API = 18088
DIF_BTC_APROX = 1.3e14          # só se a internet falhar (ordem de grandeza de 2026)
DIF_XMR_APROX = 6.0e11          # ~5 GH/s × 120 s
PADRAO = {"tarifa": 0.95, "watts": 30.0, "xmrig": "", "carteira": "", "pool": "pool.supportxmr.com:443", "tls": True,
          "threads": 0, "horas": 8.0, "temperatura": 85.0, "hashrate_medido": 0.0, "sessoes": []}

MOEDAS = {
    "xmr": {"nome": "Monero (XMR)", "algo": "RandomX", "recompensa": 0.6, "fator": 1.0, "cg": "monero", "cpu": True,
            "hs_thread": 300.0, "nota": "feita para processador: é a única que faz sentido no seu PC."},
    "btc": {"nome": "Bitcoin (BTC)", "algo": "SHA-256", "recompensa": 3.125, "fator": 2.0 ** 32, "cg": "bitcoin", "cpu": False,
            "hs_thread": 2.5e6, "nota": "só máquinas ASIC ganham; no processador o resultado é praticamente zero."},
}
SO_ASIC = {"ltc": "Litecoin (LTC): algoritmo Scrypt, dominado por máquinas ASIC.",
           "doge": "Dogecoin (DOGE): Scrypt, minerada junto com a Litecoin em máquinas ASIC.",
           "bch": "Bitcoin Cash (BCH): SHA-256, igual ao Bitcoin: só ASIC.",
           "eth": "Ethereum (ETH): não se minera mais desde setembro de 2022 (virou prova de participação).",
           "etc": "Ethereum Classic (ETC): algoritmo Etchash, de placa de vídeo; o seu PC não tem placa dedicada."}
APELIDOS = {"bitcoin": "btc", "monero": "xmr", "litecoin": "ltc", "dogecoin": "doge", "doge": "doge", "ethereum": "eth",
            "ether": "eth", "eth": "eth", "btc": "btc", "xmr": "xmr", "ltc": "ltc", "bch": "bch", "etc": "etc"}

_proc: dict = {"p": None, "token": "", "inicio": 0.0, "hashes": 0.0, "ultima": 0.0, "hs": 0.0, "shares": 0, "temp": None,
               "temp_ts": 0.0, "motivo": ""}
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────── contas (puras) ───
def ganho_dia(hashrate: float, dificuldade: float, recompensa: float, fator: float = 1.0) -> float:
    """Moedas por dia esperadas: (hashes por dia) / (hashes por bloco) × recompensa. Pura."""
    if hashrate <= 0 or dificuldade <= 0:
        return 0.0
    return hashrate * 86400 / (dificuldade * fator) * recompensa


def custo_dia(watts: float, tarifa: float) -> float:
    """Reais de luz por dia ligado direto. Pura."""
    return max(0.0, watts) * 24 / 1000 * max(0.0, tarifa)


def anos_por_bloco(hashrate: float, dificuldade: float, fator: float = 1.0) -> float:
    """Quantos anos, em média, para ESTE PC achar um bloco sozinho. Pura."""
    return float("inf") if hashrate <= 0 else dificuldade * fator / hashrate / (86400 * 365)


def threads_padrao(nucleos: int | None) -> int:
    """Metade dos núcleos lógicos (mínimo 1): o PC continua usável. Pura."""
    return max(1, int(nucleos or 2) // 2)


def carteira_valida(c: str) -> bool:
    """Endereço Monero: 95 letras começando com 4 ou 8 (ou 106, integrado). Pura."""
    return bool(re.fullmatch(r"[48][1-9A-HJ-NP-Za-km-z]{94}([1-9A-HJ-NP-Za-km-z]{11})?", str(c or "").strip()))


def fmt_moeda(v: float) -> str:
    if v == 0:
        return "0"
    if v >= 0.01:
        return f"{v:.4f}".replace(".", ",")
    return f"{v:.2e}".replace(".", ",")


def fmt_anos(a: float) -> str:
    if a == float("inf"):
        return "nunca"
    if a >= 1e6:
        return f"{a / 1e6:,.0f} milhões de anos".replace(",", ".")
    if a >= 2:
        return f"{a:,.0f} anos".replace(",", ".")
    return f"{a * 365:.0f} dias"


def analise(chave: str, hashrate: float, dificuldade: float, preco: float, watts: float, tarifa: float, medido: bool) -> dict:
    """Tudo o que a calculadora diz sobre uma moeda. Pura."""
    m = MOEDAS[chave]
    moedas = ganho_dia(hashrate, dificuldade, m["recompensa"], m["fator"])
    bruto = moedas * preco
    luz = custo_dia(watts, tarifa)
    return {"moeda": chave, "nome": m["nome"], "hashrate": hashrate, "medido": medido, "moedas_dia": moedas, "reais_dia": bruto,
            "luz_dia": luz, "saldo_dia": bruto - luz, "saldo_mes": (bruto - luz) * 30, "anos_bloco": anos_por_bloco(hashrate, dificuldade, m["fator"]),
            "compensa": bruto > luz}


def frase(a: dict, dados_aprox: bool) -> str:
    hs = a["hashrate"]
    vel = f"{hs / 1e6:.1f} MH/s" if hs >= 1e6 else f"{hs:.0f} H/s"
    t = (f"{a['nome']}: o seu PC faz uns {vel} ({'medido' if a['medido'] else 'estimado'}). Daria {fmt_moeda(a['moedas_dia'])} por dia, "
         f"{reais(a['reais_dia'])}, e gastaria {reais(a['luz_dia'])} de luz. ")
    t += (f"Sobra {reais(a['saldo_dia'])} por dia ({reais(a['saldo_mes'])} no mês)." if a["compensa"]
          else f"Prejuízo de {reais(-a['saldo_dia'])} por dia ({reais(-a['saldo_mes'])} no mês): não compensa.")
    if a["moeda"] == "btc":
        t += f" Sozinho, o seu PC levaria {fmt_anos(a['anos_bloco'])} para achar um bloco."
    if dados_aprox:
        t += " (Sem internet agora: usei a dificuldade aproximada da rede.)"
    return t


# ─────────────────────────────────────────────────────────── dados da rede ───
def dificuldade(chave: str) -> tuple[float, bool]:
    """(dificuldade, aproximada?)."""
    try:
        if chave == "btc":
            return float(_web.get_json("https://blockchain.info/q/getdifficulty", timeout=10)), False
        try:
            return float(_web.get_json("https://xmrchain.net/api/networkinfo", timeout=10)["data"]["difficulty"]), False
        except Exception:
            return float(_web.get_json("https://moneroblocks.info/api/get_stats/", timeout=10)["difficulty"]), False
    except Exception:
        return (DIF_BTC_APROX if chave == "btc" else DIF_XMR_APROX), True


def precos(ids: list[str]) -> dict[str, float]:
    """Preço em reais pelo id do CoinGecko (bitcoin, monero…). O que falhar fica de fora."""
    try:
        d = _web.get_json("https://api.coingecko.com/api/v3/simple/price", {"ids": ",".join(ids), "vs_currencies": "brl"}, timeout=10)
        return {k: float(v["brl"]) for k, v in d.items() if isinstance(v, dict) and "brl" in v}
    except Exception:
        out = {}
        if "bitcoin" in ids:
            try:
                from plugins import alerta_cotacao
                out["bitcoin"] = alerta_cotacao.cotacao("moeda", "BTC")
            except Exception:
                pass
        return out


def _cfg() -> dict:
    return {**PADRAO, **(carregar("mineracao", {}) or {})}


def _salvar(c: dict) -> None:
    guardar("mineracao", c)


def hashrate_de(chave: str, c: dict) -> tuple[float, bool]:
    if chave == "xmr" and c.get("hashrate_medido"):
        return float(c["hashrate_medido"]), True
    th = int(c.get("threads") or 0) or threads_padrao(os.cpu_count())
    return MOEDAS[chave]["hs_thread"] * th, False


# ─────────────────────────────────────────────────────────── onde pode rodar ───
def no_celular() -> bool:
    return bool(os.environ.get("JARVIS_ANDROID") or os.environ.get("ANDROID_ROOT") or os.environ.get("TERMUX_VERSION")
                or "com.termux" in sys.prefix or sys.platform == "android")


def na_tomada() -> bool | None:
    """True/False quando dá para saber; None num PC sem bateria ou sem psutil."""
    try:
        import psutil
        b = psutil.sensors_battery()
        return None if b is None else bool(b.power_plugged)
    except Exception:
        return None


def temperatura() -> float | None:
    """Temperatura do processador pelo Windows (nem todo PC informa). None quando não dá para ler."""
    if os.name != "nt":
        try:
            import psutil
            t = [x.current for v in (psutil.sensors_temperatures() or {}).values() for x in v if x.current]
            return max(t) if t else None
        except Exception:
            return None
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop "
                            "| Measure-Object -Property CurrentTemperature -Maximum).Maximum"],
                           capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        v = float(r.stdout.strip().replace(",", "."))
        return round(v / 10 - 273.15, 1) if v > 0 else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────── XMRig ───
def comando_xmrig(c: dict, token: str) -> list[str]:
    """A linha de comando do XMRig. Pura."""
    th = int(c.get("threads") or 0) or threads_padrao(os.cpu_count())
    cmd = [str(c["xmrig"]), "-o", str(c["pool"]), "-u", str(c["carteira"]).strip(), "-p", "jarvis", "--coin", "monero",
           "-t", str(th), "--cpu-priority", "0", "--http-host", "127.0.0.1", "--http-port", str(PORTA_API),
           "--http-access-token", token, "--print-time", "60"]
    if c.get("tls", True) and str(c["pool"]).endswith(":443"):
        cmd.append("--tls")
    return cmd


def problemas_para_ligar(c: dict) -> list[str]:
    erros = []
    if no_celular():
        return ["no celular eu não minero: esquenta, gasta a bateria e pode estragar o aparelho"]
    exe = Path(str(c.get("xmrig") or ""))
    if not c.get("xmrig"):
        erros.append("falta o caminho do xmrig.exe (baixe em github.com/xmrig/xmrig e diga 'configura a mineração, xmrig em C:\\...')")
    elif not exe.is_file() or "xmrig" not in exe.name.lower():
        erros.append(f"não achei o XMRig em {exe}")
    if not carteira_valida(c.get("carteira", "")):
        erros.append("falta uma carteira Monero válida (começa com 4 ou 8 e tem 95 letras)")
    if na_tomada() is False:
        erros.append("o notebook está na bateria: ligue na tomada antes")
    return erros


def resumo_api() -> dict | None:
    try:
        return _web.get_json(f"http://127.0.0.1:{PORTA_API}/2/summary", headers={"Authorization": f"Bearer {_proc['token']}"}, timeout=5)
    except Exception:
        return None


def rodando() -> bool:
    p = _proc["p"]
    return p is not None and p.poll() is None


def _livro(acao: str, dados: dict) -> None:
    try:
        from core import livro_razao
        livro_razao.registrar("mineracao", {"acao": acao, **dados})
    except Exception:
        pass


def _iniciar() -> str:
    with _lock:
        if rodando():
            return "A mineração já está ligada."
        c = _cfg()
        erros = problemas_para_ligar(c)
        if erros:
            return "Não liguei: " + "; ".join(erros) + "."
        token = secrets.token_hex(16)
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)            # janela visível: nada escondido
        p = subprocess.Popen(comando_xmrig(c, token), cwd=str(Path(c["xmrig"]).parent), creationflags=flags)
        _proc.update(p=p, token=token, inicio=time.time(), hashes=0.0, ultima=time.time(), hs=0.0, shares=0, temp=None, temp_ts=0.0, motivo="")
    _livro("ligou", {"pool": c["pool"], "threads": int(c.get("threads") or 0) or threads_padrao(os.cpu_count())})
    try:
        from core import relogio
        relogio.agendar("mineracao_vigia", vigiar, 60, 60)
    except Exception:
        pass
    return (f"Mineração de Monero ligada numa janela do XMRig, com {int(c.get('threads') or 0) or threads_padrao(os.cpu_count())} núcleos e "
            f"prioridade baixa. Paro sozinho em {c['horas']:g} h, se sair da tomada ou se esquentar demais.")


def _parar(motivo: str) -> str:
    with _lock:
        p = _proc["p"]
        if p is None:
            return "A mineração não está ligada."
        vigiar(fechar=False)
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(10)
            except Exception:
                p.kill()
        c = _cfg()
        horas = (time.time() - _proc["inicio"]) / 3600
        dif, _ = dificuldade("xmr")
        xmr = _proc["hashes"] / dif * MOEDAS["xmr"]["recompensa"] if dif else 0.0
        sess = {"inicio": _proc["inicio"], "fim": time.time(), "horas": round(horas, 3), "hashes": _proc["hashes"], "xmr": xmr,
                "luz": custo_dia(c["watts"], c["tarifa"]) * horas / 24, "shares": _proc["shares"], "motivo": motivo}
        c["sessoes"] = (c.get("sessoes") or [])[-199:] + [sess]
        if horas > 0.1 and _proc["hashes"] > 0:
            c["hashrate_medido"] = round(_proc["hashes"] / (horas * 3600), 1)      # próximos cálculos usam o real
        _salvar(c)
        _proc["p"] = None
    try:
        from core import relogio
        relogio.cancelar("mineracao_vigia")
    except Exception:
        pass
    _livro("desligou", {"motivo": motivo, "horas": round(horas, 2), "xmr_estimado": xmr})
    return (f"Mineração desligada ({motivo}). Rodou {horas:.1f} h: uns {fmt_moeda(xmr)} XMR estimados "
            f"e {reais(sess['luz'])} de luz.")


def vigiar(fechar: bool = True) -> None:
    """A cada minuto: soma o trabalho feito e para se algo sair do combinado."""
    if _proc["p"] is None:
        return
    agora = time.time()
    s = resumo_api()
    if s:
        hs = [x for x in (s.get("hashrate", {}).get("total") or []) if x]
        _proc["hs"] = float(hs[0]) if hs else _proc["hs"]
        _proc["shares"] = int((s.get("results") or {}).get("shares_good") or _proc["shares"])
    _proc["hashes"] += _proc["hs"] * max(0.0, agora - _proc["ultima"])
    _proc["ultima"] = agora
    if not fechar:
        return
    if _proc["p"].poll() is not None:
        _parar("o XMRig fechou")
        return
    c = _cfg()
    motivo = ""
    if na_tomada() is False:
        motivo = "o notebook saiu da tomada"
    elif (agora - _proc["inicio"]) / 3600 >= float(c.get("horas") or 8):
        motivo = f"chegou no limite de {float(c.get('horas') or 8):g} h"
    elif agora - _proc["temp_ts"] >= 300:
        _proc["temp_ts"] = agora
        _proc["temp"] = temperatura()
        if _proc["temp"] is not None and _proc["temp"] >= float(c.get("temperatura") or 85):
            motivo = f"esquentou ({_proc['temp']:.0f} °C)"
    if motivo:
        texto = _parar(motivo)
        try:
            _comum.avisar(None, texto, "mineracao")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────── ações ───
def _moedas_pedidas(texto) -> list[str]:
    t = norm(texto)
    if not t or "toda" in t or "outra" in t:
        return ["xmr", "btc"]
    ks = [APELIDOS[w] for w in re.findall(r"[a-z]+", t) if w in APELIDOS]
    return ks or ["xmr", "btc"]


def _calcular(p, pl):
    c = _cfg()
    if p.get("tarifa") or p.get("watts"):
        _configurar({k: p[k] for k in ("tarifa", "watts") if p.get(k)}, pl)
        c = _cfg()
    pedidas = _moedas_pedidas(p.get("moeda"))
    partes = [SO_ASIC[k] for k in pedidas if k in SO_ASIC]
    ks = [k for k in pedidas if k in MOEDAS]
    pr = precos([MOEDAS[k]["cg"] for k in ks]) if ks else {}
    for k in ks:
        if MOEDAS[k]["cg"] not in pr:
            partes.append(f"{MOEDAS[k]['nome']}: não consegui o preço agora (sem internet?).")
            continue
        dif, aprox = dificuldade(k)
        hs, medido = hashrate_de(k, c)
        partes.append(frase(analise(k, hs, dif, pr[MOEDAS[k]["cg"]], c["watts"], c["tarifa"], medido), aprox))
    partes.append(f"Luz considerada: {c['watts']:g} W a {reais(c['tarifa'])} o kWh (ajuste com 'minha luz é … o kWh').")
    return " ".join(partes)


def _moedas(p, pl):
    linhas = [f"{m['nome']} ({m['algo']}): {m['nota']}" for m in MOEDAS.values()] + list(SO_ASIC.values())
    return "Moedas e o seu PC: " + " ".join(linhas)


def _configurar(p, pl):
    c = _cfg()
    mud = []
    for k in ("tarifa", "watts", "threads", "horas", "temperatura"):
        if p.get(k) not in (None, ""):
            v = num1(p, k)
            if v > 0:
                c[k] = v
                mud.append(k)
    if p.get("xmrig"):
        c["xmrig"] = str(p["xmrig"]).strip().strip('"')
        mud.append("xmrig")
    if p.get("carteira"):
        if not carteira_valida(p["carteira"]):
            return "Essa carteira não parece Monero: começa com 4 ou 8 e tem 95 letras. Copie do seu app de carteira."
        c["carteira"] = str(p["carteira"]).strip()
        mud.append("carteira")
    if p.get("pool"):
        c["pool"] = str(p["pool"]).strip()
        mud.append("pool")
    if not mud:
        return (f"Mineração: luz {reais(c['tarifa'])}/kWh, {c['watts']:g} W, XMRig {'ok' if c['xmrig'] else 'não configurado'}, "
                f"carteira {'ok' if c['carteira'] else 'não configurada'}, pool {c['pool']}, limite {c['horas']:g} h e {c['temperatura']:g} °C.")
    _salvar(c)
    return "Guardei: " + ", ".join(mud) + "."


def _ligar(p, pl):
    c = _cfg()
    erros = problemas_para_ligar(c)
    if erros:
        return "Ainda não dá para ligar: " + "; ".join(erros) + "."
    if rodando():
        return "A mineração já está ligada."
    pr = precos(["monero"]).get("monero", 0.0)
    dif, _ = dificuldade("xmr")
    hs, medido = hashrate_de("xmr", c)
    a = analise("xmr", hs, dif, pr, c["watts"], c["tarifa"], medido)
    detalhe = (f"Ganho estimado {reais(a['reais_dia'])}/dia, luz {reais(a['luz_dia'])}/dia "
               f"({'sobra' if a['compensa'] else 'prejuízo de'} {reais(abs(a['saldo_dia']))}/dia). "
               f"Janela visível, prioridade baixa, para em {c['horas']:g} h.")
    from core import confirm
    return confirm.request("mineracao-ligar", "Ligar a mineração de Monero?", detalhe, _iniciar)


def _desligar(p, pl):
    return _parar("você pediu")


def _status(p, pl):
    if not rodando():
        c = _cfg()
        ult = (c.get("sessoes") or [None])[-1]
        base = "A mineração está desligada."
        return base + (f" Última vez: {ult['horas']:.1f} h, {fmt_moeda(ult['xmr'])} XMR estimados ({ult['motivo']})." if ult else "")
    vigiar(fechar=False)
    c = _cfg()
    horas = (time.time() - _proc["inicio"]) / 3600
    dif, _ = dificuldade("xmr")
    xmr = _proc["hashes"] / dif * MOEDAS["xmr"]["recompensa"] if dif else 0.0
    t = (f"Minerando há {horas:.1f} h a {_proc['hs']:.0f} H/s, {_proc['shares']} share(s) aceitos. "
         f"Uns {fmt_moeda(xmr)} XMR estimados e {reais(custo_dia(c['watts'], c['tarifa']) * horas / 24)} de luz até agora.")
    if _proc["temp"] is not None:
        t += f" Temperatura {_proc['temp']:.0f} °C."
    return t


def _relatorio(p, pl):
    ss = _cfg().get("sessoes") or []
    if not ss:
        return "Ainda não minerei nenhuma vez."
    horas = sum(s["horas"] for s in ss)
    xmr = sum(s["xmr"] for s in ss)
    luz = sum(s["luz"] for s in ss)
    pr = precos(["monero"]).get("monero")
    valor = f" (≈ {reais(xmr * pr)} hoje)" if pr else ""
    return (f"{len(ss)} sessão(ões), {horas:.1f} h no total: {fmt_moeda(xmr)} XMR estimados{valor}, {reais(luz)} de luz. "
            "O valor exato está no site da sua pool (o pagamento só sai quando passa do mínimo dela).")


def on_session_start(player) -> None:
    pass                                    # nunca liga sozinho


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"calcular": _calcular, "moedas": _moedas, "configurar": _configurar, "ligar": _ligar,
                              "desligar": _desligar, "status": _status, "relatorio": _relatorio}, player)
