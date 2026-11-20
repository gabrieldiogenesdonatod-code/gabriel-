"""
Modo vitrine (fork PT-BR 2.6): "Jarvis, se apresenta."

Abre uma tela cheia de cinema (dashboard/static/vitrine.html) e o JARVIS se
apresenta sozinho: cena por cena, com a VOZ dele narrando, legenda, efeitos
sonoros e uma demonstração animada de cada função — pronto para gravar o
vídeo de divulgação no OBS (capture a janela + o áudio do PC).

    "Jarvis, se apresenta"                 → versão completa (~4 min, 16:9)
    "Jarvis, se apresenta em versão curta" → ~1 min, as melhores
    "Jarvis, modo vitrine na vertical"     → 9:16 para Reels/TikTok/Shorts
    "Jarvis, para a vitrine" / "pula a cena"
    "Jarvis, abre o roteiro da vitrine"    → edite as falas, a ordem e o que entra

As demonstrações usam DADOS DE EXEMPLO (nenhuma conta, encomenda ou memória
sua aparece no vídeo) e nada de verdade é executado. O microfone fica pausado
durante a apresentação, para ninguém atrapalhar a gravação.
"""

from __future__ import annotations

import threading
import time

from plugins._comum import MEMORIA, abrir_no_sistema, falar, gravar_json, ler_json, registrar

PLUGIN = {
    "name": "vitrine",
    "brief": "Showcase mode: 'se apresenta' — JARVIS presents his best features scene by scene for a promo video.",
    "description": (
        "Showcase / presentation mode for recording a promo video. action='iniciar' (when the user says 'se "
        "apresenta', 'modo vitrine', 'mostra o que você sabe fazer') with optional versao ('completa' | 'curta') and "
        "formato ('horizontal' | 'vertical'): opens a full-screen stage and narrates each feature by himself with "
        "effects. While it runs, say ONLY the narration lines you receive. 'parar', 'pular' (next scene), 'roteiro' "
        "opens the editable script, 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "iniciar | parar | pular | roteiro | status"},
            "versao": {"type": "STRING"}, "formato": {"type": "STRING"},
        },
        "required": [],
    },
}

ARQ_ROTEIRO = MEMORIA / "vitrine_roteiro.json"
# visual: o nome da animação na vitrine.html. curta: entra na versão curta.
ROTEIRO_PADRAO = [
    {"visual": "abertura", "titulo": "J.A.R.V.I.S BR", "sub": "Assistente de voz em português", "curta": True,
     "fala": "Olá. Eu sou o JARVIS BR, um assistente de voz em português que roda no seu computador. "
             "Deixa eu mostrar o que eu sei fazer."},
    {"visual": "voz", "titulo": "Conversa de verdade", "sub": "Voz em tempo real · pode interromper", "curta": True,
     "fala": "Eu converso por voz em tempo real, igual a uma pessoa. Se você falar por cima, eu paro e escuto."},
    {"visual": "pc", "titulo": "Controle total do PC", "sub": "Monitor · apps · limpeza · alertas", "curta": False,
     "fala": "Eu monitoro e controlo o seu PC: abro programas, fecho o que travou, limpo arquivos e aviso se a "
             "temperatura subir."},
    {"visual": "visao", "titulo": "Eu vejo a sua tela", "sub": "Tela e câmera em tempo real", "curta": False,
     "fala": "Eu vejo a sua tela e a câmera. Apareceu um erro? É só dizer: olha isso."},
    {"visual": "boleto", "titulo": "Contas a vencer", "sub": "Boletos do e-mail e PDF", "curta": True,
     "fala": "Eu leio os boletos que chegam no e-mail e aviso antes de vencer. A conta de luz vence sexta, "
             "cento e quarenta e dois reais."},
    {"visual": "encomenda", "titulo": "Rastreio de encomendas", "sub": "Correios · Shopee · Mercado Livre",
     "curta": False,
     "fala": "Eu rastreio as suas encomendas e aviso sozinho. Senhor, sua encomenda saiu pra entrega."},
    {"visual": "radar", "titulo": "Recolhe a roupa!", "sub": "Radar de chuva bem local", "curta": True,
     "fala": "Olho o radar de chuva pra você. Vai chover em uns vinte minutos: melhor tirar a roupa do varal."},
    {"visual": "foco", "titulo": "Modo foco", "sub": "Pomodoro · celular na mão · negociação", "curta": False,
     "fala": "No foco, eu seguro as distrações. Pegou o celular? O celular pode esperar mais doze minutos."},
    {"visual": "grafo", "titulo": "Memória em grafo", "sub": "Rede neural treinada no seu PC", "curta": False,
     "fala": "Eu lembro do que você me conta e ligo as coisas, numa memória em grafo com uma rede neural "
             "treinada no seu próprio PC."},
    {"visual": "loja", "titulo": "Ajuda na loja", "sub": "Vendas · estoque · posts · clientes", "curta": False,
     "fala": "Eu também ajudo na loja: registro vendas, cuido do estoque, crio posts e preparo respostas para "
             "os clientes."},
    {"visual": "repulsor", "titulo": "Modo Homem de Ferro", "sub": "Luva repulsor · capacete · painel de LED",
     "curta": True,
     "fala": "E tem a parte Homem de Ferro: luva repulsor, capacete e painel de LED na parede, tudo com ESP32."},
    {"visual": "mao", "titulo": "Holograma na mão", "sub": "Realidade aumentada pela webcam", "curta": False,
     "fala": "Abra a mão na frente da câmera e eu mostro um holograma na palma dela."},
    {"visual": "avatar", "titulo": "Avatar para lives", "sub": "Reage ao chat e às vendas", "curta": False,
     "fala": "Nas lives eu fico no canto da tela e reajo a tudo: eu rio, me surpreendo e comemoro."},
    {"visual": "jogos", "titulo": "Arcade J.A.R.V.I.S", "sub": "19 jogos · xadrez com motor próprio", "curta": True,
     "fala": "E quando bate o tédio, são dezenove jogos: de xadrez contra mim até o labirinto do Bitinho."},
    {"visual": "fim", "titulo": "J.A.R.V.I.S BR", "sub": "Em português · no seu PC", "curta": True,
     "fala": "Tudo isso em português, rodando no seu PC. Eu sou o JARVIS BR. Até a próxima."},
]
CREDITO = "Fork do Mark LVI, de FatihMakes · licença CC BY-NC 4.0"
_lock = threading.Lock()
_estado = {"ativo": False, "indice": -1, "cenas": [], "inicio_cena": 0.0, "formato": "horizontal",
           "pular": threading.Event(), "parar": threading.Event(), "falando_desde": 0.0}


