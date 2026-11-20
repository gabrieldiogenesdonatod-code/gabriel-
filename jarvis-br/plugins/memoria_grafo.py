"""
Memória em grafo com busca por significado (fork PT-BR 2.4) — veja core/memoria_grafo.py.

    "Jarvis, o que eu decidi sobre o capacete?"      (acha pelo significado)
    "Jarvis, lembra que escolhi o ESP32-S3 para o capacete"
    "Jarvis, o que está ligado à Cristal Malhas?"
    "Jarvis, abre o mapa da memória"
    "Jarvis, importa as memórias para o grafo"       (traz a memória antiga, a da 1.4 e o diário)
    "Jarvis, treina a rede da memória"              (a rede neural local aprende com tudo)
"""

from __future__ import annotations

import threading
import time

from core import memoria_grafo as G
from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "memoria_grafo",
    "brief": "Graph memory with meaning-based search (people, projects, products, places, decisions linked).",
    "description": (
        "Long-term graph memory with semantic search. Use action='perguntar' with pergunta whenever the user asks "
        "about something from his past (what he decided, said, planned, who/what is related) — it finds it by "
        "meaning, not exact words, and returns dated notes; answer from them and say the date. 'lembrar' with texto "
        "stores a fact/decision (links people, projects, products, places automatically); 'conexoes' with nome shows "
        "what is linked to a person/project/product; 'mapa' opens the visual memory map; 'importar' brings old "
        "memories in; 'treinar' retrains the local neural network; 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "perguntar | lembrar | conexoes | mapa | importar | "
                                                                    "treinar | status"},
                       "pergunta": {"type": "STRING"}, "texto": {"type": "STRING"}, "nome": {"type": "STRING"}},
        "required": [],
    },
}

ARQ_META = MEMORIA / "memoria_grafo_meta.json"
_iniciou = threading.Event()


def _fundo(player) -> None:
    """Na abertura: importa o que for novo e retreina a rede se a memória cresceu 20%."""
    try:
        novos = G.importar(usar_ia=False)
        meta = ler_json(ARQ_META, {}) or {}
        fatos = G.estatisticas()["tipos"].get("fato", 0)
        if fatos >= 15 and (not G.ARQ_REDE.exists() or fatos >= 1.2 * meta.get("fatos_no_treino", 0) + 1):
            r = G.treinar_rede()
            meta.update(fatos_no_treino=fatos, treinada_em=time.time())
            gravar_json(ARQ_META, meta)
            print(f"[MemóriaGrafo] {r}")
        if novos:
            print(f"[MemóriaGrafo] {novos} lembrança(s) nova(s) no grafo")
    except Exception as e:
        print(f"[MemóriaGrafo] {e}")


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_fundo, args=(player,), daemon=True, name="memoria_grafo").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "perguntar").lower()
    try:
        if acao == "lembrar":
            texto = str(p.get("texto") or "").strip()
            if not texto:
                return "O que eu guardo?"
            r = G.lembrar(texto, "voce")
            if r.get("repetida"):
                return "Isso eu já sabia; reforcei a lembrança."
            ents = ", ".join(r.get("entidades") or [])
            return "Guardado" + (f", ligado a: {ents}." if ents else ".")
        if acao == "conexoes":
            nome = str(p.get("nome") or p.get("pergunta") or "").strip()
            c = G.conexoes(nome)
            if not c:
                return f"Não tenho '{nome}' no grafo ainda."
            ligados = ", ".join(x["nome"] for x in c["ligados"][:10]) or "nada"
            fatos = G.resumo_resultados(c["fatos"][:6]) if c["fatos"] else "nenhuma lembrança"
            texto = f"{c['no']['nome']} ({c['no']['tipo']}) está ligado a: {ligados}.\nLembranças:\n{fatos}"
            mostrar(player, f"MEMÓRIA — {c['no']['nome']}", texto)
            return texto
        if acao == "mapa":
            from plugins import _arcade
            return "Abri o mapa da memória." if _arcade.abrir_pagina("/grafo", 1280, 860) else \
                "Não consegui abrir o mapa (precisa do Edge ou do Chrome)."
        if acao == "importar":
            n = G.importar(usar_ia=bool(p.get("texto") == "ia"))
            return f"Importei {n} lembrança(s) nova(s) para o grafo." if n else "Nada novo para importar."
        if acao == "treinar":
            threading.Thread(target=lambda: registrar(player, f"Memória: {G.treinar_rede()}"), daemon=True).start()
            return "Comecei a treinar a rede neural da memória; aviso no registro quando terminar (leva até um minuto)."
        if acao == "status":
            e = G.estatisticas()
            t = e["tipos"]
            rede = f"rede neural com {e['rede']['palavras']} palavras" if e["rede"] else "rede neural ainda não treinada"
            sem = "embeddings do Gemini ativos" if any(k != "local" for k in e["vetores"]) else "sem embeddings do Gemini"
            return (f"{t.get('fato', 0)} lembranças, {sum(v for k, v in t.items() if k != 'fato')} coisas ligadas "
                    f"(pessoas, projetos, produtos, lugares), {e['arestas']} ligações; {rede}; {sem}.")
        pergunta = str(p.get("pergunta") or p.get("texto") or "").strip()
        if not pergunta:
            return "O que você quer lembrar?"
        res = G.buscar(pergunta, 5)
        if not res:
            return "Não achei nada parecido na memória."
        return ("Lembranças mais parecidas (a primeira é a mais provável; use a data):\n" + G.resumo_resultados(res))
    except Exception as e:
        return f"A memória em grafo falhou: {e}"
