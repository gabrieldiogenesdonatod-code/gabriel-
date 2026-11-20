"""
Criador automático de ferramentas — ideia 7 + "Jarvis que cria os próprios
plugins" (fork PT-BR 1.4).

DOIS JEITOS DE NASCER UMA FERRAMENTA

1. Você pede:
       "Jarvis, cria um plugin que me avisa quando o Free Fire atualizar"
       "Jarvis, cria uma ferramenta que organiza os downloads e mostra a saúde do PC"
   Com IA, o modelo escreve o arquivo seguindo o plugins/_template.py e as
   regras do projeto. Sem IA, há modelos prontos: VIGIA (confere uma página
   de tempos em tempos e avisa quando muda) e SEQUÊNCIA (encadeia ferramentas
   que já existem).

2. O JARVIS percebe: lê o diário de uso (core/registro_uso.py) e acha
   sequências que você repete — "toda vez que abre o projeto, você abre o VS
   Code, o terminal e o navegador" — e propõe juntar tudo numa ferramenta só.

NADA ENTRA SEM VOCÊ VER
    Todo plugin novo passa por:
      a) inspeção do código (sem apagar arquivos, sem shell=True, sem eval/exec,
         sem mexer no registro do Windows…);
      b) teste de carregamento numa CÓPIA do JARVIS, em outro processo (o
         mesmo teste do tests/test_carregamento.py: nome, declaração, tipos);
      c) o código aparece na tela para você ler;
      d) só instala com o botão CONFIRMAR. Aí ele vai para plugins/, é
         carregado na hora e o JARVIS reconecta para passar a usar pela voz.
    "Jarvis, desfaz" ou "remove o plugin X" tira de novo.

Pendentes ficam em config/ferramentas_criadas/.
"""

from __future__ import annotations

import ast
import hashlib
import json
import pprint
import re
import shutil
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

from plugins._comum import BASE, CONFIG, confirmar, desfazer, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "criador_ferramentas",
    "brief": "Create new JARVIS plugins on request or from repeated usage; review, test and install.",
    "description": (
        "Creates new JARVIS tools/plugins. action='criar' with pedido (user's description, e.g. 'warn "
        "me when Free Fire updates', 'a tool that organises downloads then shows PC health'), "
        "optional url/nome; the code is generated, safety-checked and load-tested, then shown for "
        "approval. 'sugestoes' finds repeated tool sequences worth merging; 'criar_sequencia' with id "
        "builds one. 'instalar' with nome installs after on-screen confirmation (active immediately). "
        "'pendentes', 'ver' (nome), 'descartar' (nome), 'criados', 'remover' (nome)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "criar | sugestoes | criar_sequencia | instalar | pendentes | ver | descartar | criados | remover"},
            "pedido": {"type": "STRING"}, "nome": {"type": "STRING"}, "url": {"type": "STRING"},
            "id": {"type": "STRING"}, "horas": {"type": "NUMBER"},
        },
        "required": ["action"],
    },
}

PASTA = CONFIG / "ferramentas_criadas"
_RE_NOME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")


# ── inspeção de segurança (estática) ───────────────────────────────────────────
_CHAMADAS_PROIBIDAS = {
    "os.remove", "os.unlink", "os.rmdir", "os.removedirs", "os.system", "os.popen", "os.kill",
    "os.startfile", "shutil.rmtree", "shutil.move", "send2trash.send2trash", "send2trash",
    "eval", "exec", "compile", "__import__", "ctypes.windll", "winreg.DeleteKey",
    "winreg.DeleteValue", "winreg.SetValueEx", "winreg.SetValue", "subprocess.call",
    "subprocess.Popen", "subprocess.run", "subprocess.check_output", "subprocess.check_call",
}
_METODOS_PROIBIDOS = {"unlink", "rmdir", "rmtree", "kill", "terminate", "format"}
_IMPORTS_ATENCAO = {"ctypes": "acessa funções do Windows (ctypes)", "winreg": "lê o registro do Windows",
                    "socket": "abre conexões de rede diretas", "pynput": "lê/controla teclado e mouse",
                    "pyautogui": "controla teclado e mouse", "smtplib": "envia e-mails"}
_IMPORTS_REDE = {"urllib", "requests", "httpx", "http"}


def _nome_chamada(no: ast.AST) -> str:
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        base = _nome_chamada(no.value)
        return f"{base}.{no.attr}" if base else no.attr
    return ""


