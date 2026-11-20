"""
Modo intérprete presencial (fork PT-BR 2.5).

    "Jarvis, modo intérprete em inglês"     (ou espanhol, francês, italiano…)
    "Jarvis, desliga o intérprete"

Você fala português e o JARVIS fala a tradução em inglês/espanhol na CAIXA DE
SOM, para a outra pessoa ouvir. A resposta dela volta traduzida para o
português no seu FONE. Precisa de duas saídas de áudio: o fone (Bluetooth ou
com fio) e a caixa do PC — escolha em ⚙ → Intérprete (um pedaço do nome que
aparece em "Jarvis, quais saídas de áudio eu tenho?").

Por dentro: uma sessão própria do Gemini Live só para traduzir (a do JARVIS
fica com o microfone pausado enquanto isso). O destino de cada fala é decidido
pelo idioma da TRADUÇÃO: português vai para o seu fone; o outro idioma vai para
a caixa. Enquanto a caixa fala, o microfone não manda nada (senão ele
traduziria a própria voz de volta).
"""

from __future__ import annotations

import asyncio
import collections
import queue
import re
import threading
import time
import unicodedata

from plugins._comum import cfg, mostrar, registrar

PLUGIN = {
    "name": "interprete",
    "brief": "Live interpreter: owner speaks Portuguese, guest hears English/Spanish on the speaker; replies come "
             "back in Portuguese in the owner's earphone.",
    "description": (
        "In-person interpreter mode. action='ligar' with idioma (ingles, espanhol, frances, italiano, alemao…) starts "
        "a dedicated translation session: Portuguese → guest language on the speaker, guest language → Portuguese in "
        "the earphone. 'desligar' stops it. 'saidas' lists the audio outputs (to configure earphone and speaker). "
        "'status' shows the last translations."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ligar | desligar | saidas | status"},
            "idioma": {"type": "STRING"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "interprete",
    "title": "Intérprete presencial",
    "fields": [
        {"key": "idioma", "label": "Idioma da outra pessoa", "type": "choice",
         "options": ["inglês", "espanhol", "francês", "italiano", "alemão", "japonês", "chinês"], "default": "inglês"},
        {"key": "fone", "label": "Saída do SEU fone (parte do nome; vazio = a saída padrão do Windows)", "type": "text",
         "default": ""},
        {"key": "caixa", "label": "Saída da CAIXA DE SOM para a outra pessoa (parte do nome)", "type": "text",
         "default": ""},
    ],
}

IDIOMAS = {"ingles": "inglês", "english": "inglês", "espanhol": "espanhol", "spanish": "espanhol",
           "frances": "francês", "italiano": "italiano", "alemao": "alemão", "japones": "japonês", "chines": "chinês",
           "mandarim": "chinês"}
TAXA_MIC, TAXA_VOZ = 16000, 24000
PALAVRAS = {
    "pt": set("não você vocês é tá isso obrigado obrigada muito uma um eu meu minha também então aqui onde quando "
              "porque sim olá oi tudo bem bom boa dia noite ser ter fazer quero preciso posso pode com pra para do da "
              "dos das no na nos nas ao à seu sua nós ele ela eles elas vou vai quanto custa legal certo agora já mais "
              "isso esse essa este esta aquele lá cadê ainda nada coisa gente".split()),
    "es": set("usted ustedes es el los las del muy gracias también entonces aquí dónde cuándo sí hola todo bien "
              "bueno buenas día noche quiero necesito puedo puede y pero yo mi qué cómo estoy eres soy hay "
              "vale claro ahora ya más ese esa este esta allí nada cosa gente cuánto cuesta señor".split()),
    "en": set("the is are you i to and of it that what how can do please thank thanks yes where when this my your "
              "we have want need hello hi good morning night sir much how's it's i'm don't okay right now".split()),
}
_estado = {"sessao": None}


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


# ── puro ──────────────────────────────────────────────────────────────────────
def idioma_do_texto(texto: str) -> tuple[str, int]:
    """('pt' | 'es' | 'en' | '', folga) — folga = pontos de vantagem sobre o 2º."""
    t = str(texto or "").lower()
    if not t.strip():
        return "", 0
    pal = re.findall(r"[a-záéíóúâêôãõçñü']+", t)
    pontos = {k: sum(1 for w in pal if w in v) for k, v in PALAVRAS.items()}
    pontos["pt"] += 2 * len(re.findall(r"[ãõç]", t))
    pontos["es"] += 2 * len(re.findall(r"[ñ¿¡]", t))
    ordem = sorted(pontos.items(), key=lambda kv: -kv[1])
    if ordem[0][1] == 0:
        return "", 0
    return ordem[0][0], ordem[0][1] - ordem[1][1]


def decidir_rota(entrada: str, saida: str, forcar: bool = False) -> str | None:
    """'fone' (português para o dono) | 'caixa' (o outro idioma para o convidado) | None (ainda não dá)."""
    lang_s, folga_s = idioma_do_texto(saida)
    if lang_s and (folga_s >= 2 or (forcar and folga_s >= 1)):
        return "fone" if lang_s == "pt" else "caixa"
    lang_e, folga_e = idioma_do_texto(entrada)
    if lang_e and (folga_e >= 2 or forcar):
        return "caixa" if lang_e == "pt" else "fone"
    if forcar:
        return "fone" if lang_s in ("pt", "") else "caixa"
    return None


def prompt(idioma: str) -> str:
    return (f"Você é um intérprete simultâneo profissional. Duas pessoas conversam ao vivo: o DONO, que fala português "
            f"do Brasil, e um CONVIDADO, que fala {idioma}.\n"
            f"- Quando ouvir português: diga SÓ a tradução em {idioma}, natural, em primeira pessoa (como se fosse o "
            f"próprio dono falando).\n"
            f"- Quando ouvir {idioma}: diga SÓ a tradução em português do Brasil, em primeira pessoa.\n"
            "- Nunca responda às perguntas, nunca comente, nunca explique, não cumprimente, não diga 'ele disse'. "
            "Só a tradução, curta e fiel.\n"
            "- Mantenha exatos nomes próprios, números, preços e medidas.\n"
            "- Se não entender, diga só 'pode repetir?' no idioma de quem falou.")


def achar_saida(dispositivos: list[dict], termo: str, hostapi_preferida: int | None = None) -> int | None:
    """Índice da saída de áudio cujo nome contém `termo` (preferindo a mesma API do padrão) — puro."""
    t = _dobrar(termo).strip()
    if not t:
        return None
    achados = [i for i, d in enumerate(dispositivos)
               if d.get("max_output_channels", 0) > 0 and t in _dobrar(d.get("name", ""))]
    if not achados:
        return None
    mesmos = [i for i in achados if dispositivos[i].get("hostapi") == hostapi_preferida]
    return (mesmos or achados)[0]


# ── a sessão de tradução ──────────────────────────────────────────────────────
class Sessao:
    def __init__(self, idioma: str, fone: int | None, caixa: int):
        self.idioma, self.fone, self.caixa = idioma, fone, caixa
        self.parar = threading.Event()
        self.caixa_ate = 0.0
        self.filas = {"fone": queue.Queue(maxsize=400), "caixa": queue.Queue(maxsize=400)}
        self.historico: collections.deque = collections.deque(maxlen=30)
        self.erro = ""
        self.conectado = False

    def iniciar(self) -> None:
        threading.Thread(target=lambda: asyncio.run(self._rodar()), daemon=True, name="interprete").start()
        for nome in ("fone", "caixa"):
            threading.Thread(target=self._tocar, args=(nome,), daemon=True, name=f"interprete_{nome}").start()

    def _tocar(self, nome: str) -> None:
        import numpy as np
        import sounddevice as sd
        aparelho = self.fone if nome == "fone" else self.caixa
        try:
            with sd.OutputStream(samplerate=TAXA_VOZ, channels=1, dtype="int16", device=aparelho) as saida:
                while not self.parar.is_set():
                    try:
                        pcm = self.filas[nome].get(timeout=0.3)
                    except queue.Empty:
                        continue
                    if nome == "caixa":                        # o microfone fica fechado enquanto a caixa fala
                        self.caixa_ate = time.time() + len(pcm) / 2 / TAXA_VOZ + 0.7
                    saida.write(np.frombuffer(pcm, dtype=np.int16))
        except Exception as e:
            self.erro = f"saída '{nome}': {e}"
            print(f"[Intérprete] {self.erro}")

    async def _rodar(self) -> None:
        from google import genai
        from google.genai import types

        from core import gemini
        try:
            from memory.config_manager import get_voice
            voz = get_voice()
        except Exception:
            voz = None
        while not self.parar.is_set():
            try:
                cliente = genai.Client(api_key=gemini.api_key(), http_options={"api_version": "v1beta"})
                extra = {"speech_config": types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voz)))} if voz else {}
                config = types.LiveConnectConfig(
                    response_modalities=["AUDIO"], input_audio_transcription={}, output_audio_transcription={},
                    system_instruction=prompt(self.idioma),
                    context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
                    **extra)
                async with cliente.aio.live.connect(model=gemini.live_model(), config=config) as s:
                    self.conectado, self.erro = True, ""
                    tarefas = [asyncio.create_task(self._microfone(s, types)), asyncio.create_task(self._receber(s))]
                    _feitas, pendentes = await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
                    for t in pendentes:
                        t.cancel()
                    for t in tarefas:
                        if t.done() and not t.cancelled() and t.exception():
                            raise t.exception()
            except Exception as e:
                self.conectado = False
                self.erro = str(e)[:200]
                print(f"[Intérprete] {e}")
                await asyncio.sleep(3)

    async def _microfone(self, s, types) -> None:
        import sounddevice as sd
        loop = asyncio.get_running_loop()
        fila: asyncio.Queue = asyncio.Queue(maxsize=100)

        def cb(indata, frames, _t, _status):
            try:
                loop.call_soon_threadsafe(fila.put_nowait, bytes(indata))
            except Exception:
                pass
        with sd.RawInputStream(samplerate=TAXA_MIC, channels=1, dtype="int16", blocksize=1024, callback=cb):
            while not self.parar.is_set():
                try:
                    bloco = await asyncio.wait_for(fila.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if time.time() < self.caixa_ate:
                    continue
                await s.send_realtime_input(audio=types.Blob(data=bloco, mime_type=f"audio/pcm;rate={TAXA_MIC}"))

    async def _receber(self, s) -> None:
        while not self.parar.is_set():
            entrada, saida, pendente, rota, inicio = [], [], [], None, 0.0
            async for r in s.receive():
                if self.parar.is_set():
                    return
                sc = getattr(r, "server_content", None)
                if sc is not None:
                    if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                        entrada.append(sc.input_transcription.text)
                    if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                        saida.append(sc.output_transcription.text)
                    if getattr(sc, "interrupted", False):
                        pendente.clear()
                if getattr(r, "data", None):
                    if rota is None:
                        pendente.append(r.data)
                        inicio = inicio or time.time()
                    else:
                        self._mandar(rota, r.data)
                if rota is None and pendente:
                    rota = decidir_rota("".join(entrada), "".join(saida), forcar=time.time() - inicio > 1.2)
                    if rota:
                        for pcm in pendente:
                            self._mandar(rota, pcm)
                        pendente.clear()
                if sc is not None and getattr(sc, "turn_complete", False):
                    if pendente:
                        rota = rota or decidir_rota("".join(entrada), "".join(saida), forcar=True)
                        for pcm in pendente:
                            self._mandar(rota, pcm)
                    if saida:
                        de = "pt" if rota == "caixa" else self.idioma
                        self.historico.append((time.time(), de, "".join(entrada).strip(), "".join(saida).strip()))
                        registrar(None, f"Intérprete ({'você → ' + self.idioma if rota == 'caixa' else 'convidado → você'}): "
                                        f"{' '.join(saida).strip()}")
                    break

    def _mandar(self, rota: str, pcm: bytes) -> None:
        try:
            self.filas[rota].put_nowait(pcm)
        except queue.Full:
            pass


# ── ligar / desligar ──────────────────────────────────────────────────────────
def _saidas() -> tuple[list[dict], int | None, int | None]:
    import sounddevice as sd
    dispositivos = [dict(d) for d in sd.query_devices()]
    padrao = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) else None
    host = dispositivos[padrao]["hostapi"] if padrao is not None and padrao >= 0 else None
    return dispositivos, (padrao if padrao is not None and padrao >= 0 else None), host


