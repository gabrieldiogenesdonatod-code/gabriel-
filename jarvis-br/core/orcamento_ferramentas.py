"""
Orçamento de ferramentas (fork PT-BR 2.2).

O JARVIS passou de 140 ferramentas. Mandar todas para o Gemini Live de uma vez
pesa muito no início da conversa (dezenas de milhares de tokens) e pode passar
do limite de declarações que o modelo aceita, e aí a sessão não abre ou as
ferramentas novas somem.

Aqui ficam as N mais importantes como ferramentas de verdade: as do núcleo,
as fixas (música, WhatsApp, aparelhos…) e as que você mais usa. Todas as
outras continuam funcionando por UMA ferramenta de apoio, `outras_ferramentas`,
que traz a lista delas (nome, parâmetros e para que serve) e repassa o pedido.
A verificação do dono e o registro de uso enxergam o nome verdadeiro.

O limite muda em config/api_keys.json: "limite_ferramentas": 80 (0 = sem limite).

Fork PT-BR 2.19 — catálogo sob demanda: a lista completa das extras passava de 8 mil tokens em
toda sessão (~45 por ferramenta). Agora só as 24 extras mais usadas levam a descrição; as outras
entram pelo nome e o modelo consulta o plugin `catalogo` quando precisa ("catalogo_completas").
"""

from __future__ import annotations

import json
import time

NOME_APOIO = "outras_ferramentas"
LIMITE_PADRAO = 80

# Sempre como ferramenta de verdade (o que se pede todo dia).
FIXAS = (
    "musica", "whatsapp_jarvis", "mensageiros", "companheiro", "aparelhos", "acesso_remoto", "controle_pc",
    "controle_audio_video", "controle_sistema", "monitor_sistema", "jogos", "xadrez", "memoria_projeto",
    "agendador", "pomodoro", "briefing_br", "cristal_malhas", "gastos", "protocolos", "casa_inteligente",
    "rosto_flutuante", "olha_isso", "quando_voltar", "sentinela", "verificacao", "personas", "notificacoes",
    "linha_do_tempo", "gestos", "ditado", "resumo_video", "jarvis_dj", "app_celular", "modo_jogo", "limpeza",
    "downloads", "macros", "companheiro_jogo", "gamificacao", "snapshots", "testes_vivos", "tela_ao_vivo",
    "whatsapp_conversas",                                     # 2.3
    "memoria_grafo", "missoes", "diario", "estado_mundo",     # 2.4
    "contas", "rastreio", "ideias", "chuva", "holograma_mao",  # 2.5
    "vitrine",                                                # 2.6
    "jarvis_friday", "cinema",                                # 2.7
    "modo_dormir",                                            # 2.8: "vai dormir" / "vou dormir" todo dia
    "por_que_fechou",                                         # 2.8.1: "por que você fechou?"
    "ia_local", "cerebro",                                    # 3.5.1: "instala a IA local" ia para a pesquisa na web
    "omega",                                                  # 3.6: a porta de entrada dos sistemas novos (cita os outros)
)


def nome_de(d) -> str:
    return d.get("name", "") if isinstance(d, dict) else getattr(d, "name", "")


def assinatura(d: dict) -> str:
    """'musica(action, pedido, servico): Music by voice…' (pura)."""
    props = ((d.get("parameters") or {}).get("properties") or {}) if isinstance(d, dict) else {}
    desc = str(d.get("brief") or d.get("description") or "") if isinstance(d, dict) else ""
    desc = " ".join(desc.split())
    if len(desc) > 150:
        desc = desc[:147].rsplit(" ", 1)[0] + "…"
    acoes = ""
    a = props.get("action") or {}
    if a.get("description") and "|" in a["description"]:
        acoes = f" [action: {a['description'][:90]}]"
    return f"{nome_de(d)}({', '.join(props)}){acoes}: {desc}"


COMPLETAS_PADRAO = 24       # extras que aparecem com parâmetros e descrição (as mais usadas)


def completas_configuradas() -> int:
    """config/api_keys.json: "catalogo_completas": 24 (-1 = todas, como era até a 2.18)."""
    try:
        from memory.config_manager import load_api_keys
        return int(load_api_keys().get("catalogo_completas", COMPLETAS_PADRAO))
    except Exception:
        return COMPLETAS_PADRAO


