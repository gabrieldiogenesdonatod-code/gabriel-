"""
Garantias e manuais (fork PT-BR 2.5).

    "Jarvis, guarda a garantia: comprei um roteador hoje"   (+ foto da nota)
    "Jarvis, olha essa nota fiscal"            (mostre a nota para a webcam)
    "Jarvis, quando acaba a garantia da geladeira?"
    "Jarvis, como reseto o roteador?"          (acha o manual em PDF e responde pelo manual)

A FOTO DA NOTA pode vir de: um arquivo (caminho), a webcam ("olha essa nota"),
ou a última imagem/PDF que chegou na pasta "JARVIS Uploads" (o celular manda
pelo painel) ou em Downloads nos últimos 15 minutos. Com a chave do Gemini ele
lê produto, loja, data, valor e meses de garantia; sem chave, você dita.

Ele avisa 30 dias e 7 dias antes de acabar ("A garantia do roteador acaba em
30 dias, dia 10/03. Se tiver algum defeito, é hora de acionar.").

MANUAIS: procura "<marca> <modelo> manual pdf" na internet, baixa o PDF para
memory/manuais e responde pelo texto do manual (com a página). Tudo fica só no
seu PC (memory/garantias.json, memory/garantias/ e memory/manuais/).
"""

from __future__ import annotations

import calendar
import re
import threading
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

from plugins._comum import MEMORIA, abrir_no_sistema, gravar_json, ler_json, mostrar, pasta_usuario

PLUGIN = {
    "name": "garantias",
    "brief": "Warranties from receipt photos (alerts before they end) and answers from product manuals (PDF).",
    "description": (
        "Warranties and manuals. action='nota' reads a purchase receipt (arquivo path, or camera=true to look "
        "at the webcam, or empty = newest image/PDF just received) and saves the warranty; optional produto and "
        "meses. 'adicionar' with produto, data (dd/mm/aaaa), meses, loja, valor (no photo). 'listar'. 'quando' "
        "with produto: when the warranty ends. 'manual' with pergunta (e.g. 'como reseto o roteador') and "
        "optional produto (brand + model if known): finds the PDF manual and answers from it. 'abrir_manual' "
        "with produto. 'apagar' with id. JARVIS warns 30 and 7 days before a warranty ends."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "nota | adicionar | listar | quando | manual | abrir_manual | apagar"},
            "arquivo": {"type": "STRING"}, "camera": {"type": "BOOLEAN"}, "produto": {"type": "STRING"},
            "data": {"type": "STRING"}, "meses": {"type": "INTEGER"}, "loja": {"type": "STRING"},
            "valor": {"type": "NUMBER"}, "pergunta": {"type": "STRING"}, "id": {"type": "INTEGER"},
        },
        "required": [],
    },
}

ARQ = MEMORIA / "garantias.json"
PASTA_NOTAS = MEMORIA / "garantias"
PASTA_MANUAIS = MEMORIA / "manuais"
_lock = threading.Lock()
_iniciou = threading.Event()
MESES_PADRAO = 12
PALAVRAS_VAZIAS = set("""a o as os um uma de da do das dos e em no na nos nas para pra por com como que qual quais
meu minha meus minhas seu sua isso esse essa este esta eu voce você ele ela se ao à é tem ter fazer faço faco
jarvis manual pdf""".split())
SINONIMOS = {
    "reset": ["reset", "resetar", "reseto", "restaurar", "restaure", "redefinir", "padrao de fabrica", "factory",
              "reiniciar", "restore", "configuracoes de fabrica"],
    "senha": ["senha", "password", "wifi", "wi-fi", "ssid", "chave de rede"],
    "limpar": ["limpar", "limpeza", "limpo", "clean", "cleaning", "higienizar"],
    "parear": ["parear", "pareamento", "emparelhar", "bluetooth", "pairing", "pair", "conectar"],
    "erro": ["erro", "codigo de erro", "error", "falha", "pisca", "piscando", "led", "luz"],
    "instalar": ["instalar", "instalacao", "install", "montar", "montagem", "setup"],
    "atualizar": ["atualizar", "firmware", "update", "atualizacao"],
}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _dobrar(t)).strip("-")[:60] or "produto"


