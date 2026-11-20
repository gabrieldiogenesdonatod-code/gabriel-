"""
Fish Audio — voz na nuvem, inclusive vozes clonadas (fork PT-BR 1.6).

Use em ⚙ → ENGINE & PROVIDERS, como voz do motor próprio. O avatar 3D já
mexe a boca junto com o áudio que sai (a mesma sincronia labial das outras
vozes), então uma voz do Fish Audio fala COM o rosto do JARVIS.

Pede o áudio em PCM 16 bits mono a 24 kHz, que é exatamente o que o alto-falante
do JARVIS usa: nada de decodificar ou converter.

Chave em fish.audio → API Keys. A voz é o "reference_id" de um modelo de voz
(abra a voz no site e copie o ID; vale uma voz sua, clonada lá).
"""
from __future__ import annotations

from importlib.util import find_spec
from typing import AsyncIterator

from .base import DEFAULT_CAPS, Field

API = "https://api.fish.audio/v1"
MODELS = ("s2.1-pro", "s2-pro", "s1", "s2.1-pro-free")
DEFAULT_MODEL = MODELS[0]


class FishAudioTTS:
    def __init__(self, cfg: dict):
        self.key = (cfg.get("api_key") or "").strip()
        self.voice_id = (cfg.get("voice_id") or "").strip()
        self.model = (cfg.get("model") or DEFAULT_MODEL).strip()
        self.caps = dict(DEFAULT_CAPS)
        self.caps["audio_out"] = True

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json", "model": self.model}

    def payload(self, text: str) -> dict:
        corpo = {"text": text, "format": "pcm", "sample_rate": 24000, "latency": "balanced", "normalize": True}
        if self.voice_id:
            corpo["reference_id"] = self.voice_id
        return corpo

    async def speak(self, text: str, voice: str = "") -> AsyncIterator[bytes]:
        import httpx
        if voice:
            self.voice_id = voice
        if not self.key:
            raise RuntimeError("no Fish Audio API key is set")
        text = (text or "").strip()
        if not text:
            return
        async with httpx.AsyncClient(timeout=60.0) as cl:
            async with cl.stream("POST", f"{API}/tts", headers=self._headers(), json=self.payload(text)) as r:
                if r.status_code >= 400:
                    corpo = (await r.aread()).decode("utf-8", "replace")
                    raise RuntimeError(f"Fish Audio {r.status_code}: {' '.join(corpo.split())[:160]}")
                buf = b""
                async for piece in r.aiter_bytes():
                    buf += piece
                    while len(buf) >= 2400:                  # 50 ms a 24 kHz: o "interromper" responde rápido
                        yield buf[:2400]
                        buf = buf[2400:]
                if len(buf) % 2:
                    buf = buf[:-1]
                if buf:
                    yield buf

    def probe(self) -> tuple[bool, str]:
        if not self.key:
            return False, "Sem chave da API."
        return True, f"Pronto: {self.voice_id or 'voz padrão'}, {self.model} (a chave é conferida na 1ª fala)"


def _make(cfg: dict) -> FishAudioTTS:
    return FishAudioTTS(cfg)


PROVIDER = {
    "id": "fishaudio",
    "kind": "tts",
    "label": "Fish Audio",
    "hint": "Vozes realistas e clonadas na nuvem — precisa de chave e internet",
    "requires": ("httpx",),
    "catalog": (
        {"id": "fishaudio", "label": "Fish Audio", "note": "nuvem · vozes clonadas", "local": False, "values": {}},
    ),
    "needs": (
        Field("api_key", "Chave da API", kind="secret", hint="fish.audio -> API Keys"),
        Field("voice_id", "ID da voz (reference_id)", kind="text", required=False,
              hint="abra a voz no site e copie o ID; vazio = voz padrão"),
        Field("model", "Modelo", kind="choice", choices=MODELS, default=DEFAULT_MODEL, required=False,
              hint="s2.1-pro-free é o do plano grátis de desenvolvedor"),
    ),
    "caps": {"audio_out": True},
    "factory": _make,
}


def available() -> bool:
    return find_spec("httpx") is not None
