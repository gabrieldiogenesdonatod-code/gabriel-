"""
JARVIS BIOLOGICAL CORE — ARTIFICIAL LIFE ARCHITECTURE (fork PT-BR 3.1).

Um organismo digital dentro do JARVIS: cérebro (IA básica local), coração, sistema nervoso,
circulação, DNA digital, sistema imunológico de 8 camadas, regeneração e células especializadas.
São sistemas computacionais concretos inspirados na biologia — não há "vida" de verdade aqui.

API usada pela integração (todas à prova de falha: um defeito no organismo nunca derruba o JARVIS):

    iniciar(player)            liga (idempotente). O plugin `organismo` chama no início da sessão.
    portao(nome, params)       antes de cada plugin: None (segue) · ("bloquear", msg) · ("confirmar", título, detalhe)
    inicio(nome, params)/fim   marca a ferramenta em andamento (é assim que o coração vê o que travou)
    resultado(...)             depois de cada plugin
    travou / terminou_tarde    pelo vigia de travamento
    erro_rotina / permite_rotina   pelo relógio central
    encerrar()                 desligamento seguro (também roda sozinho ao fechar)

Quando o organismo não está ligado, nada disso custa nada: a integração nem importa este pacote.
"""

from __future__ import annotations

import atexit
import threading

_org = None
_lock = threading.Lock()
_avisou_desligado = False


def iniciar(player=None, registro=None, **kw):
    """Liga o organismo (uma vez). Devolve o Organismo, ou None se desligado na configuração.
    registro: o registro de plugins para a ronda inicial (padrão: o registro vivo do JARVIS)."""
    global _org, _avisou_desligado
    from biological_core.config import cfg
    if cfg("bio_desligado"):
        if not _avisou_desligado:
            _avisou_desligado = True
            print("[Organismo] desligado em config/api_keys.json (\"bio_desligado\"): sem sistema imune, sem regeneração.")
        return None
    with _lock:
        if _org is not None and _org.ligado:
            if player is not None:
                _org.player = player
            return _org
        from biological_core.organismo import Organismo
        org = Organismo(**kw)
        org.player = player
        org.iniciar(registro)
        try:                                   # Fork PT-BR 3.6: incidentes e reparos ficam provados no livro-razão
            from core import livro_razao
            livro_razao.ligar_ao_organismo(org)
        except Exception as e:
            print(f"[Organismo] livro-razão: {e}")
        _org = org
        atexit.register(encerrar)
        return org


def ativo() -> bool:
    return _org is not None and _org.ligado


def atual():
    """O organismo ligado (ou None). (Não se chama organismo(): esse nome é o submódulo biological_core.organismo.)"""
    return _org


def encerrar() -> list:
    global _org
    with _lock:
        org, _org = _org, None
    if org is None:
        return []
    try:
        return org.encerrar()
    except Exception:
        return []


def portao(nome: str, params):
    org = _org
    if org is None or not org.ligado:
        return None
    try:
        return org.portao(nome, params if isinstance(params, dict) else {})
    except Exception:
        return None


def inicio(nome: str, params) -> int:
    org = _org
    try:
        return org.sentinela.inicio(nome, params if isinstance(params, dict) else {}) if org and org.ligado else 0
    except Exception:
        return 0


def fim(tok: int) -> None:
    org = _org
    if org and tok:
        try:
            org.sentinela.fim(tok)
        except Exception:
            pass


def resultado(nome: str, params, ms: float, ok: bool, erro=None, texto: str = "") -> None:
    org = _org
    if org is None or not org.ligado:
        return
    try:
        org.sentinela.resultado(nome, params if isinstance(params, dict) else {}, ms, ok, erro, texto)
    except Exception:
        pass


def travou(nome: str, limite: float) -> None:
    org = _org
    if org and org.ligado:
        try:
            org.sentinela.travou(nome, limite)
        except Exception:
            pass


def terminou_tarde(nome: str, segundos: float, ok: bool) -> None:
    org = _org
    if org and org.ligado:
        try:
            org.sentinela.terminou_tarde(nome, segundos, ok)
        except Exception:
            pass


def erro_rotina(nome: str, erro) -> None:
    org = _org
    if org and org.ligado and not str(nome).startswith("bio_"):
        try:
            org.sentinela.erro_rotina(nome, erro)
        except Exception:
            pass


def permite_rotina(nome: str) -> bool:
    org = _org
    if org is None or not org.ligado:
        return True
    try:
        return org.permite_rotina(nome)
    except Exception:
        return True


def resumo() -> str:
    org = _org
    return org.resumo_texto() if org and org.ligado else "O organismo não está ligado."
