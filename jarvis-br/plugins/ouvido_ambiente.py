"""
Ouvido ambiente (fork PT-BR 1.5).

Escuta o ambiente pelo MESMO microfone do JARVIS (uma cópia, processada aqui
no PC — nada é gravado nem enviado) e avisa por voz e no celular quando ouve:

    • ALARME / BIPE   — detector próprio de bipes agudos repetidos (fumaça,
                        gás, despertador, timer);
    • SONS QUE VOCÊ ENSINA — "Jarvis, aprende o som da campainha" e toque a
                        campainha: ele guarda a "assinatura" do som e reconhece
                        quando ouvir de novo (interfone, campainha, o bipe da
                        máquina de lavar…);
    • BARULHO FORTE   — estouro/vidro/batida, só quando você está fora (com
                        você no PC, o teclado daria alarme falso);
    • com o modelo YAMNet (opcional): campainha, alarme de fumaça, vidro
      quebrando, bebê chorando, cachorro, sirene, batida na porta. Instale o
      ai-edge-litert e diga "Jarvis, baixa o modelo de sons" (ou coloque o
      yamnet.tflite em config/modelos_som/ — veja o INSTALAR.txt).

    "Jarvis, liga o ouvido ambiente"      "Jarvis, aprende o som do interfone"
    "Jarvis, que sons você conhece?"      "Jarvis, esquece o som do interfone"

Respeita o mudo: com o microfone mutado (F4), ele também não escuta.
"""

from __future__ import annotations

import re
import threading
import time
import zipfile

from plugins._comum import CONFIG, MEMORIA, cfg, gravar_json, ler_json, salvar_cfg

