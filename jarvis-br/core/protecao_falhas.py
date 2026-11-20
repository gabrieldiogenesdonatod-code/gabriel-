"""
Proteção contra o JARVIS fechar sozinho (fork PT-BR 2.6.1).

Por que ele fechava: no PyQt6, qualquer erro do Python que acontece dentro de
um evento da janela (um timer, um clique, um desenho, um sinal vindo de outra
thread) chama o qFatal() — e o programa FECHA NA HORA, sem mostrar o erro.
Basta instalar o nosso sys.excepthook para o PyQt parar de fazer isso: o erro
é anotado e o JARVIS continua aberto.

Aqui também:
  • erros em threads e "erros sem dono" (unraisable) viram registro, não silêncio;
  • quedas nativas (C/C++: driver de áudio, Qt, OpenCV) vão para o arquivo pelo
    faulthandler, com a pilha de cada thread;
  • tudo fica em memory/erros.log (o arquivo é limitado a ~1 MB).
"""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ARQ = BASE / "memory" / "erros.log"
LIMITE = 1_000_000
SINAL = BASE / "memory" / "ultimo_sinal.json"          # 2.8.1: o sinal de vida (core/por_que_fechou.py lê)
_lock = threading.Lock()
_estado = {"instalado": False, "nativo": None, "ultimos": {}}


