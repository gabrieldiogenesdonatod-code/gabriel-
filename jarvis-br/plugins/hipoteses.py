"""
Motor de hipóteses concorrentes — ideia 2 (fork PT-BR 1.4).

Diante de um problema ("o PC está lento", "a internet caiu", "o som sumiu",
"o app não abre"), o JARVIS NÃO aposta na primeira explicação. Ele:

    1. levanta várias hipóteses possíveis para aquele tipo de problema;
    2. junta EVIDÊNCIAS medidas agora (telemetria, histórico do monitor,
       diário de uso, rede, processos);
    3. pontua cada hipótese: evidência a favor soma, evidência contra subtrai;
    4. devolve as 3 melhores com o NÍVEL DE CONFIANÇA, o que sustenta cada uma
       e qual teste decidiria entre elas.

As confiança são relativas entre si (somam 100%) e vêm de regras explícitas
em `CATALOGO`, então dá para ver por que uma hipótese ganhou. Para problemas
fora do catálogo, se houver IA, ela propõe hipóteses e testes — marcadas como
"estimativa da IA", porque não foram medidas.

A função `avaliar(dominio, evidencias)` é pura (está nos testes).
"""

from __future__ import annotations

import math
import time
import unicodedata

from plugins._comum import br, mostrar, tamanho

PLUGIN = {
    "name": "hipoteses",
    "brief": "Competing hypotheses with evidence and confidence for a PC/network/app problem.",
    "description": (
        "Competing-hypotheses engine. For any 'why' problem ('por que o PC está lento', 'por que a "
        "internet caiu', 'o som sumiu', 'o app não abre', 'o PC travou', 'está esquentando', 'o "
        "disco encheu'), call action='analisar' with problema = the user's words. It returns the top "
        "3 explanations with measured evidence, a confidence for each and the test that would decide. "
        "Present the confidence honestly; do not pick one as certain."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "analisar"},
            "problema": {"type": "STRING"},
        },
        "required": ["problema"],
    },
}

GB = 1024 ** 3