def analisar_seguranca(codigo: str) -> dict:
    """{'bloqueios': [...], 'avisos': [...]} (pura)."""
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as e:
        return {"bloqueios": [f"erro de sintaxe na linha {e.lineno}"], "avisos": []}
    bloq, avisos = [], set()
    apelidos = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for a in no.names:
                apelidos[a.asname or a.name] = a.name
                top = a.name.split(".")[0]
                if top in _IMPORTS_ATENCAO:
                    avisos.add(_IMPORTS_ATENCAO[top])
                if top in _IMPORTS_REDE:
                    avisos.add("acessa a internet")
                if top == "subprocess":
                    avisos.add("importa subprocess (rodar programas)")
        elif isinstance(no, ast.ImportFrom):
            top = (no.module or "").split(".")[0]
            for a in no.names:
                apelidos[a.asname or a.name] = f"{no.module}.{a.name}"
            if top in _IMPORTS_ATENCAO:
                avisos.add(_IMPORTS_ATENCAO[top])
            if top in _IMPORTS_REDE:
                avisos.add("acessa a internet")
            if no.module == "plugins._comum" and any(a.name in ("rodar", "powershell", "rodar_como_admin")
                                                      for a in no.names):
                avisos.add("roda programas/PowerShell (sem janela)")
        elif isinstance(no, ast.Call):
            nome = _nome_chamada(no.func)
            partes = nome.split(".")
            completo = ".".join([apelidos.get(partes[0], partes[0]), *partes[1:]]) if partes[0] else nome
            if completo in _CHAMADAS_PROIBIDAS or nome in _CHAMADAS_PROIBIDAS:
                bloq.append(f"linha {no.lineno}: chama {completo}")
            elif isinstance(no.func, ast.Attribute) and no.func.attr in _METODOS_PROIBIDOS:
                bloq.append(f"linha {no.lineno}: chama .{no.func.attr}()")
            for kw in no.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    bloq.append(f"linha {no.lineno}: shell=True")
            if nome in ("open",) and len(no.args) > 1 and isinstance(no.args[1], ast.Constant) \
                    and any(c in str(no.args[1].value) for c in "wax"):
                avisos.add("grava arquivos")
            if isinstance(no.func, ast.Attribute) and no.func.attr in ("write_text", "write_bytes"):
                avisos.add("grava arquivos")
    return {"bloqueios": bloq, "avisos": sorted(avisos)}


# ── utilidades ─────────────────────────────────────────────────────────────────
_VAZIAS = set("""cria crie criar faz faca fazer um uma uns umas plugin plugins ferramenta ferramentas que me
o a os as de do da dos das pra para e depois quando se em no na nos nas com por pelo pela jarvis voce
eu meu minha isso esse essa ele ela todo toda""".split())


def slug(texto: str, limite: int = 40) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    palavras = [w for w in re.split(r"[^a-z0-9]+", t) if w and w not in _VAZIAS]
    return ("_".join(palavras[:5])[:limite].strip("_") or "ferramenta")


def nome_livre(base: str) -> str:
    base = slug(base) if not _RE_NOME.match(base or "") else base
    if base[0].isdigit():
        base = "f_" + base
    try:
        from core import registro_ferramentas
        usados = registro_ferramentas.disponiveis() | registro_ferramentas.nomes_core()
    except Exception:
        usados = set()
    usados |= {p.stem for p in (BASE / "plugins").glob("*.py")}
    usados |= {p.stem for p in PASTA.glob("*.py")} if PASTA.exists() else set()
    nome, i = base, 2
    while nome in usados:
        nome, i = f"{base}_{i}", i + 1
    return nome


def nome_no_codigo(codigo: str) -> str | None:
    try:
        for no in ast.parse(codigo).body:
            if isinstance(no, ast.Assign) and any(getattr(t, "id", "") == "PLUGIN" for t in no.targets):
                for k, v in zip(no.value.keys, no.value.values):
                    if getattr(k, "value", None) == "name" and isinstance(v, ast.Constant):
                        return str(v.value)
    except Exception:
        pass
    return None


