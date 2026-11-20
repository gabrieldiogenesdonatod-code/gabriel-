"""
Acesso pela internet ao painel do JARVIS (fork PT-BR 1.8). Começa com "_": não é ferramenta.

Dois caminhos, que podem ficar ligados juntos:

  TAILSCALE (recomendado)  VPN grátis: só os SEUS aparelhos, logados na sua
      conta Tailscale, enxergam o PC. O endereço (100.x.y.z ou nome-do-pc.ts.net)
      não muda, então o celular fica pareado de vez.
  CLOUDFLARE TUNNEL        um link https://…trycloudflare.com que abre de
      qualquer navegador, sem instalar nada no celular. O link muda cada vez que
      o túnel liga, e quem não tem a chave de pareamento só vê a tela de login.

Nos dois casos o painel continua exigindo o pareamento (chave de uso único e
token), com limite de tentativas.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from plugins._comum import BASE, CNW, LINUX, MAC, WIN, rodar

FERRAMENTAS = BASE / "ferramentas"
_RE_CF = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")
_cf: dict = {"proc": None, "url": "", "erro": "", "linhas": []}
_lock = threading.Lock()


# ── Tailscale ─────────────────────────────────────────────────────────────────
def tailscale_exe() -> str | None:
    achado = shutil.which("tailscale")
    if achado:
        return achado
    for c in (r"C:\Program Files\Tailscale\tailscale.exe", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        if Path(c).exists():
            return c
    return None


def ler_status_tailscale(texto: str) -> dict:
    """Saída de `tailscale status --json` → {estado, ip, nome, conta} (pura)."""
    try:
        d = json.loads(texto)
    except (ValueError, TypeError):
        return {"estado": "erro", "ip": "", "nome": "", "conta": ""}
    eu = d.get("Self") or {}
    ips = [ip for ip in (eu.get("TailscaleIPs") or d.get("TailscaleIPs") or []) if ":" not in ip]
    usuario = (d.get("User") or {}).get(str(eu.get("UserID")), {}) if isinstance(d.get("User"), dict) else {}
    return {"estado": d.get("BackendState", ""), "ip": ips[0] if ips else "",
            "nome": str(eu.get("DNSName") or "").rstrip("."), "conta": usuario.get("LoginName", "")}


def tailscale_status() -> dict:
    exe = tailscale_exe()
    if not exe:
        return {"estado": "ausente", "ip": "", "nome": "", "conta": ""}
    cod, out = rodar([exe, "status", "--json"], timeout=10, encoding="utf-8")
    inicio = out.find("{")
    return ler_status_tailscale(out[inicio:] if inicio >= 0 else out)


def alvo_serve(url_local: str) -> str:
    """http://localhost:8000 → http://127.0.0.1:8000; https (certificado próprio) → https+insecure://… (pura)."""
    u = url_local.replace("localhost", "127.0.0.1")
    return "https+insecure://" + u[len("https://"):] if u.startswith("https://") else u


def serve_ativo(texto_status: str) -> bool:
    """Saída de `tailscale serve status --json` → há algo publicado? (pura)."""
    try:
        d = json.loads(texto_status or "{}")
    except ValueError:
        return False
    return bool(d.get("Web") or d.get("TCP"))


def tailscale_https(url_local: str) -> str:
    """2.0: liga o HTTPS do Tailscale (https://nome-do-pc.….ts.net, certificado de verdade). '' = ligado."""
    exe = tailscale_exe()
    if not exe:
        return "Tailscale não instalado"
    cod, out = rodar([exe, "serve", "--bg", alvo_serve(url_local)], timeout=30, encoding="utf-8")
    if cod != 0:
        if "https" in out.lower() and ("enable" in out.lower() or "habilit" in out.lower()):
            return ("ative o HTTPS no painel do Tailscale (login.tailscale.com → DNS → HTTPS Certificates) e tente de "
                    "novo")
        return out[-200:] or "o tailscale serve falhou"
    return ""


def tailscale_https_ligado() -> bool:
    exe = tailscale_exe()
    if not exe:
        return False
    _c, out = rodar([exe, "serve", "status", "--json"], timeout=10, encoding="utf-8")
    inicio = out.find("{")
    return serve_ativo(out[inicio:] if inicio >= 0 else "")


def instalar_tailscale() -> str:
    if WIN and shutil.which("winget"):
        cod, out = rodar(["winget", "install", "--id", "Tailscale.Tailscale", "-e", "--silent",
                          "--accept-source-agreements", "--accept-package-agreements"], timeout=600)
        if cod == 0 or "already installed" in out.lower() or "já está instalado" in out.lower():
            return ("Tailscale instalado. Abra o Tailscale (ícone perto do relógio), entre com a sua conta e instale "
                    "o app Tailscale no celular com a MESMA conta. Depois diga 'liga o acesso remoto'.")
        return f"O winget não conseguiu instalar: {out[-200:]}. Baixe em https://tailscale.com/download"
    if LINUX:
        return "No Linux: curl -fsSL https://tailscale.com/install.sh | sh  e depois  sudo tailscale up"
    return "Baixe o Tailscale em https://tailscale.com/download e entre com a sua conta."


# ── Cloudflare Tunnel ───────────────────────────────────────────────────────
def cloudflared_exe() -> str | None:
    achado = shutil.which("cloudflared")
    if achado:
        return achado
    local = FERRAMENTAS / ("cloudflared.exe" if WIN else "cloudflared")
    return str(local) if local.exists() else None


