"""
Foto → post pronto — Cristal Malhas (fork PT-BR 1.4).

Você tira a foto da roupa e solta na pasta (padrão: Imagens\\Cristal Malhas\\Novas,
dá para apontar a pasta que o celular sincroniza pelo Google Fotos/OneDrive).
O JARVIS olha a peça (visão do modelo de IA) e devolve, num arquivo ao lado
da foto e no painel:

    descrição da peça · cores e detalhes · para quem (bebê/menina/menino)
    faixa de tamanhos — do SEU estoque quando a peça está cadastrada
    legenda pronta com chamada para o WhatsApp · hashtags · roteiro de Reels

Ligado ao estoque do plugin cristal_malhas: se a peça estiver cadastrada, a
legenda usa os tamanhos e a quantidade reais (e "últimas unidades" só quando
é verdade). Nunca inventa preço.

    "Jarvis, faz o post da última foto"     "Jarvis, faz o post de todas as fotos novas"

Sem chave de IA o JARVIS não enxerga a foto: monta o post pelo NOME do
arquivo (ex.: conjunto-moletom-azul.jpg) e pelo estoque, e avisa para revisar.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, pasta_usuario

PLUGIN = {
    "name": "cristal_fotos",
    "brief": "Turns a product photo of the Cristal Malhas store into a ready post (caption, hashtags, Reels script).",
    "description": (
        "Photo to ready post for the Cristal Malhas children's clothing store: looks at the garment photo "
        "(vision), writes description, size range (from the real stock when the item is registered), "
        "caption with WhatsApp call, hashtags and a Reels script; saves next to the photo. New photos in "
        "the watched folder are processed automatically. action='processar' (optional arquivo; empty = "
        "newest photo), 'todas' (all unprocessed), 'status', 'abrir_pasta'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "processar | todas | status | abrir_pasta"},
            "arquivo": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "cristal_fotos",
    "title": "Cristal Malhas — fotos para posts",
    "fields": [
        {"key": "pasta", "label": "Pasta das fotos novas (vazio = Imagens\\Cristal Malhas\\Novas)", "type": "text",
         "default": ""},
        {"key": "vigiar", "label": "Fazer o post sozinho quando chegar foto nova", "type": "toggle", "default": True},
    ],
}

_FOTOS = {".jpg", ".jpeg", ".png", ".webp"}
_ESTADO = MEMORIA / "cristal_fotos.json"
_iniciado = threading.Event()
_lock = threading.Lock()


def pasta() -> Path:
    c = cfg("cristal_fotos", PLUGIN_SETTINGS)
    return Path(c.get("pasta") or pasta_usuario("Pictures") / "Cristal Malhas" / "Novas")


# ── estoque ────────────────────────────────────────────────────────────────────
_TAMANHO = re.compile(r"\b(RN|PP|P|M|G|GG|XG|EG|\d{1,2}(?:\s*anos?)?|T\d{1,2}|tam(?:anho)?\s*\d{1,2})\b", re.I)


def separar_tamanho(produto: str) -> tuple[str, str]:
    """('conjunto moletom azul', '4') a partir de 'Conjunto moletom azul 4' (pura)."""
    achados = list(_TAMANHO.finditer(produto))
    if not achados:
        return produto.strip(), ""
    m = achados[-1]
    tam = re.sub(r"(?i)tam(?:anho)?\s*|\s*anos?|^t", "", m.group(1)).upper()
    base = (produto[:m.start()] + produto[m.end():]).strip(" -–—/")
    return re.sub(r"\s{2,}", " ", base), tam


def estoque_parecido(texto: str) -> list[dict]:
    """Itens do estoque que combinam com a peça (por palavras)."""
    try:
        from plugins._dados_br import ler, numero
        itens = ler("cristal_estoque.csv")
    except Exception:
        return []
    palavras = {w for w in re.findall(r"\w{3,}", texto.lower())} - {"com", "para", "infantil", "roupa", "peça"}
    saida = []
    for it in itens:
        nome = it.get("produto", "")
        base, tam = separar_tamanho(nome)
        comuns = palavras & set(re.findall(r"\w{3,}", base.lower()))
        if len(comuns) >= 2 or (len(comuns) == 1 and len(palavras) <= 2):
            saida.append({"produto": nome, "base": base, "tamanho": tam,
                          "quantidade": int(numero(it.get("quantidade")))})
    return saida


def resumo_estoque(itens: list[dict]) -> str:
    if not itens:
        return ""
    tams = [f"{i['tamanho'] or 'único'}: {i['quantidade']}" for i in itens if i["quantidade"] > 0]
    total = sum(i["quantidade"] for i in itens)
    return f"{itens[0]['base']} — {total} peça(s) em estoque" + (f" ({', '.join(tams)})" if tams else "")


def tamanhos_publicos(itens: list[dict]) -> str:
    """'Tamanhos 4, 6 e 8 — últimas unidades!' (sem expor a quantidade exata)."""
    tams = [i["tamanho"] for i in itens if i["quantidade"] > 0 and i["tamanho"]]
    if not tams:
        return ""
    lista = tams[0] if len(tams) == 1 else ", ".join(tams[:-1]) + " e " + tams[-1]
    total = sum(i["quantidade"] for i in itens)
    return f"Tamanho{'s' if len(tams) > 1 else ''} {lista}" + (" — últimas unidades!" if total <= 3 else "")


# ── geração ────────────────────────────────────────────────────────────────────
def _prompt(estoque_txt: str) -> str:
    c = cfg("cristal_malhas")
    fortes = c.get("pontos_fortes") or "qualidade, custo-benefício, atendimento, conforto, versatilidade, multimarcas"
    zap = (c.get("whatsapp") or "").strip()
    tom = c.get("tom") or "carinhoso"
    return ("Você é o social media da Cristal Malhas, loja de roupas INFANTIS multimarcas em Goiânia. Olhe a "
            f"peça da foto. Tom {tom}. Pontos fortes da loja (use com naturalidade): {fortes}.\n"
            + (f"ESTOQUE REAL desta peça (interno, NÃO publique quantidades): {estoque_txt}. Na legenda cite só os "
               "tamanhos disponíveis; diga 'últimas unidades' só se houver 3 ou menos no total.\n" if estoque_txt else
               "A peça NÃO está no estoque cadastrado: a faixa de tamanhos é só uma sugestão, marque como estimativa.\n")
            + (f"WhatsApp para pedidos: {zap}\n" if zap else "")
            + "Não invente preço nem promoção. Responda SÓ JSON: {\"peca\": \"nome curto\", \"descricao\": \"2 frases\", "
            "\"cores\": [\"...\"], \"publico\": \"bebê|menina|menino|unissex\", \"tamanhos\": \"faixa\", "
            "\"legenda\": \"legenda com emojis e chamada para ação\", \"hashtags\": [\"#...\"], "
            "\"roteiro\": [{\"tempo\": \"0-3s\", \"cena\": \"o que filmar\", \"texto_tela\": \"...\"}]} "
            "com 10 a 14 hashtags (amplas + locais de Goiânia) e 4 a 6 cenas.")


def _post_ia(foto: Path, estoque_txt: str) -> dict | None:
    from plugins import _ia
    if not _ia.disponivel():
        return None
    try:
        from google.genai import types as gtypes
        from core import gemini
        dados = foto.read_bytes()
        mime = "image/png" if foto.suffix.lower() == ".png" else "image/webp" if foto.suffix.lower() == ".webp" else "image/jpeg"
        try:                                                 # fotos de celular são grandes: reduz
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(dados)).convert("RGB")
            im.thumbnail((1600, 1600))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            dados, mime = buf.getvalue(), "image/jpeg"
        except Exception:
            pass
        resp = gemini.call([gtypes.Part.from_bytes(data=dados, mime_type=mime), _prompt(estoque_txt)],
                           tier=gemini.SMART, timeout_ms=60_000)
        texto = (getattr(resp, "text", "") or "") if resp is not None else ""
        texto = texto[texto.find("{"): texto.rfind("}") + 1]
        return json.loads(texto) if texto else None
    except Exception as e:
        print(f"[CristalFotos] IA: {e}")
        return None


def _post_local(foto: Path, estoque_txt: str, publico_tam: str = "") -> dict:
    nome = re.sub(r"[_\-]+", " ", foto.stem)
    nome = re.sub(r"\b(img|dsc|whatsapp image|image|foto|\d{6,})\b", " ", nome, flags=re.I)
    nome = re.sub(r"\s{2,}", " ", nome).strip() or "nova peça"
    c = cfg("cristal_malhas")
    zap = (c.get("whatsapp") or "").strip()
    legenda = (f"✨ Chegou novidade na Cristal Malhas: {nome}! ✨\n"
               "Conforto e estilo para os pequenos aproveitarem cada momento. 💛\n"
               + (f"📏 {publico_tam}\n" if publico_tam else "")
               + (f"📲 Peça pelo WhatsApp: {zap}" if zap else "📲 Chame a gente no direct!"))
    return {"peca": nome, "descricao": "(sem IA: revise a descrição olhando a foto)", "cores": [], "publico": "",
            "tamanhos": estoque_txt or "(cadastre a peça no estoque para mostrar os tamanhos)",
            "legenda": legenda,
            "hashtags": ["#cristalmalhas", "#modainfantil", "#roupainfantil", "#lookinfantil", "#goiania",
                         "#modainfantilgoiania", "#novidade", "#kids", "#infantil", "#lojainfantil"],
            "roteiro": [{"tempo": "0-3s", "cena": "a peça inteira em movimento", "texto_tela": "Chegou! 😍"},
                        {"tempo": "3-8s", "cena": "detalhes: tecido, estampa, acabamento", "texto_tela": nome},
                        {"tempo": "8-12s", "cena": "a peça vestida ou no cabide com acessórios", "texto_tela": "Conforto para brincar"},
                        {"tempo": "12-15s", "cena": "logo da loja", "texto_tela": "Peça já no WhatsApp 📲"}]}


def texto_post(d: dict) -> str:
    linhas = [f"PEÇA: {d.get('peca', '')}", f"PARA: {d.get('publico', '')}  ·  CORES: {', '.join(d.get('cores', []))}",
              f"TAMANHOS: {d.get('tamanhos', '')}", "", d.get("descricao", ""), "", "LEGENDA", d.get("legenda", ""),
              "", " ".join(d.get("hashtags", [])), "", "ROTEIRO DO REELS"]
    for c in d.get("roteiro", []):
        linhas.append(f"[{c.get('tempo', '')}] {c.get('cena', '')}" + (f"  — tela: {c['texto_tela']}" if c.get("texto_tela") else ""))
    return "\n".join(linhas)


def processar(foto: Path, player=None) -> dict:
    nome_base = re.sub(r"[_\-]+", " ", foto.stem)
    itens = estoque_parecido(nome_base)
    estoque_txt = resumo_estoque(itens)
    d = _post_ia(foto, estoque_txt)
    origem = "IA (visão)"
    if not d:
        d, origem = _post_local(foto, estoque_txt, tamanhos_publicos(itens)), "sem IA (pelo nome do arquivo)"
    elif not estoque_txt:                     # a IA deu nome à peça: tenta o estoque de novo com ele
        itens = estoque_parecido(f"{d.get('peca', '')} {' '.join(d.get('cores', []))}")
        if itens:
            d["tamanhos"] = resumo_estoque(itens)
    d["origem"] = origem
    texto = texto_post(d)
    destino = foto.parent / "posts"
    destino.mkdir(exist_ok=True)
    (destino / f"{foto.stem}.txt").write_text(texto, encoding="utf-8")
    (destino / f"{foto.stem}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    with _lock:
        est = ler_json(_ESTADO, {}) or {}
        est[str(foto)] = {"quando": time.time(), "origem": origem}
        gravar_json(_ESTADO, est)
    mostrar(player, f"POST — {d.get('peca', foto.name)[:40]}", texto)
    return d


def novas(dentro_de: Path | None = None) -> list[Path]:
    p = dentro_de or pasta()
    if not p.is_dir():
        return []
    feitas = ler_json(_ESTADO, {}) or {}
    agora = time.time()
    return sorted((f for f in p.iterdir() if f.suffix.lower() in _FOTOS and str(f) not in feitas
                   and agora - f.stat().st_mtime > 5), key=lambda f: f.stat().st_mtime)


def _laco(player) -> None:
    time.sleep(60)
    while True:
        try:
            c = cfg("cristal_fotos", PLUGIN_SETTINGS)
            if str(c.get("vigiar", True)).lower() not in ("false", "0", "nao", "não"):
                for foto in novas()[:5]:
                    d = processar(foto, player)
                    from plugins._notificar import notificar
                    notificar(player, f"Post pronto para a foto {foto.name}: {d.get('peca', '')}. Está na pasta posts.",
                              titulo="Cristal Malhas", etiqueta="POST")
        except Exception as e:
            print(f"[CristalFotos] {e}")
        time.sleep(30)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        pasta().mkdir(parents=True, exist_ok=True)
        threading.Thread(target=_laco, args=(player,), daemon=True, name="cristal_fotos").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "processar").lower()
    try:
        alvo = pasta()
        if acao == "abrir_pasta":
            from plugins._comum import abrir_no_sistema
            alvo.mkdir(parents=True, exist_ok=True)
            abrir_no_sistema(str(alvo))
            return "Abri a pasta das fotos. Solte as fotos novas lá."
        if acao == "status":
            return f"Pasta: {alvo}. {len(novas())} foto(s) esperando post."
        if acao == "todas":
            lista = novas()
            if not lista:
                return "Não há foto nova sem post."
            for f in lista[:10]:
                processar(f, player)
            return f"Fiz {min(10, len(lista))} post(s). Estão na pasta posts, ao lado das fotos."
        arq = str(p.get("arquivo") or "").strip()
        if arq:
            foto = Path(arq) if Path(arq).is_file() else next((f for f in alvo.glob("*") if arq.lower() in f.name.lower()
                                                               and f.suffix.lower() in _FOTOS), None)
        else:
            fotos = sorted((f for f in alvo.glob("*") if f.suffix.lower() in _FOTOS), key=lambda f: f.stat().st_mtime) \
                if alvo.is_dir() else []
            foto = fotos[-1] if fotos else None
        if not foto:
            alvo.mkdir(parents=True, exist_ok=True)
            return f"Não achei a foto. Coloque as fotos em {alvo}."
        d = processar(foto, player)
        return (f"Post pronto ({d['origem']}): {d.get('peca', '')}. Tamanhos: {d.get('tamanhos', '')}. "
                "A legenda, as hashtags e o roteiro estão no painel e na pasta posts.")
    except Exception as e:
        return f"Não consegui fazer o post: {e}"