def extrair_codigo(resposta: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", resposta or "", re.S)
    return (m.group(1) if m else (resposta or "")).strip() + "\n"


# ── modelos locais (sem IA) ────────────────────────────────────────────────────
# Páginas onde dá para ver que um jogo/app atualizou. Sem IA, o vigia usa esta tabela.
PAGINAS_CONHECIDAS = {
    "free fire": ("https://play.google.com/store/apps/details?id=com.dts.freefireth&hl=pt_BR&gl=BR",
                  r"(?:Atualizado em|Updated on)\W*(?:<[^>]+>\W*)*([0-9]{1,2}[^<]{3,24}[0-9]{4})"),
    "valorant": ("https://playvalorant.com/pt-br/news/tags/patch-notes/", ""),
    "league of legends": ("https://www.leagueoflegends.com/pt-br/news/tags/patch-notes/", ""),
    "lol": ("https://www.leagueoflegends.com/pt-br/news/tags/patch-notes/", ""),
    "minecraft": ("https://www.minecraft.net/pt-br/articles", ""),
    "fortnite": ("https://www.fortnite.com/news?lang=pt-BR", ""),
    "counter strike": ("https://www.counter-strike.net/news/updates", ""),
    "cs2": ("https://www.counter-strike.net/news/updates", ""),
    "roblox": ("https://play.google.com/store/apps/details?id=com.roblox.client&hl=pt_BR&gl=BR",
               r"(?:Atualizado em|Updated on)\W*(?:<[^>]+>\W*)*([0-9]{1,2}[^<]{3,24}[0-9]{4})"),
}

_MODELO_VIGIA = '''"""
{nome} — vigia criado pelo J.A.R.V.I.S BR em {data}.

Pedido: "{pedido}"
Confere {url} a cada {horas} h e avisa (voz, registro e celular) quando
{rotulo} mudar. Dados em memory/vigia_{nome}.json.
"""

from __future__ import annotations

import html
import re
import threading
import time
import urllib.request

from plugins._comum import MEMORIA, gravar_json, ler_json
from plugins._notificar import notificar

PLUGIN = {{
    "name": "{nome}",
    "brief": "Watches {rotulo_en} for changes.",
    "description": ("Watcher created by the user: checks {url_curta} every {horas} hours and warns when "
                    "it changes (watching: {rotulo_en}). action='verificar' checks now; 'status' tells the "
                    "last value."),
    "parameters": {{"type": "OBJECT",
                   "properties": {{"action": {{"type": "STRING", "description": "verificar | status"}}}},
                   "required": []}},
}}

URL = {url!r}
PADRAO = {padrao!r}      # trecho que interessa (regex); vazio = títulos da página
HORAS = {horas}
ROTULO = {rotulo!r}
_ARQ = MEMORIA / "vigia_{nome}.json"
_iniciado = threading.Event()


def _baixar() -> str:
    req = urllib.request.Request(URL, headers={{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                                                "Accept-Language": "pt-BR,pt;q=0.9"}})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(3_000_000).decode("utf-8", "replace")


def _limpar(t: str) -> str:
    return re.sub(r"\\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def extrair(pagina: str) -> str:
    if PADRAO:
        m = re.search(PADRAO, pagina, re.I | re.S)
        if m:
            return _limpar(m.group(1) if m.groups() else m.group(0))[:300]
    titulos = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", pagina, re.I | re.S)
    titulos = [x for x in (_limpar(t) for t in titulos) if len(x) > 3][:12]
    if not titulos:
        m = re.search(r"<title[^>]*>(.*?)</title>", pagina, re.I | re.S)
        titulos = [_limpar(m.group(1))] if m else []
    return " | ".join(titulos)[:600]


def verificar(player=None, avisar=True) -> str:
    estado = ler_json(_ARQ, {{}}) or {{}}
    try:
        atual = extrair(_baixar())
    except Exception as e:
        estado["erro"] = str(e)[:200]
        estado["conferido"] = time.time()
        gravar_json(_ARQ, estado)
        return f"Não consegui ler a página agora ({{e}})."
    if not atual:
        return "A página abriu, mas não achei o trecho que eu vigio."
    antes = estado.get("valor")
    estado.update(valor=atual, conferido=time.time(), erro="")
    if antes is None:
        msg = f"Comecei a vigiar {{ROTULO}}. Agora está: {{atual[:160]}}"
    elif antes != atual:
        estado["mudou_em"] = time.time()
        msg = f"{{ROTULO}} mudou! Agora: {{atual[:160]}}"
        if avisar:
            notificar(player, msg, titulo=ROTULO, etiqueta="VIGIA")
    else:
        msg = f"{{ROTULO}}: sem mudança. Valor atual: {{atual[:120]}}"
    gravar_json(_ARQ, estado)
    return msg


def _laco(player) -> None:
    time.sleep(90)                              # deixa o JARVIS terminar de abrir
    while True:
        estado = ler_json(_ARQ, {{}}) or {{}}
        if time.time() - float(estado.get("conferido") or 0) >= HORAS * 3600:
            try:
                verificar(player)
            except Exception as e:
                print(f"[{nome}] {{e}}")
        time.sleep(600)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="{nome}").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    acao = str((parameters or {{}}).get("action") or "verificar").lower()
    try:
        if acao == "status":
            e = ler_json(_ARQ, {{}}) or {{}}
            if not e.get("valor"):
                return f"Ainda não conferi {{ROTULO}}."
            quando = time.strftime("%d/%m %H:%M", time.localtime(e.get("conferido", 0)))
            return f"{{ROTULO}}: {{e['valor'][:160]}} (conferido em {{quando}})."
        return verificar(player, avisar=False)
    except Exception as e:
        return f"O vigia falhou: {{e}}"
'''

_MODELO_SEQUENCIA = '''"""
{nome} — ferramenta criada pelo J.A.R.V.I.S BR em {data}.

Pedido/origem: "{pedido}"
Roda, em ordem, passos que já existem no JARVIS. Cada passo passa pelo
guardião de decisões; os arriscados pedem confirmação na tela.
"""

from __future__ import annotations

PLUGIN = {{
    "name": "{nome}",
    "brief": "Runs a saved sequence: {resumo_en}",
    "description": ("User-created shortcut that runs this sequence of JARVIS tools in order: {resumo_en}. "
                    "Call it when the user asks for '{gatilho}' or this whole routine."),
    "parameters": {{"type": "OBJECT", "properties": {{}}, "required": []}},
}}

PASSOS = {passos}


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        from plugins import habilidades
        return habilidades.executar(PASSOS, player, "{nome}")
    except Exception as e:
        return f"A sequência {nome} falhou: {{e}}"
'''


def gerar_vigia(nome: str, pedido: str, url: str, padrao: str = "", horas: float = 6,
                rotulo: str = "", rotulo_en: str = "") -> str:
    dominio = re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0]
    rotulo = rotulo or f"a página {dominio}"
    rotulo_en = re.sub(r"[^\x20-\x7e]", "", rotulo_en or "") or f"the page {dominio}"
    return _MODELO_VIGIA.format(nome=nome, data=time.strftime("%d/%m/%Y"), pedido=pedido.replace('"', "'"),
                                url=url, url_curta=url.split("?")[0][:80], padrao=padrao,
                                horas=float(horas) if horas else 6.0, rotulo=rotulo, rotulo_en=rotulo_en)


