"""
Reconhecimento facial do dono — plugin do J.A.R.V.I.S BR.

O que faz
    * CADASTRAR: olha para você pela webcam por alguns segundos e guarda uma
      "assinatura" numérica do seu rosto (não guarda foto nenhuma).
    * IDENTIFICAR: diz quem está na frente da câmera agora.
    * VIGIAR: fica de olho em segundo plano. Quando você senta depois de um
      tempo fora, o JARVIS te cumprimenta; se aparecer alguém que não é você,
      ele avisa.
    * ESQUECER: apaga o cadastro.

Como funciona
    Usa dois modelos que já vêm prontos para o OpenCV (que o JARVIS já instala):
    YuNet para achar rostos na imagem e SFace para transformar cada rosto em 128
    números. Dois rostos da mesma pessoa dão números parecidos; a comparação é a
    "similaridade de cosseno". Nada de dlib, nada de compilar nada no Windows.

    Os modelos (~39 MB no total) são baixados uma vez, na primeira vez que o
    plugin é usado, para `config/modelos_rosto/`.

Privacidade
    O cadastro fica em `memory/rostos/dono.npy`, só no seu computador, e está no
    .gitignore. Pessoas desconhecidas NUNCA são gravadas: o plugin só diz que
    viu alguém, e esquece em seguida.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

PLUGIN = {
    "name": "reconhecimento_facial",
    "description": (
        "Face recognition of the computer's owner through the webcam. "
        "action='cadastrar' when the user asks you to learn / remember / register "
        "their face ('lembra do meu rosto', 'cadastra meu rosto'). "
        "action='identificar' when they ask who is in front of the camera or "
        "whether you recognise them ('quem sou eu', 'você me reconhece'). "
        "action='vigiar_ligar' / 'vigiar_desligar' to start or stop watching the "
        "camera in the background, greeting the owner when they sit down and "
        "warning about strangers. action='esquecer' to delete the stored face. "
        "action='status' to say whether a face is registered and if watching is on. "
        "Do NOT use screen_process for these — this tool does its own capture. "
        "Use screen_process only to DESCRIBE what the camera shows."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "cadastrar | identificar | vigiar_ligar | "
                               "vigiar_desligar | esquecer | status",
            },
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "reconhecimento_facial",
    "title": "Reconhecimento facial",
    "fields": [
        {"key": "vigia_automatica", "label": "Vigiar a câmera ao ligar o JARVIS",
         "type": "toggle", "default": False},
        {"key": "rigor", "label": "Rigor do reconhecimento",
         "type": "choice", "options": ["normal", "rigoroso", "flexível"],
         "default": "normal"},
        {"key": "intervalo", "label": "Segundos entre cada olhada da vigia",
         "type": "text", "default": "8", "placeholder": "8"},
        {"key": "bloquear_ausencia_min",
         "label": "Bloquear o PC quando eu sair da frente por (minutos; 0 = nunca)",
         "type": "text", "default": "0", "placeholder": "0"},
    ],
}

# ── caminhos ───────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
_MODEL_DIR = _BASE / "config" / "modelos_rosto"
_FACE_DIR = _BASE / "memory" / "rostos"
_OWNER_FILE = _FACE_DIR / "dono.npy"
_CONFIG_FILE = _BASE / "config" / "api_keys.json"

# O GitHub guarda estes modelos via LFS; o endereço "media" entrega o arquivo de
# verdade, enquanto o "raw" às vezes entrega só um ponteiro de 130 bytes.
_MODELS = {
    "detector": ("face_detection_yunet_2023mar.onnx",
                 "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
                 "models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                 200_000),
    "reconhecedor": ("face_recognition_sface_2021dec.onnx",
                     "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
                     "models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
                     30_000_000),
}

# Limiar de similaridade de cosseno do SFace. 0.363 é o valor publicado pelos
# autores para "mesma pessoa"; rigoroso reduz falsos positivos, flexível ajuda
# com câmera ruim ou pouca luz.
_THRESHOLDS = {"normal": 0.40, "rigoroso": 0.48, "flexível": 0.363, "flexivel": 0.363}

_SAMPLES_WANTED = 15          # assinaturas guardadas no cadastro
_ABSENT_AFTER = 180.0         # segundos sem te ver para contar como "saiu"
_STARTUP_QUIET = 60.0         # não cumprimenta no primeiro minuto (há o briefing)
_STRANGER_COOLDOWN = 600.0    # um aviso de desconhecido a cada 10 minutos

_lock = threading.RLock()     # câmera e modelos são usados por uma coisa por vez
_models = {}                  # cache: detector / reconhecedor
_watch_thread: threading.Thread | None = None
_watch_stop = threading.Event()


# ── utilitários ────────────────────────────────────────────────────────────────
def _settings() -> dict:
    try:
        from memory.config_manager import get_plugin_config
        return get_plugin_config("reconhecimento_facial")
    except Exception:
        return {}


def _owner_name() -> str:
    try:
        cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return (cfg.get("user_name") or "").strip()
    except Exception:
        return ""


def _threshold() -> float:
    return _THRESHOLDS.get(str(_settings().get("rigor", "normal")).lower(), 0.40)


def _log(player, msg: str) -> None:
    print(f"[Rosto] {msg}")
    if player is not None:
        try:
            player.write_log(f"SYS: {msg}")
        except Exception:
            pass


def _say(player, instruction: str) -> None:
    """Pede ao JARVIS para falar algo agora, com as palavras dele."""
    fn = getattr(player, "request_say", None) if player is not None else None
    if callable(fn):
        try:
            fn(instruction)
        except Exception as e:
            print(f"[Rosto] não consegui falar: {e}")


def _ensure_models(player=None):
    """Baixa (uma vez) e carrega os dois modelos. Levanta RuntimeError se falhar."""
    import cv2

    if "detector" in _models and "reconhecedor" in _models:
        return _models["detector"], _models["reconhecedor"]

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for key, (fname, url, min_size) in _MODELS.items():
        path = _MODEL_DIR / fname
        if path.exists() and path.stat().st_size >= min_size:
            continue
        _log(player, f"Baixando o modelo de rosto ({fname}) — só desta vez…")
        tmp = path.with_suffix(".baixando")
        try:
            urllib.request.urlretrieve(url, tmp)
            if tmp.stat().st_size < min_size:
                raise RuntimeError("o arquivo baixado veio incompleto")
            tmp.replace(path)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"não consegui baixar o modelo {fname}: {e}")

    det = cv2.FaceDetectorYN.create(
        str(_MODEL_DIR / _MODELS["detector"][0]), "", (320, 320), 0.85, 0.3, 5000)
    rec = cv2.FaceRecognizerSF.create(str(_MODEL_DIR / _MODELS["reconhecedor"][0]), "")
    _models["detector"], _models["reconhecedor"] = det, rec
    return det, rec


def _open_camera():
    """Abre a mesma câmera que o resto do JARVIS usa."""
    import cv2
    index, backend = 0, cv2.CAP_ANY
    try:
        from actions.screen_processor import _cv2_backend, _get_camera_index
        index, backend = _get_camera_index(), _cv2_backend()
    except Exception:
        pass
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        return None
    for _ in range(4):          # as primeiras imagens costumam vir escuras
        cap.read()
    return cap


def _faces(det, frame):
    h, w = frame.shape[:2]
    det.setInputSize((w, h))
    _n, found = det.detect(frame)
    return [] if found is None else list(found)


def _signature(rec, frame, face):
    import numpy as np
    aligned = rec.alignCrop(frame, face)
    feat = rec.feature(aligned).flatten().astype("float32")
    norm = float(np.linalg.norm(feat)) or 1.0
    return feat / norm


def _load_owner():
    import numpy as np
    if not _OWNER_FILE.exists():
        return None
    try:
        data = np.load(_OWNER_FILE)
        return data if data.ndim == 2 and len(data) else None
    except Exception:
        return None


def _score(owner, sig) -> float:
    """Maior similaridade entre a assinatura e as guardadas no cadastro."""
    return float((owner @ sig).max())


def _look(player=None, frames: int = 3):
    """Uma olhada: devolve (viu_dono, desconhecidos, maior_score) ou None."""
    det, rec = _ensure_models(player)
    owner = _load_owner()
    with _lock:
        cap = _open_camera()
        if cap is None:
            return None
        try:
            best, strangers, saw_owner = 0.0, 0, False
            limit = _threshold()
            for _ in range(frames):
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                frame_strangers = 0
                for face in _faces(det, frame):
                    if owner is None:
                        frame_strangers += 1
                        continue
                    s = _score(owner, _signature(rec, frame, face))
                    best = max(best, s)
                    if s >= limit:
                        saw_owner = True
                    else:
                        frame_strangers += 1
                strangers = max(strangers, frame_strangers)
            return saw_owner, strangers, best
        finally:
            cap.release()


# ── ações ──────────────────────────────────────────────────────────────────────
def _cadastrar(player) -> str:
    import numpy as np

    det, rec = _ensure_models(player)
    _log(player, "Olhe para a câmera e mexa a cabeça devagar para os lados…")
    sigs, sem_rosto, varios = [], 0, 0
    with _lock:
        cap = _open_camera()
        if cap is None:
            return "Não consegui abrir a câmera. Ela está ligada e livre?"
        try:
            deadline = time.monotonic() + 12.0
            while len(sigs) < _SAMPLES_WANTED and time.monotonic() < deadline:
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                found = _faces(det, frame)
                if not found:
                    sem_rosto += 1
                    continue
                if len(found) > 1:
                    varios += 1
                    continue
                if float(found[0][-1]) < 0.9:     # rosto pouco nítido
                    continue
                sigs.append(_signature(rec, frame, found[0]))
                time.sleep(0.25)                  # variedade entre as amostras
        finally:
            cap.release()

    if len(sigs) < 6:
        if varios > sem_rosto:
            return ("Vi mais de uma pessoa na câmera. Fique sozinho na frente "
                    "dela e peça para cadastrar de novo.")
        return ("Não consegui ver seu rosto direito. Tente com mais luz, "
                "olhando para a câmera, e peça de novo.")

    _FACE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(_OWNER_FILE, np.stack(sigs))
    nome = _owner_name()
    _log(player, f"Rosto cadastrado ({len(sigs)} amostras).")
    return (f"Pronto{', ' + nome if nome else ''}. Guardei seu rosto com "
            f"{len(sigs)} amostras. Só a assinatura numérica fica salva, "
            "nenhuma foto, e só neste computador.")


def _identificar(player) -> str:
    if _load_owner() is None:
        return ("Ainda não conheço seu rosto. Peça para eu cadastrar seu rosto "
                "primeiro.")
    res = _look(player, frames=5)
    if res is None:
        return "Não consegui abrir a câmera."
    saw_owner, strangers, best = res
    nome = _owner_name() or "o dono"
    if saw_owner and not strangers:
        return f"Reconheço você: é {nome} (confiança {best:.0%})."
    if saw_owner and strangers:
        extra = "outra pessoa" if strangers == 1 else f"outras {strangers} pessoas"
        return f"Vejo {nome} e mais {extra} que eu não conheço."
    if strangers:
        quem = "uma pessoa" if strangers == 1 else f"{strangers} pessoas"
        return f"Vejo {quem}, mas não reconheço como {nome}."
    return "Não vejo ninguém na frente da câmera agora."


def _esquecer(player) -> str:
    stop_watching()
    existed = _OWNER_FILE.exists()
    _OWNER_FILE.unlink(missing_ok=True)
    _log(player, "Cadastro de rosto apagado.")
    return ("Apaguei o cadastro do seu rosto." if existed
            else "Não havia nenhum rosto cadastrado.")


def _status() -> str:
    tem = _load_owner() is not None
    vig = bool(_watch_thread and _watch_thread.is_alive())
    return (f"Rosto cadastrado: {'sim' if tem else 'não'}. "
            f"Vigia da câmera: {'ligada' if vig else 'desligada'}. "
            f"Rigor: {_settings().get('rigor', 'normal')}.")


# ── vigia em segundo plano ─────────────────────────────────────────────────────
def _watch_loop(player) -> None:
    started = time.monotonic()
    last_owner = 0.0
    owner_present = False
    stranger_streak = 0
    last_stranger_alert = 0.0
    fails = 0
    locked_for_absence = False

    try:
        interval = max(3.0, float(_settings().get("intervalo", 8) or 8))
    except (TypeError, ValueError):
        interval = 8.0

    _log(player, "Vigia da câmera ligada.")
    while not _watch_stop.wait(interval):
        try:
            res = _look(player, frames=2)
        except Exception as e:
            print(f"[Rosto] erro na vigia: {e}")
            res = None
        if res is None:
            fails += 1
            if fails == 5:
                _log(player, "A vigia não consegue abrir a câmera (talvez outro "
                             "programa esteja usando). Vou continuar tentando.")
            continue
        fails = 0
        saw_owner, strangers, _best = res
        now = time.monotonic()

        # Fork PT-BR 1.2: bloquear o PC depois de X minutos sem ver o dono
        # (como o "bloqueio dinâmico" do Windows, mas pela câmera).
        try:
            lock_min = float(str(_settings().get("bloquear_ausencia_min", 0) or 0).replace(",", "."))
        except ValueError:
            lock_min = 0.0
        if saw_owner:
            locked_for_absence = False
        elif (lock_min > 0 and last_owner > 0 and not locked_for_absence
              and now - last_owner >= lock_min * 60):
            locked_for_absence = True
            try:
                from plugins.controle_pc import bloquear_tela
                _log(player, f"Você saiu há {int(lock_min)} min: {bloquear_tela()}")
                from plugins import _monitor_db
                _monitor_db.gravar_evento("seguranca", "PC bloqueado por ausência (câmera).")
            except Exception as e:
                print(f"[Rosto] não consegui bloquear: {e}")

        if saw_owner:
            if not owner_present:
                owner_present = True
                if now - started > _STARTUP_QUIET:
                    # Fork PT-BR 1.4: depois de muito tempo fora, o relatório de
                    # "quando voltar" (downloads, internet, rede…) substitui a
                    # saudação simples. Ele mesmo decide se a ausência foi longa.
                    relatou = False
                    if last_owner > 0:
                        try:
                            from plugins import quando_voltar
                            relatou = quando_voltar.ao_voltar(player, now - last_owner, "câmera")
                        except Exception as e:
                            print(f"[Rosto] quando_voltar: {e}")
                    if not relatou:
                        nome = _owner_name()
                        _say(player,
                             "[RECONHECIMENTO FACIAL] A câmera acabou de reconhecer o "
                             f"dono{(' (' + nome + ')') if nome else ''} sentando de volta "
                             "em frente ao computador. Dê boas-vindas em UMA frase curta, "
                             "no estilo do J.A.R.V.I.S, no idioma em que vocês conversam. "
                             "Não chame nenhuma ferramenta.")
                    _log(player, "Dono reconhecido na câmera.")
            last_owner = now
            stranger_streak = 0
            # Fork PT-BR 1.5: ver você renova a sessão confiável da verificação.
            try:
                from core import verificacao
                verificacao.confiar("rosto")
            except Exception:
                pass
            continue

        if owner_present and now - last_owner > _ABSENT_AFTER:
            owner_present = False

        if strangers:
            stranger_streak += 1
            if (stranger_streak >= 2
                    and now - last_stranger_alert > _STRANGER_COOLDOWN):
                last_stranger_alert = now
                quem = "uma pessoa" if strangers == 1 else f"{strangers} pessoas"
                _log(player, f"Pessoa desconhecida na câmera ({quem}).")
                # Fork PT-BR 1.5: desconhecido sem você → a sessão confiável fecha.
                try:
                    from core import verificacao
                    verificacao.suspeitar(f"{quem} desconhecida(s) na câmera")
                except Exception:
                    pass
                # Fork PT-BR 1.2: com a guarda de segurança ligada, ela decide
                # (oferecer bloqueio, bloquear sozinho ou só avisar).
                cuidou = False
                guarda = sys.modules.get("plugins.guarda_seguranca")
                if guarda is not None:
                    try:
                        cuidou = bool(guarda.desconhecido_na_camera(player, quem))
                    except Exception as e:
                        print(f"[Rosto] guarda: {e}")
                if not cuidou:
                    _say(player,
                         f"[RECONHECIMENTO FACIAL] A câmera vê {quem} que NÃO é o dono "
                         "na frente do computador, e o dono não está junto. Avise isso "
                         "em UMA frase curta e educada. Não chame nenhuma ferramenta.")
        else:
            stranger_streak = 0

    _log(player, "Vigia da câmera desligada.")


def start_watching(player) -> str:
    global _watch_thread
    if _load_owner() is None:
        return "Antes de vigiar, preciso conhecer seu rosto. Peça para cadastrar."
    if _watch_thread and _watch_thread.is_alive():
        return "A vigia da câmera já está ligada."
    _ensure_models(player)
    _watch_stop.clear()
    _watch_thread = threading.Thread(target=_watch_loop, args=(player,),
                                     daemon=True, name="vigia-rosto")
    _watch_thread.start()
    return ("Vigia ligada. Vou te cumprimentar quando você voltar e avisar se "
            "aparecer outra pessoa. A luz da câmera vai piscar de vez em quando.")


def stop_watching() -> str:
    if not (_watch_thread and _watch_thread.is_alive()):
        return "A vigia da câmera já estava desligada."
    _watch_stop.set()
    return "Vigia da câmera desligada."


def on_session_start(player) -> None:
    """Chamado pelo main.py sempre que a sessão conecta. Idempotente."""
    if not _settings().get("vigia_automatica"):
        return
    if _watch_thread and _watch_thread.is_alive():
        return
    try:
        print(f"[Rosto] {start_watching(player)}")
    except Exception as e:
        print(f"[Rosto] vigia automática não iniciou: {e}")


# ── ponto de entrada do plugin ─────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str((parameters or {}).get("action", "")).strip().lower()
    try:
        import cv2  # noqa: F401
    except ImportError:
        return ("O OpenCV não está instalado. Rode: pip install opencv-python")
    try:
        if action in ("cadastrar", "cadastro", "aprender", "registrar"):
            return _cadastrar(player)
        if action in ("identificar", "quem", "reconhecer"):
            return _identificar(player)
        if action in ("vigiar_ligar", "vigiar", "ligar"):
            return start_watching(player)
        if action in ("vigiar_desligar", "desligar", "parar"):
            return stop_watching()
        if action in ("esquecer", "apagar"):
            return _esquecer(player)
        if action == "status":
            return _status()
        return ("Ação desconhecida. Use cadastrar, identificar, vigiar_ligar, "
                "vigiar_desligar, esquecer ou status.")
    except RuntimeError as e:
        return f"Reconhecimento facial indisponível: {e}"
    except Exception as e:
        return f"O reconhecimento facial falhou: {e}"
