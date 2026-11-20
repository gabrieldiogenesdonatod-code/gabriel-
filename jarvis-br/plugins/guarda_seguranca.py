"""
Guarda de segurança — plugin do J.A.R.V.I.S BR.

Fica de olho, em segundo plano e de forma leve (uma rodada por minuto), em:
    1. programa NOVO na inicialização do PC;
    2. conexão para fora em porta suspeita (4444, 1337, 31337, IRC, Telnet,
       Tor…) ou programa escutando numa delas;
    3. processo NOVO, sem assinatura digital válida (Windows), abrindo muitas
       conexões de rede;
    4. aparelho NOVO na sua rede local (pela tabela ARP, a cada 10 minutos);
    5. pessoa desconhecida na câmera (junto com o reconhecimento_facial):
       oferece bloquear o PC, ou bloqueia sozinho se você configurar.

Na primeira vez ele só APRENDE o que é normal no seu PC (memory/guarda_base.json)
e não avisa nada. Depois, cada novidade vira um aviso falado e um evento no
histórico do monitor. "Jarvis, isso é normal" aceita o estado atual.

Não é antivírus: não analisa arquivos nem bloqueia nada sozinho (exceto o
bloqueio de tela, se você ligar essa opção). É um par de olhos a mais.
"""

from __future__ import annotations

import ipaddress
import threading
import time

import psutil

from plugins._comum import (MEMORIA, WIN, avisar, cfg, falar, gravar_json, ler_json,
                            mostrar, num, plugin_ligado, powershell, sim)

PLUGIN = {
    "name": "guarda_seguranca",
    "brief": "Security watch: status, check now, accept as normal, name network devices.",
    "description": (
        "Security watch. action='status' for what is being watched and recent "
        "warnings; 'verificar' to run every check now (including a scan of the local "
        "network); 'aceitar' when the user says the current state is normal / trusted "
        "('isso é normal', 'pode confiar'); 'dispositivos' lists known devices on the "
        "network; 'nomear' gives a device a name (alvo = IP or MAC, nome)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | verificar | aceitar | dispositivos | nomear"},
            "alvo": {"type": "STRING"}, "nome": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "guarda_seguranca",
    "title": "Guarda de segurança",
    "fields": [
        {"key": "ligado", "label": "Vigiar em segundo plano", "type": "toggle", "default": True},
        {"key": "inicializacao", "label": "Avisar de programa novo na inicialização", "type": "toggle", "default": True},
        {"key": "portas", "label": "Avisar de conexão em porta suspeita", "type": "toggle", "default": True},
        {"key": "sem_assinatura", "label": "Avisar de processo novo sem assinatura com muita rede",
         "type": "toggle", "default": True},
        {"key": "conexoes_limite", "label": "…a partir de quantas conexões", "type": "text", "default": "20"},
        {"key": "rede_local", "label": "Avisar de aparelho novo na rede", "type": "toggle", "default": True},
        {"key": "camera", "label": "Desconhecido na câmera", "type": "choice",
         "options": ["oferecer bloqueio", "bloquear sozinho", "só avisar"], "default": "oferecer bloqueio"},
    ],
}

PORTAS_SUSPEITAS = {4444: "Metasploit", 1337: "porta 'leet'", 31337: "Back Orifice",
                    6666: "IRC", 6667: "IRC", 6697: "IRC", 12345: "NetBus", 27374: "SubSeven",
                    5555: "ADB remoto", 23: "Telnet", 2323: "Telnet", 9001: "Tor", 9050: "Tor",
                    9150: "Tor", 1080: "proxy SOCKS", 3127: "MyDoom", 20034: "NetBus 2"}

_BASE = MEMORIA / "guarda_base.json"
_thread: threading.Thread | None = None
_parar = threading.Event()
_ultimo_aviso: dict[str, float] = {}
_assinaturas: dict[str, str] = {}


def _cfg() -> dict:
    return cfg("guarda_seguranca", PLUGIN_SETTINGS)


def _base() -> dict:
    b = ler_json(_BASE, None)
    return b if isinstance(b, dict) else {}


def _salvar(b: dict) -> None:
    gravar_json(_BASE, b)


