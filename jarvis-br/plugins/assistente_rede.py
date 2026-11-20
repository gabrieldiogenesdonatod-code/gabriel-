"""
Assistente de rede — plugin do J.A.R.V.I.S BR.

"Jarvis, minha internet está lenta, por quê?" → roda um diagnóstico e explica
em português simples, do mais provável para o menos provável:

    1. o PC fala com o roteador? (ping no gateway: Wi-Fi/cabo)
    2. o roteador fala com a internet? (ping no Google e na Cloudflare, perda)
    3. o DNS está lento? (compara o seu DNS com o 1.1.1.1, com uma consulta DNS
       montada aqui mesmo, sem biblioteca nova)
    4. o sinal do Wi-Fi está fraco?
    5. este PC está ocupando a banda? (download/upload agora e programas
       conhecidos por puxar internet: OneDrive, Steam, torrent, Windows Update…)
    6. teste de velocidade (opcional, ~15 s), comparado ao seu plano, se você
       informar quantos Mbps contratou.

A interpretação fica em `diagnosticar(dados)`, uma função pura (está nos testes).
"""

from __future__ import annotations

import os
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor

from plugins._comum import br, cfg, mostrar, num, registrar, sim, velocidade

PLUGIN = {
    "name": "assistente_rede",
    "brief": "Diagnose slow internet and explain the cause with fixes.",
    "description": (
        "Network troubleshooter. Use for 'minha internet está lenta / caindo, por quê?', "
        "'o que está errado com a internet?'. action='diagnosticar' (velocidade=sim to "
        "include a ~15 s speed test). Explains the cause in plain Portuguese with fixes."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "diagnosticar"},
            "velocidade": {"type": "STRING", "description": "sim | nao"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "assistente_rede",
    "title": "Assistente de rede",
    "fields": [
        {"key": "plano_mbps", "label": "Velocidade do seu plano (Mbps, opcional)", "type": "text", "default": ""},
        {"key": "teste_padrao", "label": "Incluir teste de velocidade no diagnóstico", "type": "toggle",
         "default": True},
    ],
}

PESADOS = {"onedrive": "OneDrive", "dropbox": "Dropbox", "googledrivefs": "Google Drive",
           "steam": "Steam", "steamwebhelper": "Steam", "epicgameslauncher": "Epic Games",
           "qbittorrent": "qBittorrent", "utorrent": "uTorrent", "bittorrent": "BitTorrent",
           "transmission-gtk": "Transmission", "deluge": "Deluge", "battle.net": "Battle.net",
           "eadesktop": "EA App", "upc": "Ubisoft Connect", "riotclientservices": "Riot Client",
           "backgroundtransferhost": "Windows Update", "mousocoreworker": "Windows Update",
           "megasync": "MEGA", "icloud": "iCloud", "obs64": "OBS (transmissão)"}


# ── DNS montado à mão ──────────────────────────────────────────────────────────
def consulta_dns(servidor: str, nome: str = "google.com", timeout: float = 2.0) -> float | None:
    """ms para o servidor responder uma consulta A. None se não respondeu."""
    ident = int.from_bytes(os.urandom(2), "big")
    cab = struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode() for p in nome.split(".")) + b"\x00"
    pacote = cab + qname + struct.pack(">HH", 1, 1)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            t0 = time.perf_counter()
            s.sendto(pacote, (servidor, 53))
            resp, _ = s.recvfrom(512)
            if len(resp) >= 2 and struct.unpack(">H", resp[:2])[0] == ident:
                return round((time.perf_counter() - t0) * 1000, 1)
    except Exception:
        return None
    return None


def tempo_dns(servidor: str) -> float | None:
    tempos = [t for t in (consulta_dns(servidor, d) for d in ("google.com", "youtube.com", "whatsapp.net"))
              if t is not None]
    return round(sum(tempos) / len(tempos), 1) if tempos else None


