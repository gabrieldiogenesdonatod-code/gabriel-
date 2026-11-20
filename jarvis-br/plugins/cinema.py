"""
Sessão de cinema (fork PT-BR 2.7). Tudo software, grátis.

    "Jarvis, sessão de cinema: Interestelar"     → minimiza as janelas, não perturbe, abaixa o brilho,
                                                    vinheta própria e "a sessão começa em 3, 2, 1…" (8)
    "Intervalo de 10 minutos pra pipoca"         → pausa o filme e avisa (e dá play) quando acabar (8)
    "O que eu perdi?" / "dormi uns 20 minutos"   → resume o que já passou, SEM spoiler (9)
    "Quem é esse ator?" (com o filme pausado)    → ele olha a tela e responde (10)
    "Acabou o filme" / "nota 9"                  → JARVIS e FRIDAY comentam com você (11)
    "Assisti Duna, nota 8" / "onde parei em Dark?" / "o que eu vejo agora?"   → catálogo (12)
    "Planeja uma maratona da Marvel na ordem da história"                    → lista, tempo, intervalos (13)
    "Quiz do filme"                              → 5 perguntas: você contra a FRIDAY (14)

Para o "o que eu perdi?" ele ouve o som do PC (o pacote opcional `soundcard`)
a cada 2 minutos e anota uma linha do que acontece; sem ele, olha a tela.
Tudo fica em memory/cinema.json. Precisa da chave do Gemini para resumir,
responder e montar quiz/maratona; o catálogo funciona sem.
"""

from __future__ import annotations

import io
import random
import re
import threading
import time
import unicodedata
import wave
from datetime import datetime

from plugins._comum import MEMORIA, WIN, cfg, gravar_json, ler_json, mostrar, num, powershell, registrar

PLUGIN = {
    "name": "cinema",
    "brief": "Movie night: cinema session, intermission, what did I miss (no spoilers), ask about the screen, "
             "post-movie chat, watched catalog, marathon planner, movie quiz.",
    "description": (
        "Movie night helper. action: 'sessao' (titulo: start a cinema session — minimize windows, do not disturb, "
        "dim, intro jingle, countdown, and it listens to note what happens), 'intervalo' (minutos: pause for "
        "popcorn and resume), 'perdi' (minutos optional: what happened so far, never spoilers), 'pergunta' "
        "(pergunta: looks at the paused screen and answers, e.g. who is this actor), 'fim' (nota optional: end "
        "the session, add to catalog, JARVIS and FRIDAY talk about the movie), 'conversa' (talk about a movie), "
        "'assisti' (titulo, nota, tipo filme/serie, temporada, episodio), 'onde_parei' (titulo), 'catalogo', "
        "'recomendar', 'maratona' (tema: plan a marathon in story order), 'maratona_proximo', 'quiz' (start "
        "5 questions vs FRIDAY), 'responder' (resposta), 'parar'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"}, "titulo": {"type": "STRING"}, "minutos": {"type": "NUMBER"},
            "pergunta": {"type": "STRING"}, "nota": {"type": "NUMBER"}, "tipo": {"type": "STRING"},
            "temporada": {"type": "NUMBER"}, "episodio": {"type": "NUMBER"}, "tema": {"type": "STRING"},
            "resposta": {"type": "STRING"},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "cinema",
    "title": "Sessão de cinema",
    "fields": [
        {"key": "minimizar", "label": "Minimizar as janelas ao começar", "type": "toggle", "default": True},
        {"key": "brilho", "label": "Brilho da tela na sessão (0-100; vazio = não mexe)", "type": "text",
         "default": "35"},
        {"key": "ouvir", "label": "Anotar o filme para o 'o que eu perdi?' (ouve o som do PC)", "type": "toggle",
         "default": True},
        {"key": "intervalo_maratona", "label": "Intervalo da maratona a cada N filmes", "type": "text",
         "default": "2"},
    ],
}

ARQ = MEMORIA / "cinema.json"
CICLO_S = 120          # a cada 2 min anota o que está passando
TRECHO_S = 25          # segundos de áudio ouvidos por anotação
_lock = threading.Lock()
_ouvinte = {"ligado": False}
_intervalo = {"ate": 0.0}


