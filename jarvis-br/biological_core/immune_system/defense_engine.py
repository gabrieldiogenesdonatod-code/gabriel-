"""
Camada 3 — DEFESA: valida cada comando antes de a ferramenta rodar.

Regras, da mais forte para a mais leve:
    1. proteção do sistema  — desligar antivírus, Defender, firewall, SmartScreen ou UAC: BLOQUEIA sempre
    2. destruição total     — "format C:", "rm -rf /", apagar o disco inteiro: BLOQUEIA sempre
    3. arquivos vitais      — apagar/mover o genoma, a chave do DNA, as células-tronco ou a memória imune: BLOQUEIA
    4. anti-laço            — a mesma ferramenta chamada demais em 1 minuto (o modelo preso num laço): PAUSA
    5. pasta do sistema     — apagar/mover algo em C:\\Windows, System32, Program Files, /etc…: pede o SEU sim
    6. módulo comprometido  — plugin com arquivo alterado e falhando pedindo algo perigoso: pede o SEU sim

As regras 1, 2 e 5 só olham ferramentas que EXECUTAM coisas (nome de comando/controle, ou parâmetro
"comando", "script"…): pesquisar "como desativar o firewall" na internet continua livre.
Plugins saudáveis fazendo coisas normais não sentem diferença nenhuma.
"""

from __future__ import annotations

import re
import time
from collections import Counter, deque
from dataclasses import dataclass

PERMITIR, CONFIRMAR, BLOQUEAR = "permitir", "confirmar", "bloquear"

_EXECUTA_NOME = re.compile(r"(comando|terminal|shell|powershell|\bcmd|execut|controle|sistema|automac|script|agente|arquivo|pasta|organiz|limp)", re.I)
_EXECUTA_PARAM = {"comando", "command", "cmd", "script", "codigo", "code", "shell", "powershell", "caminho", "path", "arquivo", "pasta"}
_SINTAXE_CMD = re.compile(r"(powershell|cmd(\.exe)?\s*/c|netsh\s|\bsc(\.exe)?\s+(stop|config|delete)|reg(\.exe)?\s+(add|delete)|"
                          r"set-mppreference|bcdedit|vssadmin|wmic\s)", re.I)
_DESLIGAR = re.compile(r"(desativ|deslig|desabilit|disable|\bstop\b|\bparar\b|turn\s*off|\bkill\b|set-mppreference|"
                       r"DisableRealtimeMonitoring|advfirewall\s+set|state\s+off|sc(\.exe)?\s+(stop|config))", re.I)
_PROTECAO = re.compile(r"(antiv[ií]rus|defender|windefend|firewall|smartscreen|\buac\b|controle de conta|"
                       r"seguran[çc]a do windows|msmpeng|wscsvc|mppreference|realtimemonitoring|advfirewall|mpcmdrun|"
                       r"enablelua|tamper ?protection)", re.I)
_DESTRUICAO = re.compile(r"(rm\s+-rf\s+/(\s|$|\*)|format(\.com)?\s+[a-z]:|del(ete)?\s+/[sqf][^\n]*[a-z]:\\\*?(\s|$)|"
                         r"remove-item\s[^\n]*-recurse[^\n]*[a-z]:\\\*?(\s|$)|mkfs\.|dd\s+if=[^\n]*of=/dev/(sd|nvme|hd)|"
                         r"vssadmin\s+delete\s+shadows|cipher\s+/w:)", re.I)
_PERIGOSO = re.compile(r"(apag|delet|exclu|remov|format|destru|wipe|erase|shred|desinstal|uninstall|mover|move\b|sobrescrev|overwrite)", re.I)
_SISTEMA = re.compile(r"([a-z]:\\windows|system32|syswow64|program files|programdata\\microsoft|/etc/|/usr/|/bin/|/boot/|/sbin/|/system/)", re.I)
_VITAIS = re.compile(r"(genoma\.json|\.chave_dna|celulas_tronco\.zip|imunidade\.db)", re.I)


@dataclass
class Veredito:
    acao: str = PERMITIR
    motivo: str = ""
    regra: str = ""
    risco: float = 0.0

    @property
    def permitido(self) -> bool:
        return self.acao == PERMITIR


