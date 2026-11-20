"""
Casa inteligente barata — Tuya / Positivo Casa Inteligente (fork PT-BR 1.4).

Tomadas e lâmpadas Wi-Fi baratas no Brasil (Positivo, Nova Digital, Intelbras
linha Tuya, Smart Life…) são quase todas Tuya por dentro. O JARVIS fala com
elas DIRETO pela rede de casa (API local, biblioteca tinytuya): sem nuvem,
sem atraso, funciona mesmo sem internet.

    "Jarvis, liga a luz do quarto"          "Jarvis, desliga a tomada do ventilador"
    "Jarvis, luz da sala em 30%"            "Jarvis, deixa a luz do quarto azul"
    "Jarvis, cena dormir"                   (várias coisas de uma vez)
    Nos protocolos: passo 'casa' — "protocolo dormir" pode desligar a luz,
    pôr o som no mudo e desligar o PC (este último com confirmação).

CONFIGURAÇÃO (uma vez) — precisa da "chave local" de cada aparelho:
    1. pip install tinytuya
    2. No app Smart Life/Tuya (ou Positivo Casa Inteligente → vincule à conta
       Smart Life), deixe os aparelhos funcionando.
    3. Crie uma conta grátis em iot.tuya.com, um "Cloud Project" (data
       center "Western America" para contas do Brasil) e vincule o app
       (Devices → Link App Account → QR code).
    4. No terminal: python -m tinytuya wizard   → gera o devices.json com id,
       chave local e IP de cada aparelho.
    5. "Jarvis, importa os aparelhos da casa" (lê o devices.json da pasta do
       JARVIS ou da sua pasta de usuário) e dê nomes fáceis no
       config/casa.json, se quiser.

Aparelhos e cenas ficam em config/casa.json.
"""

