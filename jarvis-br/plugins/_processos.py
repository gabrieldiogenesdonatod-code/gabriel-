"""
Operações sobre processos — finalizar, suspender, retomar, prioridade e abrir
o local do arquivo. Usado pelo plugin monitor_sistema, pelo painel 📊 MONITOR e
pelo controle do celular, para as regras serem as mesmas em todo lugar.

Toda operação passa pela lista de proteção (plugins/_protecao.py). Finalizar é
irreversível, então quem chama decide se pede confirmação (o plugin pede pelo
core/confirm.py; o painel tem o próprio botão "tem certeza?"). Suspender e
mudar prioridade são reversíveis e registram desfazer no core/undo.py.
"""

from __future__ import annotations

import difflib
import os
import platform
import subprocess

import psutil

from plugins._comum import CNW, desfazer, iniciar
from plugins._protecao import nome_base, proteger_processo

_WIN = platform.system() == "Windows"
_MAC = platform.system() == "Darwin"

# nível → (Windows, Unix nice)
_PRIORIDADES = {
    "baixa": ("IDLE_PRIORITY_CLASS", 19),
    "abaixo": ("BELOW_NORMAL_PRIORITY_CLASS", 10),
    "normal": ("NORMAL_PRIORITY_CLASS", 0),
    "acima": ("ABOVE_NORMAL_PRIORITY_CLASS", -5),
    "alta": ("HIGH_PRIORITY_CLASS", -10),
}
_SINONIMOS_PRIORIDADE = {
    "minima": "baixa", "mínima": "baixa", "low": "baixa", "idle": "baixa",
    "abaixo do normal": "abaixo", "below": "abaixo", "below_normal": "abaixo",
    "acima do normal": "acima", "above": "acima", "above_normal": "acima",
    "high": "alta", "máxima": "alta", "maxima": "alta",
}


def nivel_prioridade(texto: str) -> str | None:
    t = str(texto or "").strip().lower()
    t = _SINONIMOS_PRIORIDADE.get(t, t)
    return t if t in _PRIORIDADES else None


def achar(alvo) -> list[psutil.Process]:
    """Processos por PID ('1234') ou por nome ('chrome', 'Chrome.exe').

    Nome: primeiro igual, depois começando com, depois parecido (difflib)."""
    texto = str(alvo or "").strip()
    if not texto:
        return []
    if texto.isdigit():
        try:
            return [psutil.Process(int(texto))]
        except Exception:
            return []
    procurado = nome_base(texto)
    iguais, comecam, todos = [], [], {}
    for p in psutil.process_iter(["name"]):
        n = nome_base(p.info.get("name") or "")
        if not n:
            continue
        todos.setdefault(n, []).append(p)
        if n == procurado:
            iguais.append(p)
        elif n.startswith(procurado) or procurado in n.replace(" ", ""):
            comecam.append(p)
    if iguais:
        return iguais
    if comecam:
        return comecam
    perto = difflib.get_close_matches(procurado, list(todos), n=1, cutoff=0.75)
    return todos[perto[0]] if perto else []


def achar_pids(pids) -> list[psutil.Process]:
    """Os processos que ainda existem entre estes PIDs."""
    vivos = []
    for pid in pids or []:
        try:
            vivos.append(psutil.Process(int(pid)))
        except Exception:
            continue
    return vivos


def descrever(procs: list[psutil.Process]) -> str:
    nomes = {}
    for p in procs:
        try:
            nomes[p.name()] = nomes.get(p.name(), 0) + 1
        except Exception:
            pass
    return ", ".join(f"{n} ({q})" if q > 1 else n for n, q in nomes.items()) or "nada"


def separar_protegidos(procs) -> tuple[list, list[str]]:
    ok, recusados = [], []
    for p in procs:
        motivo = proteger_processo(p)
        if motivo:
            try:
                recusados.append(f"{p.name()} ({motivo})")
            except Exception:
                recusados.append(f"PID {p.pid} ({motivo})")
        else:
            ok.append(p)
    return ok, sorted(set(recusados))