# ── datas (puro) ───────────────────────────────────────────────────────────────
def somar_meses(d: date, meses: int) -> date:
    m = d.month - 1 + int(meses)
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def ler_data(t: str) -> date | None:
    t = str(t or "").strip()
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", t)
    if not m:
        return None
    a = int(m.group(3))
    try:
        return date(a + 2000 if a < 100 else a, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def nome_curto(item: dict) -> str:
    """'o roteador', 'a geladeira' — como falar do produto."""
    tipo = str(item.get("tipo") or "").strip().lower()
    base = tipo or str(item.get("produto") or "produto").strip()
    w = (palavras(base) or ["x"])[0]
    fem = w in ("tv", "smart", "air", "alexa") or (w.endswith(("a", "sao", "cao", "agem", "dade"))
                                                   and not w.endswith(("ma", "sofa")))
    return f"{'a' if fem else 'o'} {base}"


def avisos_devidos(itens: list[dict], hoje: date) -> list[tuple[dict, str]]:
    saida = []
    for it in itens:
        if not it.get("fim"):
            continue
        n = (date.fromisoformat(it["fim"]) - hoje).days
        feitos = it.get("avisos") or {}
        if 0 <= n <= 7 and "7" not in feitos:
            saida.append((it, "7"))
        elif 7 < n <= 30 and "30" not in feitos:
            saida.append((it, "30"))
    return saida


def frase_aviso(item: dict, tipo: str, hoje: date) -> str:
    fim = date.fromisoformat(item["fim"])
    n = (fim - hoje).days
    quando = "hoje" if n == 0 else "amanhã" if n == 1 else f"em {n} dias"
    nome = nome_curto(item)
    return (f"A garantia d{nome} acaba {quando}, dia {fim.strftime('%d/%m')}. "
            f"Se tiver algum defeito, é hora de acionar.")


def quando_acaba(item: dict, hoje: date) -> str:
    if not item.get("fim"):
        return f"Não sei quando acaba a garantia d{nome_curto(item)}."
    fim = date.fromisoformat(item["fim"])
    n = (fim - hoje).days
    base = f"A garantia d{nome_curto(item)} ({item.get('produto')})"
    if n < 0:
        return f"{base} acabou em {fim.strftime('%d/%m/%Y')}."
    meses = n // 30
    falta = f"{n} dias" if n < 60 else f"uns {meses} meses"
    return f"{base} vai até {fim.strftime('%d/%m/%Y')} — faltam {falta}."


# ── achar o produto da pergunta (puro) ─────────────────────────────────────────
def palavras(t: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", _dobrar(t)) if w not in PALAVRAS_VAZIAS and len(w) > 1]


def nome_bom(nome: str) -> bool:
    """Dá para procurar o manual? Precisa de marca + modelo ('TP-Link Archer C6'), não só 'lava-louças'."""
    ws = palavras(nome)
    return len(ws) >= 3 or (len(ws) >= 2 and any(ch.isdigit() for ch in nome))


def item_da_pergunta(itens: list[dict], texto: str) -> dict | None:
    ps = set(palavras(texto))
    melhor, nota = None, 0
    for it in itens:
        alvo = set(palavras(" ".join(str(it.get(k) or "") for k in ("tipo", "produto", "marca", "modelo"))))
        n = len(ps & alvo) + (2 if _dobrar(it.get("tipo") or "-") in _dobrar(texto) else 0)
        if n > nota:
            melhor, nota = it, n
    return melhor


def trechos_relevantes(paginas: list[str], pergunta: str, n: int = 5) -> list[tuple[int, str]]:
    """Os pedaços do manual que mais têm a ver com a pergunta: [(página, texto)] (puro)."""
    termos = set(palavras(pergunta))
    extra = []
    for _k, lista in SINONIMOS.items():
        if any(_dobrar(s) in _dobrar(pergunta) for s in lista):
            extra += lista
    candidatos = []
    for i, pag in enumerate(paginas, 1):
        blocos = []
        for b in re.split(r"\n\s*\n", pag):
            linhas = [x for x in b.strip().splitlines() if x.strip()]
            if len(linhas) <= 12:
                blocos.append("\n".join(linhas))
            else:                                               # página sem linhas em branco: janelas de 8 linhas
                blocos += ["\n".join(linhas[k:k + 8]) for k in range(0, len(linhas) - 4, 4)]
        for b in (x for x in blocos if len(x) > 30):
            d = _dobrar(b)
            nota = sum(d.count(t) for t in termos) + 2 * sum(1 for s in extra if _dobrar(s) in d)
            if re.search(r"(^|\n)\s*(\d+[.)]|passo|step|•)", b, re.I):
                nota += 0.5                                     # parece passo a passo
            if nota > 0:
                candidatos.append((nota, i, b[:900]))
    candidatos.sort(key=lambda x: -x[0])
    vistos, saida = set(), []
    for _nota, pag, b in candidatos:
        if b[:80] in vistos:
            continue
        vistos.add(b[:80])
        saida.append((pag, b))
        if len(saida) >= n:
            break
    return saida


# ── dados ─────────────────────────────────────────────────────────────────────
def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("itens", [])
    d.setdefault("manuais", {})
    return d


def _gravar(d: dict) -> None:
    gravar_json(ARQ, d)


def _novo_item(info: dict, origem: str, nota: str = "") -> dict:
    compra = ler_data(str(info.get("data_compra") or "")) or date.today()
    try:
        meses = int(info.get("garantia_meses") or info.get("meses") or MESES_PADRAO)
    except (TypeError, ValueError):
        meses = MESES_PADRAO
    with _lock:
        d = dados()
        it = {"id": max([x["id"] for x in d["itens"]], default=0) + 1,
              "produto": str(info.get("produto") or info.get("tipo") or "produto").strip()[:80],
              "tipo": str(info.get("tipo") or "").strip().lower()[:30],
              "marca": str(info.get("marca") or "").strip()[:40], "modelo": str(info.get("modelo") or "").strip()[:60],
              "loja": str(info.get("loja") or "").strip()[:60], "valor": info.get("valor"),
              "data_compra": compra.isoformat(), "meses": meses, "fim": somar_meses(compra, meses).isoformat(),
              "numero_nota": str(info.get("numero_nota") or "")[:60], "nota": nota, "origem": origem,
              "criado": time.time(), "avisos": {}}
        d["itens"].append(it)
        _gravar(d)
    return it


def _descrever(it: dict) -> str:
    fim = date.fromisoformat(it["fim"]).strftime("%d/%m/%Y") if it.get("fim") else "?"
    partes = [f"#{it['id']} {it['produto']}"] + ([it["loja"]] if it.get("loja") else []) + \
        [f"compra em {date.fromisoformat(it['data_compra']).strftime('%d/%m/%Y')}"]
    return ", ".join(partes) + f" — garantia de {it['meses']} meses, até {fim}" + (" · tem manual" if it.get("manual")
                                                                                  else "")


# ── a nota fiscal ─────────────────────────────────────────────────────────────
PROMPT_NOTA = (
    "Isto é uma nota fiscal, cupom ou comprovante de compra brasileiro. Devolva SÓ um JSON: {\"produto\": \"nome "
    "curto do produto principal (ex.: Roteador TP-Link Archer C6)\", \"tipo\": \"o que é, 1 ou 2 palavras em "
    "minúsculas (ex.: roteador, geladeira, celular, fone)\", \"marca\": \"…\", \"modelo\": \"…\", \"loja\": \"…\", "
    "\"data_compra\": \"dd/mm/aaaa\", \"valor\": número, \"garantia_meses\": número SÓ se a garantia estiver escrita, "
    "senão null, \"numero_nota\": \"…\"}. Se houver vários produtos, use o mais caro. Use null no que não der para ler.")


def _imagem_recente(minutos: int = 15) -> Path | None:
    pastas = [Path.home() / "Downloads" / "JARVIS Uploads", Path.home() / "Documents" / "JARVIS Uploads",
              pasta_usuario("Downloads")]
    limite = time.time() - minutos * 60
    achados = []
    for p in pastas:
        if p.is_dir():
            for f in p.iterdir():
                try:
                    if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf") and \
                            f.stat().st_mtime >= limite:
                        achados.append(f)
                except OSError:
                    pass
    return max(achados, key=lambda f: f.stat().st_mtime) if achados else None


def ler_nota(arquivo: str = "", camera: bool = False, produto: str = "", meses: int | None = None) -> str:
    from plugins import _ia
    PASTA_NOTAS.mkdir(parents=True, exist_ok=True)
    if camera:
        from plugins import _camera_remota
        img, erro = _camera_remota.foto_jpeg(0, largura=1600, qualidade=90)
        if not img:
            return f"Não consegui ver pela câmera: {erro}."
        origem, bruto, sufixo = "câmera", img, ".jpg"
    else:
        caminho = Path(arquivo).expanduser() if arquivo else _imagem_recente()
        if not caminho or not caminho.exists():
            return ("Não achei a foto da nota. Mande pelo painel do celular (📎), passe o caminho do arquivo ou diga "
                    "'olha a nota' e mostre para a webcam.")
        origem, bruto, sufixo = caminho.name, caminho.read_bytes(), caminho.suffix.lower()
    info = None
    if sufixo == ".pdf":
        from plugins._boleto import texto_do_pdf
        tmp = PASTA_NOTAS / f"_tmp{int(time.time())}.pdf"
        tmp.write_bytes(bruto)
        texto = texto_do_pdf(tmp)
        tmp.unlink(missing_ok=True)
        info = _ia.perguntar_json(PROMPT_NOTA + "\n\nTEXTO DA NOTA:\n" + texto[:6000], inteligente=False) \
            if texto else None
    else:
        info = _ia.ver_imagem_json(PROMPT_NOTA, bruto, inteligente=True)
    if not isinstance(info, dict):
        if not produto:
            return ("Guardei a imagem, mas não consegui ler a nota (preciso da chave do Gemini para ler fotos). Me diga "
                    "o produto, a data da compra e os meses de garantia que eu anoto.")
        info = {}
    if produto:
        info["produto"] = produto
        info.setdefault("tipo", palavras(produto)[0] if palavras(produto) else "")
    if meses:
        info["garantia_meses"] = meses
    it = _novo_item(info, origem)
    destino = PASTA_NOTAS / f"{it['id']}{sufixo if sufixo in ('.pdf', '.png', '.webp') else '.jpg'}"
    destino.write_bytes(bruto)
    with _lock:
        d = dados()
        for x in d["itens"]:
            if x["id"] == it["id"]:
                x["nota"] = str(destino)
        _gravar(d)
    padrao = "" if info.get("garantia_meses") else f" (a nota não diz a garantia: contei {it['meses']} meses — é só me " \
                                                   f"corrigir se for outra)"
    return f"Guardei: {_descrever(it)}{padrao}. Aviso 30 dias antes de acabar."


# ── manuais ───────────────────────────────────────────────────────────────────
def _baixar_pdf(url: str, destino: Path, limite_mb: int = 40) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS-BR/2.5"})
        with urllib.request.urlopen(req, timeout=40) as r:
            dados_pdf = r.read(limite_mb * 1024 * 1024 + 1)
    except Exception as e:
        print(f"[Garantias] {url}: {e}")
        return False
    if len(dados_pdf) > limite_mb * 1024 * 1024 or not dados_pdf.startswith(b"%PDF"):
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados_pdf)
    return True


def buscar_manual(produto: str) -> tuple[Path | None, str]:
    """Procura e baixa o manual em PDF. (arquivo, url) ou (None, motivo)."""
    try:
        from actions.web_search import _ddg_search
    except Exception as e:
        return None, f"a busca na internet não está disponível ({e})"
    destino = PASTA_MANUAIS / f"{_slug(produto)}.pdf"
    if destino.exists():
        return destino, ""
    vistos = set()
    for consulta in (f"{produto} manual pdf", f"manual {produto} português pdf", f"{produto} user manual filetype:pdf"):
        resultados = _ddg_search(consulta, max_results=8)
        urls = [r["url"] for r in resultados if r.get("url")]
        urls.sort(key=lambda u: 0 if u.lower().split("?")[0].endswith(".pdf") else 1)
        for u in urls[:6]:
            if u in vistos:
                continue
            vistos.add(u)
            if _baixar_pdf(u, destino):
                return destino, u
    return None, "não achei um manual em PDF na internet"


def _paginas_do_pdf(pdf: Path) -> list[str]:
    cache = pdf.with_suffix(".paginas.json")
    if cache.exists():
        return ler_json(cache, []) or []
    paginas = []
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf)) as doc:
            paginas = [(p.extract_text() or "") for p in doc.pages[:400]]
    except Exception:
        try:
            from PyPDF2 import PdfReader
            paginas = [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages[:400]]
        except Exception as e:
            print(f"[Garantias] {pdf.name}: {e}")
    if paginas:
        gravar_json(cache, paginas)
    return paginas


