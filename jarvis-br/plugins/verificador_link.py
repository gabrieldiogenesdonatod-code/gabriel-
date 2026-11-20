"""
Verificador de link e arquivo (fork PT-BR 2.16, ideia 19).

    "Jarvis, esse link é seguro?"               (o link copiado)
    "Jarvis, verifica https://promo-pix.xyz/…"
    "Jarvis, esse arquivo que eu baixei é vírus?"  (o mais novo de Downloads)
    "Jarvis, verifica o arquivo C:\\Users\\eu\\Downloads\\setup.exe"

Consulta o VirusTotal (mais de 70 antivírus de uma vez). Precisa de uma chave
GRATUITA: crie a conta em virustotal.com → seu perfil → API Key, e cole em
⚙ → Verificador de link. Limite do plano grátis: 4 consultas por minuto e 500
por dia, só uso pessoal.

PRIVACIDADE: para arquivos ele manda SÓ o SHA-256 (a "impressão digital"), não
o arquivo. Se o VirusTotal nunca viu aquele arquivo, ele diz isso e NÃO envia
nada sozinho. Links, sim, são enviados (é assim que o serviço funciona); não
use para links com dados pessoais (de recuperação de senha, por exemplo).

Antes de consultar, faz uma checagem local rápida: domínio que imita banco ou
loja conhecida, encurtador, IP no lugar do nome, extensão perigosa (.exe, .scr,
.bat dentro de um .zip "foto.jpg.exe").
"""

from __future__ import annotations

import base64
import hashlib
import re
import time
from pathlib import Path

from plugins import _web
from plugins._comum import cfg, mostrar, pasta_usuario

