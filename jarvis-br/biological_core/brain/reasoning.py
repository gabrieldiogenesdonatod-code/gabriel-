"""
Raciocínio do cérebro — a "IA básica" local, sem internet e sem API paga.

1. ClassificadorErros (Naive Bayes multinomial, treinado no seu PC)
   Lê a mensagem de erro e diz o tipo: rede, chave, pacote, JSON corrompido, sintaxe, bug…
   Começa com exemplos-semente e APRENDE: cada incidente resolvido vira um exemplo novo, então
   erros que nenhuma regra conhecia passam a ser reconhecidos. Fica em memory/biological/cerebro.json.

2. MotorHipoteses (raciocínio bayesiano com evidências)
   Para cada falha, cria hipóteses de causa ("a internet caiu", "o arquivo do plugin mudou",
   "o serviço de fora está fora", "dados corrompidos"…). Cada hipótese começa com uma chance
   (prior, ajustada pelo histórico daquele módulo) e cada evidência multiplica essa chance
   (razão de verossimilhança). No fim, normaliza: dá a probabilidade de cada causa e a lista
   das evidências que pesaram — o cérebro sempre consegue explicar POR QUE acha aquilo.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

SEMENTES = {
    "rede": ["ConnectionError Max retries exceeded with url", "getaddrinfo failed", "Name or service not known",
             "Temporary failure in name resolution", "Failed to establish a new connection", "Network is unreachable",
             "WinError 10060 tentativa de conexão falhou", "WinError 10061 nenhuma conexão pôde ser feita",
             "ConnectionResetError conexão forçada a fechar pelo host remoto", "RemoteDisconnected Remote end closed connection",
             "SSLError EOF occurred in violation of protocol", "sem internet", "proxy error cannot connect"],
    "timeout": ["ReadTimeout read timed out", "ConnectTimeout", "TimeoutError timed out", "deadline exceeded",
                "passou de 30 s ainda trabalhando", "operation timed out", "a ferramenta travou"],
    "chave": ["401 Unauthorized", "API key not valid please pass a valid API key", "invalid api key", "Unauthenticated",
              "403 Forbidden permission denied for this key", "chave inválida", "token expirado", "missing api key",
              "chave não configurada", "credenciais inválidas"],
    "pacote": ["ModuleNotFoundError No module named", "ImportError cannot import name", "DLL load failed while importing",
               "pacote não instalado", "instale com pip install"],
    "arquivo": ["FileNotFoundError No such file or directory", "O sistema não pode encontrar o arquivo especificado",
                "arquivo não encontrado", "NotADirectoryError", "IsADirectoryError", "path does not exist", "pasta não existe"],
    "json_corrompido": ["JSONDecodeError Expecting value line 1 column 1", "Expecting property name enclosed in double quotes",
                        "Unterminated string starting at", "Extra data line column", "Invalid control character at",
                        "UnicodeDecodeError utf-8 codec can't decode byte", "arquivo de dados corrompido"],
    "permissao": ["PermissionError Errno 13 Permission denied", "Acesso negado", "WinError 5 Access is denied",
                  "Operation not permitted", "WinError 32 o arquivo já está sendo usado por outro processo"],
    "memoria": ["MemoryError", "Unable to allocate array with shape", "out of memory", "Cannot allocate memory", "CUDA out of memory"],
    "recurso": ["No space left on device", "Errno 28", "não há espaço suficiente no disco", "Too many open files", "disk full"],
    "sintaxe": ["SyntaxError invalid syntax", "IndentationError unexpected indent", "TabError inconsistent use of tabs",
                "unexpected EOF while parsing", "SyntaxError unterminated string literal"],
    "externo": ["HTTPError 404 Not Found", "500 Internal Server Error", "503 Service Unavailable", "502 Bad Gateway",
                "429 Too Many Requests", "quota exceeded", "RESOURCE_EXHAUSTED", "o site mudou elemento não encontrado",
                "resposta inesperada do servidor"],
    "bug": ["KeyError", "TypeError unsupported operand type", "AttributeError NoneType object has no attribute",
            "IndexError list index out of range", "ValueError invalid literal for int with base 10",
            "ZeroDivisionError division by zero", "NameError name is not defined",
            "UnboundLocalError local variable referenced before assignment", "RecursionError maximum recursion depth exceeded",
            "AssertionError", "TypeError missing 1 required positional argument", "not subscriptable", "object is not callable"],
}
PARADAS = {"the", "of", "a", "an", "to", "in", "is", "for", "on", "with", "at", "by", "de", "da", "do", "o", "e", "que",
           "em", "um", "uma", "os", "as", "no", "na", "por", "com", "para", "se", "ao", "line", "column", "char"}


def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


class ClassificadorErros:
    def __init__(self, dados: dict | None = None):
        self.cont: dict[str, Counter] = {}
        self.docs: Counter = Counter()
        self.aprendidos = 0
        if dados and dados.get("cont"):
            self.cont = {c: Counter(v) for c, v in dados["cont"].items()}
            self.docs = Counter(dados.get("docs", {}))
            self.aprendidos = int(dados.get("aprendidos", 0))
        else:
            for cat, exemplos in SEMENTES.items():
                for e in exemplos:
                    self._somar(e, cat)

    @staticmethod
    def tokens(texto: str) -> list[str]:
        t = _sem_acento(str(texto or ""))
        out = []
        for m in re.finditer(r"[A-Za-z][A-Za-z_]+|\d{3,5}", t):
            w = m.group(0)
            if w.isdigit():
                out.append(f"n{w}")
                continue
            partes = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", w)
            low = w.lower()
            if low not in PARADAS and len(low) > 1:
                out.append(low)
            if len(partes) > 1:
                out += [p.lower() for p in partes if len(p) > 2 and p.lower() not in PARADAS]
        return out

    def _somar(self, texto: str, cat: str, peso: int = 1) -> None:
        c = self.cont.setdefault(cat, Counter())
        for tk in self.tokens(texto):
            c[tk] += peso
        self.docs[cat] += peso

    def aprender(self, texto: str, categoria: str, peso: int = 2) -> None:
        """Um incidente resolvido vira exemplo. Peso 2: a experiência real vale mais que a semente."""
        if not texto or not categoria or categoria in ("desconhecida", "integridade", "ameaca", "anomalia", "travamento"):
            return
        self._somar(texto, categoria, peso)
        self.aprendidos += 1

    def probabilidades(self, texto: str) -> list[tuple[str, float]]:
        tks = self.tokens(texto)
        if not tks or not self.cont:
            return []
        vocab = len(set().union(*self.cont.values())) or 1
        total_docs = sum(self.docs.values()) or 1
        logs = {}
        for cat, c in self.cont.items():
            total = sum(c.values())
            lp = math.log((self.docs[cat] + 1) / (total_docs + len(self.cont)))
            for tk in tks:
                lp += math.log((c[tk] + 1) / (total + vocab))
            logs[cat] = lp
        m = max(logs.values())
        ex = {c: math.exp(v - m) for c, v in logs.items()}
        soma = sum(ex.values())
        return sorted(((c, v / soma) for c, v in ex.items()), key=lambda x: -x[1])

    def classificar(self, texto: str, minimo: float = 0.4) -> tuple[str, float, str]:
        """(categoria, confiança, de_onde): primeiro as regras de alta certeza, depois o que aprendeu."""
        from biological_core.immune_system.threat_detector import classificar_por_regras
        r = classificar_por_regras("", texto)
        if r:
            return r, 0.95, "regra"
        probs = self.probabilidades(texto)
        if not probs:
            return "desconhecida", 0.0, "nenhum"
        cat, p = probs[0]
        return (cat, round(p, 3), "aprendido") if p >= minimo else ("desconhecida", round(p, 3), "incerto")

    def exportar(self) -> dict:
        return {"cont": {c: dict(v) for c, v in self.cont.items()}, "docs": dict(self.docs), "aprendidos": self.aprendidos}

    def estado(self) -> dict:
        return {"categorias": len(self.cont), "palavras": len(set().union(*self.cont.values())) if self.cont else 0,
                "exemplos": sum(self.docs.values()), "aprendidos_com_voce": self.aprendidos}


HIPOTESES = {
    "internet_caiu": (0.10, "a internet caiu"),
    "servico_externo_fora": (0.10, "o serviço de fora está com problema"),
    "mudanca_no_codigo": (0.08, "o arquivo do plugin mudou e quebrou"),
    "codigo_quebrado": (0.03, "o código do plugin está quebrado (não compila)"),
    "edicao_no_codigo": (0.01, "arquivos de código foram editados (por você?)"),
    "protecao_enfraquecida": (0.01, "uma proteção do organismo foi enfraquecida"),
    "dados_corrompidos": (0.05, "um arquivo de dados está corrompido"),
    "pacote_faltando": (0.05, "falta um pacote Python"),
    "chave_invalida": (0.05, "a chave de API está faltando ou errada"),
    "falta_de_recurso": (0.04, "falta memória ou disco"),
    "bug_no_plugin": (0.20, "é um erro no código do plugin"),
    "parametro_ruim": (0.10, "é o pedido (parâmetros) que está ruim, não o plugin"),
    "sobrecarga": (0.05, "o JARVIS está sobrecarregado"),
    "arquivo_sumiu": (0.05, "um arquivo ou pasta sumiu"),
    "sem_permissao": (0.05, "falta permissão (arquivo em uso ou protegido)"),
    "arquivo_vital_alterado": (0.01, "um arquivo vital do organismo foi alterado"),
    "versao_nova": (0.01, "uma versão nova foi instalada por cima"),
    "vazamento_memoria": (0.01, "a memória está vazando"),
    "travamento_interno": (0.02, "uma parte interna do organismo parou"),
}

DIRETAS = {"json_corrompido": ("dados_corrompidos", 40), "pacote": ("pacote_faltando", 40), "chave": ("chave_invalida", 40),
           "memoria": ("falta_de_recurso", 30), "recurso": ("falta_de_recurso", 30), "arquivo": ("arquivo_sumiu", 15),
           "permissao": ("sem_permissao", 30)}


class MotorHipoteses:
    def evidencias(self, ctx: dict) -> dict[str, list[tuple[float, str]]]:
        ev: dict[str, list[tuple[float, str]]] = {h: [] for h in HIPOTESES}
        cat = ctx.get("categoria") or "desconhecida"

        def soma(h, lr, txt):
            ev[h].append((lr, txt))

        if cat in DIRETAS:
            h, lr = DIRETAS[cat]
            soma(h, lr, f"o erro é do tipo '{cat}'")
        if cat == "rede":
            soma("internet_caiu", 3, "erro de conexão")
            soma("servico_externo_fora", 3, "erro de conexão")
            soma("bug_no_plugin", 0.3, "erro de conexão raramente é bug")
        n = int(ctx.get("modulos_com_rede_5min") or 0)
        if n >= 2:
            soma("internet_caiu", 2.5 ** min(4, n - 1), f"{n} ferramentas sem internet ao mesmo tempo")
            soma("servico_externo_fora", 0.5, "não é só este serviço")
        con = ctx.get("conectividade")
        if con is False:
            soma("internet_caiu", 12, "o teste de conexão falhou agora")
            soma("servico_externo_fora", 0.5, "nem a internet responde")
        elif con is True and cat in ("rede", "externo", "timeout"):
            soma("internet_caiu", 0.08, "o teste de conexão funciona")
            soma("servico_externo_fora", 3, "a internet funciona, só este serviço não")
        if cat == "externo" or ctx.get("http_5xx"):
            soma("servico_externo_fora", 6, "o servidor respondeu com erro")
        if cat == "timeout":
            soma("sobrecarga", 2, "demorou demais")
            soma("servico_externo_fora", 2, "demorou demais")
            soma("internet_caiu", 1.5, "demorou demais")
        if int(ctx.get("vigia_ocupadas") or 0) >= 6:
            soma("sobrecarga", 5, f"{ctx['vigia_ocupadas']} tarefas rodando juntas")
        if int(ctx.get("timeouts_modulos_10min") or 0) >= 3:
            soma("sobrecarga", 3, "várias ferramentas travando ao mesmo tempo")
        h_mod = ctx.get("arquivo_modificado_h")
        if h_mod is not None and h_mod <= 48:
            alvo = "codigo_quebrado" if cat == "sintaxe" else "mudanca_no_codigo"
            soma(alvo, 10 if h_mod <= 6 else 5, f"o arquivo do plugin mudou há {h_mod:.1f} h".replace(".", ","))
        if cat == "bug":
            soma("bug_no_plugin", 4, "erro de programação")
            soma("mudanca_no_codigo", 2, "erro de programação")
        if cat == "sintaxe":
            soma("codigo_quebrado", 60, "o arquivo não compila")
            soma("mudanca_no_codigo", 3, "arquivo de código com erro")
            soma("bug_no_plugin", 0.5, "não compila: não é erro de execução")
        if cat == "ameaca":
            soma("protecao_enfraquecida", 300, "proteção desligada ou afrouxada por fora")
        if ctx.get("falha_so_com_params"):
            soma("parametro_ruim", 6, "a mesma ferramenta funciona com outros pedidos")
            soma("bug_no_plugin", 0.7, "funciona com outros pedidos")
        if ctx.get("ram_pc") is not None and ctx["ram_pc"] >= 90:
            soma("falta_de_recurso", 6, f"RAM do PC em {ctx['ram_pc']:.0f}%")
        if ctx.get("disco_livre_pct") is not None and ctx["disco_livre_pct"] < 5:
            soma("falta_de_recurso", 6, f"só {ctx['disco_livre_pct']:.0f}% de disco livre")
        acao = str(ctx.get("acao") or "")
        if cat == "integridade":
            if acao == "versao_nova":
                soma("versao_nova", 500, "a versão instalada mudou")
            elif "vital" in acao or acao in ("adulterado", "corrompido"):
                soma("arquivo_vital_alterado", 200, "arquivo vital diferente do DNA")
            else:
                soma("edicao_no_codigo", 200, "arquivo diferente do DNA, sem falha ligada a ele")
        if cat == "anomalia":
            if ctx.get("tipo") == "vazamento_de_memoria":
                soma("vazamento_memoria", 200, "memória subindo sem parar")
            elif ctx.get("tipo") in ("tempestade_de_eventos", "threads_vazando"):
                soma("travamento_interno", 20, "comportamento interno fora do normal")
            elif ctx.get("tipo") in ("lentidao", "rajada_de_erros"):
                soma("servico_externo_fora", 2, "ficou lento/falhando de repente")
                soma("sobrecarga", 2, "ficou lento/falhando de repente")
        if cat == "travamento":
            soma("travamento_interno", 50 if ctx.get("interno") else 3, "parou de responder")
            soma("sobrecarga", 2, "parou de responder")
        for causa, vezes in (ctx.get("causas_anteriores") or {}).items():
            if causa in ev and vezes:
                soma(causa, min(6.0, (1 + vezes) / 1.5), f"já foi '{HIPOTESES[causa][1]}' {vezes} vez(es) neste módulo")
        return ev

    def avaliar(self, ctx: dict, n: int = 5) -> list[dict]:
        ev = self.evidencias(ctx)
        logs = {}
        for h, (prior, _d) in HIPOTESES.items():
            logs[h] = math.log(prior) + sum(math.log(lr) for lr, _t in ev[h])
        m = max(logs.values())
        ex = {h: math.exp(v - m) for h, v in logs.items()}
        soma = sum(ex.values())
        out = [{"causa": h, "prob": round(v / soma, 3), "descricao": HIPOTESES[h][1],
                "evidencias": [t for lr, t in sorted(ev[h], key=lambda x: -x[0]) if lr > 1][:4]}
               for h, v in ex.items()]
        return sorted(out, key=lambda x: -x["prob"])[:n]