def finalizar(procs: list[psutil.Process], espera: float = 3.0) -> str:
    alvo, recusados = separar_protegidos(procs)
    if not alvo:
        return ("Não finalizei nada: " + "; ".join(recusados)) if recusados else \
            "Nenhum processo encontrado."
    nomes = descrever(alvo)          # antes de morrerem, enquanto o nome existe
    for p in alvo:
        try:
            p.terminate()
        except Exception:
            pass
    _vivos_ok, vivos = psutil.wait_procs(alvo, timeout=espera)
    for p in vivos:
        try:
            p.kill()
        except Exception:
            pass
    _f, ainda = psutil.wait_procs(vivos, timeout=2.0)
    msg = f"Finalizei {len(alvo) - len(ainda)} processo(s): {nomes}."
    if ainda:
        msg += f" {len(ainda)} não fecharam (talvez precisem de administrador)."
    if recusados:
        msg += " Protegidos, não mexi: " + "; ".join(recusados) + "."
    return msg


def suspender(procs) -> str:
    alvo, recusados = separar_protegidos(procs)
    feitos = []
    for p in alvo:
        try:
            p.suspend()
            feitos.append(p)
        except Exception:
            pass
    if feitos:
        pids = [p.pid for p in feitos]
        desfazer(f"suspender {descrever(feitos)}", lambda ps=pids: retomar_pids(ps))
    msg = (f"Suspendi {descrever(feitos)}." if feitos else "Não consegui suspender.")
    if recusados:
        msg += " Protegidos: " + "; ".join(recusados) + "."
    return msg


def retomar_pids(pids) -> str:
    ok = 0
    for pid in pids:
        try:
            psutil.Process(pid).resume()
            ok += 1
        except Exception:
            pass
    return f"Retomei {ok} processo(s)."


def retomar(procs) -> str:
    return retomar_pids([p.pid for p in procs])


def _ler_nice(p):
    try:
        return p.nice()
    except Exception:
        return None


def prioridade(procs, nivel: str) -> str:
    chave = nivel_prioridade(nivel)
    if not chave:
        return ("Prioridade desconhecida. Use baixa, abaixo, normal, acima ou alta. "
                "Tempo real eu não uso: pode travar o computador.")
    alvo, recusados = separar_protegidos(procs)
    win_nome, unix_nice = _PRIORIDADES[chave]
    valor = getattr(psutil, win_nome) if _WIN else unix_nice
    antes, feitos, sem_permissao = {}, [], 0
    for p in alvo:
        velho = _ler_nice(p)
        try:
            p.nice(valor)
            antes[p.pid] = velho
            feitos.append(p)
        except psutil.AccessDenied:
            sem_permissao += 1
        except Exception:
            pass
    if antes:
        def voltar(a=dict(antes)):
            for pid, v in a.items():
                if v is None:
                    continue
                try:
                    psutil.Process(pid).nice(v)
                except Exception:
                    pass
            return "Prioridades restauradas."
        desfazer(f"prioridade {chave} em {descrever(feitos)}", voltar)
    msg = f"Prioridade {chave} em {descrever(feitos)}." if feitos else "Não mudei nenhuma prioridade."
    if sem_permissao:
        msg += f" {sem_permissao} precisariam de administrador."
    if recusados:
        msg += " Protegidos: " + "; ".join(recusados) + "."
    return msg


def abrir_local(proc: psutil.Process) -> str:
    try:
        exe = proc.exe()
    except Exception:
        return "Não consegui ler o caminho desse processo (talvez seja do sistema)."
    if not exe or not os.path.exists(exe):
        return "Esse processo não tem um arquivo que eu consiga abrir."
    if _WIN:
        try:
            subprocess.Popen(["explorer", "/select,", exe], **CNW)
            return f"Abri a pasta de {os.path.basename(exe)}."
        except Exception as e:
            return f"Não consegui abrir: {e}"
    if _MAC:
        iniciar(["open", "-R", exe])
    else:
        iniciar(["xdg-open", os.path.dirname(exe)])
    return f"Abri a pasta de {os.path.basename(exe)}."
