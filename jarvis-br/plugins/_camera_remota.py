"""
Câmeras e tela para ver de longe (fork PT-BR 1.8). Começa com "_": não é ferramenta.

Fontes: a webcam do PC (a mesma que o resto do JARVIS usa) e câmeras IP que
você cadastrar em ⚙ → Acesso remoto ("Garagem=rtsp://usuario:senha@192.168.0.30/stream1").
A câmera só fica aberta enquanto alguém está olhando: 20 s sem pedido, fecha
(e a luzinha da webcam apaga). Tudo opcional: sem opencv, a câmera responde com
uma frase; a tela usa o mss + Pillow.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

from plugins._comum import MEMORIA

OCIOSA_S = 20
_fontes: dict = {}
_lock = threading.Lock()


def ler_cameras_ip(texto: str) -> list[dict]:
    """'Garagem=rtsp://…; Portão=http://…/snapshot.jpg' → [{'nome', 'fonte'}] (pura)."""
    saida = []
    for parte in str(texto or "").replace("\n", ";").split(";"):
        if "=" not in parte:
            continue
        nome, fonte = parte.split("=", 1)
        nome, fonte = nome.strip(), fonte.strip()
        if nome and fonte.lower().startswith(("rtsp://", "http://", "https://")):
            saida.append({"nome": nome, "fonte": fonte})
    return saida


def cameras() -> list[dict]:
    """[{'id': 0, 'nome': 'Webcam do PC'}, {'id': 1, 'nome': 'Garagem'}, …] (sem a URL, que tem senha)."""
    lista = [{"id": 0, "nome": "Webcam do PC", "fonte": None}]
    try:
        from plugins._comum import cfg
        from plugins.acesso_remoto import PLUGIN_SETTINGS
        extras = ler_cameras_ip(cfg("acesso_remoto", PLUGIN_SETTINGS).get("cameras_ip", ""))
    except Exception:
        extras = []
    lista += [{"id": i + 1, "nome": c["nome"], "fonte": c["fonte"]} for i, c in enumerate(extras)]
    return lista


class _Fonte:
    def __init__(self, origem):
        self.origem = origem
        self.cap = None
        self.quadro = None
        self.quando = 0.0
        self.uso = time.time()
        self.erro = ""
        self.trava = threading.Lock()
        threading.Thread(target=self._rodar, daemon=True, name="camera-remota").start()

    def _abrir(self):
        import cv2
        if self.origem is None:
            from plugins.reconhecimento_facial import _open_camera
            return _open_camera()
        cap = cv2.VideoCapture(self.origem)
        return cap if cap.isOpened() else None

    def _rodar(self):
        try:
            self.cap = self._abrir()
        except ImportError:
            self.erro = "falta o opencv (python -m pip install opencv-python)"
        except Exception as e:
            self.erro = str(e)
        if self.cap is None and not self.erro:
            self.erro = "a câmera não abriu (pode estar em uso por outro programa)"
        falhas = 0
        while self.cap is not None and time.time() - self.uso < OCIOSA_S:
            ok, q = self.cap.read()
            if ok:
                falhas = 0
                with self.trava:
                    self.quadro, self.quando = q, time.time()
            else:
                falhas += 1
                if falhas > 50:
                    self.erro = "a câmera parou de mandar imagem"
                    break
                time.sleep(0.1)
        if self.cap is not None:
            self.cap.release()
        with _lock:
            for k, v in list(_fontes.items()):
                if v is self:
                    del _fontes[k]

    def ultimo(self, espera_s: float = 6):
        self.uso = time.time()
        fim = time.time() + espera_s
        while time.time() < fim:
            with self.trava:
                if self.quadro is not None and time.time() - self.quando < 3:
                    return self.quadro
            if self.erro:
                return None
            time.sleep(0.05)
        return None


def quadro(cam_id: int = 0, espera_s: float = 6):
    """(imagem BGR do opencv | None, erro). Compartilhada: Central, gestos e presença usam a mesma câmera aberta."""
    lista = {c["id"]: c for c in cameras()}
    if cam_id not in lista:
        return None, "câmera não encontrada"
    with _lock:
        fonte = _fontes.get(cam_id)
        if fonte is None:
            fonte = _fontes[cam_id] = _Fonte(lista[cam_id]["fonte"])
    q = fonte.ultimo(espera_s)
    return (q, "") if q is not None else (None, fonte.erro or "sem imagem da câmera")


def liberar(cam_id: int = 0) -> None:
    """Fork PT-BR 2.5: solta a câmera (o laço fecha no próximo quadro), para o navegador poder usá-la
    (holograma na mão). Quem pedir um quadro depois abre de novo."""
    with _lock:
        f = _fontes.get(cam_id)
    if f is not None:
        f.uso = 0.0


def foto_jpeg(cam_id: int = 0, largura: int = 960, qualidade: int = 70) -> tuple[bytes | None, str]:
    """(jpeg, erro). Mantém a câmera aberta enquanto houver pedidos."""
    img, erro = quadro(cam_id)
    if img is None:
        return None, erro
    try:
        import cv2
        h, w = img.shape[:2]
        if w > largura:
            img = cv2.resize(img, (largura, int(h * largura / w)))
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), qualidade])
        return (buf.tobytes(), "") if ok else (None, "não consegui codificar a imagem")
    except Exception as e:
        return None, str(e)


def tela_jpeg(largura: int = 1280, qualidade: int = 60) -> tuple[bytes | None, str]:
    try:
        import mss
        from PIL import Image
    except ImportError:
        return None, "falta o mss/Pillow"
    try:
        with mss.mss() as s:
            g = s.grab(s.monitors[1] if len(s.monitors) > 1 else s.monitors[0])
            img = Image.frombytes("RGB", g.size, g.bgra, "raw", "BGRX")
        if img.width > largura:
            img = img.resize((largura, int(img.height * largura / img.width)))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=qualidade)
        return buf.getvalue(), ""
    except Exception as e:
        return None, str(e)


def salvar(dados: bytes, nome: str) -> Path:
    pasta = MEMORIA / "remoto"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"{nome}_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    arq.write_bytes(dados)
    for velho in sorted(pasta.glob("*.jpg"))[:-30]:            # guarda só as 30 últimas
        velho.unlink(missing_ok=True)
    return arq
