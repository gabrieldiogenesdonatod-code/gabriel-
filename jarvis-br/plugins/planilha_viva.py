"""
Planilha viva (fork PT-BR 2.16, ideia 8).

    "Jarvis, adiciona venda de 89 reais na planilha"
    "Jarvis, põe na planilha: conjunto moletom, 2 peças, 120 reais, Pix, cliente Ana"
    "Jarvis, usa a planilha C:\\Users\\eu\\Documents\\vendas.xlsx"     (escolhe a planilha padrão)
    "Jarvis, qual o total da coluna valor na planilha?"

Funciona com QUALQUER planilha .xlsx ou .csv: ele acha a linha de cabeçalho
(data, valor, produto, quantidade, cliente, pagamento, descrição…, com ou sem
acento, em qualquer coluna e qualquer aba), coloca cada informação na coluna
certa e escreve na primeira linha vazia depois dos dados — mantendo a
formatação e as fórmulas que já existem. A data entra sozinha.

Se a planilha estiver aberta no Excel, ele avisa para fechar (o Excel trava o
arquivo). Antes de gravar, guarda uma cópia em memory/planilhas_backup/
("Jarvis, desfaz" volta a cópia).
"""

from __future__ import annotations

import csv
import re
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from plugins._comum import MEMORIA, cfg, desfazer, mostrar, salvar_cfg

