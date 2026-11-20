"""
Camada 8 — EVOLUÇÃO: a defesa se avalia e melhora.

    relatorio()      quantos problemas, quantos curados sozinho, tempo até curar, alarmes falsos,
                     pontos fracos (módulos e categorias que mais adoecem) e recomendações
    exercitar()      "vacinas": testes de segurança que rodam numa pasta temporária, longe dos seus
                     arquivos — adultera um arquivo e confere se o DNA percebe, tenta mudar o DNA sem
                     autorização, simula 3 falhas e confere o disjuntor, manda um comando que desliga o
                     firewall e confere o bloqueio, corrompe um JSON e confere se a restauração volta
    ajustar()        alarme falso (você liberou logo depois do isolamento) deixa aquele módulo mais
                     tolerante; problema que se confirmou deixa mais atento
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from biological_core.config import gravar_json, ler_json


class Evolucao:
    def __init__(self, pasta: Path, memoria, isolamento, anomalias, classificador=None):
        self.arquivo = Path(pasta) / "evolucao.json"
        self.memoria = memoria
        self.isolamento = isolamento
        self.anomalias = anomalias
        self.classificador = classificador
        self.estado = ler_json(self.arquivo, {}) or {}

    # ── vacinas ───────────────────────────────────────────────────────────────
    def exercitar(self) -> list[dict]:
        tmp = Path(tempfile.mkdtemp(prefix="jarvis_vacina_"))
        resultados = []
        try:
            for nome, fn in (("dna_percebe_arquivo_alterado", self._v_dna), ("dna_percebe_genoma_adulterado", self._v_genoma),
                             ("dna_recusa_mudanca_sem_autorizacao", self._v_mutacao), ("disjuntor_isola_e_cura", self._v_disjuntor),
                             ("defesa_bloqueia_desligar_firewall", self._v_defesa), ("restauracao_de_json", self._v_json),
                             ("classificador_reconhece_erros", self._v_classificador)):
                t0 = time.perf_counter()
                pasta = tmp / nome
                pasta.mkdir()
                try:
                    ok, det = fn(pasta)
                except Exception as e:
                    ok, det = False, f"{type(e).__name__}: {e}"
                resultados.append({"nome": nome, "ok": bool(ok), "detalhe": det, "ms": round((time.perf_counter() - t0) * 1000, 1)})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        hist = self.estado.setdefault("exercicios", [])
        hist.append({"ts": time.time(), "resultados": resultados})
        del hist[:-10]
        self._gravar()
        return resultados

    @staticmethod
    def _projeto(p: Path) -> Path:
        raiz = p / "proj"
        (raiz / "plugins").mkdir(parents=True)
        (raiz / "plugins" / "teste.py").write_text("PLUGIN = {}\n", encoding="utf-8")
        (raiz / "ui.py").write_text('APP_VERSION  = "vacina"\n', encoding="utf-8")
        return raiz

    def _v_dna(self, p: Path):
        from biological_core.dna.digital_dna import DNA
        from biological_core.dna.integrity_checker import VerificadorIntegridade
        raiz = self._projeto(p)
        dna = DNA(raiz, p / "bio")
        dna.genese()
        (raiz / "plugins" / "teste.py").write_text("PLUGIN = {'mudou': 1}\n", encoding="utf-8")
        r = VerificadorIntegridade(dna).verificar()
        return r["modificados"] == ["plugins/teste.py"], f"modificados: {r['modificados']}"

    def _v_genoma(self, p: Path):
        from biological_core.dna.digital_dna import DNA
        raiz = self._projeto(p)
        dna = DNA(raiz, p / "bio")
        dna.genese()
        g = json.loads(dna.arquivo.read_text(encoding="utf-8"))
        g["arquivos"]["plugins/teste.py"]["sha256"] = "0" * 64
        dna.arquivo.write_text(json.dumps(g), encoding="utf-8")
        s = DNA(raiz, p / "bio").carregar()
        return s == "adulterado", f"situação lida: {s}"

    def _v_mutacao(self, p: Path):
        from biological_core.autorizacao import Autorizacoes
        from biological_core.dna.digital_dna import DNA
        raiz = self._projeto(p)
        dna = DNA(raiz, p / "bio")
        dna.genese()
        r = dna.mutar("ficha-falsa", Autorizacoes(p / "aut.json"), "tentativa")
        return r.startswith("Recusado"), r

    def _v_disjuntor(self, p: Path):
        from biological_core.immune_system.isolation_manager import GerenciadorIsolamento
        relogio = [1000.0]
        g = GerenciadorIsolamento(p / "q.json", essenciais=set(), agora=lambda: relogio[0])
        for _ in range(3):
            g.falha("vacina", "x", "erro simulado")
        bloqueado = g.bloqueio("vacina", "x") is not None
        relogio[0] += 61
        teste_liberado = g.bloqueio("vacina", "x") is None
        curou = g.sucesso("vacina", "x")
        return bloqueado and teste_liberado and curou, f"isolou={bloqueado}, testou={teste_liberado}, curou={curou}"

    def _v_defesa(self, p: Path):
        from biological_core.immune_system.defense_engine import BLOQUEAR, PERMITIR, MotorDefesa
        d = MotorDefesa()
        a = d.validar("executar_comando", {"comando": "powershell Set-MpPreference -DisableRealtimeMonitoring $true"})
        b = d.validar("busca_web", {"consulta": "como desativar o firewall do windows"})
        c = d.validar("terminal", {"comando": "format C: /q"})
        return a.acao == BLOQUEAR and b.acao == PERMITIR and c.acao == BLOQUEAR, f"defender={a.acao}, pesquisa={b.acao}, format={c.acao}"

    def _v_json(self, p: Path):
        from biological_core.immune_system.prevention_engine import Prevencao
        raiz = p / "proj"
        (raiz / "memory").mkdir(parents=True)
        arq = raiz / "memory" / "lista.json"
        arq.write_text('{"itens": [1, 2, 3]}', encoding="utf-8")
        prev = Prevencao(raiz, p / "bio")
        prev.criar_ponto("vacina")
        arq.write_text('{"itens": [1, 2', encoding="utf-8")
        ruins = prev.checar_dados(so_mudados=False)
        boa = prev.ultima_versao_boa("memory/lista.json")
        if not ruins or not boa:
            return False, "não percebeu o JSON quebrado ou não achou versão boa"
        prev.restaurar_arquivo("memory/lista.json", boa[1])
        return json.loads(arq.read_text(encoding="utf-8")) == {"itens": [1, 2, 3]}, "restaurado e conferido"

    def _v_classificador(self, p: Path):
        if self.classificador is None:
            return True, "sem classificador ligado (pulado)"
        casos = {"HTTPSConnectionPool: Max retries exceeded (getaddrinfo failed)": "rede",
                 "Expecting value: line 1 column 1 (char 0)": "json_corrompido",
                 "No module named 'cv2'": "pacote", "'NoneType' object has no attribute 'get'": "bug"}
        erros = [t for t, c in casos.items() if self.classificador.classificar(t)[0] != c]
        return not erros, "todos certos" if not erros else f"errou: {erros}"

    # ── relatório ─────────────────────────────────────────────────────────────
    def relatorio(self, dias: int = 7, aprendizado: dict | None = None, extra: dict | None = None) -> dict:
        desde = time.time() - dias * 86400
        est = self.memoria.estatisticas(desde)
        ex = (self.estado.get("exercicios") or [{}])[-1]
        falhos = [r for r in ex.get("resultados", []) if not r["ok"]]
        falsos = {l["chave"].split("|")[0] for l in self.isolamento.liberacoes
                  if l["ts"] >= desde and l["por"] == "usuario" and l["isolado_s"] < 600}
        taxa = est["automaticos"] / est["resolvidos"] if est["resolvidos"] else None
        rec = self.recomendacoes(est, falhos, falsos, extra or {})
        nota = 100
        nota -= 15 * len(falhos)
        nota -= min(20, 4 * est["abertos"])
        nota -= min(15, 5 * len(falsos))
        if taxa is not None and taxa < 0.5:
            nota -= 10
        return {"dias": dias, **est, "taxa_automatica": round(taxa, 2) if taxa is not None else None,
                "alarmes_falsos": sorted(falsos), "exercicios": ex.get("resultados", []), "exercicios_ts": ex.get("ts"),
                "recomendacoes": rec, "nota_defesa": max(0, nota), "aprendizado": aprendizado or {}}

    def recomendacoes(self, est: dict, falhos: list, falsos: set, extra: dict) -> list[str]:
        r = []
        for f in falhos:
            r.append(f"A vacina '{f['nome']}' falhou ({f['detalhe']}): essa defesa precisa de conserto.")
        desde = time.time() - 7 * 86400
        incs = self.memoria.incidentes(desde=desde, limite=500)
        por = {}
        for i in incs:
            por.setdefault((i["modulo"], i["categoria"]), 0)
            por[(i["modulo"], i["categoria"])] += 1
        for (mod, cat), n in sorted(por.items(), key=lambda x: -x[1]):
            if cat in ("rede", "externo") and n >= 3:
                r.append(f"'{mod}' adoeceu {n} vezes por internet/serviço esta semana: vale ele guardar o último resultado para funcionar offline.")
            elif cat == "timeout" and n >= 3:
                r.append(f"'{mod}' travou {n} vezes: o tempo dele já foi aumentado; se continuar, o serviço dele está lento.")
            elif cat in ("bug", "sintaxe") and n >= 2:
                r.append(f"'{mod}' teve {n} erros de código: diga 'Jarvis, analisa seus erros' para o auto-melhoria propor a correção.")
        for p in self.memoria.padroes()[:3]:
            if p["hora_tipica"] is not None:
                r.append(f"O erro de '{p['modulo']}' ({p['categoria']}) volta em {p['dias']} dias diferentes, quase sempre por volta das "
                         f"{p['hora_tipica']}h: vale ver o que roda nesse horário.")
        for mod in sorted(falsos):
            r.append(f"Você liberou '{mod}' logo depois do isolamento: ele ficou mais tolerante a falhas.")
        if est["abertos"] >= 3:
            r.append(f"Há {est['abertos']} problemas abertos; diga 'Jarvis, mostra os incidentes'.")
        if extra.get("dias_sem_ponto", 0) >= 3:
            r.append(f"Faz {extra['dias_sem_ponto']} dias sem ponto de restauração dos dados.")
        for p in extra.get("pacotes_essenciais", []):
            r.append(f"Pacote essencial faltando: {p} (pip install {p}).")
        return r[:10]

    def ajustar(self) -> list[str]:
        """Aplica o aprendizado dos alarmes falsos nos limites (uma vez por liberação)."""
        ate = self.estado.get("ajustado_ate", 0)
        feitos = []
        for l in list(self.isolamento.liberacoes):
            if l["ts"] <= ate or l["por"] != "usuario" or l["isolado_s"] >= 600:
                continue
            mod = l["chave"].split("|")[0]
            v = self.isolamento.ajustar_limiar(mod, alarme_falso=True)
            self.anomalias.ajustar(mod, alarme_falso=True)
            feitos.append(f"{mod}: tolera {v} falhas seguidas")
        if self.isolamento.liberacoes:
            self.estado["ajustado_ate"] = max(l["ts"] for l in self.isolamento.liberacoes)
        self._gravar()
        return feitos

    def _gravar(self) -> None:
        try:
            gravar_json(self.arquivo, self.estado)
        except Exception:
            pass
