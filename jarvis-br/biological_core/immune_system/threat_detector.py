"""
Camadas 1 e 2 do sistema imune — DETECÇÃO e IDENTIFICAÇÃO.

Detecção: transforma tudo que dá errado em "sintoma" — exceção de plugin, resposta de falha,
ferramenta travada (vigia), rotina de fundo com erro (relógio), plugin que não carregou,
dependência ausente, arquivo de dados quebrado, mudança no DNA e queda na última execução.

Identificação: diz QUAL módulo, classifica o problema (rede, chave, pacote, JSON corrompido,
sintaxe, bug…), calcula a gravidade e separa falha normal de possível ameaça. As regras aqui
são as de alta certeza; o que elas não reconhecem vai para o classificador que aprende (cérebro).
"""

from __future__ import annotations

import importlib.util
import re
import time
import traceback as _tb
from pathlib import Path

from biological_core.config import ESSENCIAIS, GRAVIDADES, RAIZ
from biological_core.immune_system.immune_memory import impressao_digital

DESCRICAO = {
    "rede": "sem internet ou o servidor não respondeu", "timeout": "demorou demais / travou",
    "chave": "chave de API ausente ou inválida", "pacote": "pacote Python não instalado",
    "arquivo": "arquivo ou pasta não encontrado", "json_corrompido": "arquivo de dados corrompido",
    "permissao": "sem permissão (arquivo em uso ou protegido)", "memoria": "faltou memória",
    "recurso": "disco cheio ou limite do sistema", "sintaxe": "erro de sintaxe no código",
    "externo": "o serviço de fora respondeu com erro", "bug": "erro no código do plugin",
    "integridade": "arquivo diferente do DNA", "ameaca": "operação perigosa ou não autorizada",
    "travamento": "parte do organismo parou de responder", "anomalia": "comportamento fora do normal",
    "desconhecida": "problema ainda não identificado",
}

REGRAS = [
    (r"JSONDecodeError|Expecting (value|property name)|Unterminated string|Invalid control character", "json_corrompido"),
    (r"ModuleNotFoundError|No module named|DLL load failed|cannot import name|Needs a package that is not installed", "pacote"),
    (r"SyntaxError|IndentationError|TabError", "sintaxe"),
    (r"MemoryError|Unable to allocate|out of memory|Cannot allocate memory", "memoria"),
    (r"No space left|Errno 28|espa[çc]o suficiente|Too many open files", "recurso"),
    (r"PermissionError|Access is denied|Acesso negado|WinError 5\b|WinError 32\b|Errno 13|Operation not permitted", "permissao"),
    (r"\b401\b|API[_ ]?key not valid|invalid api key|Unauthenticated|chave (inv[aá]lida|n[aã]o configurada)", "chave"),
    (r"FileNotFoundError|No such file or directory|n[aã]o pode encontrar o (arquivo|caminho)", "arquivo"),
    (r"ReadTimeout|ConnectTimeout|TimeoutError|timed out|\bTimeout\b|passou de \d+ s", "timeout"),
    (r"ConnectionError|getaddrinfo|Name or service not known|Failed to establish|Max retries exceeded|"
     r"Network is unreachable|WinError 1006[01]|Temporary failure in name resolution|RemoteDisconnected", "rede"),
    (r"\b(429|50[0234])\b|Too Many Requests|Service Unavailable|Bad Gateway|quota|RESOURCE_EXHAUSTED", "externo"),
]
_REGRAS = [(re.compile(p, re.I), c) for p, c in REGRAS]

BASE_GRAVIDADE = {"json_corrompido": "alta", "sintaxe": "alta", "memoria": "alta", "recurso": "alta",
                  "pacote": "media", "chave": "media", "permissao": "media", "timeout": "media", "arquivo": "media",
                  "bug": "media", "travamento": "media", "rede": "baixa", "externo": "baixa", "anomalia": "baixa",
                  "desconhecida": "baixa", "integridade": "media", "ameaca": "alta"}


def classificar_por_regras(tipo: str, mensagem: str) -> str | None:
    texto = f"{tipo} {mensagem}"
    for rx, cat in _REGRAS:
        if rx.search(texto):
            return cat
    return None


def subir(grav: str, n: int = 1) -> str:
    return GRAVIDADES[min(len(GRAVIDADES) - 1, GRAVIDADES.index(grav) + n)]


def gravidade(categoria: str, modulo: str, ocorrencias: int = 1) -> str:
    g = BASE_GRAVIDADE.get(categoria, "baixa")
    if modulo in ESSENCIAIS:
        g = subir(g)
    if ocorrencias >= 10:
        g = subir(g)
    return g


