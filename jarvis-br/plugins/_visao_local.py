"""
Visão no próprio PC (fork PT-BR 2.5). Começa com "_": não é ferramenta.

Detector de objetos do MediaPipe (EfficientDet-Lite0, as 80 classes do COCO:
celular, controle remoto, notebook, copo, livro, mochila…) + o detector de mãos
que os gestos já usam. Roda no PC, sem mandar imagem para ninguém; o modelo
(4 MB) é baixado uma vez para config/modelos/.

Quem usa: o pomodoro ("Senhor, o celular pode esperar mais 12 minutos") e a
câmera do quarto (o que o COCO conhece, quando não há chave do Gemini).
Sem mediapipe, as funções devolvem None e quem chama segue sem visão local.
"""

from __future__ import annotations

import threading
import urllib.request

from plugins._comum import CONFIG

MODELO = CONFIG / "modelos" / "efficientdet_lite0.tflite"
URL = ("https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/latest/"
       "efficientdet_lite0.tflite")
NOMES = {"cell phone": "celular", "remote": "controle", "laptop": "notebook", "keyboard": "teclado",
         "mouse": "mouse", "cup": "copo", "bottle": "garrafa", "book": "livro", "scissors": "tesoura",
         "backpack": "mochila", "handbag": "bolsa", "umbrella": "guarda-chuva", "tv": "TV", "person": "pessoa",
         "clock": "relógio", "cat": "gato", "dog": "cachorro", "wine glass": "taça", "bowl": "tigela",
         "toothbrush": "escova de dentes", "hair drier": "secador", "teddy bear": "bichinho de pelúcia",
         "sports ball": "bola", "chair": "cadeira", "bed": "cama", "couch": "sofá", "dining table": "mesa"}
_lock = threading.Lock()
_det = {"obj": None, "mao": None, "erro": ""}


def disponivel() -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec("mediapipe") is not None
    except Exception:
        return False


def _objetos():
    with _lock:
        if _det["obj"] is None and not _det["erro"]:
            try:
                from mediapipe.tasks.python import BaseOptions, vision
                if not MODELO.exists():
                    MODELO.parent.mkdir(parents=True, exist_ok=True)
                    with urllib.request.urlopen(URL, timeout=60) as r:
                        MODELO.write_bytes(r.read())
                op = vision.ObjectDetectorOptions(base_options=BaseOptions(model_asset_path=str(MODELO)),
                                                  running_mode=vision.RunningMode.IMAGE, max_results=12,
                                                  score_threshold=0.3)
                _det["obj"] = vision.ObjectDetector.create_from_options(op)
            except Exception as e:
                _det["erro"] = str(e)
                print(f"[Visão] detector de objetos indisponível: {e}")
        return _det["obj"]


def _maos():
    with _lock:
        if _det["mao"] is None:
            try:
                from mediapipe.tasks.python import BaseOptions, vision

                from plugins.gestos import MODELO as MODELO_MAO
                from plugins.gestos import URL_MODELO
                if not MODELO_MAO.exists():
                    MODELO_MAO.parent.mkdir(parents=True, exist_ok=True)
                    with urllib.request.urlopen(URL_MODELO, timeout=60) as r:
                        MODELO_MAO.write_bytes(r.read())
                op = vision.HandLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODELO_MAO)),
                                                  running_mode=vision.RunningMode.IMAGE, num_hands=2,
                                                  min_hand_detection_confidence=0.5)
                _det["mao"] = vision.HandLandmarker.create_from_options(op)
            except Exception as e:
                print(f"[Visão] detector de mãos indisponível: {e}")
                _det["mao"] = False
        return _det["mao"] or None


def _imagem(bgr):
    import mediapipe as mp
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=bgr[:, :, ::-1].copy())


def detectar(bgr) -> list[dict] | None:
    """[{'nome': 'cell phone', 'nome_pt': 'celular', 'score': .8, 'caixa': (x, y, w, h) de 0 a 1}] ou None."""
    det = _objetos() if disponivel() else None
    if det is None or bgr is None:
        return None
    h, w = bgr.shape[:2]
    saida = []
    for d in det.detect(_imagem(bgr)).detections:
        cat = d.categories[0]
        b = d.bounding_box
        saida.append({"nome": cat.category_name, "nome_pt": NOMES.get(cat.category_name, cat.category_name),
                      "score": round(float(cat.score), 2),
                      "caixa": (b.origin_x / w, b.origin_y / h, b.width / w, b.height / h)})
    return saida


def maos(bgr) -> list[list[tuple[float, float]]] | None:
    """Pontos das mãos (x, y de 0 a 1) ou None se não há detector."""
    det = _maos() if disponivel() else None
    if det is None or bgr is None:
        return None
    return [[(p.x, p.y) for p in mao] for mao in det.detect(_imagem(bgr)).hand_landmarks]


def celular_na_mao_puro(objetos: list[dict], pontos_maos: list | None, minimo: float = 0.35) -> bool:
    """Tem celular E uma mão encostando nele? Sem detector de mãos: celular erguido e bem visto (puro)."""
    celulares = [o for o in objetos if o["nome"] == "cell phone" and o["score"] >= minimo]
    for c in celulares:
        x, y, w, h = c["caixa"]
        mx, my = 0.25 * w + 0.03, 0.25 * h + 0.03
        if pontos_maos is None:
            if c["score"] >= 0.5 and y + h / 2 < 0.8:
                return True
            continue
        for mao in pontos_maos:
            if any(x - mx <= px <= x + w + mx and y - my <= py <= y + h + my for px, py in mao):
                return True
    return False


def celular_na_mao(bgr) -> bool | None:
    objs = detectar(bgr)
    if objs is None:
        return None
    if not any(o["nome"] == "cell phone" for o in objs):
        return False
    return celular_na_mao_puro(objs, maos(bgr))


def onde_na_imagem(caixa: tuple) -> str:
    """'à esquerda, embaixo' — onde está a caixa na foto (puro)."""
    x, y, w, h = caixa
    cx, cy = x + w / 2, y + h / 2
    lado = "à esquerda" if cx < 0.36 else "à direita" if cx > 0.64 else "no meio"
    altura = "em cima" if cy < 0.36 else "embaixo" if cy > 0.64 else ""
    return f"{lado}{', ' + altura if altura else ''} da imagem"


def miniatura_cinza(bgr, lado: int = 64):
    import cv2
    return cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (lado, int(lado * 3 / 4)), interpolation=cv2.INTER_AREA)


def mudou(antes, agora, limite: float = 7.0) -> bool:
    """A cena mudou (média da diferença dos tons de cinza)? (puro)"""
    import numpy as np
    if antes is None or agora is None:
        return True
    return float(np.abs(np.asarray(antes, float) - np.asarray(agora, float)).mean()) > limite