def declaracao_apoio(extras: list[dict], uso: dict[str, int] | None = None, completas: int | None = None) -> dict:
    """Fork PT-BR 2.19: catálogo sob demanda. Só as extras mais usadas levam a assinatura completa;
    as outras entram pelo nome (~4 tokens cada, em vez de ~45) e o modelo pede os detalhes quando
    precisar: parametros='?' mostra como usar uma, buscar='…' procura pela necessidade."""
    uso = uso or {}
    n = completas_configuradas() if completas is None else completas
    if n < 0 or len(extras) <= n:
        cheias, resto = list(extras), []
    else:
        ordem = sorted(range(len(extras)), key=lambda i: (-uso.get(nome_de(extras[i]), 0), i))
        topo = set(ordem[:n])
        cheias = [d for i, d in enumerate(extras) if i in topo]
        resto = [d for i, d in enumerate(extras) if i not in topo]
    desc = ("Runs one of JARVIS's EXTRA tools that are not listed separately. Pass nome = the tool name and "
            "parametros = a JSON object string with its parameters (same names as in the list). Use it exactly like "
            "calling that tool directly.")
    if cheias:
        desc += " Extra tools:\n" + "\n".join(assinatura(d) for d in cheias)
    if resto:
        desc += ("\nMORE extra tools, listed by name only. Before the first use of one of them, call with nome=<name> "
                 "and parametros='?' to get its parameters, then call it. To find the right tool for a request, call "
                 "with buscar='what the user wants, in Portuguese'. Never say you cannot do something before searching. "
                 "Names: " + ", ".join(nome_de(d) for d in resto))
    return {
        "name": NOME_APOIO,
        "description": desc,
        "parameters": {
            "type": "OBJECT",
            "properties": {"nome": {"type": "STRING", "description": "extra tool name, e.g. quiz_geek"},
                           "parametros": {"type": "STRING", "description": "JSON object with the tool's parameters, "
                                                                           "or '?' to see how to use it"},
                           "buscar": {"type": "STRING", "description": "search the extra tools by need"}},
        },
    }


def dividir(decls: list, limite: int, uso: dict[str, int] | None = None,
            fixas: tuple[str, ...] = FIXAS, protegidas: set[str] | None = None) -> tuple[list, list]:
    """(mantidas, extras). `protegidas` (núcleo e ações) nunca saem. Puro."""
    if not limite or len(decls) <= limite:
        return list(decls), []
    uso = uso or {}
    protegidas = protegidas or set()
    vagas = max(1, limite - 1)                                  # uma vaga é da ferramenta de apoio
    ordem_fixa = {n: i for i, n in enumerate(fixas)}

    def prioridade(item):
        i, d = item
        n = nome_de(d)
        if n in protegidas:
            return (0, i)
        if n in ordem_fixa:
            return (1, ordem_fixa[n])
        return (2, -uso.get(n, 0), i)

    ordenadas = sorted(enumerate(decls), key=prioridade)
    manter_idx = {i for i, _d in ordenadas[:vagas]}
    mantidas = [d for i, d in enumerate(decls) if i in manter_idx]
    extras = [d for i, d in enumerate(decls) if i not in manter_idx and isinstance(d, dict)]
    return mantidas, extras


def uso_recente(dias: int = 30) -> dict[str, int]:
    try:
        from core import registro_uso
        cont: dict[str, int] = {}
        for c in registro_uso.chamadas(time.time() - dias * 86400):
            cont[c["ferramenta"]] = cont.get(c["ferramenta"], 0) + 1
        return cont
    except Exception:
        return {}


def limite_configurado() -> int:
    try:
        from memory.config_manager import load_api_keys
        v = load_api_keys().get("limite_ferramentas", LIMITE_PADRAO)
        return max(0, int(v))
    except Exception:
        return LIMITE_PADRAO


def aplicar(decls: list, protegidas: set[str]) -> tuple[list, set[str]]:
    """Declarações para mandar ao Gemini + nomes que foram para a ferramenta de apoio."""
    uso = uso_recente()
    mantidas, extras = dividir(decls, limite_configurado(), uso, protegidas=protegidas)
    if not extras:
        return mantidas, set()
    apoio = declaracao_apoio(extras, uso)
    print(f"[Ferramentas] {len(mantidas)} diretas + {len(extras)} pela ferramenta '{NOME_APOIO}' "
          f"(catálogo ≈ {len(apoio['description']) // 4} tokens)")
    return mantidas + [apoio], {nome_de(d) for d in extras}


def desembrulhar(nome: str, args: dict) -> tuple[str, dict]:
    """outras_ferramentas(nome='quiz_geek', parametros='{"tema": "anime"}') → ('quiz_geek', {...}) (pura).
    2.19: buscar='…' e parametros='?' viram chamadas ao plugin `catalogo`."""
    if nome != NOME_APOIO:
        return nome, args
    real = str(args.get("nome") or "").strip()
    p = args.get("parametros") or {}
    busca = str(args.get("buscar") or "").strip()
    if busca and not real:
        return "catalogo", {"action": "buscar", "texto": busca}
    if isinstance(p, str) and p.strip().lower() in ("?", "ajuda", "help"):
        return "catalogo", {"action": "ajuda", "nome": real}
    if isinstance(p, str):
        try:
            p = json.loads(p) if p.strip() else {}
        except ValueError:
            p = {"action": p.strip()} if p.strip() else {}
    return real, (p if isinstance(p, dict) else {})
