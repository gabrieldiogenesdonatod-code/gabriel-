# MINER AI — mineração inteligente de criptomoedas

O MINER AI faz parte do J.A.R.V.I.S BR, mas também funciona sozinho. Ele minera **de verdade**, só no **seu** PC, e
deixa claro o que é dinheiro e o que é conta.

## Como usar

| Pelo JARVIS (voz) | Pela linha de comando |
|---|---|
| "Jarvis, o miner ai compensa?" | `python -m miner_ai calcular` |
| "Jarvis, configura o miner ai: carteira_btc=bc1q…, tarifa=0,98" | `python -m miner_ai configurar carteira_btc=bc1q… tarifa=0,98` |
| "Jarvis, inicia o miner ai no bitcoin" | `python -m miner_ai minerar btc` |
| "Jarvis, inicia o miner ai na monero" | `python -m miner_ai minerar xmr` |
| "Jarvis, abre o painel do miner ai" | `python -m miner_ai painel` → http://127.0.0.1:18090 |
| "Jarvis, pausa / retoma / para o miner ai" | botões do painel, ou Ctrl+C |

## As duas moedas

- **Bitcoin (BTC):** roda em Python puro, sem instalar nada.
  - Ele se conecta a uma pool solo de verdade (padrão: solo.ckpool.org) usando o **seu endereço público** como usuário.
  - Cada *share* aceito é trabalho real. Mas só um **bloco** paga, e num PC isso é **loteria**: em média, bilhões de anos.
  - Se um dia sair um bloco, a recompensa vai direto para o seu endereço.
- **Monero (XMR):** usa o **XMRig**, que **você** baixa em github.com/xmrig/xmrig. É a moeda mais eficiente no processador.
  - O pagamento sai pela pool (padrão: SupportXMR) quando passar do mínimo dela.
  - O Windows Defender costuma marcar o XMRig como "potencialmente indesejado". O MINER AI não mexe no antivírus: permitir é decisão sua.
- **Outras moedas:** Litecoin, Dogecoin e Bitcoin Cash precisam de máquina ASIC. Ethereum Classic precisa de placa de vídeo. Ethereum não se minera mais.

## Economia de energia (configuração → o que faz)

- **cpu_max:** limite de CPU. O motor Bitcoin trabalha uma parte do tempo e descansa no resto.
- **temperatura_max:** acima dela, pausa. A 5 °C do limite, reduz a intensidade.
  - Nem todo notebook informa a temperatura. Quando não informa, o painel mostra "—".
- **economico:** usa 1 núcleo e no máximo 30% de CPU. No Windows, só minera com o PC parado há `ocioso_min` minutos.
- **horarios:** por exemplo `22:00-07:00`. Fora dele, pausa sozinho.
- **parar_na_bateria**, **horas_max:** pausa na bateria e para no fim do tempo da sessão.
- **tdp_watts / watts_medidos:** o consumo é estimado pelo TDP. Com um medidor de tomada, ponha a diferença medida em `watts_medidos`.
- **tarifa:** R$ por kWh, da sua conta de luz.

## A regra fundamental: cada número tem o seu rótulo

- **REAL:** shares aceitos pela pool e blocos achados.
- **CONFIRMADO:** saldo na blockchain do seu endereço público (Bitcoin) ou já pago pela pool (Monero), com a fonte.
- **PENDENTE:** chegando na blockchain, ou devido pela pool e ainda não pago.
- **SIMULAÇÃO:** projeções do cérebro, ou seja, o que *poderia* render. **Não é dinheiro.**
- **CUSTO:** energia estimada (watts × tempo × tarifa).

## O cérebro

- Calcula a rentabilidade com o preço e a dificuldade de agora.
- Diz claramente quando **não compensa**, que é o normal num PC comum.
- Recomenda configurações e **aprende** com o histórico do seu PC: hashrate real e eficiência por núcleo e por carga.
- Nunca promete lucro.

## Segurança

- Só minera no próprio PC, nunca no celular.
- Nunca escondido: tem painel, avisos e janela do XMRig.
- Nunca liga sozinho. Pelo JARVIS, sempre pede confirmação na tela; pela linha de comando, pede para você digitar SIM.
- Não instala nada.
- Só guarda endereços **públicos**. Recusa chave privada, xprv e frase de recuperação, e nunca grava isso.
- O painel só abre no próprio PC (127.0.0.1). Os botões exigem uma senha da sessão.
- Pelo JARVIS, ligar e desligar ficam registrados no livro-razão.

Arquivos: `memory/miner_ai/` (config.json, historico.json, sessoes.json).