def baixar_cloudflared() -> str:
    """Baixa o cloudflared oficial (GitHub da Cloudflare) para ferramentas/."""
    if MAC:
        return "No Mac: brew install cloudflared"
    nome = "cloudflared-windows-amd64.exe" if WIN else "cloudflared-linux-amd64"
    destino = FERRAMENTAS / ("cloudflared.exe" if WIN else "cloudflared")
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{nome}"
    try:
        FERRAMENTAS.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(".baixando")
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-BR/1.8"})
        with urllib.request.urlopen(req, timeout=180) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        if tmp.stat().st_size < 5_000_000:
            tmp.unlink(missing_ok=True)
            return "O download do cloudflared veio incompleto. Tente de novo."
        tmp.replace(destino)
        if not WIN:
            destino.chmod(0o755)
        return ""
    except Exception as e:
        return f"Não consegui baixar o cloudflared: {e}"


def achar_url_cloudflare(linha: str) -> str:
    m = _RE_CF.search(linha or "")
    return m.group(0) if m else ""


def cloudflare_ligar(url_local: str, sem_verificar_tls: bool = False, espera_s: float = 40) -> tuple[str, str]:
    """Liga o túnel rápido. Devolve (url_publica, erro)."""
    with _lock:
        p = _cf["proc"]
        if p is not None and p.poll() is None and _cf["url"]:
            return _cf["url"], ""
    exe = cloudflared_exe()
    if not exe:
        erro = baixar_cloudflared()
        if erro:
            return "", erro
        exe = cloudflared_exe()
    args = [exe, "tunnel", "--no-autoupdate", "--url", url_local]
    if sem_verificar_tls:
        args.append("--no-tls-verify")
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", **CNW)
    except OSError as e:
        return "", f"O cloudflared não abriu: {e}"
    with _lock:
        _cf.update(proc=proc, url="", erro="", linhas=[])

    def ler():
        for linha in proc.stdout:
            with _lock:
                _cf["linhas"] = (_cf["linhas"] + [linha.rstrip()])[-40:]
                if not _cf["url"]:
                    _cf["url"] = achar_url_cloudflare(linha)
                    if _cf["url"]:                             # 2.3: o número da Twilio segue o endereço novo
                        threading.Thread(target=_avisar_url, args=(_cf["url"],), daemon=True).start()
        with _lock:
            if _cf["proc"] is proc:
                _cf["url"] = ""
    threading.Thread(target=ler, daemon=True, name="cloudflared").start()
    fim = time.time() + espera_s
    while time.time() < fim:
        with _lock:
            if _cf["url"]:
                return _cf["url"], ""
        if proc.poll() is not None:
            break
        time.sleep(0.3)
    with _lock:
        ultimas = " | ".join(_cf["linhas"][-3:])
    return "", f"O túnel não respondeu a tempo. {ultimas[-300:]}"


def _avisar_url(url: str) -> None:
    try:
        from plugins import _atendente_voz
        _atendente_voz.url_mudou(url)
    except Exception as e:
        print(f"[Túnel] {e}")


def cloudflare_url() -> str:
    with _lock:
        p = _cf["proc"]
        return _cf["url"] if p is not None and p.poll() is None else ""


def cloudflare_desligar() -> bool:
    with _lock:
        p, _cf["proc"], _cf["url"] = _cf["proc"], None, ""
    if p is None or p.poll() is not None:
        return False
    p.terminate()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()
    return True


# ── painel ─────────────────────────────────────────────────────────────────────
def painel():
    try:
        from core import registro_ferramentas
        return getattr(registro_ferramentas.app(), "_dashboard", None)
    except Exception:
        return None


def endereco_local(srv=None) -> tuple[str, bool]:
    """(url que o túnel deve buscar no próprio PC, é https com certificado próprio?)."""
    srv = srv if srv is not None else painel()
    try:
        from dashboard.server import PORT, SECURE_PORT
        https = bool(srv is not None and srv._ssl_enabled())
        return (f"https://localhost:{SECURE_PORT}" if https else f"http://localhost:{PORT}"), https
    except Exception:
        return "http://localhost:8000", False


def enderecos() -> dict:
    """Todos os jeitos de abrir o painel agora: {'tailscale': url, 'cloudflare': url, 'local': url}."""
    srv = painel()
    saida = {}
    if srv is not None:
        try:
            saida["local"] = srv.get_url()
        except Exception:
            pass
        ts = tailscale_status()
        if ts["estado"] == "Running" and ts["ip"]:
            base = saida.get("local", "http://x:8000")
            porta = base.rsplit(":", 1)[-1]
            esquema = base.split("://")[0]
            saida["tailscale"] = f"{esquema}://{ts['nome'] or ts['ip']}:{porta}"
            if ts["nome"] and tailscale_https_ligado():          # 2.0: HTTPS de verdade (app do celular, microfone)
                saida["tailscale_https"] = f"https://{ts['nome']}"
    cf = cloudflare_url()
    if cf:
        saida["cloudflare"] = cf
    return saida


def link_de_entrada(base: str, srv=None, validade_s: int = 600) -> str:
    """Link de uso único que já entra no painel (vale 10 minutos)."""
    srv = srv if srv is not None else painel()
    if srv is None or not base:
        return ""
    return f"{base.rstrip('/')}/auto-login?key={srv.new_key(validade_s)}"
