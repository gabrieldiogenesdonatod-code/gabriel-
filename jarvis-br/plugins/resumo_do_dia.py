"""Resumo do dia (2.19): junta num relato só o que está pendente hoje em todos os plugins (água, hábitos, contas, loja…)."""
from __future__ import annotations

import re

from plugins._lote2 import P, rodar

PLUGIN = P("resumo_do_dia", "One spoken summary of what's pending today across plugins: habits, water, countdowns, bills, pets, pantry, reviews, store.",
           "agora | completo", "agora: only what needs attention. completo: every section.", "")

# (título, ferramenta, parâmetros)
SECOES = [("Sonho desta noite", "sonhos", {"action": "ultimo"}), ("Hábitos", "sequencias", {"action": "hoje"}), ("Água", "hidratacao", {"action": "hoje"}),
          ("Cardápio", "cardapio", {"action": "hoje"}), ("Revisões", "revisao_espacada", {"action": "hoje"}),
          ("Contagens", "calculadora_datas", {"action": "contagens"}), ("Assinaturas", "assinaturas", {"action": "proximas"}),
          ("Vencimentos", "vencimentos", {"action": "proximos"}), ("Despensa", "despensa", {"action": "vencendo"}),
          ("Pets", "pets", {"action": "vencendo"}), ("Lista de espera", "lista_espera", {"action": "pendentes"}),
          ("Pedidos", "fornecedores", {"action": "pendentes"}), ("Metas", "metas_pessoais", {"action": "listar"}),
          ("Emprestados", "emprestimos", {"action": "lista"})]
NADA = re.compile(r"^(nenhum|ningu|nada|sem |ainda n|sonhei com os seus n|lista vazia|tudo feito|n[aã]o |despensa em dia|configure)", re.I)


def montar(executar, completo: bool = False) -> list[str]:
    """executar(nome, params) -> texto. Devolve as linhas que valem a pena falar. Pura."""
    out = []
    for titulo, nome, params in SECOES:
        try:
            r = str(executar(nome, params)).strip()
        except Exception:
            continue
        if r and (completo or not NADA.match(r)) and "não existe" not in r:
            out.append(f"{titulo}: {r}")
    return out


def _go(p, pl):
    from core import registro_ferramentas
    linhas = montar(lambda n, a: registro_ferramentas.executar(n, a, pl), p["action"] == "completo")
    return "\n".join(linhas) or "Nada pendente hoje, senhor. Dia livre."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"agora": _go, "completo": _go}, player, "Resumo do dia")
