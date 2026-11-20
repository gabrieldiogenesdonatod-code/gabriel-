"""
IA local (fork PT-BR 3.5) — o JARVIS funcionando SEM INTERNET, com tudo no seu PC.

Com internet: tudo igual, o Gemini conversa (rápido e inteligente).
Sem internet: o JARVIS troca SOZINHO para o modo local e volta para o Gemini quando a rede volta.

    ouvir   → Whisper (faster-whisper, modelo "base", na CPU)
    pensar  → um modelo de linguagem pequeno rodando no llama.cpp (llama-server), no seu PC
              · "leve"    Llama 3.2 1B (≈ 0,8 GB) — o indicado para 8 GB de RAM sem placa de vídeo
              · "esperto" Llama 3.2 3B (≈ 2 GB)   — entende melhor, responde mais devagar
    falar   → a voz do próprio Windows (já vem no sistema)
    atalho  → o cérebro local (core/cerebro.py): comando que você já usou é feito na hora, sem nem
              perguntar ao modelo (o modelo pequeno é lento na CPU).

Instalar é UMA vez, com o seu SIM na tela ("Jarvis, instala a IA local"): baixa o llama-server
oficial do llama.cpp (GitHub), o modelo (Hugging Face) e o faster-whisper (pip). Nada de Ollama,
nada de Qwen, nada pago. Fica tudo na pasta ia_local/ do JARVIS. Depois disso, ele liga o servidor
sozinho quando precisa.

O que é honesto dizer: na CPU, o modelo pequeno leva alguns segundos para começar a responder e
erra mais que o Gemini. É o JARVIS "econômico" — o que importa é que ele continua funcionando.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "ia_local"
ARQ = PASTA / "ia_local.json"
PORTA = 8089
MODELOS = {
    "leve": {"nome": "Llama 3.2 1B", "arquivo": "Llama-3.2-1B-Instruct-Q4_K_M.gguf", "mb": 808,
             "url": "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"},
    "esperto": {"nome": "Llama 3.2 3B", "arquivo": "Llama-3.2-3B-Instruct-Q4_K_M.gguf", "mb": 2020,
                "url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"},
}
LLAMA_RELEASE = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
ASSETS_WINDOWS = (r"bin-win-cpu-x64\.zip$", r"bin-win-avx2-x64\.zip$", r"bin-win-noavx-x64\.zip$")
EXTRA_MB = {"servidor": 120, "whisper": 450}
TESTE_REDE = ("generativelanguage.googleapis.com", 443)
_SEM_CONSOLE = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_instalando = {"ativo": False, "etapa": "", "pct": 0.0}


# ─────────────────────────────────────────────────────────── configuração ───
def config() -> dict:
    try:
        d = json.loads(ARQ.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def salvar(**kw) -> dict:
    d = config()
    d.update(kw)
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = ARQ.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQ)
    return d


def exe_servidor() -> Path:
    return PASTA / "llama" / ("llama-server.exe" if os.name == "nt" else "llama-server")


def arquivo_modelo(chave: str | None = None) -> Path:
    m = MODELOS.get(chave or config().get("modelo") or "leve", MODELOS["leve"])
    return PASTA / "modelos" / m["arquivo"]


def pronto() -> bool:
    """Instalada: servidor + modelo no disco (o Whisper é conferido na hora de ouvir)."""
    return bool(config().get("instalado")) and exe_servidor().is_file() and arquivo_modelo().is_file()


def automatico() -> bool:
    return bool(config().get("auto", True))


# ─────────────────────────────────────────────────────────── puras ───
def escolher_asset(release: dict, padroes=ASSETS_WINDOWS) -> tuple[str, str] | None:
    """O zip do llama.cpp para Windows/CPU na release (o nome muda de versão para versão). Pura."""
    assets = [(a.get("name", ""), a.get("browser_download_url", "")) for a in release.get("assets", [])]
    for p in padroes:
        for nome, url in assets:
            if re.search(p, nome) and url:
                return nome, url
    return None


def mb_necessarios(chave: str, whisper_instalado: bool, servidor_instalado: bool) -> int:
    m = MODELOS[chave]["mb"]
    return m + (0 if servidor_instalado else EXTRA_MB["servidor"]) + (0 if whisper_instalado else EXTRA_MB["whisper"]) + 200


def comando_servidor(exe: Path, modelo: Path, porta: int = PORTA, nucleos: int | None = None) -> list[str]:
    n = max(2, min(8, (nucleos or os.cpu_count() or 4) - 1))
    return [str(exe), "-m", str(modelo), "--host", "127.0.0.1", "--port", str(porta), "-c", "4096", "-t", str(n),
            "--jinja", "--no-webui"]


def pipeline_local() -> tuple[dict, dict]:
    """(pipeline, configurações) do modo local, no formato do config/api_keys.json."""
    pipe = {"llm": "openai_compat", "stt": "whisper", "tts": "system_tts"}
    creds = {"openai_compat": {"base_url": f"http://127.0.0.1:{PORTA}/v1", "model": arquivo_modelo().name,
                               "api_key": "", "max_tools": "10", "max_tool_chars": "7000"},
             "whisper": {"backend": "local", "model": "base", "device": "cpu", "language": "pt"},
             "system_tts": {}}
    return pipe, creds


# ─────────────────────────────────────────────────────────── rede ───
def internet_ok(timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection(TESTE_REDE, timeout=timeout):
            return True
    except OSError:
        return False


# ─────────────────────────────────────────────────────────── servidor ───
def servidor_ligado(timeout: float = 1.5) -> bool:
    try:
        import requests
        return requests.get(f"http://127.0.0.1:{PORTA}/health", timeout=timeout).status_code == 200
    except Exception:
        return False


def ligar_servidor(esperar_s: float = 90) -> str:
    """Liga o llama-server (se ainda não estiver no ar) e espera ele carregar o modelo."""
    global _proc
    if not pronto():
        return "A IA local ainda não está instalada."
    if servidor_ligado():
        return "O servidor da IA local já está ligado."
    with _lock:
        if _proc is None or _proc.poll() is not None:
            log = open(PASTA / "servidor.log", "ab")
            _proc = subprocess.Popen(comando_servidor(exe_servidor(), arquivo_modelo()), stdout=log, stderr=log,
                                     cwd=str(exe_servidor().parent), **_SEM_CONSOLE)
    fim = time.time() + esperar_s
    while time.time() < fim:
        if servidor_ligado():
            return f"IA local ligada ({MODELOS.get(config().get('modelo', 'leve'), MODELOS['leve'])['nome']})."
        if _proc is not None and _proc.poll() is not None:
            return "O servidor da IA local fechou sozinho; veja ia_local/servidor.log."
        time.sleep(0.5)
    return "O servidor da IA local ainda está carregando o modelo."


def desligar_servidor() -> str:
    global _proc
    with _lock:
        p, _proc = _proc, None
    if p is None or p.poll() is not None:
        return "O servidor da IA local não estava ligado por mim."
    p.terminate()
    try:
        p.wait(10)
    except Exception:
        p.kill()
    return "Servidor da IA local desligado."


atexit.register(lambda: desligar_servidor() if _proc is not None else None)


# ─────────────────────────────────────────────────────────── troca automática ───
_temporario = {"ativo": False}


def usar_local_agora() -> bool:
    """Chamado antes de cada conexão: sem internet e com a IA local pronta → modo local (temporário)."""
    if not (pronto() and automatico()) or internet_ok():
        sair_do_local()
        return False
    ligar_servidor()
    pipe, creds = pipeline_local()
    from memory import config_manager
    config_manager.definir_temporario(pipe, creds)
    _temporario["ativo"] = True
    return True


def sair_do_local() -> None:
    if _temporario["ativo"]:
        try:
            from memory import config_manager
            config_manager.definir_temporario(None, None)
        except Exception:
            pass
        _temporario["ativo"] = False


def no_local() -> bool:
    return _temporario["ativo"]


def vigiar_volta(ao_voltar: Callable[[], None], intervalo_s: float = 20) -> threading.Thread:
    """Enquanto estiver no modo local por falta de rede, confere a internet; quando voltar, chama ao_voltar."""
    vigia = _temporario.get("vigia")
    if vigia is not None and vigia.is_alive():
        return vigia

    def laco():
        while _temporario["ativo"]:
            time.sleep(intervalo_s)
            if _temporario["ativo"] and internet_ok():
                ao_voltar()
                return
    t = threading.Thread(target=laco, daemon=True, name="ia_local_volta")
    _temporario["vigia"] = t
    t.start()
    return t


# ─────────────────────────────────────────────────────────── instalação ───
def baixar(url: str, destino: Path, progresso: Callable[[float], None] | None = None, sessao=None) -> Path:
    """Baixa com retomada (.part + Range): se a internet cair no meio, continua de onde parou."""
    import requests
    s = sessao or requests
    destino.parent.mkdir(parents=True, exist_ok=True)
    parte = destino.with_suffix(destino.suffix + ".part")
    feito = parte.stat().st_size if parte.exists() else 0
    cab = {"Range": f"bytes={feito}-"} if feito else {}
    with s.get(url, headers=cab, stream=True, timeout=30, allow_redirects=True) as r:
        if r.status_code == 416:                                    # já estava completo
            parte.replace(destino)
            return destino
        r.raise_for_status()
        if feito and r.status_code != 206:                          # servidor não retoma: começa de novo
            feito = 0
        total = feito + int(r.headers.get("Content-Length") or 0)
        with open(parte, "ab" if feito else "wb") as f:
            for bloco in r.iter_content(1 << 20):
                if bloco:
                    f.write(bloco)
                    feito += len(bloco)
                    if progresso and total:
                        progresso(min(1.0, feito / total))
    parte.replace(destino)
    return destino


LLAMA_RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15"
LLAMA_PAGINA_ULTIMA = "https://github.com/ggml-org/llama.cpp/releases/latest"
LLAMA_DOWNLOAD = "https://github.com/ggml-org/llama.cpp/releases/download/{tag}/llama-{tag}-bin-win-cpu-x64.zip"
MANUAL = ("Baixe à mão em github.com/ggml-org/llama.cpp/releases o arquivo que termina em 'bin-win-cpu-x64.zip' e "
          "coloque na pasta ia_local\\download do JARVIS; depois rode o instalador de novo.")


def tag_da_url(url: str) -> str | None:
    """'…/releases/tag/b5200' → 'b5200'. Pura."""
    m = re.search(r"/releases/tag/([^/?#]+)", url or "")
    return m.group(1) if m else None


def achar_zip_servidor(sessao=None) -> tuple[str, str]:
    """(nome, url) do llama.cpp para Windows/CPU. Três caminhos, porque a API do GitHub às vezes recusa
    (limite de pedidos, rede da escola, antivírus) e a release mais nova às vezes ainda está subindo os arquivos."""
    import requests
    s = sessao or requests
    erros = []
    try:                                           # 1) API: as últimas releases, a primeira que tiver o zip
        r = s.get(LLAMA_RELEASES, timeout=20, headers={"Accept": "application/vnd.github+json"})
        dados = r.json()
        if isinstance(dados, dict):
            erros.append(f"API do GitHub: {str(dados.get('message', dados))[:120]}")
        for rel in dados if isinstance(dados, list) else []:
            achado = escolher_asset(rel)
            if achado:
                return achado
    except Exception as e:
        erros.append(f"API do GitHub: {e}")
    try:                                           # 2) sem API: a página da última versão diz o número dela
        r = s.get(LLAMA_PAGINA_ULTIMA, timeout=20, allow_redirects=False)
        tag = tag_da_url(r.headers.get("Location", "")) or tag_da_url(getattr(r, "url", ""))
        if tag:
            url = LLAMA_DOWNLOAD.format(tag=tag)
            if s.head(url, timeout=20, allow_redirects=True).status_code < 400:
                return f"llama-{tag}-bin-win-cpu-x64.zip", url
            erros.append(f"o arquivo da versão {tag} ainda não está lá")
    except Exception as e:
        erros.append(f"página do GitHub: {e}")
    raise RuntimeError("não consegui achar o llama.cpp no GitHub (" + "; ".join(erros)[:300] + "). " + MANUAL)


def instalar_servidor(progresso=None, sessao=None) -> str:
    if exe_servidor().is_file():
        return "já estava"
    if os.name != "nt":
        raise RuntimeError("o instalador automático do servidor é para Windows; em outro sistema instale o llama.cpp")
    pasta = PASTA / "download"
    manual = sorted(pasta.glob("*bin-win-cpu-x64.zip")) if pasta.is_dir() else []
    if manual:                                     # você baixou à mão: usa esse
        zip_, nome = manual[-1], manual[-1].name
    else:
        nome, url = achar_zip_servidor(sessao)
        zip_ = baixar(url, pasta / nome, progresso, sessao=sessao)
    destino = exe_servidor().parent
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_) as z:
        for info in z.infolist():
            base = Path(info.filename).name
            if base == exe_servidor().name or base.lower().endswith(".dll"):
                with z.open(info) as src, open(destino / base, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    if not exe_servidor().is_file():
        raise RuntimeError("o zip do llama.cpp não tinha o llama-server. " + MANUAL)
    zip_.unlink(missing_ok=True)
    return nome


def whisper_instalado() -> bool:
    from importlib.util import find_spec
    return find_spec("faster_whisper") is not None


def instalar_whisper() -> str:
    if not whisper_instalado():
        r = subprocess.run([sys.executable, "-m", "pip", "install", "faster-whisper"], capture_output=True, text=True,
                           timeout=1800, **_SEM_CONSOLE)
        if r.returncode != 0:
            raise RuntimeError("o pip não conseguiu instalar o faster-whisper: " + (r.stderr or r.stdout)[-300:])
    # Baixa o modelo "base" agora, enquanto tem internet (depois ele fica no cache e funciona offline).
    code = "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"
    subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=1800, **_SEM_CONSOLE)
    return "ok"


def estado_instalacao() -> dict:
    return dict(_instalando)


def instalar(chave: str = "leve", avisar: Callable[[str], None] | None = None) -> str:
    """Instala tudo (servidor, modelo, Whisper). Demora: chame numa thread. Devolve o resumo."""
    if chave not in MODELOS:
        return f"Modelo desconhecido: {chave}. Use leve ou esperto."
    if _instalando["ativo"]:
        return "Já estou instalando a IA local."
    diga = avisar or (lambda t: None)
    precisa = mb_necessarios(chave, whisper_instalado(), exe_servidor().is_file())
    livre = shutil.disk_usage(PASTA.parent).free // (1 << 20)
    if livre < precisa:
        return f"Falta espaço: preciso de uns {precisa} MB livres e o disco tem {livre} MB."
    if not internet_ok():
        return "Para instalar eu preciso de internet uma vez."
    _instalando.update(ativo=True, etapa="", pct=0.0)
    try:
        def etapa(nome):
            _instalando.update(etapa=nome, pct=0.0)
            diga(f"IA local: {nome}…")
        prog = lambda f: _instalando.update(pct=round(f * 100, 1))  # noqa: E731
        etapa("baixando o servidor llama.cpp")
        instalar_servidor(prog)
        m = MODELOS[chave]
        etapa(f"baixando o modelo {m['nome']} (≈ {m['mb']} MB)")
        if not arquivo_modelo(chave).is_file():
            baixar(m["url"], arquivo_modelo(chave), prog)
        etapa("instalando o Whisper para ouvir sem internet")
        instalar_whisper()
        salvar(instalado=True, modelo=chave, auto=config().get("auto", True), quando=time.strftime("%Y-%m-%d %H:%M"))
        return (f"IA local instalada: {m['nome']}. Quando a internet cair, eu passo sozinho para o modo local e "
                "volto para o Gemini quando ela voltar.")
    except Exception as e:
        return f"A instalação parou em '{_instalando['etapa']}': {e}. Peça de novo que eu continuo de onde parei."
    finally:
        _instalando.update(ativo=False)


def remover_modelo(chave: str) -> str:
    arq = arquivo_modelo(chave)
    if not arq.is_file():
        return "Esse modelo não está baixado."
    if config().get("modelo") == chave and servidor_ligado():
        desligar_servidor()
    arq.unlink()
    if config().get("modelo") == chave:
        salvar(instalado=False)
    return f"Apaguei o modelo {MODELOS[chave]['nome']} ({MODELOS[chave]['mb']} MB liberados)."


def conversar(texto: str, timeout: float = 120) -> str:
    """Pergunta direto ao modelo local (para testar sem precisar derrubar a internet)."""
    import requests
    if not servidor_ligado():
        msg = ligar_servidor()
        if not servidor_ligado():
            return msg
    r = requests.post(f"http://127.0.0.1:{PORTA}/v1/chat/completions", timeout=timeout, json={
        "model": arquivo_modelo().name, "max_tokens": 200, "temperature": 0.6,
        "messages": [{"role": "system", "content": "Você é o JARVIS. Responda em português do Brasil, curto."},
                     {"role": "user", "content": texto}]})
    r.raise_for_status()
    return (r.json()["choices"][0]["message"].get("content") or "").strip()


# ─────────────────────────────────────────────────────────── atalho do cérebro ───
class ComReflexo:
    """Embrulha o modelo do modo local: comando que o cérebro já sabe vira chamada de ferramenta NA HORA,
    e a resposta depois da ferramenta sai pronta, sem esperar o modelo (que é lento na CPU)."""

    PREFIXO = "reflexo-"

    def __init__(self, llm, sem_ia: bool = True):
        self._llm, self._sem_ia, self._n = llm, sem_ia, 0
        self.caps = dict(getattr(llm, "caps", {}) or {})

    def __getattr__(self, nome):
        return getattr(self._llm, nome)

    @staticmethod
    def _texto(msg: dict) -> str:
        c = msg.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return " ".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
        return ""

    async def chat(self, messages, tools=None, *, stream: bool = True):
        ultimo = messages[-1] if messages else {}
        if ultimo.get("role") == "tool" and str(ultimo.get("tool_call_id", "")).startswith(self.PREFIXO):
            from core import cerebro
            yield {"text": cerebro.resposta_curta(self._texto(ultimo))}
            return
        if ultimo.get("role") == "user":
            try:
                from core import cerebro
                r = cerebro.entender(self._texto(ultimo), sem_ia=self._sem_ia)
            except Exception:
                r = {"reflexo": False}
            if r.get("reflexo"):
                from providers.base import FunctionCall
                self._n += 1
                yield {"tool_calls": [FunctionCall(id=f"{self.PREFIXO}{self._n}", name=r["ferramenta"], args=dict(r["args"]))]}
                return
        async for ev in self._llm.chat(messages, tools, stream=stream):
            yield ev


if __name__ == "__main__":                       # instalar_ia_local.bat: instala sem depender do Gemini
    chave = sys.argv[1] if len(sys.argv) > 1 else "esperto"

    def _mostrar_progresso():
        ultimo = ""
        while _instalando["ativo"] or not ultimo:
            linha = f"  {_instalando['etapa']} {_instalando['pct']:.0f}%"
            if linha != ultimo and _instalando["etapa"]:
                print(linha, flush=True)
                ultimo = linha
            time.sleep(2)
            if not _instalando["ativo"] and ultimo:
                break

    threading.Thread(target=_mostrar_progresso, daemon=True).start()
    print(instalar(chave, avisar=lambda t: print(t, flush=True)), flush=True)
    if pronto():
        print("Testando: ligando o servidor (pode levar 1 minuto)...", flush=True)
        print(ligar_servidor(), flush=True)
        try:
            print("A IA local respondeu:", conversar("Diga oi em uma frase curta."), flush=True)
        except Exception as e:
            print("Teste falhou:", e, flush=True)
        desligar_servidor()