from __future__ import annotations

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plugins._comum import BASE, CONFIG, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "casa_inteligente",
    "brief": "Controls Tuya/Positivo smart plugs and bulbs on the local network; scenes.",
    "description": (
        "Smart home (Tuya / Positivo / Smart Life plugs and bulbs) over the local network. action="
        "'ligar' | 'desligar' | 'alternar' with aparelho (name, e.g. 'luz do quarto'; 'tudo' = all), "
        "'brilho' with aparelho + nivel 0-100, 'cor' with aparelho + cor (azul, vermelho, branco quente...), "
        "'status' (optional aparelho), 'listar', 'cena' with nome (runs a saved scene), 'criar_cena' "
        "with nome + passos (e.g. 'desligar luz do quarto, desligar tomada da tv'), 'importar' (reads "
        "tinytuya's devices.json)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "ligar | desligar | alternar | brilho | cor | status | listar | cena | criar_cena | importar"},
            "aparelho": {"type": "STRING"}, "nivel": {"type": "INTEGER"}, "cor": {"type": "STRING"},
            "nome": {"type": "STRING"}, "passos": {"type": "STRING"}, "caminho": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

_ARQ = CONFIG / "casa.json"
_SEM_LIB = ("Para controlar a casa preciso da biblioteca tinytuya: pip install tinytuya. "
            "Depois rode 'python -m tinytuya wizard' para pegar as chaves dos aparelhos.")
CORES = {"vermelho": (255, 0, 0), "verde": (0, 255, 0), "azul": (0, 80, 255), "amarelo": (255, 200, 0),
         "laranja": (255, 110, 0), "roxo": (140, 0, 255), "rosa": (255, 60, 160), "ciano": (0, 220, 255),
         "lilas": (190, 120, 255), "branco": None, "branco quente": "quente", "branco frio": "frio"}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode().strip()


def carregar() -> dict:
    d = ler_json(_ARQ, {}) or {}
    d.setdefault("aparelhos", [])
    d.setdefault("cenas", {})
    return d


def achar(d: dict, nome: str) -> list[dict]:
    """Aparelhos que casam com o nome falado ('luz do quarto', 'quarto', 'tudo', 'luzes')."""
    t = _dobrar(nome)
    aps = d["aparelhos"]
    if t in ("tudo", "todos", "todas", "a casa", "casa"):
        return list(aps)
    if t in ("luzes", "as luzes", "todas as luzes", "lampadas"):
        return [a for a in aps if a.get("tipo") == "lampada"]
    exatos = [a for a in aps if _dobrar(a["nome"]) == t]
    if exatos:
        return exatos
    palavras = [w for w in re.findall(r"\w{3,}", t) if w not in ("luz", "tomada", "lampada", "da", "do")]
    contem = [a for a in aps if all(w in _dobrar(a["nome"]) for w in palavras)] if palavras else []
    if contem:
        tipo = "lampada" if re.search(r"luz|lampada", t) else "tomada" if "tomada" in t else ""
        return [a for a in contem if not tipo or a.get("tipo") == tipo] or contem
    return []


def _dispositivo(a: dict):
    import tinytuya
    classe = tinytuya.BulbDevice if a.get("tipo") == "lampada" else tinytuya.OutletDevice
    dev = classe(a["id"], a.get("ip") or "Auto", a.get("chave", ""), version=float(a.get("versao") or 3.3),
                 connection_timeout=4)
    dev.set_socketRetryLimit(1)
    return dev


def comando(a: dict, acao: str, valor=None) -> str:
    dev = _dispositivo(a)
    if acao == "ligar":
        r = dev.turn_on()
    elif acao == "desligar":
        r = dev.turn_off()
    elif acao == "alternar":
        st = dev.status() or {}
        ligado = bool((st.get("dps") or {}).get("1", (st.get("dps") or {}).get("20", False)))
        r = dev.turn_off() if ligado else dev.turn_on()
        acao = "desligar" if ligado else "ligar"
    elif acao == "brilho":
        if a.get("tipo") != "lampada":
            return f"{a['nome']} não é lâmpada"
        dev.turn_on()
        r = dev.set_brightness_percentage(max(1, min(100, int(valor or 100))))
    elif acao == "cor":
        if a.get("tipo") != "lampada":
            return f"{a['nome']} não é lâmpada"
        cor = CORES.get(_dobrar(str(valor or "")), CORES.get(str(valor or "").lower(), "?"))
        dev.turn_on()
        if cor == "?":
            return f"não conheço a cor {valor}"
        if cor is None or cor in ("quente", "frio"):
            r = dev.set_white_percentage(100, 0 if cor == "quente" else 100 if cor == "frio" else 50)
        else:
            r = dev.set_colour(*cor)
    elif acao == "status":
        st = dev.status() or {}
        if "Error" in st:
            return f"{a['nome']}: sem resposta ({st.get('Error')})"
        dps = st.get("dps") or {}
        ligado = dps.get("1", dps.get("20"))
        return f"{a['nome']}: {'ligado' if ligado else 'desligado'}"
    else:
        return f"ação {acao} desconhecida"
    if isinstance(r, dict) and r.get("Error"):
        return f"{a['nome']}: falhou ({r.get('Error')})"
    return f"{a['nome']}: ok"


def executar(nome: str, acao: str, valor=None) -> str:
    try:
        import tinytuya  # noqa: F401
    except ImportError:
        return _SEM_LIB
    d = carregar()
    if not d["aparelhos"]:
        return "Nenhum aparelho cadastrado. Rode o tinytuya wizard e diga 'importa os aparelhos da casa'."
    alvos = achar(d, nome)
    if not alvos:
        return f"Não achei '{nome}'. Aparelhos: {', '.join(a['nome'] for a in d['aparelhos'])}."
    with ThreadPoolExecutor(max_workers=min(8, len(alvos))) as ex:
        res = list(ex.map(lambda a: _seguro(a, acao, valor), alvos))
    falhas = [r for r in res if not r.endswith(": ok") and acao != "status"]
    if acao == "status":
        return "; ".join(res) + "."
    if not falhas:
        verbo = {"ligar": "Liguei", "desligar": "Desliguei", "alternar": "Alternei", "brilho": "Ajustei o brilho de",
                 "cor": "Mudei a cor de"}.get(acao, "Pronto:")
        return f"{verbo} {', '.join(a['nome'] for a in alvos)}."
    return "; ".join(res) + "."


def _seguro(a, acao, valor) -> str:
    try:
        return comando(a, acao, valor)
    except Exception as e:
        return f"{a['nome']}: erro ({e})"


def passo_de_texto(texto: str) -> tuple[str, str, str | None] | None:
    """'desligar luz do quarto' → ('desligar', 'luz do quarto', None) (pura)."""
    t = texto.strip().lower()
    m = re.match(r"(ligar|liga|desligar|desliga|alternar|apagar|apaga|acender|acende)\s+(?:a\s+|o\s+)?(.+)", t)
    if m:
        verbo = {"liga": "ligar", "acender": "ligar", "acende": "ligar", "desliga": "desligar", "apagar": "desligar",
                 "apaga": "desligar"}.get(m.group(1), m.group(1))
        return verbo, m.group(2), None
    m = re.match(r"(.+?)\s+(?:em|a|para)\s+(\d{1,3})\s*%", t)
    if m:
        return "brilho", m.group(1), m.group(2)
    m = re.match(r"(.+?)\s+(?:cor\s+)?(" + "|".join(sorted(CORES, key=len, reverse=True)) + r")$", t)
    if m:
        return "cor", m.group(1), m.group(2)
    return None


def rodar_cena(nome: str) -> str:
    d = carregar()
    cena = d["cenas"].get(_dobrar(nome)) or next((v for k, v in d["cenas"].items() if _dobrar(nome) in k), None)
    if not cena:
        return f"Não tenho a cena '{nome}'. Cenas: {', '.join(d['cenas']) or 'nenhuma'}."
    feitos = []
    for passo in cena:
        p = passo_de_texto(passo) if isinstance(passo, str) else None
        if p:
            feitos.append(executar(p[1], p[0], p[2]))
    return " ".join(feitos) or "A cena está vazia."


def importar(caminho: str = "") -> str:
    candidatos = [Path(caminho)] if caminho else [BASE / "devices.json", Path.home() / "devices.json",
                                                  Path.cwd() / "devices.json"]
    arq = next((c for c in candidatos if c.is_file()), None)
    if not arq:
        return ("Não achei o devices.json. Rode 'python -m tinytuya wizard' na pasta do JARVIS e peça de novo.")
    dados = json.loads(arq.read_text(encoding="utf-8"))
    ips = {}
    snap = arq.with_name("snapshot.json")
    if snap.is_file():
        try:
            for x in json.loads(snap.read_text(encoding="utf-8")).get("devices", []):
                ips[x.get("id")] = (x.get("ip"), x.get("ver") or x.get("version"))
        except Exception:
            pass
    d = carregar()
    existentes = {a["id"] for a in d["aparelhos"]}
    novos = 0
    for x in dados:
        if not x.get("id") or not x.get("key") or x["id"] in existentes:
            continue
        cat = str(x.get("category") or "")
        tipo = "lampada" if cat in ("dj", "dd", "xdd", "fwd", "dc") or re.search(r"l[aâ]mpada|luz|bulb|light", x.get("name", ""), re.I) \
            else "tomada"
        ip, ver = ips.get(x["id"], (x.get("ip"), x.get("version")))
        d["aparelhos"].append({"nome": (x.get("name") or x["id"]).strip().lower(), "id": x["id"], "chave": x["key"],
                               "ip": ip or "", "versao": str(ver or "3.3"), "tipo": tipo})
        novos += 1
    gravar_json(_ARQ, d)
    return f"Importei {novos} aparelho(s): " + ", ".join(a["nome"] for a in d["aparelhos"][-novos:]) + "." if novos \
        else "Nenhum aparelho novo no devices.json."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "importar":
            return importar(str(p.get("caminho") or ""))
        if acao == "listar":
            d = carregar()
            if not d["aparelhos"]:
                return "Nenhum aparelho cadastrado ainda. " + _SEM_LIB
            mostrar(player, "CASA INTELIGENTE", "\n".join(f"{a['nome']} ({a.get('tipo')}) — {a.get('ip') or 'IP automático'}"
                                                         for a in d["aparelhos"])
                    + ("\n\nCENAS\n" + "\n".join(f"{k}: {', '.join(v)}" for k, v in d["cenas"].items()) if d["cenas"] else ""))
            return f"{len(d['aparelhos'])} aparelho(s): " + ", ".join(a["nome"] for a in d["aparelhos"]) + "."
        if acao == "cena":
            return rodar_cena(str(p.get("nome") or ""))
        if acao == "criar_cena":
            nome = _dobrar(str(p.get("nome") or ""))
            passos = [x.strip() for x in re.split(r",|;| e (?=(?:liga|desliga|apaga|acende))", str(p.get("passos") or "")) if x.strip()]
            validos = [x for x in passos if passo_de_texto(x)]
            if not nome or not validos:
                return "Diga o nome da cena e os passos, como: desligar luz do quarto, desligar tomada da tv."
            d = carregar()
            d["cenas"][nome] = validos
            gravar_json(_ARQ, d)
            return f"Cena '{nome}' salva com {len(validos)} passo(s)."
        aparelho = str(p.get("aparelho") or "").strip()
        if acao == "status" and not aparelho:
            aparelho = "tudo"
        if not aparelho:
            return "Qual aparelho?"
        valor = p.get("nivel") if acao == "brilho" else p.get("cor")
        return executar(aparelho, acao, valor)
    except Exception as e:
        return f"A casa inteligente falhou: {e}"
