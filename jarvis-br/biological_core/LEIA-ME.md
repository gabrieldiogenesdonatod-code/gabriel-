# JARVIS BIOLOGICAL CORE — ARTIFICIAL LIFE ARCHITECTURE (3.1)

Um organismo digital dentro do J.A.R.V.I.S BR: cérebro, coração, sistema nervoso, circulação,
DNA digital, sistema imunológico de 8 camadas, regeneração e seis tipos de células especializadas.

**O que isto é, de verdade:** sistemas computacionais concretos, em Python puro, inspirados na
biologia. Não há "vida" nem consciência aqui. Tudo roda no seu PC (ou no celular pelo Termux),
sem internet, sem API paga, sem Ollama e sem Qwen.

## Como usar

| Diga | O que acontece |
|---|---|
| "Jarvis, como está a sua saúde?" | nota de 0 a 100, órgãos com problema, o que está isolado |
| "Jarvis, abre o painel do organismo" | página futurista que se atualiza sozinha (memory/biological/painel.html) |
| "Jarvis, mostra os incidentes" / "explica o incidente 3" | o que adoeceu e POR QUE o cérebro decidiu cada reparo |
| "Jarvis, o que está em quarentena?" / "libera o rastreio" | partes isoladas; liberar ensina o organismo a ser mais tolerante |
| "Jarvis, mostra os reparos pendentes" | o que espera o seu SIM (aparece no banner CONFIRMAR) |
| "Jarvis, faz um exame completo" / "roda as vacinas" | checagem completa e os testes de segurança |
| "Jarvis, o que você aprendeu se consertando?" / "relatório da defesa" | placar dos reparos, recomendações |
| "Jarvis, reconhece as mudanças no DNA" | depois que VOCÊ editou código ou instalou versão nova |

No celular: aba **Corpo** (com os botões Autorizar / Negar / Liberar).

## Onde cada órgão se liga ao JARVIS (nada foi substituído)

| Ponto do JARVIS | O que o organismo faz ali |
|---|---|
| `core/plugin_loader.py` (`PluginRegistry.run`) | **portão** antes de cada plugin (defesa + isolamento) e o resultado depois |
| `core/vigia.py` (3.0) | ferramenta que passou do limite e a que terminou atrasada; limite por ferramenta (`LIMITES`) |
| `core/relogio.py` (3.0) | rotina com erro, rotina travada, pausa das não essenciais na febre |
| `core/confirm.py` | banner CONFIRMAR para tudo que precisa do seu sim (o modelo não consegue forjar) |
| `core/undo.py` | "Jarvis, desfaz" também desfaz um reparo |
| `core/central_avisos.py` | avisos de saúde respeitam jogo, live e chamada |
| `core/telemetria.py` | temperatura e CPU do PC vêm da fonte única do projeto |
| `core/protecao_falhas.py` | a linha do tempo do erros.log registra os eventos do organismo |
| `plugins/auto_melhoria.py` | o cérebro encaminha erro de código para a correção testada numa cópia |
| `plugins/organismo.py` | liga o organismo no início da sessão e é por onde você conversa com ele |
| `celular/jarvis_celular.py` | liga no Termux; `/api/corpo` e a aba Corpo |

Sem o organismo ligado, os pontos de integração não custam nada (nem importam o pacote).

## Os órgãos

- **Sistema nervoso** (`nervous_system/`): eventos com id, tópico, origem, prioridade, horário e
  histórico; assinatura com curinga (`incidente.*`); pedido de ajuda entre órgãos; assinante que
  erra 5 vezes é desligado ("inflamado") sem derrubar os outros. Importantes vão para `nervos.jsonl`.
- **Circulação** (`circulation/`): fila de prioridade numa thread própria, sem duplicar evento
  (mesma chave vira um só), mede fluxo e espera, alivia congestionamento descartando o de baixa prioridade.
- **DNA** (`dna/`): genoma assinado (HMAC-SHA256) com o SHA-256 de cada arquivo de código, módulos,
  versão e dependências; banco de células-tronco (cópia confiável do código). Gênese automática no
  primeiro início; depois, só muda com a sua autorização.