# ── dados ─────────────────────────────────────────────────────────────────────
SESSAO_MAX_S = 6 * 3600   # 2.7.1: sessão esquecida (JARVIS fechado no meio) não deixa o não perturbe para sempre


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("sessao", {})
    s = d["sessao"]
    if s.get("ativa") and time.time() - float(s.get("inicio") or 0) > SESSAO_MAX_S:
        s["ativa"] = False
    d.setdefault("catalogo", [])
    d.setdefault("maratona", {})
    d.setdefault("quiz", {})
    return d


def _salvar(d: dict) -> None:
    with _lock:
        gravar_json(ARQ, d)


def chave(titulo: str) -> str:
    t = unicodedata.normalize("NFKD", str(titulo or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def achar(catalogo: list[dict], titulo: str) -> dict | None:
    k = chave(titulo)
    if not k:
        return None
    for item in catalogo:
        if chave(item.get("titulo")) == k:
            return item
    for item in catalogo:
        ki = chave(item.get("titulo"))
        if k in ki or ki in k:
            return item
    return None


def registrar_assistido(catalogo: list[dict], titulo: str, nota=None, tipo: str = "", temporada=None,
                        episodio=None, quando: str | None = None) -> dict:
    """Pura: atualiza (ou cria) o item do catálogo e devolve ele."""
    item = achar(catalogo, titulo)
    if item is None:
        item = {"titulo": titulo.strip(), "tipo": "", "nota": None, "vezes": 0, "historico": []}
        catalogo.append(item)
    if tipo:
        item["tipo"] = "série" if chave(tipo).startswith("seri") else "filme"
    elif temporada or episodio:
        item["tipo"] = "série"
    elif not item.get("tipo"):
        item["tipo"] = "filme"
    if nota is not None and str(nota) != "":
        item["nota"] = max(0.0, min(10.0, num(nota)))
    if temporada or episodio:
        item["parou"] = {"temporada": int(num(temporada, 1) or 1), "episodio": int(num(episodio, 1) or 1)}
    item["vezes"] = int(item.get("vezes") or 0) + 1
    item["ultima"] = quando or datetime.now().strftime("%Y-%m-%d")
    item["historico"] = (item.get("historico") or [])[-20:] + [item["ultima"]]
    return item


def onde_parei(catalogo: list[dict], titulo: str) -> str:
    item = achar(catalogo, titulo)
    if not item:
        return f"Não tenho '{titulo}' no seu catálogo."
    if item.get("parou"):
        p = item["parou"]
        return (f"Em {item['titulo']} o senhor parou na temporada {p['temporada']}, episódio {p['episodio']} "
                f"(em {item.get('ultima', '?')}). O próximo é o episódio {p['episodio'] + 1}.")
    return f"{item['titulo']}: assistido em {item.get('ultima', '?')}" + \
        (f", nota {item['nota']:g}." if item.get("nota") is not None else ".")


def plano_maratona(filmes: list[dict], a_cada: int = 2, intervalo_min: int = 15) -> dict:
    """Pura: soma o tempo e põe intervalos. filmes = [{"titulo", "minutos"}]."""
    a_cada = max(1, int(a_cada or 2))
    itens, total = [], 0
    for i, f in enumerate(filmes):
        m = int(num(f.get("minutos"), 120) or 120)
        itens.append({"titulo": str(f.get("titulo") or f"Filme {i + 1}"), "minutos": m,
                      "ano": f.get("ano") or "", "inicio_min": total})
        total += m
        if (i + 1) % a_cada == 0 and i + 1 < len(filmes):
            itens.append({"titulo": "Intervalo", "minutos": intervalo_min, "intervalo": True, "inicio_min": total})
            total += intervalo_min
    return {"itens": itens, "total_min": total, "filmes": len(filmes)}


def horas(minutos: int) -> str:
    h, m = divmod(int(minutos), 60)
    return f"{h}h{m:02d}" if h else f"{m} min"


def linha_ate(linha: list[dict], ate_min: float | None = None, desde_min: float | None = None) -> list[dict]:
    """Pura: as anotações do filme dentro da janela pedida (nunca depois de agora → sem spoiler)."""
    return [x for x in linha if (ate_min is None or x["min"] <= ate_min) and (desde_min is None or x["min"] >= desde_min)]


def conferir(resposta: str, pergunta: dict) -> bool:
    """Pura: aceita a letra (A-D), o número (1-4) ou o texto da opção certa."""
    r = chave(resposta)
    certa = int(pergunta.get("certa", 0))
    opcoes = pergunta.get("opcoes") or []
    letras = "abcd"
    if r in (letras[certa:certa + 1], str(certa + 1), f"letra {letras[certa:certa + 1]}", f"opcao {certa + 1}"):
        return True
    return bool(opcoes) and certa < len(opcoes) and r and (r == chave(opcoes[certa]) or
                                                           (len(r) > 3 and r in chave(opcoes[certa])))


# ── sessão ────────────────────────────────────────────────────────────────────
def _brilho(valor: int | None = None) -> int | None:
    """Lê (valor=None) ou ajusta o brilho do monitor (notebooks; monitores externos costumam não aceitar)."""
    if not WIN:
        return None
    try:
        if valor is None:
            c, out = powershell("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness)"
                                ".CurrentBrightness", timeout=8)
            return int(out.strip().splitlines()[0]) if c == 0 and out.strip() else None
        c, _ = powershell("Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
                          f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1;Brightness={int(valor)}}}",
                          timeout=8)
        return int(valor) if c == 0 else None
    except Exception:
        return None


