"""
Parceiro de rima (fork PT-BR 1.6).

Para quem escreve rap: conta as sílabas poéticas de cada verso (a métrica),
mostra o esquema de rimas (AABB, ABAB…), aponta versos fora do ritmo e sugere
rimas para uma palavra (rimas perfeitas e toantes), também com as palavras das
suas próprias letras. Com a chave do Gemini, sugere versos inteiros no tema.

    "Jarvis, rima com 'coração'"
    "Jarvis, analisa minha letra"      (cole a letra, ou ele lê a área de transferência)
    "Jarvis, me dá um verso sobre superação que rime com 'caminho'"
    "Jarvis, guarda essa letra"        (as suas palavras viram sugestões de rima)
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from plugins._comum import MEMORIA, gravar_json, ler_json, mostrar

PLUGIN = {
    "name": "parceiro_rima",
    "brief": "Rap writing partner: syllable count (meter), rhyme scheme, rhyme suggestions, verses with AI.",
    "description": (
        "Rhyme partner for rap lyrics. action='rimas' with palavra (rhymes, perfect and slant); 'analisar' with texto "
        "(lyrics; without texto reads the clipboard: syllables per line, rhyme scheme, lines off the beat); 'verso' "
        "with tema + palavra (AI writes lines ending in a rhyme); 'guardar' with texto (keeps the user's lyrics so "
        "their own words become suggestions)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "rimas | analisar | verso | guardar"},
                       "palavra": {"type": "STRING"}, "texto": {"type": "STRING"}, "tema": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "rimas.json"
VOGAIS = "aeiou"
# palavras comuns em letras de rap, para ter sugestão mesmo sem IA
LEXICO = """
coração razão missão visão paixão perdão chão irmão mão solidão união canção multidão ilusão emoção pressão
caminho sozinho carinho espinho destino menino ninho vizinho moinho linho
vida corrida ferida saída medida querida batida partida bebida comida
mundo segundo profundo fundo vagabundo imundo
luta disputa escuta labuta conduta bruta
sonho medonho tristonho risonho
dor amor valor calor favor clamor rancor suor cor flor senhor setor
fé pé maré café até jacaré
noite açoite
guerra terra serra erra
fogo jogo logo rogo
rua lua sua nua crua
tempo vento momento talento lamento pensamento sentimento argumento
verdade saudade cidade vontade liberdade humildade realidade maldade idade
gente frente mente semente quente presente valente
quebrada estrada jornada caminhada parada calçada madrugada nada
favela panela janela vela sentinela tela
corre sorte morte norte forte suporte transporte
batalha navalha muralha medalha canalha
treta caneta planeta meta letra
dinheiro inteiro guerreiro primeiro parceiro verdadeiro brasileiro
""".split()


def _dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()


def silabas(palavra: str) -> list[str]:
    """Separação silábica aproximada do português (boa o bastante para métrica) (pura)."""
    p = re.sub(r"[^a-záàâãéêíóôõúüç]", "", (palavra or "").lower())
    if not p:
        return []
    p = re.sub(r"ã[oe]", "ã", re.sub(r"õe", "õ", p))          # "ão", "ãe", "õe" são ditongos, não hiatos
    base = _dobrar(p)
    grupos = re.findall(r"[^aeiou]*[aeiou]+(?:[^aeiou]*$)?", base)
    if not grupos:
        return [p]
    # separa hiatos comuns: duas vogais "fortes" seguidas (a, e, o) e i/u tônicos marcados
    saida = []
    for g in grupos:
        m = re.search(r"[aeiou]+", g)
        nucleo = m.group(0) if m else ""
        if len(nucleo) >= 2 and re.search(r"[aeo][aeo]", nucleo):
            corte = m.start() + re.search(r"[aeo][aeo]", nucleo).start() + 1
            saida += [g[:corte], g[corte:]]
        else:
            saida.append(g)
    return saida


def silabas_poeticas(verso: str) -> int:
    """Conta até a última sílaba tônica e junta vogais entre palavras (sinalefa) (pura)."""
    palavras = re.findall(r"[\wÀ-ÿ]+", verso or "")
    if not palavras:
        return 0
    total = sum(len(silabas(w)) for w in palavras)
    for a, b in zip(palavras, palavras[1:]):                  # "de amor" → "deamor"
        if _dobrar(a)[-1:] in VOGAIS and _dobrar(b)[:1] in VOGAIS + "h":
            total -= 1
    ultima = _dobrar(palavras[-1])
    sil = silabas(palavras[-1])
    if len(sil) >= 2 and not re.search(r"[áéíóúâêô]|(r|l|z|x|n|i|u|im|um|om|ns)$", palavras[-1].lower()) \
            and re.search(r"[aeo]s?$|em$|am$", ultima):
        total -= 1                                            # paroxítona: não conta a última átona
    return max(1, total)


def terminacao(palavra: str) -> str:
    """Parte que rima: da vogal tônica até o fim (aproximada) (pura)."""
    w = re.sub(r"[^\wÀ-ÿ]", "", (palavra or "").lower())
    if not w:
        return ""
    acento = re.search(r"[áéíóúâêôãõ][^áéíóúâêôãõ]*$", w)
    if acento:
        return _dobrar(w[acento.start():])
    base = _dobrar(w)
    vog = [m.start() for m in re.finditer(r"[aeiou]", base)]
    if not vog:
        return base
    oxitona = re.search(r"(r|l|z|x|i|u|im|um|om|ns|is|us)$", base) or len(vog) == 1
    i = vog[-1] if oxitona else (vog[-2] if len(vog) >= 2 else vog[-1])
    if not oxitona and len(vog) >= 2 and vog[-1] - vog[-2] == 1:    # ditongo final: "histórias"
        i = vog[-3] if len(vog) >= 3 else vog[-2]
    return base[i:]


def toante(palavra: str) -> str:
    return re.sub(r"[^aeiou]", "", terminacao(palavra))


def rimam(a: str, b: str) -> str:
    """'perfeita', 'toante' ou '' (pura)."""
    if _dobrar(a) == _dobrar(b):
        return ""
    if terminacao(a) and terminacao(a) == terminacao(b):
        return "perfeita"
    return "toante" if toante(a) and toante(a) == toante(b) else ""


def esquema(versos: list[str]) -> str:
    """'AABB'… pela última palavra de cada verso (pura)."""
    letras, finais = [], []
    for v in versos:
        palavras = re.findall(r"[\wÀ-ÿ]+", v)
        fim = palavras[-1] if palavras else ""
        idx = next((i for i, f in enumerate(finais) if rimam(f, fim) or _dobrar(f) == _dobrar(fim)), None)
        if idx is None:
            finais.append(fim)
            idx = len(finais) - 1
        letras.append(chr(65 + idx % 26))
    return "".join(letras)


def sugerir(palavra: str, extras: list[str]) -> tuple[list[str], list[str]]:
    cands = list(dict.fromkeys(LEXICO + extras))
    perfeitas = [w for w in cands if rimam(palavra, w) == "perfeita"]
    toantes = [w for w in cands if rimam(palavra, w) == "toante"]
    return perfeitas[:20], toantes[:12]


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "rimas").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        minhas = d.get("palavras", [])
        if acao == "guardar":
            texto = str(p.get("texto") or "")
            novas = [w.lower() for w in re.findall(r"[\wÀ-ÿ]{3,}", texto)]
            d["palavras"] = list(dict.fromkeys(minhas + novas))[-3000:]
            d.setdefault("letras", []).append(texto[:5000])
            gravar_json(_ARQ, d)
            return f"Guardei a letra ({len(novas)} palavras). Elas entram nas sugestões de rima."
        if acao == "analisar":
            texto = str(p.get("texto") or "")
            if not texto:
                from plugins.olha_isso import _clipboard
                texto = _clipboard()
            versos = [v.strip() for v in texto.splitlines() if v.strip()]
            if not versos:
                return "Cole a letra (ou copie e peça de novo)."
            contas = [silabas_poeticas(v) for v in versos]
            esq = esquema(versos)
            moda = Counter(contas).most_common(1)[0][0]
            fora = [i + 1 for i, c in enumerate(contas) if abs(c - moda) >= 3]
            mostrar(player, "ANÁLISE DA LETRA", "\n".join(f"{esq[i]}  {contas[i]:>2}  {v}" for i, v in enumerate(versos))
                    + f"\n\nEsquema: {esq} · métrica mais comum: {moda} sílabas"
                    + (f"\nVersos fora do ritmo: {', '.join(map(str, fora))}" if fora else ""))
            return (f"{len(versos)} versos, esquema {esq[:16]}, a maioria com {moda} sílabas"
                    + (f"; os versos {', '.join(map(str, fora[:6]))} fogem do ritmo" if fora else "; ritmo bem regular")
                    + ". Detalhes no painel.")
        palavra = str(p.get("palavra") or "").strip()
        if acao == "verso":
            from plugins import _ia
            if not _ia.disponivel():
                return "Para escrever versos preciso da chave do Gemini; posso sugerir rimas: diga 'rima com …'."
            r = _ia.perguntar(f"Escreva 4 versos de rap em português do Brasil sobre '{p.get('tema') or 'superação'}', "
                              f"com métrica parecida e rimas" + (f", terminando com rima em '{palavra}'" if palavra else "")
                              + ". Só os versos, um por linha.", False, 30) or ""
            return f"Versos: {r}" if r else "Não consegui os versos agora."
        if not palavra:
            return "Rima com qual palavra?"
        perfeitas, toantes = sugerir(palavra, minhas)
        if not perfeitas and not toantes:
            from plugins import _ia
            if _ia.disponivel():
                r = _ia.perguntar(f"Liste 15 rimas em português para '{palavra}' (perfeitas primeiro), só as palavras "
                                  "separadas por vírgula.", False, 20)
                if r:
                    return f"Rimas com {palavra}: {r}"
            return f"Não achei rimas para '{palavra}' no meu vocabulário (termina em '{terminacao(palavra)}')."
        return (f"Rima com {palavra} ({len(silabas(palavra))} sílabas): " + ", ".join(perfeitas)
                + (f". Toantes: {', '.join(toantes)}" if toantes else "") + ".")
    except Exception as e:
        return f"O parceiro de rima falhou: {e}"