def gerar_sequencia(nome: str, pedido: str, passos: list[dict]) -> str:
    resumo = "; ".join(p.get("descricao") or p.get("ferramenta") for p in passos)
    resumo_en = re.sub(r"[^\x20-\x7e]", "", resumo).replace('"', "'")[:300] or "saved steps"
    return _MODELO_SEQUENCIA.format(nome=nome, data=time.strftime("%d/%m/%Y"), pedido=pedido.replace('"', "'"),
                                    resumo_en=resumo_en, gatilho=re.sub(r"[^\x20-\x7e]", "", pedido)[:60].replace("'", ""),
                                    passos=pprint.pformat(passos, width=100, sort_dicts=False))


_RE_AVISA = re.compile(r"(?:avis|notific|alert)\w*\s+(?:quando|se)\s+(?:o\s+|a\s+|os\s+|as\s+)?(?P<alvo>.+?)\s+"
                       r"(?:atualiz|mud|lan[cç]|sai[ru]?|ficar|tiver|chegar|baixar|subir)", re.I)


def gerar_local(pedido: str, url: str = "", horas: float = 6) -> tuple[str | None, str, str]:
    """(código, nome, explicação). Código None quando não há modelo local que sirva."""
    m = _RE_AVISA.search(pedido)
    url_no_pedido = re.search(r"https?://\S+", pedido)
    if m or url or url_no_pedido:
        alvo = (m.group("alvo") if m else "").strip(" .")
        url = url or (url_no_pedido.group(0) if url_no_pedido else "")
        padrao = ""
        if not url:
            for chave, (u, pad) in PAGINAS_CONHECIDAS.items():
                if re.search(rf"\b{re.escape(chave)}\b", pedido, re.I):
                    url, padrao, alvo = u, pad, alvo or chave
                    break
        if not url:
            return None, "", (f"Para vigiar '{alvo or pedido}' sem IA eu preciso do endereço da página que "
                              "mostra a novidade. Me passe a URL.")
        nome = nome_livre(f"vigia_{slug(alvo or 'pagina', 24)}")
        rotulo = f"a atualização de {alvo}" if alvo else ""
        return (gerar_vigia(nome, pedido, url, padrao, horas, rotulo, f"{alvo} updates" if alvo else ""),
                nome, "modelo VIGIA (sem IA)")
    from plugins import habilidades
    passos = habilidades.planejar_local(re.sub(r"^.*?\b(?:que|pra|para)\s+", "", pedido, count=1))
    if passos and all(p["ferramenta"] != "manual" for p in passos):
        nome = nome_livre(slug(pedido, 40))
        return gerar_sequencia(nome, pedido, passos), nome, "modelo SEQUÊNCIA (sem IA)"
    return None, "", ("Sem IA eu só sei criar dois tipos: um VIGIA de página (\"me avisa quando X atualizar\", "
                      "com a URL) e uma SEQUÊNCIA de ferramentas que já existem. Para o resto, configure a "
                      "chave do Gemini.")


