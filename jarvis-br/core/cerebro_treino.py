"""
Treino do CÉREBRO PRONTO (fork PT-BR 3.9.4) — gera core/cerebro_base.json.

O cérebro local (core/cerebro.py) nascia quase vazio: só as frases de exemplo dos plugins, sem os
parâmetros, então ele adivinhava a ferramenta mas não sabia O QUE fazer com ela. Este arquivo é o
"livro de estudo": centenas de comandos do dia a dia, escritos do jeito que brasileiro fala
("aumenta o som", "bota mais alto", "não tô ouvindo nada"…), cada um com a ferramenta E a ação.

Rodar (da pasta do projeto) para treinar de novo depois de mudar as frases:

    python -m core.cerebro_treino            # gera core/cerebro_base.json e mostra a nota da prova
    python -m core.cerebro_treino --prova    # só a prova, sem gravar

Como é treinado:
  1. Cada intenção tem padrões com alternativas: "(aumenta|sobe) [o] volume" vira "aumenta volume",
     "aumenta o volume", "sobe volume", "sobe o volume"…  (até MAX_POR_INTENCAO frases cada).
  2. Frases que dão a mesma "chave" (core/cerebro.chave) são juntadas; frase que caiu em duas
     intenções diferentes é ambígua e sai do treino (aparece no relatório).
  3. Uma PROVA com frases que o cérebro NUNCA viu (PROVA, no fim do arquivo) mede o acerto do
     modelo treinado. O arquivo só é gravado se a prova passar de NOTA_MINIMA.
  4. Os padrões com lacuna (PADROES) — "abre o <app>", "toca <música>", "volume <número>"… —
     vão junto e servem quando o Gemini está fora.

Segurança: nada de desligar/reiniciar/formatar/apagar aqui. Ferramenta crítica nunca vira reflexo
(core/cerebro.py confere de novo na hora de usar), e com o Gemini no ar a base só SUGERE.
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "core" / "cerebro_base.json"
VERSAO = 1
MAX_POR_INTENCAO = 160
NOTA_MINIMA = 0.85

# ─────────────────────────────────────────────────────────── intenções ───
# (ferramenta, parâmetros fixos, [padrões]).  (a|b|) = alternativas (vazio vale), [x] = opcional.
I = []


def intencao(ferramenta: str, args: dict, *padroes: str) -> None:
    I.append((ferramenta, dict(args), list(padroes)))


CS = "computer_settings"
_VOL = "(volume|som|audio)"
_PC = "(pc|computador|notebook|maquina)"

# ── som e tela ──
intencao(CS, {"action": "volume_up"},
         "(aumenta|aumente|aumentar|sobe|suba|subir|levanta|bota|coloca) [o] " + _VOL + " [mais] [alto]",
         "(mais alto|mais som|mais volume|volume mais alto|som mais alto)",
         "nao (to|estou|tou) ouvindo (nada|direito|bem)", "(ta|esta) (muito|bem) baixo [o som]",
         "aumenta um pouco [o som]", "volume pra cima", "sobe o som ai")
intencao(CS, {"action": "volume_down"},
         "(abaixa|abaixe|abaixar|diminui|diminua|diminuir|baixa|baixe|reduz|reduza) [o] " + _VOL,
         "(mais baixo|menos som|menos volume|volume mais baixo|som mais baixo)",
         "(ta|esta) (muito|bem|meio) alto [o som]", "volume pra baixo", "(deixa|bota|coloca) o (som|volume) mais (baixo|baixinho)", "abaixa um pouco [o som]")
intencao(CS, {"action": "mute"},
         "(muta|mute|silencia|silenciar|desliga|corta|tira) [o] " + _VOL,
         "(deixa|coloca|bota) [o pc] no mudo", "(silencia|muta|mute) o " + _PC, "modo mudo", "(muta|silencia) tudo", "sem som")
intencao(CS, {"action": "brightness_up"},
         "(aumenta|aumente|sobe|suba|aumentar) [o] brilho [da tela]", "(mais brilho|tela mais clara|clareia a tela)",
         "(ta|esta) muito escur(o|a) [a tela]")
intencao(CS, {"action": "brightness_down"},
         "(abaixa|abaixe|diminui|diminua|baixa|reduz) [o] brilho [da tela]", "(menos brilho|tela mais escura|escurece a tela)",
         "(ta|esta) muito clar(o|a) [a tela]")
intencao(CS, {"action": "screenshot"},
         "(tira|tire|faz|faca|bate|bata|tirar) [um|uma] (print|printscreen|captura de tela|screenshot|foto da tela)",
         "(printa|printar) [a tela]", "(salva|grava) [um] print [da tela]", "captura [a] tela")
intencao(CS, {"action": "lock_screen"},
         "(bloqueia|bloqueie|bloquear|tranca|tranque|trava) [o|a] (" + _PC[1:-1] + "|tela)",
         "bloqueia tudo", "vou sair (bloqueia|tranca) [o pc]")
intencao(CS, {"action": "show_desktop"},
         "(mostra|mostre|vai para|vai pra|abre) [a] area de trabalho", "(minimiza|minimizar) tudo", "esconde tudo [da tela]")
intencao(CS, {"action": "minimize"}, "(minimiza|minimize|minimizar) [essa|esta|a] janela", "(esconde|abaixa) [essa] janela")
intencao(CS, {"action": "maximize"}, "(maximiza|maximize|maximizar) [essa|esta|a] janela", "janela (grande|maximizada)",
         "aumenta [essa] janela")
intencao(CS, {"action": "close_window"}, "(fecha|feche|fechar) [essa|esta|a] janela", "fecha [essa] janela ai")
intencao(CS, {"action": "full_screen"}, "(tela cheia|modo tela cheia)", "(coloca|bota|deixa|poe) [em] tela cheia",
         "(sai|sair) da tela cheia")
intencao(CS, {"action": "switch_window"}, "(troca|muda|alterna|trocar) [de] janela", "proxima janela", "volta pra outra janela")
intencao(CS, {"action": "snap_left"}, "(joga|coloca|move|manda) [a] janela pra esquerda", "janela na esquerda")
intencao(CS, {"action": "snap_right"}, "(joga|coloca|move|manda) [a] janela pra direita", "janela na direita")
intencao(CS, {"action": "task_manager"}, "(abre|abra|abrir|chama|mostra) [o] gerenciador de tarefas", "gerenciador de tarefas")
intencao(CS, {"action": "file_explorer"},
         "(abre|abra|abrir) [o] (explorador de arquivos|explorer|gerenciador de arquivos|meus arquivos)", "explorador de arquivos")
intencao(CS, {"action": "open_settings"}, "(abre|abra|abrir) [as] (configuracoes|configuracao|definicoes) [do windows|do pc|do sistema]",
         "configuracoes do (windows|pc|sistema)")
intencao(CS, {"action": "dark_mode"}, "(liga|ativa|ativar|coloca|bota) [o] (modo escuro|tema escuro|dark mode)",
         "(modo escuro|tema escuro|dark mode)")
intencao(CS, {"action": "sleep_display"}, "(apaga|desliga|desligar|apagar) [a] (tela|monitor)", "(tela|monitor) (apagado|desligado)")
intencao(CS, {"action": "pause_video"}, "(pausa|pause|pausar|despausa) [o] video", "(da|de) (play|pause) [no video]")
intencao(CS, {"action": "refresh_page"}, "(atualiza|atualize|atualizar|recarrega|recarregue|recarregar) [a] pagina", "(da|aperta) f5")
intencao(CS, {"action": "new_tab"}, "(abre|abra|abrir|cria) [uma] (nova aba|aba nova|outra aba)", "nova aba")
intencao(CS, {"action": "close_tab"}, "(fecha|feche|fechar) [essa|esta|a] aba", "fecha [a] guia")
intencao(CS, {"action": "next_tab"}, "(proxima|outra) aba", "(vai|passa|muda) pra proxima aba")
intencao(CS, {"action": "prev_tab"}, "aba anterior", "(volta|vai) pra aba anterior")
intencao(CS, {"action": "go_back"}, "(volta|voltar|volte) [a|uma] pagina", "pagina anterior")
intencao(CS, {"action": "zoom_in"}, "(aumenta|aumente|da) [o] zoom", "(mais zoom|zoom mais|aproxima)", "(aumenta|aumente) [a] letra")
intencao(CS, {"action": "zoom_out"}, "(diminui|diminua|tira) [o] zoom", "(menos zoom|zoom menos|afasta)", "(diminui|diminua) [a] letra")
intencao(CS, {"action": "zoom_reset"}, "(zoom normal|volta o zoom|reseta o zoom|zoom padrao)")
intencao(CS, {"action": "scroll_down"}, "(rola|rolar|desce|descer|desca) [a pagina] [pra baixo]", "(rola|desce) [um pouco] pra baixo")
intencao(CS, {"action": "scroll_up"}, "(rola|rolar|sobe|subir|suba) [a pagina] pra cima", "sobe a pagina")
intencao(CS, {"action": "scroll_top"}, "(vai|volta) pro (topo|inicio) [da pagina]", "(topo|comeco) da pagina")
intencao(CS, {"action": "scroll_bottom"}, "(vai|desce) pro (fim|final) [da pagina]", "(fim|final) da pagina")
intencao(CS, {"action": "copy"}, "(copia|copie|copiar) [isso|isto|o texto]", "control c")
intencao(CS, {"action": "paste"}, "(cola|cole|colar) [isso|aqui|o texto]", "control v")
intencao(CS, {"action": "select_all"}, "(seleciona|selecione|selecionar|marca) tudo", "control a")
intencao(CS, {"action": "save"}, "(salva|salve|salvar) [o] (arquivo|documento|isso)", "control s")
intencao(CS, {"action": "find_on_page"}, "(procura|procure|busca) na pagina", "(pesquisa|procura) nessa pagina")

intencao("controle_audio_video", {"action": "trocar_saida", "dispositivo": "fone"},
         "(troca|muda|passa|joga) [o] (som|audio) (pro|para o|pra) fone", "som no fone", "usa o fone [de ouvido]")
intencao("controle_audio_video", {"action": "trocar_saida", "dispositivo": "caixa"},
         "(troca|muda|passa|joga) [o] (som|audio) (pra|para a) caixa [de som]", "som na caixa [de som]")
intencao("controle_audio_video", {"action": "saidas"}, "(quais|lista) [as] saidas de (som|audio)", "dispositivos de (som|audio)")
intencao("controle_audio_video", {"action": "apps_audio"}, "(quem|que programa|qual app) (ta|esta) (tocando|fazendo barulho)",
         "(de onde|da onde) (vem|ta vindo) esse som")
intencao("controle_audio_video", {"action": "luz_noturna", "ligar": "sim"},
         "(liga|ativa|ativar) [a] luz noturna", "(filtro de luz azul|modo leitura da tela)")
intencao("controle_audio_video", {"action": "luz_noturna", "ligar": "nao"}, "(desliga|desativa|desativar) [a] luz noturna")

# ── apps (abrir / fechar) ──
_APPS = {
    "chrome": "(chrome|google chrome|o chrome)", "navegador": "(navegador|browser|internet)",
    "spotify": "spotify", "discord": "(discord|o discord|disc)", "steam": "steam", "whatsapp": "(whatsapp|zap|whats|zapzap)",
    "telegram": "telegram", "vscode": "(vscode|vs code|visual studio code|code)", "bloco de notas": "(bloco de notas|notepad)",
    "calculadora": "calculadora", "word": "word", "excel": "excel", "powerpoint": "powerpoint", "obs": "(obs|obs studio)",
    "epic games": "(epic|epic games)", "roblox": "roblox", "minecraft": "minecraft", "netflix": "netflix",
    "edge": "(edge|microsoft edge)", "firefox": "firefox", "paint": "paint", "teams": "teams", "zoom": "zoom",
    "outlook": "outlook", "terminal": "(terminal|cmd|prompt de comando|powershell)", "photoshop": "photoshop",
    "capcut": "capcut", "premiere": "premiere", "valorant": "valorant", "league of legends": "(league of legends|lol)",
    "fortnite": "fortnite", "gta": "(gta|gta 5|gta v)", "camera": "(camera|webcam)", "notion": "notion",
    "pycharm": "pycharm", "blender": "blender", "vlc": "vlc", "audacity": "audacity", "figma": "figma",
}
for _app, _p in _APPS.items():
    intencao("open_app", {"app_name": _app},
             f"(abre|abra|abrir|inicia|inicie|iniciar|executa|executar|roda|rodar|liga|bota|carrega) [o|a] {_p}",
             f"(quero|preciso) (usar|abrir) [o|a] {_p}", f"{_p} (por favor|ai)", f"(entra|entrar) no {_p}")
    if _app not in ("calculadora", "camera", "terminal", "navegador"):
        intencao("computer_control", {"action": "close_app", "app_name": _app},
                 f"(fecha|feche|fechar|encerra|encerrar|sai do|sair do|mata|finaliza|finalizar) [o|a] {_p}",
                 f"(tira|desliga) [o|a] {_p}")

# ── navegador / youtube / vídeo ──
for _site, _url, _p in (("youtube", "https://www.youtube.com", "(youtube|yt)"), ("gmail", "https://mail.google.com", "(gmail|meu email|e-mail|email)"),
                         ("instagram", "https://www.instagram.com", "(instagram|insta)"), ("github", "https://github.com", "github"),
                         ("chatgpt", "https://chatgpt.com", "(chatgpt|chat gpt)"), ("google", "https://www.google.com", "google"),
                         ("twitch", "https://www.twitch.tv", "twitch"), ("tiktok", "https://www.tiktok.com", "tiktok"),
                         ("mercado livre", "https://www.mercadolivre.com.br", "mercado livre"), ("shopee", "https://shopee.com.br", "shopee"),
                         ("google drive", "https://drive.google.com", "(google drive|drive|meu drive)"),
                         ("twitter", "https://x.com", "(twitter|x)"), ("facebook", "https://www.facebook.com", "(facebook|face)"),
                         ("linkedin", "https://www.linkedin.com", "linkedin"), ("amazon", "https://www.amazon.com.br", "amazon"),
                         ("google maps", "https://maps.google.com", "(google maps|maps|mapa)")):
    intencao("browser_control", {"action": "go_to", "url": _url},
             f"(abre|abra|abrir|entra|entrar|acessa|acessar|vai|ir) [no|na|o|a|pro|pra] {_p}", f"(site|pagina) do {_p}")
intencao("youtube_video", {"action": "trending"}, "(o que|oque) (ta|esta) em alta no youtube", "(videos|tendencias) em alta [no youtube]",
         "trending do youtube", "o que ta bombando no youtube")
intencao("video_player", {"action": "stop"}, "(para|pare|parar|fecha|feche|tira|desliga) [o] video", "chega de video", "some com o video")
intencao("video_player", {"action": "mute"}, "(muta|silencia|tira o som d)o video", "video sem som")
intencao("video_player", {"action": "unmute"}, "(liga|ativa|coloca|bota|quero ouvir) o som do video", "(desmuta|desmutar) [o] video",
         "video com som")

# ── música ──
M = "musica"
intencao(M, {"action": "tocar"}, "(toca|toque|tocar|bota|coloca|poe|solta) (uma|um|alguma) (musica|som|musiquinha|cancao)",
         "(quero|vamos) ouvir (musica|um som)", "(solta|manda|bota) o som", "(volta|continua) a tocar")
intencao(M, {"action": "pausar"}, "(pausa|pause|pausar|para|pare|parar) [a] (musica|cancao|spotify|som)", "(da|de) pause [na musica]",
         "(segura|para) a musica ai")
intencao(M, {"action": "continuar"}, "(continua|continue|continuar|retoma|retomar|despausa|volta) [a] (musica|cancao|spotify)",
         "(da|de) play [na musica]", "pode voltar a musica")
intencao(M, {"action": "proxima"}, "(proxima|outra) (musica|faixa|cancao)", "(pula|pule|pular|passa|passe|troca|troque) [essa|a] (musica|faixa)",
         "(nao gostei dessa|pula essa|passa essa|proxima)", "(passa|pula|vai|manda) pra (proxima|a proxima)")
intencao(M, {"action": "anterior"}, "(musica|faixa) anterior", "(volta|voltar|volte) [a|uma] (musica|faixa)", "toca a anterior")
intencao(M, {"action": "tocando"}, "(que|qual) musica (e essa|ta tocando|esta tocando)", "(o que|oque) (ta|esta) tocando",
         "(qual o nome|nome) dessa musica", "quem canta essa")
intencao(M, {"action": "curtir"}, "(curte|curtir|curta) (essa|a) musica", "(gostei|amei) dessa musica", "salva essa musica")
intencao(M, {"action": "sugerir"}, "(sugere|sugira|recomenda|recomende|indica) (uma|alguma) musica", "o que eu ouco (agora|hoje)")
intencao(M, {"action": "player"}, "(abre|mostra|abrir) [o] player [de musica]", "(tela|janela) tocando agora")
intencao(M, {"action": "radio"}, "(toca|liga|bota|coloca) [uma|a] radio", "radio do meu gosto", "(liga|toca) o radio")
for _h, _p in (("focar", "(focar|concentrar|foco|trabalhar)"), ("treino", "(treino|treinar|academia|malhar)"), ("relaxar", "(relaxar|relaxante|calma)"),
               ("dormir", "(dormir|sono)"), ("festa", "(festa|animada|animar)"), ("estudar", "(estudar|estudo|estudos)"), ("triste", "(triste|tristeza|sofrencia)")):
    intencao(M, {"action": "humor", "pedido": _h}, f"(toca|bota|coloca|quero|poe) (musica|som|playlist|uma musica) (pra|para|de) {_p}",
             f"(musica|playlist|som) (pra|para|de) {_p}")

# ── tempo, dinheiro, briefing, hora ──
intencao("briefing_br", {"parte": "clima"},
         "(como|como que) (ta|esta|vai estar|vai ficar) o (tempo|clima) [hoje|amanha|la fora]", "(previsao do tempo|previsao) [de hoje|pra hoje]",
         "vai chover [hoje|amanha|mais tarde]", "(qual|que) (a temperatura|temperatura) [agora|hoje|la fora]", "(ta|esta) (fazendo frio|fazendo calor|calor|frio) [la fora]",
         "(preciso|levo) [de] guarda chuva", "(como|qual) (ta|esta) o clima")
intencao("briefing_br", {"parte": "cotacao"}, "(quanto|qual) (ta|esta|e|o valor do|a cotacao do) [o] (dolar|euro)",
         "cotacao do (dolar|euro) [hoje]", "(dolar|euro) (hoje|agora)", "(preco|valor) do (dolar|euro)")
intencao("briefing_br", {"parte": "tudo"}, "(me da|me de|quero|faz|faca) [o] (briefing|resumo do dia|resumo da manha)",
         "(briefing|resumo do dia|resumo matinal)", "(como|o que) (ta|esta) o (dia|mundo) hoje", "(novidades|noticias) de hoje")
intencao("estado_mundo", {"action": "agora"}, "(que|quais|qual) (horas|hora) (sao|e) [agora]", "(me fala|me diz|diz) a hora",
         "(que horas|horas) (sao|e)", "(sabe|tem) (que horas|as horas)")
intencao("estado_mundo", {"action": "perdi"}, "(o que|oque) eu perdi", "(teve|tem|chegou) (algum|alguma) (aviso|alerta|novidade)",
         "avisos (atrasados|guardados|pendentes)", "(me conta|conta) o que eu perdi")
intencao("alerta_cotacao", {"action": "cotacao", "ativo": "bitcoin"}, "(quanto|qual) (ta|esta|e) o (bitcoin|btc)", "(cotacao|preco|valor) do (bitcoin|btc)")
intencao("alerta_cotacao", {"action": "listar"}, "(quais|lista|mostra) [os|meus] alertas de cotacao", "meus alertas de (preco|cotacao)")

# ── PC: monitor, saúde, limpeza, downloads, modo jogo ──
MS = "monitor_sistema"
intencao(MS, {"action": "status"}, "(como|como que) (ta|esta|anda) [o|meu] " + _PC, "(status|estado|situacao) do " + _PC,
         "(uso|consumo) (de|da) (cpu|ram|memoria|processador)", "(quanto|qual) (de|o uso de) (cpu|ram|memoria) [ta usando|esta usando]",
         "(temperatura|temp) (do|da) (pc|cpu|processador|placa de video|gpu)", "(o pc|o computador) (ta|esta) (bem|ok|esquentando)")
intencao(MS, {"action": "pesando"}, "(o que|oque|quem) (ta|esta) (pesando|travando|deixando lento|deixando o pc lento|consumindo tudo)",
         "(por que|porque) [o|meu] " + _PC + " (ta|esta) (lento|travando|pesado)", "[o|meu] " + _PC + " (ta|esta) (lento|travando|pesado)",
         "(qual|que) programa (ta|esta) (pesando|travando|gastando memoria)")
intencao(MS, {"action": "internet"}, "(como|como que) (ta|esta) [a|minha] (internet|conexao|wifi|rede)", "(qual|qual e) [o] meu ip",
         "(to|estou|tou) (conectado|com internet|online)", "(tem|ta com) internet", "(qual|como ta) o ping")
intencao(MS, {"action": "velocidade"}, "(testa|teste|testar|mede|medir|faz um teste de) [a] velocidade [da internet|da rede]",
         "speed ?test", "(qual|quanto) (e|ta) a velocidade da (internet|rede)", "(teste|medidor) de velocidade")
intencao(MS, {"action": "discos"}, "(quanto|qual) (de )?espaco (livre|eu tenho|tenho|sobrou) [no|nos] [disco|hd|ssd]",
         "(espaco|armazenamento) (do|no) (disco|hd|ssd|pc)", "(o|meu) (disco|hd|ssd) (ta|esta) cheio")
intencao(MS, {"action": "top"}, "(mostra|lista|quais) [os] processos", "(tabela|lista) de processos", "programas (rodando|abertos) agora")
intencao(MS, {"action": "relatorio", "periodo": "hoje"}, "(como|como que) foi [o] " + _PC + " hoje", "relatorio do pc [de hoje]")
intencao(MS, {"action": "painel"}, "(abre|mostra|abrir) [o] (monitor|painel do monitor|painel de desempenho)", "monitor do sistema")
intencao("saude_pc", {"action": "verificar"}, "(como|como que) (ta|esta) a saude do " + _PC, "(saude|nota|check ?up|checkup) do " + _PC,
         "(faz|faca|roda) um (check ?up|checkup|diagnostico) [no|do] [pc|computador]", "(diagnostico|diagnostica) [o] " + _PC)
intencao("limpeza", {"action": "previa"}, "(limpa|limpe|limpar|faxina) [o] " + _PC, "(libera|liberar|libere) espaco [no disco|no pc]",
         "(limpa|limpar|apaga|apagar) [os] (arquivos temporarios|temporarios|lixo|cache)", "(limpeza|faxina) do (pc|sistema|computador)")
intencao("limpeza", {"action": "previa", "categorias": "lixeira"}, "(esvazia|esvaziar|esvazie|limpa|limpar) [a] lixeira")
intencao("downloads", {"action": "organizar"}, "(organiza|organize|organizar|arruma|arrumar) [a pasta] [de] downloads",
         "(downloads|pasta de downloads) (ta|esta) (uma bagunca|baguncada)")
intencao("downloads", {"action": "ultimo"}, "(abre|abrir|abra) [o] ultimo download", "(o que|oque) eu baixei por ultimo", "ultimo arquivo baixado")
intencao("downloads", {"action": "hoje"}, "(o que|oque) eu baixei hoje", "downloads de hoje")
intencao("downloads", {"action": "abrir_pasta"}, "(abre|abrir|abra|mostra) [a] pasta [de] downloads", "(meus downloads|pasta downloads)")
for _pasta, _p in (("documentos", "(documentos|meus documentos)"), ("imagens", "(imagens|fotos|minhas fotos)"),
                   ("videos", "(videos|meus videos)"), ("musicas", "(musicas|minhas musicas)")):
    intencao("controle_sistema", {"action": "abrir_pasta", "pasta": _pasta}, f"(abre|abrir|abra|mostra) [a] pasta [de|dos|das] {_p}")
intencao("controle_sistema", {"action": "recentes"}, "(arquivos|documentos) recentes", "(quais|o que) (arquivos )?eu abri por ultimo")
intencao("controle_sistema", {"action": "clipboard_ler"}, "(o que|oque) (tem|ta) na area de transferencia", "(le|leia|ler) [a] area de transferencia",
         "o que eu copiei")
intencao("controle_sistema", {"action": "plano_energia", "plano": "economia"}, "(modo|plano) (economia|economico) [de energia|de bateria]",
         "(economiza|economizar|poupa|poupar) (bateria|energia)")
intencao("controle_sistema", {"action": "plano_energia", "plano": "alto desempenho"}, "(modo|plano) (alto desempenho|desempenho maximo|performance)",
         "(desempenho maximo|maximo desempenho)")
intencao("controle_pc", {"action": "apps_abertos"}, "(quais|que) (programas|apps|aplicativos) (estao|tao|to) abertos", "(lista|mostra) [os] (programas|apps) abertos")
intencao("modo_jogo", {"action": "ligar"}, "(liga|ativa|ativar|entra no|coloca no|bota no) [o] modo (jogo|gamer|game|desempenho)",
         "(vou|bora|vamos) jogar", "modo (jogo|gamer|game)", "hora do (jogo|game)")
intencao("modo_jogo", {"action": "desligar"}, "(desliga|desativa|desativar|sai do|sair do) [o] modo (jogo|gamer|game|desempenho)",
         "(modo normal|parei de jogar|terminei de jogar|acabei de jogar)")
intencao("modo_jogo", {"action": "overlay", "ligar": "sim"}, "(mostra|liga|ativa) [o] (overlay|fps|contador de fps)")

# ── foco, tempo, sono ──
intencao("pomodoro", {"action": "iniciar"}, "(inicia|iniciar|comeca|comecar|liga|ativa|bota) [um|o] pomodoro", "pomodoro",
         "(vamos|bora|hora de) focar", "(modo|sessao de) foco", "(me ajuda a|quero) focar")
intencao("pomodoro", {"action": "pausar"}, "(pausa|pausar|pause) [o] pomodoro")
intencao("pomodoro", {"action": "retomar"}, "(retoma|retomar|continua|continuar|volta) [o] pomodoro")
intencao("pomodoro", {"action": "parar"}, "(para|parar|pare|encerra|cancela|desliga) [o] pomodoro", "(chega de|sai do modo) foco")
intencao("pomodoro", {"action": "status"}, "(quanto|quanto tempo) falta [do|no|pro] (pomodoro|foco)", "status do pomodoro")
intencao("pomodoro", {"action": "hoje"}, "(quantos|quanto) pomodoros [eu fiz] hoje", "pomodoros de hoje")
intencao("cronometros", {"action": "timers"}, "(quanto|quanto tempo) falta [no|do|pro] (timer|temporizador)", "(quais|meus|lista os) (timers|temporizadores)")
intencao("cronometros", {"action": "iniciar"}, "(inicia|iniciar|comeca|comecar|liga|dispara) [o] cronometro", "cronometro")
intencao("cronometros", {"action": "volta"}, "(marca|marcar) [uma] volta", "nova volta")
intencao("cronometros", {"action": "parar"}, "(para|parar|pare) [o] cronometro", "(quanto deu|quanto marcou) [o] cronometro")
MD = "modo_dormir"
intencao(MD, {"action": "dormir"}, "(vai|pode ir) dormir", "(dorme|dormir) [jarvis]", "(entra|liga|ativa) [o] modo (dormir|soneca|repouso)",
         "(descansa|descanse) [um pouco]", "modo (dormir|repouso)")
intencao(MD, {"action": "boa_noite"}, "(vou|to indo|tou indo|estou indo) (dormir|deitar|pra cama)", "boa noite vou (dormir|deitar)",
         "(modo noite|hora de dormir)", "(fui|vou) dormir")
intencao(MD, {"action": "sono"}, "(como|quanto) (foi o meu sono|eu dormi)", "(relatorio|diario) do sono", "(dormi|eu dormi) bem")
intencao(MD, {"action": "despertador"}, "(tem|qual) (despertador|alarme) (marcado|ligado)", "(meu|meus) (despertador|alarme)")
intencao(MD, {"action": "cochilo"}, "(quero|vou) (tirar um cochilo|cochilar)", "(cochilo|soneca rapida)")
for _som, _p in (("chuva", "(chuva|barulho de chuva)"), ("mar", "(mar|ondas|praia)"), ("ruido_branco", "(ruido branco|chiado)"),
                 ("ventilador", "ventilador"), ("lareira", "lareira"), ("floresta", "(floresta|natureza|passarinho)")):
    intencao(MD, {"action": "sons", "som": _som}, f"(toca|bota|coloca|liga|poe) [o] (som|barulho|barulhinho) de {_p}", f"som de {_p}")
intencao(MD, {"action": "sons", "som": "parar"}, "(para|desliga|tira) [o] (som|barulho) (de chuva|de mar|ambiente|de fundo)")
intencao(MD, {"action": "respirar"}, "(exercicio de|vamos fazer uma) respiracao", "(me ajuda a|quero) respirar", "respiracao guiada")

# ── casa ──
CI = "casa_inteligente"
for _ap, _p in (("luz do quarto", "luz do quarto"), ("luz da sala", "luz da sala"), ("luz da cozinha", "luz da cozinha"),
                ("tv", "(tv|televisao)"), ("ventilador", "ventilador"), ("luz", "(luz|lampada)")):
    intencao(CI, {"action": "ligar", "aparelho": _ap}, f"(liga|ligar|acende|acender|acenda|ligue) [a|o] {_p}")
    intencao(CI, {"action": "desligar", "aparelho": _ap}, f"(desliga|desligar|apaga|apagar|apague|desligue) [a|o] {_p}")
intencao(CI, {"action": "desligar", "aparelho": "tudo"}, "(desliga|apaga|apagar|desligar) (todas as luzes|as luzes) [da casa]")
intencao(CI, {"action": "ligar", "aparelho": "tudo"}, "(liga|acende|acender|ligar) (todas as luzes|as luzes) [da casa]")
intencao(CI, {"action": "listar"}, "(quais|lista|mostra) [os] (aparelhos|dispositivos) da casa", "casa inteligente")
intencao(CI, {"action": "status"}, "(o que|oque) (ta|esta) ligado (em casa|na casa)", "status da casa")

# ── listas, dinheiro, agenda, notas ──
intencao("lista_compras", {"action": "ver"}, "(o que|oque) (tem|falta) na [minha] lista [de compras|do mercado]",
         "(mostra|le|leia|ver) [a|minha] lista (de compras|do mercado)", "lista de compras", "o que eu preciso comprar")
intencao("lista_compras", {"action": "limpar"}, "(limpa|limpar|apaga|zera|esvazia) [a] lista (de compras|do mercado)")
intencao("lista_compras", {"action": "enviar"}, "(manda|envia|enviar|mandar) [a] lista (de compras|do mercado) [no whatsapp|pra mim]")
intencao("gastos", {"action": "resumo"}, "(quanto|quanto que) (eu )?gastei (esse mes|este mes|no mes|hoje|essa semana)",
         "(resumo|relatorio) (dos|de) gastos", "(meus gastos|minhas despesas) [do mes]")
intencao("gastos", {"action": "apagar_ultimo"}, "(apaga|desfaz|remove|cancela) [o] ultimo gasto")
intencao("agenda", {"action": "listar", "quando": "hoje"}, "(o que|oque) (eu )?tenho (hoje|pra hoje)", "(minha )?agenda (de|pra) hoje",
         "(compromissos|reunioes) (de|pra) hoje", "tenho (algum compromisso|alguma reuniao) hoje")
intencao("agenda", {"action": "listar", "quando": "amanha"}, "(o que|oque) (eu )?tenho (amanha|pra amanha)", "(minha )?agenda (de|pra) amanha",
         "(compromissos|reunioes) (de|pra) amanha")
intencao("agenda", {"action": "listar", "quando": "semana"}, "(minha )?agenda da semana", "(compromissos|reunioes) da semana", "o que tenho essa semana")
intencao("segundo_cerebro", {"action": "listar"}, "(o que|oque) tem no meu (segundo )?cerebro", "(mostra|lista) [as] (minhas )?notas", "minhas anotacoes")
intencao("ideias", {"action": "listar"}, "(quais|mostra|lista) [as] (minhas )?ideias", "caixinha de ideias", "(minhas ideias|ideias salvas)")
intencao("ideias", {"action": "revisar"}, "(revisa|revisar) [as] (minhas )?ideias", "ideias paradas")
intencao("diario", {"action": "entrevista"}, "(vamos|bora) (fazer|escrever) o diario", "(abre|comeca) o diario", "quero falar do meu dia")
intencao("diario", {"action": "listar"}, "(mostra|le|lista) [o] (meu )?diario", "ultimos dias do diario")
intencao("feriados", {"action": "proximo"}, "(qual|quando) (e )?o proximo feriado", "proximo feriado", "(tem|quando tem) feriado")
intencao("feriados", {"action": "emendas"}, "(quais|onde) (feriados )?(da pra|posso) emendar", "emendas de feriado")
intencao("feriados", {"action": "lista"}, "(lista|quais sao) [os] feriados [do ano|desse ano]", "feriados do ano")

# ── diversão ──
intencao("piadas", {"action": "contar"}, "(conta|conte|contar|manda|fala) (uma|outra|alguma) piada", "(me faz|me faca) rir", "piada",
         "(sabe|tem) (alguma )?piada")
intencao("piadas", {"action": "contar", "tipo": "dev"}, "(conta|manda|fala) (uma )?piada de (programador|programacao|dev)")
intencao("jogos", {"action": "abrir"}, "(abre|abrir|abra|mostra) [o] arcade", "(quero|vamos|bora) jogar (algo|alguma coisa|um jogo)", "(jogos|joguinhos) do jarvis")
for _j, _p in (("xadrez", "xadrez"), ("damas", "damas"), ("velha", "(jogo da velha|velha)"), ("2048", "2048"), ("cobrinha", "(cobrinha|snake)"),
               ("tetris", "(tetris|blocos)"), ("minas", "campo minado"), ("sudoku", "sudoku"), ("forca", "forca"), ("memoria", "jogo da memoria")):
    intencao("jogos", {"action": "abrir", "jogo": _j}, f"(abre|abrir|vamos jogar|bora jogar|quero jogar|joga) [um|o] {_p}", f"(jogar|partida de) {_p}")
intencao("quiz_geek", {"action": "pergunta"}, "(me faz|faz|faca|manda) uma pergunta [de quiz|geek]", "(quiz|quiz geek)", "(vamos|bora) (fazer um|jogar) quiz")
intencao("quiz_geek", {"action": "placar"}, "placar do quiz", "(quantas|quanto) eu acertei no quiz")
for _cat, _p in (("comida", "(o que|oque) eu (como|janto|almoco) hoje"), ("filme", "(que|qual) filme eu (vejo|assisto)"),
                 ("serie", "(que|qual) serie eu (vejo|assisto)"), ("jogo", "(que|qual) jogo eu jogo")):
    intencao("roleta", {"action": "sortear", "categoria": _cat}, _p, f"sorteia [um|uma] {_cat}", f"roleta de {_cat}")
intencao("humor", {"action": "status"}, "(como|como que) (voce|vc) (ta|esta) [hoje]", "(qual|como ta) (o )?seu humor [hoje]", "tudo bem com voce")
intencao("adivinha", {"action": "novo"}, "(vamos|bora) jogar adivinha", "(jogo do|joga o) adivinha", "adivinha quem")

# ── tela, sistema do JARVIS ──
intencao("tela_ao_vivo", {"action": "ligar"}, "(olha|ve|veja|assiste|acompanha) a minha tela (ao vivo|em tempo real)", "(liga|ativa) [a] tela ao vivo",
         "fica olhando (a )?minha tela")
intencao("tela_ao_vivo", {"action": "desligar"}, "(para|pare|desliga|chega) de olhar (a )?minha tela", "(desliga|desativa) [a] tela ao vivo")
intencao("acompanhar", {"action": "tela"}, "(o que|oque) (tem|ta|esta|aparece) na (minha )?tela", "(olha|ve|veja|da uma olhada) (na|a) (minha )?tela",
         "(o que|oque) (voce|vc) (ta|esta) vendo [na tela]", "(le|leia) (o que ta na )?(minha )?tela")
intencao("acompanhar", {"action": "camera"}, "(olha|ve|veja) (pela|na) (camera|webcam)", "(o que|oque) (voce|vc) ve na (camera|webcam)")
intencao("cerebro", {"action": "estado"}, "(o que|oque) (voce|vc) (ja )?aprendeu [comigo]", "(estado|status) do (seu )?cerebro", "(como|como ta) (o )?seu cerebro")
intencao("cerebro", {"action": "reflexos"}, "(quais|mostra) [os] (seus )?reflexos", "(quais|que) comandos (voce|vc) (faz|ja faz) sozinho")
intencao("app_celular", {"action": "instalar"}, "(instala|instalar|como instalo) [o] (app|aplicativo) [do jarvis] no (celular|telefone)", "jarvis no celular")
intencao("modos", {"action": "listar"}, "(quais|lista|mostra) [os] modos [que voce tem]", "(modos|lista de modos) [disponiveis]")
intencao("modos", {"action": "sair"}, "(sai|sair|desliga|desativa) [do|o] modo [atual]", "(modo normal|volta ao normal)")
for _modo, _p in (("estudo", "(estudo|estudar)"), ("loja", "loja"), ("programador", "(programador|programacao|codigo|dev)"),
                  ("reuniao", "reuniao"), ("treino", "(treino|academia)"), ("live", "(live|transmissao)"), ("cozinha", "cozinha"),
                  ("festa", "festa"), ("gravacao", "(gravacao|gravar)")):
    intencao("modos", {"action": "entrar", "modo": _modo}, f"(entra no|ativa o|liga o|coloca no|bota no|vamos pro|ativar) modo {_p}", f"modo {_p}")

# ─────────────────────────────────────────────────── padrões com lacuna ───
# Para quando o Gemini está fora: "abre <qualquer app>", "toca <qualquer música>", "volume <número>".
# re = expressão sobre o texto NORMALIZADO (core/cerebro.normalizar: minúsculo, sem acento, sem "jarvis").
# "{nome}" nos parâmetros é trocado pelo grupo com esse nome. "nao" = palavras que, se forem a lacuna, não valem.
PADROES = [
    {"re": r"^(?:abre|abra|abrir|inicia|inicie|iniciar|executa|executar)\s+(?:o |a |os |as )?(?:programa |app |aplicativo |jogo )?(?P<app>[a-z0-9][a-z0-9 .+-]{1,40})$",
     "f": "open_app", "a": {"app_name": "{app}"},
     "nao": ["isso", "ele", "ela", "tudo", "loja", "caixa", "conta", "lista"],
     "nao_contem": ["janela", "aba", "guia", "pasta", "arquivo", "site", "pagina", "porta", "planilha", "portao", "geladeira"]},
    {"re": r"^(?:toca|toque|tocar|bota pra tocar|coloca pra tocar|poe pra tocar|quero ouvir|solta)\s+(?:a musica |a cancao |musica |as musicas d[oae]s? |o album |a playlist |um pouco de |uma d[oae]s? )?(?P<pedido>[a-z0-9][a-z0-9 '&.-]{1,60})$",
     "f": "musica", "a": {"action": "tocar", "pedido": "{pedido}"},
     "nao": ["musica", "um som", "som", "uma musica", "alguma musica", "radio", "a radio", "o radio", "o telefone", "o alarme"]},
    {"re": r"^(?:coloca |bota |poe |deixa |muda |ajusta )?(?:o )?volume\s+(?:em |no |na |para |pra |pro |a |ao )?(?P<nivel>\d{1,3})(?:\s*%| por cento)?$",
     "f": "controle_audio_video", "a": {"action": "volume", "nivel": "{nivel}"}},
    {"re": r"^(?:coloca |bota |poe |deixa |muda |ajusta )?(?:o )?brilho\s+(?:em |no |na |para |pra |pro |a |ao )?(?P<nivel>\d{1,3})(?:\s*%| por cento)?$",
     "f": "controle_audio_video", "a": {"action": "brilho", "nivel": "{nivel}"}},
    {"re": r"^(?:(?:poe|bota|coloca|cria|marca|liga|inicia|faz|faca) )?(?:um |o )?(?:timer|temporizador|alarme rapido) (?:de |pra |para |por )?(?P<tempo>\d{1,3} ?(?:h|hora|horas|min|minuto|minutos|s|seg|segundo|segundos)(?: e \d{1,2} ?(?:min|minutos|s|segundos))?)(?: (?:pra|para|pro) (?:o |a )?(?P<nome>[a-z ]{2,30}))?$",
     "f": "cronometros", "a": {"action": "timer", "tempo": "{tempo}", "nome": "{nome}"}},
    {"re": r"^(?:como (?:ta|esta|vai estar|fica) )?(?:o )?(?:tempo|clima|previsao do tempo|previsao) (?:em|no|na|de|para|pra) (?P<city>[a-z][a-z ]{2,40})$",
     "f": "weather_report", "a": {"city": "{city}"},
     "nao": ["hoje", "amanha", "agora", "casa", "semana", "fim de semana"]},
    {"re": r"^(?:pesquisa|pesquise|pesquisar|procura na internet|procure na internet|busca na internet|busque na internet|joga no google|googla)\s+(?:sobre |por |o que e |quem e |quem foi )?(?P<query>.{3,120})$",
     "f": "web_search", "a": {"query": "{query}"}},
    {"re": r"^(?:anota|anote|anotar|guarda|guarde|salva|salve)(?: no meu (?:segundo )?cerebro| ai| isso)?(?: que|:)?\s+(?P<texto>.{4,200})$",
     "f": "segundo_cerebro", "a": {"action": "anotar", "texto": "{texto}"},
     "nao": ["essa musica", "esse prompt", "o arquivo", "isso", "o documento"]},
    {"re": r"^(?:adiciona|adicione|coloca|bota|poe|inclui|acrescenta) (?P<itens>.{2,80}?) na (?:minha )?lista(?: de compras| do mercado)?$",
     "f": "lista_compras", "a": {"action": "adicionar", "itens": "{itens}"}},
    {"re": r"^(?:gastei|paguei) (?:r )?(?P<valor>\d+(?:[.,]\d{1,2})?)(?: reais| conto| pila)? (?:no|na|em|com|de|do|da) (?P<descricao>.{2,60})$",
     "f": "gastos", "a": {"action": "registrar", "valor": "{valor}", "descricao": "{descricao}", "categoria": "outros"}},
    {"re": r"^(?:fecha|feche|fechar|encerra|encerrar)\s+(?:o |a )?(?P<app>[a-z0-9][a-z0-9 .+-]{1,30})$",
     "f": "computer_control", "a": {"action": "close_app", "app_name": "{app}"},
     "nao": ["janela", "aba", "guia", "tudo", "jarvis", "voce", "programa", "isso", "isto", "pc", "computador", "porta", "loja", "caixa",
             "conta", "olho", "olhos", "a boca", "boca", "o jarvis", "sistema", "windows", "explorer", "explorador"],
     "nao_contem": ["janela", "aba", "guia", "pasta", "arquivo", "porta", "portao", "jarvis", "sistema", "tudo", "todos", "todas"]},
]

# ─────────────────────────────────────────────────────────── prova ───
# Frases que NÃO estão nos padrões acima (jeitos diferentes de pedir), com a resposta certa (ferramenta, action).
PROVA = [
    ("da uma aumentada no volume", CS, "volume_up"), ("abaixa esse som pelo amor de deus", CS, "volume_down"),
    ("coloca no mudo agora", CS, "mute"), ("tira um print pra mim", CS, "screenshot"), ("tranca o computador", CS, "lock_screen"),
    ("abre o spotify pra mim", "open_app", None), ("inicia o discord agora", "open_app", None), ("fecha o steam", "computer_control", "close_app"),
    ("pula essa musica", "musica", "proxima"), ("pausa a musica rapidinho", "musica", "pausar"), ("que musica e essa que ta tocando", "musica", "tocando"),
    ("como ta o tempo hoje", "briefing_br", None), ("quanto ta o dolar hoje", "briefing_br", None), ("vai chover mais tarde", "briefing_br", None),
    ("por que meu notebook ta travando tanto", MS, "pesando"), ("como esta meu computador", MS, "status"), ("testa minha internet", MS, "velocidade"),
    ("quanto espaco sobrou no hd", MS, "discos"), ("faz uma faxina no pc", "limpeza", "previa"), ("organiza meus downloads", "downloads", "organizar"),
    ("ativa modo gamer", "modo_jogo", "ligar"), ("vou dormir agora", MD, None), ("to indo deitar", MD, "boa_noite"), ("comeca o pomodoro", "pomodoro", "iniciar"),
    ("acende a luz do quarto", CI, "ligar"), ("apaga todas as luzes", CI, "desligar"), ("o que tem na lista do mercado", "lista_compras", "ver"),
    ("quanto gastei esse mes", "gastos", "resumo"), ("o que eu tenho pra amanha", "agenda", "listar"), ("me conta uma piada", "piadas", "contar"),
    ("bora jogar xadrez", "jogos", "abrir"), ("que horas sao", "estado_mundo", "agora"), ("toca musica pra estudar", "musica", "humor"),
    ("abre o youtube", "browser_control", "go_to"), ("para o video", "video_player", "stop"), ("aumenta o brilho", CS, "brightness_up"),
    ("abre o gerenciador de tarefas", CS, "task_manager"), ("fecha essa aba", CS, "close_tab"), ("minimiza tudo", CS, "show_desktop"),
    ("qual o proximo feriado", "feriados", "proximo"), ("o que voce ta vendo na minha tela", "acompanhar", "tela"),
    ("liga o modo estudo", "modos", "entrar"), ("toca som de chuva", MD, "sons"), ("qual meu ip", MS, "internet"),
    ("joga o som pro fone", "controle_audio_video", "trocar_saida"), ("o que eu perdi", "estado_mundo", "perdi"),
    ("recarrega a pagina", CS, "refresh_page"), ("musica anterior", "musica", "anterior"), ("abre a pasta de documentos", "controle_sistema", "abrir_pasta"),
]
PROVA_PADROES = [
    ("abre o davinci resolve", "open_app", {"app_name": "davinci resolve"}), ("toca legiao urbana", "musica", {"action": "tocar", "pedido": "legiao urbana"}),
    ("volume em 40", "controle_audio_video", {"action": "volume", "nivel": "40"}),
    ("poe um timer de 10 minutos pro bolo", "cronometros", {"action": "timer", "tempo": "10 minutos", "nome": "bolo"}),
    ("tempo em sao paulo", "weather_report", {"city": "sao paulo"}),
    ("adiciona leite e pao na lista de compras", "lista_compras", {"action": "adicionar", "itens": "leite e pao"}),
    ("gastei 40 no almoco", "gastos", {"action": "registrar", "valor": "40", "descricao": "almoco", "categoria": "outros"}),
]


# ─────────────────────────────────────────────────────────── expansão ───
def expandir(padrao: str) -> list[str]:
    """'(a|b) [c] d' → ['a d', 'a c d', 'b d', 'b c d']. Aceita grupos aninhados. Pura."""
    padrao = re.sub(r"\[([^\[\]]*)\]", r"(\1|)", padrao)
    while "[" in padrao:
        padrao = re.sub(r"\[([^\[\]]*)\]", r"(\1|)", padrao)

    def _exp(s: str) -> list[str]:
        i = s.find("(")
        if i < 0:
            return [s]
        prof, j = 0, i
        for j in range(i, len(s)):
            prof += {"(": 1, ")": -1}.get(s[j], 0)
            if prof == 0:
                break
        dentro, partes, prof, ini = s[i + 1:j], [], 0, 0
        for k, ch in enumerate(dentro):
            prof += {"(": 1, ")": -1}.get(ch, 0)
            if ch == "|" and prof == 0:
                partes.append(dentro[ini:k])
                ini = k + 1
        partes.append(dentro[ini:])
        out = []
        for p in partes:
            for resto in _exp(s[j + 1:]):
                for meio in _exp(p):
                    out.append(s[:i] + meio + resto)
        return out

    return [" ".join(x.replace(" ?", " ").split()) for x in _exp(padrao.replace("?", ""))]


def gerar(semente: int = 39) -> tuple[list[dict], list[str]]:
    """As frases de treino [{t, k, f, a}] e os avisos (ambiguidades)."""
    from core.cerebro import chave
    rnd = random.Random(semente)
    por_chave: dict[str, dict] = {}
    conflitos: dict[str, set] = {}
    for f, a, padroes in I:
        frases = sorted({x for p in padroes for x in expandir(p) if x.strip()})
        if len(frases) > MAX_POR_INTENCAO:
            frases = sorted(rnd.sample(frases, MAX_POR_INTENCAO))
        for t in frases:
            k = chave(t)
            if not k:
                continue
            alvo = (f, json.dumps(a, sort_keys=True))
            if k in por_chave and (por_chave[k]["f"], json.dumps(por_chave[k]["a"], sort_keys=True)) != alvo:
                conflitos.setdefault(k, {(por_chave[k]["f"], json.dumps(por_chave[k]["a"], sort_keys=True))}).add(alvo)
                continue
            por_chave.setdefault(k, {"t": t, "k": k, "f": f, "a": a})
    for k in conflitos:
        por_chave.pop(k, None)
    avisos = [f"ambíguo, fora do treino: '{k}' → " + " | ".join(sorted(f"{f} {a}" for f, a in v)) for k, v in sorted(conflitos.items())]
    return list(por_chave.values()), avisos


def validar(exemplos: list[dict]) -> list[str]:
    """Confere se cada ferramenta e cada action existem no código do JARVIS (não inventa ferramenta)."""
    fontes = {}
    for pasta in ("actions", "plugins"):
        for arq in (RAIZ / pasta).glob("*.py"):
            txt = arq.read_text(encoding="utf-8", errors="replace")
            for nome in re.findall(r"""(?:"name"\s*:\s*|\bP\(\s*)"([a-z_0-9]+)\"""", txt):
                fontes.setdefault(nome, "")
                fontes[nome] += txt
    main = (RAIZ / "main.py").read_text(encoding="utf-8", errors="replace")
    erros = []
    for f in sorted({e["f"] for e in exemplos} | {p["f"] for p in PADROES}):
        if f not in fontes and f'"name": "{f}"' not in main:
            erros.append(f"ferramenta não existe: {f}")
    for e in exemplos + [{"f": p["f"], "a": p["a"]} for p in PADROES]:
        acao = e["a"].get("action")
        if acao and e["f"] in fontes and acao not in fontes[e["f"]]:
            erros.append(f"action '{acao}' não aparece em {e['f']}")
    return sorted(set(erros))


