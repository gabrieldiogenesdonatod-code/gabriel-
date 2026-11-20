"""
Celular como chave (fork PT-BR 1.5).

Se a sua "chave" está perto, o JARVIS confia em você; se ela sai de perto,
a sessão confiável fecha (e, se quiser, a Sentinela liga sozinha).

TRÊS TIPOS DE CHAVE
  • pulseira/relógio Bluetooth (Mi Band, Galaxy Watch, Amazfit…): o melhor —
    anunciam o tempo todo com endereço fixo. Precisa do bleak (pip install bleak).
  • celular na mesma rede Wi-Fi: sem instalar nada. Confere pelo endereço
    físico (MAC) da rede de casa. Desligue "MAC aleatório" para a rede de casa
    no celular, ou use o MAC que o celular mostra para ESSA rede (ele é fixo
    por rede).
  • app de beacon no celular (ex.: "Beacon Simulator" no Android): anuncia um
    nome fixo por Bluetooth, mesmo com a tela apagada.
  Celulares comuns trocam o endereço Bluetooth sozinhos a cada ~15 min — por
  isso o celular "puro" funciona melhor pelo Wi-Fi.

    "Jarvis, procura minha pulseira"     (lista o que está por perto)
    "Jarvis, usa a Mi Band 8 como chave" / "usa o celular no Wi-Fi como chave"
    "Jarvis, minha chave está perto?"
"""

from __future__ import annotations

import re
import threading
import time

from plugins._comum import CONFIG, WIN, gravar_json, ler_json, mostrar, rodar

PLUGIN = {
    "name": "chave_celular",
    "brief": "Phone/band as a key: nearby = trusted session; away = session closes.",
    "description": (
        "Uses the user's phone or smart band as a presence key for verification. action='procurar' "
        "(scan nearby Bluetooth devices and Wi-Fi neighbours), 'definir' with tipo (bluetooth|wifi) and alvo "
        "(device name or address/MAC as listed), 'status' ('is my key near?'), 'remover'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "procurar | definir | status | remover"},
            "tipo": {"type": "STRING"}, "alvo": {"type": "STRING"},
        },
        "required": [],
    },
}

ARQ = CONFIG / "chave_celular.json"
_estado = {"perto": None, "visto": 0.0, "rssi": None, "ultimo": {}}
_iniciado = threading.Event()
_RE_MAC = re.compile(r"([0-9a-f]{2}[:-]){5}[0-9a-f]{2}", re.I)


def config() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("dispositivos", [])
    d.setdefault("fechar_ao_sair", True)
    d.setdefault("minutos_ausente", 3)
    return d


def normalizar_mac(m: str) -> str:
    return m.strip().upper().replace("-", ":")


# ── Bluetooth (bleak) ──────────────────────────────────────────────────────────
def varrer_bluetooth(segundos: float = 6.0) -> list[dict] | None:
    """[{nome, endereco, rssi}] ou None sem o bleak."""
    try:
        import asyncio
        from bleak import BleakScanner
    except ImportError:
        return None

    async def varrer():
        achados = await BleakScanner.discover(timeout=segundos, return_adv=True)
        return [{"nome": (adv.local_name or dev.name or "").strip(), "endereco": normalizar_mac(dev.address),
                 "rssi": getattr(adv, "rssi", None)} for dev, adv in achados.values()]

    try:
        return asyncio.run(varrer())
    except Exception as e:
        print(f"[Chave] bluetooth: {e}")
        return []


# ── Wi-Fi (ARP) ────────────────────────────────────────────────────────────────
def vizinhos_wifi() -> list[dict]:
    _c, saida = rodar(["arp", "-a"], timeout=8)
    vizinhos = []
    for linha in saida.splitlines():
        ip = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", linha)
        mac = _RE_MAC.search(linha)
        if ip and mac and not mac.group(0).lower().startswith(("ff-ff", "ff:ff", "01-00-5e", "01:00:5e")):
            vizinhos.append({"ip": ip.group(1), "mac": normalizar_mac(mac.group(0))})
    return vizinhos


def _ping(ip: str) -> bool:
    args = ["ping", "-n", "1", "-w", "800", ip] if WIN else ["ping", "-c", "1", "-W", "1", ip]
    c, _s = rodar(args, timeout=4)
    return c == 0


def presente(disp: dict, bt: list[dict] | None, wifi: list[dict] | None) -> tuple[bool, int | None]:
    """A chave está perto? (pura, recebe as varreduras)."""
    if disp.get("tipo") == "bluetooth":
        alvo = disp.get("alvo", "")
        for d in bt or []:
            casa = (normalizar_mac(alvo) == d["endereco"]) if _RE_MAC.fullmatch(alvo.strip()) else \
                (alvo.lower() in d["nome"].lower() if alvo else False)
            if casa and (d["rssi"] is None or d["rssi"] >= int(disp.get("rssi_min", -85))):
                return True, d["rssi"]
        return False, None
    alvo = normalizar_mac(disp.get("alvo", ""))
    return any(v["mac"] == alvo for v in wifi or []), None