# ── geração com IA ─────────────────────────────────────────────────────────────
_REGRAS_IA = """Você escreve UM plugin Python para o J.A.R.V.I.S BR (assistente de voz em PyQt6 + Gemini Live,
Windows 10/11, Python 3.14). O arquivo vai para plugins/ e é carregado automaticamente.

CONTRATO (obrigatório)
- PLUGIN = {"name": "<snake_case, ^[a-zA-Z_][a-zA-Z0-9_]{0,63}$>", "brief": "<1 frase em inglês>",
  "description": "<inglês, até 600 caracteres: quando usar, ações e parâmetros>",
  "parameters": {"type": "OBJECT", "properties": {<nome>: {"type": "STRING"|"NUMBER"|"INTEGER"|"BOOLEAN",
  "description": "..."}}, "required": [<só propriedades que existem>]}}
- def run(parameters: dict, player=None, session_memory=None) -> str — NUNCA levanta exceção (try/except
  com mensagem); devolve UMA frase curta em português do Brasil, que o JARVIS fala.
- Aceite parameters={"action": "status"} sem efeito colateral (é usado no teste automático).
- Trabalho contínuo: def on_session_start(player) que inicia UMA thread daemon (use um threading.Event
  para não iniciar duas vezes); espere pelo menos 60 s entre verificações; primeira verificação após 60 s.

AJUDANTES DISPONÍVEIS (use-os)
- from plugins._comum import MEMORIA, CONFIG, WIN, ler_json, gravar_json, registrar, mostrar, confirmar,
  pasta_usuario, abrir_no_sistema, rodar
  ler_json(caminho, padrao) / gravar_json(caminho, dados) — guarde dados em MEMORIA / "<name>.json"
  registrar(player, texto) — escreve no registro; mostrar(player, titulo, texto) — painel de texto
  confirmar(chave, titulo, detalhe, funcao_sem_argumentos) — trava com botão na tela (devolva o retorno)
  rodar(lista_args, timeout) -> (codigo, saida) — roda programa SEM janela de console
- from plugins._notificar import notificar — notificar(player, texto, titulo="...") avisa por voz,
  registro e celular.
- IA: from core import gemini; gemini.text(prompt, tier=gemini.FAST) ou gemini.as_json(...). Nunca crie
  cliente próprio.
- Internet: urllib.request (stdlib) ou requests, sempre com timeout.
- Dependência fora da biblioteca padrão (exceto requests, psutil, numpy): importe DENTRO da função, com
  try/except ImportError devolvendo "Instale X com: pip install X".

PROIBIDO
- apagar/mover arquivos, finalizar processos, mexer no registro do Windows ou em serviços,
  shell=True, os.system, eval/exec, subprocess direto (use rodar), ctypes.
- Ações destrutivas: não faça. Se o pedido exigir, recuse naquela ação com uma frase.

Responda APENAS com o código, num único bloco ```python."""


def gerar_ia(pedido: str, nome: str, url: str = "", erros: list[str] | None = None,
             codigo_anterior: str = "") -> str | None:
    from plugins import _ia
    if not _ia.disponivel():
        return None
    prompt = _REGRAS_IA + f'\n\nPEDIDO DO USUÁRIO: "{pedido}"\nUse "name": "{nome}".'
    if url:
        prompt += f"\nURL indicada pelo usuário: {url}"
    if erros:
        prompt += ("\n\nA versão anterior falhou na validação. Corrija SÓ o necessário.\nERROS:\n- "
                   + "\n- ".join(erros) + "\n\nCÓDIGO ANTERIOR:\n```python\n" + codigo_anterior[:12000] + "\n```")
    resp = _ia.perguntar(prompt, inteligente=True, segundos=90)
    return extrair_codigo(resp) if resp else None


# ── pendentes ──────────────────────────────────────────────────────────────────
def _meta_arq(nome: str) -> Path:
    return PASTA / f"{nome}.json"


def guardar_pendente(nome: str, codigo: str, meta: dict) -> Path:
    PASTA.mkdir(parents=True, exist_ok=True)
    arq = PASTA / f"{nome}.py"
    arq.write_text(codigo, encoding="utf-8")
    gravar_json(_meta_arq(nome), meta)
    return arq


def pendentes() -> list[dict]:
    if not PASTA.exists():
        return []
    saida = []
    for m in sorted(PASTA.glob("*.json")):
        d = ler_json(m, {}) or {}
        if d.get("estado") == "pendente" and (PASTA / f"{m.stem}.py").exists():
            saida.append(d)
    return saida


def criados() -> list[dict]:
    return [ler_json(m, {}) or {} for m in sorted(PASTA.glob("*.json"))] if PASTA.exists() else []


def _resumo_revisao(meta: dict) -> str:
    v, s = meta.get("validacao", {}), meta.get("seguranca", {})
    linhas = [f"Origem: {meta.get('origem')}", f"Pedido: {meta.get('pedido')}", "",
              "TESTE DE CARREGAMENTO: " + ("OK" if v.get("ok") else "FALHOU")]
    linhas += [f"  ✖ {e}" for e in v.get("erros", [])]
    if v.get("resposta_teste"):
        linhas.append(f"  resposta ao teste: {v['resposta_teste']}")
    linhas += ["", "INSPEÇÃO DE SEGURANÇA: " + ("BLOQUEADO" if s.get("bloqueios") else "sem bloqueios")]
    linhas += [f"  ✖ {b}" for b in s.get("bloqueios", [])]
    linhas += [f"  ⚠ {a}" for a in s.get("avisos", [])]
    return "\n".join(linhas)