def _manual_do(item: dict | None, produto: str) -> tuple[Path | None, str, str]:
    """(pdf, nome do produto, motivo)"""
    nome = (" ".join(x for x in (item.get("marca"), item.get("modelo")) if x) or item.get("produto", "")) if item \
        else produto
    nome = nome.strip()
    if item and item.get("manual") and Path(item["manual"]).exists():
        return Path(item["manual"]), nome, ""
    d = dados()
    slug = _slug(nome)
    if slug in d["manuais"] and Path(d["manuais"][slug]["arquivo"]).exists():
        return Path(d["manuais"][slug]["arquivo"]), nome, ""
    if not nome_bom(nome):
        return None, nome, "preciso da marca e do modelo (fica na etiqueta do aparelho)"
    pdf, url = buscar_manual(nome)
    if not pdf:
        return None, nome, url
    with _lock:
        d = dados()
        d["manuais"][slug] = {"produto": nome, "arquivo": str(pdf), "url": url, "ts": time.time()}
        if item:
            for x in d["itens"]:
                if x["id"] == item["id"]:
                    x["manual"] = str(pdf)
        _gravar(d)
    return pdf, nome, ""


def responder_manual(pergunta: str, produto: str = "", player=None) -> str:
    d = dados()
    item = item_da_pergunta(d["itens"], f"{produto} {pergunta}")
    if item and produto and not set(palavras(produto)) & set(palavras(" ".join(
            str(item.get(k) or "") for k in ("tipo", "produto", "marca", "modelo")))):
        item = None
    pdf, nome, motivo = _manual_do(item, produto)
    if not pdf:
        base = (item or {}).get("tipo") or produto.strip() or (palavras(pergunta)[-1:] or ["aparelho"])[0]
        return f"Não achei o manual: {motivo}. Qual é a marca e o modelo d{nome_curto({'tipo': base})}?"
    paginas = _paginas_do_pdf(pdf)
    if not any(p.strip() for p in paginas):
        abrir_no_sistema(str(pdf))
        return f"Achei o manual do {nome}, mas o PDF é só imagem (não dá para ler o texto). Abri ele para você."
    trechos = trechos_relevantes(paginas, pergunta, 6)
    if not trechos:
        return f"O manual do {nome} não fala disso com essas palavras. Quer que eu abra o PDF?"
    from plugins import _ia
    contexto = "\n\n".join(f"[página {p}]\n{t}" for p, t in trechos)
    resposta = _ia.perguntar(
        f"Você é o JARVIS. Responda em português do Brasil, em passos curtos e numerados, usando SÓ estes trechos do "
        f"manual do {nome}. Diga a página. Se os trechos não respondem, diga isso.\n\nPERGUNTA: {pergunta}\n\n"
        f"TRECHOS DO MANUAL:\n{contexto[:7000]}", inteligente=True, segundos=40)
    if resposta:
        mostrar(player, f"MANUAL · {nome.upper()}", resposta)
        return resposta
    pag, melhor = trechos[0]
    mostrar(player, f"MANUAL · {nome.upper()}", contexto[:4000])
    return f"Pelo manual do {nome} (página {pag}):\n{melhor[:700]}"