def _gravar_audio(segundos: int = TRECHO_S) -> bytes | None:
    """O som que está saindo do PC (loopback), em WAV 16 kHz mono. None sem o pacote `soundcard`."""
    try:
        import numpy as np
        import soundcard as sc
        alto = sc.default_speaker()
        mic = sc.get_microphone(id=str(alto.name), include_loopback=True)
        with mic.recorder(samplerate=16000, channels=1) as rec:
            x = rec.record(numframes=16000 * segundos)
        x = np.asarray(x, dtype="float32").reshape(-1)
        if float(np.abs(x).max() if x.size else 0) < 0.003:
            return None                                         # silêncio (filme pausado)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
        return buf.getvalue()
    except Exception:
        return None


def _tela() -> bytes | None:
    try:
        from plugins import olha_isso
        r = olha_isso.capturar(olha_isso.janela_alvo(), largura_max=1100)
        return r[0] if r else None
    except Exception:
        return None


def _anotar_uma(titulo: str, minuto: int, anterior: str) -> str | None:
    from plugins import _ia
    base = (f"Você acompanha o filme/série '{titulo}' junto com o usuário (minuto {minuto}). Em UMA ou DUAS frases "
            f"curtas em português, diga o que acontece neste trecho (quem aparece, o que fazem, o clima). "
            f"Anotação anterior: {anterior[:300] or '(nenhuma)'}. Se não der para entender, responda só 'nada'.")
    wav = _gravar_audio()
    texto = _ia.ouvir_audio(base + " Isto é o áudio do filme.", wav) if wav else None
    if not texto:
        img = _tela()
        texto = _ia.ver_imagem(base + " Isto é a tela agora.", img) if img else None
    if not texto or chave(texto) in ("nada", ""):
        return None
    return texto.strip()[:400]


def _ouvir_laco() -> None:
    while _ouvinte["ligado"]:
        t0 = time.time()
        try:
            d = dados()
            s = d["sessao"]
            if not s.get("ativa"):
                break
            if time.time() >= _intervalo["ate"]:
                minuto = int((time.time() - s["inicio"] - s.get("pausado_s", 0)) / 60)
                linha = s.setdefault("linha", [])
                texto = _anotar_uma(s.get("titulo", "o filme"), minuto, linha[-1]["texto"] if linha else "")
                if texto:
                    d = dados()
                    d["sessao"].setdefault("linha", []).append({"min": minuto, "texto": texto})
                    _salvar(d)
        except Exception as e:
            print(f"[Cinema] anotação: {e}")
        time.sleep(max(5.0, CICLO_S - (time.time() - t0)))
    _ouvinte["ligado"] = False


