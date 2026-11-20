"""Todos os plugins carregam — inclusive SEM nenhuma dependência opcional.

O teste esconde os pacotes opcionais (pynput, pyperclip, pyautogui, pycaw,
comtypes, OpenCV, mss, send2trash, FastAPI, openpyxl, wmi, pynvml) e confere
que o carregador de plugins não rejeita nenhum plugin: cada dependência extra
só pode ser importada na hora do uso.
"""
import builtins
import importlib
import sys
import unittest
from pathlib import Path

import tests  # noqa: F401

OPCIONAIS = ("pynput", "pyperclip", "pyautogui", "pycaw", "comtypes", "cv2", "mss", "send2trash",
             "fastapi", "uvicorn", "openpyxl", "wmi", "pynvml",
             # 1.4
             "tinytuya", "soundcard", "faster_whisper", "rapidocr_onnxruntime", "pytesseract", "pypdf",
             "PyPDF2", "docx", "imageio_ffmpeg", "ddgs", "duckduckgo_search", "PIL",
             # 1.5
             "resemblyzer", "webrtcvad", "bleak", "ai_edge_litert", "tflite_runtime", "tensorflow",
             # 1.6
             "chess", "mido", "pywebostv", "websockets")

NOVOS = {"monitor_sistema", "controle_pc", "controle_audio_video", "controle_sistema", "modo_jogo",
         "limpeza", "guarda_seguranca", "macros", "agendador", "historico_clipboard", "gravador_tela",
         "saude_pc", "downloads", "pomodoro", "assistente_rede", "protocolos", "briefing_br",
         "reconhecimento_facial", "cristal_malhas", "gastos",
         "rosto_flutuante",
         # 1.4
         "guardiao_decisoes", "gemeo_digital", "hipoteses", "simulador", "memoria_inteligente", "conselho",
         "laboratorio", "criador_ferramentas", "radar_anomalias", "memoria_contrafactual", "mapa_dependencias",
         "oportunidades", "habilidades", "reconstrucao", "prioridades", "linha_do_tempo", "quando_voltar",
         "olha_isso", "boot_cinematico", "legenda_ao_vivo", "cristal_fotos", "cristal_video",
         "cristal_calendario", "vigia_preco", "casa_inteligente", "personas", "capacete", "notificacoes",
         # 1.5
         "verificacao", "voz_dono", "chave_celular", "sentinela", "ouvido_ambiente", "ligacao", "servidores",
         "geofence", "habitos", "memoria_tela", "demonstracao", "modo_professor", "ditado_codigo", "postura",
         "humor", "companheiro_jogo", "segunda_opiniao", "auto_melhoria",
         # 1.6
         "aparelhos", "armadura", "realidade_aumentada", "modo_carro", "turno_noite", "explica_repo", "gerador_testes",
         "documentacao", "changelog_falado", "painel_dev", "gerador_projetos", "detector_golpe", "senha_vazada",
         "guarda_vps", "modo_convidado", "estilo_escrita", "resumo_grupo", "aniversarios", "ata_chamada", "entrevista",
         "portfolio", "cacador_vagas", "professor_ingles", "ensina_errado", "gerador_beats", "contador_historias",
         "parceiro_rima", "mestre_rpg", "thumbnails", "capsula_tempo", "conselheiro_decisao", "gamificacao",
         "retrospectiva", "cuidador", "xadrez", "quiz_geek", "modo_debate", "eu_virtual", "narrador", "roleta",
         # 1.7
         "jogos",
         # 1.8
         "acesso_remoto", "whatsapp_jarvis",
         # 1.9
         "gestos", "pausa_ausente", "memoria_projeto", "snapshots", "modo_aula", "ditado", "testes_vivos",
         "relatorio_loja", "jarvis_dj", "resumo_video",
         # 2.0
         "musica", "mensageiros", "companheiro", "app_celular",
         # 2.2
         "tela_ao_vivo",
         # 2.3
         "whatsapp_conversas",
         # 2.4
         "estado_mundo", "evolucao", "memoria_grafo", "missoes", "estudio_rap", "diario", "seguranca_adaptativa",
         # 2.4.1
         "interrupcao",
         # 2.5
         "contas", "rastreio", "garantias", "chuva", "ideias", "objetos_quarto", "plantas", "painel_led",
         "luva_repulsor", "conversa_grupo", "avatar_live", "holograma_mao", "interprete",
         # 2.6
         "vitrine",
         # 2.7
         "jarvis_friday", "cinema", "radionovela", "talk_show", "neste_dia", "campanha_heroi",
         # 2.8
         "modo_dormir",
         "por_que_fechou",
         # 2.9
         "segundo_cerebro", "biblioteca_prompts",
         # 2.10
         "explica_crianca", "coach_decisao", "procrastinacao",
         # 2.11
         "renomear_fotos", "organizador_abas", "modo_apresentacao", "assistente_viagem", "clone_estudo",
         "modo_faxina", "palpite_humor", "preencher_form", "acompanhar",
         # 2.13
         "porteiro_voz", "vigia_codigo",
         # 2.14
         "probabilidades",
         # 2.15
         "expressoes",
         # 2.16
         "consulta_brasil", "feriados", "alerta_cotacao", "cupom_fiscal", "racha_conta", "controle_mei",
         "planilha_viva", "agenda", "alerta_nome", "fila_leitura", "corretor_atalho", "atalhos_texto",
         "pesquisa_profunda", "duplicados", "cofre_senhas", "verificador_link", "jogar_junto",
         # 2.17
         "modos", "clientes_loja", "fiado", "meta_vendas", "torneio", "adivinha", "git_assistente", "apps_winget",
         "lista_compras", "manutencao_casa",
         # 2.18
         'anagramas', 'assinaturas', 'astronomia', 'calculadora', 'calculadora_datas', 'calculadora_musical', 'cardapio',
         'checklists', 'codificador', 'codigos_hash', 'cofrinho', 'colinha_dev', 'combustivel', 'conta_luz', 'conversor_dados',
         'conversor_unidades', 'cores', 'cron_explica', 'cronometros', 'dados_falsos', 'eletronica', 'emprestimos', 'enigmas',
         'ferramentas_texto', 'hidratacao', 'horas_freela', 'juros', 'leitura_livros', 'matematica_rapida', 'modelos_dev',
         'pets', 'piadas', 'placar', 'portas_locais', 'precificacao', 'presentes', 'promocoes_loja', 'raio_x_projeto',
         'receitas', 'recibos', 'regex_ajuda', 'requisitos_python', 'respiracao', 'rodizio_tarefas', 'semver', 'sequencias',
         'snippets', 'sorteio', 'tabela_tamanhos', 'treino', 'trocas_loja', 'validador_documentos', 'watchlist',
         'celular_android',
         # 2.19
         'catalogo', 'lixeira', 'backup_dados', 'resumo_do_dia', 'autodiagnostico', 'caixa_loja', 'lista_espera', 'fornecedores',
         'cupons_loja', 'cartao_fidelidade', 'metricas_marketing', 'etiquetas', 'investimentos', 'quitar_dividas', 'precos_mercado',
         'ponto', 'calculos_trabalhistas', 'vencimentos', 'despensa', 'onde_guardei', 'calculadora_obra', 'churrascometro', 'festa',
         'metas_pessoais', 'corrida', 'telefones_uteis', 'bingo', 'revisao_espacada', 'notas_escola', 'abnt', 'diario_classe',
         'algebra', 'geometria', 'diff_texto', 'jwt_decodificar', 'timestamp', 'http_teste', 'sqlite_ajuda', 'env_arquivo',
         'segredos_codigo', 'qualidade_codigo', 'log_analisador', 'explorar_json', 'calculadora_ip', 'bits_bytes', 'analise_csv',
         'eletronica_pro', 'impressao_3d', 'calculadora_ia', 'diario_treino_ia', 'banner_ascii', 'texto_estilizado', 'forca',
         'mini_jogos', 'jogos_de_festa', 'caca_palavras', 'trava_linguas', 'curiosidades', 'frase_do_dia',
         # 2.20
         'sonhos',
         # 2.21
         'multiverso', 'eu_do_passado', 'palavras_secretas', 'sentido_aranha',
         # 3.0
         'oraculo', 'antecipacao', 'pre_mortem', 'detector_cansaco', 'cofre_condicional', 'cacador_promessas', 'serendipidade',
         'e_se', 'crescimento_criancas', 'conferir_pagamento', 'commit_mentiroso', 'arqueologo_codigo', 'dojo_debug', 'livro_vo',
         'jornal_vida', 'rap_semana', 'mapa_calor', 'trilha_produtiva', 'duelo_ia',
         # 3.1
         'organismo',
         # 3.2
         'anti_eco', 'modo_anonimo', 'estudos',
         # 3.3
         'caixa_preta', 'eu_do_futuro', 'codigo_rap',
         # 3.4
         'cerebro',
         # 3.5
         'ia_local',
         # 3.6
         'omega', 'livro_razao', 'experimento_vida', 'metacognicao',
         'mineracao', 'carteira_cripto', 'veiculo', 'mapa_mental', 'miner_ai',
         # 3.9.1
         'hud39',
         # 3.9.3
         'salvos'}


