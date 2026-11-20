"""
Ajudantes compartilhados pelos plugins do J.A.R.V.I.S BR.

Começa com "_": o carregador de plugins pula este arquivo, então ele não vira
ferramenta.

O que tem aqui
    * caminhos do projeto (BASE, MEMORIA, CONFIG);
    * `cfg(ns, PLUGIN_SETTINGS)`: a configuração do plugin já com os valores
      padrão aplicados (o app só grava o que você mudou no painel);
    * `rodar` / `powershell`: subprocess que NUNCA abre janela de console no
      Windows e nunca levanta exceção;
    * `falar` / `registrar`: falar pelo JARVIS e escrever no registro;
    * `confirmar`: a trava do core/confirm.py, com proteção contra dois
      pedidos ao mesmo tempo;
    * `desfazer`: registra a volta no core/undo.py;
    * formatação brasileira de números, bytes e porcentagens;
    * JSON com gravação atômica.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

SO = platform.system()                 # "Windows" | "Darwin" | "Linux"
WIN, MAC, LINUX = SO == "Windows", SO == "Darwin", SO == "Linux"

BASE = Path(__file__).resolve().parent.parent
MEMORIA = BASE / "memory"
CONFIG = BASE / "config"

NAO_DISPONIVEL = "Não disponível neste sistema."

# Nenhum subprocess abre janela de console no Windows.
CNW: dict = ({"creationflags": subprocess.CREATE_NO_WINDOW} if WIN else {})


# ── configuração ───────────────────────────────────────────────────────────────
def cfg(namespace: str, settings: dict | None = None) -> dict:
    """Valores salvos do plugin, completados pelos padrões do PLUGIN_SETTINGS."""
    padroes = {}
    for f in (settings or {}).get("fields", []):
        if isinstance(f, dict) and f.get("key"):
            padroes[f["key"]] = f.get("default")
    try:
        from memory.config_manager import get_plugin_config
        salvos = get_plugin_config(namespace)
    except Exception:
        salvos = {}
    padroes.update({k: v for k, v in salvos.items() if v is not None and v != ""})
    return padroes


def salvar_cfg(namespace: str, valores: dict) -> None:
    try:
        from memory.config_manager import save_plugin_config
        save_plugin_config(namespace, valores)
    except Exception as e:
        print(f"[Comum] não salvei a configuração de {namespace}: {e}")


def plugin_ligado(nome: str) -> bool:
    try:
        from memory.config_manager import get_plugin_enabled
        return bool(get_plugin_enabled(nome))
    except Exception:
        return True


def nome_usuario() -> str:
    try:
        dados = json.loads((CONFIG / "api_keys.json").read_text(encoding="utf-8"))
        return (dados.get("user_name") or "").strip()
    except Exception:
        return ""


# ── números ────────────────────────────────────────────────────────────────────
def num(valor, padrao: float = 0.0) -> float:
    """Aceita 40, '40', '40,5', '1.234,56', '85%', ' 90 '."""
    if isinstance(valor, bool):
        return float(valor)
    if isinstance(valor, (int, float)):
        return float(valor)
    t = str(valor or "").replace("%", "").replace("R$", "").strip().replace(" ", "")
    if not t:
        return padrao
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return padrao


def sim(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor or "").strip().lower() in ("1", "true", "sim", "s", "yes", "on", "ligado")


def br(valor: float, casas: int = 1) -> str:
    """1234.5 → '1.234,5'."""
    s = f"{valor:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def tamanho(n: float) -> str:
    """Bytes em texto: 3.4e9 → '3,2 GB'."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "?"
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unidade == "TB":
            casas = 0 if unidade in ("B", "KB") else 1
            return f"{br(n, casas)} {unidade}"
        n /= 1024
    return f"{br(n)} TB"


def velocidade(bps: float) -> str:
    """Bytes por segundo em texto: 1_250_000 → '1,2 MB/s'."""
    return tamanho(bps) + "/s"


def duracao(segundos: float) -> str:
    s = int(max(0, segundos))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}min"
    if m:
        return f"{m}min {s:02d}s"
    return f"{s}s"


# ── subprocess sem console ─────────────────────────────────────────────────────
def tem(programa: str) -> bool:
    return shutil.which(programa) is not None


def rodar(args: list[str], timeout: float = 15, entrada: str | None = None,
          encoding: str | None = None) -> tuple[int, str]:
    """(código, saída+erro). Nunca levanta exceção; -1 quando nem rodou."""
    if encoding is None:
        encoding = "oem" if WIN else "utf-8"
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout,
                           input=entrada.encode(encoding, "replace") if entrada else None,
                           **CNW)
        saida = (r.stdout or b"") + (b"\n" + r.stderr if r.stderr else b"")
        try:
            texto = saida.decode(encoding, "replace")
        except LookupError:
            texto = saida.decode("utf-8", "replace")
        return r.returncode, texto.strip()
    except FileNotFoundError:
        return -1, f"{args[0]} não encontrado"
    except subprocess.TimeoutExpired:
        return -1, f"{args[0]} demorou demais"
    except Exception as e:
        return -1, str(e)


def iniciar(args: list[str]) -> bool:
    """Inicia sem esperar e sem console. True se o processo começou."""
    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **CNW)
        return True
    except Exception as e:
        print(f"[Comum] não iniciei {args[:1]}: {e}")
        return False