# ── avisos sozinho ─────────────────────────────────────────────────────────────
def verificar(hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    falas = []
    with _lock:
        d = dados()
        for it, tipo in avisos_devidos(d["itens"], hoje):
            it.setdefault("avisos", {})[tipo] = time.time()
            falas.append(frase_aviso(it, tipo, hoje))
        if falas:
            _gravar(d)
    for f in falas:
        try:
            from plugins._notificar import notificar
            notificar(None, f, titulo="Garantia", etiqueta="GARANTIA")
        except Exception as e:
            print(f"[Garantias] {e}")
    return falas


def _laco() -> None:
    time.sleep(120)
    while True:
        if 9 <= datetime.now().hour < 21:
            try:
                verificar()
            except Exception as e:
                print(f"[Garantias] {e}")
        time.sleep(3 * 3600)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="garantias").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "nota":
            return ler_nota(str(p.get("arquivo") or ""), bool(p.get("camera")), str(p.get("produto") or ""),
                            int(p["meses"]) if p.get("meses") else None)
        if acao == "adicionar":
            if not p.get("produto"):
                return "Qual é o produto?"
            info = {"produto": p["produto"], "tipo": (palavras(str(p["produto"])) or [""])[0],
                    "data_compra": p.get("data") or date.today().isoformat(), "meses": p.get("meses") or MESES_PADRAO,
                    "loja": p.get("loja") or "", "valor": p.get("valor")}
            return f"Anotei: {_descrever(_novo_item(info, 'ditado'))}."
        if acao == "manual":
            pergunta = str(p.get("pergunta") or "").strip()
            if not pergunta:
                return "O que você quer saber do manual?"
            return responder_manual(pergunta, str(p.get("produto") or ""), player)
        d = dados()
        if acao in ("quando", "abrir_manual"):
            it = item_da_pergunta(d["itens"], str(p.get("produto") or ""))
            if acao == "quando":
                return quando_acaba(it, date.today()) if it else "Não tenho a garantia desse produto. Quer me mandar a nota?"
            pdf, nome, motivo = _manual_do(it, str(p.get("produto") or ""))
            if not pdf:
                return f"Não achei o manual: {motivo}."
            abrir_no_sistema(str(pdf))
            return f"Abri o manual do {nome}."
        if acao == "apagar":
            with _lock:
                d = dados()
                alvo = next((x for x in d["itens"] if x["id"] == int(p.get("id") or 0)), None)
                if not alvo:
                    return "Não achei esse número."
                d["itens"].remove(alvo)
                _gravar(d)
            return f"Tirei {alvo['produto']} da lista (a foto da nota continua em {PASTA_NOTAS})."
        if not d["itens"]:
            return "Nenhuma garantia guardada. Mande a foto da nota ou diga 'olha essa nota fiscal'."
        hoje = date.today()
        ordem = sorted(d["itens"], key=lambda x: x.get("fim") or "9999")
        vigentes = [x for x in ordem if x.get("fim") and date.fromisoformat(x["fim"]) >= hoje]
        texto = "\n".join(_descrever(x) for x in ordem)
        mostrar(player, "GARANTIAS", texto)
        return f"{len(vigentes)} na garantia, {len(ordem) - len(vigentes)} vencida(s):\n{texto}"
    except Exception as e:
        return f"As garantias falharam: {e}"