def _cortar() -> None:
    try:
        if ARQ.exists() and ARQ.stat().st_size > LIMITE:
            dados = ARQ.read_bytes()[-LIMITE // 2:]
            ARQ.write_bytes(dados)
    except OSError:
        pass


def anotar(titulo: str, tipo, valor, tb) -> str:
    """Escreve o erro no log e no console. Devolve o texto (para testes)."""
    texto = "".join(traceback.format_exception(tipo, valor, tb)) if tipo else str(valor)
    chave = f"{titulo}:{texto[-300:]}"
    agora = time.time()
    with _lock:
        repetido = agora - _estado["ultimos"].get(chave, 0) < 30           # o mesmo erro em laço: anota 1 vez
        _estado["ultimos"][chave] = agora
        if len(_estado["ultimos"]) > 200:
            _estado["ultimos"].clear()
    if repetido:
        return texto
    linha = f"\n=== {time.strftime('%d/%m/%Y %H:%M:%S')} · {titulo} ===\n{texto}"
    try:
        print(f"[ERRO] {titulo}: {tipo.__name__ if tipo else ''} {valor}", file=sys.__stderr__ or sys.stderr)
    except Exception:
        pass
    try:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        _cortar()
        with open(ARQ, "a", encoding="utf-8") as f:
            f.write(linha)
    except OSError:
        pass
    return texto


def _hook(tipo, valor, tb):
    if issubclass(tipo, KeyboardInterrupt):
        sys.__excepthook__(tipo, valor, tb)
        return
    anotar("erro na janela/programa (o JARVIS continua aberto)", tipo, valor, tb)


def _hook_thread(args):
    if args.exc_type is SystemExit:
        return
    nome = getattr(args.thread, "name", "?")
    anotar(f"erro na thread '{nome}'", args.exc_type, args.exc_value, args.exc_traceback)


def _hook_sem_dono(u):
    anotar(f"erro sem dono ({u.err_msg or 'unraisable'})", type(u.exc_value) if u.exc_value else None,
           u.exc_value, u.exc_traceback)


def versao() -> str:
    """A versão desta pasta (lida do ui.py sem importar o Qt)."""
    try:
        import re as _r
        m = _r.search(r'APP_VERSION\s*=\s*"J\.A\.R\.V\.I\.S BR ([^"]+)"', (BASE / "ui.py").read_text(encoding="utf-8"))
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def instalar() -> None:
    if _estado["instalado"]:
        return
    _estado["instalado"] = True
    try:                                                         # 2.7.3: mostra QUAL pasta/versão está abrindo
        print(f"[JARVIS] J.A.R.V.I.S BR {versao()} · pasta: {BASE}", file=sys.__stderr__ or sys.stderr)
    except Exception:
        pass
    sys.excepthook = _hook
    threading.excepthook = _hook_thread
    sys.unraisablehook = _hook_sem_dono
    queda = queda_anterior()
    antes = como_fechou_da_ultima_vez()
    _estado["antes"] = antes
    try:                                                         # 2.8.1: o texto da execução anterior
        _estado["log_anterior"] = ARQ.read_text(encoding="utf-8", errors="replace")[-200000:]
    except OSError:
        _estado["log_anterior"] = ""
    if antes == "sem registro":
        print("[AVISO] Da última vez o JARVIS fechou sem deixar motivo: o processo foi encerrado de fora "
              "(Gerenciador de Tarefas, antivírus, falta de memória ou o Windows). Veja memory/erros.log.",
              file=sys.__stderr__ or sys.stderr)
    elif antes and antes != "queda":
        print(f"[INFO] Da última vez o JARVIS fechou por: {antes}", file=sys.__stderr__ or sys.stderr)
    if queda:
        print("[ERRO] O JARVIS caiu da última vez (queda do Windows/driver, não do Python). Trecho de "
              f"memory/erros.log:\n{queda}", file=sys.__stderr__ or sys.stderr)
    try:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        _cortar()
        _estado["nativo"] = open(ARQ, "a", encoding="utf-8")                 # fica aberto: o faulthandler usa
        _estado["nativo"].write(f"\n=== {time.strftime('%d/%m/%Y %H:%M:%S')} · JARVIS iniciado ===\n"
                                f"versão {versao()} · pasta {BASE} · pid {os.getpid()}\n")   # 2.7.3 / 2.8.1
        _estado["nativo"].flush()
        faulthandler.enable(file=_estado["nativo"], all_threads=True)
        import atexit
        atexit.register(registrar_saida, "o programa terminou (janela fechada ou fim normal)")
    except Exception:
        try:
            faulthandler.enable()
        except Exception:
            pass


def diagnosticar_em_segundo_plano() -> None:
    """Fork PT-BR 2.8.1: se da última vez ele fechou sem motivo ou caiu, descobre por quê (erros.log + registro
    de erros do Windows + sinal de vida) e mostra no console e no erros.log. Numa thread: não atrasa a abertura."""
    if _estado.get("antes") not in ("sem registro", "queda"):
        return

    def ir():
        try:
            from core import por_que_fechou
            texto = por_que_fechou.diagnosticar(_estado.get("log_anterior") or "")
        except Exception as e:
            texto = f"não consegui descobrir ({e})"
        _estado["explicacao"] = texto
        print(f"[POR QUE FECHOU] {texto}", file=sys.__stderr__ or sys.stderr)
        evento(f"diagnóstico da vez anterior: {texto}")
    threading.Thread(target=ir, daemon=True, name="por_que_fechou").start()


def explicacao_anterior() -> str:
    """O diagnóstico da vez anterior (vazio enquanto não terminou ou quando fechou normalmente)."""
    return str(_estado.get("explicacao") or "")


def evento(texto: str) -> None:
    """Fork PT-BR 2.8.1: uma linha na linha do tempo do erros.log ("conectou", "a sessão caiu", "reconectando").
    Numa queda, mostra o que o JARVIS fazia logo antes."""
    linha = " ".join(str(texto or "").split())[:300]
    if not linha:
        return
    with _lock:
        agora = time.time()
        if _estado.get("ult_evento") == linha and agora - _estado.get("ult_evento_ts", 0) < 30:
            return
        _estado["ult_evento"], _estado["ult_evento_ts"] = linha, agora
        try:
            f = _estado.get("nativo")
            if f is not None and not f.closed:
                f.write(f"{time.strftime('%H:%M:%S')} · evento: {linha}\n")
                f.flush()
        except Exception:
            pass


def batimento(atividade=None, a_cada_s: float = 15.0) -> None:
    """Fork PT-BR 2.8.1: o "sinal de vida" em memory/ultimo_sinal.json (hora, RAM, o que fazia). Se o processo
    morrer sem deixar nada, a próxima abertura sabe até quando ele viveu e quanta memória tinha."""
    if _estado.get("batimento"):
        return
    _estado["batimento"] = True
    _estado["parar_batimento"] = False

    def ir():
        import json
        try:
            import psutil
            proc = psutil.Process()
        except Exception:
            psutil = proc = None
        while not _estado.get("parar_batimento"):
            arq = SINAL
            d = {"ts": time.time(), "pid": os.getpid(), "versao": versao(), "threads": threading.active_count()}
            if psutil is not None:
                try:
                    d["ram_pc"] = float(psutil.virtual_memory().percent)
                    d["ram_jarvis_mb"] = proc.memory_info().rss / 1e6
                except Exception:
                    pass
            if atividade is not None:
                try:
                    d["atividade"] = str(atividade() or "")[:120]
                except Exception:
                    pass
            try:
                tmp = arq.with_suffix(".tmp")
                tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
                tmp.replace(arq)
            except Exception:
                pass
            time.sleep(a_cada_s)
    threading.Thread(target=ir, daemon=True, name="sinal_de_vida").start()


def registrar_saida(motivo: str) -> None:
    """Fork PT-BR 2.7.2: anota POR QUE o JARVIS fechou (na próxima abertura ele mostra)."""
    if _estado.get("saida"):
        return
    _estado["saida"] = motivo
    try:
        with open(ARQ, "a", encoding="utf-8") as f:
            f.write(f"\n=== {time.strftime('%d/%m/%Y %H:%M:%S')} · JARVIS fechado: {motivo} ===\n")
    except OSError:
        pass


def como_fechou_da_ultima_vez() -> str:
    """O motivo da última saída; 'queda' (erro do Windows/driver), 'sem registro' (alguém matou o processo,
    antivírus, falta de memória, Windows desligou) ou '' quando é a primeira vez."""
    try:
        txt = ARQ.read_text(encoding="utf-8", errors="replace")[-40000:]
    except OSError:
        return ""
    if "· JARVIS iniciado ===" not in txt:
        return ""
    ultima = txt.rsplit("· JARVIS iniciado ===", 1)[-1]
    if "Fatal Python error" in ultima or "Windows fatal exception" in ultima:
        return "queda"
    m = _re_saida.search(ultima)
    return m.group(1).strip() if m else "sem registro"


def queda_anterior() -> str:
    """Se a última execução morreu numa queda nativa, devolve o começo dela (para mostrar no console)."""
    try:
        txt = ARQ.read_text(encoding="utf-8", errors="replace")[-20000:]
    except OSError:
        return ""
    ultima = txt.rsplit("· JARVIS iniciado ===", 1)[-1]
    i = ultima.find("Fatal Python error")
    if i < 0:
        i = ultima.find("Windows fatal exception")
    return ultima[i:i + 1200].strip() if i >= 0 else ""


def protegido(nome: str, fn, *args, tentativas: int = 5, espera_s: float = 3.0):
    """Roda fn; se cair com erro, anota e tenta de novo (até `tentativas` vezes seguidas)."""
    falhas = 0
    while True:
        inicio = time.time()
        try:
            return fn(*args)
        except KeyboardInterrupt:
            raise
        except Exception:
            anotar(f"{nome} caiu (tentando de novo)", *sys.exc_info())
            falhas = 0 if time.time() - inicio > 120 else falhas + 1          # rodou bem 2 min: zera
            if falhas >= tentativas:
                anotar(f"{nome}: desisti depois de {tentativas} quedas seguidas", None, "veja os erros acima", None)
                return None
            time.sleep(espera_s)


# ── fechar o programa só quando pedem de verdade ──────────────────────────────
import re as _re

_re_saida = _re.compile(r"· JARVIS fechado: (.+?) ===")
import unicodedata as _ud

# Fork PT-BR 2.7.2: antes, qualquer "Jarvis, fecha …" contava, porque a própria palavra "Jarvis" (o nome
# que a pessoa usa para chamar) era tomada como o alvo. "Jarvis, fecha o Discord" fechava o JARVIS.
# Agora o alvo tem que vir LOGO DEPOIS do verbo ("fecha o Jarvis", "desliga você", "encerra o programa"),
# ou a fala inteira tem que ser só o pedido ("pode fechar", "Jarvis, desliga").
_VERBO = (r"(?:fecha|feche|fechar|desliga|desligue|desligar|encerra|encerre|encerrar|finaliza|finalize|finalizar|"
          r"sai|saia|sair|shut ?down|close|exit|quit)")
_ALVO = (r"(?:jarvis|voce|vc|o programa|o assistente|o aplicativo|o app do jarvis|seu programa|yourself|the program)")
_PEDIDO_COM_ALVO = _re.compile(rf"\b{_VERBO}(?:-se)?\s+(?:o\s+|a\s+|tu\s+|o\s+seu\s+)?{_ALVO}\b")
_SO_O_PEDIDO = _re.compile(rf"^(?:(?:ei|ok|e ai)\s+)?(?:jarvis\s+)?(?:pode\s+|por favor\s+|ja\s+pode\s+)*"
                           rf"{_VERBO}(?:-se)?(?:\s+(?:por favor|agora|ja|jarvis))*$")


def pedido_de_fechar(fala: str) -> bool:
    """A pessoa pediu para FECHAR O JARVIS? 'tchau', 'para', 'desliga o intérprete' ou 'Jarvis, fecha o
    Discord' não valem (puro)."""
    t = _ud.normalize("NFKD", str(fala or "").lower()).encode("ascii", "ignore").decode()
    t = _re.sub(r"[^\w\s-]", " ", t)
    t = _re.sub(r"\s+", " ", t).strip()
    if not t:
        return False
    return bool(_PEDIDO_COM_ALVO.search(t) or _SO_O_PEDIDO.match(t))