def ligar(idioma: str = "") -> str:
    if _estado["sessao"] is not None:
        return f"O intérprete já está ligado ({_estado['sessao'].idioma})."
    c = cfg("interprete", PLUGIN_SETTINGS)
    idioma = IDIOMAS.get(_dobrar(idioma).strip(), idioma.strip()) or str(c.get("idioma") or "inglês")
    try:
        from plugins import _ia
        if not _ia.disponivel():
            return "O intérprete usa o Gemini Live: preciso da chave do Gemini configurada."
        dispositivos, padrao, host = _saidas()
    except Exception as e:
        return f"Não consegui ver as saídas de áudio: {e}"
    fone = achar_saida(dispositivos, str(c.get("fone") or ""), host) if c.get("fone") else padrao
    caixa = achar_saida(dispositivos, str(c.get("caixa") or ""), host)
    if caixa is None:
        return ("Falta escolher a CAIXA DE SOM em ⚙ → Intérprete (um pedaço do nome da saída). Saídas: "
                + listar_saidas(dispositivos) + ".")
    if fone == caixa:
        return "O fone e a caixa são a mesma saída. Conecte o fone (Bluetooth ou com fio) e escolha as duas em ⚙ → Intérprete."
    from core import microfone
    microfone.reservar("intérprete", 900)
    sessao = Sessao(idioma, fone, caixa)
    _estado["sessao"] = sessao
    sessao.iniciar()
    threading.Thread(target=_manter_reserva, args=(sessao,), daemon=True).start()
    nome_fone = dispositivos[fone]["name"] if fone is not None else "saída padrão"
    return (f"Intérprete ligado: você fala português e a tradução em {idioma} sai na caixa ({dispositivos[caixa]['name']}); "
            f"o que a outra pessoa disser chega em português no seu fone ({nome_fone}). Enquanto isso eu fico calado. "
            "Para parar: 'Jarvis, desliga o intérprete' (no teclado, se precisar).")