def criar(pedido: str, nome: str = "", url: str = "", horas: float = 6, player=None) -> dict:
    from plugins import _ia, laboratorio
    origem, explicacao = "", ""
    codigo = None
    nome_final = nome_livre(slug(nome)) if nome else ""
    if _ia.disponivel():
        nome_final = nome_final or nome_livre(slug(pedido, 40))
        codigo = gerar_ia(pedido, nome_final, url)
        origem = "IA (Gemini/provedor configurado)"
    if not codigo:
        codigo, nome_local, explicacao = gerar_local(pedido, url, horas)
        if not codigo:
            return {"ok": False, "mensagem": explicacao}
        nome_final, origem = nome_local, explicacao
    nome_cod = nome_no_codigo(codigo)
    if nome_cod and nome_cod != nome_final and _RE_NOME.match(nome_cod):
        codigo = codigo.replace(f'"name": "{nome_cod}"', f'"name": "{nome_final}"', 1)
    tentativas = 0
    while True:
        seg = analisar_seguranca(codigo)
        val = laboratorio.validar_plugin(codigo, f"{nome_final}.py", testar_run=not seg["bloqueios"])
        if (val.get("ok") and not seg["bloqueios"]) or tentativas >= 2 or not origem.startswith("IA"):
            break
        tentativas += 1
        novo = gerar_ia(pedido, nome_final, url, val.get("erros", []) + seg["bloqueios"], codigo)
        if not novo:
            break
        codigo = novo
    meta = {"nome": nome_final, "pedido": pedido, "origem": origem, "criado": time.strftime("%Y-%m-%d %H:%M"),
            "estado": "pendente", "validacao": val, "seguranca": seg, "consertos": tentativas}
    guardar_pendente(nome_final, codigo, meta)
    mostrar(player, f"PLUGIN NOVO — {nome_final}", _resumo_revisao(meta) + "\n\n" + "─" * 60 + "\n" + codigo)
    return {"ok": True, "nome": nome_final, "meta": meta}


# ── instalação ─────────────────────────────────────────────────────────────────
def instalar(nome: str, player=None) -> str:
    from plugins import _guardiao, laboratorio
    arq = PASTA / f"{nome}.py"
    meta = ler_json(_meta_arq(nome), {}) or {}
    if not arq.exists() or meta.get("estado") != "pendente":
        disponiveis = ", ".join(m["nome"] for m in pendentes()) or "nenhum"
        return f"Não tenho plugin pendente chamado '{nome}'. Pendentes: {disponiveis}."
    codigo = arq.read_text(encoding="utf-8")
    seg = analisar_seguranca(codigo)
    if seg["bloqueios"]:
        return "Não instalo: a inspeção achou " + "; ".join(seg["bloqueios"][:3]) + "."
    val = laboratorio.validar_plugin(codigo, arq.name)
    if not val.get("ok"):
        return "Não instalo: o teste de carregamento falhou — " + "; ".join(val.get("erros", [])[:3])
    destino = BASE / "plugins" / arq.name
    if destino.exists():
        return f"Já existe plugins/{arq.name}. Escolha outro nome."
    av = _guardiao.avaliar("criador_ferramentas", {"action": "instalar", "nome": nome}, f"instalar plugin {nome}")
    if av.decisao == "bloquear":
        return "O guardião bloqueou: " + av.texto()

    def fazer() -> str:
        shutil.copy2(arq, destino)
        from core import registro_ferramentas
        ok, msg = registro_ferramentas.carregar_plugin(destino)
        if not ok:
            destino.unlink(missing_ok=True)
            return f"Não consegui ativar: {msg}"
        mod = sys.modules.get(f"plugins.{destino.stem}")
        if mod is not None and callable(getattr(mod, "on_session_start", None)):
            threading.Thread(target=mod.on_session_start, args=(player,), daemon=True).start()
        meta.update(estado="instalado", instalado=time.strftime("%Y-%m-%d %H:%M"), ferramenta=msg)
        gravar_json(_meta_arq(nome), meta)
        desfazer(f"instalação do plugin {nome}", lambda: remover(nome, direto=True))
        threading.Timer(8.0, registro_ferramentas.reconectar, args=(f"plugin novo {nome}",)).start()
        return (f"Instalei e ativei o plugin {nome}. Daqui a pouco eu reconecto para passar a usá-lo "
                "pela voz.")

    avisos = ("\nAtenção: " + "; ".join(seg["avisos"])) if seg["avisos"] else ""
    return confirmar(f"criador:{nome}", f"Instalar o plugin '{nome}'?",
                     f"{meta.get('pedido', '')}\nTeste de carregamento: OK.{avisos}\n"
                     f"O código está no painel. Depois de instalar, 'desfazer' remove.", fazer)