def _local(erro: BaseException, raiz: Path) -> tuple[str, int]:
    """Arquivo e linha do último quadro DENTRO do projeto (onde costuma estar o conserto)."""
    for q in reversed(_tb.extract_tb(erro.__traceback__) if erro.__traceback__ else []):
        try:
            return Path(q.filename).resolve().relative_to(raiz).as_posix(), int(q.lineno or 0)
        except Exception:
            continue
    return "", 0


def sintoma(modulo: str, acao: str = "*", erro: BaseException | None = None, texto: str = "", origem: str = "plugin",
            categoria: str | None = None, params: dict | None = None, raiz: Path = RAIZ, **extra) -> dict:
    """Um sintoma padronizado: o que todas as camadas seguintes entendem."""
    if erro is not None:
        tipo, msg = type(erro).__name__, str(erro)
        arquivo, linha = _local(erro, Path(raiz))
        tb = "".join(_tb.format_exception(type(erro), erro, erro.__traceback__))[-2000:]
    else:
        tipo, msg, arquivo, linha, tb = extra.pop("tipo", "Falha"), str(texto), extra.pop("arquivo", ""), extra.pop("linha", 0), ""
    categoria = categoria or classificar_por_regras(tipo, msg)
    s = {"ts": time.time(), "origem": origem, "modulo": modulo or "?", "acao": acao or "*", "tipo": tipo,
         "mensagem": msg[:500], "arquivo": arquivo, "linha": linha, "categoria": categoria, "traceback": tb,
         "params": _params_curtos(params), "impressao": impressao_digital(modulo, acao, tipo, msg, arquivo, linha),
         "ameaca": False}
    s.update(extra)
    return s


def _params_curtos(params) -> str:
    if not isinstance(params, dict):
        return ""
    try:
        from core import anonimo                 # 3.2: modo anônimo — os pedidos não ficam no incidente
        if anonimo.ativo():
            return ""
    except Exception:
        pass
    limpo = {k: ("•••" if re.search(r"senha|password|token|key|chave|secret|pin", str(k), re.I) else str(v)[:60])
             for k, v in params.items()}
    return str(limpo)[:200]


def eh_ameaca(s: dict) -> bool:
    """Falha normal × possível ameaça: integridade de arquivo vital, DNA adulterado, defesa que bloqueou,
    configuração crítica alterada por fora."""
    return bool(s.get("ameaca")) or s.get("categoria") == "ameaca"


class DetectorAmeacas:
    def __init__(self, raiz: Path = RAIZ):
        self.raiz = Path(raiz)

    def dependencias_ausentes(self, requirements: list[str] | None = None, essenciais=("PyQt6", "numpy", "google-genai", "sounddevice")) -> dict:
        try:
            from plugins.autodiagnostico import tem
        except Exception:
            def tem(p):
                try:
                    return importlib.util.find_spec(p.lower().replace("-", "_")) is not None
                except Exception:
                    return False
        if requirements is None:
            try:
                linhas = (self.raiz / "requirements.txt").read_text(encoding="utf-8").splitlines()
                requirements = sorted({re.split(r"[<>=!~\[; ]", l.split("#")[0].strip())[0] for l in linhas
                                       if "sys_platform" not in l or self._plataforma_ok(l)} - {""})
            except OSError:
                requirements = []
        falta = [p for p in requirements if not p.startswith("-") and not tem(p)]
        return {"essenciais": [p for p in falta if p in essenciais], "opcionais": [p for p in falta if p not in essenciais]}

    @staticmethod
    def _plataforma_ok(linha: str) -> bool:
        import sys
        m = re.search(r"sys_platform\s*(==|!=)\s*['\"](\w+)['\"]", linha)
        if not m:
            return True
        return (sys.platform == m.group(2)) == (m.group(1) == "==")

    def plugins_quebrados(self, registro) -> list[dict]:
        """Plugins que nem carregaram (sintaxe, pacote faltando…) viram sintomas no início."""
        out = []
        try:
            for r in registro.list_for_ui():
                if not r.get("valid"):
                    erro = str(r.get("error") or "")
                    out.append(sintoma(r["name"], "carregar", texto=erro, origem="carregamento", tipo="NaoCarregou",
                                       categoria=classificar_por_regras("", erro) or "bug", arquivo=f"plugins/{r['name']}.py"))
        except Exception:
            pass
        return out

    def queda_anterior(self) -> dict | None:
        try:
            from core import protecao_falhas
            if protecao_falhas.como_fechou_da_ultima_vez() == "queda":
                trecho = protecao_falhas.queda_anterior()[:300]
                return sintoma("jarvis", "execucao_anterior", texto=f"o JARVIS caiu da última vez: {trecho}",
                               origem="boot", categoria="travamento", tipo="QuedaNativa")
        except Exception:
            pass
        return None
