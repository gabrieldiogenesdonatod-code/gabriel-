"""
Controle do MEI (fork PT-BR 2.16, ideia 6).

    "Jarvis, quanto eu já faturei no MEI esse ano?"
    "Jarvis, anota faturamento de 1.200 reais"         (venda fora da loja: serviço, freela…)
    "Jarvis, abri o MEI em março de 2026"              (limite proporcional no ano de abertura)

Soma as vendas da Cristal Malhas (memory/cristal_vendas.csv) com o que você
anotar aqui (memory/mei_faturamento.csv) e compara com o limite anual: R$ 81 mil
em 2026 (R$ 6.750 por mês no ano em que o MEI foi aberto). Há um projeto de lei
(PLP 186/2026) para subir o teto, ainda NÃO aprovado — se mudar, troque o valor
em ⚙ → Controle do MEI.

Avisa sozinho (uma vez por dia, no máximo) quando passar de 70%, 85% e 95% do
limite, e explica a regra: passando até 20% do teto, você paga a diferença e sai
do MEI no ano seguinte; acima disso, o desenquadramento volta a janeiro.
Isto é uma conta de apoio, não substitui o contador.
"""

from __future__ import annotations

import threading
import time
from datetime import date, datetime

from plugins._comum import cfg, mostrar, plugin_ligado, salvar_cfg
from plugins._dados_br import acrescentar, ler, numero, reais

PLUGIN = {
    "name": "controle_mei",
    "brief": "MEI annual revenue vs the legal limit (R$ 81k in 2026); log revenue; warns near the limit.",
    "description": (
        "MEI revenue control. action='status' (optional ano) shows revenue so far vs the annual limit, monthly average "
        "and projection. action='anotar' with valor and optional descricao logs revenue outside the store. "
        "action='abertura' with mes (1-12) and ano sets when the MEI was opened (proportional limit that year)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "status | anotar | abertura"},
                       "valor": {"type": "NUMBER"}, "descricao": {"type": "STRING"},
                       "ano": {"type": "INTEGER"}, "mes": {"type": "INTEGER"}},
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "controle_mei",
    "title": "Controle do MEI",
    "fields": [
        {"key": "limite_anual", "label": "Limite anual do MEI (R$)", "type": "number", "default": 81000},
        {"key": "contar_loja", "label": "Somar as vendas da Cristal Malhas", "type": "toggle", "default": True},
        {"key": "abertura", "label": "Mês/ano de abertura do MEI (ex.: 03/2026)", "type": "text", "default": ""},
    ],
}

ARQ = "mei_faturamento.csv"
CAMPOS = ["data", "valor", "descricao"]
FAIXAS = (0.70, 0.85, 0.95, 1.0)
_avisado: dict[str, str] = {}


def limite_do_ano(ano: int, limite: float, abertura: str = "") -> float:
    """No ano de abertura, R$ limite/12 por mês desde o mês de abertura (pura)."""
    try:
        m, a = (int(x) for x in abertura.split("/"))
    except (ValueError, AttributeError):
        return limite
    if a != ano:
        return limite
    return limite / 12 * (12 - m + 1)


def faturamento(ano: int, contar_loja: bool = True) -> tuple[float, dict[int, float]]:
    por_mes: dict[int, float] = {}
    fontes = [(ARQ, "valor")] + ([("cristal_vendas.csv", "total")] if contar_loja else [])
    for arq, campo in fontes:
        for linha in ler(arq):
            d = str(linha.get("data") or "")
            if d[:4] == str(ano):
                try:
                    mes = int(d[5:7])
                except ValueError:
                    continue
                por_mes[mes] = por_mes.get(mes, 0.0) + numero(linha.get(campo))
    return sum(por_mes.values()), por_mes


def analise(total: float, limite: float, hoje: date, ano: int, inicio_mes: int = 1) -> dict:
    """Uso do limite, média, projeção do ano e a mensagem da faixa (pura)."""
    meses = max(1, (hoje.month if ano == hoje.year else 12) - inicio_mes + 1)
    media = total / meses
    restantes = (12 - hoje.month) if ano == hoje.year else 0
    projecao = total + media * restantes
    pct = total / limite if limite else 0
    if pct >= 1.2:
        aviso = "passou mais de 20% do limite: o desenquadramento volta a 1º de janeiro deste ano; fale com um contador"
    elif pct >= 1:
        aviso = ("passou do limite (até 20%): paga a diferença no DAS da declaração e vira ME a partir de janeiro; "
                 "fale com um contador")
    elif pct >= .95:
        aviso = "a menos de 5% do limite; cuidado com as próximas vendas"
    elif pct >= .85:
        aviso = "já passou de 85% do limite"
    elif pct >= .7:
        aviso = "já passou de 70% do limite"
    else:
        aviso = ""
    sobra = max(0.0, limite - total)
    return {"pct": pct, "media": media, "projecao": projecao, "sobra": sobra, "aviso": aviso,
            "por_mes_ate_fim": sobra / restantes if restantes else sobra, "estoura": projecao > limite}


