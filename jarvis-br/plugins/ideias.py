"""
Caixinha de ideias (fork PT-BR 2.5).

    "Jarvis, anota uma ideia: app de estoque pra lojas pequenas."
    "Jarvis, quais ideias eu tenho de música?"      "Jarvis, mostra minhas ideias"
    "Jarvis, acrescenta na ideia do app de estoque: dá pra vender por assinatura"
    "Jarvis, a ideia do app de estoque vira projeto"

As ideias ficam separadas por tema (programação, loja, música, conteúdo, jogos,
casa, estudo, negócio… ou o tema que a IA sugerir). Todo DOMINGO ele lembra
das ideias paradas há mais de duas semanas e pergunta se alguma vira projeto.
"Virar projeto" cria a pasta Documentos\\JARVIS\\projetos\\<nome> com a ideia,
as suas notas e um primeiro plano (com a chave do Gemini). Tudo em
memory/ideias.json.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from datetime import date, datetime

from plugins._comum import MEMORIA, abrir_no_sistema, gravar_json, ler_json, mostrar, pasta_usuario

PLUGIN = {
    "name": "ideias",
    "brief": "Idea box: saves ideas by theme, Sunday review of stalled ideas, turns an idea into a project folder.",
    "description": (
        "Idea box. action='anotar' with texto (the idea, in the user's words). 'listar' (optional tema). 'nota' with "
        "ideia (id or words) and texto: adds a thought to an idea. 'projeto' with ideia: turns it into a project "
        "(folder + first plan). 'arquivar' with ideia. 'revisar': the review of stalled ideas now. Every Sunday "
        "JARVIS reminds of stalled ideas by himself."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "anotar | listar | nota | projeto | arquivar | revisar"},
            "texto": {"type": "STRING"}, "ideia": {"type": "STRING"}, "tema": {"type": "STRING"},
        },
        "required": [],
    },
}

ARQ = MEMORIA / "ideias.json"
_lock = threading.Lock()
_iniciou = threading.Event()
PARADA_DIAS = 14
TEMAS = [
    ("programação", r"\bapp\b|aplicativo|sistema|software|site|programa|bot\b|api\b|script|automat|plugin|extens"),
    ("loja", r"\bloja\b|cliente|estoque|venda|vender|malha|roupa|cole[çc][ãa]o|pe[çc]a|fornecedor|vitrine"),
    ("música", r"m[úu]sica|\brap\b|beat|letra|rima|clipe|\bfeat\b|[áa]lbum|\bep\b|batida"),
    ("conteúdo", r"v[íi]deo|youtube|tiktok|reels|canal|\blive\b|post|instagram|podcast|roteiro"),
    ("jogos", r"\bjogo|game|roblox|minecraft|fase|personagem|\bmapa\b"),
    ("casa", r"\bcasa\b|quarto|cozinha|reforma|m[óo]vel|jardim|planta|\bled\b|decora"),
    ("estudo", r"estud|curso|aprender|livro|faculdade|prova|ingl[êe]s"),
    ("negócio", r"neg[óo]cio|empresa|startup|assinatura|lucro|marketing|marca|produto"),
]


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def tema_por_regra(texto: str) -> str:
    t = str(texto or "").lower()
    for nome, padrao in TEMAS:
        if re.search(padrao, t):
            return nome
    return "outros"


def tema_de(texto: str, existentes: list[str]) -> str:
    regra = tema_por_regra(texto)
    if regra != "outros":
        return regra
    try:
        from plugins import _ia
        j = _ia.perguntar_json(
            f"Classifique esta ideia num TEMA curto (1 ou 2 palavras, minúsculas, em português). Prefira um destes se "
            f"servir: {', '.join(sorted(set(existentes + [n for n, _p in TEMAS])))}. Ideia: \"{texto}\". "
            "Responda {\"tema\": \"...\"}.", inteligente=False, segundos=15)
        tema = str((j or {}).get("tema") or "").strip().lower()[:24]
        return tema or "outros"
    except Exception:
        return "outros"


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("ideias", [])
    d.setdefault("ultimo_domingo", "")
    return d


def _gravar(d: dict) -> None:
    gravar_json(ARQ, d)


def achar(ideias: list[dict], termo: str) -> list[dict]:
    t = str(termo or "").strip()
    if t.lstrip("#").isdigit():
        return [i for i in ideias if i["id"] == int(t.lstrip("#"))]
    ps = [w for w in re.findall(r"[a-z0-9]+", _dobrar(t)) if len(w) > 2 and w not in ("ideia", "que", "pra", "para",
                                                                                         "uma", "das", "dos", "com")]
    if not ps:
        return []
    notas = []
    for i in ideias:
        alvo = _dobrar(i["texto"] + " " + " ".join(i.get("notas") or []))
        n = sum(1 for w in ps if w in alvo)
        if n:
            notas.append((n, i))
    if not notas:
        return []
    melhor = max(n for n, _i in notas)
    return [i for n, i in notas if n == melhor]


def paradas(ideias: list[dict], hoje: float, dias: int = PARADA_DIAS) -> list[dict]:
    """Ideias abertas sem mexer há `dias` dias, das mais velhas para as mais novas (puro)."""
    abertas = [i for i in ideias if i.get("status", "nova") in ("nova", "pensando")
               and hoje - i.get("mexida", i["criada"]) >= dias * 86400]
    return sorted(abertas, key=lambda i: i.get("mexida", i["criada"]))


def frase_domingo(lista: list[dict]) -> str:
    if not lista:
        return ""
    nomes = [f"“{i['texto'][:60]}”" for i in lista[:3]]
    junto = nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
    resto = f" (e mais {len(lista) - 3})" if len(lista) > 3 else ""
    if len(lista) == 1:
        return f"Domingo das ideias: a ideia {junto} está parada há um tempo. Vira projeto essa semana?"
    return f"Domingo das ideias: {len(lista)} ideias paradas — {junto}{resto}. Alguma vira projeto essa semana?"


def _descrever(i: dict) -> str:
    st = {"nova": "", "pensando": " · pensando", "projeto": " · VIROU PROJETO", "arquivada": " · arquivada"}
    notas = f" (+{len(i['notas'])} nota{'s' if len(i['notas']) > 1 else ''})" if i.get("notas") else ""
    return f"#{i['id']} {i['texto']}{notas}{st.get(i.get('status', 'nova'), '')}"


def anotar(texto: str, tema: str = "") -> str:
    texto = " ".join(str(texto or "").split()).strip(" .")
    if len(texto) < 3:
        return "Qual é a ideia?"
    texto = texto[0].upper() + texto[1:]
    with _lock:
        d = dados()
        existentes = sorted({i.get("tema", "outros") for i in d["ideias"]})
    tema = (tema or "").strip().lower() or tema_de(texto, existentes)
    with _lock:
        d = dados()
        igual = next((i for i in d["ideias"] if _dobrar(i["texto"]) == _dobrar(texto)), None)
        if igual:
            return f"Essa já está na caixinha: {_descrever(igual)}."
        i = {"id": max([x["id"] for x in d["ideias"]], default=0) + 1, "texto": texto, "tema": tema,
             "criada": time.time(), "mexida": time.time(), "status": "nova", "notas": []}
        d["ideias"].append(i)
        _gravar(d)
        mesmas = sum(1 for x in d["ideias"] if x.get("tema") == tema and x.get("status") != "arquivada")
    return f"Anotei na caixinha, tema {tema} (#{i['id']}). Você tem {mesmas} ideia{'s' if mesmas > 1 else ''} de {tema}."


def virar_projeto(i: dict) -> str:
    from plugins._comum import nome_usuario
    slug = re.sub(r"[^a-z0-9]+", "-", _dobrar(i["texto"]))[:40].strip("-") or f"ideia-{i['id']}"
    pasta = pasta_usuario("Documents") / "JARVIS" / "projetos" / slug
    pasta.mkdir(parents=True, exist_ok=True)
    plano = ""
    try:
        from plugins import _ia
        plano = _ia.perguntar(
            f"Transforme esta ideia num primeiro plano curto, em português do Brasil, em Markdown: 1) o que é em uma "
            f"frase, 2) a menor versão que já serve (3 a 5 itens), 3) os 3 primeiros passos desta semana, 4) um risco. "
            f"Ideia: {i['texto']}. Notas: {'; '.join(i.get('notas') or []) or 'nenhuma'}.", inteligente=True,
            segundos=40) or ""
    except Exception:
        plano = ""
    corpo = [f"# {i['texto']}", "", f"Ideia #{i['id']} da caixinha do JARVIS · tema {i.get('tema', 'outros')} · "
             f"anotada em {datetime.fromtimestamp(i['criada']).strftime('%d/%m/%Y')}"
             + (f" por {nome_usuario()}" if nome_usuario() else ""), ""]
    if i.get("notas"):
        corpo += ["## Notas", ""] + [f"- {n}" for n in i["notas"]] + [""]
    corpo += ["## Primeiro plano", "", plano.strip() or "- [ ] O que é em uma frase:\n- [ ] A menor versão que já serve:\n"
              "- [ ] Os 3 primeiros passos:", ""]
    (pasta / "IDEIA.md").write_text("\n".join(corpo), encoding="utf-8")
    abrir_no_sistema(str(pasta))
    dica = " Se for programa, diga 'cria o projeto' que eu monto o código." if i.get("tema") == "programação" else ""
    return f"Virou projeto! Criei {pasta} com a ideia e um primeiro plano.{dica}"


def revisar(automatico: bool = False) -> str:
    with _lock:
        d = dados()
        lista = paradas(d["ideias"], time.time())
        if automatico:
            d["ultimo_domingo"] = date.today().isoformat()
            _gravar(d)
    return frase_domingo(lista)


def _laco() -> None:
    time.sleep(150)
    while True:
        agora = datetime.now()
        try:
            if agora.weekday() == 6 and 10 <= agora.hour < 20 and dados()["ultimo_domingo"] != date.today().isoformat():
                texto = revisar(automatico=True)
                if texto:
                    from plugins._notificar import notificar
                    notificar(None, texto, titulo="Ideias", etiqueta="IDEIAS")
        except Exception as e:
            print(f"[Ideias] {e}")
        time.sleep(1800)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="ideias").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "anotar":
            return anotar(str(p.get("texto") or p.get("ideia") or ""), str(p.get("tema") or ""))
        if acao == "revisar":
            return revisar() or "Nenhuma ideia parada: todas foram mexidas nas últimas duas semanas."
        if acao in ("nota", "projeto", "arquivar"):
            with _lock:
                d = dados()
                alvo = achar(d["ideias"], str(p.get("ideia") or ""))
                if not alvo:
                    return "Não achei essa ideia na caixinha."
                if len(alvo) > 1:
                    return "Achei mais de uma: " + "; ".join(_descrever(i) for i in alvo[:4]) + ". Qual delas?"
                i = alvo[0]
                i["mexida"] = time.time()
                if acao == "nota":
                    if not p.get("texto"):
                        return "O que eu acrescento na ideia?"
                    i.setdefault("notas", []).append(str(p["texto"]).strip())
                    i["status"] = "pensando" if i.get("status") == "nova" else i.get("status")
                elif acao == "arquivar":
                    i["status"] = "arquivada"
                else:
                    i["status"] = "projeto"
                _gravar(d)
            if acao == "nota":
                return f"Acrescentei na ideia #{i['id']}."
            if acao == "arquivar":
                return f"Arquivei a ideia #{i['id']}."
            return virar_projeto(i)
        d = dados()
        tema = str(p.get("tema") or "").strip().lower()
        ideias = [i for i in d["ideias"] if i.get("status") != "arquivada"
                  and (not tema or _dobrar(tema) in _dobrar(i.get("tema", "")))]
        if not ideias:
            return f"Nenhuma ideia{' de ' + tema if tema else ''} na caixinha ainda. Diga 'anota uma ideia: …'."
        por_tema: dict[str, list] = {}
        for i in ideias:
            por_tema.setdefault(i.get("tema", "outros"), []).append(i)
        texto = "\n\n".join(f"{t.upper()} ({len(v)})\n" + "\n".join("• " + _descrever(i) for i in v)
                            for t, v in sorted(por_tema.items(), key=lambda kv: -len(kv[1])))
        mostrar(player, "CAIXINHA DE IDEIAS", texto)
        return texto
    except Exception as e:
        return f"A caixinha de ideias falhou: {e}"