def remover(nome: str, direto: bool = False, player=None) -> str:
    destino = BASE / "plugins" / f"{nome}.py"
    meta = ler_json(_meta_arq(nome), {}) or {}
    if not destino.exists() or meta.get("estado") != "instalado":
        return f"'{nome}' não é um plugin instalado pelo criador."

    def fazer() -> str:
        from core import registro_ferramentas
        PASTA.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destino, PASTA / destino.name)
        destino.unlink()
        registro_ferramentas.descarregar_plugin(meta.get("ferramenta") or nome)
        meta.update(estado="pendente", removido=time.strftime("%Y-%m-%d %H:%M"))
        gravar_json(_meta_arq(nome), meta)
        threading.Timer(4.0, registro_ferramentas.reconectar, args=(f"plugin removido {nome}",)).start()
        return f"Removi o plugin {nome}. Ele voltou para os pendentes, se quiser reinstalar."

    if direto:
        return fazer()
    return confirmar(f"criador_remover:{nome}", f"Remover o plugin '{nome}'?",
                     "Ele sai de plugins/ e volta para os pendentes.", fazer)


# ── sequências repetidas (ideia 7) ─────────────────────────────────────────────
_META_FERRAMENTAS = {"criador_ferramentas", "guardiao_decisoes", "oportunidades", "radar_anomalias",
                     "memoria_contrafactual", "reconstrucao", "habilidades", "conselho", "laboratorio",
                     "mapa_dependencias", "simulador", "hipoteses", "gemeo_digital", "prioridades",
                     "linha_do_tempo", "notificacoes"}


def _passo(c: dict) -> tuple[str, str, str]:
    try:
        p = json.loads(c.get("params") or "{}")
    except Exception:
        p = {}
    alvo = str(p.get("alvo") or p.get("app_name") or p.get("nome") or p.get("query") or "").lower()
    return (c["ferramenta"], c.get("acao") or "", alvo)


def sequencias_repetidas(chamadas: list[dict], janela_s: float = 600, min_vezes: int = 3,
                         tamanhos=(2, 3, 4)) -> list[dict]:
    """Sequências de 2–4 chamadas que se repetem em sessões diferentes (pura)."""
    uteis = [c for c in chamadas if c["ferramenta"] not in _META_FERRAMENTAS and c.get("ok", 1)]
    sessoes, atual, ultimo = [], [], None
    for c in uteis:
        if ultimo is not None and c["ts"] - ultimo > janela_s:
            sessoes.append(atual)
            atual = []
        atual.append(c)
        ultimo = c["ts"]
    if atual:
        sessoes.append(atual)
    contagem, dias, exemplo = Counter(), defaultdict(set), {}
    for s in sessoes:
        vistos = set()
        for n in tamanhos:
            for i in range(len(s) - n + 1):
                janela = s[i:i + n]
                chave = tuple(_passo(c) for c in janela)
                # passos repetidos dentro da janela ("volume, volume" ou A,B,A,B) não são rotina
                if len(set(chave)) < len(chave) or chave in vistos:
                    continue
                vistos.add(chave)
                contagem[chave] += 1
                dias[chave].add(time.strftime("%Y-%m-%d", time.localtime(janela[0]["ts"])))
                exemplo[chave] = janela
    achados, conjuntos = [], set()
    for k in sorted((k for k, v in contagem.items() if v >= min_vezes),
                    key=lambda k: min(c["ts"] for c in exemplo[k])):
        assinatura = (frozenset(k), contagem[k])        # A,B e B,A da mesma rotina: fica a primeira
        if assinatura in conjuntos:
            continue
        conjuntos.add(assinatura)
        achados.append(k)
    # tira as que estão contidas numa maior com a mesma frequência
    finais = []
    for k in sorted(achados, key=len, reverse=True):
        if any(len(f) > len(k) and contagem[f] >= contagem[k] and
               any(f[i:i + len(k)] == k for i in range(len(f) - len(k) + 1)) for f in finais):
            continue
        finais.append(k)
    saida = []
    for k in sorted(finais, key=lambda x: (-contagem[x] * len(x), -len(x))):
        passos = []
        for c in exemplo[k]:
            try:
                params = json.loads(c.get("params") or "{}")
            except Exception:
                params = {}
            desc = f"{c['ferramenta']} {c.get('acao') or ''}".strip()
            alvo = params.get("alvo") or params.get("app_name") or params.get("nome") or params.get("query")
            passos.append({"ferramenta": c["ferramenta"], "params": params,
                           "descricao": f"{desc} {alvo}".strip() if alvo else desc})
        ident = "seq-" + hashlib.sha1(repr(k).encode()).hexdigest()[:6]
        saida.append({"id": ident, "vezes": contagem[k], "dias": len(dias[k]), "passos": passos})
    return saida


def sugestoes(dias: int = 30) -> list[dict]:
    from core import registro_uso
    return sequencias_repetidas(registro_uso.chamadas(time.time() - dias * 86400))