def sessao(titulo: str) -> str:
    c = cfg("cinema", PLUGIN_SETTINGS)
    d = dados()
    if d["sessao"].get("ativa"):
        return f"Já estamos numa sessão ({d['sessao'].get('titulo')}). Diga 'acabou o filme' para encerrar."
    anterior = None
    if str(c.get("brilho") or "").strip():
        anterior = _brilho()
        if anterior is not None:
            _brilho(int(max(0, min(100, num(c.get("brilho"), 35)))))
    d["sessao"] = {"ativa": True, "titulo": titulo or "o filme", "inicio": time.time() + 8, "pausado_s": 0,
                   "linha": [], "brilho_antes": anterior}
    _salvar(d)
    if c.get("minimizar", True):
        try:
            from plugins import _janelas
            _janelas.minimizar_tudo()
        except Exception:
            pass

    # Fork PT-BR 2.7.1: a abertura passa pelo encenar, que pausa o microfone (antes o JARVIS ouvia a
    # FRIDAY pela caixa de som e respondia no meio da contagem).
    from plugins import _dupla as D
    D.encenar([{"quem": "JARVIS", "efeito": "vinheta",
                "texto": f"Senhor, bem-vindo à sessão de cinema. Hoje: {titulo or 'o filme escolhido'}. "
                         "Celular no silencioso, por favor."},
               {"quem": "FRIDAY", "texto": "E a pipoca? Espero que tenha pipoca."},
               {"quem": "JARVIS", "texto": "A sessão começa em três… dois… um."}],
              "Sessão de cinema", ["JARVIS", "FRIDAY"], abrir_palco=False, ao_terminar=lambda: D.efeito("whoosh"))
    if sim_cfg(c.get("ouvir", True)) and not _ouvinte["ligado"]:
        _ouvinte["ligado"] = True
        threading.Thread(target=_ouvir_laco, daemon=True, name="cinema_ouvir").start()
    registrar(None, f"🎬 Sessão de cinema: {titulo}")
    return ("Sessão de cinema começando: janelas minimizadas, não perturbe ligado" +
            (", brilho reduzido" if anterior is not None else "") +
            ". Eu mesmo faço a vinheta e a contagem; fique em silêncio agora.")


def sim_cfg(v) -> bool:
    return str(v).lower() not in ("false", "0", "não", "nao", "off", "")


def intervalo(minutos: float) -> str:
    d = dados()
    s = d["sessao"]
    minutos = max(1.0, min(60.0, num(minutos, 10) or 10))
    _intervalo["ate"] = time.time() + minutos * 60
    _intervalo["vez"] = vez = _intervalo.get("vez", 0) + 1     # 2.7.1: um intervalo novo cancela o anterior
    if s.get("ativa"):
        s["pausado_s"] = s.get("pausado_s", 0) + minutos * 60
        _salvar(d)
    try:
        from plugins import _midia
        _midia.tecla("play_pause")
    except Exception:
        pass

    def vale() -> bool:
        return _intervalo.get("vez") == vez and bool(_intervalo["ate"])

    def play():
        if vale():
            _intervalo["ate"] = 0.0
            try:
                from plugins import _midia
                _midia.tecla("play_pause")
            except Exception as e:
                print(f"[Cinema] intervalo: {e}")

    def fim():
        from plugins import _dupla as D
        time.sleep(max(0.0, minutos * 60 - 60))
        if vale():
            D.encenar([{"quem": "FRIDAY", "texto": "Um minuto para acabar o intervalo, chefe. Corre!"}],
                      abrir_palco=False)
            time.sleep(55)
        if vale():
            if not D.encenar([{"quem": "JARVIS", "efeito": "vinheta", "texto": "O filme vai continuar."}],
                             abrir_palco=False, ao_terminar=play):
                play()
    threading.Thread(target=fim, daemon=True, name="cinema_intervalo").start()
    return f"Intervalo de {minutos:g} minutos. Pausei o filme; eu aviso um minuto antes e dou play de novo."


def perdi(minutos: float | None = None) -> str:
    s = dados()["sessao"]
    if not s.get("inicio"):
        return "Não há sessão de cinema agora. Diga 'sessão de cinema' antes do filme para eu acompanhar."
    agora_min = (time.time() - s["inicio"] - s.get("pausado_s", 0)) / 60
    desde = agora_min - minutos if minutos else None
    trechos = linha_ate(s.get("linha", []), agora_min, desde)
    if not trechos:
        return "Ainda não anotei nada do filme (preciso do pacote soundcard ou da tela, e da chave do Gemini)."
    from plugins import _ia
    notas = "\n".join(f"min {x['min']}: {x['texto']}" for x in trechos)
    r = _ia.perguntar(f"O usuário está vendo '{s.get('titulo')}' e perdeu um pedaço. Anotações do que já "
                      f"passou:\n{notas}\n\nResuma em até 5 frases faladas, em português, SÓ o que já aconteceu. "
                      "NUNCA diga ou insinue o que vai acontecer depois, nem teorias sobre o final. Comece com "
                      "'Enquanto o senhor estava fora…'.")
    return r or "Resumo das anotações:\n" + notas