- **Sistema imunológico** (`immune_system/` + `cells/`), 8 camadas:
  1. detecção (sentinelas: plugins, vigia, relógio, rondas, anomalias estatísticas)
  2. identificação (regras + classificador do cérebro; gravidade; falha normal × ameaça)
  3. defesa (desligar antivírus/firewall, destruir o disco, mexer no DNA: bloqueado; laço: pausa;
     pasta do sistema ou plugin comprometido pedindo algo perigoso: pede o seu sim)
  4. isolamento (quarentena só do pedaço doente; disjuntor 1 min → 5 min → 30 min → 2 h com teste)
  5. reparação (regeneração)
  6. memória (SQLite: incidentes, anticorpos, ameaças, decisões)
  7. prevenção (pontos de restauração dos dados com versões guardadas uma vez só, checagem de JSON
     e SQLite, verificação de código antes de recarregar, avaliação de risco)
  8. evolução (relatório, recomendações, 7 vacinas numa pasta temporária, limites adaptativos)
- **Cérebro** (`brain/`) — a IA básica local:
  - classificador Naive Bayes de mensagens de erro que aprende com cada cura;
  - motor de hipóteses bayesiano (prior pelo histórico do módulo × razões de verossimilhança das
    evidências) que explica as evidências;
  - decisão por regras + permissões + amostragem de Thompson moderada sobre o placar de cada
    tratamento (por tipo de problema e por erro específico).
- **Coração** (`heart/`): thread própria (bate a cada 10 s, ~1 ms), sinais vitais, órgãos vivos,
  módulos travados, reflexos (memória alta → limpa caches; febre → pausa rotinas não essenciais;
  temperatura crítica → aviso urgente), ciclo de inicialização e encerramento seguro.
- **Regeneração** (`regeneration/`): o protocolo de 10 passos (detectar, identificar, avaliar risco,
  isolar, consultar histórico, ponto de recuperação, aplicar, reiniciar, testar, informar), com cada
  passo gravado no incidente.
- **Células** (`cells/`): sentinela, detectora, defensora, reparadora, de memória e analista.
- **Sono de manutenção**: entre 4h e 6h — arquiva incidentes velhos, compacta o banco, cria o ponto
  de restauração do dia, roda as vacinas, ajusta limites e prepara o boletim da manhã.

## Configuração (config/api_keys.json, tudo opcional)

```json
{ "bio_autonomia": "normal", "bio_pre_autorizados": ["restaurar_json"], "bio_batimento_s": 10,
  "bio_rajada_por_min": 30, "bio_desligado": false }
```

`observar` = só detecta, isola o que trava e avisa. Diminuir a autonomia é imediato; aumentar e
desligar pedem o seu sim na tela. Mudança nessas chaves feita por fora vira alerta.

## Arquivos (memory/biological/)

`genoma.json` · `.chave_dna` · `celulas_tronco.zip` (~2,3 MB) · `imunidade.db` · `quarentena.json` ·
`cerebro.json` · `autorizacoes.json` · `estado.json` · `diario.json` · `nervos.jsonl` ·
`evolucao.json` · `prevencao.json` · `pontos/` · `painel.html`

## Medido (sandbox Linux, projeto real com 339 plugins)

- liga em ~150 ms (a gênese do DNA, só na primeira vez, ~130 ms; o resto ~20 ms)
- portão por ferramenta: mediana 7 µs, p99 44 µs · batimento: ~1 ms
- +2 threads (coração e circulação); as rotinas usam o relógio central da 3.0
- 53 testes próprios (`tests/test_50_bio_*.py`) + toda a suíte do projeto

## Limites honestos

- Python não consegue matar uma thread presa: o organismo isola a ferramenta travada e avisa,
  mas a thread só libera quando ela terminar (ou reiniciando o JARVIS).
- Plugins rodam no mesmo processo: a defesa age no portão (parâmetros) e na detecção; ela não é
  uma caixa de areia contra um plugin malicioso que você mesmo instalou.
- A chave do DNA fica no seu PC: pega mudança acidental e adulteração ingênua, não um invasor com
  controle total da máquina.
- O classificador começa com ~90 exemplos; ele melhora com o uso, mas erra em mensagens muito
  diferentes de tudo que já viu (aí ele diz "desconhecida" e escolhe o reparo mais seguro).
- "Recuperação" de código só existe para arquivos que estavam no DNA (células-tronco); plugin
  novo ainda não reconhecido não tem cópia confiável.
- Os sinais vitais dependem do psutil (no Termux podem faltar; o resto funciona).
