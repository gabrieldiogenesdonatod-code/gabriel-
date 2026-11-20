"""
Módulo Cristal Malhas — plugin do J.A.R.V.I.S BR.

Para a divulgação:
    "Jarvis, faz um roteiro de Reels pro conjunto moletom infantil azul"
    → roteiro cena a cena, legenda pronta e hashtags, mostrados no painel.

Para o dia a dia da loja:
    "Jarvis, vendi 2 conjuntos moletom azul por 89,90 cada"
    "Jarvis, chegaram 10 conjuntos moletom azul"
    "Jarvis, quanto tem de conjunto moletom azul?"
    "Jarvis, quanto a loja vendeu este mês?"

Arquivos (abrem direto no Excel):
    memory/cristal_vendas.csv
    memory/cristal_estoque.csv
"""

from __future__ import annotations

from datetime import datetime

from plugins._dados_br import acrescentar, chave, escrever, ler, numero, reais

PLUGIN = {
    "name": "cristal_malhas",
    "description": (
        "Tools for the user's children's clothing store, Cristal Malhas. "
        "action='conteudo' to write a short-video script (Reels/TikTok/Stories), "
        "caption and hashtags for a product — pass produto and optionally formato. "
        "action='venda' to record a sale (produto, quantidade, valor = price PER "
        "UNIT in reais). action='entrada' when stock arrives (produto, quantidade). "
        "action='estoque' to say how many are in stock (produto optional = all). "
        "action='resumo' for sales totals (periodo: hoje | semana | mes). "
        "Use this instead of any spreadsheet tool for the store."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "conteudo | venda | entrada | estoque | resumo"},
            "produto": {"type": "STRING", "description": "Product description"},
            "quantidade": {"type": "NUMBER", "description": "Units, default 1"},
            "valor": {"type": "NUMBER", "description": "Unit price in reais"},
            "formato": {"type": "STRING", "description": "reels | tiktok | stories"},
            "periodo": {"type": "STRING", "description": "hoje | semana | mes"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "cristal_malhas",
    "title": "Cristal Malhas",
    "fields": [
        {"key": "pontos_fortes", "label": "Pontos fortes da loja", "type": "text",
         "default": "qualidade, custo-benefício, atendimento, conforto, "
                    "versatilidade, multimarcas"},
        {"key": "whatsapp", "label": "WhatsApp da loja (para a legenda)",
         "type": "text", "default": ""},
        {"key": "tom", "label": "Tom dos textos", "type": "choice",
         "options": ["carinhoso", "divertido", "direto", "elegante"],
         "default": "carinhoso"},
    ],
}

_VENDAS = "cristal_vendas.csv"
_ESTOQUE = "cristal_estoque.csv"
_CAMPOS_VENDA = ["data", "produto", "quantidade", "valor_unitario", "total"]
_CAMPOS_ESTOQUE = ["produto", "quantidade", "atualizado"]


def _cfg() -> dict:
    try:
        from memory.config_manager import get_plugin_config
        return get_plugin_config("cristal_malhas")
    except Exception:
        return {}


# ── conteúdo para redes sociais ───────────────────────────────────────────────
def _conteudo(produto: str, formato: str, player) -> str:
    if not produto.strip():
        return "Qual produto é o vídeo?"
    cfg = _cfg()
    fortes = cfg.get("pontos_fortes") or PLUGIN_SETTINGS["fields"][0]["default"]
    tom = cfg.get("tom") or "carinhoso"
    zap = (cfg.get("whatsapp") or "").strip()
    formato = (formato or "reels").strip().lower()

    prompt = (
        "Você é o social media de uma loja de roupas infantis multimarcas chamada "
        "Cristal Malhas. Escreva em português do Brasil, tom " + tom + ".\n"
        f"Produto: {produto}\nFormato: {formato} vertical, 15 a 30 segundos.\n"
        f"Pontos fortes da loja para destacar com naturalidade: {fortes}.\n"
        + (f"WhatsApp para pedidos: {zap}\n" if zap else "")
        + "Responda SÓ com JSON neste formato:\n"
        '{"gancho": "frase dos 2 primeiros segundos",'
        ' "cenas": [{"tempo": "0-3s", "imagem": "o que filmar", "texto_tela": "..."}],'
        ' "legenda": "legenda completa com chamada para ação e emojis",'
        ' "hashtags": ["#..."]}\n'
        "Entre 4 e 6 cenas, entre 8 e 12 hashtags (misture amplas e locais). "
        "Não invente preço, tamanho nem promoção que não foi informada."
    )
    try:
        from core import gemini
        data = gemini.as_json(prompt, tier=gemini.SMART, timeout_ms=45_000)
    except Exception as e:
        return f"Não consegui gerar o conteúdo agora: {e}"
    if not isinstance(data, dict) or not data.get("cenas"):
        return "O modelo não devolveu um roteiro válido. Tente de novo."

    linhas = [f"GANCHO: {data.get('gancho', '')}", "", "ROTEIRO"]
    for c in data.get("cenas", []):
        linhas.append(f"[{c.get('tempo', '')}] {c.get('imagem', '')}")
        if c.get("texto_tela"):
            linhas.append(f"    texto na tela: {c['texto_tela']}")
    linhas += ["", "LEGENDA", data.get("legenda", ""), "",
               " ".join(data.get("hashtags", []))]
    texto = "\n".join(linhas)

    if player is not None:
        try:
            player.show_content(f"CRISTAL — {produto[:30]}", texto)
        except Exception:
            pass
    return (f"Roteiro de {formato} pronto e no painel, com {len(data['cenas'])} cenas, "
            f"legenda e {len(data.get('hashtags', []))} hashtags. "
            f"O gancho é: {data.get('gancho', '')}")


# ── estoque e vendas ───────────────────────────────────────────────────────────
def _estoque_mudar(produto: str, delta: int) -> int | None:
    """Soma delta ao estoque; devolve a nova quantidade (None se não existia)."""
    linhas = ler(_ESTOQUE)
    k = chave(produto)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    for linha in linhas:
        if chave(linha.get("produto", "")) == k:
            nova = int(numero(linha.get("quantidade"))) + delta
            linha["quantidade"], linha["atualizado"] = str(nova), agora
            escrever(_ESTOQUE, _CAMPOS_ESTOQUE, linhas)
            return nova
    if delta > 0:
        linhas.append({"produto": produto.strip(), "quantidade": str(delta),
                       "atualizado": agora})
        escrever(_ESTOQUE, _CAMPOS_ESTOQUE, linhas)
        return delta
    return None


def _venda(produto: str, qtd: int, valor: float) -> str:
    if not produto.strip():
        return "Qual produto foi vendido?"
    # Usa o nome como está no estoque, para "MOLETOM azul" e "moletom azul"
    # contarem como o mesmo produto nos relatórios.
    k = chave(produto)
    for item in ler(_ESTOQUE):
        if chave(item.get("produto", "")) == k:
            produto = item["produto"]
            break
    total = qtd * valor
    acrescentar(_VENDAS, _CAMPOS_VENDA, {
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "produto": produto.strip(), "quantidade": qtd,
        "valor_unitario": f"{valor:.2f}".replace(".", ","),
        "total": f"{total:.2f}".replace(".", ","),
    })
    resto = _estoque_mudar(produto, -qtd)
    msg = f"Venda registrada: {qtd}× {produto}"
    msg += f", total {reais(total)}." if valor else " (sem valor informado)."
    if resto is not None:
        msg += f" Restam {resto} no estoque."
        if resto <= 2:
            msg += " Atenção: estoque baixo."
    return msg


def _entrada(produto: str, qtd: int) -> str:
    if not produto.strip():
        return "Qual produto chegou?"
    nova = _estoque_mudar(produto, qtd)
    return f"Entrada registrada: agora há {nova} de {produto} no estoque."


def _estoque(produto: str) -> str:
    linhas = ler(_ESTOQUE)
    if not linhas:
        return "O estoque ainda está vazio. Registre as entradas primeiro."
    if produto.strip():
        k = chave(produto)
        achados = [l for l in linhas if k in chave(l.get("produto", ""))]
        if not achados:
            return f"Não tenho {produto} no estoque registrado."
        return "; ".join(f"{l['produto']}: {l['quantidade']}" for l in achados) + "."
    baixos = [l for l in linhas if int(numero(l.get("quantidade"))) <= 2]
    total = sum(int(numero(l.get("quantidade"))) for l in linhas)
    msg = f"{len(linhas)} produtos, {total} peças no total."
    if baixos:
        msg += " Estoque baixo: " + ", ".join(
            f"{l['produto']} ({l['quantidade']})" for l in baixos) + "."
    return msg


def _resumo(periodo: str, player) -> str:
    vendas = ler(_VENDAS)
    hoje = datetime.now()
    periodo = (periodo or "mes").lower()
    if periodo.startswith("hoje"):
        prefixo, nome = hoje.strftime("%Y-%m-%d"), "hoje"
        filtradas = [v for v in vendas if v["data"].startswith(prefixo)]
    elif periodo.startswith("semana"):
        nome = "nos últimos 7 dias"
        filtradas = []
        for v in vendas:
            try:
                if (hoje - datetime.strptime(v["data"][:10], "%Y-%m-%d")).days < 7:
                    filtradas.append(v)
            except ValueError:
                pass
    else:
        prefixo, nome = hoje.strftime("%Y-%m"), "este mês"
        filtradas = [v for v in vendas if v["data"].startswith(prefixo)]

    if not filtradas:
        return f"Nenhuma venda registrada {nome}."
    total = sum(numero(v["total"]) for v in filtradas)
    pecas = sum(int(numero(v["quantidade"])) for v in filtradas)
    por_produto: dict[str, list] = {}       # chave → [nome, peças]
    for v in filtradas:
        item = por_produto.setdefault(chave(v["produto"]), [v["produto"], 0])
        item[1] += int(numero(v["quantidade"]))
    top = max(por_produto.values(), key=lambda kv: kv[1])
    texto = "\n".join(f"{v['data']}  {v['quantidade']}× {v['produto']}  {reais(numero(v['total']))}"
                      for v in filtradas)
    if player is not None:
        try:
            player.show_content(f"VENDAS {nome.upper()}", texto + f"\n\nTOTAL: {reais(total)}")
        except Exception:
            pass
    return (f"{nome.capitalize()}: {len(filtradas)} vendas, {pecas} peças, "
            f"{reais(total)}. Mais vendido: {top[0]} ({top[1]}).")


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    action = str(p.get("action", "")).strip().lower()
    produto = str(p.get("produto") or "")
    qtd = max(1, int(numero(p.get("quantidade"), 1)))
    try:
        if action in ("conteudo", "conteúdo", "roteiro", "legenda"):
            return _conteudo(produto, str(p.get("formato") or ""), player)
        if action == "venda":
            return _venda(produto, qtd, numero(p.get("valor")))
        if action == "entrada":
            return _entrada(produto, qtd)
        if action == "estoque":
            return _estoque(produto)
        if action == "resumo":
            return _resumo(str(p.get("periodo") or ""), player)
        return "Ação desconhecida. Use conteudo, venda, entrada, estoque ou resumo."
    except Exception as e:
        return f"O módulo Cristal Malhas falhou: {e}"