# ── voz ────────────────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "criar").lower()
    nome = slug(str(p.get("nome") or ""), 64) if p.get("nome") else ""
    try:
        if acao == "criar":
            pedido = str(p.get("pedido") or "").strip()
            if not pedido:
                return "O que a ferramenta nova deve fazer?"
            r = criar(pedido, nome, str(p.get("url") or ""), float(p.get("horas") or 6), player)
            if not r["ok"]:
                return r["mensagem"]
            m = r["meta"]
            if m["seguranca"]["bloqueios"]:
                return (f"Escrevi o plugin {r['nome']}, mas a inspeção encontrou algo que eu não instalo: "
                        f"{m['seguranca']['bloqueios'][0]}. Deixei o código no painel.")
            if not m["validacao"].get("ok"):
                return (f"Escrevi o plugin {r['nome']}, mas ele não passou no teste de carregamento: "
                        f"{'; '.join(m['validacao'].get('erros', [])[:2])}. O código está no painel.")
            return (f"Criei o plugin {r['nome']} ({m['origem']}). Ele passou no teste de carregamento"
                    + (f"; atenção: {', '.join(m['seguranca']['avisos'])}" if m["seguranca"]["avisos"] else "")
                    + ". O código está no painel. Diga 'instala o plugin " + r["nome"] + "' para aprovar.")
        if acao == "instalar":
            alvo = nome or (pendentes()[-1]["nome"] if pendentes() else "")
            return instalar(alvo, player) if alvo else "Não há plugin pendente."
        if acao == "pendentes":
            lista = pendentes()
            return ("Pendentes: " + ", ".join(f"{m['nome']} ({'ok' if m.get('validacao', {}).get('ok') else 'com erro'})"
                                              for m in lista)) if lista else "Nenhum plugin esperando aprovação."
        if acao == "ver":
            arq = PASTA / f"{nome}.py"
            if not arq.exists():
                arq = BASE / "plugins" / f"{nome}.py"
            if not arq.exists():
                return f"Não achei o plugin {nome}."
            meta = ler_json(_meta_arq(nome), {}) or {}
            mostrar(player, f"PLUGIN — {nome}", (_resumo_revisao(meta) + "\n\n" if meta else "")
                    + arq.read_text(encoding="utf-8"))
            return f"Abri o código do {nome} no painel."
        if acao == "descartar":
            arq = PASTA / f"{nome}.py"
            meta = ler_json(_meta_arq(nome), {}) or {}
            if meta.get("estado") != "pendente":
                return f"'{nome}' não está pendente."
            arq.unlink(missing_ok=True)
            _meta_arq(nome).unlink(missing_ok=True)
            return f"Descartei o plugin {nome}."
        if acao == "criados":
            lista = criados()
            if not lista:
                return "Ainda não criei nenhum plugin."
            return "; ".join(f"{m.get('nome')}: {m.get('estado')}" for m in lista[-10:])
        if acao == "remover":
            return remover(nome, player=player)
        if acao == "sugestoes":
            sug = sugestoes()
            if not sug:
                return "Ainda não vi nenhuma sequência que você repita o bastante para virar ferramenta."
            mostrar(player, "SEQUÊNCIAS REPETIDAS",
                    "\n\n".join(f"[{s['id']}] {s['vezes']}x em {s['dias']} dia(s):\n  " +
                                "\n  ".join(x["descricao"] for x in s["passos"]) for s in sug[:8]))
            s = sug[0]
            return (f"Achei {len(sug)} rotina(s). A principal ({s['id']}), {s['vezes']} vezes: "
                    + ", depois ".join(x["descricao"] for x in s["passos"])
                    + ". Quer que eu transforme em uma ferramenta? Diga 'cria a sequência " + s["id"] + "'.")
        if acao == "criar_sequencia":
            ident = str(p.get("id") or "").strip()
            s = next((x for x in sugestoes() if x["id"] == ident or not ident), None)
            if not s:
                return f"Não achei a sequência {ident}."
            nome_f = nome_livre(nome or "rotina_" + slug(s["passos"][0]["descricao"], 20))
            codigo = gerar_sequencia(nome_f, f"rotina repetida {s['vezes']}x", s["passos"])
            from plugins import laboratorio
            meta = {"nome": nome_f, "pedido": f"sequência {s['id']} repetida {s['vezes']} vezes",
                    "origem": "sequência detectada no uso", "criado": time.strftime("%Y-%m-%d %H:%M"),
                    "estado": "pendente", "seguranca": analisar_seguranca(codigo),
                    "validacao": laboratorio.validar_plugin(codigo, f"{nome_f}.py", testar_run=False)}
            guardar_pendente(nome_f, codigo, meta)
            mostrar(player, f"PLUGIN NOVO — {nome_f}", _resumo_revisao(meta) + "\n\n" + codigo)
            return f"Montei a ferramenta {nome_f}. Diga 'instala o plugin {nome_f}' para aprovar."
        return "Ações: criar, sugestoes, criar_sequencia, instalar, pendentes, ver, descartar, criados, remover."
    except Exception as e:
        return f"O criador de ferramentas falhou: {e}"
