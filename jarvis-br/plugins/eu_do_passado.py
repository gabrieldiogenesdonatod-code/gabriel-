"""
Eu do passado (2.21): converse com quem você era há alguns meses.

Todo mês o JARVIS guarda uma "fotografia" de você: o que estava nas suas memórias, metas, ideias,
anotações e projetos naquela época. Depois você pode conversar com aquela versão:

    "Jarvis, me deixa falar com o eu de 6 meses atrás: o que você queria para hoje?"
    "Jarvis, o que mudou em mim desde março?"

Ele responde em primeira pessoa, COMO você respondia na época, usando só o que estava guardado
naquela fotografia (não inventa lembrança). Sem fotografia antiga ainda, ele avisa e já tira a
primeira, para daqui a alguns meses você ter com quem conversar.
"""

from __future__ import annotations

import json
import time
from datetime import date

from plugins._lote2 import P, carregar, guardar, num1, rodar

PLUGIN = P("eu_do_passado", "Talk to your past self: monthly snapshots of what you had in memories, goals, ideas and notes; chat in first person "
           "as you were N months ago, or compare then vs now.",
           "conversar | mudou | fotografar | fotografias",
           "conversar: pergunta, meses (how far back, default 6). mudou: meses. fotografar: save today's snapshot (automatic monthly).",
           "pergunta meses")

FONTES = [("metas", "metas_pessoais", {"action": "listar"}), ("ideias", "ideias", {"action": "listar"}),
          ("segundo cérebro", "segundo_cerebro", {"action": "listar"}), ("hábitos", "sequencias", {"action": "ofensivas"}),
          ("cofrinho", "cofrinho", {"action": "ver"}), ("livros", "leitura_livros", {"action": "estante"}),
          ("modos que mais usava", "modos", {"action": "historico"}), ("sonho mais recente", "sonhos", {"action": "ultimo"})]


def tirar_foto(executar) -> dict:
    """executar(nome, params) -> texto. Junta o retrato do mês. Pura (com executar)."""
    partes = {}
    try:
        from memory.memory_manager import load_memory
        partes["memórias"] = json.dumps(load_memory() or {}, ensure_ascii=False)[:2500]
    except Exception:
        pass
    for titulo, nome, params in FONTES:
        try:
            r = str(executar(nome, params))[:700]
            if r and "não existe" not in r and not r.lower().startswith(("nenhum", "ainda n", "lista vazia")):
                partes[titulo] = r
        except Exception:
            pass
    return {"dia": date.today().isoformat(), "partes": partes}


def mais_perto(fotos: list[dict], meses: float, hoje: date) -> dict | None:
    """A fotografia mais próxima de 'meses' atrás (precisa ter pelo menos 25 dias). Pura."""
    alvo = meses * 30.4
    velhas = [f for f in fotos if (hoje - date.fromisoformat(f["dia"])).days >= 25]
    return min(velhas, key=lambda f: abs((hoje - date.fromisoformat(f["dia"])).days - alvo)) if velhas else None


def _executar(pl):
    from core import registro_ferramentas
    return lambda n, a: registro_ferramentas.executar(n, a, pl)


def garantir_foto_do_mes(pl=None) -> bool:
    fotos = carregar("eu_do_passado", [])
    if fotos and fotos[-1]["dia"][:7] == date.today().isoformat()[:7]:
        return False
    fotos.append(tirar_foto(_executar(pl)))
    guardar("eu_do_passado", fotos[-36:])
    return True


def _go(p, pl):
    a, fotos = p["action"], carregar("eu_do_passado", [])
    if a == "fotografias":
        return "\n".join(f"{f['dia']}: {', '.join(f['partes'])}" for f in fotos) or "Nenhuma fotografia ainda."
    if a == "fotografar":
        fotos.append(tirar_foto(_executar(pl)))
        guardar("eu_do_passado", fotos[-36:])
        return f"Fotografia de hoje guardada ({len(fotos[-1]['partes'])} assuntos). Daqui a uns meses dá para conversar com este você."
    garantir_foto_do_mes(pl)
    meses = num1(p, "meses", 6)
    foto = mais_perto(carregar("eu_do_passado", []), meses, date.today())
    if not foto:
        return ("Ainda não tenho uma fotografia sua com mais de um mês. Já tirei a de hoje: a partir do mês que vem dá para "
                "conversar com o você de agora.")
    dias = (date.today() - date.fromisoformat(foto["dia"])).days
    retrato = "\n".join(f"[{k}] {v}" for k, v in foto["partes"].items())
    from core import gemini
    if a == "mudou":
        agora = tirar_foto(_executar(pl))["partes"]
        pedido = (f"Compare o retrato do usuário de {dias} dias atrás com o de hoje e diga, em até 5 frases calorosas e "
                  f"concretas, o que mudou, o que ele conquistou e o que ficou pelo caminho.\n\nANTES ({foto['dia']}):\n{retrato}\n\n"
                  f"HOJE:\n" + "\n".join(f"[{k}] {v}" for k, v in agora.items()))
    else:
        pergunta = str(p.get("pergunta") or "Oi! Como você está e o que você quer para o futuro?")
        pedido = (f"Você é o PRÓPRIO usuário, como ele era em {foto['dia']} (há {dias} dias). Fale em primeira pessoa, no jeito "
                  "dele, curto (até 4 frases), usando SÓ o que está no retrato abaixo; se o retrato não cobre o assunto, diga "
                  "'naquela época eu nem pensava nisso'. Não invente lembranças nem fatos. Quem pergunta é o você do futuro.\n\n"
                  f"RETRATO:\n{retrato}\n\nPERGUNTA DO VOCÊ DO FUTURO: {pergunta}")
    r = gemini.text(pedido, tier=gemini.SMART, default="")
    if not r:
        return "Não consegui abrir o portal agora (preciso da chave do Gemini e de internet)."
    quem = f"o você de {round(dias / 30.4)} mês(es) atrás" if a == "conversar" else "comparando"
    return f"[{quem}, {foto['dia']}] {r}"


def on_session_start(player) -> None:
    from core import relogio                         # 3.0: relógio central, sem thread própria
    relogio.agendar("eu_do_passado", lambda: garantir_foto_do_mes(player), a_cada_s=6 * 3600, primeira_em_s=120)


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("conversar mudou fotografar fotografias".split(), _go), player, "Eu do passado")