def pergunta(texto: str) -> str:
    img = _tela()
    if not img:
        return "Não consegui ver a tela agora."
    s = dados()["sessao"]
    from plugins import _ia
    r = _ia.ver_imagem(f"O usuário está vendo '{s.get('titulo') or 'um filme'}' e pausou nesta cena. Pergunta: "
                       f"{texto}\nResponda em português, em até 3 frases. Se for sobre um ator, diga quem parece "
                       "ser e outros filmes conhecidos dele, deixando claro quando não tiver certeza. Não conte nada "
                       "que acontece depois desta cena.", img, inteligente=True)
    return r or "Não consegui analisar a cena (preciso da chave do Gemini e de internet)."


def conversa(titulo: str = "", nota=None) -> str:
    from plugins import _dupla as D
    if D.rodando():
        return "Já tem uma cena rodando."
    s = dados()["sessao"]
    titulo = titulo or s.get("titulo") or "o filme"
    notas = "\n".join(f"min {x['min']}: {x['texto']}" for x in (s.get("linha") or [])[-40:])
    extra = f"Anotações do que passou:\n{notas}\n" if notas else ""
    if nota is not None:
        extra += f"O usuário deu nota {num(nota):g} de 10.\n"
    falas = D.roteiro(f"O filme '{titulo}' acabou de terminar. JARVIS e FRIDAY comentam com o senhor como "
                      "amigos saindo do cinema: o que acharam, uma teoria, um detalhe escondido, e cada um diz a "
                      "sua nota de 0 a 10. Spoilers do filme estão liberados agora (ele já viu). Termine "
                      "perguntando a nota do senhor.", ["JARVIS", "FRIDAY"], 8, extra)
    if not falas:
        return "Não consegui montar a conversa agora (preciso da chave do Gemini)."
    D.encenar(falas, f"Depois do filme · {titulo}", ["JARVIS", "FRIDAY"])
    mostrar(None, "DEPOIS DO FILME", D.texto_falas(falas))
    return "JARVIS e FRIDAY estão comentando o filme no palco. Fique em silêncio até eles terminarem."


def fim(nota=None, conversar: bool = True) -> str:
    d = dados()
    s = d["sessao"]
    if not s.get("ativa"):
        return "Não há sessão ativa."
    _ouvinte["ligado"] = False
    _intervalo["ate"] = 0.0
    if s.get("brilho_antes") is not None:
        _brilho(int(s["brilho_antes"]))
    titulo = s.get("titulo") or "filme"
    s["ativa"] = False
    s["fim"] = time.time()
    if titulo and titulo != "o filme":
        registrar_assistido(d["catalogo"], titulo, nota)
    _salvar(d)
    msg = f"Sessão de {titulo} encerrada; o não perturbe acabou e guardei no seu catálogo."
    if conversar:
        msg += " " + conversa(titulo, nota)
    return msg


# ── catálogo, maratona, quiz ──────────────────────────────────────────────────
def catalogo_texto() -> str:
    cat = dados()["catalogo"]
    if not cat:
        return "Seu catálogo está vazio. Diga 'assisti tal filme, nota 8'."
    linhas = [f"• {x['titulo']} ({x.get('tipo', 'filme')})" + (f" — nota {x['nota']:g}" if x.get("nota") is not None
                                                              else "") +
              (f" — parou T{x['parou']['temporada']}E{x['parou']['episodio']}" if x.get("parou") else "")
              for x in sorted(cat, key=lambda x: x.get("ultima", ""), reverse=True)[:30]]
    mostrar(None, "CATÁLOGO", "\n".join(linhas))
    return f"{len(cat)} títulos no catálogo. Os mais recentes:\n" + "\n".join(linhas[:8])