PLUGIN = {
    "name": "ouvido_ambiente",
    "brief": "Recognises home sounds (alarm beeps, taught sounds like the doorbell, loud bangs) and alerts.",
    "description": (
        "Ambient hearing: local detection of alarm beeps, sounds the user teaches (doorbell, intercom...), loud "
        "bangs while the owner is away, and YAMNet classes if the optional model is installed; alerts by voice and "
        "phone. action='ligar' | 'desligar' | 'aprender' with nome (then the user plays the sound) | 'listar' | "
        "'esquecer' with nome | 'baixar_yamnet' (downloads the optional YAMNet model) | 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "ligar | desligar | aprender | listar | esquecer | baixar_yamnet | status"},
            "nome": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "ouvido_ambiente",
    "title": "Ouvido ambiente",
    "fields": [
        {"key": "ligado", "label": "Escutar o ambiente", "type": "toggle", "default": False},
        {"key": "alarmes", "label": "Avisar de alarmes/bipes", "type": "toggle", "default": True},
        {"key": "barulho", "label": "Avisar de barulho forte (só com você fora)", "type": "toggle", "default": True},
        {"key": "mudo", "label": "Escutar mesmo com o microfone mutado", "type": "toggle", "default": False},
    ],
}

TAXA, JANELA, PASSO, NFFT, N_MEL = 16000, 400, 160, 512, 64
ARQ_SONS = MEMORIA / "sons_aprendidos.json"
PASTA_MODELO = CONFIG / "modelos_som"
_estado = {"ligado": False, "aprendendo": None, "ultimo": {}, "eventos": 0}
_iniciado = threading.Event()
_cache: dict = {}


def _sim(v) -> bool:
    return str(v).strip().lower() not in ("false", "0", "nao", "não", "off")


# ── características (puras, numpy) ─────────────────────────────────────────────
def _filtros_mel():
    import numpy as np
    if "mel" not in _cache:
        def mel(f):
            return 1127.0 * np.log1p(f / 700.0)

        def inv(m):
            return 700.0 * (np.exp(m / 1127.0) - 1)
        pontos = inv(np.linspace(mel(125.0), mel(7500.0), N_MEL + 2))
        bins = np.fft.rfftfreq(NFFT, 1 / TAXA)
        F = np.zeros((N_MEL, len(bins)), dtype="float32")
        for i in range(N_MEL):
            esq, cen, dir_ = pontos[i:i + 3]
            F[i] = np.clip(np.minimum((bins - esq) / (cen - esq), (dir_ - bins) / (dir_ - cen)), 0, None)
        _cache["mel"] = F
        _cache["janela"] = np.hanning(JANELA).astype("float32")
    return _cache["mel"], _cache["janela"]


def espectro(x):
    """Magnitudes (T, 257) de quadros de 25 ms a cada 10 ms. x: float32 em [-1, 1]."""
    import numpy as np
    _F, jan = _filtros_mel()
    if len(x) < JANELA:
        return np.zeros((0, NFFT // 2 + 1), dtype="float32")
    quadros = np.lib.stride_tricks.sliding_window_view(x, JANELA)[::PASSO]
    return np.abs(np.fft.rfft(quadros * jan, NFFT)).astype("float32")


def log_mel(espec):
    import numpy as np
    F, _j = _filtros_mel()
    return np.log(espec @ F.T + 1e-3)


def bipes(espec, fmin: float = 2400, fmax: float = 4600) -> list[tuple[int, int, float]]:
    """Trechos tonais agudos: [(quadro_inicio, quadro_fim, freq_hz)] (pura)."""
    import numpy as np
    freqs = np.fft.rfftfreq(NFFT, 1 / TAXA)
    banda = (freqs >= fmin) & (freqs <= fmax)
    sub = espec[:, banda]
    if not len(sub):
        return []
    pico = sub.max(axis=1)
    med = np.median(sub, axis=1) + 1e-6
    total = espec.sum(axis=1) + 1e-6
    tonal = (pico / med > 12) & (pico * 4 > 0.25 * total) & (pico > 0.5)
    f_pico = freqs[banda][sub.argmax(axis=1)]
    saida, ini = [], None
    for i, t in enumerate(list(tonal) + [False]):
        if t and ini is None:
            ini = i
        elif not t and ini is not None:
            if i - ini >= 12:                                   # ≥ 120 ms
                saida.append((ini, i, float(np.median(f_pico[ini:i]))))
            ini = None
    return saida


def eh_alarme(lista_bipes: list[tuple[int, int, float]]) -> bool:
    """3 ou mais bipes de frequência parecida = alarme."""
    if len(lista_bipes) < 3:
        return False
    freqs = sorted(b[2] for b in lista_bipes)
    meio = freqs[len(freqs) // 2]
    return sum(1 for f in freqs if abs(f - meio) < 150) >= 3


def _formas(m, faixa: float = 4.6):
    """Cada quadro vira a FORMA do espectro (sem o volume): só os 20 dB de cima
    contam (o chão de ruído vira constante), depois média 0 e norma 1."""
    import numpy as np
    m = np.maximum(m, m.max(axis=1, keepdims=True) - faixa)
    f = m - m.mean(axis=1, keepdims=True)
    return f / (np.linalg.norm(f, axis=1, keepdims=True) + 1e-6)


def parecido(janela_mel, modelo_mel, passo: int = 2) -> float:
    """Semelhança do som aprendido em qualquer posição dos últimos segundos (pura).

    Compara a forma do espectro quadro a quadro (cosseno), alinhando o modelo
    em todas as posições da janela; o volume não importa, o timbre e a melodia sim."""
    import numpy as np
    T = len(modelo_mel)
    if T == 0 or len(janela_mel) < T:
        return 0.0
    S = _formas(janela_mel) @ _formas(modelo_mel).T          # (N, T)
    # quadros mais fortes do modelo pesam mais: a cauda de um "dong" que some no
    # ruído de outro cômodo não pode derrubar a nota
    forca = modelo_mel.max(axis=1)
    peso = np.clip((forca - forca.min()) / ((forca.max() - forca.min()) or 1.0), 0, 1) ** 2
    peso = peso / (peso.sum() or 1.0)
    idx = np.arange(T)
    melhor = 0.0
    for ini in range(0, len(janela_mel) - T + 1, passo):
        melhor = max(melhor, float(S[ini + idx, idx] @ peso))
    return melhor


def barulho_forte(espec, fundo_db: float) -> bool:
    """Estouro largo e agudo bem acima do fundo, durando ≥ 30 ms (pura)."""
    import numpy as np
    energia = 10 * np.log10(np.square(espec).sum(axis=1) + 1e-9)
    freqs = np.fft.rfftfreq(NFFT, 1 / TAXA)
    agudo = np.square(espec[:, freqs > 3000]).sum(axis=1) / (np.square(espec).sum(axis=1) + 1e-9)
    alto = (energia > fundo_db + 25) & (agudo > 0.35)
    seguidos = 0
    for a in alto:
        seguidos = seguidos + 1 if a else 0
        if seguidos >= 8:                    # ≥ 80 ms: um clique de teclado não passa de ~3 quadros
            return True
    return False


# ── YAMNet (opcional) ──────────────────────────────────────────────────────────
_ALVOS_YAMNET = [(r"doorbell|ding-dong", "a campainha"), (r"smoke detector|smoke alarm|fire alarm", "um alarme de incêndio"),
                 (r"glass|shatter", "vidro quebrando"), (r"baby cry|infant cry", "bebê chorando"),
                 (r"^dog$|bark", "cachorro latindo"), (r"siren", "uma sirene"), (r"knock", "batida na porta"),
                 (r"^alarm$|alarm clock", "um alarme")]


def ler_rotulos(texto: str, eh_csv: bool) -> list[str]:
    """Rótulos do YAMNet: .txt = um por linha; .csv = última coluna (com aspas e vírgulas) (pura)."""
    if not eh_csv:
        return [l.strip() for l in texto.splitlines() if l.strip()]
    import csv
    import io
    linhas = [l for l in csv.reader(io.StringIO(texto)) if l]
    if linhas and not linhas[0][0].strip().isdigit():          # cabeçalho index,mid,display_name
        linhas = linhas[1:]
    return [l[-1].strip() for l in linhas]


def _yamnet():
    if "yamnet" in _cache:
        return _cache["yamnet"]
    _cache["yamnet"] = None
    modelo = PASTA_MODELO / "yamnet.tflite"
    if not modelo.exists():
        return None
    Interp = None
    for mod in ("ai_edge_litert.interpreter", "tflite_runtime.interpreter", "tensorflow.lite"):
        try:
            Interp = __import__(mod, fromlist=["Interpreter"]).Interpreter
            break
        except Exception:
            continue
    if Interp is None:
        return None
    rotulos = []
    try:
        with zipfile.ZipFile(modelo) as z:                     # o .tflite com metadados é um zip
            nome = next(n for n in z.namelist() if n.endswith((".txt", ".csv")))
            rotulos = ler_rotulos(z.read(nome).decode("utf-8", "replace"), nome.endswith(".csv"))
    except Exception:
        csv_ = PASTA_MODELO / "yamnet_class_map.csv"
        if csv_.exists():
            rotulos = ler_rotulos(csv_.read_text(encoding="utf-8"), True)
    it = Interp(model_path=str(modelo))
    ent = it.get_input_details()[0]
    if len(ent["shape"]) == 1 and ent["shape"][0] <= 0:      # entrada de tamanho livre: fixa em 0,975 s
        it.resize_tensor_input(ent["index"], [15600])
    it.allocate_tensors()
    _cache["yamnet"] = (it, rotulos)
    return _cache["yamnet"]


# Endereços oficiais do Google (MediaPipe) para o YAMNet com os rótulos embutidos; o
# primeiro que responder com um .tflite válido é usado.
URLS_YAMNET = (
    "https://storage.googleapis.com/mediapipe-models/audio_classifier/yamnet/float32/latest/yamnet.tflite",
    "https://storage.googleapis.com/mediapipe-assets/yamnet_audio_classifier_with_metadata.tflite",
)


def eh_tflite(dados: bytes) -> bool:
    """Um modelo TFLite tem a marca 'TFL3' nos bytes 4–8 (pura)."""
    return len(dados) > 100_000 and dados[4:8] == b"TFL3"


def baixar_yamnet() -> str:
    import requests
    erros = []
    for url in URLS_YAMNET:
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and eh_tflite(r.content):
                PASTA_MODELO.mkdir(parents=True, exist_ok=True)
                (PASTA_MODELO / "yamnet.tflite").write_bytes(r.content)
                _cache.pop("yamnet", None)
                return f"baixado ({len(r.content) / 1e6:.1f} MB)"
            erros.append(f"{url.split('/')[3]}: HTTP {r.status_code}")
        except Exception as e:
            erros.append(f"{url.split('/')[3]}: {e}")
    return "não consegui baixar (" + "; ".join(erros) + ")"


def classificar_yamnet(x) -> list[tuple[str, float]]:
    import numpy as np
    y = _yamnet()
    if not y:
        return []
    it, rotulos = y
    ent = it.get_input_details()[0]
    forma = [int(v) for v in ent["shape"]]
    n = forma[-1] if forma[-1] > 0 else 15600
    trecho = np.zeros(n, dtype="float32")
    ultimo = x[-n:]
    trecho[:len(ultimo)] = ultimo
    it.set_tensor(ent["index"], trecho.reshape(forma) if len(forma) > 1 else trecho)
    it.invoke()
    notas = it.get_tensor(it.get_output_details()[0]["index"]).reshape(-1, len(rotulos) or 521).mean(axis=0)
    achados = []
    for i in np.argsort(-notas)[:5]:
        rot = rotulos[i] if i < len(rotulos) else str(i)
        for rx, nome in _ALVOS_YAMNET:
            if re.search(rx, rot, re.I) and notas[i] >= 0.35:
                achados.append((nome, float(notas[i])))
                break
    return achados


# ── processamento contínuo ─────────────────────────────────────────────────────
class Ouvinte:
    """Recebe blocos do microfone e decide. Separado do I/O para poder testar."""

    def __init__(self):
        import collections
        self.audio = collections.deque(maxlen=int(4 * TAXA / 1024) + 2)
        self.fundo_db = -40.0
        self.ultimo_proc = 0.0
        self.sons = carregar_sons()

    def processar(self, agora: float, x, fora: bool, c: dict) -> list[str]:
        import numpy as np
        espec = espectro(x)
        if not len(espec):
            return []
        energia = 10 * np.log10(np.square(espec).sum(axis=1) + 1e-9)
        self.fundo_db = 0.95 * self.fundo_db + 0.05 * float(np.percentile(energia, 20))
        achados = []
        if _sim(c.get("alarmes", True)) and eh_alarme(bipes(espec)):
            achados.append("um alarme ou bipe insistente")
        if fora and _sim(c.get("barulho", True)) and barulho_forte(espec[-100:], self.fundo_db):
            achados.append("um barulho forte (vidro quebrando ou batida?)")
        if self.sons:
            mel = log_mel(espec)
            for nome, modelo in self.sons.items():
                if parecido(mel, modelo) >= 0.70:
                    achados.append(f"o som '{nome}'")
        for nome, _p in classificar_yamnet(x[-15600:]):
            achados.append(nome)
        return achados


def carregar_sons() -> dict:
    import numpy as np
    d = ler_json(ARQ_SONS, {}) or {}
    return {k: np.array(v, dtype="float32") for k, v in d.items()}


def aprender_de(x) -> list | None:
    """Recorta o som alto do trecho (≥ 12 dB acima do fundo) e devolve o modelo log-mel."""
    import numpy as np
    espec = espectro(x)
    if not len(espec):
        return None
    energia = 10 * np.log10(np.square(espec).sum(axis=1) + 1e-9)
    fundo = float(np.percentile(energia, 15))
    alto = np.where(energia > fundo + 12)[0]
    if len(alto) < 15:
        return None
    ini, fim = int(alto[0]), int(alto[-1]) + 1                # só a parte que soa (sem o silêncio em volta)
    fim = min(fim, ini + 300)                                  # no máximo 3 s
    return log_mel(espec[ini:fim]).round(3).tolist()


def _ao_audio(player):
    ouv = {"obj": None, "pendente": []}

    def receber(ts, bloco, mudo, jarvis_falando):
        import numpy as np
        if not _estado["ligado"] and not _estado["aprendendo"]:
            return
        c = cfg("ouvido_ambiente", PLUGIN_SETTINGS)
        if (mudo and not _sim(c.get("mudo", False))) or jarvis_falando:
            return
        if ouv["obj"] is None:
            ouv["obj"] = Ouvinte()
        o = ouv["obj"]
        o.audio.append(bloco)
        if _estado["aprendendo"]:
            nome, ate = _estado["aprendendo"]
            ouv["pendente"].append(bloco)
            if ts >= ate:
                x = np.concatenate(ouv["pendente"]).astype("float32") / 32768.0
                ouv["pendente"] = []
                _estado["aprendendo"] = None
                modelo = aprender_de(x)
                from plugins._notificar import notificar
                if modelo:
                    d = ler_json(ARQ_SONS, {}) or {}
                    d[nome] = modelo
                    gravar_json(ARQ_SONS, d)
                    o.sons = carregar_sons()
                    notificar(player, f"Aprendi o som '{nome}'. Vou avisar quando ouvir de novo.",
                              titulo="Ouvido ambiente", etiqueta="SOM")
                else:
                    notificar(player, f"Não ouvi nenhum som claro para '{nome}'. Tente de novo mais perto.",
                              titulo="Ouvido ambiente", etiqueta="SOM")
            return
        if ts - o.ultimo_proc < 1.0:
            return
        o.ultimo_proc = ts
        x = np.concatenate(list(o.audio)).astype("float32") / 32768.0
        try:
            from core import verificacao
            fora = not verificacao.confiavel() or verificacao.windows_travado()
        except Exception:
            fora = False
        from plugins._notificar import notificar as avisar_celular
        for achado in set(o.processar(ts, x, fora, c)):
            if avisar_celular(player, f"Ouvi {achado}.", titulo="Ouvido ambiente", etiqueta="SOM",
                         chave=f"som:{achado}", intervalo_s=120, prioridade="high"):
                _estado["eventos"] += 1
                try:
                    from plugins import _monitor_db
                    _monitor_db.gravar_evento("aviso", f"Ouvido ambiente: {achado}")
                except Exception:
                    pass
    return receber


def _ligar(player) -> None:
    from core import escuta
    if "receptor" not in _cache:
        _cache["receptor"] = _ao_audio(player)
    escuta.inscrever(_cache["receptor"])


def on_session_start(player) -> None:
    if _iniciado.is_set():
        return
    _iniciado.set()
    if _sim(cfg("ouvido_ambiente", PLUGIN_SETTINGS).get("ligado", False)):
        _estado["ligado"] = True
        _ligar(player)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        import numpy  # noqa: F401
        if acao == "ligar":
            salvar_cfg("ouvido_ambiente", {"ligado": True})
            _estado["ligado"] = True
            _ligar(player)
            return ("Ouvido ambiente ligado: aviso de alarmes, dos sons que você me ensinar e de barulho forte quando "
                    "você estiver fora. Tudo processado aqui, nada é gravado.")
        if acao == "desligar":
            salvar_cfg("ouvido_ambiente", {"ligado": False})
            _estado["ligado"] = False
            return "Ouvido ambiente desligado."
        if acao == "aprender":
            nome = str(p.get("nome") or "").strip().lower() or "som"
            _estado["aprendendo"] = (nome, time.time() + 12)
            _ligar(player)
            return f"Pode tocar '{nome}' agora: estou ouvindo pelos próximos 12 segundos."
        if acao == "esquecer":
            d = ler_json(ARQ_SONS, {}) or {}
            nome = str(p.get("nome") or "").strip().lower()
            if d.pop(nome, None) is None:
                return f"Não conheço o som '{nome}'."
            gravar_json(ARQ_SONS, d)
            return f"Esqueci o som '{nome}'."
        if acao == "baixar_yamnet":
            r = baixar_yamnet()
            if not r.startswith("baixado"):
                return f"O modelo YAMNet {r}. Dá para baixar à mão: veja o INSTALAR.txt."
            if _yamnet():
                return f"YAMNet {r} e funcionando: agora também reconheço campainha, sirene, vidro e outros sons."
            return (f"YAMNet {r}, mas falta o leitor de modelos. No PowerShell: python -m pip install ai-edge-litert "
                    "e reinicie o JARVIS.")
        sons = list((ler_json(ARQ_SONS, {}) or {}).keys())
        if acao == "listar":
            extra = " Com o YAMNet instalado também reconheço campainha, sirene, vidro e outros." if _yamnet() else ""
            return ("Sons que eu conheço: alarme/bipe, barulho forte" + (", " + ", ".join(sons) if sons else "")
                    + "." + extra)
        return (f"Ouvido ambiente {'ligado' if _estado['ligado'] else 'desligado'}; {len(sons)} som(ns) aprendido(s); "
                f"{_estado['eventos']} aviso(s) desde que abri.")
    except ImportError:
        return "Preciso do numpy para ouvir o ambiente."
    except Exception as e:
        return f"O ouvido ambiente falhou: {e}"
