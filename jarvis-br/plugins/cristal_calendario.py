"""
Calendário comercial infantil — Cristal Malhas (fork PT-BR 1.4).

As datas que vendem roupa infantil no Brasil, calculadas para cada ano
(Páscoa e Carnaval pelo cálculo da Páscoa; Dia das Mães, dos Pais e Black
Friday pela regra do dia da semana):

    Volta às aulas · Carnaval · Páscoa · Dia das Mães · Coleção inverno ·
    Festa junina · Dia dos Pais · Volta às aulas (2º semestre) · Coleção
    verão · Dia do Cliente · Dia das Crianças · Black Friday · Natal

Umas 3 semanas antes (ajustável), o JARVIS avisa:
    "Senhor, faltam 20 dias para o Dia das Crianças, quer que eu monte a campanha?"
E a campanha sai com cronograma de posts, ideias de vitrine e roteiros —
usando o que existe no SEU estoque (com IA; sem IA, um roteiro-modelo).

ESTOQUE POR TAMANHO
    Lê o estoque do plugin cristal_malhas e separa o tamanho do nome da peça
    ("Conjunto moletom azul 4" → tamanho 4). Avisa quando um tamanho está
    acabando enquanto os outros ainda têm: "Conjunto moletom azul: o 4 tem só
    1 peça (o 6 e o 8 ainda têm 5)".

    "Jarvis, quais datas comerciais estão chegando?"
    "Jarvis, monta a campanha do Dia das Crianças"
    "Jarvis, quais tamanhos estão acabando?"
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta

from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "cristal_calendario",
    "brief": "Children's retail calendar for Cristal Malhas (alerts ~3 weeks before) and low stock per size.",
    "description": (
        "Commercial calendar for the Cristal Malhas children's clothing store (back to school, Easter, "
        "Mother's Day, June festivals, Father's Day, Children's Day, Black Friday, Christmas...) with "
        "alerts weeks before, campaign plans, and low-stock-per-size alerts. action='proximas' (upcoming "
        "dates), 'campanha' with data (date name) to build a campaign, 'tamanhos' (sizes running out)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "proximas | campanha | tamanhos"},
            "data": {"type": "STRING", "description": "commercial date name, e.g. Dia das Crianças"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "cristal_calendario",
    "title": "Cristal Malhas — calendário e estoque",
    "fields": [
        {"key": "antecedencia", "label": "Avisar quantos dias antes", "type": "text", "default": "21"},
        {"key": "estoque_minimo", "label": "Avisar quando um tamanho tiver até (peças)", "type": "text", "default": "1"},
        {"key": "avisos", "label": "Avisar sozinho (datas e tamanhos)", "type": "toggle", "default": True},
    ],
}

_ESTADO = MEMORIA / "cristal_calendario.json"
_iniciado = threading.Event()


# ── datas (puras) ──────────────────────────────────────────────────────────────
def pascoa(ano: int) -> date:
    """Algoritmo de Meeus/Jones/Butcher (calendário gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def n_esimo(ano: int, mes: int, dia_semana: int, n: int) -> date:
    """n-ésimo dia da semana do mês (segunda=0)."""
    d = date(ano, mes, 1)
    d += timedelta(days=(dia_semana - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def datas_do_ano(ano: int) -> list[dict]:
    p = pascoa(ano)
    datas = [
        ("volta_aulas", "Volta às aulas", date(ano, 2, 2), "kits de uniforme e mochila, looks de primeiro dia, conforto para a escola"),
        ("carnaval", "Carnaval", p - timedelta(days=47), "fantasias e looks coloridos, bodies estampados, tiaras"),
        ("pascoa", "Páscoa", p, "looks de família, pijamas temáticos, presentes no lugar do ovo"),
        ("dia_das_maes", "Dia das Mães", n_esimo(ano, 5, 6, 2), "tal mãe, tal filha, kits presente, fotos com as mães clientes"),
        ("colecao_inverno", "Coleção outono-inverno", date(ano, 4, 20), "moletons, conjuntos de frio, pijamas quentinhos"),
        ("festa_junina", "Festa junina", date(ano, 6, 1), "vestidos caipiras, xadrez, camisas e chapéus para as festas das escolas"),
        ("dia_dos_pais", "Dia dos Pais", n_esimo(ano, 8, 6, 2), "tal pai, tal filho, bodies com frases, kits presente"),
        ("volta_aulas_2", "Volta às aulas (2º semestre)", date(ano, 7, 28), "reposição de peças, conforto para a escola"),
        ("colecao_verao", "Coleção primavera-verão", date(ano, 9, 22), "estampas leves, shorts, vestidos, moda praia infantil"),
        ("dia_do_cliente", "Dia do Cliente", date(ano, 9, 15), "mimo para clientes fiéis, sorteio, agradecimento nas redes"),
        ("dia_das_criancas", "Dia das Crianças", date(ano, 10, 12), "o MAIOR do ano: kits presente, embalagem especial, vitrine temática"),
        ("black_friday", "Black Friday", n_esimo(ano, 11, 3, 4) + timedelta(days=1), "seleção de peças da estação anterior, combos"),
        ("natal", "Natal", date(ano, 12, 25), "looks de festa, pijamas de Natal em família, presentes por faixa de idade"),
    ]
    return [{"chave": k, "nome": n, "data": d, "ideias": i} for k, n, d, i in datas]


def proximas(hoje: date | None = None, dias: int = 90) -> list[dict]:
    hoje = hoje or date.today()
    todas = datas_do_ano(hoje.year) + datas_do_ano(hoje.year + 1)
    saida = [dict(d, faltam=(d["data"] - hoje).days) for d in todas if 0 <= (d["data"] - hoje).days <= dias]
    return sorted(saida, key=lambda d: d["faltam"])


def achar_data(nome: str, hoje: date | None = None) -> dict | None:
    import unicodedata
    def dobra(t):
        return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    alvo = dobra(nome)
    for d in proximas(hoje, 400):
        if alvo and (alvo in dobra(d["nome"]) or dobra(d["nome"]) in alvo or alvo.replace(" ", "_") in d["chave"]):
            return d
    return None


# ── estoque por tamanho (puro) ─────────────────────────────────────────────────
def tamanhos_acabando(itens: list[dict], minimo: int = 1) -> list[dict]:
    """itens: [{'produto','quantidade'}] → peças com algum tamanho ≤ mínimo e outros ainda com estoque."""
    from plugins.cristal_fotos import separar_tamanho
    grupos = defaultdict(dict)
    for it in itens:
        base, tam = separar_tamanho(str(it.get("produto", "")))
        if tam:
            try:
                grupos[base][tam] = int(float(str(it.get("quantidade", 0)).replace(",", ".")))
            except ValueError:
                continue
    saida = []
    for base, tams in grupos.items():
        baixos = {t: q for t, q in tams.items() if q <= minimo}
        bons = {t: q for t, q in tams.items() if q > minimo}
        if baixos and bons:
            saida.append({"peca": base, "baixos": baixos, "outros": bons})
    return saida


def _texto_tamanhos(a: dict) -> str:
    baixos = ", ".join(f"o {t} tem {'só ' + str(q) if q else 'zero'}" for t, q in a["baixos"].items())
    outros = ", ".join(f"o {t} ({q})" for t, q in a["outros"].items())
    return f"{a['peca']}: {baixos} (ainda têm: {outros})"


def _itens_estoque() -> list[dict]:
    try:
        from plugins._dados_br import ler
        return ler("cristal_estoque.csv")
    except Exception:
        return []


# ── campanha ───────────────────────────────────────────────────────────────────
def campanha(d: dict) -> str:
    itens = _itens_estoque()
    from plugins.cristal_fotos import separar_tamanho
    pecas = defaultdict(int)
    for it in itens:
        base, _t = separar_tamanho(it.get("produto", ""))
        try:
            pecas[base] += int(float(str(it.get("quantidade", 0)).replace(",", ".")))
        except ValueError:
            pass
    top = sorted(pecas.items(), key=lambda x: -x[1])[:12]
    estoque_txt = "; ".join(f"{p} ({q})" for p, q in top) or "estoque não cadastrado"
    semanas = max(1, d["faltam"] // 7)
    from plugins import _ia
    if _ia.disponivel():
        r = _ia.perguntar(
            f"Você é o marketing da Cristal Malhas, loja de roupa INFANTIL multimarcas em Goiânia. Monte a campanha "
            f"para {d['nome']} ({d['data']:%d/%m/%Y}, faltam {d['faltam']} dias). Ideias da data: {d['ideias']}. "
            f"Peças com mais estoque: {estoque_txt}. Inclua: 1) conceito e frase da campanha; 2) cronograma semana a "
            f"semana até a data (posts, Reels, stories, status do WhatsApp); 3) 3 roteiros curtos de Reels; 4) vitrine "
            "e embalagem; 5) quais peças do estoque destacar. Não invente preço nem desconto. Português do Brasil, "
            "direto, em tópicos.", inteligente=True, segundos=90)
        if r:
            return r
    linhas = [f"CAMPANHA — {d['nome'].upper()} ({d['data']:%d/%m}, faltam {d['faltam']} dias)", "",
              f"Ideias da data: {d['ideias']}.", "", "CRONOGRAMA"]
    roteiro = ["aquecimento: enquete nos stories ('qual look para a data?') e bastidores das peças chegando",
               "vitrine e Reels mostrando os kits; post carrossel com os destaques do estoque",
               "contagem regressiva nos stories + status do WhatsApp com as peças por tamanho",
               "últimos dias: lembrete de entrega/retirada e 'últimas unidades' SÓ se for verdade"]
    for i in range(min(semanas, 4)):
        linhas.append(f"  Semana {i + 1}: {roteiro[i if semanas >= 4 else min(3, i + 4 - semanas)]}")
    linhas += ["", "DESTAQUES DO ESTOQUE"] + [f"  · {p} ({q} peças)" for p, q in top[:8]]
    linhas += ["", "Configure a chave de IA para receber roteiros e textos prontos."]
    return "\n".join(linhas)


# ── avisos automáticos ─────────────────────────────────────────────────────────
def verificar(player=None, hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    c = cfg("cristal_calendario", PLUGIN_SETTINGS)
    try:
        antecedencia = int(float(str(c.get("antecedencia") or 21)))
        minimo = int(float(str(c.get("estoque_minimo") or 1)))
    except ValueError:
        antecedencia, minimo = 21, 1
    est = ler_json(_ESTADO, {}) or {}
    avisados = set(est.get("avisados", []))
    falas = []
    for d in proximas(hoje, antecedencia):
        chave = f"{d['data'].year}:{d['chave']}"
        if chave in avisados:
            continue
        avisados.add(chave)
        falas.append(f"Faltam {d['faltam']} dias para {d['nome']} ({d['data']:%d/%m}). Quer que eu monte a campanha?")
    tams = tamanhos_acabando(_itens_estoque(), minimo)
    assinatura = sorted(_texto_tamanhos(a) for a in tams)
    if assinatura and assinatura != est.get("tamanhos_avisados"):
        falas.append("Tamanhos acabando — " + "; ".join(assinatura[:3]) + ".")
    est["tamanhos_avisados"] = assinatura
    est["avisados"] = sorted(avisados)
    est["verificado"] = hoje.isoformat()
    gravar_json(_ESTADO, est)
    return falas


def _laco(player) -> None:
    time.sleep(300)
    while True:
        try:
            c = cfg("cristal_calendario", PLUGIN_SETTINGS)
            est = ler_json(_ESTADO, {}) or {}
            if (str(c.get("avisos", True)).lower() not in ("false", "0", "nao", "não")
                    and est.get("verificado") != date.today().isoformat() and datetime.now().hour >= 9):
                from plugins._notificar import notificar
                for fala in verificar(player):
                    notificar(player, fala, titulo="Cristal Malhas", etiqueta="LOJA")
                    time.sleep(20)
        except Exception as e:
            print(f"[CristalCalendario] {e}")
        time.sleep(1800)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="cristal_calendario").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "proximas").lower()
    try:
        if acao == "campanha":
            d = achar_data(str(p.get("data") or "")) or (proximas()[0] if proximas() else None)
            if not d:
                return "Não achei essa data comercial."
            texto = campanha(d)
            mostrar(player, f"CAMPANHA — {d['nome']}", texto)
            return f"A campanha de {d['nome']} está no painel: faltam {d['faltam']} dias."
        if acao == "tamanhos":
            c = cfg("cristal_calendario", PLUGIN_SETTINGS)
            tams = tamanhos_acabando(_itens_estoque(), int(float(str(c.get("estoque_minimo") or 1))))
            if not tams:
                return ("Nenhum tamanho acabando. (Para eu enxergar tamanhos, cadastre as peças com o tamanho no "
                        "fim do nome, como 'conjunto moletom azul 4'.)")
            mostrar(player, "TAMANHOS ACABANDO", "\n".join(_texto_tamanhos(a) for a in tams))
            return "Tamanhos acabando: " + "; ".join(_texto_tamanhos(a) for a in tams[:3]) + "."
        lista = proximas(dias=120)
        if not lista:
            return "Nenhuma data comercial nos próximos 4 meses."
        mostrar(player, "CALENDÁRIO COMERCIAL", "\n".join(
            f"{d['data']:%d/%m/%Y}  ({d['faltam']:>3} dias)  {d['nome']} — {d['ideias']}" for d in lista))
        return "Próximas datas: " + "; ".join(f"{d['nome']} em {d['faltam']} dias" for d in lista[:4]) + "."
    except Exception as e:
        return f"O calendário falhou: {e}"
