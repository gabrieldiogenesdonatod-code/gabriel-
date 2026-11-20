"""
Ajudante para os plugins da 1.4 usarem o modelo de IA QUANDO houver um.

Regra de todos os módulos novos: funcionar sem IA (por regras, estatística e
análise de código) e ficar MELHOR com ela. `perguntar` e `perguntar_json`
devolvem None quando não há chave, não há internet ou o modelo não respondeu,
e quem chama segue pelo caminho local.

Passa pelo core/gemini.py (nunca cria um cliente próprio), então respeita o
provedor escolhido em MOTOR & PROVEDORES, os prazos e a escada de modelos.
"""

from __future__ import annotations


def disponivel() -> bool:
    try:
        from core import gemini
        return bool(gemini.api_key())
    except Exception:
        return False


def perguntar(prompt: str, inteligente: bool = False, segundos: int = 30) -> str | None:
    if not disponivel():
        return None
    try:
        from core import gemini
        r = gemini.text(prompt, tier=gemini.SMART if inteligente else gemini.FAST,
                        timeout_ms=max(10_000, segundos * 1000))
        return r.strip() or None
    except Exception as e:
        print(f"[IA] {e}")
        return None


def perguntar_json(prompt: str, inteligente: bool = True, segundos: int = 45):
    if not disponivel():
        return None
    try:
        from core import gemini
        return gemini.as_json(prompt, tier=gemini.SMART if inteligente else gemini.FAST,
                              timeout_ms=max(10_000, segundos * 1000))
    except Exception as e:
        print(f"[IA] {e}")
        return None


# ── Fork PT-BR 2.5: olhar uma imagem (nota fiscal, boleto, cômodo, celular na mão) ──
def _jpeg_reduzido(dados: bytes, lado: int = 1600) -> tuple[bytes, str]:
    try:
        import io

        from PIL import Image
        im = Image.open(io.BytesIO(dados)).convert("RGB")
        im.thumbnail((lado, lado))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return dados, "image/jpeg"


def ver_imagem(prompt: str, imagem: bytes, inteligente: bool = False, segundos: int = 40,
               lado: int = 1600) -> str | None:
    """O modelo olha a imagem e responde. None sem chave/internet (quem chama segue sem IA)."""
    if not disponivel() or not imagem:
        return None
    try:
        from google.genai import types as gtypes

        from core import gemini
        dados, mime = _jpeg_reduzido(imagem, lado)
        resp = gemini.call([gtypes.Part.from_bytes(data=dados, mime_type=mime), prompt],
                           tier=gemini.SMART if inteligente else gemini.FAST, timeout_ms=max(10_000, segundos * 1000))
        texto = (getattr(resp, "text", "") or "") if resp is not None else ""
        return texto.strip() or None
    except Exception as e:
        print(f"[IA] imagem: {e}")
        return None


def ver_imagem_json(prompt: str, imagem: bytes, inteligente: bool = False, segundos: int = 40, lado: int = 1600):
    """Como ver_imagem, mas devolve o JSON (dict/list) da resposta, ou None."""
    import json
    texto = ver_imagem(prompt + "\nResponda SÓ com JSON, sem comentários.", imagem, inteligente, segundos, lado)
    if not texto:
        return None
    ini = min([i for i in (texto.find("{"), texto.find("[")) if i >= 0], default=-1)
    fim = max(texto.rfind("}"), texto.rfind("]"))
    if ini < 0 or fim <= ini:
        return None
    try:
        return json.loads(texto[ini:fim + 1])
    except ValueError:
        return None


def ouvir_audio(prompt: str, wav: bytes, inteligente: bool = False, segundos: int = 60) -> str | None:
    """Fork PT-BR 2.7: o modelo ouve um trecho de áudio (WAV) e responde. None sem chave/internet."""
    if not disponivel() or not wav:
        return None
    try:
        from google.genai import types as gtypes

        from core import gemini
        resp = gemini.call([gtypes.Part.from_bytes(data=wav, mime_type="audio/wav"), prompt],
                           tier=gemini.SMART if inteligente else gemini.FAST, timeout_ms=max(10_000, segundos * 1000))
        texto = (getattr(resp, "text", "") or "") if resp is not None else ""
        return texto.strip() or None
    except Exception as e:
        print(f"[IA] áudio: {e}")
        return None