def ip_publico_suspeito(ip: str) -> bool:
    """True para IPs da internet (não privados, não loopback, não multicast)."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_multicast or a.is_link_local
                or a.is_reserved or a.is_unspecified)


# ── coleta ─────────────────────────────────────────────────────────────────────
def _inicializacao_atual() -> dict[str, str]:
    try:
        from plugins.controle_sistema import listar_inicializacao
        return {f"{i['origem']}|{i['nome']}": i["comando"] for i in listar_inicializacao()}
    except Exception:
        return {}


def _exes_atuais() -> dict[str, str]:
    exes = {}
    for p in psutil.process_iter(["exe", "name"]):
        e = p.info.get("exe")
        if e:
            exes[e.lower()] = p.info.get("name") or e
    return exes


def _arp() -> dict[str, str]:
    try:
        from core import telemetria
        rede = telemetria.rede_local()
        pares = telemetria.tabela_arp()
        return {mac: ip for ip, mac in pares.items()
                if rede is None or ipaddress.ip_address(ip) in rede}
    except Exception:
        return {}


def assinatura(exe: str) -> str:
    """'Valid', 'NotSigned', 'HashMismatch'… (Windows). Cache por executável."""
    if not WIN:
        return "n/d"
    if exe in _assinaturas:
        return _assinaturas[exe]
    _c, out = powershell(f"(Get-AuthenticodeSignature -LiteralPath '{exe.replace(chr(39), chr(39) * 2)}').Status",
                         timeout=15)
    _assinaturas[exe] = (out.strip().splitlines() or ["?"])[-1]
    return _assinaturas[exe]


# ── verificações (cada uma devolve uma lista de (chave, aviso)) ────────────────
def checar_inicializacao(base: dict) -> list[tuple[str, str]]:
    atual = _inicializacao_atual()
    conhecidos = base.setdefault("inicializacao", {})
    novos = [(k, v) for k, v in atual.items() if k not in conhecidos]
    base["inicializacao"] = {**conhecidos, **atual}
    return [(f"ini:{k}", f"Programa novo na inicialização do PC: {k.split('|', 1)[1]} "
                         f"({v[:80]}).") for k, v in novos]


def checar_conexoes(base: dict, c: dict) -> list[tuple[str, str]]:
    avisos = []
    nomes: dict[int, str] = {}
    por_pid: dict[int, int] = {}
    try:
        conexoes = psutil.net_connections(kind="inet")
    except Exception:
        return []
    for cx in conexoes:
        pid = cx.pid or 0
        if pid and pid not in nomes:
            try:
                nomes[pid] = psutil.Process(pid).name()
            except Exception:
                nomes[pid] = "?"
        if cx.raddr:
            por_pid[pid] = por_pid.get(pid, 0) + 1
        if not sim(c.get("portas", True)):
            continue
        if cx.raddr and cx.raddr.port in PORTAS_SUSPEITAS and ip_publico_suspeito(cx.raddr.ip):
            avisos.append((f"porta:{nomes.get(pid)}:{cx.raddr.port}",
                           f"{nomes.get(pid, '?')} está conectado a {cx.raddr.ip} na porta "
                           f"{cx.raddr.port} ({PORTAS_SUSPEITAS[cx.raddr.port]}), que é suspeita."))
        if cx.status == "LISTEN" and cx.laddr and cx.laddr.port in PORTAS_SUSPEITAS \
                and cx.laddr.port not in (23,):
            avisos.append((f"escuta:{nomes.get(pid)}:{cx.laddr.port}",
                           f"{nomes.get(pid, '?')} está aceitando conexões na porta "
                           f"{cx.laddr.port} ({PORTAS_SUSPEITAS[cx.laddr.port]})."))
    if sim(c.get("sem_assinatura", True)):
        limite = num(c.get("conexoes_limite"), 20)
        exes_conhecidos = base.setdefault("exes", {})
        for pid, n in por_pid.items():
            if n < limite or not pid:
                continue
            try:
                exe = (psutil.Process(pid).exe() or "").lower()
            except Exception:
                continue
            if not exe or exe in exes_conhecidos:
                continue
            status = assinatura(exe)
            if status not in ("Valid", "n/d"):
                avisos.append((f"assin:{exe}", f"Processo novo {nomes.get(pid)} sem assinatura válida "
                                               f"({status}) abriu {n} conexões de rede."))
            exes_conhecidos[exe] = nomes.get(pid, "")
    return avisos


def checar_rede(base: dict) -> list[tuple[str, str]]:
    atual = _arp()
    conhecidos = base.setdefault("dispositivos", {})
    avisos = []
    for mac, ip in atual.items():
        if mac not in conhecidos:
            conhecidos[mac] = {"ip": ip, "nome": "", "visto": time.time()}
            avisos.append((f"rede:{mac}", f"Aparelho novo na sua rede: {ip} (MAC {mac})."))
        else:
            conhecidos[mac]["ip"] = ip
            conhecidos[mac]["visto"] = time.time()
    return avisos


def rodada(c: dict, incluir_rede: bool) -> list[tuple[str, str]]:
    """Uma rodada completa. Na primeira vez só aprende (devolve [])."""
    base = _base()
    primeira = not base
    avisos = []
    if sim(c.get("inicializacao", True)):
        avisos += checar_inicializacao(base)
    avisos += checar_conexoes(base, c)
    if incluir_rede and sim(c.get("rede_local", True)):
        avisos += checar_rede(base)
    if primeira:
        base["exes"] = {**base.get("exes", {}), **_exes_atuais()}
        base["criado"] = time.time()
        _salvar(base)
        return []
    _salvar(base)
    return avisos


def _laco(player):
    ultima_rede = 0.0
    # Na primeira volta, o PC "normal" é aprendido inclusive a rede.
    if not _base():
        rodada(_cfg(), incluir_rede=True)
    while not _parar.wait(60):
        if not plugin_ligado("guarda_seguranca"):
            continue
        c = _cfg()
        if not sim(c.get("ligado", True)):
            continue
        rede = time.time() - ultima_rede > 600
        if rede:
            ultima_rede = time.time()
        try:
            avisos = rodada(c, rede)
        except Exception as e:
            print(f"[Guarda] rodada falhou: {e}")
            continue
        for chave, msg in avisos:
            if time.time() - _ultimo_aviso.get(chave, 0) < 3600:
                continue
            _ultimo_aviso[chave] = time.time()
            try:
                from plugins import _monitor_db
                _monitor_db.gravar_evento("seguranca", msg)
            except Exception:
                pass
            avisar(player, msg + " Se for normal, diga 'isso é normal'.", "GUARDA DE SEGURANÇA")


def on_session_start(player) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _parar.clear()
    _thread = threading.Thread(target=_laco, args=(player,), daemon=True, name="guarda")
    _thread.start()


# ── integração com o reconhecimento facial ─────────────────────────────────────
def desconhecido_na_camera(player, quem: str) -> bool:
    """Chamado pelo reconhecimento_facial. True se a guarda cuidou do aviso."""
    if not plugin_ligado("guarda_seguranca"):
        return False
    modo = str(_cfg().get("camera") or "oferecer bloqueio")
    try:
        from plugins import _monitor_db
        _monitor_db.gravar_evento("seguranca", f"Pessoa desconhecida na câmera ({quem}).")
    except Exception:
        pass
    if modo == "bloquear sozinho":
        from plugins.controle_pc import bloquear_tela
        bloquear_tela()
        falar(player, f"[GUARDA DE SEGURANÇA] A câmera viu {quem} que não é o dono e o PC "
                      "foi bloqueado. Diga isso em UMA frase curta. Não chame ferramentas.")
        return True
    if modo == "oferecer bloqueio":
        falar(player, f"[GUARDA DE SEGURANÇA] A câmera vê {quem} que NÃO é o dono, e o dono não "
                      "está junto. Avise em UMA frase e pergunte se quer bloquear o PC. Se a resposta "
                      "for sim, chame controle_pc com action='bloquear'.")
        return True
    return False


# ── entrada ────────────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "status").strip().lower()
    try:
        if a == "status":
            b = _base()
            if not b:
                return "A guarda ainda está aprendendo o que é normal no seu PC."
            try:
                from plugins import _monitor_db
                evs = [e for e in _monitor_db.eventos(time.time() - 7 * 86400, 50) if e["tipo"] == "seguranca"]
            except Exception:
                evs = []
            texto = (f"Vigiando: {len(b.get('inicializacao', {}))} itens de inicialização, "
                     f"{len(b.get('dispositivos', {}))} aparelhos conhecidos na rede, portas suspeitas "
                     f"e processos sem assinatura.")
            return texto + (f" {len(evs)} aviso(s) na última semana; o último: {evs[0]['mensagem']}"
                            if evs else " Nenhum aviso na última semana.")
        if a == "verificar":
            from core import telemetria
            telemetria.dispositivos_rede(varrer=True)       # enche a tabela ARP
            avisos = rodada(_cfg(), incluir_rede=True)
            if not avisos:
                return "Verifiquei inicialização, conexões e rede: nada de novo."
            mostrar(player, "GUARDA DE SEGURANÇA", "\n".join(m for _k, m in avisos))
            return f"{len(avisos)} novidade(s): " + " ".join(m for _k, m in avisos[:3])
        if a == "aceitar":
            b = _base()
            b["inicializacao"] = _inicializacao_atual()
            b["exes"] = {**b.get("exes", {}), **_exes_atuais()}
            for mac, ip in _arp().items():
                b.setdefault("dispositivos", {}).setdefault(mac, {"ip": ip, "nome": "", "visto": time.time()})
            _salvar(b)
            _ultimo_aviso.clear()
            return "Entendido: o estado atual passa a ser o normal."
        if a == "dispositivos":
            ds = _base().get("dispositivos", {})
            if not ds:
                return "Ainda não conheço aparelhos na sua rede."
            mostrar(player, "APARELHOS CONHECIDOS", "\n".join(
                f"{d['ip']:<16} {mac}  {d.get('nome') or '—'}" for mac, d in ds.items()))
            return f"Conheço {len(ds)} aparelho(s) na sua rede."
        if a == "nomear":
            alvo, nome = str(p.get("alvo") or "").lower().strip(), str(p.get("nome") or "").strip()
            b = _base()
            for mac, d in b.get("dispositivos", {}).items():
                if alvo in (mac, d.get("ip")):
                    d["nome"] = nome
                    _salvar(b)
                    return f"Aparelho {d['ip']} agora se chama {nome}."
            return f"Não conheço o aparelho {alvo}."
        return "Ação desconhecida para a guarda."
    except Exception as e:
        return f"A guarda de segurança falhou: {e}"
