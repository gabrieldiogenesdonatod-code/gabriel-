#!/data/data/com.termux/files/usr/bin/python
"""
J.A.R.V.I.S BR 1.5 — geofence pelo celular (Termux + Termux:API).

Avisa o JARVIS quando você CHEGA e quando SAI de casa, e liga o PC pela rede
(Wake-on-LAN) quando você chega. Detecta "em casa" pelo nome do Wi-Fi (gasta
quase nada de bateria) e, se quiser, também pelo GPS.

No PC: "Jarvis, configura o geofence" mostra o TOPICO e a CHAVE para colar abaixo.
Passo a passo: LEIA-ME.md (nesta mesma pasta).
"""

import json
import math
import socket
import subprocess
import time
import urllib.request

# ======================= CONFIGURE AQUI =======================
SERVIDOR = "https://ntfy.sh"
TOPICO = "COLE_O_TOPICO_AQUI"
CHAVE = "COLE_A_CHAVE_AQUI"
REDE_CASA = "NOME_DO_SEU_WIFI"          # exatamente como aparece no celular
PC_MAC = ""                              # ex.: "AA:BB:CC:DD:EE:FF" (vazio = não liga o PC)
USAR_GPS = False                         # True para também usar a localização
CASA_LAT, CASA_LON, RAIO_M = 0.0, 0.0, 150
INTERVALO_S = 60                         # de quanto em quanto tempo conferir
MINUTOS_PARA_SAIR = 10                   # fora de casa por esse tempo = "saiu"
# ==============================================================


def termux(cmd: list[str]) -> dict:
    try:
        saida = subprocess.run(cmd, capture_output=True, text=True, timeout=40).stdout
        return json.loads(saida) if saida.strip() else {}
    except Exception:
        return {}


def wifi_atual() -> str:
    return str(termux(["termux-wifi-connectioninfo"]).get("ssid", "")).strip('"')


def distancia_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def em_casa() -> bool:
    if REDE_CASA and wifi_atual() == REDE_CASA:
        return True
    if USAR_GPS and CASA_LAT:
        loc = termux(["termux-location", "-p", "network", "-r", "once"])
        if "latitude" in loc:
            return distancia_m(loc["latitude"], loc["longitude"], CASA_LAT, CASA_LON) <= RAIO_M
    return False


def avisar(evento: str) -> bool:
    try:
        req = urllib.request.Request(f"{SERVIDOR}/{TOPICO}", data=f"{evento} {CHAVE}".encode(), method="POST")
        with urllib.request.urlopen(req, timeout=20):
            return True
    except Exception as e:
        print("falhou ao avisar:", e)
        return False


def ligar_pc() -> None:
    """Wake-on-LAN: o pacote mágico vai para a rede de casa (o PC precisa ter WoL ligado na BIOS)."""
    mac = PC_MAC.replace(":", "").replace("-", "")
    if len(mac) != 12:
        return
    pacote = bytes.fromhex("FF" * 6 + mac * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for destino in ("255.255.255.255",):
            s.sendto(pacote, (destino, 9))


def main() -> None:
    estado = "casa" if em_casa() else "fora"
    fora_desde = None if estado == "casa" else time.time()
    print("geofence iniciado; agora:", estado)
    while True:
        time.sleep(INTERVALO_S)
        casa = em_casa()
        if casa:
            fora_desde = None
            if estado != "casa":
                estado = "casa"
                ligar_pc()
                for _ in range(10):                 # o PC pode demorar a ligar; o ntfy guarda a mensagem
                    if avisar("chegou"):
                        break
                    time.sleep(30)
                print(time.strftime("%H:%M"), "chegou")
        else:
            fora_desde = fora_desde or time.time()
            if estado == "casa" and time.time() - fora_desde >= MINUTOS_PARA_SAIR * 60:
                estado = "fora"
                avisar("saiu")
                print(time.strftime("%H:%M"), "saiu")


if __name__ == "__main__":
    main()
