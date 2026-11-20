"""
Thumbnails e capas (fork PT-BR 1.6).

Gera capas para YouTube (1280×720), post (1080×1080) e story/Reels
(1080×1920): fundo em degradê com o estilo escolhido, título grande com
contorno (quebra de linha e tamanho automáticos), uma faixa de destaque e,
se quiser, uma foto (com recorte automático e borda brilhante).

    "Jarvis, faz uma thumbnail: COMO CRIEI MEU JARVIS, estilo tech"
    "Jarvis, capa de post: PROMOÇÃO DIA DAS CRIANÇAS, com a foto C:\\fotos\\vestido.jpg"
    "Jarvis, story: NOVIDADES NA LOJA, estilo loja"

Salva em Imagens\\JARVIS\\capas e abre.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from plugins._comum import WIN, abrir_no_sistema, pasta_usuario

PLUGIN = {
    "name": "thumbnails",
    "brief": "Generates YouTube thumbnails, post and story covers with title, gradient style and optional photo.",
    "description": (
        "Thumbnail/cover generator: titulo (big text), optional destaque (small tag text), formato = youtube | post | "
        "story, estilo = tech | gamer | loja | minimal | fogo, optional foto (image path). Saves a PNG in "
        "Pictures/JARVIS/capas and opens it."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"titulo": {"type": "STRING"}, "destaque": {"type": "STRING"}, "formato": {"type": "STRING"},
                       "estilo": {"type": "STRING"}, "foto": {"type": "STRING"}},
        "required": ["titulo"],
    },
}

FORMATOS = {"youtube": (1280, 720), "post": (1080, 1080), "story": (1080, 1920)}
ESTILOS = {  # (cor de cima, cor de baixo, cor do título, contorno, faixa)
    "tech": ((6, 18, 38), (0, 92, 140), (255, 255, 255), (0, 0, 0), (0, 214, 255)),
    "gamer": ((40, 0, 60), (200, 0, 110), (255, 255, 255), (20, 0, 30), (255, 214, 0)),
    "loja": ((255, 236, 245), (255, 168, 205), (60, 20, 70), (255, 255, 255), (255, 92, 150)),
    "minimal": ((245, 245, 245), (220, 224, 230), (20, 24, 30), (255, 255, 255), (37, 99, 235)),
    "fogo": ((30, 0, 0), (230, 80, 0), (255, 240, 200), (40, 0, 0), (255, 200, 0)),
}


def fonte(tamanho: int):
    from PIL import ImageFont
    candidatos = (["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/seguibl.ttf"]
                  if WIN else []) + ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                    "/System/Library/Fonts/Supplemental/Impact.ttf"]
    for c in candidatos:
        if Path(c).exists():
            return ImageFont.truetype(c, tamanho)
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def quebrar(desenho, texto: str, largura: int, tamanho_max: int, linhas_max: int = 4):
    """Maior fonte em que o texto cabe na largura em até N linhas → (fonte, linhas)."""
    palavras = texto.split()
    tamanho = tamanho_max
    while tamanho >= 24:
        f = fonte(tamanho)
        linhas, atual = [], ""
        for w in palavras:
            teste = f"{atual} {w}".strip()
            if desenho.textlength(teste, font=f) <= largura or not atual:
                atual = teste
            else:
                linhas.append(atual)
                atual = w
        linhas.append(atual)
        if len(linhas) <= linhas_max and all(desenho.textlength(l, font=f) <= largura for l in linhas):
            return f, linhas
        tamanho -= 6
    return fonte(24), [texto[:60]]


def gerar(titulo: str, formato: str = "youtube", estilo: str = "tech", destaque: str = "", foto: str = "") -> Path:
    from PIL import Image, ImageDraw, ImageFilter
    largura, altura = FORMATOS.get(formato, FORMATOS["youtube"])
    c1, c2, cor_txt, contorno, faixa = ESTILOS.get(estilo, ESTILOS["tech"])
    img = Image.new("RGB", (largura, altura))
    d = ImageDraw.Draw(img)
    for y in range(altura):                                    # degradê vertical
        t = y / max(1, altura - 1)
        d.line([(0, y), (largura, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
    area_texto = largura
    if foto and Path(foto).is_file():
        f = Image.open(foto).convert("RGB")
        alvo_l = int(largura * (0.45 if formato == "youtube" else 0.8))
        alvo_a = int(altura * (0.9 if formato == "youtube" else 0.5))
        escala = max(alvo_l / f.width, alvo_a / f.height)
        f = f.resize((int(f.width * escala), int(f.height * escala)))
        f = f.crop(((f.width - alvo_l) // 2, (f.height - alvo_a) // 2, (f.width + alvo_l) // 2, (f.height + alvo_a) // 2))
        x = largura - alvo_l - int(largura * 0.03) if formato == "youtube" else (largura - alvo_l) // 2
        y = (altura - alvo_a) // 2 if formato == "youtube" else int(altura * 0.45)
        brilho = Image.new("RGB", (alvo_l + 40, alvo_a + 40), faixa).filter(ImageFilter.GaussianBlur(14))
        img.paste(brilho, (x - 20, y - 20))
        img.paste(f, (x, y))
        if formato == "youtube":
            area_texto = x - int(largura * 0.06)
    margem = int(largura * 0.05)
    fnt, linhas = quebrar(d, titulo.upper(), area_texto - 2 * margem, int(altura * (0.19 if formato == "youtube" else 0.1)))
    alt_linha = int(fnt.size * 1.08) if hasattr(fnt, "size") else 40
    bloco = alt_linha * len(linhas)
    y0 = (altura - bloco) // 2 if not foto or formato == "youtube" else int(altura * 0.12)
    for i, linha in enumerate(linhas):
        d.text((margem, y0 + i * alt_linha), linha, font=fnt, fill=cor_txt,
               stroke_width=max(2, alt_linha // 14), stroke_fill=contorno)
    if destaque:
        fd = fonte(max(22, int(altura * 0.05)))
        w = int(d.textlength(destaque.upper(), font=fd)) + 40
        y = max(10, y0 - int(altura * 0.1))
        d.rounded_rectangle([margem, y, margem + w, y + int(altura * 0.075)], radius=12, fill=faixa)
        d.text((margem + 20, y + int(altura * 0.012)), destaque.upper(), font=fd, fill=(0, 0, 0) if sum(faixa) > 400 else (255, 255, 255))
    pasta = pasta_usuario("Pictures") / "JARVIS" / "capas"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = re.sub(r"[^a-z0-9]+", "_", titulo.lower())[:40].strip("_") or "capa"
    destino = pasta / f"{formato}_{nome}_{time.strftime('%H%M%S')}.png"
    img.save(destino)
    return destino


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    try:
        titulo = str(p.get("titulo") or "").strip()
        if not titulo:
            return "Qual é o título da capa?"
        formato = next((f for f in FORMATOS if f in str(p.get("formato") or "").lower()), "youtube")
        if "reels" in str(p.get("formato") or "").lower():
            formato = "story"
        estilo = next((e for e in ESTILOS if e in str(p.get("estilo") or "").lower()), "tech")
        foto = str(p.get("foto") or "").strip().strip('"')
        destino = gerar(titulo, formato, estilo, str(p.get("destaque") or ""), foto)
        abrir_no_sistema(str(destino))
        return f"Capa pronta ({formato}, estilo {estilo}) em {destino}." + \
            (" Não achei a foto, então fiz sem ela." if foto and not Path(foto).is_file() else "")
    except ImportError:
        return "Preciso do Pillow (vem no requirements.txt)."
    except Exception as e:
        return f"A capa falhou: {e}"