def verificar(player=None) -> bool | None:
    c = config()
    if not c["dispositivos"]:
        return None
    precisa_bt = any(d.get("tipo") == "bluetooth" for d in c["dispositivos"])
    precisa_wifi = any(d.get("tipo") == "wifi" for d in c["dispositivos"])
    bt = varrer_bluetooth(5) if precisa_bt else None
    wifi = None
    if precisa_wifi:
        for d in c["dispositivos"]:
            if d.get("tipo") == "wifi" and d.get("ip"):
                _ping(d["ip"])                         # renova a tabela ARP
        wifi = vizinhos_wifi()
    perto, rssi = False, None
    for d in c["dispositivos"]:
        ok, r = presente(d, bt, wifi)
        if ok:
            perto, rssi = True, r
            if d.get("tipo") == "wifi" and wifi:
                ip = next((v["ip"] for v in wifi if v["mac"] == normalizar_mac(d["alvo"])), d.get("ip", ""))
                if ip != d.get("ip"):                          # só grava quando o IP do celular mudou
                    d["ip"] = ip
                    gravar_json(ARQ, c)
            break
    from core import verificacao
    antes = _estado["perto"]
    if perto:
        _estado.update(perto=True, visto=time.time(), rssi=rssi)
        verificacao.confiar("celular")
        if antes is False:
            verificacao.avisar_evento("chave_voltou", "")
    elif time.time() - _estado["visto"] >= float(c["minutos_ausente"]) * 60:
        if antes:
            if c["fechar_ao_sair"]:
                verificacao.encerrar("a sua chave (celular/pulseira) saiu de perto")
            verificacao.avisar_evento("chave_saiu", "")
        _estado["perto"] = False
    return perto


def _laco(player) -> None:
    time.sleep(30)
    while True:
        try:
            verificar(player)
        except Exception as e:
            print(f"[Chave] {e}")
        time.sleep(20)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="chave_celular").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        c = config()
        if acao == "procurar":
            bt = varrer_bluetooth(8)
            wifi = vizinhos_wifi()
            linhas = ["BLUETOOTH (mais perto primeiro)"]
            if bt is None:
                linhas.append("  instale o bleak para procurar: python -m pip install bleak")
            else:
                for d in sorted(bt, key=lambda x: -(x["rssi"] or -999))[:25]:
                    linhas.append(f"  {d['nome'] or '(sem nome)':<28} {d['endereco']}  sinal {d['rssi']}")
            linhas += ["", "WI-FI (aparelhos na sua rede)"] + [f"  {v['ip']:<16} {v['mac']}" for v in wifi[:30]]
            mostrar(player, "PROCURAR CHAVE", "\n".join(linhas))
            nomes = [d["nome"] for d in sorted(bt or [], key=lambda x: -(x["rssi"] or -999)) if d["nome"]][:4]
            return ("Achei por perto: " + ", ".join(nomes) + ". " if nomes else "") + \
                "A lista completa está no painel; diga qual usar como chave."
        if acao == "definir":
            tipo = "wifi" if "wi" in str(p.get("tipo") or "").lower() else "bluetooth"
            alvo = str(p.get("alvo") or "").strip()
            if not alvo:
                return "Diga o nome ou o endereço da chave (como aparece em 'procura minha pulseira')."
            if tipo == "wifi" and not _RE_MAC.fullmatch(alvo):
                viz = [v for v in vizinhos_wifi() if v["ip"] == alvo]
                if not viz:
                    return "Para o Wi-Fi preciso do MAC do celular (ou do IP dele, se ele estiver conectado agora)."
                c["dispositivos"].append({"tipo": "wifi", "alvo": viz[0]["mac"], "ip": alvo})
            else:
                c["dispositivos"].append({"tipo": tipo, "alvo": alvo, "rssi_min": -85})
            gravar_json(ARQ, c)
            return f"Pronto: {alvo} ({tipo}) é a sua chave. Com ela perto, eu confio em você."
        if acao == "remover":
            gravar_json(ARQ, {**c, "dispositivos": []})
            return "Removi a chave."
        if not c["dispositivos"]:
            return "Nenhuma chave definida. Diga 'procura minha pulseira' ou 'usa o celular no Wi-Fi como chave'."
        perto = verificar(player)
        return "Sua chave está perto." if perto else "Não encontro sua chave por perto agora."
    except Exception as e:
        return f"A chave falhou: {e}"
