"""
Motor de decisão do cérebro: escolhe o reparo, dentro do que é PERMITIDO, e aprende com o resultado.

1. Regras: cada causa provável aponta tratamentos (internet caiu → esperar a rede; dados
   corrompidos → restaurar o JSON; bug → recarregar / pedir correção ao auto-melhoria…).
2. Permissão: o nível de autonomia (config "bio_autonomia") e o nível de cada tratamento filtram
   o que pode. Tratamento que já falhou 2 vezes nesse mesmo erro (memória imunológica) sai da lista.
3. Experiência (amostragem de Thompson, moderada): cada tratamento tem um placar de sucessos e falhas
   por tipo de problema e por erro específico (que vale o dobro). A nota de cada opção é a relevância
   para a causa × a chance estimada de funcionar (média Beta), mais um pequeno sorteio Beta para ainda
   testar opções novas de vez em quando, menos o custo (pedir para você custa mais que fazer algo
   seguro sozinho). Sem experiência ele segue a causa mais provável; com experiência, o que funcionou.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field

from biological_core.config import AUTORIZACAO, SEGURA
from biological_core.regeneration.repair_manager import CATALOGO

MAPA = {
    "internet_caiu": ["esperar_rede", "isolar_temporario"],
    "servico_externo_fora": ["isolar_temporario", "esperar_rede", "observar"],
    "mudanca_no_codigo": ["recarregar_modulo", "sugerir_correcao", "restaurar_codigo"],
    "codigo_quebrado": ["restaurar_codigo", "sugerir_correcao"],
    "edicao_no_codigo": ["observar"],
    "protecao_enfraquecida": ["pedir_intervencao"],
    "dados_corrompidos": ["restaurar_json", "pedir_intervencao"],
    "pacote_faltando": ["informar_pacote"],
    "chave_invalida": ["pedir_chave"],
    "falta_de_recurso": ["reflexo_memoria", "avisar_recurso", "isolar_temporario"],
    "bug_no_plugin": ["sugerir_correcao", "recarregar_modulo", "isolar_temporario"],
    "parametro_ruim": ["observar", "sugerir_correcao"],
    "sobrecarga": ["aumentar_limite", "isolar_temporario"],
    "arquivo_sumiu": ["recriar_pasta", "pedir_intervencao"],
    "sem_permissao": ["observar", "pedir_intervencao"],
    "arquivo_vital_alterado": ["pedir_intervencao"],
    "versao_nova": ["pedir_intervencao"],
    "vazamento_memoria": ["reflexo_memoria", "avisar_recurso"],
    "travamento_interno": ["reanimar_orgao", "pedir_intervencao"],
}
SO_OBSERVAR = {"observar", "isolar_temporario", "esperar_rede", "pedir_chave", "informar_pacote", "sugerir_correcao",
               "avisar_recurso", "pedir_intervencao", "reanimar_orgao"}


@dataclass
class Decisao:
    tratamento: str
    explicacao: str
    hipoteses: list = field(default_factory=list)
    alternativas: list = field(default_factory=list)


class MotorDecisao:
    def __init__(self, placar: dict | None = None, semente: int | None = None):
        self.placar: dict[str, list[int]] = dict(placar or {})       # "categoria|tratamento" → [sucessos, falhas]
        self.rng = random.Random(semente)

    @staticmethod
    def custo(t: str) -> float:
        """Chamar você "sem plano" é o último recurso; pedir o seu sim para um reparo concreto custa menos."""
        tr = CATALOGO.get(t)
        if tr is None:
            return 1.0
        if t == "pedir_intervencao":
            return 0.2
        if t == "sugerir_correcao":
            return 0.06                                      # depende de você conversar com o auto-melhoria
        if tr.nivel == AUTORIZACAO:
            return 0.08
        return 0.02 if tr.notifica else 0.0

    @staticmethod
    def permitido(t: str, autonomia: str) -> bool:
        tr = CATALOGO.get(t)
        if tr is None or tr.nivel not in (SEGURA, AUTORIZACAO):
            return False
        return autonomia != "observar" or t in SO_OBSERVAR or tr.nivel == AUTORIZACAO

    def decidir(self, inc: dict, hipoteses: list[dict], excluir: set[str] | None = None, autonomia: str = "normal",
                placar_erro: dict | None = None, conhecido: str | None = None) -> Decisao:
        relev: dict[str, float] = defaultdict(float)
        for h in hipoteses[:4]:
            for i, t in enumerate(MAPA.get(h["causa"], [])):
                relev[t] += h["prob"] * (1.0 - 0.35 * i)
        if conhecido and conhecido in CATALOGO:
            relev[conhecido] += 0.5
        excluir = set(excluir or ())
        cands = [t for t in relev if t not in excluir and self.permitido(t, autonomia)]
        top = hipoteses[0] if hipoteses else {"descricao": "causa desconhecida", "prob": 0.0, "causa": "?"}
        if not cands:
            return Decisao("pedir_intervencao", f"Já tentei o que sabia para '{top['descricao']}' (ou não tenho permissão): "
                                                "isolo e chamo você.", hipoteses[:3], [])
        cat = inc.get("categoria") or "desconhecida"
        placar_erro = placar_erro or {}
        notas = []
        for t in cands:
            s_c, f_c = self.placar.get(f"{cat}|{t}", [0, 0])
            s_i, f_i = placar_erro.get(t, [0, 0])
            a, b = 2 + s_c + 2 * s_i, 2 + f_c + 2 * f_i
            media = a / (a + b)
            theta = self.rng.betavariate(a, b)                   # o sorteio de Thompson: um pouco de exploração
            u = relev[t] * (0.35 + 0.65 * media) + 0.15 * (theta - media) - self.custo(t)
            notas.append((u, t, s_c + s_i, f_c + f_i))
        notas.sort(reverse=True)
        _u, escolha, s, f = notas[0]
        if conhecido == escolha:
            motivo = "é o anticorpo deste erro: já resolveu antes"
        elif s + f:
            motivo = f"funcionou {s} de {s + f} vez(es) em problemas de '{cat}'"
        else:
            motivo = "ainda não tenho experiência com isso; é o tratamento mais indicado e seguro para essa causa"
        exp = (f"Causa mais provável: {top['descricao']} ({top['prob']:.0%}"
               + (f"; {', '.join(top.get('evidencias', [])[:2])}" if top.get("evidencias") else "") + "). "
               f"Escolhi '{escolha}' ({CATALOGO[escolha].descricao}): {motivo}.")
        return Decisao(escolha, exp, hipoteses[:3], [t for _u, t, _s, _f in notas[1:4]])

    def aprender(self, categoria: str, tratamento: str, sucesso: bool) -> None:
        k = f"{categoria or 'desconhecida'}|{tratamento}"
        s, f = self.placar.get(k, [0, 0])
        self.placar[k] = [s + int(sucesso), f + int(not sucesso)]

    def resumo(self) -> list[dict]:
        out = []
        for k, (s, f) in self.placar.items():
            cat, t = k.split("|", 1)
            out.append({"categoria": cat, "tratamento": t, "sucessos": s, "falhas": f,
                        "taxa": round(s / (s + f), 2) if s + f else None})
        return sorted(out, key=lambda x: -(x["sucessos"] + x["falhas"]))
