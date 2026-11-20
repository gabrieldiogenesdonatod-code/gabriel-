"""
Guarda do VPS (fork PT-BR 1.6).

De tempos em tempos, entra no seu servidor pelo SSH (o do próprio Windows,
com chave — sem senha guardada) e lê o registro de login: quantas tentativas
de invasão, de quais IPs, que usuários tentaram e — o mais importante — se
alguém ENTROU de um IP novo. Avisa no celular quando algo foge do normal.

    "Jarvis, vigia meu VPS root@1.2.3.4"           (porta 22; ou 'porta 2222')
    "Jarvis, como está a segurança do VPS?"
    "Jarvis, bloqueia o IP 45.10.20.30 no VPS"     (ufw; com confirmação)

Precisa: login por CHAVE SSH funcionando (ssh usuario@ip entra sem senha) e,
para bloquear, sudo sem senha para o ufw (ou rode o comando que ele mostra).
"""

from __future__ import annotations

import re
import threading
import time
from collections import Counter

from plugins._comum import CONFIG, confirmar, gravar_json, ler_json, mostrar, rodar, tem

PLUGIN = {
    "name": "guarda_vps",
    "brief": "VPS guard: reads SSH auth logs over SSH (key auth), reports attack IPs and new logins, can block IPs.",
    "description": (
        "VPS security guard over SSH (key-based login). action='adicionar' with alvo (user@host) + porta, 'status' "
        "(attack summary: failed logins per IP, users tried, successful logins and new IPs), 'recursos' (server CPU, "
        "memory and disk use; also checked every 30 min with alerts), 'bloquear' with ip "
        "(ufw deny, on-screen confirmation), 'remover' with alvo."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "adicionar | status | recursos | bloquear | remover"},
                       "alvo": {"type": "STRING"}, "porta": {"type": "INTEGER"}, "ip": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = CONFIG / "guarda_vps.json"
_iniciado = threading.Event()
COMANDO_LOG = ("(journalctl -u ssh -u sshd --since '-24h' --no-pager -o short-iso 2>/dev/null"
               " || sudo -n journalctl -u ssh -u sshd --since '-24h' --no-pager -o short-iso 2>/dev/null"
               " || tail -n 20000 /var/log/auth.log 2>/dev/null || tail -n 20000 /var/log/secure 2>/dev/null)"
               " | grep -E 'Failed password|Invalid user|Accepted (password|publickey)|maximum authentication'"
               " | tail -n 20000; echo '@@F2B'; systemctl is-active fail2ban 2>/dev/null")


# 1.9: uso do servidor (CPU, memória, disco), além da segurança
COMANDO_RECURSOS = ("echo @@LOAD; cat /proc/loadavg; echo @@CPUS; nproc; echo @@MEM; free -m | awk '/^Mem:/{print $2, $7}';"
                    " echo @@DISCO; df -P -x tmpfs -x devtmpfs -x overlay -x squashfs | tail -n +2; echo @@UP; cat /proc/uptime")


def analisar_recursos(out: str) -> dict:
    """Saída do COMANDO_RECURSOS → {cpu_pct, mem_pct, discos[(ponto, pct)], dias_ligado} (pura)."""
    blocos, atual = {}, None
    for linha in (out or "").splitlines():
        if linha.startswith("@@"):
            atual = linha[2:].strip()
            blocos[atual] = []
        elif atual:
            blocos[atual].append(linha.strip())
    r = {"cpu_pct": None, "mem_pct": None, "discos": [], "dias_ligado": None}
    try:
        carga = float(blocos["LOAD"][0].split()[1])          # média de 5 min
        cpus = max(1, int(blocos["CPUS"][0]))
        r["cpu_pct"] = round(min(100.0, carga / cpus * 100), 1)
    except (KeyError, IndexError, ValueError):
        pass
    try:
        total, livre = (int(x) for x in blocos["MEM"][0].split()[:2])
        r["mem_pct"] = round((total - livre) / total * 100, 1) if total else None
    except (KeyError, IndexError, ValueError):
        pass
    for linha in blocos.get("DISCO", []):
        partes = linha.split()
        if len(partes) >= 6 and partes[4].endswith("%"):
            try:
                r["discos"].append((partes[5], int(partes[4][:-1])))
            except ValueError:
                pass
    try:
        r["dias_ligado"] = round(float(blocos["UP"][0].split()[0]) / 86400, 1)
    except (KeyError, IndexError, ValueError):
        pass
    return r


def alertas_recursos(r: dict, cpu: float = 90, mem: float = 90, disco: float = 90) -> list[str]:
    """O que está passando do limite (pura)."""
    a = []
    if r.get("cpu_pct") is not None and r["cpu_pct"] >= cpu:
        a.append(f"CPU em {r['cpu_pct']:.0f}%")
    if r.get("mem_pct") is not None and r["mem_pct"] >= mem:
        a.append(f"memória em {r['mem_pct']:.0f}%")
    a += [f"disco {ponto} em {pct}%" for ponto, pct in r.get("discos", []) if pct >= disco]
    return a


def recursos(s: dict) -> tuple[dict | None, str]:
    cod, out = _ssh(s["alvo"], int(s.get("porta") or 22), COMANDO_RECURSOS, timeout=25)
    if cod == 255 or "Permission denied" in out or "@@LOAD" not in out:
        return None, f"não li o uso do {s['alvo']} ({out[-160:].strip()})"
    return analisar_recursos(out), ""


def analisar(log: str) -> dict:
    """Linhas do sshd → resumo (pura)."""
    falhas, usuarios, aceitos = Counter(), Counter(), []
    for linha in (log or "").splitlines():
        m = re.search(r"Failed password for (?:invalid user )?(\S+) from ([\d.:a-fA-F]+)", linha)
        if m:
            falhas[m.group(2)] += 1
            usuarios[m.group(1)] += 1
            continue
        m = re.search(r"Invalid user (\S*) from ([\d.:a-fA-F]+)", linha)
        if m:
            falhas[m.group(2)] += 1
            usuarios[m.group(1) or "(vazio)"] += 1
            continue
        m = re.search(r"Accepted (password|publickey) for (\S+) from ([\d.:a-fA-F]+)", linha)
        if m:
            aceitos.append({"metodo": m.group(1), "usuario": m.group(2), "ip": m.group(3), "linha": linha[:120]})
    fail2ban = "@@F2B" in log and log.split("@@F2B", 1)[1].strip().startswith("active")
    return {"falhas": sum(falhas.values()), "ips": falhas.most_common(15), "usuarios": usuarios.most_common(10),
            "aceitos": aceitos, "fail2ban": fail2ban}


def _ssh(alvo: str, porta: int, comando: str, timeout: float = 40) -> tuple[int, str]:
    if not tem("ssh"):
        return -1, "o ssh não está instalado (no Windows: Configurações → Apps → Recursos opcionais → Cliente OpenSSH)"
    return rodar(["ssh", "-p", str(porta), "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                  "-o", "StrictHostKeyChecking=accept-new", alvo, comando], timeout=timeout, encoding="utf-8")


def checar(s: dict) -> tuple[dict | None, str]:
    cod, out = _ssh(s["alvo"], int(s.get("porta") or 22), COMANDO_LOG)
    if cod == 255 or "Permission denied" in out:
        return None, f"não entrei no {s['alvo']} ({out[-160:].strip()}). Configure o login por chave."
    return analisar(out), ""


def novos_ips(r: dict, conhecidos: list[str]) -> list[dict]:
    return [a for a in r["aceitos"] if a["ip"] not in conhecidos]


def _laco(player) -> None:
    time.sleep(120)
    while True:
        try:
            d = ler_json(_ARQ, {}) or {}
            for s in d.get("servidores", []):
                r, erro = checar(s)
                if not r:
                    continue
                novos = novos_ips(r, s.setdefault("ips_conhecidos", []))
                if novos and s["ips_conhecidos"]:                # o 1º registro só aprende
                    from plugins._notificar import notificar
                    ips = ", ".join(sorted({a["ip"] for a in novos}))
                    notificar(player, f"Login no VPS {s['alvo']} de IP novo: {ips}. Se não foi você, troque as chaves "
                                      "e bloqueie o IP.", titulo="GUARDA DO VPS", prioridade="urgent",
                              chave=f"vps:{s['alvo']}:{ips}", intervalo_s=3600)
                s["ips_conhecidos"] = sorted(set(s["ips_conhecidos"]) | {a["ip"] for a in r["aceitos"]})[-50:]
                if r["falhas"] >= int(s.get("limite", 500)):
                    from plugins._notificar import notificar
                    notificar(player, f"{r['falhas']} tentativas de invasão no {s['alvo']} nas últimas 24 h"
                                      + ("" if r["fail2ban"] else "; o fail2ban não está ativo") + ".",
                              titulo="GUARDA DO VPS", falar_agora=False, chave=f"vps-ataque:{s['alvo']}",
                              intervalo_s=12 * 3600, prioridade="high")
                s["ultimo"] = {"ts": time.time(), "falhas": r["falhas"]}
                rr, _e = recursos(s)                              # 1.9: CPU, memória e disco do servidor
                if rr:
                    s["recursos"] = {**rr, "ts": time.time()}
                    altos = alertas_recursos(rr)
                    if altos:
                        from plugins._notificar import notificar
                        notificar(player, f"Servidor {s['alvo']}: " + ", ".join(altos) + ".", titulo="VIGIA DO SERVIDOR",
                                  chave=f"vps-recursos:{s['alvo']}:{','.join(altos)}", intervalo_s=6 * 3600,
                                  prioridade="high")
            gravar_json(_ARQ, d)
        except Exception as e:
            print(f"[GuardaVPS] {e}")
        time.sleep(1800)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="guarda_vps").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("servidores", [])
        if acao == "adicionar":
            alvo = str(p.get("alvo") or "").strip()
            if not re.fullmatch(r"[\w.-]+@[\w.-]+", alvo):
                return "Diga como usuario@ip (ex.: root@1.2.3.4)."
            s = {"alvo": alvo, "porta": int(p.get("porta") or 22), "ips_conhecidos": []}
            r, erro = checar(s)
            if not r:
                return f"Não consegui: {erro}"
            s["ips_conhecidos"] = sorted({a["ip"] for a in r["aceitos"]})
            d["servidores"] = [x for x in d["servidores"] if x["alvo"] != alvo] + [s]
            gravar_json(_ARQ, d)
            return (f"Vigiando {alvo}: {r['falhas']} tentativas falhas nas últimas 24 h; "
                    f"{'fail2ban ativo' if r['fail2ban'] else 'sem fail2ban (recomendo instalar)'}. Confiro a cada 30 min.")
        if acao == "remover":
            d["servidores"] = [x for x in d["servidores"] if x["alvo"] != str(p.get("alvo") or "").strip()]
            gravar_json(_ARQ, d)
            return "Parei de vigiar esse servidor."
        if not d["servidores"]:
            return "Nenhum VPS vigiado. Diga 'vigia meu VPS root@ip'."
        s = next((x for x in d["servidores"] if x["alvo"] == str(p.get("alvo") or "").strip()), d["servidores"][0])
        if acao == "recursos":
            rr, erro = recursos(s)
            if not rr:
                return erro
            partes = [f"CPU {rr['cpu_pct']:.0f}%" if rr["cpu_pct"] is not None else "",
                      f"memória {rr['mem_pct']:.0f}%" if rr["mem_pct"] is not None else "",
                      ", ".join(f"disco {p} {pct}%" for p, pct in rr["discos"][:4]),
                      f"ligado há {rr['dias_ligado']:.0f} dias" if rr["dias_ligado"] is not None else ""]
            altos = alertas_recursos(rr)
            return f"{s['alvo']}: " + "; ".join(x for x in partes if x) + "." + \
                (f" Atenção: {', '.join(altos)}." if altos else "")
        if acao == "bloquear":
            ip = str(p.get("ip") or "").strip()
            if not re.fullmatch(r"[\d.:a-fA-F]{3,45}", ip):
                return "Qual IP?"
            cmd = f"sudo -n ufw deny from {ip} comment jarvis"
            return confirmar(f"vps:bloquear:{ip}", f"Bloquear {ip} no {s['alvo']}?", cmd,
                             lambda: (lambda r: f"Bloqueado: {r[1][-200:]}" if r[0] == 0 else
                                      f"Não deu ({r[1][-160:]}). Rode no servidor: {cmd.replace('-n ', '')}")(
                                 _ssh(s["alvo"], int(s.get("porta") or 22), cmd)))
        r, erro = checar(s)
        if not r:
            return erro
        mostrar(player, f"GUARDA DO VPS — {s['alvo']} (24 h)", "\n".join(
            [f"Tentativas falhas: {r['falhas']}   fail2ban: {'ativo' if r['fail2ban'] else 'NÃO'}", "", "IPs que mais tentaram:"]
            + [f"  {ip:<40} {n}" for ip, n in r["ips"]] + ["", "Usuários tentados:"]
            + [f"  {u:<20} {n}" for u, n in r["usuarios"]] + ["", "Logins com sucesso:"]
            + [f"  {a['usuario']}@{a['ip']} ({a['metodo']})" + ("  ← NOVO" if a["ip"] not in s.get("ips_conhecidos", []) else "")
               for a in r["aceitos"][-15:]]))
        novos = novos_ips(r, s.get("ips_conhecidos", []))
        return (f"{s['alvo']}: {r['falhas']} tentativas falhas em 24 h"
                + (f", o IP que mais tentou foi {r['ips'][0][0]} ({r['ips'][0][1]}×)" if r["ips"] else "")
                + (f". ATENÇÃO: {len(novos)} login(s) de IP novo" if novos else ". Nenhum login de IP desconhecido")
                + ("" if r["fail2ban"] else ". Recomendo o fail2ban") + ". Detalhes no painel.")
    except Exception as e:
        return f"A guarda do VPS falhou: {e}"