def _d(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()


DOMINIOS = {
    "lento": ("lent", "devagar", "pesad", "engasg", "demor"),
    "internet": ("internet", "wifi", "wi-fi", "rede", "ping", "lag", "conexao", "site"),
    "travou": ("trav", "congel", "nao responde", "parou de responder", "tela preta"),
    "quente": ("quent", "esquent", "temperatura", "ventoinha", "barulh"),
    "disco": ("disco", "espaco", "armazenamento", "cheio", "hd ", "ssd"),
    "som": ("som", "audio", "volume", "mudo", "fone", "caixa de som", "microfone"),
    "app": ("nao abre", "nao abriu", "nao inicia", "fecha sozinho", "crash", "abrir o", "erro ao abrir"),
}


def dominio_de(problema: str) -> str | None:
    t = _d(problema)
    melhor, n = None, 0
    for dom, termos in DOMINIOS.items():
        c = sum(1 for x in termos if x in t)
        if c > n:
            melhor, n = dom, c
    return melhor


# ── evidências medidas ─────────────────────────────────────────────────────────
def coletar() -> dict:
    from core import telemetria
    s = telemetria.get().snapshot()
    procs = s.get("processos") or []
    ram = s.get("ram") or {}
    e = {
        "cpu": s.get("cpu") or 0, "ram_pct": ram.get("pct") or 0, "swap_pct": (s.get("swap") or {}).get("pct") or 0,
        "temp": s.get("cpu_temp"), "gpu": (s.get("gpu") or {}).get("uso"), "gpu_temp": (s.get("gpu") or {}).get("temp"),
        "disco_min_livre": min((100 - p["pct"] for p in s.get("particoes") or []), default=100),
        "disco_io": sum((s.get("disco_io") or {}).values()),
        "top_cpu": procs[0] if procs else None,
        "top_ram": max(procs, key=lambda p: p["ram"], default=None),
        "processos": len(procs), "uptime_dias": (s.get("uptime") or 0) / 86400,
        "internet": s.get("internet"), "ping": ((s.get("ping") or {}).get("8.8.8.8") or {}).get("ms"),
        "perda": ((s.get("ping") or {}).get("8.8.8.8") or {}).get("perda"),
        "gw_ms": ((s.get("ping") or {}).get("gateway") or {}).get("ms"),
        "wifi_sinal": (s.get("wifi") or {}).get("sinal"),
        "uso_rede": (s.get("rede") or {}).get("down", 0) + (s.get("rede") or {}).get("up", 0),
        "freq": s.get("cpu_freq_mhz"), "bateria": s.get("bateria"),
    }
    try:
        from plugins import _monitor_db
        evs = _monitor_db.eventos(time.time() - 3 * 3600, 100)
        e["quedas_recentes"] = sum(1 for x in evs if x["tipo"] == "internet_caiu")
        r = _monitor_db.resumo(time.time() - 3600)
        e["cpu_media_hora"] = r.get("cpu_media")
        e["temp_max_hora"] = r.get("temp_max")
    except Exception:
        pass
    try:
        from core import registro_uso
        ch = registro_uso.chamadas(time.time() - 3600)
        e["falhas_hora"] = sum(1 for c in ch if not c["ok"])
    except Exception:
        pass
    return e


# Cada hipótese: (nome, explicação, priori, [(teste(e) → força -1..1 ou None, descrição)], próximo teste)
def _h(nome, explicacao, priori, sinais, teste):
    return {"nome": nome, "explicacao": explicacao, "priori": priori, "sinais": sinais, "teste": teste}


def _cpu_alta(e): return None if e.get("cpu") is None else (1.0 if e["cpu"] > 85 else .5 if e["cpu"] > 60 else -.6)
def _ram_alta(e): return 1.0 if e["ram_pct"] > 90 else .5 if e["ram_pct"] > 80 else -.6
def _swap(e): return .6 if e["swap_pct"] > 50 and e["ram_pct"] > 80 else (0 if e["swap_pct"] < 20 else .2)
def _quente(e): return None if e.get("temp") is None else (1.0 if e["temp"] >= 90 else .5 if e["temp"] >= 80 else -.5)
def _disco_cheio(e): return 1.0 if e["disco_min_livre"] < 5 else .5 if e["disco_min_livre"] < 10 else -.5
def _disco_ocupado(e): return .8 if e["disco_io"] > 80 * 1024 ** 2 else .3 if e["disco_io"] > 20 * 1024 ** 2 else -.3
def _uptime(e): return .7 if e["uptime_dias"] > 10 else .3 if e["uptime_dias"] > 4 else -.3
def _muitos(e): return .5 if e["processos"] > 300 else -.2
def _sem_net(e): return None if e.get("internet") is None else (1.0 if e["internet"] is False else -.8)
def _gw_ruim(e): return None if e.get("gw_ms") is None and e.get("internet") is None else \
    (1.0 if e.get("gw_ms") is None else .7 if e["gw_ms"] > 30 else -.6)
def _ping_alto(e): return None if e.get("ping") is None else (.9 if e["ping"] > 150 else .4 if e["ping"] > 80 else -.6)
def _perda(e): return None if e.get("perda") is None else (1.0 if e["perda"] > 5 else .4 if e["perda"] > 0 else -.4)
def _sinal(e): return None if e.get("wifi_sinal") is None else (.9 if e["wifi_sinal"] < 40 else .3 if e["wifi_sinal"] < 60 else -.5)
def _banda(e): return .8 if e["uso_rede"] > 3 * 1024 ** 2 else .3 if e["uso_rede"] > 1024 ** 2 else -.4
def _quedas(e): return None if e.get("quedas_recentes") is None else (.9 if e["quedas_recentes"] >= 2 else .4 if e["quedas_recentes"] else -.2)
def _freq_baixa(e): return None if not e.get("freq") else (.6 if e["freq"] < 1200 else -.2)
def _bateria(e):
    b = e.get("bateria")
    return None if not b else (.6 if not b.get("na_tomada") else -.3)
def _gpu_alta(e): return None if e.get("gpu") is None else (.8 if e["gpu"] > 90 else -.3)


CATALOGO = {
    "lento": [
        _h("processador sobrecarregado", "algum programa está usando quase toda a CPU", .25,
           [(_cpu_alta, "uso de CPU"), (_quente, "temperatura")],
           "abrir o top de processos por CPU e fechar o que estiver no alto"),
        _h("memória RAM esgotada", "falta RAM e o Windows está usando o disco como memória", .25,
           [(_ram_alta, "uso de RAM"), (_swap, "uso da memória virtual")],
           "ver o top por memória; se a RAM estiver acima de 90%, fechar abas e apps"),
        _h("disco cheio ou sobrecarregado", "o disco está quase cheio ou lendo/gravando sem parar", .15,
           [(_disco_cheio, "espaço livre"), (_disco_ocupado, "leitura/escrita agora")],
           "ver quem está usando o disco no top de processos e rodar a limpeza"),
        _h("superaquecimento", "o processador esquentou e reduziu a velocidade para se proteger", .1,
           [(_quente, "temperatura"), (_freq_baixa, "frequência da CPU")],
           "medir a temperatura depois de 5 minutos parado e limpar a poeira"),
        _h("economia de energia", "está na bateria ou num plano de economia, que limita o desempenho", .1,
           [(_bateria, "bateria"), (_freq_baixa, "frequência da CPU")],
           "ligar na tomada e trocar o plano de energia para equilibrado/alto desempenho"),
        _h("PC há muito tempo sem reiniciar", "programas acumulam memória e processos com o tempo", .15,
           [(_uptime, "dias ligado"), (_muitos, "quantidade de processos")],
           "reiniciar e ver se melhora"),
    ],
    "internet": [
        _h("sem conexão com o roteador", "o Wi-Fi/cabo caiu entre o PC e o roteador", .2,
           [(_gw_ruim, "resposta do roteador"), (_sinal, "sinal do Wi-Fi")],
           "chegar perto do roteador ou trocar para cabo"),
        _h("problema na operadora", "o roteador responde, mas a internet depois dele não", .25,
           [(_sem_net, "internet"), (lambda e: None if e.get("gw_ms") is None else (.6 if e["gw_ms"] < 15 else -.3),
                                     "roteador respondendo bem"), (_quedas, "quedas nas últimas 3 h")],
           "reiniciar o modem; se continuar, ver se a operadora está com falha"),
        _h("Wi-Fi fraco ou com interferência", "o sinal está fraco e os pacotes se perdem no ar", .2,
           [(_sinal, "sinal do Wi-Fi"), (_perda, "perda de pacotes"), (_gw_ruim, "resposta do roteador")],
           "testar perto do roteador ou na rede 5 GHz"),
        _h("banda ocupada", "algum programa (ou outro aparelho) está baixando/enviando muito", .2,
           [(_banda, "uso de rede deste PC"), (_ping_alto, "latência")],
           "pausar downloads, sincronização na nuvem e atualizações"),
        _h("rota/servidor distante lento", "a latência até a internet está alta mesmo com tudo bem em casa", .15,
           [(_ping_alto, "latência"), (lambda e: None if e.get("gw_ms") is None else (.5 if e["gw_ms"] < 15 else -.3),
                                       "roteador respondendo bem")],
           "rodar o teste de velocidade e comparar com outro horário"),
    ],
    "travou": [
        _h("falta de memória", "a RAM acabou e tudo ficou esperando o disco", .3,
           [(_ram_alta, "uso de RAM"), (_swap, "memória virtual")], "ver o top por memória"),
        _h("programa travado em loop", "um programa está preso usando 100% de um núcleo ou mais", .25,
           [(_cpu_alta, "uso de CPU")], "ver o top por CPU e finalizar o que estiver travado"),
        _h("superaquecimento", "o PC esquenta e trava para se proteger", .15,
           [(_quente, "temperatura")], "ver a temperatura e limpar a ventilação"),
        _h("disco com problema ou cheio", "o disco não dá conta e o sistema congela", .15,
           [(_disco_cheio, "espaço livre"), (_disco_ocupado, "uso do disco")],
           "conferir a saúde SMART dos discos (Jarvis, como estão os discos?)"),
        _h("placa de vídeo no limite", "a GPU está no máximo (jogo, render)", .15,
           [(_gpu_alta, "uso da GPU")], "baixar a qualidade gráfica ou limitar o FPS"),
    ],
    "quente": [
        _h("carga alta", "o PC está trabalhando muito e esquenta", .35,
           [(_cpu_alta, "uso de CPU"), (_gpu_alta, "uso da GPU")], "ver o top de processos"),
        _h("ventilação ruim ou poeira", "esquenta mesmo com pouca carga", .35,
           [(_quente, "temperatura"), (lambda e: None if e.get("cpu") is None else (.7 if e["cpu"] < 30 else -.4),
                                       "carga baixa")],
           "limpar a poeira, deixar as saídas de ar livres"),
        _h("ambiente quente / notebook em superfície macia", "o calor não tem para onde ir", .3,
           [(_bateria, "é notebook")], "usar uma superfície dura ou base com ventoinha"),
    ],
    "disco": [
        _h("arquivos temporários e caches", "lixo acumulado", .35, [(_disco_cheio, "espaço livre")],
           "Jarvis, limpa o PC"),
        _h("arquivos grandes esquecidos", "vídeos, instaladores e backups antigos", .35,
           [(_disco_cheio, "espaço livre")], "Jarvis, quais os maiores arquivos?"),
        _h("algo gravando sem parar", "um programa está escrevendo muito no disco agora", .3,
           [(_disco_ocupado, "escrita no disco")], "ver o top de processos por disco"),
    ],
    "som": [
        _h("saída de som errada", "o som está indo para outro aparelho (fone, TV, HDMI)", .4, [],
           "Jarvis, quais são as saídas de som? e trocar para a certa"),
        _h("volume ou mudo", "o volume geral ou do app está zerado/mudo", .35, [],
           "Jarvis, volume em 50 e tira o mudo"),
        _h("driver/serviço de áudio travado", "o serviço de áudio do Windows parou", .25, [],
           "reiniciar o serviço 'Windows Audio' ou o PC"),
    ],
    "app": [
        _h("nome ou atalho errado", "o JARVIS não achou o programa com esse nome", .3,
           [(lambda e: None if e.get("falhas_hora") is None else (.5 if e["falhas_hora"] else -.2), "falhas recentes")],
           "Jarvis, procura o app X (e criar um apelido)"),
        _h("já está aberto em segundo plano", "o app está na bandeja e só não apareceu", .25, [],
           "olhar a bandeja do Windows ou pedir para focar o app"),
        _h("falta de memória", "o app não consegue iniciar sem RAM", .2, [(_ram_alta, "uso de RAM")],
           "fechar programas pesados e tentar de novo"),
        _h("instalação corrompida ou bloqueio do antivírus", "o próprio app está quebrado", .25, [],
           "abrir o app pelo Menu Iniciar e ver a mensagem de erro; reinstalar se preciso"),
    ],
}


def avaliar(dominio: str, e: dict) -> list[dict]:
    """Pura: pontua as hipóteses do domínio com as evidências e devolve em ordem."""
    resultados = []
    for h in CATALOGO.get(dominio, []):
        pontos = math.log(h["priori"] / (1 - h["priori"]))
        a_favor, contra, sem = [], [], []
        for teste, desc in h["sinais"]:
            try:
                f = teste(e)
            except Exception:
                f = None
            if f is None:
                sem.append(desc)
                continue
            pontos += 1.8 * f
            (a_favor if f > 0 else contra if f < 0 else sem).append(desc)
        resultados.append({**{k: h[k] for k in ("nome", "explicacao", "teste")},
                           "pontos": pontos, "a_favor": a_favor, "contra": contra, "sem_dado": sem})
    if not resultados:
        return []
    m = max(r["pontos"] for r in resultados)
    soma = sum(math.exp(r["pontos"] - m) for r in resultados)
    for r in resultados:
        r["confianca"] = math.exp(r["pontos"] - m) / soma
    return sorted(resultados, key=lambda r: -r["confianca"])


def _evidencias_texto(e: dict) -> list[str]:
    linhas = [f"CPU {br(e['cpu'], 0)}%   RAM {br(e['ram_pct'], 0)}%   swap {br(e['swap_pct'], 0)}%   "
              f"temp {('%s °C' % br(e['temp'], 0)) if e.get('temp') is not None else '—'}",
              f"disco livre (menor) {br(e['disco_min_livre'], 0)}%   disco agora {tamanho(e['disco_io'])}/s   "
              f"ligado há {br(e['uptime_dias'], 1)} dias"]
    if e.get("top_cpu"):
        linhas.append(f"mais CPU: {e['top_cpu']['nome']} ({br(e['top_cpu']['cpu'], 0)}%)   "
                      f"mais RAM: {e['top_ram']['nome']} ({tamanho(e['top_ram']['ram'])})")
    linhas.append(f"internet {e.get('internet')}   ping {e.get('ping')} ms   roteador {e.get('gw_ms')} ms   "
                  f"perda {e.get('perda')}%   Wi-Fi {e.get('wifi_sinal')}%")
    return linhas


def run(parameters: dict, player=None, session_memory=None) -> str:
    problema = str((parameters or {}).get("problema") or "").strip()
    if not problema:
        return "Qual é o problema?"
    try:
        dom = dominio_de(problema)
        if dom is None:
            from plugins._ia import perguntar_json
            r = perguntar_json(
                "Problema relatado num PC Windows: \"" + problema + "\". Liste 3 hipóteses concorrentes. "
                "Responda SÓ JSON: {\"hipoteses\": [{\"nome\": \"...\", \"explicacao\": \"...\", "
                "\"confianca\": 0-100, \"teste\": \"como confirmar\"}]} em português do Brasil.")
            hs = (r or {}).get("hipoteses") if isinstance(r, dict) else None
            if not hs:
                return ("Não reconheço esse tipo de problema e não tenho IA disponível agora para levantar "
                        "hipóteses. Tente descrever como lentidão, internet, travamento, som, disco ou app.")
            mostrar(player, "HIPÓTESES (ESTIMATIVA DA IA — NÃO MEDIDAS)", "\n\n".join(
                f"{i + 1}. {h.get('nome')} — {h.get('confianca')}%\n   {h.get('explicacao')}\n   teste: {h.get('teste')}"
                for i, h in enumerate(hs[:3])))
            return "Estimativa da IA, sem medição: " + "; ".join(
                f"{h.get('nome')} ({h.get('confianca')}%)" for h in hs[:3]) + "."
        e = coletar()
        res = avaliar(dom, e)[:3]
        linhas = ["EVIDÊNCIAS MEDIDAS AGORA"] + _evidencias_texto(e) + [""]
        for i, r in enumerate(res, 1):
            linhas += [f"{i}. {r['nome'].upper()} — confiança {br(100 * r['confianca'], 0)}%",
                       f"   {r['explicacao']}",
                       f"   a favor: {', '.join(r['a_favor']) or '—'}   contra: {', '.join(r['contra']) or '—'}"
                       + (f"   sem dado: {', '.join(r['sem_dado'])}" if r["sem_dado"] else ""),
                       f"   teste que decide: {r['teste']}", ""]
        mostrar(player, f"HIPÓTESES — {problema[:40].upper()}", "\n".join(linhas))
        a, b = res[0], res[1] if len(res) > 1 else None
        fala = f"Mais provável: {a['nome']} ({br(100 * a['confianca'], 0)}%)"
        if a["a_favor"]:
            fala += f", porque {' e '.join(a['a_favor'])} indicam isso"
        fala += "."
        if b:
            fala += f" Segunda hipótese: {b['nome']} ({br(100 * b['confianca'], 0)}%)."
        if a["confianca"] < 0.45:
            fala += " Não tenho certeza; o teste que decide é: " + a["teste"] + "."
        else:
            fala += " Para confirmar: " + a["teste"] + "."
        return fala
    except Exception as ex:
        return f"O motor de hipóteses falhou: {ex}"
