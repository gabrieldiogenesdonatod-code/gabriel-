"""
J.A.R.V.I.S BR no celular (fork PT-BR 2.18, atualizado na 2.19) — o JARVIS inteiro rodando no Android pelo Termux.

    python celular/jarvis_celular.py            → abre http://localhost:8765 no Chrome do celular
    python celular/jarvis_celular.py --rede     → também na rede de casa (com senha), para usar de outro aparelho

O que roda aqui
    * TODOS os plugins de plugins/ (os que precisam do PC respondem "não disponível");
    * TODOS os modos (os 145 prontos, em 10 categorias, e os que você criar);
    * o cérebro é o Gemini pela API REST (só a chave grátis, nenhum pacote extra);
    * a interface (celular/jarvis_celular.html) fala e ouve pelo próprio Chrome.

Economia de token: o modelo recebe só ~20 ferramentas diretas + 3 de apoio
(buscar_ferramentas, usar_ferramenta, pesquisar_web). As outras ~250 continuam
todas disponíveis: ele busca a que precisa e usa pelo nome.

Só usa a biblioteca padrão do Python. Nada de PyQt, FastAPI ou google-genai.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

HTML = Path(__file__).resolve().parent / "jarvis_celular.html"
API = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
MODELOS = ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-flash-lite-latest")
TERMUX = bool(shutil.which("termux-open-url"))

# Ferramentas que vão direto para o modelo (o resto fica atrás de buscar/usar).
DIRETAS = ("modos", "celular_android", "calculadora", "cronometros", "lista_compras", "sequencias", "segundo_cerebro",
           "gastos", "cristal_malhas", "clientes_loja", "fiado", "meta_vendas", "piadas", "sorteio", "chuva", "rastreio",
           "contas", "alerta_cotacao", "consulta_brasil", "feriados", "hidratacao", "receitas",
           # 2.19: o que mais se usa com o celular na mão
           "resumo_do_dia", "onde_guardei", "precos_mercado")


# ═════════════════════════════════════════════════════════════════ eventos ═══
class Eventos:
    """Fila que a interface busca a cada 2 s: falas, cartões e registro."""

    def __init__(self):
        self.itens: list[dict] = []
        self.n = 0
        self.lock = threading.Lock()

    def add(self, tipo: str, **dados) -> None:
        with self.lock:
            self.n += 1
            self.itens.append({"id": self.n, "tipo": tipo, "ts": time.time(), **dados})
            del self.itens[:-300]

    def desde(self, n: int) -> list[dict]:
        with self.lock:
            return [e for e in self.itens if e["id"] > n]


EVENTOS = Eventos()


class PlayerCelular:
    """Faz o papel da janela do PC (JarvisUI) para os plugins."""

    def __init__(self, motor_fn=None):
        self.motor_fn = motor_fn          # devolve o Motor (para transformar instruções em fala)

    def write_log(self, msg: str) -> None:
        msg = str(msg)
        if msg.startswith("SYS: ") or msg.startswith("JARVIS: "):
            EVENTOS.add("log", texto=msg.split(": ", 1)[1][:500])

    def show_content(self, titulo, texto) -> None:
        EVENTOS.add("cartao", titulo=str(titulo), texto=str(texto)[:6000])

    def request_say(self, instrucao: str) -> None:
        instrucao = str(instrucao)
        m = re.search(r"Diga exatamente[^:]*:\s*(.+)$", instrucao, re.S)
        if m:                                           # guias (respiração, jogos): fala direta, sem gastar token
            EVENTOS.add("fala", texto=m.group(1).strip())
            return
        m = re.search(r"(?:frase(?: curta)?[^:]*|uma frase):\s*(.+?)(?:\s*Não chame.*)?$", instrucao, re.S)
        if m and len(m.group(1)) < 300:                 # aviso pronto ("Timer acabou")
            EVENTOS.add("fala", texto=m.group(1).strip())
            return
        motor = self.motor_fn() if self.motor_fn else None
        if motor is None:
            EVENTOS.add("fala", texto=instrucao[:300])
            return
        threading.Thread(target=lambda: EVENTOS.add("fala", texto=motor.aviso(instrucao)), daemon=True).start()

    plugin_say = request_say

    def __getattr__(self, nome):          # qualquer outro método da janela do PC vira "não faz nada"
        return lambda *a, **k: None


# ═════════════════════════════════════════════════════════ ajustes do celular ═══
def _ajustar_para_celular() -> None:
    """Pastas visíveis no Android, abrir links pelo Android, e Gemini por REST sem o pacote google-genai."""
    from plugins import _comum

    compart = Path.home() / "storage" / "shared"
    if compart.exists():
        nomes = {"Documents": "Documents", "Downloads": "Download", "Pictures": "Pictures", "Videos": "Movies",
                 "Desktop": "Documents"}
        _comum.pasta_usuario = lambda nome: compart / nomes.get(nome, nome)

    if TERMUX:
        import webbrowser

        def abrir(alvo) -> bool:
            try:
                subprocess.Popen(["termux-open", str(alvo)] if not str(alvo).startswith(("http", "spotify:", "tel:"))
                                 else ["termux-open-url", str(alvo)])
                return True
            except Exception:
                return False
        _comum.abrir_no_sistema = abrir
        webbrowser.open = lambda url, *a, **k: abrir(url)

    try:
        import google.genai  # noqa: F401
    except Exception:
        from core import gemini
        gemini.client = lambda timeout_ms=60_000, key="": _ClienteREST(key or gemini.api_key(), timeout_ms)


class _Resposta:
    def __init__(self, texto: str):
        self.text, self.candidates = texto, []


class _ClienteREST:
    """O pedaço do google-genai que os plugins usam (client.models.generate_content), por REST."""

    def __init__(self, chave: str, timeout_ms: int):
        self.models, self.chave, self.timeout = self, chave, max(10, timeout_ms / 1000)

    def generate_content(self, model: str, contents, config=None):
        corpo = {"contents": _conteudos(contents)}
        if config is not None:
            g = config if isinstance(config, dict) else {k: getattr(config, k, None) for k in
                                                         ("system_instruction", "temperature", "response_mime_type")}
            if g.get("system_instruction"):
                corpo["system_instruction"] = {"parts": [{"text": str(g["system_instruction"])}]}
            cfg = {k: v for k, v in (("temperature", g.get("temperature")),
                                     ("responseMimeType", g.get("response_mime_type"))) if v is not None}
            if cfg:
                corpo["generationConfig"] = cfg
        r = gemini_rest(model, corpo, self.chave, self.timeout)
        return _Resposta(texto_de(r))


def _conteudos(c) -> list[dict]:
    if isinstance(c, str):
        return [{"role": "user", "parts": [{"text": c}]}]
    if isinstance(c, list) and c and isinstance(c[0], dict) and "role" in c[0]:
        return c
    partes = []
    for x in (c if isinstance(c, (list, tuple)) else [c]):
        if isinstance(x, str):
            partes.append({"text": x})
        elif isinstance(x, dict):
            partes.append(x)
        elif getattr(x, "text", None):
            partes.append({"text": x.text})
        elif getattr(x, "inline_data", None) is not None:
            import base64
            d = x.inline_data
            partes.append({"inline_data": {"mime_type": d.mime_type, "data": base64.b64encode(d.data).decode()}})
    return [{"role": "user", "parts": partes or [{"text": str(c)}]}]


def gemini_rest(modelo: str, corpo: dict, chave: str, timeout: float = 60) -> dict:
    req = urllib.request.Request(API.format(m=modelo, k=chave), data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detalhe}") from None


def texto_de(r: dict) -> str:
    partes = ((r.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in partes if not p.get("thought")).strip()


# ═══════════════════════════════════════════════════════════════════ motor ═══
_CHAVES_SCHEMA = {"type", "description", "properties", "required", "items", "enum", "format", "nullable"}


def limpar_schema(s):
    """Deixa só o que a API REST aceita (um schema estranho derrubaria o pedido inteiro)."""
    if not isinstance(s, dict):
        return {"type": "STRING"}
    out = {k: v for k, v in s.items() if k in _CHAVES_SCHEMA}
    out["type"] = str(out.get("type") or "STRING").upper()
    if "properties" in out:
        out["properties"] = {k: limpar_schema(v) for k, v in (out["properties"] or {}).items()}
        out["required"] = [r for r in out.get("required") or [] if r in out["properties"]]
        if not out["required"]:
            out.pop("required")
    if out["type"] == "ARRAY":
        out["items"] = limpar_schema(out.get("items") or {"type": "STRING"})
    if out["type"] == "OBJECT" and not out.get("properties"):
        out.pop("properties", None)
    return out


def encurtar(schema: dict, limite: int = 100) -> dict:
    """Corta as descrições dos parâmetros (no celular as ferramentas vão em TODA mensagem: cada token conta)."""
    for nome, prop in (schema.get("properties") or {}).items():
        d = str(prop.get("description") or "")
        teto = 170 if nome == "action" else limite
        if len(d) > teto:
            prop["description"] = d[:teto].rsplit(" ", 1)[0] + "…"
    return schema


def assinatura(d: dict) -> str:
    props = (d.get("parameters") or {}).get("properties") or {}
    campos = ", ".join(f"{k}{'=' + v['description'][:70] if k == 'action' and v.get('description') else ''}"
                       for k, v in props.items())
    return f"{d['name']}({campos}): {' '.join(str(d.get('description', '')).split())[:400]}"


def doc_pt(nome: str) -> str:
    """Primeira frase do arquivo do plugin, em português (a mesma do plugin `catalogo`)."""
    from plugins import catalogo
    return catalogo.doc_pt(nome)


def buscar(declaracoes: list[dict], pergunta: str, n: int = 6) -> list[dict]:
    """Mesma busca do PC (plugin `catalogo`): nome vale 3, descrição vale 1, com radical das palavras.
    3.4: as ferramentas que o cérebro local aprendeu com você para essa frase vêm primeiro."""
    from plugins import catalogo
    return catalogo.com_cerebro(declaracoes, pergunta, n)


class Motor:
    def __init__(self, registro, chave_fn, llm=None):
        self.reg = registro
        self.chave_fn = chave_fn
        self.llm = llm or gemini_rest            # os testes trocam por um Gemini falso
        self.historico: list[dict] = []
        self.lock = threading.Lock()
        self.modelo_ok: str | None = None

    # -- catálogo --
    def declaracoes(self) -> list[dict]:
        return self.reg.get_tool_declarations()

    def ferramentas(self) -> list[dict]:
        decl = {d["name"]: d for d in self.declaracoes()}
        diretas = [{"name": n, "description": " ".join(str(decl[n].get("brief") or decl[n]["description"]).split())[:260],
                    "parameters": encurtar(limpar_schema(decl[n]["parameters"]))} for n in DIRETAS if n in decl]
        apoio = [
            {"name": "buscar_ferramentas", "description": "Find other JARVIS tools for a request (returns names, params, "
             "what they do). Use before saying you can't do something.",
             "parameters": {"type": "OBJECT", "properties": {"pergunta": {"type": "STRING"}}, "required": ["pergunta"]}},
            {"name": "usar_ferramenta", "description": "Run any JARVIS tool by exact name with its parameters as a JSON "
             "object string, e.g. nome='juros', parametros='{\"action\":\"parcela\",\"valor\":\"1000\"}'.",
             "parameters": {"type": "OBJECT", "properties": {"nome": {"type": "STRING"}, "parametros": {"type": "STRING"}},
                            "required": ["nome"]}},
            {"name": "pesquisar_web", "description": "Search the internet (news, scores, prices, facts that change).",
             "parameters": {"type": "OBJECT", "properties": {"pergunta": {"type": "STRING"}}, "required": ["pergunta"]}},
        ]
        return diretas + apoio

    def sistema(self) -> str:
        from memory.config_manager import get_assistant_name, get_user_name
        nome, usuario = get_assistant_name() or "JARVIS", get_user_name() or ""
        from core import anonimo
        if anonimo.ativo():
            usuario = ""                                   # 3.2: modo anônimo — o modelo não recebe quem você é
        outras = sorted(n for n in (d["name"] for d in self.declaracoes()) if n not in DIRETAS)
        txt = (f"Você é {nome}, o assistente J.A.R.V.I.S do {usuario or 'usuário'}, rodando no CELULAR Android dele. "
               "Responda em português do Brasil, curto e natural (vai ser falado em voz alta: sem markdown, sem listas "
               "longas, sem emojis). Chame o usuário de 'senhor'. Se dá para fazer com uma ferramenta, FAÇA chamando-a, "
               "não diga que vai fazer. Ferramentas que precisam do PC (teclado, janelas, webcam do PC) não funcionam "
               "aqui: diga isso em uma frase. Para coisas do celular use celular_android. "
               f"Hora local: {time.strftime('%d/%m/%Y %H:%M')}.\n"
               f"Outras ferramentas (use buscar_ferramentas e depois usar_ferramenta): {', '.join(outras)}.")
        try:
            from plugins import modos
            k = modos.atual()
            m = modos.todos().get(k)
            if m:
                txt += f"\n\n[MODO {m['titulo'].upper()} LIGADO] Enquanto ele estiver ligado: {m.get('jeito', '')}"
        except Exception:
            pass
        if anonimo.ativo():
            txt += "\n\n" + anonimo.INSTRUCAO
        try:
            from core import caixa_preta                    # 3.3: erros que você já corrigiu
            licoes = caixa_preta.instrucao()
            if licoes:
                txt += "\n\n" + licoes
        except Exception:
            pass
        return txt

    # -- chamada ao modelo com escada de modelos --
    def _gerar(self, corpo: dict) -> dict:
        chave = self.chave_fn()
        if not chave:
            raise RuntimeError("SEM_CHAVE")
        from memory.config_manager import load_api_keys
        preferido = load_api_keys().get("celular_modelo")
        ordem = [m for m in dict.fromkeys([preferido, self.modelo_ok, *MODELOS]) if m]
        erro = None
        for m in ordem:
            try:
                r = self.llm(m, corpo, chave, 60)
                self.modelo_ok = m
                return r
            except Exception as e:
                erro = e
                if not re.search(r"HTTP (429|404|500|502|503|504)|timed out|Temporary", str(e)):
                    break
        raise RuntimeError(str(erro))

    def _executar(self, nome: str, args: dict) -> tuple[str, str]:
        args = dict(args or {})
        if nome == "buscar_ferramentas":
            achadas = buscar(self.declaracoes(), str(args.get("pergunta", "")))
            return nome, "\n".join(map(assinatura, achadas)) or "Nenhuma ferramenta parecida."
        if nome == "pesquisar_web":
            return nome, self.pesquisar(str(args.get("pergunta", "")))
        if nome == "usar_ferramenta":
            nome = str(args.get("nome") or "")
            p = args.get("parametros") or {}
            if isinstance(p, str):
                try:
                    p = json.loads(p or "{}")
                except Exception:
                    p = {"action": p}
            args = p if isinstance(p, dict) else {}
        if not self.reg.has(nome):
            parecidas = [d["name"] for d in buscar(self.declaracoes(), nome.replace("_", " "), 4)]
            return nome, f"A ferramenta '{nome}' não existe. Parecidas: {', '.join(parecidas) or 'nenhuma'}."
        EVENTOS.add("ferramenta", nome=nome, params=args)
        from core import vigia                      # 3.0: nenhum plugin segura a conversa por mais de ~30 s

        def tarde(n, res, dur):
            EVENTOS.add("cartao", titulo=f"{n.upper()} (terminou)", texto=res[:6000])
            EVENTOS.add("fala", texto=f"Terminei {n.replace('_', ' ')}: {res[:240]}")
        r, _ = vigia.executar_sync(lambda: self.reg.run(nome, args, player=PLAYER), nome, ao_terminar_tarde=tarde)
        try:
            from core import cerebro                       # 3.4: o cérebro local aprende frase → ferramenta
            cerebro.anotar_chamada(nome, args, str(r), proprio=getattr(self, "_reflexo_agora", False))
        except Exception:
            pass
        try:
            from core import livro_razao                   # 3.6: prova do que foi feito pelo celular
            livro_razao.ferramenta(nome, args, str(r))
        except Exception:
            pass
        return nome, str(r)[:4000]

    def _pelo_cerebro(self, texto: str, sem_ia: bool = False) -> dict | None:
        """3.4: comando que o cérebro local já sabe roda na hora, sem gastar o Gemini."""
        try:
            from core import cerebro
            r = cerebro.entender(texto, sem_ia=sem_ia)
            if not r["reflexo"] or not self.reg.has(r["ferramenta"]):
                return None
            self._reflexo_agora = True                    # 3.6: reflexo não conta como acerto na medição do cérebro
            try:
                nome, res = self._executar(r["ferramenta"], dict(r["args"]))
            finally:
                self._reflexo_agora = False
            cerebro.turno(texto)
            resposta = cerebro.resposta_curta(res)
            self.historico += [{"role": "user", "parts": [{"text": texto}]},
                               {"role": "model", "parts": [{"text": resposta}]}]
            del self.historico[:-60]
            return {"resposta": resposta, "ferramentas": [nome], "cerebro": True}
        except Exception as e:
            print(f"[Cérebro] {e}")
            return None

    def conversar(self, texto: str) -> dict:
        with self.lock:
            rapido = self._pelo_cerebro(texto)
        if rapido:
            return rapido
        with self.lock:
            inicio = len(self.historico)
            self.historico.append({"role": "user", "parts": [{"text": texto}]})
            usadas = []
            try:
                for _ in range(8):
                    corpo = {"system_instruction": {"parts": [{"text": self.sistema()}]},
                             "contents": self._cortar(), "tools": [{"function_declarations": self.ferramentas()}],
                             "generationConfig": {"temperature": 0.7}}
                    r = self._gerar(corpo)
                    conteudo = ((r.get("candidates") or [{}])[0].get("content")) or {"role": "model", "parts": []}
                    conteudo.setdefault("role", "model")
                    self.historico.append(conteudo)
                    chamadas = [p["functionCall"] for p in conteudo.get("parts", []) if "functionCall" in p]
                    if not chamadas:
                        resposta = texto_de(r) or "Feito, senhor."
                        break
                    respostas = []
                    for c in chamadas:
                        nome, res = self._executar(c.get("name", ""), c.get("args") or {})
                        usadas.append(nome)
                        respostas.append({"functionResponse": {"name": c.get("name", ""), "response": {"resultado": res}}})
                    self.historico.append({"role": "user", "parts": respostas})
                else:
                    resposta = "Fiz o que pude, senhor."
            except Exception as e:
                del self.historico[inicio:]          # turno que falhou não fica no histórico
                sem_ia = self._pelo_cerebro(texto, sem_ia=True)       # 3.4: sem Gemini, o cérebro tenta
                if sem_ia:
                    sem_ia["resposta"] += " (feito pelo cérebro local, sem o Gemini)"
                    return sem_ia
                if str(e) == "SEM_CHAVE":
                    return {"resposta": "Cole a sua chave grátis do Gemini em Ajustes para eu poder pensar.", "erro": "chave"}
                traceback.print_exc()
                return {"resposta": f"Não consegui falar com o Gemini agora ({str(e)[:160]}).", "erro": "gemini"}
            del self.historico[:-60]
            try:
                from core import caixa_preta                # 3.3: a sua correção vira lição
                caixa_preta.turno(texto, resposta)
            except Exception:
                pass
            try:
                from core import cerebro                    # 3.4: frase → ferramenta que deu certo
                cerebro.turno(texto, resposta)
            except Exception:
                pass
            return {"resposta": resposta, "ferramentas": usadas}

    def _cortar(self) -> list[dict]:
        """Últimas mensagens começando numa fala do usuário (nunca no meio de uma chamada de ferramenta)."""
        h = self.historico[-30:]
        for i, c in enumerate(h):
            if c["role"] == "user" and any("text" in p for p in c.get("parts", [])):
                return h[i:]
        return self.historico[-1:]

    def pesquisar(self, pergunta: str) -> str:
        try:
            r = self._gerar({"contents": [{"role": "user", "parts": [{"text": pergunta + " (responda em português, curto)"}]}],
                             "tools": [{"google_search": {}}]})
            fontes = [c.get("web", {}).get("title", "") for c in
                      ((r.get("candidates") or [{}])[0].get("groundingMetadata") or {}).get("groundingChunks", [])][:3]
            return texto_de(r) + (f" (Fontes: {', '.join(f for f in fontes if f)})" if any(fontes) else "")
        except Exception as e:
            return f"A pesquisa falhou: {e}"

    def aviso(self, instrucao: str) -> str:
        """Transforma uma instrução de plugin ('[CHUVA] Diga ao usuário…') numa frase falada."""
        try:
            r = self._gerar({"system_instruction": {"parts": [{"text": "Você é o JARVIS. Responda com UMA frase curta em "
                                                                      "português, pronta para ser falada."}]},
                             "contents": [{"role": "user", "parts": [{"text": instrucao}]}]})
            return texto_de(r) or instrucao[:200]
        except Exception:
            return re.sub(r"^\[[^\]]+\]\s*", "", instrucao)[:200]


# ═══════════════════════════════════════════════════════════════ estado ═══
PLAYER = PlayerCelular()
MOTOR: Motor | None = None
REG = None
SENHA = ""


def iniciar(llm=None):
    global MOTOR, REG
    from core import registro_ferramentas
    from core.plugin_loader import discover_plugins
    from memory.config_manager import get_gemini_key

    _ajustar_para_celular()
    REG = discover_plugins(RAIZ / "plugins", set(), logger=lambda m: None)
    registro_ferramentas.definir(None, REG, PLAYER)
    MOTOR = Motor(REG, lambda: (get_gemini_key() or "").strip(), llm)
    PLAYER.motor_fn = lambda: MOTOR
    if llm is None:                                   # 2.20/2.21: no celular ele também sonha, sente e fotografa o mês
        import importlib
        for nome in ("sonhos", "sentido_aranha", "eu_do_passado", "organismo"):
            try:
                importlib.import_module(f"plugins.{nome}").on_session_start(PLAYER)
            except Exception:
                pass
        _ligar_avisos_do_organismo()
    return MOTOR


def _ligar_avisos_do_organismo() -> None:
    """3.1: os avisos de saúde do organismo aparecem como cartão no celular."""
    try:
        import biological_core
        org = biological_core.atual()
        if org is not None and not getattr(org, "_aviso_celular", False):
            org._aviso_celular = True
            org.ouvintes_aviso.append(lambda texto, prio: EVENTOS.add("cartao", titulo="SAÚDE DO JARVIS", texto=texto))
    except Exception:
        pass


def corpo() -> dict:
    """3.1: tudo o que a aba Corpo mostra (painel do Biological Core)."""
    import biological_core
    org = biological_core.atual()
    if org is None:
        return {"ligado": False}
    from biological_core.dashboard.biological_dashboard import dados, svg
    if not org.coracao.batimentos:
        org.coracao.bater()
    d = dados(org)
    return {"ligado": True, "dados": d, "svg": svg(d)}


def corpo_acao(d: dict) -> str:
    """3.1: os botões da aba Corpo. Aprovar aqui é o SEU dedo na tela — o modelo não passa por este caminho."""
    import biological_core
    org = biological_core.atual()
    if org is None:
        return "O organismo está desligado."
    acao = str(d.get("acao") or "")
    if acao == "autorizar":
        return org.autorizacoes.conceder(str(d.get("id")), "celular")
    if acao == "negar":
        return org.autorizacoes.negar(str(d.get("id")), "celular")
    if acao == "liberar":
        soltos = org.imune.isolamento.liberar(str(d.get("modulo")), None, por="usuario")
        return f"Liberado: {', '.join(soltos)}" if soltos else "Não estava isolado."
    if acao == "exame":
        from plugins import organismo
        return organismo.run({"action": "exame"}, PLAYER)
    return "Ação desconhecida."


def estado() -> dict:
    from memory.config_manager import get_gemini_key, get_user_name, get_plugin_enabled, load_api_keys
    from plugins import modos
    k = modos.atual()
    lista_modos = [{"id": n, "titulo": m.get("titulo", n), "jeito": m.get("jeito", ""),
                    "proprio": n not in modos.MODOS and n not in modos.MODOS_EXTRAS and n not in modos.MODOS_LOTE3} for n, m in modos.todos().items()]
    plugins = [{"nome": r["name"], "valido": r["valid"], "ligado": r["enabled"],
                "resumo": (doc_pt(r["name"]) or (REG._plugins[r["name"]].brief if r["valid"] else "") or r["description"])[:200],
                "erro": r.get("error", "")} for r in REG.list_for_ui()]
    return {"configurado": bool(get_gemini_key()), "modo": k, "modos": lista_modos, "plugins": plugins,
            "usuario": get_user_name(), "modelo": load_api_keys().get("celular_modelo") or MOTOR.modelo_ok or MODELOS[0],
            "termux": TERMUX, "total_plugins": sum(1 for p in plugins if p["valido"])}


def salvar_config(d: dict) -> None:
    from memory import config_manager as cm
    dados = cm.load_api_keys()
    if d.get("chave"):
        dados["gemini_api_key"] = str(d["chave"]).strip()
    if "usuario" in d:
        dados["user_name"] = str(d["usuario"]).strip()
    if "modelo" in d:
        dados["celular_modelo"] = str(d["modelo"]).strip()
    cm.ensure_config_dir()
    cm.CONFIG_FILE.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════════════════ servidor ═══
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _ok(self, corpo, tipo="application/json; charset=utf-8", codigo=200):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _autorizado(self) -> bool:
        if not SENHA:
            return True
        q = parse_qs(urlparse(self.path).query)
        return self.headers.get("X-Senha") == SENHA or (q.get("s") or [""])[0] == SENHA

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._ok(HTML.read_bytes(), "text/html; charset=utf-8")
        if u.path == "/manifest.webmanifest":
            return self._ok({"name": "J.A.R.V.I.S", "short_name": "JARVIS", "start_url": "/", "display": "standalone",
                             "background_color": "#02070d", "theme_color": "#02070d",
                             "icons": [{"src": "/icone.svg", "sizes": "any", "type": "image/svg+xml"}]},
                            "application/manifest+json")
        if u.path == "/icone.svg":
            return self._ok((RAIZ / "celular" / "app" / "icone.svg").read_bytes(), "image/svg+xml")
        if not self._autorizado():
            return self._ok({"erro": "senha"}, codigo=401)
        if u.path == "/api/estado":
            return self._ok(estado())
        if u.path == "/api/corpo":
            return self._ok(corpo())
        if u.path == "/api/eventos":
            n = int((parse_qs(u.query).get("desde") or ["0"])[0])
            return self._ok({"eventos": EVENTOS.desde(n), "ultimo": EVENTOS.n})
        self._ok({"erro": "não existe"}, codigo=404)

    def do_POST(self):
        if not self._autorizado():
            return self._ok({"erro": "senha"}, codigo=401)
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except Exception:
            d = {}
        u = urlparse(self.path).path
        try:
            if u == "/api/chat":
                return self._ok(MOTOR.conversar(str(d.get("texto", ""))[:4000]))
            if u == "/api/modo":
                from plugins import modos
                r = modos.entrar(d.get("modo", ""), PLAYER) if d.get("acao") == "entrar" else modos.sair(PLAYER)
                return self._ok({"resposta": re.sub(r"^\[MODO [^\]]+\]\s*", "", r).split(" Enquanto")[0]
                                 .split(" Volte ao")[0], "modo": modos.atual()})
            if u == "/api/modo_criar":
                from plugins import modos
                return self._ok({"resposta": modos.run({"action": "criar", "modo": d.get("modo"),
                                                        "descricao": d.get("descricao"), "passos": d.get("passos")})})
            if u == "/api/plugin":
                from memory.config_manager import save_plugin_enabled
                save_plugin_enabled(str(d.get("nome")), bool(d.get("ligado")))
                return self._ok({"ok": True})
            if u == "/api/ferramenta":
                nome, res = MOTOR._executar(str(d.get("nome")), d.get("params") or {})
                return self._ok({"resposta": res})
            if u == "/api/config":
                salvar_config(d)
                return self._ok({"ok": True})
            if u == "/api/corpo":
                return self._ok({"resposta": corpo_acao(d)})
            if u == "/api/esquecer":
                MOTOR.historico.clear()
                return self._ok({"ok": True})
        except Exception as e:
            traceback.print_exc()
            return self._ok({"resposta": f"Erro: {e}"}, codigo=500)
        self._ok({"erro": "não existe"}, codigo=404)


def _ip_local() -> str:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main():
    global SENHA
    ap = argparse.ArgumentParser(description="J.A.R.V.I.S BR no celular")
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--rede", action="store_true", help="aceitar outros aparelhos da rede (com senha)")
    ap.add_argument("--nao-abrir", action="store_true", help="não abrir o navegador sozinho")
    a = ap.parse_args()
    print("J.A.R.V.I.S BR — carregando plugins…")
    iniciar()
    total = sum(1 for r in REG.list_for_ui() if r["valid"])
    host = "0.0.0.0" if a.rede else "127.0.0.1"
    srv = ThreadingHTTPServer((host, a.porta), Handler)
    url = f"http://localhost:{a.porta}/"
    print(f"✔ {total} plugins prontos. Abra no Chrome: {url}")
    if a.rede:
        SENHA = os.environ.get("JARVIS_SENHA") or secrets.token_urlsafe(6)
        print(f"  Na rede de casa: http://{_ip_local()}:{a.porta}/?s={SENHA}")
    print("  Para fechar: Ctrl+C (ou feche a notificação do Termux).")
    if not a.nao_abrir and TERMUX:
        threading.Timer(1.0, lambda: subprocess.Popen(["termux-open-url", url])).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nAté logo, senhor.")


if __name__ == "__main__":
    main()
