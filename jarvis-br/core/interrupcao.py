"""
Interromper o JARVIS no meio da frase (fork PT-BR 2.4.1).

Jeitos de cortar a fala dele:
  • falar por cima (interrupção por voz — desliga em ⚙ CONFIG. DE PLUGINS →
    Interrupção, ou "Jarvis, desliga a interrupção por voz");
  • ESC ou o botão ✋ INTERROMPER, com a janela do JARVIS na frente;
  • Ctrl+Alt+P em qualquer janela (Windows);
  • apertar a tecla do push-to-talk enquanto ele fala.

O que estava errado até a 2.4, e o que este módulo arruma:
  1. depois de um ESC a PRÓXIMA resposta saía muda. O "estou interrompido" só
     desligava no fim do turno do servidor; como o servidor manda a resposta
     mais rápido do que ela toca, normalmente esse fim já tinha passado, e o
     próximo fim era o da resposta seguinte — que era jogada fora inteira;
  2. o aviso `interrupted` do Gemini (ele parou de gerar porque você falou ou
     chegou outro pedido) era ignorado, e o áudio que já tinha chegado tocava;
  3. o que já estava no buffer da placa de som (até meio segundo) ainda tocava
     depois do ESC;
  4. falar por cima não fazia nada: o microfone fica fechado para o modelo
     enquanto o JARVIS fala (senão ele ouve o próprio eco) e a detecção local
     estava desligada.

Tudo aqui é puro ou recebe as dependências por parâmetro, para dar teste.
"""

from __future__ import annotations

import threading
import time
from collections import deque

# Ctrl+Alt+P ("parar"): livre no Windows e no teclado ABNT2 (AltGr+P não digita nada).
ATALHO = ("ctrl", "alt", "p")
FATIA_ESCRITA = 1920            # 40 ms de áudio a 24 kHz, 16 bits, mono
ESPERA_MAX_DESCARTE_S = 4.0     # segurança: sem nada da resposta cortada por 4 s, volta a tocar
PREROLL_S = 0.9                 # quanto do começo da sua fala vai junto quando você interrompe
JANELA_ENVIO_S = 1.5            # depois de interromper pela voz, o microfone vai direto ao modelo
NIVEL_SILENCIO = 0.06           # abaixo disso o microfone "não ouviu nada" (o mesmo piso do core/echo.py)
NIVEL_VOZ_FONE = 0.08           # com fone, som sustentado acima disso é você falando


def config(chave: str, padrao=None):
    """Opção de ⚙ CONFIG. DE PLUGINS → Interrupção (plugins/interrupcao.py)."""
    try:
        from memory.config_manager import get_plugin_setting
        v = get_plugin_setting("interrupcao", chave, padrao)
        return padrao if v is None else v
    except Exception:
        return padrao


