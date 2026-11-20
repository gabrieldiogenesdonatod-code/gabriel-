"""
Livro da vó (3.0): toda semana o JARVIS sugere UMA pergunta para você fazer à sua vó. Você conta a
resposta (falando ou digitando) e ele vai montando um livro de memórias, com capítulos, pronto
para imprimir.

    "Jarvis, qual a pergunta da semana para a vó?"
    "Jarvis, a vó respondeu: 'Eu morava num sítio perto de Trindade…'"
    "Jarvis, gera o livro da vó."

As respostas ficam guardadas do jeito que ela falou. Nada sai do seu computador.
"""

from __future__ import annotations

import html
import time

from plugins._lote2 import P, carregar, guardar, norm, pagina, rodar

PLUGIN = P("livro_vo", "Grandma's memory book: a weekly question to ask her, her answers saved in her words, printable book with chapters.",
           "pergunta | responder | outra | livro | progresso",
           "pergunta: this week's question (capitulo optional). responder: texto (her answer, in her words). outra: skip to "
           "another question. livro: generate the printable book (titulo optional).",
           "texto capitulo titulo")

CAPITULOS = {
    "Infância": ["Onde a senhora nasceu e como era a casa?", "Do que a senhora mais gostava de brincar?", "Como era a sua mãe? E o seu pai?",
                 "Qual a primeira lembrança que a senhora tem?", "A senhora ia para a escola? Como era?", "Qual era a comida da sua infância?"],
    "Família": ["Como a senhora conheceu o vô?", "Como foi o dia do seu casamento?", "Como foi quando nasceu o seu primeiro filho?",
                "Qual história da família todo mundo conta até hoje?", "Quem foi a pessoa mais importante da sua vida?"],
    "Juventude": ["O que a senhora fazia nos fins de semana quando era moça?", "Qual música tocava no rádio na sua juventude?",
                  "Qual foi a maior aventura que a senhora já viveu?", "O que a senhora sonhava ser quando crescesse?"],
    "Trabalho": ["Qual foi o seu primeiro trabalho?", "Qual trabalho a senhora mais gostou de fazer?", "Qual foi a fase mais difícil e como passou por ela?"],
    "Goiânia de antigamente": ["Como era Goiânia (ou a sua cidade) quando a senhora era jovem?", "O que tinha onde hoje é o centro?",
                               "Como as pessoas se divertiam na cidade?", "O que mudou que a senhora sente falta?"],
    "Casa e cozinha": ["Qual receita a senhora faz que ninguém faz igual? Me ensina o segredo?", "Qual era o prato de domingo?",
                       "Qual remédio caseiro a sua mãe usava?", "Como era um dia comum na sua casa?"],
    "O que a vida ensinou": ["Qual o melhor conselho que a senhora já recebeu?", "Do que a senhora tem mais orgulho?",
                             "O que a senhora faria diferente?", "O que é felicidade para a senhora?"],
    "Para os netos": ["O que a senhora quer que os netos nunca esqueçam?", "Que conselho a senhora daria para mim?",
                      "Como a senhora quer ser lembrada?"],
}
TODAS = [(c, q) for c, qs in CAPITULOS.items() for q in qs]


def proxima(respondidas: set[str], pulada: str = "", capitulo: str = "") -> tuple[str, str] | None:
    """A próxima pergunta sem resposta, alternando capítulos. Pura."""
    pendentes = [(c, q) for c, q in TODAS if q not in respondidas and q != pulada and (not capitulo or norm(capitulo) in norm(c))]
    if not pendentes:
        return None
    por_cap = {}
    for c, q in pendentes:
        por_cap.setdefault(c, []).append(q)
    feitos = {c: sum(q in respondidas for q in qs) for c, qs in CAPITULOS.items()}
    cap = min(por_cap, key=lambda c: (feitos[c], list(CAPITULOS).index(c)))
    return cap, por_cap[cap][0]


def montar_livro(respostas: list[dict], titulo: str) -> str:
    corpo = ["<div style='text-align:center;margin:80px 0'><h1 style='font-size:40px'>" + html.escape(titulo) + "</h1>"
             f"<p>Memórias contadas a mim, {time.strftime('%Y')}</p></div>"]
    for cap in CAPITULOS:
        doc = [r for r in respostas if r["capitulo"] == cap]
        if not doc:
            continue
        corpo.append(f"<h2 style='page-break-before:always'>{html.escape(cap)}</h2>")
        for r in doc:
            corpo.append(f"<p><i>{html.escape(r['pergunta'])}</i></p><p style='font-size:18px;line-height:1.6'>"
                         f"{html.escape(r['resposta'])}</p><p style='color:#777;font-size:12px'>{r['quando']}</p>")
    return "".join(corpo)


def passo(player) -> None:
    est = carregar("livro_vo", {"respostas": [], "ultima_sugestao": 0, "atual": None})
    agora = time.localtime()
    if agora.tm_wday == 6 and 10 <= agora.tm_hour < 18 and time.time() - est.get("ultima_sugestao", 0) > 6 * 86400:
        prox = proxima({r["pergunta"] for r in est["respostas"]})
        if prox:
            est["atual"], est["ultima_sugestao"] = list(prox), time.time()
            guardar("livro_vo", est)
            from plugins._comum import avisar
            avisar(player, f"Pergunta da semana para a vó: {prox[1]}", "LIVRO DA VÓ")


def on_session_start(player) -> None:
    from core import relogio
    relogio.agendar("livro_vo", lambda: passo(player), a_cada_s=3 * 3600, primeira_em_s=600)


def _go(p, pl):
    a, est = p["action"], carregar("livro_vo", {"respostas": [], "ultima_sugestao": 0, "atual": None})
    feitas = {r["pergunta"] for r in est["respostas"]}
    if a == "progresso":
        return (f"{len(est['respostas'])} de {len(TODAS)} memórias guardadas. " +
                ", ".join(f"{c}: {sum(r['capitulo'] == c for r in est['respostas'])}/{len(q)}" for c, q in CAPITULOS.items()) + ".")
    if a == "livro":
        if not est["respostas"]:
            return "Ainda não há respostas. Comece pela pergunta da semana."
        titulo = str(p.get("titulo") or "As memórias da minha vó")
        arq = pagina("Livro da vo", titulo, montar_livro(est["respostas"], titulo))
        return f"O livro tem {len(est['respostas'])} memória(s) em {len({r['capitulo'] for r in est['respostas']})} capítulo(s). Abri para imprimir: {arq}"
    if a == "responder":
        texto = str(p.get("texto") or "").strip()
        if len(texto) < 3:
            return "Qual foi a resposta dela? Pode ditar do jeito que ela falou."
        cap, perg = est.get("atual") or proxima(feitas) or ("Para os netos", "Memória livre")
        est["respostas"].append({"capitulo": cap, "pergunta": perg, "resposta": texto, "quando": time.strftime("%d/%m/%Y")})
        est["atual"] = None
        guardar("livro_vo", est)
        return f"Guardei a resposta no capítulo {cap}. Já são {len(est['respostas'])} memória(s). Que lindo. 💛"
    pulada = est["atual"][1] if a == "outra" and est.get("atual") else ""
    prox = proxima(feitas, pulada, str(p.get("capitulo") or ""))
    if not prox:
        return "Todas as perguntas foram respondidas! Diga 'gera o livro da vó'."
    est["atual"] = list(prox)
    guardar("livro_vo", est)
    return f"Pergunta para a vó ({prox[0]}): {prox[1]}"


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("pergunta responder outra livro progresso".split(), _go), player, "Livro da vó")