def recomendar() -> str:
    cat = dados()["catalogo"]
    if not cat:
        return "Preciso de alguns filmes no seu catálogo, com nota, para recomendar."
    from plugins import _ia
    lista = "; ".join(f"{x['titulo']} ({x.get('nota', '?')})" for x in cat[-60:])
    r = _ia.perguntar(f"Filmes e séries que o usuário viu, com a nota dele de 0 a 10: {lista}. Recomende 3 títulos "
                      "que ele AINDA NÃO viu, combinando com o gosto (pese as notas altas), com uma frase cada "
                      "explicando o porquê. Português, sem spoilers.")
    if r:
        return r
    top = sorted([x for x in cat if x.get("nota") is not None], key=lambda x: -x["nota"])[:3]
    return "Sem a IA agora. Seus favoritos são: " + ", ".join(x["titulo"] for x in top) + \
        ". Que tal rever um deles?"


def maratona(tema: str) -> str:
    from plugins import _ia
    lista = _ia.perguntar_json(f"Monte uma maratona: {tema}. Na ordem cronológica da HISTÓRIA (não de lançamento), "
                               "a não ser que o pedido diga outra coisa. Responda SÓ JSON: "
                               '[{"titulo": "...", "ano": 2008, "minutos": 126}] com a duração real aproximada.')
    if not isinstance(lista, list) or not lista:
        return "Não consegui montar a maratona agora (preciso da chave do Gemini)."
    c = cfg("cinema", PLUGIN_SETTINGS)
    plano = plano_maratona([x for x in lista if isinstance(x, dict)][:30], int(num(c.get("intervalo_maratona"), 2)))
    d = dados()
    d["maratona"] = {"tema": tema, **plano, "atual": 0, "criada": datetime.now().strftime("%Y-%m-%d")}
    _salvar(d)
    filmes = [x for x in plano["itens"] if not x.get("intervalo")]
    texto = "\n".join(f"{i + 1}. {x['titulo']}" + (f" ({x['ano']})" if x.get("ano") else "") +
                      f" — {horas(x['minutos'])}" for i, x in enumerate(filmes))
    mostrar(None, f"MARATONA · {tema}", texto + f"\n\nTotal com intervalos: {horas(plano['total_min'])}")
    return (f"Maratona pronta: {plano['filmes']} títulos, {horas(plano['total_min'])} no total com intervalos. "
            f"Começa por {filmes[0]['titulo']}. Diga 'próximo da maratona' quando terminar cada um.")


def maratona_proximo() -> str:
    d = dados()
    m = d["maratona"]
    filmes = [x for x in m.get("itens", []) if not x.get("intervalo")]
    if not filmes:
        return "Não há maratona planejada."
    atual = int(m.get("atual", 0))
    if atual < len(filmes):
        registrar_assistido(d["catalogo"], filmes[atual]["titulo"])
    m["atual"] = atual + 1
    _salvar(d)
    if m["atual"] >= len(filmes):
        return f"Maratona '{m.get('tema')}' concluída! {len(filmes)} títulos. Impressionante, senhor."
    falta = sum(x["minutos"] for x in filmes[m["atual"]:])
    pausa = " Hora do intervalo antes." if m["atual"] % max(1, int(num(cfg("cinema", PLUGIN_SETTINGS)
                                                                     .get("intervalo_maratona"), 2))) == 0 else ""
    return (f"Próximo: {filmes[m['atual']]['titulo']} ({m['atual'] + 1} de {len(filmes)}). "
            f"Faltam {horas(falta)} de filme.{pausa}")


def quiz() -> str:
    s = dados()["sessao"]
    titulo = s.get("titulo") or ""
    notas = "\n".join(f"min {x['min']}: {x['texto']}" for x in (s.get("linha") or [])[-60:])
    from plugins import _ia
    qs = _ia.perguntar_json(f"Crie 5 perguntas de múltipla escolha (4 opções) sobre detalhes do filme '{titulo}'"
                            + (f", baseadas nestas anotações do que o usuário viu:\n{notas}\n" if notas else ". ") +
                            'Responda SÓ JSON: [{"pergunta": "...", "opcoes": ["...", "...", "...", "..."], '
                            '"certa": 0}] (certa = índice 0-3).')
    if not isinstance(qs, list) or not qs:
        return "Não consegui montar o quiz agora (preciso da chave do Gemini)."
    qs = [q for q in qs if isinstance(q, dict) and q.get("opcoes")][:5]
    rng = random.Random()
    # A FRIDAY acerta ~70%: ela também "assistiu", mas se distrai com a pipoca.
    for q in qs:
        q["friday"] = int(q.get("certa", 0)) if rng.random() < 0.7 else rng.choice(
            [i for i in range(len(q["opcoes"])) if i != int(q.get("certa", 0))] or [0])
    d = dados()
    d["quiz"] = {"titulo": titulo, "perguntas": qs, "i": 0, "voce": 0, "friday": 0}
    _salvar(d)
    return "Quiz do filme: você contra a FRIDAY, 5 perguntas. Leia a primeira:\n" + _texto_pergunta(qs[0], 1)