PLUGIN = {
    "name": "planilha_viva",
    "brief": "Append a row to any spreadsheet (xlsx/csv) by voice, mapping values to the right columns; column totals.",
    "description": (
        "Living spreadsheet. action='adicionar' with campos = what to write as 'coluna: valor; coluna: valor' "
        "(e.g. 'valor: 89; produto: conjunto moletom; quantidade: 2; pagamento: pix') — date is filled automatically; "
        "optional arquivo and aba. action='usar' with arquivo sets the default spreadsheet. action='colunas' shows the "
        "detected columns. action='total' with coluna sums a column (optional filtro = text that must appear in the row)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "adicionar | usar | colunas | total"},
                       "campos": {"type": "STRING"}, "arquivo": {"type": "STRING"}, "aba": {"type": "STRING"},
                       "coluna": {"type": "STRING"}, "filtro": {"type": "STRING"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {"namespace": "planilha_viva", "title": "Planilha viva",
                   "fields": [{"key": "arquivo", "label": "Planilha padrão (.xlsx ou .csv)", "type": "text",
                               "default": ""}]}

SINONIMOS = {
    "data": ("data", "dia", "date", "quando", "emissao"),
    "valor": ("valor", "total", "preco", "price", "r$", "quantia", "montante", "receita", "venda", "valor total"),
    "produto": ("produto", "item", "peca", "mercadoria", "descricao do produto", "artigo", "modelo"),
    "quantidade": ("quantidade", "qtd", "qtde", "quant", "pecas", "unidades"),
    "cliente": ("cliente", "comprador", "nome", "nome do cliente"),
    "pagamento": ("pagamento", "forma de pagamento", "forma", "pgto", "meio de pagamento"),
    "descricao": ("descricao", "observacao", "obs", "detalhe", "historico", "nota"),
    "categoria": ("categoria", "tipo", "classe"),
}


def _n(t) -> str:
    return " ".join(unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
                    .replace("_", " ").split())


def ler_campos(texto: str) -> dict[str, str]:
    """'valor: 89; produto: moletom' → {'valor': '89', 'produto': 'moletom'} (pura)."""
    saida = {}
    for parte in re.split(r"[;\n]", texto or ""):
        if ":" in parte:
            k, v = parte.split(":", 1)
            if k.strip() and v.strip():
                saida[_n(k)] = v.strip()
    return saida


def mapear(cabecalho: list, campos: dict[str, str]) -> dict[int, str]:
    """Índice da coluna → valor. Casa pelo nome exato, por sinônimo e por pedaço (pura)."""
    cols = [_n(c) for c in cabecalho]
    usado: dict[int, str] = {}
    for chave, valor in campos.items():
        alvo = None
        if chave in cols:
            alvo = cols.index(chave)
        else:
            grupo = next((g for g, sins in SINONIMOS.items() if chave == g or chave in sins), None)
            nomes = SINONIMOS.get(grupo, ()) + ((grupo,) if grupo else ())
            alvo = next((i for i, c in enumerate(cols) if c and c in nomes and i not in usado), None)
            if alvo is None:
                alvo = next((i for i, c in enumerate(cols) if c and i not in usado and
                             (chave in c or any(s in c for s in nomes if len(s) > 2))), None)
        if alvo is not None and alvo not in usado:
            usado[alvo] = valor
    return usado


def achar_cabecalho(linhas: list[list]) -> int | None:
    """A linha (até a 15ª) com mais nomes de coluna conhecidos (pura)."""
    conhecidos = {s for sins in SINONIMOS.values() for s in sins} | set(SINONIMOS)
    melhor, pontos = None, 0
    for i, linha in enumerate(linhas[:15]):
        p = sum(1 for c in linha if _n(c) in conhecidos or any(k in _n(c) for k in SINONIMOS if len(k) > 3))
        if p > pontos:
            melhor, pontos = i, p
    return melhor if pontos >= 1 else None


def converter(valor: str, nome_coluna: str):
    """'89' / 'R$ 1.234,50' → número; datas ficam texto (pura)."""
    v = valor.strip()
    if _n(nome_coluna) in SINONIMOS["data"]:
        return v
    t = v.replace("R$", "").replace(" ", "")
    if re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?|-?\d+(,\d+)?|-?\d+\.\d+", t):
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        try:
            f = float(t)
            return int(f) if f.is_integer() and "," not in v and "." not in v else f
        except ValueError:
            return v
    return v


def _arquivo(p: dict) -> Path:
    alvo = str(p.get("arquivo") or cfg("planilha_viva", PLUGIN_SETTINGS).get("arquivo") or "").strip().strip('"')
    if not alvo:
        raise ValueError("Qual planilha? Diga 'usa a planilha' e o caminho, ou configure em ⚙ → Planilha viva.")
    caminho = Path(alvo).expanduser()
    if not caminho.exists():
        raise ValueError(f"Não achei a planilha {caminho}.")
    return caminho


def _backup(caminho: Path) -> Path:
    pasta = MEMORIA / "planilhas_backup"
    pasta.mkdir(parents=True, exist_ok=True)
    copia = pasta / f"{caminho.stem}_{time.strftime('%Y%m%d_%H%M%S')}{caminho.suffix}"
    shutil.copy2(caminho, copia)
    copias = sorted(pasta.glob(f"{caminho.stem}_*{caminho.suffix}"))
    for velha in copias[:-20]:
        velha.unlink(missing_ok=True)
    return copia


def _abrir_xlsx(caminho: Path, aba: str = ""):
    import openpyxl
    wb = openpyxl.load_workbook(caminho)
    folhas = [wb[aba]] if aba and aba in wb.sheetnames else wb.worksheets
    for ws in folhas:
        linhas = [[c.value for c in row] for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 15))]
        h = achar_cabecalho(linhas)
        if h is not None:
            return wb, ws, h + 1, [c if c is not None else "" for c in linhas[h]]
    raise ValueError("Não achei o cabeçalho (data, valor, produto…) em nenhuma aba.")


def adicionar(p: dict) -> tuple[str, str]:
    caminho = _arquivo(p)
    campos = ler_campos(str(p.get("campos") or ""))
    if not campos:
        return "O que devo escrever? Ex.: 'valor: 89; produto: moletom'.", ""
    if caminho.suffix.lower() == ".csv":
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            amostra = f.read(4096)
            f.seek(0)
            sep = ";" if amostra.count(";") >= amostra.count(",") else ","
            linhas = list(csv.reader(f, delimiter=sep))
        h = achar_cabecalho(linhas)
        if h is None:
            return "Não achei o cabeçalho dessa planilha.", ""
        cab = linhas[h]
    else:
        wb, ws, linha_cab, cab = _abrir_xlsx(caminho, str(p.get("aba") or ""))
    mapa = mapear(cab, campos)
    idx_data = next((i for i, c in enumerate(cab) if _n(c) in SINONIMOS["data"]), None)
    if idx_data is not None and idx_data not in mapa:
        mapa[idx_data] = datetime.now().strftime("%d/%m/%Y")
    sobrou = [k for k in campos if not any(v == campos[k] for v in mapa.values())]
    if not mapa:
        return f"Nenhuma coluna combina com {', '.join(campos)}. As colunas são: {', '.join(map(str, cab))}.", ""
    copia = _backup(caminho)
    try:
        if caminho.suffix.lower() == ".csv":
            nova = [""] * len(cab)
            for i, v in mapa.items():
                nova[i] = v
            with caminho.open("a", encoding="utf-8-sig", newline="") as f:
                csv.writer(f, delimiter=sep).writerow(nova)
            n_linha = len(linhas) + 1
        else:
            n_linha = linha_cab + 1
            for r in range(ws.max_row, linha_cab, -1):          # última linha com dado nas colunas do cabeçalho
                if any(ws.cell(r, i + 1).value not in (None, "") for i in range(len(cab)) if cab[i]):
                    n_linha = r + 1
                    break
            for i, v in mapa.items():
                cel = ws.cell(n_linha, i + 1)
                if idx_data == i and isinstance(v, str) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
                    cel.value = datetime.strptime(v, "%d/%m/%Y")
                    acima = ws.cell(n_linha - 1, i + 1)
                    cel.number_format = acima.number_format if acima.is_date else "DD/MM/YYYY"
                else:
                    cel.value = converter(v, cab[i])
                    acima = ws.cell(n_linha - 1, i + 1)
                    if acima.number_format and acima.number_format != "General":
                        cel.number_format = acima.number_format
            wb.save(caminho)
    except PermissionError:
        return "A planilha está aberta em outro programa (provavelmente o Excel). Feche e me peça de novo.", ""
    desfazer(f"linha nova em {caminho.name}", lambda: (shutil.copy2(copia, caminho), "Planilha voltou como era.")[1])
    escrito = ", ".join(f"{cab[i]}: {v}" for i, v in sorted(mapa.items()))
    fala = f"Escrevi na linha {n_linha} de {caminho.name}: {escrito}."
    if sobrou:
        fala += f" Não achei coluna para: {', '.join(sobrou)}."
    return fala, ""


def total(p: dict) -> str:
    caminho = _arquivo(p)
    if caminho.suffix.lower() == ".csv":
        with caminho.open(encoding="utf-8-sig", newline="") as f:
            amostra = f.read(4096)
            f.seek(0)
            linhas = list(csv.reader(f, delimiter=";" if amostra.count(";") >= amostra.count(",") else ","))
        h = achar_cabecalho(linhas)
        cab, dados = linhas[h], linhas[h + 1:]
    else:
        wb, ws, linha_cab, cab = _abrir_xlsx(caminho, str(p.get("aba") or ""))
        dados = [[c.value for c in row] for row in ws.iter_rows(min_row=linha_cab + 1)]
    m = mapear(cab, {_n(p.get("coluna") or "valor"): "x"})
    if not m:
        return f"Não achei a coluna {p.get('coluna')}."
    i = next(iter(m))
    filtro = _n(p.get("filtro") or "")
    soma, n = 0.0, 0
    for linha in dados:
        if i >= len(linha) or linha[i] in (None, ""):
            continue
        if filtro and filtro not in _n(" ".join(str(x) for x in linha if x is not None)):
            continue
        v = linha[i] if isinstance(linha[i], (int, float)) else converter(str(linha[i]), "")
        if isinstance(v, (int, float)):
            soma += v
            n += 1
    txt = f"{soma:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"A coluna {cab[i]} soma {txt} em {n} linhas" + (f" com '{p.get('filtro')}'" if filtro else "") + "."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "adicionar").lower()
    try:
        if a == "usar":
            caminho = Path(str(p.get("arquivo") or "").strip().strip('"')).expanduser()
            if not caminho.exists() or caminho.suffix.lower() not in (".xlsx", ".xlsm", ".csv"):
                return "Preciso do caminho de uma planilha .xlsx ou .csv que exista."
            salvar_cfg("planilha_viva", {"arquivo": str(caminho)})
            return f"Pronto: a planilha padrão agora é {caminho.name}."
        if a == "colunas":
            caminho = _arquivo(p)
            if caminho.suffix.lower() == ".csv":
                return run({"action": "total", "coluna": "valor", "arquivo": str(caminho)}, player)
            _wb, ws, linha, cab = _abrir_xlsx(caminho, str(p.get("aba") or ""))
            return f"Na aba {ws.title}, linha {linha}, as colunas são: " + ", ".join(str(c) for c in cab if c) + "."
        if a == "total":
            return total(p)
        fala, painel = adicionar(p)
        if painel:
            mostrar(player, "PLANILHA", painel)
        return fala
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"A planilha viva falhou: {e}"
