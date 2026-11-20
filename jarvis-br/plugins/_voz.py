"""
Voz do dono — reconhecimento de quem fala (fork PT-BR 1.5). Começa com "_": não é ferramenta.

Usa o resemblyzer (instale: pip install webrtcvad-wheels librosa scipy torch e depois
pip install resemblyzer --no-deps — o --no-deps evita que ele tente compilar o
webrtcvad original, que no Windows exige o Visual C++). Ele transforma 1–3 s de fala numa "impressão" de 256
números; a sua fica em memory/voz/dono.npy (não é gravação: não dá para ouvir
nada a partir dela). A verificação compara a impressão do ÚLTIMO PEDIDO com a sua.

Sem o resemblyzer, `disponivel()` é False e a verificação usa só rosto,
Windows e chave do celular.
"""

from __future__ import annotations

import threading

from plugins._comum import MEMORIA, cfg

PASTA = MEMORIA / "voz"
ARQ_DONO = PASTA / "dono.npy"
LIMIAR_PADRAO = 0.75
_enc = {"obj": None, "erro": ""}
_lock = threading.Lock()


def disponivel() -> bool:
    try:
        import resemblyzer  # noqa: F401
        return True
    except Exception as e:
        _enc["erro"] = str(e)
        return False


def _encoder():
    with _lock:
        if _enc["obj"] is None:
            from resemblyzer import VoiceEncoder
            _enc["obj"] = VoiceEncoder("cpu", verbose=False)
        return _enc["obj"]


def impressao(pcm_int16):
    """Embedding normalizado (256) de um trecho de fala 16 kHz. None se curto/sem voz."""
    import numpy as np
    from resemblyzer import preprocess_wav
    wav = preprocess_wav(pcm_int16.astype("float32") / 32768.0, source_sr=16000)
    if len(wav) < 16000 * 0.8:
        return None
    e = _encoder().embed_utterance(wav)
    n = float(np.linalg.norm(e)) or 1.0
    return e / n


def semelhanca(a, b) -> float:
    import numpy as np
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


def limiar() -> float:
    try:
        return float(str(cfg("voz_dono").get("limiar") or LIMIAR_PADRAO).replace(",", "."))
    except ValueError:
        return LIMIAR_PADRAO


def perfil():
    import numpy as np
    if not ARQ_DONO.exists():
        return None
    try:
        d = np.load(ARQ_DONO)
        return d if d.ndim == 1 else d.mean(axis=0)
    except Exception:
        return None


def salvar_perfil(impressoes: list) -> None:
    import numpy as np
    PASTA.mkdir(parents=True, exist_ok=True)
    media = np.mean(np.stack(impressoes), axis=0)
    media = media / (float(np.linalg.norm(media)) or 1.0)
    np.save(ARQ_DONO, media.astype("float32"))


def comparar_trecho(pcm_int16) -> float | None:
    if not disponivel():
        return None
    p = perfil()
    if p is None or pcm_int16 is None:
        return None
    e = impressao(pcm_int16)
    return None if e is None else semelhanca(e, p)


def verificar_ultimo_pedido() -> bool | None:
    """True/False para o último trecho de fala; None se não dá para saber."""
    try:
        from core import escuta
        s = comparar_trecho(escuta.ultimo_trecho())
    except Exception as e:
        print(f"[Voz] {e}")
        return None
    if s is None:
        return None
    return s >= limiar()
