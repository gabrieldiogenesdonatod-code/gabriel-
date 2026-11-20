"""
Conversa em grupo (fork PT-BR 2.5): quem está falando?

    "Jarvis, aprende a minha voz, eu sou o Rafael"
    "Jarvis, aprende a voz da Maria"              (a Maria fala uns 8 segundos depois do bip)
    "Jarvis, modo conversa em grupo"              → separa quem fala e responde cada um pelo nome
    "Jarvis, quem falou agora?"   "Jarvis, desliga a conversa em grupo"

Com o modo ligado, a cada fala nova ele reconhece a voz (no próprio PC) e
deixa uma nota na conversa ("quem está falando agora: Maria"), então a
resposta vem para a pessoa certa: "Maria, a sua é com gelo; Rafael, a sua…".
Voz desconhecida: ele trata como visita e pode perguntar o nome.

Com o resemblyzer instalado (o mesmo da verificação de voz) fica bem mais
preciso; sem ele usa o timbre, que separa bem vozes diferentes. As impressões
de voz ficam em memory/vozes (números, não gravações).
"""

from __future__ import annotations

import queue
import threading
import time

from plugins import _vozes as V
from plugins._comum import mostrar, registrar

PLUGIN = {
    "name": "conversa_grupo",
    "brief": "Group conversation: recognizes who is speaking (voice prints) so JARVIS answers each person by name.",
    "description": (
        "Group conversation with several people in the room. action='ligar' turns on speaker recognition (notes "
        "'who is speaking now' are added to the conversation: answer that person by name). 'desligar'. "
        "'aprender' with nome: learns a person's voice (the person talks ~8 s after a beep; tell them to talk). "
        "'esquecer' with nome. 'pessoas' lists known voices. 'quem': who spoke recently."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ligar | desligar | aprender | esquecer | pessoas | quem"},
            "nome": {"type": "STRING"},
        },
        "required": [],
    },
}

_estado = {"ligado": False, "ultimo_nome": None, "ultima_nota": 0.0, "historico": [], "aprendendo": "",
           "desconhecido_nota": 0.0}
_separador = V.Separador()
_fila: queue.Queue = queue.Queue(maxsize=3)
_trabalhador = {"vivo": False}


def _app():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.app()
    except Exception:
        return None


def nota(texto: str) -> bool:
    app = _app()
    fn = getattr(app, "nota_contexto", None)
    return bool(fn and fn(texto))


def frase_nota(nome: str | None) -> str:
    if nome:
        return f"[Conversa em grupo] Quem está falando agora: {nome}."
    return "[Conversa em grupo] Agora fala uma voz que eu não conheço (visita?)."


def decidir_nota(nome: str | None, ultimo: str | None, desde_ultima_s: float,
                 desde_desconhecido_s: float) -> bool:
    """Vale mandar a nota? Só quando muda quem fala (ou de tempos em tempos) — puro."""
    if nome is None:
        return desde_desconhecido_s > 45
    return nome != ultimo or desde_ultima_s > 90


# ── ouvir ─────────────────────────────────────────────────────────────────────
def _ouvir(ts, bloco, mudo, jarvis_falando) -> None:
    if not _estado["ligado"] or mudo or _estado["aprendendo"]:
        return
    trecho = _separador.bloco(ts, bloco, jarvis_falando)
    if trecho is not None:
        try:
            _fila.put_nowait((ts, trecho))
        except queue.Full:
            pass


def _identificar_laco() -> None:
    while True:
        ts, trecho = _fila.get()
        try:
            qual = V.motor()
            vetor, qual = V.impressao(trecho, qual)
            nome, nota_ = V.identificar(vetor, V.perfis(qual), qual, V.raios(qual))
        except Exception as e:
            print(f"[Grupo] {e}")
            continue
        agora = time.time()
        _estado["historico"] = (_estado["historico"] + [(agora, nome or "desconhecido", nota_)])[-30:]
        if not _estado["ligado"]:
            continue
        if decidir_nota(nome, _estado["ultimo_nome"], agora - _estado["ultima_nota"],
                        agora - _estado["desconhecido_nota"]):
            if nota(frase_nota(nome)):
                if nome:
                    _estado["ultimo_nome"], _estado["ultima_nota"] = nome, agora
                else:
                    _estado["desconhecido_nota"] = agora


def _garantir_trabalhador() -> None:
    if not _trabalhador["vivo"]:
        _trabalhador["vivo"] = True
        threading.Thread(target=_identificar_laco, daemon=True, name="grupo").start()


def ligar() -> str:
    pessoas = V.nomes()
    if not pessoas:
        return ("Ainda não conheço nenhuma voz. Diga 'aprende a minha voz, eu sou …' e depois 'aprende a voz da …' "
                "para cada pessoa.")
    from core import escuta
    _estado.update(ligado=True, ultimo_nome=None, ultima_nota=0.0)
    _separador.zerar()
    escuta.inscrever(_ouvir)
    _garantir_trabalhador()
    nota(f"[MODO CONVERSA EM GRUPO ligado] Há mais de uma pessoa no quarto. Vozes que conheço: {', '.join(pessoas)}. "
         "Antes de algumas falas vai aparecer uma nota '[Conversa em grupo] Quem está falando agora: Nome'. Responda "
         "essa pessoa chamando pelo nome, lembre o que cada um pediu e, se perguntarem, diga quem disse o quê. Não "
         "leia estas notas em voz alta.")
    motor = "impressão de voz (resemblyzer)" if V.motor() == "resemblyzer" else "timbre (instale o resemblyzer " \
                                                                                  "para ficar mais preciso)"
    return f"Modo conversa em grupo ligado. Conheço: {', '.join(pessoas)}. Reconheço pelo {motor}."