def powershell(script: str, timeout: float = 20) -> tuple[int, str]:
    """Roda um script PowerShell sem janela e com saída em UTF-8."""
    if not WIN:
        return -1, NAO_DISPONIVEL
    prefixo = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
               "$ProgressPreference='SilentlyContinue';"
               "$ErrorActionPreference='SilentlyContinue';")
    return rodar(["powershell", "-NoProfile", "-NonInteractive",
                  "-ExecutionPolicy", "Bypass", "-Command", prefixo + script],
                 timeout=timeout, encoding="utf-8")


def powershell_json(script: str, timeout: float = 20):
    """Roda e interpreta a saída como JSON (lista ou dict). None se falhar."""
    codigo, saida = powershell(script + " | ConvertTo-Json -Depth 4 -Compress",
                               timeout=timeout)
    if codigo != 0 or not saida.strip():
        return None
    inicio = min([i for i in (saida.find("["), saida.find("{")) if i >= 0], default=-1)
    if inicio < 0:
        return None
    try:
        return json.loads(saida[inicio:])
    except Exception:
        return None


def como_lista(valor) -> list:
    """O ConvertTo-Json do PowerShell devolve objeto solto quando é um só."""
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def abrir_no_sistema(alvo: str) -> bool:
    """Abre arquivo, pasta ou URL com o programa padrão."""
    try:
        if WIN:
            os.startfile(alvo)                          # noqa: S606
            return True
        return iniciar(["open" if MAC else "xdg-open", alvo])
    except Exception as e:
        print(f"[Comum] não abri {alvo}: {e}")
        return False


def eh_admin() -> bool:
    try:
        if WIN:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def rodar_como_admin(programa: str, argumentos: str = "") -> bool:
    """Windows: pede elevação (aparece o aviso do UAC). True se o UAC aceitou."""
    if not WIN:
        return False
    try:
        import ctypes
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", programa,
                                                argumentos or None, None, 0)
        return int(r) > 32
    except Exception as e:
        print(f"[Comum] elevação falhou: {e}")
        return False


# ── falar e registrar ──────────────────────────────────────────────────────────
def registrar(player, mensagem: str) -> None:
    print(f"[JARVIS-BR] {mensagem}")
    if player is not None:
        try:
            player.write_log(mensagem if ":" in mensagem[:6] else f"SYS: {mensagem}")
        except Exception:
            pass


def falar(player, instrucao: str) -> None:
    """Pede ao JARVIS para falar agora. Funciona com request_say (o que o
    main.py instala na interface) ou plugin_say."""
    if player is None:
        return
    for nome in ("request_say", "plugin_say"):
        fn = getattr(player, nome, None)
        if callable(fn):
            try:
                fn(instrucao)
                return
            except Exception as e:
                print(f"[Comum] não consegui falar: {e}")


def avisar(player, texto: str, etiqueta: str = "AVISO") -> None:
    """Registra e fala uma frase curta, no idioma da conversa."""
    registrar(player, texto)
    try:                                                       # 2.4: central de avisos (não fala no meio do jogo)
        from core import central_avisos
        central_avisos.avisar(texto, central_avisos.prioridade_de(etiqueta, "", texto), etiqueta, player)
    except Exception:
        falar(player, f"[{etiqueta}] Diga ao usuário, em UMA frase curta e no idioma "
                      f"da conversa: {texto} Não chame nenhuma ferramenta.")


def mostrar(player, titulo: str, texto: str) -> None:
    if player is not None:
        try:
            player.show_content(titulo, texto)
        except Exception:
            pass


# ── confirmar e desfazer ───────────────────────────────────────────────────────
def confirmar(chave: str, titulo: str, detalhe: str,
              acao: Callable[[], str]) -> str:
    """Põe a ação atrás do botão CONFIRMAR do HUD.

    A ação só roda se uma pessoa apertar o botão. O modelo não consegue
    confirmar sozinho."""
    try:
        from core import confirm
    except Exception:
        return "A confirmação não está disponível agora, então não fiz nada."
    if confirm.pending_title():
        return ("Já existe uma confirmação esperando na tela. Responda aquela "
                "primeiro.")
    return confirm.request(key=chave, title=titulo, detail=detalhe, run=acao)


def desfazer(rotulo: str, funcao: Callable[[], str]) -> None:
    try:
        from core.undo import push_undo
        push_undo(rotulo, funcao)
    except Exception:
        pass


# ── JSON atômico ───────────────────────────────────────────────────────────────
_json_lock = threading.Lock()


def ler_json(caminho: Path, padrao=None):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def gravar_json(caminho: Path, dados) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    with _json_lock:
        tmp.write_text(json.dumps(dados, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(caminho)


def pasta_usuario(nome: str) -> Path:
    """Downloads, Vídeos, Documentos… respeitando a pasta real no Windows."""
    casa = Path.home()
    if WIN and nome in ("Downloads", "Videos", "Documents", "Pictures", "Desktop"):
        guids = {"Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
                 "Videos": "My Video", "Documents": "Personal",
                 "Pictures": "My Pictures", "Desktop": "Desktop"}
        try:
            import winreg
            chave = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            valor, _ = winreg.QueryValueEx(chave, guids[nome])
            return Path(os.path.expandvars(valor))
        except Exception:
            pass
    alternativas = {"Videos": ["Videos", "Vídeos", "Movies"],
                    "Documents": ["Documents", "Documentos"],
                    "Pictures": ["Pictures", "Imagens"],
                    "Desktop": ["Desktop", "Área de Trabalho", "Área de trabalho"]}
    for n in alternativas.get(nome, [nome]):
        if (casa / n).exists():
            return casa / n
    return casa / nome


def pasta_jarvis(nome: str) -> Path:
    """2.16: Documentos/JARVIS/<nome>, criada se não existir."""
    pasta = pasta_usuario("Documents") / "JARVIS" / nome
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