def roteiro() -> list[dict]:
    d = ler_json(ARQ_ROTEIRO, None)
    if not isinstance(d, list) or not d:
        gravar_json(ARQ_ROTEIRO, ROTEIRO_PADRAO)
        return [dict(c) for c in ROTEIRO_PADRAO]
    return [c for c in d if isinstance(c, dict) and c.get("fala") and not c.get("pular")]


def escolher(cenas: list[dict], versao: str) -> list[dict]:
    """Versão curta: só as marcadas (a abertura e o fim sempre entram) — puro."""
    if not str(versao or "").lower().startswith("curt"):
        return cenas
    return [c for i, c in enumerate(cenas) if c.get("curta") or i == 0 or i == len(cenas) - 1]


def duracao_estimada(fala: str) -> float:
    """Segundos para falar (≈ 14 letras/s) — puro."""
    return 2.0 + len(str(fala or "")) / 14.0


def _app():
    try:
        from core import registro_ferramentas
        return registro_ferramentas.app()
    except Exception:
        return None


def _narrar(texto: str) -> None:
    """A fala sai na voz do JARVIS; espera ele terminar (ou o tempo estimado, sem sessão)."""
    app = _app()
    estimado = duracao_estimada(texto)
    if app is None or not getattr(app, "session", None):
        _esperar(estimado)
        return
    try:
        from core import registro_ferramentas
        player = registro_ferramentas.player()
    except Exception:
        player = None
    falar(player, "[VITRINE] Você está gravando um vídeo de apresentação. Leia em voz alta, exatamente assim, "
                  f"com entusiasmo e sem acrescentar nada nem chamar ferramentas: «{texto}»")
    comecou = time.time()
    while time.time() - comecou < 6 and not getattr(app, "_is_speaking", False):     # o modelo começa a falar
        if _esperar(0.1):
            return
    _estado["falando_desde"] = time.time()
    limite = time.time() + estimado + 10
    while time.time() < limite and getattr(app, "_is_speaking", False):
        if _esperar(0.15):
            return
    _esperar(0.7)


def _esperar(segundos: float) -> bool:
    """Dorme; True se pediram para pular ou parar."""
    fim = time.time() + segundos
    while time.time() < fim:
        if _estado["parar"].is_set() or _estado["pular"].is_set():
            return True
        time.sleep(0.05)
    return False


