"""
Renomeador de fotos pelo conteúdo (fork PT-BR 2.11).

Pega fotos com nome sem graça (IMG_2026.jpg, WhatsApp-Image-...jpg) e renomeia pelo
que APARECE nelas, com o ano: "praia_2026_amigos.jpg", "cachorro_2026.jpg".

    "Jarvis, renomeia as fotos da pasta Imagens."
    "Jarvis, dá uma olhada e sugere nomes pras fotos de downloads."  (só sugere, não mexe)

Usa a visão do JARVIS (precisa da chave do Gemini). O ano vem da data da foto (EXIF)
ou da data do arquivo. Por segurança, ele PRIMEIRO mostra o antes→depois e só renomeia
com a sua confirmação; nunca apaga nada e nunca troca a extensão.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from plugins._comum import confirmar, mostrar, pasta_usuario

PLUGIN = {
    "name": "renomear_fotos",
    "brief": "Renames photos by what's in them (+year), e.g. praia_2026_amigos.jpg. Preview first, rename on confirm.",
    "description": (
        "Renames image files based on their visual content plus the year (e.g. 'praia_2026_amigos.jpg'). Needs the "
        "Gemini vision. action='sugerir' (default: just preview old→new names, change nothing) or 'renomear' "
        "(applies, after the user confirms). pasta = folder (default Pictures); quantas = max files (default 30). "
        "Use for 'renomeia as fotos da pasta X', 'dá nomes melhores pras minhas fotos'. Never deletes or changes "
        "the file extension."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "sugerir | renomear"},
            "pasta": {"type": "STRING", "description": "folder with the photos (default: Pictures)"},
            "quantas": {"type": "NUMBER", "description": "max photos this run (default 30)"},
        },
    },
}

EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".gif"}
GENERICO = re.compile(r"(?i)^(img|image|dsc|foto|photo|screenshot|captura|whatsapp|pxl|gopro|_|\d)")
MAX_PADRAO = 30


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def slug(texto: str, limite: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", dobrar(texto)).strip("_")
    return s[:limite].strip("_")


def ano_de(exif_ano: str | None, mtime_ano: int) -> int:
    """Ano da foto: do EXIF (AAAA:MM:DD...) se der, senão da data do arquivo (puro)."""
    m = re.match(r"\s*(\d{4})", str(exif_ano or ""))
    if m:
        ano = int(m.group(1))
        if 1990 <= ano <= 2100:
            return ano
    return mtime_ano


def montar_nome(assunto: str, ano: int, detalhe: str = "", ext: str = ".jpg") -> str:
    """'praia' + 2026 + 'amigos' → 'praia_2026_amigos.jpg' (puro)."""
    base = slug(assunto) or "foto"
    partes = [base, str(ano)]
    d = slug(detalhe)
    if d and d not in base:
        partes.append(d)
    return "_".join(partes)[:70] + (ext.lower() if ext else ".jpg")


def resolver_conflitos(planos: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    """Garante nomes únicos na pasta (acrescenta _2, _3) e não renomeia pro mesmo nome (puro-ish)."""
    usados: dict[str, int] = {}
    saida = []
    for origem, nome in planos:
        existentes = {p.name.lower() for p in origem.parent.iterdir()} if origem.parent.exists() else set()
        existentes.discard(origem.name.lower())
        base, ext = (nome.rsplit(".", 1) + [""])[:2]
        cand, n = nome, 1
        while cand.lower() in existentes or usados.get(cand.lower()):
            n += 1
            cand = f"{base}_{n}.{ext}" if ext else f"{base}_{n}"
        usados[cand.lower()] = 1
        saida.append((origem, cand))
    return saida


def eh_generico(nome: str) -> bool:
    """O nome atual é 'sem graça' (vale renomear)? (puro)"""
    return bool(GENERICO.match(Path(nome).stem))


# ── visão + arquivos ─────────────────────────────────────────────────────────
def _pasta(pasta: str) -> Path:
    p = str(pasta or "").strip()
    if not p:
        return pasta_usuario("Pictures")
    cam = Path(p).expanduser()
    if not cam.is_absolute() and not cam.exists():
        for base in ("Pictures", "Downloads", "Desktop", "Documents"):
            alt = pasta_usuario(base) / p
            if alt.exists():
                return alt
    return cam


def _ano_arquivo(caminho: Path) -> int:
    import datetime
    exif_ano = None
    try:
        from PIL import Image
        img = Image.open(caminho)
        exif = img.getexif()
        exif_ano = exif.get(36867) or exif.get(306) or (exif.get_ifd(0x8769).get(36867) if exif else None)
    except Exception:
        exif_ano = None
    try:
        mtime_ano = datetime.datetime.fromtimestamp(caminho.stat().st_mtime).year
    except OSError:
        mtime_ano = datetime.date.today().year
    return ano_de(exif_ano, mtime_ano)


def _ver(caminho: Path) -> tuple[str, str]:
    """(assunto, detalhe) do conteúdo da foto, pela visão. ('', '') se não der."""
    try:
        from plugins import _ia
        dados = caminho.read_bytes()
        j = _ia.ver_imagem_json(
            "Dê um nome curto de arquivo para esta foto, pelo que aparece nela. Responda "
            "{\"assunto\": \"2 a 4 palavras em português, minúsculas, sem acento\", "
            "\"detalhe\": \"opcional, 1 palavra, ex. lugar ou quem\"}.", dados, inteligente=False, segundos=30) or {}
        return str(j.get("assunto") or "").strip(), str(j.get("detalhe") or "").strip()
    except Exception as e:
        print(f"[Fotos] visão: {e}")
        return "", ""


def planejar(pasta: Path, quantas: int) -> tuple[list[tuple[Path, str]], int]:
    """Olha as fotos e devolve (planos antes→depois, quantas foram ignoradas por já ter bom nome)."""
    fotos = sorted((p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXT),
                   key=lambda p: p.stat().st_mtime)
    planos, puladas = [], 0
    for foto in fotos:
        if len(planos) >= quantas:
            break
        if not eh_generico(foto.name):
            puladas += 1
            continue
        assunto, detalhe = _ver(foto)
        if not assunto:
            continue
        novo = montar_nome(assunto, _ano_arquivo(foto), detalhe, foto.suffix)
        if novo.lower() != foto.name.lower():
            planos.append((foto, novo))
    return resolver_conflitos(planos), puladas


def _aplicar(planos: list[tuple[Path, str]]) -> str:
    feitas = 0
    for origem, nome in planos:
        try:
            origem.rename(origem.with_name(nome))
            feitas += 1
        except OSError as e:
            print(f"[Fotos] não renomeei {origem.name}: {e}")
    return f"Renomeei {feitas} de {len(planos)} fotos."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "sugerir").strip()
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return ("Pra renomear pelo conteúdo eu preciso da visão (Gemini) ligada — coloque a chave em ⚙ MOTOR & "
                    "PROVEDORES.")
    except Exception:
        pass
    pasta = _pasta(p.get("pasta") or "")
    if not pasta.exists() or not pasta.is_dir():
        return f"Não achei a pasta {pasta}. Diga o nome certo (ex.: 'as fotos da pasta Imagens')."
    try:
        quantas = int(float(p.get("quantas") or MAX_PADRAO))
    except (ValueError, TypeError):
        quantas = MAX_PADRAO
    quantas = max(1, min(100, quantas))
    planos, puladas = planejar(pasta, quantas)
    if not planos:
        return (f"Olhei {pasta.name} e não achei fotos pra renomear" +
                (f" ({puladas} já têm nome bom)." if puladas else " (sem fotos com nome genérico)."))
    previa = "\n".join(f"{o.name}  →  {novo}" for o, novo in planos[:30])
    mostrar(player, f"RENOMEAR FOTOS · {pasta.name}", previa)
    if acao in ("renomear", "aplicar", "pode", "confirmar", "sim"):
        return confirmar("renomear_fotos", f"Renomear {len(planos)} fotos em {pasta.name}",
                         f"{len(planos)} fotos vão ganhar nomes novos pelo conteúdo. Nada é apagado.",
                         lambda: _aplicar(planos))
    return (f"Olhei {pasta.name}: {len(planos)} fotos dá pra renomear pelo conteúdo (mostrei o antes→depois na "
            f"tela). Quer que eu renomeie? É só dizer 'pode renomear'. Nada é apagado.")