def _texto(params, limite: int = 4000) -> str:
    partes = []

    def andar(v, prof=0):
        if prof > 4 or sum(len(p) for p in partes) > limite:
            return
        if isinstance(v, dict):
            for x in v.values():
                andar(x, prof + 1)
        elif isinstance(v, (list, tuple)):
            for x in v[:50]:
                andar(x, prof + 1)
        elif v is not None:
            partes.append(str(v))
    andar(params)
    return " ".join(partes)[:limite]


class MotorDefesa:
    def __init__(self, rajada_por_min: int = 30):
        self.rajada_por_min = rajada_por_min
        self._chamadas: dict[str, deque] = {}
        self._pausado_ate: dict[str, float] = {}
        self.bloqueios: Counter = Counter()
        self.confirmacoes: Counter = Counter()

    def executa(self, nome: str, params: dict) -> bool:
        chaves = {str(k).lower() for k in (params or {})}
        return bool(_EXECUTA_NOME.search(nome or "")) or bool(chaves & _EXECUTA_PARAM) or bool(_SINTAXE_CMD.search(_texto(params)))

    def validar(self, nome: str, params: dict | None, estado_modulo: str = "saudavel", agora: float | None = None) -> Veredito:
        params = params or {}
        agora = agora or time.time()
        texto = _texto(params)
        executa = self.executa(nome, params)
        acao_txt = str(params.get("action") or params.get("acao") or "")

        if executa and _PROTECAO.search(texto) and _DESLIGAR.search(texto):
            return self._bloquear("protecao_do_sistema", "desligar antivírus, firewall ou proteções do sistema nunca é permitido", 1.0)
        if executa and _DESTRUICAO.search(texto):
            return self._bloquear("destruicao_total", "comando que apaga o disco ou o sistema inteiro", 1.0)
        if _VITAIS.search(texto) and (_PERIGOSO.search(texto) or _PERIGOSO.search(acao_txt)):
            return self._bloquear("arquivos_vitais", "mexer nos arquivos vitais do organismo (DNA, memória imune) não é permitido", 0.9)

        fila = self._chamadas.setdefault(nome, deque(maxlen=self.rajada_por_min + 5))
        if self._pausado_ate.get(nome, 0) > agora:
            return self._bloquear("anti_laco", f"'{nome}' foi chamada {self.rajada_por_min}+ vezes em 1 minuto; pausa de segurança", 0.5)
        fila.append(agora)
        if len(fila) > self.rajada_por_min and agora - fila[-self.rajada_por_min - 1] < 60:
            self._pausado_ate[nome] = agora + 60
            fila.clear()
            return self._bloquear("anti_laco", f"'{nome}' foi chamada mais de {self.rajada_por_min} vezes em 1 minuto: "
                                               "parece um laço; pausei por 1 minuto", 0.5)

        perigoso = bool(_PERIGOSO.search(acao_txt) or _PERIGOSO.search(texto))
        if executa and perigoso and _SISTEMA.search(texto):
            return self._confirmar("pasta_do_sistema", "apagar ou mover algo dentro de uma pasta do sistema operacional", 0.8)
        if estado_modulo == "comprometido" and perigoso:
            return self._confirmar("modulo_comprometido", f"'{nome}' está com o arquivo alterado e falhando, e pediu uma ação perigosa", 0.7)
        return Veredito(PERMITIR)

    def _bloquear(self, regra: str, motivo: str, risco: float) -> Veredito:
        self.bloqueios[regra] += 1
        return Veredito(BLOQUEAR, motivo, regra, risco)

    def _confirmar(self, regra: str, motivo: str, risco: float) -> Veredito:
        self.confirmacoes[regra] += 1
        return Veredito(CONFIRMAR, motivo, regra, risco)

    def estado(self) -> dict:
        agora = time.time()
        return {"bloqueios": dict(self.bloqueios), "confirmacoes": dict(self.confirmacoes),
                "pausadas": [n for n, t in self._pausado_ate.items() if t > agora], "rajada_por_min": self.rajada_por_min}