class TestCarregamento(unittest.TestCase):
    def _descobrir(self):
        from core.plugin_loader import discover_plugins
        for nome in [m for m in sys.modules if m.startswith("plugins.") and not m.startswith("plugins._")]:
            del sys.modules[nome]
        return discover_plugins(Path(tests.RAIZ) / "plugins", set(), logger=lambda m: None)

    def test_todos_carregam(self):
        reg = self._descobrir()
        lista = reg.list_for_ui()
        rejeitados = [(p["name"], p.get("error")) for p in lista if not p["valid"]]
        self.assertEqual(rejeitados, [])
        self.assertTrue(NOVOS <= {p["name"] for p in lista})

    def test_sem_dependencias_opcionais(self):
        original = builtins.__import__

        def bloquear(nome, *args, **kwargs):
            if nome.split(".")[0] in OPCIONAIS:
                raise ImportError(f"(teste) {nome} escondido")
            return original(nome, *args, **kwargs)

        guardados = {m: sys.modules.pop(m) for m in list(sys.modules) if m.split(".")[0] in OPCIONAIS}
        builtins.__import__ = bloquear
        try:
            reg = self._descobrir()
            rejeitados = [(p["name"], p.get("error")) for p in reg.list_for_ui() if not p["valid"]]
            self.assertEqual(rejeitados, [])
            # e as ferramentas respondem com uma frase, sem levantar exceção
            for nome, params in (("macros", {"action": "gravar", "nome": "x"}),
                                 ("historico_clipboard", {"action": "listar"}),
                                 ("gravador_tela", {"action": "status"}),
                                 ("controle_audio_video", {"action": "apps_audio"}),
                                 ("modo_jogo", {"action": "status"}),
                                 ("casa_inteligente", {"action": "ligar", "aparelho": "luz"}),
                                 ("legenda_ao_vivo", {"action": "status"}),
                                 ("cristal_video", {"action": "status"}),
                                 ("notificacoes", {"action": "status"}),
                                 # 1.5: sem resemblyzer/bleak/YAMNet respondem com uma frase
                                 ("voz_dono", {"action": "aprender"}),
                                 ("chave_celular", {"action": "status"}),
                                 ("ouvido_ambiente", {"action": "status"}),
                                 ("companheiro_jogo", {"action": "status"}),
                                 ("segunda_opiniao", {"pergunta": "p", "rascunho": "r"}),
                                 # 1.6: sem mido/pywebostv respondem com uma frase (xadrez: motor próprio na 1.7)
                                 ("xadrez", {"action": "tabuleiro"}),
                                 ("jogos", {"action": "placar"}),
                                 # 1.8: sem painel/ponte respondem com uma frase
                                 ("acesso_remoto", {"action": "status"}),
                                 ("whatsapp_jarvis", {"action": "status"}),
                                 # 1.9: sem câmera/mediapipe/projetos respondem com uma frase
                                 ("gestos", {"action": "status"}),
                                 ("pausa_ausente", {"action": "status"}),
                                 ("jarvis_dj", {"action": "status"}),
                                 ("snapshots", {"action": "status"}),
                                 ("relatorio_loja", {"action": "status"}),
                                 ("memoria_projeto", {"action": "listar"}),
                                 ("modo_aula", {"action": "status"}),
                                 # 2.0: sem Spotify/Telegram/Discord respondem com uma frase
                                 ("musica", {"action": "status"}),
                                 ("mensageiros", {"action": "status"}),
                                 ("companheiro", {"action": "status"}),
                                 ("app_celular", {"action": "status"}),
                                 ("tela_ao_vivo", {"action": "status"}),
                                 # 2.3: sem a ponte do WhatsApp e sem a Twilio respondem com uma frase
                                 ("whatsapp_conversas", {"action": "status"}),
                                 ("ligacao", {"action": "status"}),
                                 # 2.4: sem microfone, numpy de rede treinada, ffmpeg ou Gemini respondem com uma frase
                                 ("estado_mundo", {"action": "agora"}),
                                 ("evolucao", {"action": "relatorio"}),
                                 ("memoria_grafo", {"action": "status"}),
                                 ("missoes", {"action": "listar"}),
                                 ("estudio_rap", {"action": "takes"}),
                                 ("seguranca_adaptativa", {"action": "status"}),
                                 ("interrupcao", {"action": "status"}),
                                 # 2.5: sem PDF, câmera, MediaPipe, ESP32, OBS ou Gemini respondem com uma frase
                                 ("contas", {"action": "listar"}),
                                 ("rastreio", {"action": "listar"}),
                                 ("garantias", {"action": "listar"}),
                                 ("ideias", {"action": "listar"}),
                                 ("objetos_quarto", {"action": "status"}),
                                 ("plantas", {"action": "status"}),
                                 ("painel_led", {"action": "status"}),
                                 ("luva_repulsor", {"action": "status"}),
                                 ("conversa_grupo", {"action": "pessoas"}),
                                 ("avatar_live", {"action": "status"}),
                                 ("holograma_mao", {"action": "limpar"}),
                                 ("interprete", {"action": "status"}),
                                 ("vitrine", {"action": "status"}),
                                 # 2.7: sem Gemini/voz respondem com uma frase
                                 ("jarvis_friday", {"action": "placar"}),
                                 ("cinema", {"action": "catalogo"}),
                                 ("cinema", {"action": "onde_parei", "titulo": "Dark"}),
                                 ("radionovela", {"action": "resumo"}),
                                 ("talk_show", {"action": "status"}),
                                 ("neste_dia", {"action": "data", "data": "28/10/2026"}),
                                 ("campanha_heroi", {"action": "vilao"}),
                                 # 2.8: sem main.py, placa de som ou faster-whisper respondem com uma frase
                                 ("modo_dormir", {"action": "status"}),
                                 ("modo_dormir", {"action": "ciclos", "acordar_as": "06:30"}),
                                 ("por_que_fechou", {"action": "historico"}),
                                 ("segundo_cerebro", {"action": "listar"}),
                                 ("biblioteca_prompts", {"action": "listar"}),
                                 ("explica_crianca", {"action": "explicar", "assunto": "teste"}),
                                 ("coach_decisao", {"action": "listar"}),
                                 ("procrastinacao", {"action": "status"}),
                                 ("renomear_fotos", {"action": "sugerir"}),
                                 ("organizador_abas", {"action": "listar"}),
                                 ("modo_apresentacao", {"action": "status"}),
                                 ("assistente_viagem", {"action": "fuso", "lugar": "Lisboa"}),
                                 ("clone_estudo", {"action": "desempenho"}),
                                 ("palpite_humor", {"action": "palpite"}),
                                 ("preencher_form", {"action": "ver"}),
                                 ("acompanhar", {"action": "tela"}),
                                 ("pomodoro", {"action": "negociar", "o_que": "YouTube", "minutos": 5}),
                                 ("aparelhos", {"action": "listar"}),
                                 ("detector_golpe", {"texto": "oi"})):
                r = reg.run(nome, params)
                self.assertIsInstance(r, str)
                self.assertTrue(r)
        finally:
            builtins.__import__ = original
            sys.modules.update(guardados)

    def test_declaracoes_validas_para_o_gemini(self):
        """Toda propriedade precisa de 'type'; 'required' só pode citar o que existe."""
        reg = self._descobrir()
        for d in reg.get_tool_declarations():
            props = d["parameters"].get("properties", {})
            for k, v in props.items():
                self.assertIn(v.get("type"), ("STRING", "NUMBER", "INTEGER", "BOOLEAN", "OBJECT", "ARRAY"),
                              f"{d['name']}.{k}")
            for r in d["parameters"].get("required", []):
                self.assertIn(r, props, d["name"])
            self.assertLess(len(d["description"]), 1500, d["name"])

    def test_modulos_core_sem_interface(self):
        for m in ("core.telemetria", "core.qt_bridge", "plugins._monitor_db", "plugins._processos",
                  "plugins._janelas", "plugins._indice_apps", "plugins._painel_remoto"):
            importlib.import_module(m)


if __name__ == "__main__":
    unittest.main()