# ── coleta ─────────────────────────────────────────────────────────────────────
def coletar(testar_velocidade: bool) -> dict:
    import psutil

    from core import telemetria
    tel = telemetria.get()
    s = tel.snapshot()
    gw = s.get("gateway") or telemetria.gateway_e_dns()[0]
    dns_sis = (s.get("dns") or telemetria.gateway_e_dns()[1] or [""])[0]
    with ThreadPoolExecutor(max_workers=6) as ex:
        f_gw = ex.submit(telemetria.medir_latencia, gw, 5) if gw else None
        f_g = ex.submit(telemetria.medir_latencia, "8.8.8.8", 5)
        f_c = ex.submit(telemetria.medir_latencia, "1.1.1.1", 5)
        f_dns = ex.submit(tempo_dns, dns_sis) if dns_sis else None
        f_cf = ex.submit(tempo_dns, "1.1.1.1")
        f_vel = ex.submit(telemetria.teste_velocidade) if testar_velocidade else None
        gwr = f_gw.result() if f_gw else {"ms": None, "perda": 100.0}
        g, cf = f_g.result(), f_c.result()
        d = {
            "gateway": gw, "gateway_ms": gwr["ms"], "gateway_perda": gwr["perda"],
            "internet_ms": min([x["ms"] for x in (g, cf) if x["ms"] is not None], default=None),
            "internet_perda": min(g["perda"], cf["perda"]),
            "dns_servidor": dns_sis, "dns_sistema_ms": f_dns.result() if f_dns else None,
            "dns_cloudflare_ms": f_cf.result(),
            "wifi_ssid": (s.get("wifi") or {}).get("ssid"), "wifi_sinal": (s.get("wifi") or {}).get("sinal"),
            "uso_down": (s.get("rede") or {}).get("down", 0.0), "uso_up": (s.get("rede") or {}).get("up", 0.0),
        }
        if f_vel:
            v = f_vel.result()
            d["down_mbps"], d["up_mbps"] = v.get("down_mbps"), v.get("up_mbps")
    conexoes = s.get("conexoes_por_pid") or {}
    pesados = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info.get("name") or "").lower().removesuffix(".exe")
        if n in PESADOS and (conexoes.get(p.pid, 0) > 0 or n in ("backgroundtransferhost", "mousocoreworker")):
            pesados.add(PESADOS[n])
    d["pesados"] = sorted(pesados)
    return d


