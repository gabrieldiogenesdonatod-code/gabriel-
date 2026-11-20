"""
Cérebro central — JARVIS BRAIN.

Coordena o organismo pelo sistema nervoso:
    incidente.novo      → pede à célula analista as hipóteses de causa, escolhe o reparo PERMITIDO
                          (motor de decisão) e dá a ordem à célula reparadora
    reparo.resultado    → avalia: deu certo? aprende. Falhou? tenta o próximo (até 3), depois chama você
    sintoma.recuperado  → o módulo voltou a funcionar depois do reparo: confirma o sucesso, fecha o
                          incidente com a causa confirmada e ensina o classificador
    sintoma.falha       → o mesmo erro voltou durante a observação: o reparo não resolveu

Memória de longo prazo: o placar dos tratamentos e o classificador ficam em
memory/biological/cerebro.json; incidentes, decisões e anticorpos na memória imunológica.
Ele sempre explica a decisão: "Causa mais provável: a internet caiu (91%; 3 ferramentas sem internet
ao mesmo tempo). Escolhi 'esperar_rede': funcionou 8 de 9 vezes…"
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from biological_core.brain.decision_engine import MAPA, MotorDecisao
from biological_core.brain.reasoning import ClassificadorErros, MotorHipoteses
from biological_core.config import AUTORIZACAO, autonomia, gravar_json, ler_json
from biological_core.nervous_system.communication import Orgao
from biological_core.nervous_system.event_bus import ALTA, NORMAL
from biological_core.regeneration.repair_manager import CATALOGO

MAX_TENTATIVAS = 3
OBSERVACAO_S = 24 * 3600
CAUSA_PARA_CATEGORIA = {"internet_caiu": "rede", "servico_externo_fora": "externo", "dados_corrompidos": "json_corrompido",
                        "pacote_faltando": "pacote", "chave_invalida": "chave", "falta_de_recurso": "recurso",
                        "bug_no_plugin": "bug", "mudanca_no_codigo": "bug", "codigo_quebrado": "sintaxe",
                        "arquivo_sumiu": "arquivo", "sem_permissao": "permissao", "sobrecarga": "timeout"}


class Cerebro(Orgao):
    nome = "cerebro"

    def __init__(self, bus, org, pasta: Path, semente: int | None = None):
        super().__init__(bus)
        self.org = org
        self.arquivo = Path(pasta) / "cerebro.json"
        d = ler_json(self.arquivo, {}) or {}
        self.classificador = ClassificadorErros(d.get("classificador"))
        self.hipoteses = MotorHipoteses()
        self.decisao = MotorDecisao(d.get("placar"), semente)
        self.metricas = d.get("metricas", {"decisoes": 0, "sucessos": 0, "fracassos": 0})
        self.tentativas: dict[int, list[str]] = {}
        self.pendentes: dict[tuple[str, str], dict] = {}
        self.situacao: dict = {"ultima_decisao": None, "febre": False, "saude": None}
        self._lock = threading.RLock()
        self.ouvir("incidente.novo", lambda ev: self.tratar(ev.dados))
        self.ouvir("reparo.resultado", self._resultado)
        self.ouvir("sintoma.recuperado", self._recuperou)
        self.ouvir("sintoma.falha", self._recaida)
        self.ouvir("saude.mudou", lambda ev: self.situacao.update(saude=ev.dados))
        self.oferecer_ajuda("classificar", lambda d: self.classificador.classificar(d.get("texto", "")))

    # ── decidir ───────────────────────────────────────────────────────────────
    def tratar(self, inc: dict, motivo: str = "") -> str | None:
        with self._lock:
            iid = int(inc["id"])
            tent = self.tentativas.setdefault(iid, [])
            hip = next(iter(self.pedir_ajuda("investigar", inc)), None) or self.hipoteses.avaliar(
                {"categoria": inc.get("categoria"), "acao": inc.get("acao"), "modulo": inc.get("modulo")})
            anticorpo = self.org.memoria.reconhecer(inc.get("impressao") or "") or {}
            excluir = set(tent) | self.org.memoria.tratamentos_que_falharam(inc.get("impressao") or "")
            if len(tent) >= MAX_TENTATIVAS:
                excluir |= set(CATALOGO) - {"pedir_intervencao"}
            dec = self.decisao.decidir(inc, hip, excluir, autonomia(), anticorpo.get("placar"), anticorpo.get("tratamento_bom"))
            if dec.tratamento == "pedir_intervencao" and "pedir_intervencao" in tent:
                return None                                    # já está esperando você
            tent.append(dec.tratamento)
            did = self.org.memoria.registrar_decisao(iid, dec.tratamento, dec.explicacao, dec.hipoteses)
            self.metricas["decisoes"] += 1
            causa = hip[0]["causa"] if hip else None
            self.situacao["ultima_decisao"] = {"incidente": iid, "modulo": inc.get("modulo"), "tratamento": dec.tratamento,
                                               "explicacao": dec.explicacao, "ts": time.time()}
            self.org.memoria.atualizar(iid, estado="tratando", tratamento=dec.tratamento, **({"causa": causa} if causa else {}))
        self.enviar("ordem.reparar", {"incidente": inc, "tratamento": dec.tratamento, "decisao": did,
                                      "explicacao": dec.explicacao, "causa": causa, "hipoteses": dec.hipoteses}, ALTA)
        return dec.tratamento

    # ── avaliar ───────────────────────────────────────────────────────────────
    def _resultado(self, ev) -> None:
        r = ev.dados
        inc, t, estado, did = r["incidente"], r["tratamento"], r["estado"], r.get("decisao")
        if estado == "resolvido":
            self._sucesso(inc, t, did, r.get("mensagem", "reparo testado e aprovado"))
        elif estado == "falhou":
            self._fracasso(inc, t, did, r.get("mensagem", ""))
            self.tratar(self.org.memoria.incidente(inc["id"]) or inc, "o tratamento anterior falhou")
        elif estado == "pulado":
            self.tratar(self.org.memoria.incidente(inc["id"]) or inc, "tratamento pulado")
        elif estado in ("aplicado", "informado"):
            with self._lock:
                self.pendentes[(inc["modulo"], inc.get("acao") or "*")] = {"ts": time.time(), "inc": inc, "t": t, "did": did}
                self.org.observando.add(inc["modulo"])
            novo = "aguardando_humano" if estado == "informado" else ("observando" if t == "observar" else "isolado")
            self.org.memoria.atualizar(inc["id"], estado=novo)
        elif estado in ("aguardando_autorizacao", "aguardando_humano"):
            self.org.memoria.atualizar(inc["id"], estado=estado)

    def _recuperou(self, ev) -> None:
        mod, acao = ev.dados.get("modulo"), ev.dados.get("acao") or "*"
        with self._lock:
            p = self.pendentes.pop((mod, acao), None) or self.pendentes.pop((mod, "*"), None)
            if not any(k[0] == mod for k in self.pendentes):
                self.org.observando.discard(mod)
        if p:
            self._sucesso(p["inc"], p["t"], p["did"], "voltou a funcionar depois do tratamento")
            return
        for inc in self.org.memoria.abertos():             # curou sozinho (o disjuntor testou e passou)
            if inc["modulo"] == mod and inc["acao"] in (acao, "*") and inc["categoria"] not in ("integridade",):
                self.org.memoria.fechar(inc["id"], "voltou a funcionar sozinho", causa=inc.get("causa"))
                self.org.saude.registrar_recuperacao()
                self.enviar("incidente.resolvido", {"id": inc["id"], "modulo": mod, "como": "sozinho"}, NORMAL)

    def _recaida(self, ev) -> None:
        s = ev.dados
        with self._lock:
            chave = next((k for k in ((s.get("modulo"), s.get("acao") or "*"), (s.get("modulo"), "*")) if k in self.pendentes), None)
            p = self.pendentes.get(chave) if chave else None
            if not p or p["inc"].get("impressao") != s.get("impressao") or time.time() - p["ts"] < 2:
                return
            self.pendentes.pop(chave, None)
        self._fracasso(p["inc"], p["t"], p["did"], "o mesmo erro voltou")
        inc = self.org.memoria.incidente(p["inc"]["id"])
        if inc and inc["estado"] not in ("resolvido",):
            self.tratar(inc, "o mesmo erro voltou")

    def _causa_confirmada(self, inc: dict, t: str) -> str | None:
        fontes = [c for c, ts in MAPA.items() if t in ts]
        atual = inc.get("causa")
        if atual in fontes:
            return atual
        return fontes[0] if len(fontes) == 1 else atual

    def _sucesso(self, inc: dict, t: str, did, como: str) -> None:
        cat = inc.get("categoria") or "desconhecida"
        causa = self._causa_confirmada(inc, t)
        self.decisao.aprender(cat, t, True)
        if inc.get("impressao"):
            self.org.memoria.registrar_tratamento(inc["impressao"], t, True)
        if did:
            self.org.memoria.resultado_decisao(did, "sucesso")
        humano = CATALOGO[t].nivel == AUTORIZACAO or CATALOGO[t].notifica if t in CATALOGO else False
        self.org.memoria.fechar(inc["id"], como, causa=causa, tratamento=t, humano=humano)
        texto = f"{inc.get('tipo', '')} {inc.get('mensagem', '')}"
        aprender_como = cat if cat != "desconhecida" else CAUSA_PARA_CATEGORIA.get(causa or "")
        if aprender_como:
            self.classificador.aprender(texto, aprender_como)
        self.metricas["sucessos"] += 1
        self.tentativas.pop(int(inc["id"]), None)
        self.org.saude.registrar_recuperacao()
        self.org.imune.isolamento.liberar(inc["modulo"], None if inc.get("acao") in (None, "*") else inc["acao"], por="regeneracao")
        self.enviar("incidente.resolvido", {"id": inc["id"], "modulo": inc["modulo"], "tratamento": t, "causa": causa, "como": como}, NORMAL)
        self.salvar()

    def _fracasso(self, inc: dict, t: str, did, motivo: str) -> None:
        self.decisao.aprender(inc.get("categoria") or "desconhecida", t, False)
        if inc.get("impressao"):
            self.org.memoria.registrar_tratamento(inc["impressao"], t, False)
        if did:
            self.org.memoria.resultado_decisao(did, f"falhou: {motivo}"[:200])
        self.metricas["fracassos"] += 1
        self.salvar()

    # ── manutenção e consulta ─────────────────────────────────────────────────
    def manutencao(self) -> int:
        """Observação que passou de 24 h sem o módulo ser usado: para de esperar (sem contar como sucesso)."""
        limite = time.time() - OBSERVACAO_S
        with self._lock:
            velhos = [k for k, p in self.pendentes.items() if p["ts"] < limite]
            for k in velhos:
                self.pendentes.pop(k, None)
                self.org.observando.discard(k[0])
        return len(velhos)

    def explicar(self, iid: int) -> str:
        inc = self.org.memoria.incidente(iid)
        if not inc:
            return f"Não achei o incidente {iid}."
        linhas = [f"Incidente {iid} — {inc['modulo']} ({inc['categoria']}, gravidade {inc['gravidade']}, {inc['ocorrencias']}×): "
                  f"{inc['mensagem'][:160]}. Estado: {inc['estado']}."]
        for d in reversed(self.org.memoria.decisoes(10, iid)):
            linhas.append(f"• {d['explicacao']}" + (f" → {d['resultado']}" if d.get("resultado") else " → em andamento"))
        prot = (inc.get("detalhes") or {}).get("protocolo")
        if prot:
            linhas.append("Protocolo: " + " · ".join(f"{p['passo']}: {p['detalhe']}" for p in prot.get("passos", [])[-4:]))
        return "\n".join(linhas)

    def aprendizado(self) -> dict:
        m = self.metricas
        total = m["sucessos"] + m["fracassos"]
        return {"classificador": self.classificador.estado(), "tratamentos": self.decisao.resumo()[:12],
                "decisoes": m["decisoes"], "acerto": round(m["sucessos"] / total, 2) if total else None,
                "em_observacao": [f"{k[0]}|{k[1]}: {p['t']}" for k, p in self.pendentes.items()]}

    def salvar(self) -> None:
        try:
            gravar_json(self.arquivo, {"classificador": self.classificador.exportar(), "placar": self.decisao.placar,
                                       "metricas": self.metricas})
        except Exception:
            pass
