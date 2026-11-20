"""
Ajudantes de rede local (fork PT-BR 1.6). Começa com "_": não é ferramenta.

Acha os aparelhos da sua rede (ARP + portas conhecidas + SSDP), descobre o
tipo de cada um, manda o "pacote mágico" do Wake-on-LAN e assina os pedidos
para o agente dos outros PCs. As funções marcadas "(pura)" estão nos testes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import socket
import time
from concurrent.futures import ThreadPoolExecutor

PORTA_AGENTE = 47777

# porta → pista do que é o aparelho
PORTAS = {
    PORTA_AGENTE: "agente", 8060: "roku", 8001: "samsung", 8002: "samsung", 3000: "lg", 3001: "lg",
    5555: "adb", 8009: "chromecast", 6668: "tuya", 445: "windows", 3389: "windows", 22: "ssh",
    80: "http", 9100: "impressora", 631: "impressora", 554: "camera",
}


# ── classificação (pura) ───────────────────────────────────────────────────────
def classificar(portas: set[int] | list[int], ssdp: str = "", nome: str = "") -> str:
    """Tipo provável a partir das portas abertas, do cabeçalho SSDP e do nome na rede (pura)."""
    p, s, n = set(portas), (ssdp or "").lower(), (nome or "").lower()
    if PORTA_AGENTE in p:
        return "pc"                                        # PC com o agente do JARVIS
    if 8060 in p or "roku" in s:
        return "tv_roku"
    if {8001, 8002} & p or "samsung" in s or "tizen" in s:
        return "tv_samsung"
    if {3000, 3001} & p or "webos" in s or "lg" in s.split():
        return "tv_lg"
    if 5555 in p:
        return "tv_android" if re.search(r"tv|bravia|mibox|chromecast|google tv|tcl|philips", f"{s} {n}") else "android"
    if 8009 in p:
        return "chromecast"
    if 6668 in p:
        return "tuya"
    if {9100, 631} & p:
        return "impressora"
    if {445, 3389} & p:
        return "pc_windows"
    if 554 in p:
        return "camera"
    if re.search(r"android|galaxy|iphone|redmi|motorola|moto-|xiaomi", n):
        return "celular"
    return "desconhecido"


def ler_ssdp(resposta: str) -> dict:
    """Cabeçalhos de uma resposta SSDP ('SERVER: Roku/9.4 UPnP/1.0' → {'server': ...}) (pura)."""
    cab = {}
    for linha in (resposta or "").splitlines()[1:]:
        if ":" in linha:
            k, v = linha.split(":", 1)
            cab[k.strip().lower()] = v.strip()
    return cab


def pacote_magico(mac: str) -> bytes:
    """O pacote do Wake-on-LAN: 6 × FF e 16 × o MAC (pura)."""
    hexa = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(hexa) != 12:
        raise ValueError(f"MAC inválido: {mac}")
    return b"\xff" * 6 + bytes.fromhex(hexa) * 16


def assinar(chave: str, corpo: bytes) -> str:
    return hmac.new(chave.encode(), corpo, hashlib.sha256).hexdigest()


def pedido_assinado(chave: str, acao: str, args: dict | None = None) -> tuple[bytes, str]:
    """Corpo JSON (com hora e número único, contra repetição) e a assinatura (pura, exceto hora/nonce)."""
    corpo = json.dumps({"acao": acao, "args": args or {}, "ts": time.time(),
                        "nonce": secrets.token_hex(8)}, ensure_ascii=False).encode()
    return corpo, assinar(chave, corpo)


# ── rede ──────────────────────────────────────────────────────────────────────
def ip_local() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))                  # não manda nada; só escolhe a interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def acordar(mac: str, ip: str = "") -> None:
    """Wake-on-LAN para o broadcast geral e o da sub-rede."""
    pacote = pacote_magico(mac)
    destinos = {"255.255.255.255"}
    if ip:
        destinos.add(".".join(ip.split(".")[:3] + ["255"]))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for d in destinos:
            for porta in (9, 7):
                s.sendto(pacote, (d, porta))


def porta_aberta(ip: str, porta: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((ip, porta), timeout=timeout):
            return True
    except OSError:
        return False


def ssdp(segundos: float = 2.5) -> dict[str, str]:
    """IP → cabeçalho SERVER de quem respondeu ao M-SEARCH (TVs, Roku, Chromecast...)."""
    msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\n"
           "ST: ssdp:all\r\n\r\n").encode()
    achados: dict[str, str] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
        s.settimeout(0.5)
        try:
            s.sendto(msg, ("239.255.255.250", 1900))
        except OSError:
            return achados
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                dados, (ip, _p) = s.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            cab = ler_ssdp(dados.decode("utf-8", "replace"))
            achados[ip] = " ".join(filter(None, (achados.get(ip, ""), cab.get("server", ""), cab.get("st", ""))))[:300]
    return achados


def _nome_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""


def varrer(segundos_ssdp: float = 2.5) -> list[dict]:
    """Toda a rede /24: quem responde, portas conhecidas, SSDP, MAC (ARP) e nome."""
    meu = ip_local()
    base = ".".join(meu.split(".")[:3])
    ips = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != meu]
    with ThreadPoolExecutor(max_workers=96) as ex:
        fut_ssdp = ex.submit(ssdp, segundos_ssdp)
        resultados = list(ex.map(lambda ip: (ip, {p for p in PORTAS if porta_aberta(ip, p)}), ips))
        cab_ssdp = fut_ssdp.result()
    try:
        from plugins.chave_celular import vizinhos_wifi
        macs = {v["ip"]: v["mac"] for v in vizinhos_wifi()}
    except Exception:
        macs = {}
    vivos = {ip for ip, portas in resultados if portas} | set(cab_ssdp) | {ip for ip in macs if ip.startswith(base + ".")}
    saida = []
    portas_de = dict(resultados)
    with ThreadPoolExecutor(max_workers=32) as ex:
        nomes = dict(zip(sorted(vivos), ex.map(_nome_dns, sorted(vivos))))
    for ip in sorted(vivos, key=lambda x: int(x.split(".")[-1])):
        portas = portas_de.get(ip, set())
        saida.append({"ip": ip, "mac": macs.get(ip, ""), "portas": sorted(portas), "ssdp": cab_ssdp.get(ip, ""),
                      "nome_rede": nomes.get(ip, ""),
                      "tipo": classificar(portas, cab_ssdp.get(ip, ""), nomes.get(ip, ""))})
    return saida
