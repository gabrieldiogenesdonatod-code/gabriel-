"""
HUD 3.9 — o painel J.A.R.V.I.S animado, interativo e com os dados reais do PC (fork PT-BR 3.9.1).

    "Jarvis, abre o HUD"            "Jarvis, abre o HUD 3.9 em tela cheia"
    "Jarvis, fecha o HUD"           Botão  🛰  HUD 3.9  na gaveta de controles
    python -m hud39                 roda sem o JARVIS (só o painel)

O QUE TEM
    A arte do HUD de fundo, com os textos fixos trocados por números de verdade (core/telemetria.py):
    relógio, CPU, RAM, disco, rede, ping, GPU, temperaturas, processos e o sistema operacional.
    Animações por cima (anéis girando, radar, globo, reator pulsando, varredura, gráficos ao vivo)
    e tudo clicável:
        SISTEMA / logo      painel "Sobre o sistema" e "Sobre o J.A.R.V.I.S"
        INTERNET / globo    IP, Wi-Fi, ping, velocidade; abre o navegador
        ARQUIVOS            abre Documentos, Downloads, Imagens, Área de trabalho
        MÚSICA              tocar/pausar, próxima, anterior, volume (teclas de mídia do sistema)
        VÍDEOS              pasta de vídeos e pedido ao JARVIS (YouTube)
        JOGOS               Steam (se tiver) e pedido ao JARVIS
        CONFIG / reator     cor, sons, animações, varredura, tela cheia
        círculo JARVIS      fala ou digita um comando — vai para o JARVIS como se fosse no chat
        reator do peito     diagnóstico animado com os números do momento
        processos / GPU     detalhes

SEGURANÇA
    Só escuta em 127.0.0.1 e confere o cabeçalho Host (outro site não consegue ler nem mandar nada).
    Toda ação exige o token que só a página servida aqui conhece. Nenhuma ação apaga, instala ou
    finaliza nada: abre pastas, aperta teclas de mídia e repassa texto ao JARVIS.
"""
from __future__ import annotations

from .servidor import abrir, endereco, parar  # noqa: F401

VERSAO = "3.9.3"

_ESTADOS_PT = {"SLEEPING": "DORMINDO", "INITIALISING": "INICIANDO", "LISTENING": "OUVINDO", "SPEAKING": "FALANDO",
               "THINKING": "PENSANDO", "PROCESSING": "PROCESSANDO", "MUTED": "MUTADO"}


def abrir_do_jarvis(janela, tela_cheia: bool = True, painel: str = "", tema: str = "") -> str:
    """Abre o HUD ligado ao JARVIS. `janela` é a MainWindow do ui.py ou o JarvisUI que os plugins recebem.

    Os comandos vão pelo mesmo caminho do chat de texto (on_text_command) e o estado é só lido
    (OUVINDO, FALANDO…), nunca alterado: nada aqui mexe na interface Qt fora da thread dela.
    """
    win = getattr(janela, "_win", janela)

    def comando(texto: str) -> None:
        fn = getattr(win, "on_text_command", None)
        if callable(fn):
            fn(texto)

    def estado() -> dict:
        hud = getattr(win, "hud", None)
        st = str(getattr(hud, "state", "") or "")
        return {"estado": _ESTADOS_PT.get(st, st) or None, "falando": bool(getattr(hud, "speaking", False)),
                "mudo": bool(getattr(win, "_muted", False))}

    return abrir(comando=comando, estado=estado, tela_cheia=tela_cheia, painel=painel, tema=tema)