def _texto_pergunta(q: dict, n: int) -> str:
    return f"Pergunta {n}: {q['pergunta']}\n" + "\n".join(f"{'ABCD'[i]}) {o}" for i, o in enumerate(q["opcoes"][:4]))


def responder(resposta: str) -> str:
    d = dados()
    z = d["quiz"]
    qs = z.get("perguntas") or []
    if not qs or z.get("i", 0) >= len(qs):
        return "Não há quiz em andamento. Diga 'quiz do filme'."
    q = qs[z["i"]]
    ok = conferir(resposta, q)
    fr = q.get("friday") == int(q.get("certa", 0))
    z["voce"] += int(ok)
    z["friday"] += int(fr)
    z["i"] += 1
    certa = "ABCD"[int(q.get("certa", 0))] + ") " + q["opcoes"][int(q.get("certa", 0))]
    msg = ("Acertou! " if ok else f"Errou. A certa era {certa}. ") + \
        ("A FRIDAY também acertou. " if fr else f"A FRIDAY chutou {'ABCD'[q.get('friday', 0)]} e errou. ")
    if z["i"] < len(qs):
        _salvar(d)
        return msg + f"Placar: você {z['voce']} × FRIDAY {z['friday']}.\n" + _texto_pergunta(qs[z["i"]], z["i"] + 1)
    _salvar(d)
    fim_ = "Você venceu a FRIDAY!" if z["voce"] > z["friday"] else ("Empate!" if z["voce"] == z["friday"]
                                                                    else "A FRIDAY venceu — ela vai se gabar.")
    return msg + f"Fim do quiz: você {z['voce']} × FRIDAY {z['friday']}. {fim_}"


# ── ferramenta ────────────────────────────────────────────────────────────────
def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "").lower()
    try:
        if acao == "sessao":
            return sessao(str(p.get("titulo") or ""))
        if acao == "intervalo":
            return intervalo(p.get("minutos") or 10)
        if acao == "perdi":
            return perdi(num(p.get("minutos")) or None)
        if acao == "pergunta":
            return pergunta(str(p.get("pergunta") or "o que está acontecendo nesta cena?"))
        if acao == "fim":
            return fim(p.get("nota"))
        if acao == "conversa":
            return conversa(str(p.get("titulo") or ""), p.get("nota"))
        if acao == "assisti":
            titulo = str(p.get("titulo") or "").strip()
            if not titulo:
                return "Qual filme ou série?"
            d = dados()
            item = registrar_assistido(d["catalogo"], titulo, p.get("nota"), str(p.get("tipo") or ""),
                                       p.get("temporada"), p.get("episodio"))
            _salvar(d)
            return f"Anotado: {item['titulo']}" + (f", nota {item['nota']:g}" if item.get("nota") is not None
                                                   else "") + "."
        if acao == "onde_parei":
            return onde_parei(dados()["catalogo"], str(p.get("titulo") or ""))
        if acao == "catalogo":
            return catalogo_texto()
        if acao == "recomendar":
            return recomendar()
        if acao == "maratona":
            return maratona(str(p.get("tema") or p.get("titulo") or "Marvel"))
        if acao == "maratona_proximo":
            return maratona_proximo()
        if acao == "quiz":
            return quiz()
        if acao == "responder":
            return responder(str(p.get("resposta") or ""))
        if acao == "parar":
            from plugins import _dupla as D
            D.parar()
            return "Parei."
        return ("Ações: sessao, intervalo, perdi, pergunta, fim, conversa, assisti, onde_parei, catalogo, recomendar, "
                "maratona, maratona_proximo, quiz, responder, parar.")
    except Exception as e:
        return f"Cinema falhou: {e}"