def _status(ano: int) -> tuple[str, str]:
    c = cfg("controle_mei", PLUGIN_SETTINGS)
    limite = limite_do_ano(ano, float(c.get("limite_anual") or 81000), str(c.get("abertura") or ""))
    total, por_mes = faturamento(ano, bool(c.get("contar_loja", True)))
    try:
        m_ab, a_ab = (int(x) for x in str(c.get("abertura") or "").split("/"))
        inicio = m_ab if a_ab == ano else 1
    except ValueError:
        inicio = 1
    r = analise(total, limite, date.today(), ano, inicio)
    painel = [f"Faturamento {ano}: {reais(total)} de {reais(limite)} ({r['pct'] * 100:.0f}%)",
              f"Média por mês: {reais(r['media'])}   Projeção do ano: {reais(r['projecao'])}",
              f"Ainda cabe: {reais(r['sobra'])}" + (f" (uns {reais(r['por_mes_ate_fim'])} por mês até dezembro)"
                                                    if ano == date.today().year and date.today().month < 12 else ""),
              ""] + [f"  {m:02d}/{ano}: {reais(v)}" for m, v in sorted(por_mes.items())]
    if r["aviso"]:
        painel += ["", "⚠ " + r["aviso"]]
    fala = f"Em {ano} você faturou {reais(total)}, {r['pct'] * 100:.0f}% do limite de {reais(limite)}. "
    fala += f"Cabem mais {reais(r['sobra'])}."
    if r["estoura"]:
        fala += f" No ritmo atual o ano fecha em {reais(r['projecao'])}, acima do limite."
    if r["aviso"]:
        fala += f" Atenção: {r['aviso']}."
    return fala, "\n".join(painel)


def _laco(player) -> None:
    while True:
        time.sleep(3600)
        if not plugin_ligado("controle_mei"):
            continue
        try:
            ano = date.today().year
            c = cfg("controle_mei", PLUGIN_SETTINGS)
            limite = limite_do_ano(ano, float(c.get("limite_anual") or 81000), str(c.get("abertura") or ""))
            total, _ = faturamento(ano, bool(c.get("contar_loja", True)))
            faixa = max((f for f in FAIXAS if total >= f * limite), default=None)
            hoje = date.today().isoformat()
            if faixa and _avisado.get(str(faixa)) is None and c.get(f"avisou_{int(faixa * 100)}_{ano}") is None:
                _avisado[str(faixa)] = hoje
                salvar_cfg("controle_mei", {f"avisou_{int(faixa * 100)}_{ano}": hoje})
                from plugins._notificar import notificar
                notificar(player, f"MEI: você já faturou {reais(total)} em {ano}, {faixa * 100:.0f}% do limite.", "MEI")
        except Exception as e:
            print(f"[MEI] {e}")


def on_session_start(player) -> None:
    threading.Thread(target=_laco, args=(player,), daemon=True, name="controle_mei").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "status").lower()
    try:
        if a == "anotar":
            v = float(p.get("valor") or 0)
            if v <= 0:
                return "Qual valor?"
            acrescentar(ARQ, CAMPOS, {"data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                      "valor": f"{v:.2f}".replace(".", ","),
                                      "descricao": str(p.get("descricao") or "faturamento")})
            fala, _ = _status(date.today().year)
            return f"Anotado {reais(v)}. " + fala
        if a == "abertura":
            mes, ano = int(p.get("mes") or 1), int(p.get("ano") or date.today().year)
            salvar_cfg("controle_mei", {"abertura": f"{mes:02d}/{ano}"})
            return f"Anotado: MEI aberto em {mes:02d}/{ano}."
        fala, painel = _status(int(p.get("ano") or date.today().year))
        mostrar(player, "CONTROLE DO MEI", painel)
        return fala
    except Exception as e:
        return f"O controle do MEI falhou: {e}"
