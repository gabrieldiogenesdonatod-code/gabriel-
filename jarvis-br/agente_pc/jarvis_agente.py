"""
Agente do J.A.R.V.I.S BR para os OUTROS PCs da casa (fork PT-BR 1.6).

Copie esta pasta (agente_pc) para o outro PC, que só precisa ter o Python.
Não precisa instalar nada além dele. Primeira vez, no PowerShell da pasta:

    python jarvis_agente.py --instalar

Isso cria a chave secreta, abre a porta 47777 no firewall (pede administrador)
e faz o agente abrir junto com o Windows, escondido. A chave aparece na tela:
no PC do JARVIS, diga "Jarvis, pareia o PC da sala" e informe a chave
(ou use ⚙ CONFIG. DE PLUGINS → Aparelhos).

Com o agente, o JARVIS consegue NESTE PC: ver o status (CPU, RAM, ligado há
quanto tempo, quem está usando), desligar, reiniciar, suspender, bloquear,
abrir programas e sites, fechar programas, mudar o volume, mostrar uma
mensagem, tirar print e rodar comandos. Ligar o PC é pela rede (Wake-on-LAN),
que precisa estar ativado na BIOS e na placa de rede.

Segurança: cada pedido vem assinado com a chave (HMAC-SHA256), com a hora e
um número que não pode ser repetido. Sem a chave, nada acontece. Tudo fica
anotado em agente.log. Para não aceitar comandos de terminal, ponha
"permitir_comandos": false no agente.json.

    python jarvis_agente.py              roda (em primeiro plano, mostra o registro)
    python jarvis_agente.py --chave      mostra a chave
    python jarvis_agente.py --nova-chave troca a chave (pareie de novo)
    python jarvis_agente.py --remover    tira da inicialização do Windows
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQ = PASTA / "agente.json"
LOG = PASTA / "agente.log"
WIN = platform.system() == "Windows"
CNW = {"creationflags": 0x08000000} if WIN else {}          # CREATE_NO_WINDOW
PORTA = 47777
JANELA_S = 60                                                 # pedido vale por 60 s
_vistos: dict[str, float] = {}
_lock = threading.Lock()


def config() -> dict:
    try:
        c = json.loads(ARQ.read_text(encoding="utf-8"))
    except Exception:
        c = {}
    mudou = False
    if not c.get("chave"):
        c["chave"], mudou = secrets.token_urlsafe(24), True
    for k, v in (("porta", PORTA), ("permitir_comandos", True), ("nome", socket.gethostname())):
        if k not in c:
            c[k], mudou = v, True
    if mudou:
        ARQ.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    return c


def anotar(texto: str) -> None:
    linha = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {texto}"
    print(linha)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
        if LOG.stat().st_size > 2_000_000:
            LOG.write_text(linha + "\n", encoding="utf-8")
    except OSError:
        pass


def mac() -> str:
    m = uuid.getnode()
    return ":".join(f"{(m >> s) & 0xff:02X}" for s in range(40, -1, -8))


# ── conferência do pedido (pura, testada) ─────────────────────────────────────
def conferir(chave: str, corpo: bytes, assinatura: str, agora: float | None = None) -> tuple[bool, str, dict]:
    """(ok, motivo, pedido). Confere assinatura, hora e repetição."""
    esperado = hmac.new(chave.encode(), corpo, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperado, assinatura or ""):
        return False, "assinatura inválida", {}
    try:
        p = json.loads(corpo.decode("utf-8"))
    except Exception:
        return False, "pedido ilegível", {}
    agora = agora or time.time()
    if abs(agora - float(p.get("ts", 0))) > JANELA_S:
        return False, "pedido velho (confira o relógio dos dois PCs)", {}
    nonce = str(p.get("nonce", ""))
    with _lock:
        for n, t in list(_vistos.items()):
            if agora - t > JANELA_S * 2:
                del _vistos[n]
        if not nonce or nonce in _vistos:
            return False, "pedido repetido", {}
        _vistos[nonce] = agora
    return True, "", p


# ── ações ─────────────────────────────────────────────────────────────────────
def _rodar(args, timeout: float = 20, shell: bool = False) -> tuple[int, str]:
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, shell=shell, **CNW)
        saida = (r.stdout or b"") + (b"\n" + r.stderr if r.stderr else b"")
        return r.returncode, saida.decode("oem" if WIN else "utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        return -1, f"passou de {timeout:.0f} s"
    except Exception as e:
        return -1, str(e)


def _ps(script: str, timeout: float = 20) -> tuple[int, str]:
    return _rodar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


def status() -> dict:
    d = {"nome": socket.gethostname(), "sistema": f"{platform.system()} {platform.release()}", "mac": mac()}
    try:
        import psutil
        d.update(cpu=psutil.cpu_percent(interval=0.5), ram=psutil.virtual_memory().percent,
                 ligado_ha_min=int((time.time() - psutil.boot_time()) / 60),
                 usuarios=sorted({u.name for u in psutil.users()}))
        procs = sorted(psutil.process_iter(["name", "memory_info"]),
                       key=lambda p: -(p.info["memory_info"].rss if p.info.get("memory_info") else 0))
        d["pesados"] = [p.info["name"] for p in procs[:6]]
        bat = psutil.sensors_battery()
        if bat:
            d["bateria"] = int(bat.percent)
    except ImportError:
        d["obs"] = "instale o psutil neste PC para ver CPU e RAM"
    return d


def _volume(qual: str) -> str:
    if not WIN:
        return "volume: só no Windows"
    tecla = {"mais": 175, "menos": 174, "mudo": 173}.get(qual)
    if not tecla:
        return "use mais, menos ou mudo"
    vezes = 1 if qual == "mudo" else 5
    _ps(f"$w = New-Object -ComObject WScript.Shell; 1..{vezes} | % {{ $w.SendKeys([char]{tecla}) }}")
    return f"volume {qual}"


def _print() -> dict:
    if not WIN:
        return {"erro": "print: só no Windows"}
    tmp = Path(os.environ.get("TEMP", str(PASTA))) / "jarvis_print.png"
    _ps("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$i = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
        "$g = [System.Drawing.Graphics]::FromImage($i); $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $i.Size); "
        f"$i.Save('{tmp}', [System.Drawing.Imaging.ImageFormat]::Png)", 30)
    if not tmp.exists():
        return {"erro": "não consegui tirar o print (o PC está bloqueado?)"}
    dados = base64.b64encode(tmp.read_bytes()).decode()
    tmp.unlink(missing_ok=True)
    return {"png": dados}


def executar(acao: str, args: dict, c: dict) -> dict:
    a = args or {}
    if acao == "status":
        return status()
    if acao in ("desligar", "reiniciar", "sair", "cancelar"):
        seg = str(int(a.get("segundos", 10)))
        cmd = {"desligar": ["shutdown", "/s", "/t", seg], "reiniciar": ["shutdown", "/r", "/t", seg],
               "sair": ["shutdown", "/l"], "cancelar": ["shutdown", "/a"]}[acao] if WIN else \
            {"desligar": ["shutdown", "-h", "+1"], "reiniciar": ["shutdown", "-r", "+1"],
             "sair": ["loginctl", "terminate-user", os.environ.get("USER", "")], "cancelar": ["shutdown", "-c"]}[acao]
        cod, out = _rodar(cmd)
        return {"ok": cod == 0, "saida": out or f"{acao} em {seg} s"}
    if acao == "suspender":
        if WIN:
            threading.Timer(2, lambda: _rodar(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])).start()
        else:
            threading.Timer(2, lambda: _rodar(["systemctl", "suspend"])).start()
        return {"ok": True, "saida": "suspendendo"}
    if acao == "bloquear":
        if WIN:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        else:
            _rodar(["loginctl", "lock-sessions"])
        return {"ok": True, "saida": "bloqueado"}
    if acao == "abrir":
        alvo = str(a.get("alvo") or "").strip()
        if not alvo:
            return {"erro": "diga o programa ou o site"}
        if WIN:
            cod, out = _rodar(f'start "" "{alvo}"', shell=True)
        else:
            cod, out = _rodar(["xdg-open", alvo])
        return {"ok": cod == 0, "saida": out or f"abri {alvo}"}
    if acao == "fechar":
        nome = str(a.get("alvo") or "").strip()
        if not nome:
            return {"erro": "diga o programa"}
        nome = nome if nome.lower().endswith(".exe") or not WIN else nome + ".exe"
        cod, out = _rodar(["taskkill", "/im", nome, "/f"] if WIN else ["pkill", "-f", nome])
        return {"ok": cod == 0, "saida": out}
    if acao == "volume":
        return {"ok": True, "saida": _volume(str(a.get("qual") or ""))}
    if acao == "mensagem":
        texto = str(a.get("texto") or "")[:400]
        if WIN:
            texto_ps = texto.replace("'", "''")
            threading.Thread(target=_ps, args=(
                "Add-Type -AssemblyName PresentationFramework; "
                f"[System.Windows.MessageBox]::Show('{texto_ps}', 'J.A.R.V.I.S') | Out-Null", 600), daemon=True).start()
        else:
            _rodar(["notify-send", "J.A.R.V.I.S", texto])
        return {"ok": True, "saida": "mensagem mostrada"}
    if acao == "print":
        return _print()
    if acao == "rodar":
        if not c.get("permitir_comandos", True):
            return {"erro": "este PC não aceita comandos de terminal (permitir_comandos = false)"}
        comando = str(a.get("comando") or "").strip()
        if not comando:
            return {"erro": "qual comando?"}
        cod, out = _rodar(["powershell", "-NoProfile", "-Command", comando] if WIN else ["bash", "-lc", comando],
                          timeout=float(a.get("timeout", 60)))
        return {"ok": cod == 0, "codigo": cod, "saida": out[-4000:]}
    return {"erro": f"ação desconhecida: {acao}"}


class Atendente(BaseHTTPRequestHandler):
    server_version = "JarvisAgente/1.6"

    def log_message(self, *a):                               # o registro é o nosso
        pass

    def _responder(self, codigo: int, dados: dict) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path.startswith("/ola"):                     # sem chave: só o básico para achar e acordar
            self._responder(200, {"jarvis_agente": 1, "nome": config()["nome"], "mac": mac(),
                                  "sistema": platform.system()})
        else:
            self._responder(404, {"erro": "?"})

    def do_POST(self):
        c = config()
        tamanho = min(int(self.headers.get("Content-Length") or 0), 64_000)
        corpo = self.rfile.read(tamanho)
        ok, motivo, p = conferir(c["chave"], corpo, self.headers.get("X-Assinatura", ""))
        if not ok:
            anotar(f"RECUSADO de {self.client_address[0]}: {motivo}")
            self._responder(403, {"erro": motivo})
            return
        acao = str(p.get("acao") or "")
        anotar(f"{self.client_address[0]} pediu {acao} {json.dumps(p.get('args') or {}, ensure_ascii=False)[:200]}")
        try:
            self._responder(200, executar(acao, p.get("args") or {}, c))
        except Exception as e:
            anotar(f"erro em {acao}: {e}")
            self._responder(500, {"erro": str(e)})


def _pasta_inicializar() -> Path:
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def instalar() -> None:
    c = config()
    if WIN:
        pyw = Path(sys.executable).with_name("pythonw.exe")
        exe = pyw if pyw.exists() else Path(sys.executable)
        vbs = _pasta_inicializar() / "jarvis_agente.vbs"
        vbs.write_text(f'CreateObject("WScript.Shell").Run """{exe}"" ""{Path(__file__).resolve()}""", 0\n',
                       encoding="utf-8")
        print(f"Abre com o Windows: {vbs}")
        regra = (f'netsh advfirewall firewall add rule name="JARVIS agente" dir=in action=allow protocol=TCP '
                 f'localport={c["porta"]} profile=private')
        cod, out = _rodar(regra, shell=True)
        if cod != 0:
            print("Para liberar o firewall, abra o PowerShell COMO ADMINISTRADOR e rode:\n  " + regra)
        else:
            print("Firewall liberado (só em rede privada).")
        subprocess.Popen([str(exe), str(Path(__file__).resolve())], **CNW)
    else:
        print("No Linux, rode 'python3 jarvis_agente.py' na inicialização (ex.: crontab @reboot).")
    print(f"\nCHAVE DESTE PC ({c['nome']}): {c['chave']}\nMAC: {mac()}  IP: {_ip()}\n"
          "No JARVIS: \"Jarvis, pareia o PC <nome>\" e informe a chave.")


def _ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "?"
    finally:
        s.close()


def main() -> None:
    args = set(sys.argv[1:])
    if "--nova-chave" in args:
        c = config()
        c["chave"] = secrets.token_urlsafe(24)
        ARQ.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Chave nova: {c['chave']}")
        return
    if "--chave" in args:
        print(config()["chave"])
        return
    if "--remover" in args:
        (_pasta_inicializar() / "jarvis_agente.vbs").unlink(missing_ok=True)
        print("Removido da inicialização.")
        return
    if "--instalar" in args:
        instalar()
        return
    c = config()
    anotar(f"Agente ouvindo na porta {c['porta']} ({c['nome']}, {_ip()}, MAC {mac()})")
    ThreadingHTTPServer(("0.0.0.0", int(c["porta"])), Atendente).serve_forever()


if __name__ == "__main__":
    main()