class EstadoInterrupcao:
    """O que fazer com o áudio que chega do servidor depois de uma interrupção.

    `epoca` muda a cada interrupção: o áudio guardado na fila leva a época em
    que chegou, e o que for de uma época velha não toca. `descartando` só liga
    se o servidor AINDA estava mandando a resposta cortada — se ele já tinha
    terminado, nada mais daquela resposta vai chegar e a próxima toca normal.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.epoca = 0
        self.descartando = False
        self.resposta_em_curso = False
        self._desde = 0.0
        self._ultimo = 0.0

    def zerar(self) -> None:
        with self._lock:
            self.epoca += 1
            self.descartando = False
            self.resposta_em_curso = False

    def pedir(self, agora: float | None = None) -> bool:
        """Interrupção local (ESC, botão, atalho, voz). True se vai descartar o resto da resposta."""
        agora = time.monotonic() if agora is None else agora
        with self._lock:
            self.epoca += 1
            if self.resposta_em_curso:
                self.descartando = True
                self._desde = self._ultimo = agora
            return self.descartando

    def descartar_proxima(self, agora: float | None = None) -> None:
        """3.2 (anti-eco): o que o microfone mandou era a voz do próprio JARVIS — a resposta a isso,
        já chegando ou ainda por vir, é jogada fora até o fim do turno."""
        agora = time.monotonic() if agora is None else agora
        with self._lock:
            self.epoca += 1
            self.descartando = True
            self._desde = self._ultimo = agora

    def marcar_resposta(self) -> None:
        with self._lock:
            self.resposta_em_curso = True

    def audio_chegou(self, agora: float | None = None) -> bool:
        """Chegou áudio do modelo. True = jogar fora (é o resto da resposta cortada)."""
        agora = time.monotonic() if agora is None else agora
        with self._lock:
            self.resposta_em_curso = True
            if self.descartando:
                self._ultimo = agora
                return True
            return False

    def fim_do_turno(self) -> bool:
        """turn_complete. True se ele encerrou a resposta que você cortou."""
        with self._lock:
            self.resposta_em_curso = False
            era = self.descartando
            self.descartando = False
            return era

    def servidor_interrompeu(self) -> bool:
        """O Gemini avisou `interrupted`: ele parou a resposta. O que vier depois é novo."""
        with self._lock:
            era = self.descartando
            self.epoca += 1
            self.descartando = False
            self.resposta_em_curso = False
            return era

    def vencido(self, agora: float | None = None, limite: float = ESPERA_MAX_DESCARTE_S) -> bool:
        """Segurança: descartando há muito tempo sem chegar nada da resposta cortada → para de descartar."""
        agora = time.monotonic() if agora is None else agora
        with self._lock:
            if self.descartando and agora - max(self._desde, self._ultimo) > limite:
                self.descartando = False
                self.resposta_em_curso = False
                return True
            return False


class DetectorVoz:
    """Decide, bloco a bloco do microfone, quando a SUA voz deve cortar o JARVIS.

    Guarda o último ~1 s do microfone (pre-roll) para o modelo ouvir o começo
    do que você disse, não só o que veio depois de detectar.
    """

    def __init__(self, preroll_s: float = PREROLL_S) -> None:
        self._preroll: deque[tuple[float, bytes]] = deque(maxlen=64)
        self._preroll_s = preroll_s
        self.seguidos = 0
        self._enviar_ate = 0.0
        # O microfone ficou quieto enquanto o JARVIS falava alto? (fone de ouvido)
        self._quieto: deque[bool] = deque(maxlen=60)
        # Barulho de fundo com o JARVIS calado (TV, música, ventilador): a sua voz
        # precisa passar bem disso para contar.
        self._ambiente: deque[float] = deque(maxlen=160)
        # Quanto do som do JARVIS o microfone pega NESTA fala (nível do microfone ÷
        # nível tocado), dos blocos que não eram voz. Zera a cada fala: se você
        # mexer no volume, a próxima fala já aprende o novo.
        self._razoes: deque[float] = deque(maxlen=25)

    def zerar(self) -> None:
        """Começo de uma fala nova (o que se sabe sobre fone/caixa de som continua)."""
        self._preroll.clear()
        self._razoes.clear()
        self.seguidos = 0
        self._enviar_ate = 0.0

    def observar(self, nivel: float, nivel_saida: float) -> None:
        """Bloco que não foi voz, com o JARVIS falando alto: o microfone ouviu ele? Quanto?"""
        if nivel_saida > 0.15:
            self._quieto.append(nivel < max(NIVEL_SILENCIO, 1.5 * self.fundo + 0.02))
        if nivel_saida > 0.1:
            self._razoes.append(nivel / nivel_saida)

    @property
    def ganho_recente(self) -> float | None:
        """Eco desta fala: mediana de nível do microfone ÷ nível tocado (None nos primeiros ~0,5 s)."""
        if len(self._razoes) < 8:
            return None
        return sorted(self._razoes)[len(self._razoes) // 2]

    def ambiente(self, nivel: float) -> None:
        """Nível do microfone com o JARVIS calado (chamado fora da fala dele)."""
        self._ambiente.append(float(nivel))

    @property
    def fundo(self) -> float:
        """Barulho de fundo típico (o que o microfone ouve com o JARVIS calado e você quieto)."""
        if len(self._ambiente) < 15:
            return 0.0
        return sorted(self._ambiente)[int(0.3 * (len(self._ambiente) - 1))]

    @property
    def piso_voz(self) -> float:
        """Nível mínimo para um bloco contar como voz: acima do barulho de fundo."""
        return max(NIVEL_VOZ_FONE, 2.0 * self.fundo + 0.04)

    @property
    def sem_eco(self) -> bool:
        """Fone de ouvido (ou microfone longe da caixa): o microfone quase não ouve o JARVIS."""
        return len(self._quieto) >= 30 and sum(self._quieto) >= 0.85 * len(self._quieto)

    def bloco(self, dados: bytes, eh_voz: bool, necessarios: int, agora: float | None = None) -> str:
        """'nada' | 'interromper' (corte agora e mande o pre-roll) | 'enviar' (já cortou: mande direto)."""
        agora = time.monotonic() if agora is None else agora
        self._preroll.append((agora, dados))
        if agora < self._enviar_ate:
            return "enviar"
        self.seguidos = self.seguidos + 1 if eh_voz else 0
        if self.seguidos >= max(1, int(necessarios)):
            self.seguidos = 0
            self._enviar_ate = agora + JANELA_ENVIO_S
            return "interromper"
        return "nada"

    def esvaziar(self, agora: float | None = None) -> list[bytes]:
        """O começo da sua fala (só o que é recente; nada de um minuto atrás)."""
        agora = time.monotonic() if agora is None else agora
        blocos = [d for t, d in self._preroll if agora - t <= self._preroll_s]
        self._preroll.clear()
        return blocos


def parece_voz(guarda, pcm, sr: int, nivel: float, nivel_saida: float, agora: float | None = None,
               ganho: float | None = None) -> bool:
    """Este bloco do microfone é uma pessoa falando, e não o eco do JARVIS? (caixa de som)

    1º caminho: o EchoGuard (core/echo.py) subtrai o que está tocando e sobra voz
    de outra pessoa — e não pode estar mais baixo do que o eco esperado.
    2º caminho (só depois de ~0,5 s da fala, com o eco DESTA fala medido em
    `ganho`): o som está bem mais alto do que o eco e o conteúdo não bate direito
    com o que o JARVIS está falando — quanto mais alto, menos o conteúdo precisa provar.
    """
    try:
        if not getattr(guarda, "_hist", None):
            return False                      # ainda não sabemos o que está tocando
        if guarda.is_user_speech(pcm, sr, nivel, agora):
            g = ganho if ganho is not None else (guarda.gain if getattr(guarda, "calibrated", False) else None)
            return not (g is not None and nivel < g * nivel_saida * 1.3)
        if ganho is None:
            return False
        esperado = ganho * nivel_saida
        residuo = 1.0 - guarda.last_similarity
        if residuo >= max(guarda.floor * 1.8, 0.18) and nivel >= esperado * 1.6 + 0.06:
            return True
        return residuo >= guarda.floor * 0.9 and nivel >= esperado * 2.5 + 0.10
    except Exception:
        return False                          # na dúvida, não corta


def continuo(pcm, partes: int = 8) -> bool:
    """Som que dura o bloco inteiro (voz), e não um estalo (tecla, clique, batida na mesa)."""
    try:
        import numpy as np
        x = np.asarray(pcm, dtype=np.float32).reshape(-1)
        n = (x.size // partes) * partes
        if n < partes * 16:
            return False
        e = (x[:n].reshape(partes, -1) ** 2).mean(axis=1)
        return int((e >= 0.25 * float(e.max())).sum()) >= max(1, int(partes * 0.6))
    except Exception:
        return False


def eh_voz(guarda, detector: DetectorVoz, pcm, sr: int, nivel: float, nivel_saida: float,
           agora: float | None = None) -> bool:
    """Decisão de cada bloco enquanto o JARVIS fala.

    Com fone (o microfone não ouve o JARVIS), som sustentado já é você. Com caixa
    de som, precisa separar a sua voz do eco (parece_voz). O que NÃO foi voz
    ensina se esta é uma sala com eco ou sem.
    """
    if detector.sem_eco:                       # fone: o microfone não ouve o JARVIS
        voz = nivel >= detector.piso_voz and continuo(pcm)
    else:                                      # caixa de som: separa do eco (e do fundo)
        voz = (parece_voz(guarda, pcm, sr, nivel, nivel_saida, agora, detector.ganho_recente)
               and nivel >= detector.piso_voz and continuo(pcm))
    if not voz:
        detector.observar(nivel, nivel_saida)
    return voz


def escrever_cortavel(escrever, dados: bytes, epoca_atual, epoca: int, fatia: int = FATIA_ESCRITA) -> bool:
    """Escreve em pedaços de 40 ms e para no meio se houve interrupção. False = foi cortado."""
    for i in range(0, len(dados), fatia):
        if epoca_atual() != epoca:
            return False
        escrever(dados[i:i + fatia])
    return True


# Fork PT-BR 2.7.3: a antiga descartar_saida() (abort() + start() na placa de som) foi APAGADA. Ela era
# chamada pelo botão INTERROMPER até a 2.6.1 e derrubava o Python inteiro em várias placas no Windows.
# Nada no projeto pode voltar a chamar abort() num stream de áudio (tests/test_31_falhas.py confere).
