"""
Guardião de decisões — o avaliador de risco central (ideia 12, fork PT-BR 1.4).

Antes de uma ação importante, avalia quatro coisas e decide:

    risco          0 nenhum · 1 baixo · 2 médio · 3 alto
    reversível     dá para desfazer? (o core/undo.py ou a própria ação)
    impacto        o que muda: nada, uma configuração, arquivos, o sistema todo
    permissão      precisa de administrador?

    decisão:  "automático"  risco ≤ 1 e reversível
              "confirmar"   risco 2, ou irreversível, ou precisa de administrador
              "bloquear"    toca em algo protegido (processos/pastas do sistema)

As regras ficam em três lugares, nesta ordem de prioridade:
    1. config/guardiao.json — as SUAS regras ("sempre perguntar antes de X",
       "pode fazer Y sozinho"), criadas por voz ou à mão;
    2. o catálogo abaixo, ferramenta por ferramenta;
    3. uma heurística por palavras (apagar, desligar, instalar, formatar…)
       para o que não está no catálogo.

Quem usa: habilidades combináveis (cada passo de uma cadeia), criador de
ferramentas (antes de instalar), laboratório, simulador e o conselho de agentes.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import asdict, dataclass

from plugins._comum import CONFIG, gravar_json, ler_json

ARQ_POLITICA = CONFIG / "guardiao.json"


@dataclass
class Avaliacao:
    acao: str
    risco: int
    reversivel: bool
    impacto: str
    admin: bool
    decisao: str
    motivos: list

    def texto(self) -> str:
        nivel = ("nenhum", "baixo", "médio", "alto")[max(0, min(3, self.risco))]
        d = {"automático": "posso fazer sozinho", "confirmar": "preciso da sua confirmação",
             "bloquear": "não vou fazer"}[self.decisao]
        partes = [f"{self.acao}: risco {nivel}, {'reversível' if self.reversivel else 'IRREVERSÍVEL'}, "
                  f"impacto em {self.impacto}" + (", precisa de administrador" if self.admin else "")
                  + f" — {d}."]
        if self.motivos:
            partes.append("Motivo: " + "; ".join(self.motivos) + ".")
        return " ".join(partes)

    def dict(self) -> dict:
        return asdict(self)


# (ferramenta, ação) → (risco, reversível, impacto, admin). ação "*" vale para todas.
CATALOGO: dict[tuple[str, str], tuple[int, bool, str, bool]] = {
    ("controle_pc", "desligar"): (2, False, "o sistema todo", False),
    ("controle_pc", "reiniciar"): (2, False, "o sistema todo", False),
    ("controle_pc", "sair"): (2, False, "a sessão", False),
    ("controle_pc", "hibernar"): (1, True, "a sessão", False),
    ("controle_pc", "suspender"): (1, True, "a sessão", False),
    ("controle_pc", "bloquear"): (0, True, "a sessão", False),
    ("controle_pc", "agendar"): (2, True, "o sistema todo", False),
    ("controle_pc", "fechar"): (1, False, "um programa", False),
    ("controle_pc", "fechar_janela"): (1, False, "um programa", False),
    ("controle_pc", "abrir"): (0, True, "nada", False),
    ("controle_pc", "*"): (0, True, "uma janela", False),
    ("controle_audio_video", "*"): (0, True, "uma configuração", False),
    ("controle_audio_video", "resolucao"): (1, True, "a tela", False),
    ("controle_sistema", "servico_parar"): (2, True, "o sistema todo", True),
    ("controle_sistema", "servico_iniciar"): (1, True, "o sistema todo", True),
    ("controle_sistema", "inicializacao_desativar"): (1, True, "uma configuração", False),
    ("controle_sistema", "wifi"): (2, True, "a conexão", False),
    ("controle_sistema", "modo_aviao"): (2, True, "a conexão", False),
    ("controle_sistema", "renovar_ip"): (1, True, "a conexão", True),
    ("controle_sistema", "plano_energia"): (0, True, "uma configuração", False),
    ("controle_sistema", "*"): (0, True, "nada", False),
    ("limpeza", "*"): (2, False, "arquivos", False),
    ("downloads", "organizar"): (1, True, "arquivos", False),
    ("downloads", "*"): (0, True, "nada", False),
    ("monitor_sistema", "processo"): (2, False, "um programa", False),
    ("monitor_sistema", "*"): (0, True, "nada", False),
    ("modo_jogo", "*"): (1, True, "programas e configurações", False),
    ("macros", "rodar"): (2, False, "o que a macro fizer", False),
    ("macros", "apagar"): (1, False, "arquivos", False),
    ("macros", "*"): (0, True, "nada", False),
    ("agendador", "*"): (1, True, "uma configuração", False),
    ("file_controller", "*"): (2, True, "arquivos", False),
    ("computer_settings", "*"): (1, True, "uma configuração", False),
    ("computer_control", "*"): (1, False, "o que estiver na tela", False),
    ("send_message", "*"): (2, False, "uma mensagem enviada", False),
    ("criador_ferramentas", "instalar"): (2, True, "o próprio JARVIS", False),
    ("criador_ferramentas", "remover"): (1, True, "o próprio JARVIS", False),
    ("criador_ferramentas", "*"): (0, True, "nada (fica pendente até você aprovar)", False),
    ("laboratorio", "*"): (0, True, "uma cópia isolada", False),
    # 1.4: habilidades internas (cada cadeia é avaliada passo a passo)
    ("habilidades", "*"): (0, True, "a cadeia (cada passo é avaliado)", False),
    ("buscar_arquivos", "*"): (0, True, "nada", False),
    ("arquivos_recentes", "*"): (0, True, "nada", False),
    ("ler_arquivos", "*"): (0, True, "nada", False),
    ("resumir", "*"): (0, True, "nada", False),
    ("gerar_relatorio", "*"): (0, True, "um arquivo novo", False),
    ("salvar_arquivo", "*"): (1, True, "um arquivo novo em Documentos/JARVIS", False),
    ("abrir", "*"): (0, True, "nada", False),
    ("manual", "*"): (0, True, "nada (você faz)", False),
    # 1.4: ferramentas novas
    ("memoria_contrafactual", "aplicar"): (1, True, "um protocolo ou apelido", False),
    ("memoria_contrafactual", "*"): (0, True, "nada", False),
    ("oportunidades", "aceitar"): (1, True, "depende da sugestão", False),
    ("oportunidades", "*"): (0, True, "nada", False),
    ("prioridades", "*"): (0, True, "a sua lista de tarefas", False),
    ("memoria_inteligente", "*"): (0, True, "a memória do JARVIS", False),
    ("casa_inteligente", "importar"): (0, True, "a lista de aparelhos", False),
    ("casa_inteligente", "*"): (1, True, "aparelhos da casa", False),
    ("personas", "trocar"): (1, True, "a voz e o nome do assistente", False),
    ("personas", "*"): (0, True, "nada", False),
    ("capacete", "nova_chave"): (1, True, "o acesso do capacete", False),
    ("capacete", "*"): (0, True, "nada", False),
    ("cristal_fotos", "*"): (0, True, "arquivos novos ao lado das fotos", False),
    ("cristal_video", "*"): (0, True, "um vídeo novo", False),
    ("cristal_calendario", "*"): (0, True, "nada", False),
    ("cristal_malhas", "*"): (0, True, "o estoque e as vendas da loja", False),
    ("vigia_preco", "*"): (0, True, "a lista de vigias", False),
    ("legenda_ao_vivo", "*"): (0, True, "nada", False),
    ("olha_isso", "*"): (0, True, "nada", False),
    ("boot_cinematico", "*"): (0, True, "nada", False),
    ("notificacoes", "*"): (0, True, "nada", False),
    ("conselho", "*"): (0, True, "nada", False),
    ("mapa_dependencias", "*"): (0, True, "nada", False),
    ("hipoteses", "*"): (0, True, "nada", False),
    ("simulador", "*"): (0, True, "nada (só simula)", False),
    ("gemeo_digital", "*"): (0, True, "nada", False),
    ("radar_anomalias", "*"): (0, True, "nada", False),
    ("reconstrucao", "*"): (0, True, "nada", False),
    ("linha_do_tempo", "*"): (0, True, "nada", False),
    ("quando_voltar", "*"): (0, True, "nada", False),
    ("guardiao_decisoes", "*"): (0, True, "as regras do guardião", False),
    # 1.5: verificação e ferramentas novas
    ("verificacao", "desligar"): (2, True, "a segurança do JARVIS", False),
    ("verificacao", "nivel"): (1, True, "a segurança do JARVIS", False),
    ("verificacao", "*"): (0, True, "nada", False),
    ("voz_dono", "esquecer"): (1, False, "o seu perfil de voz", False),
    ("voz_dono", "*"): (0, True, "o seu perfil de voz", False),
    ("chave_celular", "definir"): (1, True, "a segurança do JARVIS", False),
    ("chave_celular", "remover"): (1, True, "a segurança do JARVIS", False),
    ("chave_celular", "*"): (0, True, "nada", False),
    ("sentinela", "desativar"): (1, True, "a vigilância do PC", False),
    ("sentinela", "*"): (0, True, "a câmera (vigia)", False),
    ("ouvido_ambiente", "*"): (0, True, "nada (só ouve)", False),
    ("ligacao", "ligar"): (1, False, "uma ligação para o seu celular", False),
    ("ligacao", "testar"): (1, False, "uma ligação para o seu celular", False),
    ("ligacao", "atender"): (1, True, "o número da Twilio passa a atender (secretária; você com PIN)", False),   # 2.3
    ("ligacao", "*"): (0, True, "nada", False),
    ("servidores", "*"): (0, True, "a lista de servidores", False),
    ("geofence", "protocolo"): (1, True, "o que o protocolo fizer quando você chegar", False),
    ("geofence", "*"): (0, True, "nada", False),
    ("habitos", "*"): (0, True, "abre programas que você já usa", False),
    ("memoria_tela", "apagar"): (1, False, "o histórico da tela", False),
    ("memoria_tela", "*"): (0, True, "o histórico da tela", False),
    ("demonstracao", "repetir"): (2, False, "o que a tarefa gravada fizer", False),
    ("demonstracao", "apagar"): (1, False, "uma tarefa gravada", False),
    ("demonstracao", "*"): (0, True, "nada", False),
    ("modo_professor", "*"): (0, True, "nada", False),
    ("ditado_codigo", "*"): (0, True, "um arquivo novo em Documentos/JARVIS/codigo", False),
    ("postura", "*"): (0, True, "nada", False),
    ("humor", "*"): (0, True, "nada", False),
    ("companheiro_jogo", "*"): (0, True, "nada", False),
    ("segunda_opiniao", "*"): (0, True, "nada", False),
    ("auto_melhoria", "aplicar"): (2, True, "o próprio JARVIS (com cópia e desfazer)", False),
    ("auto_melhoria", "*"): (0, True, "nada (fica pendente até você aprovar)", False),
    # 1.6: aparelhos da rede e ferramentas novas
    ("aparelhos", "rodar"): (2, False, "outro PC ou o celular (comando de terminal)", False),
    ("aparelhos", "desligar"): (1, True, "um aparelho da casa", False),
    ("aparelhos", "reiniciar"): (1, True, "um PC da casa", False),
    ("aparelhos", "*"): (1, True, "aparelhos da casa", False),
    ("acesso_remoto", "ligar"): (1, True, "o painel fica acessível pela internet (com pareamento)", False),   # 1.8
    ("acesso_remoto", "*"): (0, True, "só o acesso remoto", False),
    ("whatsapp_jarvis", "*"): (1, True, "a conversa do WhatsApp do JARVIS", False),
    ("snapshots", "voltar"): (1, True, "os arquivos do projeto (salva antes; dá para desfazer)", False),   # 1.9
    ("snapshots", "*"): (0, True, "só cópias de segurança", False),
    ("ditado", "*"): (1, True, "o texto no app aberto (Ctrl+Z desfaz)", False),
    ("testes_vivos", "*"): (0, True, "só roda os testes do projeto", False),
    ("modo_aula", "*"): (0, True, "uma gravação nova em Documentos", False),
    ("gestos", "*"): (0, True, "nada (usa a câmera)", False),
    ("pausa_ausente", "*"): (0, True, "nada (usa a câmera)", False),
    ("musica", "*"): (0, True, "só a música tocando", False),                                    # 2.0
    ("mensageiros", "enviar"): (1, False, "uma mensagem para você mesmo", False),
    ("mensageiros", "ligar_celular"): (1, False, "uma ligação para o seu celular (Twilio cobra)", False),
    ("mensageiros", "*"): (0, True, "os bots do Telegram/Discord", False),
    ("companheiro", "ligar_celular"): (1, False, "uma ligação para o seu celular (Twilio cobra)", False),
    ("companheiro", "*"): (0, True, "só as ofertas do companheiro", False),
    ("tela_ao_vivo", "*"): (1, True, "a sua tela é enviada ao Gemini enquanto estiver ligada", False),          # 2.2
    ("whatsapp_conversas", "mandar"): (1, False, "uma mensagem no SEU nome para um contato", False),          # 2.3
    ("whatsapp_conversas", "ausente"): (1, True, "o JARVIS responde suas conversas como seu assistente", False),
    ("whatsapp_conversas", "liberar"): (1, True, "resposta automática para um contato", False),
    ("whatsapp_conversas", "secretaria"): (1, True, "ligações do WhatsApp são recusadas e viram recado", False),
    ("whatsapp_conversas", "pessoal"): (1, True, "o JARVIS lê as mensagens que chegam para você", False),
    ("whatsapp_conversas", "recados"): (0, True, "a lista de recados", False),
    ("whatsapp_conversas", "*"): (0, True, "nada (só lê)", False),
    ("estado_mundo", "*"): (0, True, "nada (só lê)", False),                                                  # 2.4
    ("evolucao", "zerar"): (1, False, "o que o JARVIS aprendeu sobre o seu jeito", False),
    ("evolucao", "*"): (0, True, "o jeito de responder", False),
    ("memoria_grafo", "*"): (0, True, "a memória em grafo", False),
    ("missoes", "criar"): (1, True, "uma tarefa longa em segundo plano (fotos são copiadas; mover pede confirmação)", False),
    ("missoes", "desfazer"): (1, True, "fotos voltam para onde estavam", False),
    ("missoes", "*"): (0, True, "as missões", False),
    ("diario", "*"): (0, True, "o diário", False),
    ("estudio_rap", "*"): (0, True, "um arquivo novo em Música/JARVIS/takes", False),
    ("seguranca_adaptativa", "normal"): (1, True, "um tipo de aviso de segurança deixa de aparecer", False),
    ("seguranca_adaptativa", "pausar"): (1, True, "o vigia de segurança fica parado", False),
    ("seguranca_adaptativa", "*"): (0, True, "nada (só lê)", False),
    ("interrupcao", "*"): (0, True, "o jeito de interromper o JARVIS", False),                              # 2.4.1
    ("contas", "email"): (0, True, "nada (só lê os e-mails com boleto)", False),                             # 2.5
    ("contas", "apagar"): (1, False, "uma conta sai da lista", False),
    ("contas", "*"): (0, True, "a lista de contas", False),
    ("rastreio", "remover"): (0, True, "uma encomenda sai da lista (dá para desfazer)", False),
    ("rastreio", "*"): (0, True, "a lista de encomendas", False),
    ("garantias", "apagar"): (1, False, "uma garantia sai da lista", False),
    ("garantias", "*"): (0, True, "as garantias e os manuais", False),
    ("chuva", "*"): (0, True, "nada (só olha o tempo)", False),
    ("ideias", "*"): (0, True, "a caixinha de ideias", False),
    ("objetos_quarto", "ligar"): (1, True, "a câmera do quarto olha o cômodo de tempos em tempos", False),
    ("objetos_quarto", "*"): (0, True, "nada (usa a câmera)", False),
    ("plantas", "*"): (0, True, "os sensores das plantas", False),
    ("painel_led", "*"): (0, True, "o painel de LED", False),
    ("luva_repulsor", "testar"): (0, True, "faz a ação do gesto agora (ex.: fechar a janela da frente)", False),
    ("luva_repulsor", "*"): (0, True, "a luva", False),
    ("conversa_grupo", "*"): (0, True, "as vozes conhecidas", False),
    ("avatar_live", "*"): (0, True, "o avatar da live", False),
    ("holograma_mao", "*"): (0, True, "nada (usa a câmera)", False),
    ("interprete", "*"): (0, True, "o microfone fica com o intérprete enquanto ligado", False),
    ("vitrine", "*"): (0, True, "nada (só a apresentação; o microfone pausa enquanto ela roda)", False),     # 2.6
    ("jarvis_friday", "ultron"): (1, True, "a voz e o jeito do JARVIS até 'volta ao normal' (reconecta)", False),  # 2.7
    ("jarvis_friday", "*"): (0, True, "nada (uma cena no palco; o microfone pausa enquanto ela roda)", False),
    ("cinema", "sessao"): (1, True, "minimiza as janelas, não perturbe e brilho até 'acabou o filme'", False),
    ("cinema", "intervalo"): (0, True, "pausa o player e dá play no fim", False),
    ("cinema", "*"): (0, True, "o seu catálogo de filmes", False),
    ("radionovela", "*"): (0, True, "nada (uma cena no palco)", False),
    ("talk_show", "*"): (1, True, "grava o microfone e o som do PC até 'encerra o programa'", False),
    ("neste_dia", "*"): (0, True, "nada (só lê)", False),
    ("campanha_heroi", "*"): (0, True, "nada (só lê o registro de uso)", False),
    ("modo_dormir", "boa_noite"): (1, True, "não perturbe, luzes, som e tela até de manhã (e o PC, se pedir)",
                                   False),                                                            # 2.8
    ("modo_dormir", "*"): (0, True, "nada (o JARVIS só para de ouvir até acordar)", False),
    ("por_que_fechou", "*"): (0, True, "nada (só lê o registro de erros)", False),                    # 2.8.1
    ("segundo_cerebro", "*"): (0, True, "guarda/lê as suas notas no PC (e no cofre do Obsidian)", False),   # 2.9
    ("biblioteca_prompts", "*"): (0, True, "guarda/lê os seus prompts no PC", False),                 # 2.9
    ("explica_crianca", "*"): (0, True, "nada (só reescreve a explicação)", False),                   # 2.10
    ("coach_decisao", "*"): (0, True, "guarda/lê as suas decisões no PC", False),                     # 2.10
    ("procrastinacao", "*"): (0, True, "nada (só olha qual janela está na frente, como a linha do tempo)", False),
    # 2.11
    ("renomear_fotos", "renomear"): (1, True, "renomeia fotos de uma pasta (não apaga)", False),
    ("renomear_fotos", "*"): (0, True, "nada (só sugere nomes)", False),
    ("organizador_abas", "*"): (0, True, "abre/guarda links de navegador", False),
    ("modo_apresentacao", "*"): (0, True, "não perturbe, tela acesa e teclas de slide", False),
    ("assistente_viagem", "*"): (0, True, "nada (lista, fuso, roteiro)", False),
    ("clone_estudo", "*"): (0, True, "guarda/lê o seu desempenho nos estudos", False),
    ("modo_faxina", "limpar"): (2, False, "apaga temporários, lixeira, recentes e cache/histórico do navegador", True),
    ("modo_faxina", "*"): (0, True, "nada (só mostra o que daria pra limpar)", False),
    ("palpite_humor", "*"): (0, True, "nada (horário e tempo de tela)", False),
    ("preencher_form", "*"): (0, True, "digita os seus dados no campo em foco (guardados no PC)", False),
    ("acompanhar", "*"): (0, True, "tira uma foto da tela/câmera na hora para te ajudar (não salva)", False),
    # 2.13
    ("porteiro_voz", "desligar"): (1, True, "deixa qualquer pessoa falar com o JARVIS (desliga o porteiro)", False),
    ("porteiro_voz", "*"): (0, True, "nada (só decide com quem o JARVIS fala)", False),
    ("vigia_codigo", "*"): (0, True, "olha a sua tela de código enquanto vigia (não salva) e fala os erros", False),
    ("guarda_vps", "bloquear"): (2, True, "o firewall do servidor", False),
    ("guarda_vps", "*"): (0, True, "nada (só lê o registro)", False),
    ("documentacao", "docstrings"): (1, True, "um arquivo de código (com cópia e desfazer)", False),
    ("documentacao", "*"): (0, True, "um README novo", False),
    ("gerador_testes", "*"): (0, True, "um arquivo de teste novo", False),
    ("gerador_projetos", "*"): (0, True, "uma pasta nova em Documentos/JARVIS", False),
    ("ata_chamada", "*"): (1, True, "grava o áudio da chamada", False),
    ("modo_convidado", "*"): (0, True, "o acesso das visitas", False),
    ("turno_noite", "*"): (0, True, "nada (testa e confere)", False),
    ("modo_carro", "*"): (0, True, "nada", False),
    ("cuidador", "*"): (0, True, "a rotina de cuidados", False),
    ("capsula_tempo", "*"): (0, True, "as cápsulas do tempo", False),
    ("aniversarios", "*"): (0, True, "a lista de aniversários", False),
    ("gamificacao", "*"): (0, True, "nada", False),
    ("thumbnails", "*"): (0, True, "uma imagem nova", False),
    ("gerador_beats", "*"): (0, True, "um áudio novo", False),
    ("jogos", "*"): (0, True, "só o placar dos jogos", False),                 # 1.7
    ("xadrez", "*"): (0, True, "só a partida salva", False),
    # só consultam: seguras
    ("web_search", "*"): (0, True, "nada", False),
    ("weather_report", "*"): (0, True, "nada", False),
    ("screen_process", "*"): (0, True, "nada", False),
    ("youtube_video", "*"): (0, True, "nada", False),
    ("flight_finder", "*"): (0, True, "nada", False),
    ("file_processor", "*"): (0, True, "nada", False),
    ("briefing_br", "*"): (0, True, "nada", False),
    ("saude_pc", "*"): (0, True, "nada", False),
    ("assistente_rede", "*"): (0, True, "nada", False),
    ("open_app", "*"): (0, True, "nada", False),
}

# Leitura e consulta: sempre seguras.
_SO_LEITURA = {"status", "listar", "ver", "consultar", "buscar", "relatorio", "verificar", "previa",
               "pesando", "top", "internet", "discos", "eventos", "hoje", "estado", "prever",
               "explicar", "mapa", "impacto", "historico", "linha_do_tempo", "sugestoes"}

_PALAVRAS = [  # (regex, risco, reversível, impacto, admin, motivo)
    (r"\bformat", 3, False, "o disco", True, "formatar apaga tudo"),
    (r"\b(apag|delet|exclu|remov|limp)", 2, False, "arquivos", False, "apaga coisas"),
    (r"\b(deslig|reinici|shutdown|reboot|logoff)", 2, False, "o sistema todo", False,
     "fecha todos os programas"),
    (r"\b(instal|desinstal|uninstall)", 2, True, "o sistema", True, "instala/remove programas"),
    (r"\b(regist|regedit|hkey_)", 3, False, "o registro do Windows", True, "mexe no registro"),
    (r"\b(envi|mand|post|public)", 2, False, "algo fora do PC", False, "não dá para desenviar"),
    (r"\b(mov|renome|sobrescrev|substitu)", 1, True, "arquivos", False, "muda arquivos de lugar"),
    (r"\b(mat|finaliz|kill|encerr)", 2, False, "um programa", False, "o que não foi salvo se perde"),
]

_PASTAS_PROTEGIDAS = [p.lower() for p in (
    os.environ.get("SystemRoot", r"C:\Windows"), r"C:\Program Files", r"C:\Program Files (x86)",
    r"C:\ProgramData", "/bin", "/sbin", "/usr", "/etc", "/boot", "/System", "/Library") if p]


def _dobrar(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


def politica() -> dict:
    p = ler_json(ARQ_POLITICA, None)
    return p if isinstance(p, dict) else {"sempre_perguntar": [], "pode_sozinho": [], "nunca": []}


def definir_regra(tipo: str, termo: str) -> str:
    tipo = {"perguntar": "sempre_perguntar", "sozinho": "pode_sozinho", "nunca": "nunca"}.get(tipo, tipo)
    if tipo not in ("sempre_perguntar", "pode_sozinho", "nunca") or not termo.strip():
        return "Regra inválida."
    p = politica()
    for k in ("sempre_perguntar", "pode_sozinho", "nunca"):
        p.setdefault(k, [])
        if termo in p[k]:
            p[k].remove(termo)
    p[tipo].append(termo.strip())
    gravar_json(ARQ_POLITICA, p)
    nomes = {"sempre_perguntar": "vou sempre perguntar antes de",
             "pode_sozinho": "posso fazer sozinho", "nunca": "nunca vou fazer"}
    return f"Regra salva: {nomes[tipo]} '{termo.strip()}'."


_RE_CAMINHO = re.compile(r"([a-zA-Z]:[\\/][^\s\"']*|(?<![\w.])/(?:bin|sbin|usr|etc|boot|System|Library)\b[^\s\"']*)")


def _caminhos(params: dict, descricao: str = "") -> list[str]:
    saida = []
    for v in list((params or {}).values()) + [descricao]:
        if isinstance(v, str):
            saida += _RE_CAMINHO.findall(v)
    return saida


def avaliar(ferramenta: str = "", params: dict | None = None, descricao: str = "") -> Avaliacao:
    params = params or {}
    acao = str(params.get("action") or params.get("acao") or params.get("operacao") or "")
    rotulo = (f"{ferramenta}.{acao}" if ferramenta else "") or descricao[:60] or "ação"
    texto = _dobrar(" ".join([ferramenta, acao, descricao, " ".join(str(v) for v in params.values())]))
    motivos: list[str] = []

    # 1) catálogo / leitura
    perfil = CATALOGO.get((ferramenta, acao)) or CATALOGO.get((ferramenta, "*"))
    if acao in _SO_LEITURA or (acao and acao.startswith(("listar", "ver_", "status"))):
        risco, rev, impacto, admin = 0, True, "nada (só leitura)", False
    elif perfil:
        risco, rev, impacto, admin = perfil
    else:
        risco, rev, impacto, admin = 0, True, "nada", False
        for padrao, r, rv, imp, ad, motivo in _PALAVRAS:
            if re.search(padrao, texto) and r > risco:
                risco, rev, impacto, admin = r, rv, imp, ad
                motivos.append(motivo)
        if not motivos and ferramenta:
            risco, impacto = 1, "desconhecido"
            motivos.append("ferramenta sem perfil de risco conhecido")

    # 2) pastas e processos protegidos
    bloquear = False
    for c in _caminhos(params, descricao):
        cl = c.lower().replace("/", os.sep) if os.sep == "\\" else c.lower()
        if any(cl.startswith(p) for p in _PASTAS_PROTEGIDAS):
            if any(w in texto for w in ("apag", "delet", "exclu", "remov", "mov", "renome", "limp",
                                         "edit", "escrev", "sobrescrev", "substitu")):
                motivos.append(f"{c} é pasta do sistema")
                bloquear = True
                risco, rev = max(risco, 2), False
    alvo = str(params.get("alvo") or params.get("nome") or "")
    if alvo and re.search(r"(fech|finaliz|mat|kill|encerr|suspend)", texto):
        from plugins._protecao import motivo_protecao
        m = motivo_protecao(alvo)
        if m:
            motivos.append(f"{alvo} {m}")
            bloquear = True

    # 3) suas regras
    pol = politica()
    if any(_dobrar(t) in texto for t in pol.get("nunca", [])):
        motivos.append("você pediu para eu nunca fazer isso")
        bloquear = True
    perguntar = any(_dobrar(t) in texto for t in pol.get("sempre_perguntar", []))
    sozinho = any(_dobrar(t) in texto for t in pol.get("pode_sozinho", []))
    if perguntar:
        motivos.append("você pediu para eu sempre perguntar")

    if bloquear or risco >= 3:
        decisao = "bloquear"
    elif perguntar or risco >= 2 or not rev or admin:
        decisao = "automático" if (sozinho and risco < 3 and not perguntar) else "confirmar"
        if decisao == "automático":
            motivos.append("você autorizou isso antes")
    else:
        decisao = "automático"
    return Avaliacao(rotulo, risco, rev, impacto, admin, decisao, motivos)