def _apresentar(cenas: list[dict]) -> None:
    from core import microfone
    try:
        microfone.esperar_jarvis_calar(maximo_s=12, folga_s=0.5)
        microfone.reservar("vitrine", 60 * 30)
        _esperar(2.5)                                          # tempo de a janela abrir e você dar REC
        for i, c in enumerate(cenas):
            if _estado["parar"].is_set():
                break
            _estado["pular"].clear()
            with _lock:
                _estado["indice"], _estado["inicio_cena"] = i, time.time()
            _esperar(1.2)                                      # a animação de entrada aparece antes da fala
            _narrar(c["fala"])
            _esperar(float(c.get("pausa", 1.5)))
        with _lock:
            _estado["indice"] = len(cenas)                     # tela final (créditos)
        _esperar(4)
    except Exception as e:
        registrar(None, f"Vitrine: {e}")
    finally:
        microfone.liberar()
        with _lock:
            _estado["ativo"] = False
        registrar(None, "Vitrine: apresentação terminada.")


def estado_tela(_q: dict | None = None) -> dict:
    app = _app()
    falando = bool(getattr(app, "_is_speaking", False)) if app is not None else False
    nivel = float(getattr(app, "_out_level", 0.0) or 0.0) if falando else 0.0
    with _lock:
        i, cenas = _estado["indice"], _estado["cenas"]
        cena = cenas[i] if 0 <= i < len(cenas) else None
        return {"ativo": _estado["ativo"], "indice": i, "total": len(cenas), "cena": cena,
                "tempo": round(time.time() - _estado["inicio_cena"], 2), "falando": falando, "nivel": round(nivel, 3),
                "formato": _estado["formato"], "credito": CREDITO, "fim": i >= len(cenas) and bool(cenas)}


def comando_tela(b: dict) -> dict:
    acao = str(b.get("acao") or "")
    if acao == "pular":
        _estado["pular"].set()
    elif acao == "parar":
        _estado["parar"].set()
    return {"ok": True}


def _registrar_rotas() -> None:
    from plugins import _arcade
    _arcade.ROTAS_GET["/api/vitrine"] = estado_tela
    _arcade.ROTAS_POST["/api/vitrine/cmd"] = comando_tela


def iniciar(versao: str = "", formato: str = "") -> str:
    if _estado["ativo"]:
        return "A vitrine já está rodando. Diga 'para a vitrine' para encerrar."
    cenas = escolher(roteiro(), versao)
    vertical = str(formato or "").lower().startswith("vert")
    with _lock:
        _estado.update(ativo=True, indice=-1, cenas=cenas, inicio_cena=time.time(),
                       formato="vertical" if vertical else "horizontal")
    _estado["pular"].clear()
    _estado["parar"].clear()
    from plugins import _arcade
    _registrar_rotas()
    _arcade.abrir_pagina("/vitrine", 608 if vertical else 1600, 1080 if vertical else 900,
                         extras=["--autoplay-policy=no-user-gesture-required"])
    threading.Thread(target=_apresentar, args=(cenas,), daemon=True, name="vitrine").start()
    total = sum(duracao_estimada(c["fala"]) + 4 for c in cenas)
    return (f"Modo vitrine: {len(cenas)} cenas, uns {round(total / 60)} min. Diga só: 'Luzes, câmera… vamos lá.' "
            "Comece a gravar no OBS (janela + áudio do PC). Esc na tela pula; 'para a vitrine' encerra.")


def on_session_start(player) -> None:
    try:
        _registrar_rotas()
    except Exception:
        pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "iniciar").lower()
    try:
        if acao == "iniciar":
            return iniciar(str(p.get("versao") or ""), str(p.get("formato") or ""))
        if acao == "parar":
            _estado["parar"].set()
            return "Vitrine encerrada." if _estado["ativo"] else "A vitrine não está rodando."
        if acao == "pular":
            _estado["pular"].set()
            return "Próxima cena."
        if acao == "roteiro":
            roteiro()
            abrir_no_sistema(str(ARQ_ROTEIRO))
            return (f"Abri o roteiro ({ARQ_ROTEIRO.name}). Mude as falas, a ordem, ponha \"pular\": true numa cena "
                    "ou \"curta\": true para entrar na versão curta. Apague o arquivo para voltar ao padrão.")
        e = estado_tela()
        if not e["ativo"]:
            return f"Vitrine parada. O roteiro tem {len(roteiro())} cenas."
        return f"Vitrine rodando: cena {e['indice'] + 1} de {e['total']}."
    except Exception as e:
        return f"A vitrine falhou: {e}"
