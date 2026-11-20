"""
Camada 4 — ISOLAMENTO: impede que uma falha se espalhe e que o JARVIS fique preso nela.

Isola só o PEDAÇO doente: no `rastreio`, se só a ação "consultar" quebra, "listar" e "guardar"
continuam funcionando ("rastreio|consultar" fica isolado, "rastreio|*" não).

Disjuntor (como o da sua casa), por ferramenta+ação:
    fechado      tudo normal
    aberto       3 falhas seguidas (o limite se adapta): ninguém chama até o tempo de descanso passar
                 — 1 min, depois 5 min, 30 min e 2 h se continuar falhando
    meio aberto  passou o descanso: UMA chamada de teste é liberada. Deu certo → fecha (curado).
                 Falhou → abre de novo, com descanso maior.

Quarentena: isolamento sem prazo (ameaça, integridade, ou um reparo que precisa de você).
Sai quando o teste de recuperação passa ou quando você diz "libera".
Os ESSENCIAIS (organismo, catálogo, modos, auto-melhoria…) nunca são isolados.
Tudo fica salvo em memory/biological/quarentena.json e sobrevive a reinício.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from biological_core.config import ESSENCIAIS, duracao, gravar_json, ler_json

DESCANSOS = (60, 300, 1800, 7200)
LIMIAR_PADRAO = 3


def chave(modulo: str, acao: str | None = None) -> str:
    return f"{modulo}|{acao or '*'}"


class GerenciadorIsolamento:
    def __init__(self, arquivo: Path, essenciais=ESSENCIAIS, agora: Callable[[], float] = time.time):
        self.arquivo = Path(arquivo)
        self.essenciais = set(essenciais)
        self.agora = agora
        self._lock = threading.RLock()
        d = ler_json(self.arquivo, {}) or {}
        self.disjuntores: dict[str, dict] = d.get("disjuntores", {})
        self.quarentena: dict[str, dict] = d.get("quarentena", {})
        self.limiares: dict[str, int] = d.get("limiares", {})
        self.liberacoes: deque = deque(d.get("liberacoes", []), maxlen=100)
        self.curas = int(d.get("curas", 0))

    # ── consulta (portão) ─────────────────────────────────────────────────────
    def bloqueio(self, modulo: str, acao: str | None) -> str | None:
        """Mensagem para o modelo se a chamada está isolada; None se pode seguir."""
        if modulo in self.essenciais:
            return None
        agora = self.agora()
        with self._lock:
            for k in (chave(modulo), chave(modulo, acao)):
                q = self.quarentena.get(k)
                if q:
                    return (f"[ISOLADO] '{k.replace('|*', '').replace('|', ' → ')}' está em quarentena há "
                            f"{duracao(agora - q['desde'])}: {q['motivo']}. Diga ao usuário em uma frase que essa parte "
                            "está isolada para proteger o JARVIS e que ele pode dizer 'libera' se quiser. Não chame de novo agora.")
            for k in (chave(modulo, acao), chave(modulo)):
                d = self.disjuntores.get(k)
                if not d or d["estado"] == "fechado":
                    continue
                if d["estado"] == "aberto" and agora < d["aberto_ate"]:
                    return (f"[DESCANSANDO] '{modulo}' falhou {d['falhas']} vezes seguidas ({d['motivo']}). "
                            f"O JARVIS testa de novo em {duracao(d['aberto_ate'] - agora)}. Diga isso ao usuário em uma "
                            "frase e não chame de novo agora.")
                if d["estado"] == "aberto":                 # descanso acabou → meio aberto
                    d["estado"], d["teste_desde"] = "meio_aberto", agora
                    self._gravar()
                    return None                              # esta é a chamada de teste
                if d["estado"] == "meio_aberto":
                    if agora - d.get("teste_desde", 0) > 120:   # o teste sumiu (travou): libera outro
                        d["teste_desde"] = agora
                        return None
                    return f"[TESTANDO] '{modulo}' está sendo testado agora depois de falhar. Tente daqui a pouco."
        return None

    def estado_de(self, modulo: str, acao: str | None = None) -> str:
        with self._lock:
            if chave(modulo) in self.quarentena or chave(modulo, acao) in self.quarentena:
                return "quarentena"
            d = self.disjuntores.get(chave(modulo, acao)) or self.disjuntores.get(chave(modulo))
            return d["estado"] if d else "fechado"

    # ── resultados ────────────────────────────────────────────────────────────
    def sucesso(self, modulo: str, acao: str | None) -> bool:
        """True se esta chamada CUROU um disjuntor (estava aberto/meio aberto e agora deu certo)."""
        curou = False
        with self._lock:
            for k in (chave(modulo, acao), chave(modulo)):
                d = self.disjuntores.get(k)
                if not d:
                    continue
                if d["estado"] != "fechado":
                    curou = True
                    self.curas += 1
                    d.update(estado="fechado", falhas=0, curado_em=self.agora())
                else:
                    d["falhas"] = 0
                    if self.agora() - d.get("ultima_abertura", 0) > 86400:
                        d["aberturas"] = 0
            if curou:
                self._gravar()
        return curou

    def falha(self, modulo: str, acao: str | None, motivo: str, categoria: str = "") -> bool:
        """Conta a falha. True se o disjuntor ACABOU de abrir."""
        if modulo in self.essenciais:
            return False
        agora = self.agora()
        k = chave(modulo, acao)
        with self._lock:
            d = self.disjuntores.setdefault(k, {"estado": "fechado", "falhas": 0, "aberturas": 0, "aberto_ate": 0,
                                                "motivo": "", "categoria": "", "primeira_falha": agora})
            if d["estado"] == "fechado" and d["falhas"] and agora - d.get("ultima_falha", agora) > 600:
                d["falhas"] = 0                              # falhas espalhadas no dia não contam como "seguidas"
            d["falhas"] += 1
            d.update(ultima_falha=agora, motivo=motivo[:160], categoria=categoria)
            limiar = self.limiares.get(modulo, LIMIAR_PADRAO)
            if d["estado"] == "meio_aberto" or (d["estado"] == "fechado" and d["falhas"] >= limiar):
                self._abrir(d, agora)
                self._gravar()
                return True
            return False

    def _abrir(self, d: dict, agora: float) -> None:
        d["aberturas"] = d.get("aberturas", 0) + 1
        d.update(estado="aberto", aberto_ate=agora + DESCANSOS[min(d["aberturas"], len(DESCANSOS)) - 1],
                 ultima_abertura=agora)

    def abrir(self, modulo: str, acao: str | None, motivo: str, categoria: str = "") -> bool:
        """Abre o disjuntor na hora (tratamento 'isolar_temporario' / 'esperar_rede')."""
        if modulo in self.essenciais:
            return False
        with self._lock:
            d = self.disjuntores.setdefault(chave(modulo, acao), {"estado": "fechado", "falhas": 0, "aberturas": 0,
                                                                  "aberto_ate": 0, "motivo": "", "categoria": categoria})
            if d["estado"] != "aberto":
                d["motivo"] = motivo[:160]
                self._abrir(d, self.agora())
                self._gravar()
            return True

    def meio_abrir(self, modulo: str, acao: str | None = None) -> int:
        """Encurta o descanso: a próxima chamada já é o teste (a internet voltou, por exemplo)."""
        n = 0
        with self._lock:
            for k, d in self.disjuntores.items():
                if k.split("|")[0] == modulo and (acao is None or k == chave(modulo, acao)) and d["estado"] == "aberto":
                    d["aberto_ate"] = self.agora()
                    n += 1
            if n:
                self._gravar()
        return n

    # ── quarentena ────────────────────────────────────────────────────────────
    def isolar(self, modulo: str, acao: str | None, motivo: str, incidente: int | None = None, por: str = "imune") -> bool:
        if modulo in self.essenciais:
            return False
        with self._lock:
            self.quarentena[chave(modulo, acao)] = {"motivo": motivo[:200], "desde": self.agora(), "incidente": incidente, "por": por}
            self._gravar()
        return True

    def liberar(self, modulo: str, acao: str | None = None, por: str = "usuario") -> list[str]:
        """Tira da quarentena e fecha os disjuntores. Liberado logo depois de isolar conta como alarme falso."""
        agora = self.agora()
        soltos = []
        with self._lock:
            for k in list(self.quarentena):
                if k.split("|")[0] == modulo and (acao is None or k == chave(modulo, acao)):
                    q = self.quarentena.pop(k)
                    soltos.append(k)
                    self.liberacoes.append({"chave": k, "ts": agora, "por": por, "isolado_s": agora - q["desde"]})
            for k, d in self.disjuntores.items():
                if k.split("|")[0] == modulo and (acao is None or k == chave(modulo, acao)) and d["estado"] != "fechado":
                    soltos.append(k)
                    self.liberacoes.append({"chave": k, "ts": agora, "por": por,
                                            "isolado_s": agora - d.get("ultima_abertura", agora)})
                    d.update(estado="fechado", falhas=0)
            if soltos:
                self._gravar()
        return sorted(set(soltos))

    def alarmes_falsos(self, modulo: str, janela_s: float = 600) -> int:
        return sum(1 for l in self.liberacoes if l["chave"].split("|")[0] == modulo and l["por"] == "usuario"
                   and l["isolado_s"] < janela_s)

    def ajustar_limiar(self, modulo: str, alarme_falso: bool) -> int:
        with self._lock:
            v = self.limiares.get(modulo, LIMIAR_PADRAO)
            v = min(6, v + 1) if alarme_falso else max(2, v - 1)
            self.limiares[modulo] = v
            self._gravar()
            return v

    def listar(self) -> list[dict]:
        agora = self.agora()
        with self._lock:
            out = [{"chave": k, "tipo": "quarentena", "motivo": q["motivo"], "ha": duracao(agora - q["desde"]),
                    "incidente": q.get("incidente")} for k, q in self.quarentena.items()]
            out += [{"chave": k, "tipo": d["estado"], "motivo": d["motivo"], "falhas": d["falhas"],
                     "volta_em": duracao(max(0, d["aberto_ate"] - agora)) if d["estado"] == "aberto" else "testando"}
                    for k, d in self.disjuntores.items() if d["estado"] != "fechado"]
        return out

    def _gravar(self) -> None:
        try:
            gravar_json(self.arquivo, {"disjuntores": self.disjuntores, "quarentena": self.quarentena,
                                       "limiares": self.limiares, "liberacoes": list(self.liberacoes), "curas": self.curas})
        except Exception:
            pass