def desligar() -> str:
    from core import escuta
    _estado["ligado"] = False
    escuta.desinscrever(_ouvir)
    nota("[MODO CONVERSA EM GRUPO desligado] Volte a falar só com o dono, como sempre.")
    return "Modo conversa em grupo desligado."


# ── aprender uma voz ──────────────────────────────────────────────────────────
def _aprender(nome: str) -> None:
    from core import escuta, microfone
    try:
        microfone.esperar_jarvis_calar(maximo_s=15)
        try:
            from plugins import _som
            import numpy as np
            t = _som.tempo(0.18, 22050)
            _som.tocar_uma((0.5 * np.sin(2 * np.pi * 880 * t)).astype("float32"), 22050, 0.5)
        except Exception:
            pass
        limiar = V.Separador().limiar_rms
        coletado: list = []

        def ouvir(ts, bloco, mudo, falando):
            import numpy as np
            if not falando:
                b = np.asarray(bloco).reshape(-1)
                if b.size and float(np.sqrt(np.mean(b.astype(np.float32) ** 2))) >= limiar:
                    coletado.append(b.astype(np.int16))
        with microfone.reservado_por(f"aprendendo a voz de {nome}", 25):
            escuta.inscrever(ouvir)
            fim = time.time() + 20
            while time.time() < fim and sum(b.size for b in coletado) < 8 * V.TAXA:
                time.sleep(0.2)
            escuta.desinscrever(ouvir)
        import numpy as np
        total = sum(b.size for b in coletado) / V.TAXA
        if total < 3:
            _avisar(f"Não ouvi o suficiente da voz de {nome} ({total:.0f} s). Tente de novo, falando mais perto.")
            return
        audio = np.concatenate(coletado)
        qual = V.motor()
        pedacos = [audio[i:i + 3 * V.TAXA] for i in range(0, audio.size - 2 * V.TAXA, 2 * V.TAXA)] or [audio]
        vetores = [v for v in (V.impressao(p, qual)[0] for p in pedacos) if v is not None]
        if not vetores:
            _avisar(f"Não consegui tirar a impressão da voz de {nome}. Tente de novo.")
            return
        V.salvar(nome, vetores, qual)
        _avisar(f"Pronto, aprendi a voz de {nome}.")
        if _estado["ligado"]:
            nota(f"[Conversa em grupo] Agora também conheço a voz de {nome}.")
    except Exception as e:
        _avisar(f"Não consegui aprender a voz de {nome}: {e}")
    finally:
        _estado["aprendendo"] = ""


def _avisar(texto: str) -> None:
    try:
        from plugins._notificar import notificar
        notificar(None, texto, titulo="Conversa em grupo", etiqueta="GRUPO")
    except Exception:
        registrar(None, texto)


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "pessoas").lower()
    nome = " ".join(str(p.get("nome") or "").split()).strip().title()
    try:
        if acao == "ligar":
            return ligar()
        if acao == "desligar":
            return desligar()
        if acao == "aprender":
            if not nome:
                return "De quem é a voz? Me diga o nome."
            if _estado["aprendendo"]:
                return f"Já estou aprendendo a voz de {_estado['aprendendo']}. Espere terminar."
            _estado["aprendendo"] = nome
            threading.Thread(target=_aprender, args=(nome,), daemon=True, name="aprender_voz").start()
            return (f"Diga para {nome}: depois do bip, falar qualquer coisa por uns 8 segundos, com a voz normal "
                    "(contar como foi o dia serve). Eu aviso quando aprender.")
        if acao == "esquecer":
            return f"Esqueci a voz de {nome}." if nome and V.esquecer(nome) else "Não conheço essa voz."
        if acao == "quem":
            if not _estado["historico"]:
                return "Ainda não identifiquei ninguém (o modo conversa em grupo está " + \
                    ("ligado)." if _estado["ligado"] else "desligado).")
            agora = time.time()
            linhas = [f"{n} (há {int(agora - ts)} s)" for ts, n, _nota in reversed(_estado["historico"][-5:])]
            return "Falaram por último: " + ", ".join(linhas) + "."
        pessoas = V.nomes()
        texto = ("Vozes que eu conheço: " + ", ".join(pessoas) + ".") if pessoas else "Ainda não conheço nenhuma voz."
        texto += f" Modo conversa em grupo {'ligado' if _estado['ligado'] else 'desligado'}."
        mostrar(player, "CONVERSA EM GRUPO", texto)
        return texto
    except Exception as e:
        return f"A conversa em grupo falhou: {e}"
