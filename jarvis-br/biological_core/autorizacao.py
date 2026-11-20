"""
Autorizações do organismo: o que precisa do SEU sim — e que a IA não consegue dar no seu lugar.

Reparo que muda arquivo (restaurar um JSON, voltar um código para a cópia confiável) e qualquer
mudança no DNA viram um PEDIDO. O pedido aparece:
    • no PC: no banner CONFIRMAR / CANCELAR do core/confirm.py (só um clique de gente aprova);
    • no celular: na aba "Corpo", com os botões Autorizar / Negar.

A ferramenta que o modelo usa (plugin `organismo`) consegue LISTAR e mostrar de novo um pedido,
mas não tem como aprovar: aprovar só existe no caminho da interface. Ao aprovar, sai uma ficha de
uso único (vale 10 minutos, só para aquela ação) e é ela que o reparo confere antes de mexer.

Os pedidos ficam guardados: se o JARVIS reiniciar, eles continuam esperando a sua resposta.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from biological_core.config import cfg, gravar_json, ler_json

VALIDADE_FICHA_S = 600
VALIDADE_PEDIDO_S = 7 * 86400


def _livro(p: dict, resposta: str, origem: str) -> None:
    """Fork PT-BR 3.6: cada autorização dada ou negada fica provada no livro-razão."""
    try:
        from core import livro_razao
        livro_razao.registrar("autorizacao", {"acao": p.get("acao"), "alvo": p.get("alvo"), "titulo": p.get("titulo"),
                                              "resposta": resposta, "origem": origem})
    except Exception:
        pass


class Autorizacoes:
    def __init__(self, arquivo: Path):
        self.arquivo = Path(arquivo)
        self._lock = threading.Lock()
        self._pendentes: dict[str, dict] = {}
        self._executores: dict[str, Callable[[str], str]] = {}
        self._fabricas: dict[str, Callable[[dict], Callable[[str], str]]] = {}
        self._fichas: dict[str, tuple[str, float]] = {}
        self.historico: deque[dict] = deque(maxlen=50)
        self.ao_mudar: Callable[[], None] | None = None
        d = ler_json(self.arquivo, {}) or {}
        agora = time.time()
        self._pendentes = {p["id"]: p for p in d.get("pendentes", []) if agora - p.get("criado", 0) < VALIDADE_PEDIDO_S}
        self.historico.extend(d.get("historico", [])[-50:])

    # ── pedidos ───────────────────────────────────────────────────────────────
    def registrar_fabrica(self, acao: str, fabrica: Callable[[dict], Callable[[str], str]]) -> None:
        """Como refazer a ação de um pedido depois de reiniciar (as funções não vão para o disco)."""
        self._fabricas[acao] = fabrica

    def pedir(self, acao: str, titulo: str, detalhe: str, executar: Callable[[str], str] | None, alvo: str = "",
              mostrar: bool = True, dados: dict | None = None) -> dict:
        with self._lock:
            p = next((x for x in self._pendentes.values() if x["acao"] == acao and x["alvo"] == alvo), None)
            if p is None:
                pid = f"A{secrets.randbelow(90000) + 10000}"
                while pid in self._pendentes:
                    pid = f"A{secrets.randbelow(90000) + 10000}"
                p = {"id": pid, "acao": acao, "alvo": alvo, "titulo": titulo[:120], "detalhe": detalhe[:600],
                     "criado": time.time(), "dados": dict(dados or {})}
                self._pendentes[pid] = p
            if executar is not None:
                self._executores[p["id"]] = executar
        self._gravar()
        if mostrar:
            p["tela"] = self.mostrar(p["id"])
        return p

    def pre_autorizado(self, acao: str) -> bool:
        return acao in set(cfg("bio_pre_autorizados", []) or [])

    def ficha_pre_autorizada(self, acao: str, alvo: str = "") -> str | None:
        """Ficha para uma ação que você autorizou de antemão em config/api_keys.json."""
        return self._emitir(f"{acao}:{alvo}") if self.pre_autorizado(acao) else None

    def mostrar(self, pid: str) -> str:
        """Põe o pedido no banner CONFIRMAR do HUD. 'na_tela', 'ocupado' (outro banner aberto) ou 'sem_tela'."""
        p = self._pendentes.get(pid)
        if not p:
            return "nao_existe"
        try:
            from core import confirm
            if confirm._show_cb is None:
                return "sem_tela"
            if confirm.pending_title():
                return "ocupado"
            confirm.request(f"bio-{pid}", f"🧬 {p['titulo']}", p["detalhe"], lambda: self.conceder(pid, "tela do PC"))
            return "na_tela"
        except Exception:
            return "sem_tela"

    def conceder(self, pid: str, origem: str = "painel") -> str:
        """SÓ a interface chama isto (botão do HUD ou do celular). Faz a ação aprovada."""
        with self._lock:
            p = self._pendentes.pop(pid, None)
            fn = self._executores.pop(pid, None)
        if p is None:
            return "Esse pedido não existe mais (já foi respondido ou venceu)."
        if fn is None and p["acao"] in self._fabricas:
            try:
                fn = self._fabricas[p["acao"]](p)
            except Exception:
                fn = None
        self.historico.append({"id": pid, "acao": p["acao"], "alvo": p["alvo"], "resposta": "autorizado",
                               "origem": origem, "ts": time.time()})
        self._gravar()
        _livro(p, "autorizado", origem)
        if fn is None:
            return "Autorizado, mas não sei mais refazer essa ação. Nada foi mudado."
        try:
            return str(fn(self._emitir(f"{p['acao']}:{p['alvo']}")) or "Feito.")
        except Exception as e:
            return f"A ação autorizada falhou: {e}"

    def negar(self, pid: str, origem: str = "painel") -> str:
        with self._lock:
            p = self._pendentes.pop(pid, None)
            self._executores.pop(pid, None)
        if p is None:
            return "Esse pedido não existe mais."
        self.historico.append({"id": pid, "acao": p["acao"], "alvo": p["alvo"], "resposta": "negado",
                               "origem": origem, "ts": time.time()})
        self._gravar()
        _livro(p, "negado", origem)
        return f"Negado: {p['titulo']}. Nada foi mudado."

    def pendentes(self) -> list[dict]:
        with self._lock:
            return sorted(({k: v for k, v in p.items() if k != "tela"} for p in self._pendentes.values()),
                          key=lambda p: p["criado"])

    # ── fichas de uso único ───────────────────────────────────────────────────
    def _emitir(self, escopo: str) -> str:
        ficha = secrets.token_urlsafe(18)
        with self._lock:
            agora = time.time()
            self._fichas = {k: v for k, v in self._fichas.items() if v[1] > agora}
            self._fichas[ficha] = (escopo, agora + VALIDADE_FICHA_S)
        return ficha

    def validar(self, ficha: str | None, escopo: str) -> bool:
        """Confere e GASTA a ficha. Só vale para o escopo exato ('acao:alvo') e dentro da validade."""
        if not ficha:
            return False
        with self._lock:
            v = self._fichas.pop(ficha, None)
        return bool(v and v[0] == escopo and v[1] > time.time())

    def _gravar(self) -> None:
        try:
            with self._lock:
                d = {"pendentes": [{k: v for k, v in p.items() if k != "tela"} for p in self._pendentes.values()],
                     "historico": list(self.historico)}
            gravar_json(self.arquivo, d)
        except Exception:
            pass
        if self.ao_mudar:
            try:
                self.ao_mudar()
            except Exception:
                pass