def montar(exemplos: list[dict]) -> dict:
    return {"versao": VERSAO, "gerado": time.strftime("%Y-%m-%d"), "exemplos": [{"k": e["k"], "f": e["f"], "a": e["a"]} for e in exemplos],
            "padroes": PADROES}


def prova(base: dict) -> tuple[float, list[str]]:
    """Mede o cérebro com a base nova, sem nada aprendido do usuário, nas frases da PROVA (que ele nunca viu)."""
    from core import cerebro as C
    erros, certos = [], 0
    with C.base_temporaria(base):
        for frase, f, acao in PROVA:
            r = C.entender(frase, sem_ia=True)
            ok = r["ferramenta"] == f and (acao is None or (r["args"] or {}).get("action") == acao)
            certos += ok
            if not ok:
                erros.append(f"  ✗ '{frase}' → {r['ferramenta']} {r['args']} (esperado {f} {acao or ''}) [{r['motivo']}]")
        for frase, f, args in PROVA_PADROES:
            r = C.entender(frase, sem_ia=True)
            ok = r["ferramenta"] == f and r["args"] == args and r["reflexo"]
            certos += ok
            if not ok:
                erros.append(f"  ✗ '{frase}' → {r['ferramenta']} {r['args']} reflexo={r['reflexo']} (esperado {f} {args})")
    return certos / (len(PROVA) + len(PROVA_PADROES)), erros


def main(argv: list[str]) -> int:
    exemplos, avisos = gerar()
    erros = validar(exemplos)
    print(f"Intenções: {len(I)} · frases de treino: {len(exemplos)} · padrões com lacuna: {len(PADROES)} · "
          f"ferramentas: {len({e['f'] for e in exemplos})}")
    for a in avisos[:30]:
        print("  aviso:", a)
    if erros:
        print("ERROS:\n  " + "\n  ".join(erros))
        return 2
    base = montar(exemplos)
    nota, falhas = prova(base)
    print(f"Prova (frases que ele nunca viu): {nota:.0%} de acerto")
    for x in falhas:
        print(x)
    if nota < NOTA_MINIMA:
        print(f"Nota abaixo de {NOTA_MINIMA:.0%}: o arquivo NÃO foi gravado.")
        return 1
    if "--prova" not in argv:
        SAIDA.write_text(json.dumps(base, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Gravado: {SAIDA.relative_to(RAIZ)} ({SAIDA.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