# ── interpretação (pura) ───────────────────────────────────────────────────────
def diagnosticar(d: dict, plano_mbps: float | None = None) -> tuple[str, list[str], list[str]]:
    """(resumo, causas, sugestões) — das mais prováveis para as menos."""
    causas, dicas = [], []
    gw_ms, gw_perda = d.get("gateway_ms"), d.get("gateway_perda") or 0
    net_ms, net_perda = d.get("internet_ms"), d.get("internet_perda") or 0
    sinal = d.get("wifi_sinal")

    if net_ms is None and gw_ms is None:
        resumo = "Este PC não está conseguindo falar nem com o roteador."
        causas.append("O Wi-Fi ou o cabo está desconectado, ou o roteador está desligado/travado.")
        dicas += ["Confira se o Wi-Fi está conectado (ou se o cabo está bem encaixado).",
                  "Desligue o roteador da tomada por 30 segundos e ligue de novo."]
        return resumo, causas, dicas
    if net_ms is None:
        resumo = "O roteador responde, mas a internet não chega até ele."
        causas.append("O problema está depois do roteador: modem, cabo da operadora ou a própria operadora.")
        dicas += ["Reinicie o modem/roteador (30 segundos fora da tomada).",
                  "Se continuar, veja se a operadora está com falha na sua região."]
        return resumo, causas, dicas

    if gw_ms is not None and (gw_perda > 5 or gw_ms > 30):
        causas.append(f"A ligação entre o PC e o roteador está ruim (resposta de {br(gw_ms, 0)} ms"
                      + (f", {br(gw_perda, 0)}% de perda" if gw_perda else "") + "); deveria ser menos de 10 ms.")
        dicas.append("Chegue mais perto do roteador, use a rede 5 GHz ou, se puder, um cabo.")
    if sinal is not None and sinal < 50:
        causas.append(f"O sinal do Wi-Fi está fraco ({sinal}%).")
        if "Chegue mais perto do roteador, use a rede 5 GHz ou, se puder, um cabo." not in dicas:
            dicas.append("Chegue mais perto do roteador ou tire obstáculos (paredes, micro-ondas) do caminho.")
    if net_perda > 2:
        causas.append(f"Há perda de pacotes de {br(net_perda, 0)}% até a internet: isso causa travadas em "
                      "jogos, chamadas e vídeos.")
        dicas.append("Reinicie o roteador; se continuar, reclame com a operadora (perda acima de 1% não é normal).")
    if net_ms > 100:
        causas.append(f"A latência até a internet está alta ({br(net_ms, 0)} ms; o normal é abaixo de 50).")
        if gw_ms is not None and gw_ms < 15:
            dicas.append("Como o roteador está bem, a demora está na operadora ou em alguém usando muito a "
                         "internet da casa (download, streaming, atualização de videogame).")

    dns_sis, dns_cf = d.get("dns_sistema_ms"), d.get("dns_cloudflare_ms")
    if dns_sis is None and dns_cf is not None:
        causas.append(f"O seu servidor de DNS ({d.get('dns_servidor') or '?'}) não respondeu: os sites demoram "
                      "para começar a abrir.")
        dicas.append("Troque o DNS para 1.1.1.1 e 8.8.8.8 (nas configurações de rede ou no roteador).")
    elif dns_sis is not None and dns_cf is not None and dns_sis > 80 and dns_sis > 2 * dns_cf:
        causas.append(f"O seu DNS está lento ({br(dns_sis, 0)} ms); o 1.1.1.1 respondeu em {br(dns_cf, 0)} ms. "
                      "Isso atrasa o começo de cada site.")
        dicas.append("Troque o DNS para 1.1.1.1 e 8.8.8.8 (nas configurações de rede ou no roteador).")

    uso_down, uso_up = d.get("uso_down") or 0, d.get("uso_up") or 0
    pesados = d.get("pesados") or []
    if uso_down > 2 * 1024 * 1024 or uso_up > 1024 * 1024:
        texto = f"Este PC está usando a internet agora: ↓ {velocidade(uso_down)} e ↑ {velocidade(uso_up)}"
        texto += (" (provavelmente " + ", ".join(pesados) + ")." if pesados else ".")
        causas.append(texto)
        if uso_up > 1024 * 1024:
            dicas.append("Upload alto (backup/sincronização) congestiona tudo: pause a sincronização na nuvem.")
        else:
            dicas.append("Pause downloads e atualizações enquanto precisa da internet.")
    elif pesados:
        causas.append("Programas que costumam puxar internet estão abertos: " + ", ".join(pesados) + ".")
        dicas.append("Se estiverem baixando ou sincronizando, pause enquanto precisa da internet.")

    down = d.get("down_mbps")
    if down is not None:
        if plano_mbps and plano_mbps > 0 and down < 0.5 * plano_mbps:
            causas.append(f"O download medido foi {br(down)} Mbps, só {br(100 * down / plano_mbps, 0)}% do seu "
                          f"plano de {br(plano_mbps, 0)} Mbps.")
            dicas.append("Teste com cabo; se continuar baixo, reclame com a operadora (o mínimo garantido é 40%).")
        elif down < 5:
            causas.append(f"A velocidade de download está baixa: {br(down)} Mbps.")

    if not causas:
        resumo = (f"Daqui está tudo normal: roteador a {br(gw_ms or 0, 0)} ms, internet a {br(net_ms, 0)} ms"
                  + (f", download de {br(down)} Mbps" if down is not None else "") + ".")
        dicas += ["A lentidão pode ser de outro aparelho da casa usando a internet ou do próprio site/serviço.",
                  "Se for no Wi-Fi, teste perto do roteador para comparar."]
        return resumo, causas, dicas
    resumo = causas[0]
    return resumo, causas, list(dict.fromkeys(dicas))


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    c = cfg("assistente_rede", PLUGIN_SETTINGS)
    testar = sim(p["velocidade"]) if p.get("velocidade") not in (None, "") else sim(c.get("teste_padrao", True))
    registrar(player, "Diagnosticando a rede" + (" (com teste de velocidade, ~15 s)…" if testar else "…"))
    try:
        d = coletar(testar)
    except Exception as e:
        return f"O diagnóstico falhou: {e}"
    plano = num(c.get("plano_mbps"), 0) or None
    resumo, causas, dicas = diagnosticar(d, plano)
    linhas = [f"Roteador ({d.get('gateway') or '?'}): {br(d['gateway_ms'], 0) + ' ms' if d.get('gateway_ms') is not None else 'sem resposta'}"
              f"   perda {br(d.get('gateway_perda') or 0, 0)}%",
              f"Internet: {br(d['internet_ms'], 0) + ' ms' if d.get('internet_ms') is not None else 'sem resposta'}"
              f"   perda {br(d.get('internet_perda') or 0, 0)}%",
              f"DNS ({d.get('dns_servidor') or '?'}): {d.get('dns_sistema_ms') or '—'} ms   1.1.1.1: {d.get('dns_cloudflare_ms') or '—'} ms",
              f"Wi-Fi: {d.get('wifi_ssid') or '—'}   sinal {d.get('wifi_sinal') if d.get('wifi_sinal') is not None else '—'}%",
              f"Uso agora: ↓ {velocidade(d.get('uso_down') or 0)}   ↑ {velocidade(d.get('uso_up') or 0)}"]
    if d.get("down_mbps") is not None:
        linhas.append(f"Velocidade: ↓ {br(d['down_mbps'])} Mbps   ↑ {br(d.get('up_mbps') or 0)} Mbps")
    linhas += ["", "O QUE ENCONTREI"] + [f"• {x}" for x in (causas or ["Nada de errado daqui."])]
    linhas += ["", "O QUE FAZER"] + [f"→ {x}" for x in dicas]
    mostrar(player, "DIAGNÓSTICO DA REDE", "\n".join(linhas))
    fala = resumo
    if len(causas) > 1:
        fala += " Também: " + " ".join(causas[1:3])
    if dicas:
        fala += " Sugestão: " + dicas[0]
    return fala
