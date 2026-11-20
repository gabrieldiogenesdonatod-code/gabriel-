"""Calculadora de IP (2.19): rede, máscara, broadcast e quantidade de hosts de um endereço; divide em sub-redes; seu IP local."""
from __future__ import annotations

import ipaddress
import socket

from plugins._lote2 import P, num1, rodar

PLUGIN = P("calculadora_ip", "IP/subnet calculator: network, mask, broadcast, host range and count for an address/prefix; is IP in network; split into subnets; local IP.",
           "rede | contem | dividir | meu_ip",
           "rede: ip ('192.168.1.10/24'). contem: ip (network), outro (address). dividir: ip (network), prefixo (new, e.g. 26).",
           "ip outro prefixo")


def info(cidr: str) -> dict:
    iface = ipaddress.ip_interface(cidr.strip())
    n = iface.network
    hosts = max(0, n.num_addresses - 2) if n.prefixlen < 31 else n.num_addresses
    return {"rede": str(n), "mascara": str(n.netmask), "broadcast": str(n.broadcast_address), "hosts": hosts,
            "primeiro": str(n.network_address + 1) if hosts else str(n.network_address),
            "ultimo": str(n.broadcast_address - 1) if hosts else str(n.broadcast_address), "privada": iface.ip.is_private}


def _go(p, pl):
    a, ip = p["action"], str(p.get("ip") or "").strip()
    if a == "meu_ip":
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            try:
                s.connect(("10.255.255.255", 1))
                return f"Seu IP na rede local é {s.getsockname()[0]}."
            except OSError:
                return "Sem rede no momento."
    if a == "contem":
        dentro = ipaddress.ip_address(str(p.get("outro")).strip()) in ipaddress.ip_network(ip, strict=False)
        return f"{p.get('outro')} {'está' if dentro else 'NÃO está'} dentro de {ip}."
    if a == "dividir":
        subs = list(ipaddress.ip_network(ip, strict=False).subnets(new_prefix=int(num1(p, "prefixo", 26))))
        return f"{len(subs)} sub-rede(s): " + ", ".join(str(s) for s in subs[:16]) + ("…" if len(subs) > 16 else "")
    i = info(ip if "/" in ip else ip + "/24")
    return (f"Rede {i['rede']}, máscara {i['mascara']}, broadcast {i['broadcast']}, {i['hosts']} hosts "
            f"({i['primeiro']} a {i['ultimo']}), {'privada' if i['privada'] else 'pública'}.")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("rede contem dividir meu_ip".split(), _go), player)