PLUGIN = {
    "name": "verificador_link",
    "brief": "Check a link or downloaded file against VirusTotal (70+ antivirus) plus local red-flag checks.",
    "description": (
        "Link/file safety check. action='link' with optional url (default: copied link). action='arquivo' with optional "
        "caminho (default: newest file in Downloads) — only the SHA-256 is sent. Report the verdict plainly: safe, "
        "suspicious or dangerous, with the number of engines that flagged it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "link | arquivo"},
                       "url": {"type": "STRING"}, "caminho": {"type": "STRING"}},
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {"namespace": "verificador_link", "title": "Verificador de link",
                   "fields": [{"key": "virustotal_key", "label": "Chave da API do VirusTotal (grátis)",
                               "type": "password", "default": ""}]}

VT = "https://www.virustotal.com/api/v3"
MARCAS = ("itau", "bradesco", "santander", "caixa", "bancodobrasil", "nubank", "bancointer", "c6bank", "mercadopago",
          "mercadolivre", "magalu", "magazineluiza", "americanas", "shopee", "amazon", "netflix", "whatsapp",
          "instagram", "facebook", "gov", "receita", "correios", "detran", "serasa", "picpay", "paypal")
OFICIAIS = ("itau.com.br", "bradesco.com.br", "santander.com.br", "caixa.gov.br", "bb.com.br", "nubank.com.br",
            "bancointer.com.br", "inter.co", "c6bank.com.br", "mercadopago.com.br", "mercadolivre.com.br",
            "magazineluiza.com.br", "magalu.com", "americanas.com.br", "shopee.com.br", "amazon.com.br", "amazon.com",
            "netflix.com", "whatsapp.com", "instagram.com", "facebook.com", "gov.br", "correios.com.br",
            "serasa.com.br", "picpay.com", "paypal.com")
ENCURTADORES = ("bit.ly", "tinyurl.com", "cutt.ly", "encurtador.com.br", "is.gd", "t.co", "rebrand.ly", "shorturl.at")
PERIGOSAS = (".exe", ".scr", ".bat", ".cmd", ".msi", ".vbs", ".js", ".jar", ".ps1", ".apk", ".com", ".pif", ".lnk")


def dominio(url: str) -> str:
    m = re.match(r"^[a-z]+://([^/:?#]+)", url.strip().lower())
    return re.sub(r"^www\.", "", m.group(1)) if m else ""


def sinais_locais(url: str) -> list[str]:
    """Bandeiras vermelhas sem internet (pura)."""
    d = dominio(url)
    sinais = []
    if not d:
        return ["não parece um link válido"]
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", d):
        sinais.append("usa um número IP no lugar do nome do site")
    if d in ENCURTADORES:
        sinais.append("é um link encurtado: o destino real fica escondido")
    oficial = any(d == o or d.endswith("." + o) for o in OFICIAIS)
    plano = d.replace("-", "").replace(".", "")
    imita = [m for m in MARCAS if m in plano]
    if imita and not oficial:
        sinais.append(f"usa o nome '{imita[0]}' mas não é o site oficial")
    if re.search(r"\.(xyz|top|click|buzz|rest|icu|monster|sbs|cfd|live|shop)$", d):
        sinais.append("termina num domínio muito usado em golpes")
    if d.count("-") >= 3 or len(d) > 45:
        sinais.append("o endereço é longo e estranho")
    if url.lower().startswith("http://") and any(k in url.lower() for k in ("login", "senha", "pix", "pagamento", "conta")):
        sinais.append("pede dados sem cadeado (http, sem s)")
    if Path(url.split("?")[0]).suffix.lower() in PERIGOSAS:
        sinais.append("baixa um programa direto")
    return sinais


def sinais_arquivo(caminho: Path) -> list[str]:
    nome = caminho.name.lower()
    sinais = []
    partes = nome.split(".")
    if len(partes) >= 3 and "." + partes[-1] in PERIGOSAS and partes[-2] in ("jpg", "png", "pdf", "doc", "docx", "mp4", "xlsx"):
        sinais.append(f"nome disfarçado: parece .{partes[-2]} mas é .{partes[-1]} (programa)")
    elif caminho.suffix.lower() in PERIGOSAS:
        sinais.append("é um programa/script: só abra se você sabe de onde veio")
    return sinais


def veredito(stats: dict) -> tuple[str, int, int]:
    """('seguro' | 'suspeito' | 'perigoso', alertas, total) (pura)."""
    mal, sus = int(stats.get("malicious", 0)), int(stats.get("suspicious", 0))
    total = sum(int(v) for v in stats.values() if isinstance(v, (int, float)))
    if mal >= 3:
        return "perigoso", mal + sus, total
    if mal or sus >= 2:
        return "suspeito", mal + sus, total
    return "seguro", mal + sus, total


def _chave() -> str:
    return str(cfg("verificador_link", PLUGIN_SETTINGS).get("virustotal_key") or "").strip()


def checar_link(url: str) -> tuple[str, str]:
    sinais = sinais_locais(url)
    k = _chave()
    if not k:
        base = "Sem a chave do VirusTotal, olhei só por fora: "
        return (base + ("; ".join(sinais) + ". Eu não abriria." if sinais else "não vi nada estranho, mas isso não "
                        "garante que é seguro.")), ""
    id_ = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    h = {"x-apikey": k}
    try:
        d = _web.get_json(f"{VT}/urls/{id_}", headers=h)
    except _web.ErroWeb as e:
        if e.status != 404:
            raise
        _web.post_json(f"{VT}/urls", {"url": url}, h, form=True)
        time.sleep(15)
        try:
            d = _web.get_json(f"{VT}/urls/{id_}", headers=h)
        except _web.ErroWeb:
            return ("O VirusTotal ainda está analisando esse link (é novo para eles). " +
                    ("Por fora: " + "; ".join(sinais) + "." if sinais else "Pergunte de novo em um minuto.")), ""
    at = d.get("data", {}).get("attributes", {})
    v, alertas, total = veredito(at.get("last_analysis_stats", {}))
    quem = [f"{n}: {r.get('result')}" for n, r in (at.get("last_analysis_results") or {}).items()
            if r.get("category") in ("malicious", "suspicious")][:12]
    painel = "\n".join([f"Link: {url}", f"Veredito: {v.upper()} ({alertas} de {total} antivírus)"] +
                       ([f"Sinais: {s}" for s in sinais]) + ([""] + quem if quem else []))
    fala = {"seguro": f"Parece seguro: nenhum dos {total} antivírus acusou",
            "suspeito": f"Suspeito: {alertas} de {total} antivírus acusaram",
            "perigoso": f"PERIGOSO: {alertas} de {total} antivírus dizem que é golpe ou vírus. Não abra"}[v]
    if sinais and v == "seguro":
        fala += ", mas por fora " + "; ".join(sinais)
    return fala + ".", painel


def _mais_novo() -> Path | None:
    pasta = pasta_usuario("Downloads")
    arqs = [f for f in pasta.iterdir() if f.is_file() and not f.name.endswith((".crdownload", ".part", ".tmp"))] \
        if pasta.exists() else []
    return max(arqs, key=lambda f: f.stat().st_mtime) if arqs else None


def checar_arquivo(caminho: Path) -> tuple[str, str]:
    sinais = sinais_arquivo(caminho)
    sha = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            sha.update(bloco)
    h = sha.hexdigest()
    k = _chave()
    if not k:
        return ("Sem a chave do VirusTotal não consigo consultar. " + ("; ".join(sinais) + "." if sinais else "")), ""
    try:
        d = _web.get_json(f"{VT}/files/{h}", headers={"x-apikey": k})
    except _web.ErroWeb as e:
        if e.status == 404:
            return (f"O VirusTotal nunca viu {caminho.name}. Isso não quer dizer que é seguro: é só que é raro. "
                    + ("; ".join(sinais) + ". " if sinais else "") + "Se quiser, envie você mesmo em virustotal.com."), ""
        raise
    at = d.get("data", {}).get("attributes", {})
    v, alertas, total = veredito(at.get("last_analysis_stats", {}))
    nome_ameaca = (at.get("popular_threat_classification") or {}).get("suggested_threat_label", "")
    fala = {"seguro": f"{caminho.name} parece seguro: nenhum dos {total} antivírus acusou",
            "suspeito": f"{caminho.name} é suspeito: {alertas} de {total} antivírus acusaram",
            "perigoso": f"{caminho.name} é PERIGOSO: {alertas} de {total} antivírus acusaram"
                        + (f" ({nome_ameaca})" if nome_ameaca else "") + ". Não abra e apague"}[v]
    if sinais:
        fala += ". Atenção: " + "; ".join(sinais)
    return fala + ".", f"Arquivo: {caminho}\nSHA-256: {h}\nVeredito: {v} ({alertas}/{total})"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "link").lower()
    try:
        if a == "arquivo":
            c = Path(str(p.get("caminho") or "").strip().strip('"')) if p.get("caminho") else _mais_novo()
            if not c or not c.exists():
                return "Não achei o arquivo."
            fala, painel = checar_arquivo(c)
        else:
            url = str(p.get("url") or "").strip()
            if not url:
                try:
                    import pyperclip
                    url = pyperclip.paste().strip()
                except Exception:
                    url = ""
            m = re.search(r"(https?://\S+|\b[\w-]+(\.[\w-]+)+/\S*)", url)
            if not m:
                return "Copie o link (ou diga) e me peça de novo."
            url = m.group(0) if m.group(0).startswith("http") else "http://" + m.group(0)
            fala, painel = checar_link(url)
        if painel:
            mostrar(player, "VERIFICADOR", painel)
        return fala
    except _web.ErroWeb as e:
        if e.status == 429:
            return "Passou do limite grátis do VirusTotal (4 por minuto). Tente em um minuto."
        if e.status in (401, 403):
            return "A chave do VirusTotal não foi aceita. Confira em ⚙ → Verificador de link."
        return f"Não consegui consultar agora: {e}."
    except Exception as e:
        return f"O verificador falhou: {e}"
