"""
MINER AI (fork PT-BR 3.9) — sistema inteligente de mineração de criptomoedas, com energia, segurança e honestidade
em primeiro lugar.

    python -m miner_ai calcular            → o cérebro diz se compensa (simulação, com a sua conta de luz)
    python -m miner_ai minerar btc         → Bitcoin em Python puro, sem instalar nada, numa pool solo de verdade
    python -m miner_ai minerar xmr         → Monero pelo XMRig que VOCÊ baixou (o mais eficiente no processador)
    python -m miner_ai painel              → dashboard no navegador (http://127.0.0.1:18090)
    "Jarvis, abre o miner ai" / "Jarvis, inicia o miner ai no bitcoin" / "Jarvis, o miner ai compensa?"

Módulos (cada um independente, sem nada do JARVIS — dá para usar sozinho):
    seguranca  endereços públicos válidos; recusa chave privada e frase de recuperação; nunca no celular
    economia   limite de CPU, temperatura, watts e kWh estimados, modo econômico, horários, pausa e redução
    rede       preços, dificuldade das redes, saldo PÚBLICO do endereço e saldo na pool (só leitura)
    cerebro    rentabilidade, veredito honesto, recomendação e aprendizado com o histórico do seu PC
    stratum_btc / motor_btc   protocolo Stratum + SHA-256d em Python puro (mineração real)
    motor_xmrig               controle do XMRig (Monero), janela visível
    controlador               junta tudo: regras de economia, métricas, histórico, estado rotulado
    painel                    dashboard local (só 127.0.0.1)

REGRA FUNDAMENTAL — cada número tem o seu rótulo, e eles nunca se misturam:
    real        trabalho aceito pela pool (shares) e blocos achados
    confirmado  saldo que está NA BLOCKCHAIN ou já foi PAGO pela pool (com a fonte e a hora da consulta)
    pendente    o que a pool diz que deve a você, ainda não pago
    simulacao   projeções do cérebro (o que PODERIA render) — não é dinheiro
    custos      energia estimada (watts × tempo × tarifa)
Nunca promete lucro. Num PC comum, minerar quase sempre dá prejuízo: o cérebro mostra isso com números.
"""
__version__ = "1.0"