def _manter_reserva(sessao: Sessao) -> None:
    from core import microfone
    while _estado["sessao"] is sessao and not sessao.parar.is_set():
        microfone.reservar("intérprete", 900)
        time.sleep(300)


def desligar() -> str:
    sessao = _estado["sessao"]
    if sessao is None:
        return "O intérprete não está ligado."
    sessao.parar.set()
    _estado["sessao"] = None
    from core import microfone
    microfone.liberar()
    return f"Intérprete desligado ({len(sessao.historico)} falas traduzidas). Voltei a ouvir você."


def listar_saidas(dispositivos: list[dict] | None = None) -> str:
    if dispositivos is None:
        dispositivos, _p, _h = _saidas()
    vistos, nomes = set(), []
    for d in dispositivos:
        if d.get("max_output_channels", 0) > 0 and d["name"] not in vistos:
            vistos.add(d["name"])
            nomes.append(d["name"])
    return "; ".join(nomes[:12]) or "nenhuma"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "status").lower()
    try:
        if acao == "ligar":
            return ligar(str(p.get("idioma") or ""))
        if acao == "desligar":
            return desligar()
        if acao == "saidas":
            texto = listar_saidas()
            mostrar(player, "SAÍDAS DE ÁUDIO", texto.replace("; ", "\n"))
            return f"Saídas de áudio: {texto}. Coloque um pedaço do nome do fone e da caixa em ⚙ → Intérprete."
        s = _estado["sessao"]
        if s is None:
            return "Intérprete desligado. Diga 'modo intérprete em inglês' (ou espanhol) para ligar."
        ultimas = "\n".join(f"• {txt}" for _ts, _de, _ent, txt in list(s.historico)[-5:])
        estado = "conectado" if s.conectado else f"conectando… {s.erro}"
        return f"Intérprete em {s.idioma}: {estado}." + (f"\nÚltimas traduções:\n{ultimas}" if ultimas else "")
    except Exception as e:
        return f"O intérprete falhou: {e}"
