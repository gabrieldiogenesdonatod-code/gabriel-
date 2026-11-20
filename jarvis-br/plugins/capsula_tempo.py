"""
Cápsula do tempo (fork PT-BR 1.6).

Mensagens para o "você do futuro": o JARVIS guarda e só entrega na data
marcada — com voz, no painel e no celular. Até lá, ele não mostra o
conteúdo (só que existe uma cápsula e quando ela abre).

    "Jarvis, cápsula do tempo para daqui a 1 ano: espero que o JARVIS esteja vendendo"
    "Jarvis, mensagem para mim em 25/12/2027: …"
    "Jarvis, quantas cápsulas eu tenho?"
    "Jarvis, guarda esse recado pro meu eu daqui 1 ano"   (2.4: grava a SUA voz; no dia, ele toca o áudio)
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta

from pathlib import Path

from plugins._comum import MEMORIA, abrir_no_sistema, falar, gravar_json, ler_json, mostrar, registrar

PLUGIN = {
    "name": "capsula_tempo",
    "brief": "Time capsule: messages to the future self, delivered on the chosen date (voice, panel, phone).",
    "description": (
        "Time capsule: action='criar' with mensagem + quando ('daqui a 1 ano', 'em 6 meses', '25/12/2027', "
        "'no ano que vem'); 'gravar' with quando records the user's VOICE message (up to segundos, default 90; stops "
        "after he stops talking) and plays it back on that day — after calling, say only 'Pode falar, estou "
        "gravando.'; 'listar' (how many and when they open, without revealing contents); 'abrir' (delivers the "
        "ones whose date has arrived)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "criar | gravar | listar | abrir"},
                       "mensagem": {"type": "STRING"}, "segundos": {"type": "NUMBER"}, "quando": {"type": "STRING"}},
        "required": [],
    },
}

_ARQ = MEMORIA / "capsulas.json"
PASTA_AUDIO = MEMORIA / "capsulas_audio"
_iniciado = threading.Event()


def data_de(texto: str, hoje: date | None = None) -> date | None:
    """'daqui a 2 anos', 'em 6 meses', '3 semanas', '25/12/2027', 'ano que vem', 'natal' → data (pura)."""
    hoje = hoje or date.today()
    t = (texto or "").lower()
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", t)
    if m:
        ano = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        try:
            return date(ano, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"(\d+|um|uma|dois|duas|tr[eê]s|seis|dez)\s*(dia|semana|m[eê]s|mes|ano)", t)
    numeros = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "seis": 6, "dez": 10}
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else numeros.get(m.group(1), 1)
        u = m.group(2)
        if u.startswith("dia"):
            return hoje + timedelta(days=n)
        if u.startswith("semana"):
            return hoje + timedelta(weeks=n)
        if u.startswith("m"):
            mes = hoje.month - 1 + n
            ano, mes = hoje.year + mes // 12, mes % 12 + 1
            return date(ano, mes, min(hoje.day, 28))
        try:
            return hoje.replace(year=hoje.year + n)
        except ValueError:
            return hoje.replace(year=hoje.year + n, day=28)
    if "ano que vem" in t or "proximo ano" in t or "próximo ano" in t:
        return hoje.replace(year=hoje.year + 1, day=min(hoje.day, 28))
    if "natal" in t:
        d = date(hoje.year, 12, 25)
        return d if d > hoje else date(hoje.year + 1, 12, 25)
    if "ano novo" in t or "reveillon" in t or "réveillon" in t:
        return date(hoje.year + 1, 1, 1)
    return None


def carregar() -> list[dict]:
    return (ler_json(_ARQ, {}) or {}).get("capsulas", [])


def para_hoje() -> list[dict]:
    """Cápsulas que já podem abrir e ainda não foram entregues (usado no boot)."""
    hoje = date.today().isoformat()
    return [c for c in carregar() if not c.get("entregue") and c["abre"] <= hoje]


def entregar(player=None) -> int:
    d = ler_json(_ARQ, {}) or {}
    prontas = [c for c in d.get("capsulas", []) if not c.get("entregue") and c["abre"] <= date.today().isoformat()]
    for c in prontas:
        c["entregue"] = time.time()
    if prontas:
        gravar_json(_ARQ, d)
        texto = "\n\n".join(f"Escrita em {datetime.fromtimestamp(c['criada']):%d/%m/%Y}:\n{c['mensagem']}" for c in prontas)
        mostrar(player, "CÁPSULA DO TEMPO", texto)
        audios = [c["audio"] for c in prontas if c.get("audio") and Path(c["audio"]).exists()]
        try:
            from plugins._notificar import notificar
            notificar(player, f"Abriu {len(prontas)} cápsula(s) do tempo.", titulo="CÁPSULA DO TEMPO", falar_agora=False)
        except Exception:
            pass
        so_texto = [c for c in prontas if not c.get("audio")]
        if so_texto:
            falar(player, "[CÁPSULA DO TEMPO] Com emoção, diga que chegou o dia de abrir uma mensagem que o próprio "
                          "usuário escreveu no passado, e leia: "
                          + "\n\n".join(c["mensagem"] for c in so_texto)[:1500] + ". Não chame nenhuma ferramenta.")
        if audios:                                             # 2.4: recado na voz dele
            falar(player, "[CÁPSULA DO TEMPO] Com emoção, diga em UMA frase que chegou o dia de ouvir um recado que ele "
                          "gravou para si mesmo no passado, e que vai tocar agora. Não chame nenhuma ferramenta.")
            threading.Thread(target=_tocar_audios, args=(audios,), daemon=True).start()
    return len(prontas)


def _tocar_audios(audios: list[str]) -> None:
    time.sleep(7)
    for a in audios:
        abrir_no_sistema(a)
        time.sleep(2)


def _gravar_recado(quando: date, segundos: float, player) -> None:
    from core import microfone
    try:
        from plugins import _som
        microfone.esperar_jarvis_calar()
        with microfone.reservado_por("cápsula do tempo", segundos + 5):
            audio = microfone.gravar(segundos, parar_no_silencio=True, silencio_s=3.5)
        if len(audio) < 44100 * 1.5:
            registrar(player, "Cápsula do tempo: não ouvi nada; nada foi guardado.")
            return
        PASTA_AUDIO.mkdir(parents=True, exist_ok=True)
        cid = uuid.uuid4().hex[:8]
        arq = _som.salvar_wav(PASTA_AUDIO / f"{cid}.wav", _som.normalizar(audio, 0.9))
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("capsulas", []).append({"id": cid, "mensagem": "(recado em áudio)", "audio": str(arq),
                                             "criada": time.time(), "abre": quando.isoformat(), "entregue": None})
        gravar_json(_ARQ, d)
        registrar(player, f"Cápsula do tempo: recado de {len(audio) / 44100:.0f} s lacrado até {quando:%d/%m/%Y}.")
        falar(player, f"[CÁPSULA DO TEMPO] Diga em UMA frase que o recado foi lacrado e abre em {quando:%d/%m/%Y}. "
                      "Não chame nenhuma ferramenta.")
    except Exception as e:
        registrar(player, f"Cápsula do tempo: não consegui gravar ({e}).")


def _laco(player) -> None:
    time.sleep(60)
    while True:
        try:
            from plugins.linha_do_tempo import ocioso_segundos
            if datetime.now().hour >= 8 and ocioso_segundos() < 120 and para_hoje():
                entregar(player)
        except Exception as e:
            print(f"[Cápsula] {e}")
        time.sleep(600)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="capsula_tempo").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        d = ler_json(_ARQ, {}) or {}
        d.setdefault("capsulas", [])
        if acao == "criar":
            msg, quando = str(p.get("mensagem") or "").strip(), data_de(str(p.get("quando") or ""))
            if not msg:
                return "O que você quer dizer para o você do futuro?"
            if not quando or quando <= date.today():
                return "Para quando? (ex.: daqui a 1 ano, em 6 meses, 25/12/2027)"
            d["capsulas"].append({"id": uuid.uuid4().hex[:8], "mensagem": msg, "criada": time.time(),
                                  "abre": quando.isoformat(), "entregue": None})
            gravar_json(_ARQ, d)
            return f"Cápsula lacrada. Abre em {quando:%d/%m/%Y} — até lá, nem eu falo o que está escrito."
        if acao == "gravar":
            quando = data_de(str(p.get("quando") or ""))
            if not quando or quando <= date.today():
                return "Para quando? (ex.: daqui a 1 ano, em 6 meses, 25/12/2027)"
            import importlib.util
            if importlib.util.find_spec("sounddevice") is None:
                return "Para gravar preciso do sounddevice (python -m pip install sounddevice)."
            seg = max(10.0, min(300.0, float(p.get("segundos") or 90)))
            threading.Thread(target=_gravar_recado, args=(quando, seg, player), daemon=True).start()
            return (f"Gravando o recado para {quando:%d/%m/%Y} (até {seg:.0f} s; paro quando você ficar quieto). "
                    "Diga só: 'Pode falar, estou gravando.'")
        if acao == "abrir":
            n = entregar(player)
            return f"Abri {n} cápsula(s)." if n else "Nenhuma cápsula chegou na data ainda."
        fechadas = [c for c in d["capsulas"] if not c.get("entregue")]
        if not fechadas:
            return "Nenhuma cápsula fechada. Diga 'cápsula do tempo para daqui a 1 ano: …'."
        proxima = min(fechadas, key=lambda c: c["abre"])
        return f"{len(fechadas)} cápsula(s) lacrada(s); a próxima abre em {date.fromisoformat(proxima['abre']):%d/%m/%Y}."
    except Exception as e:
        return f"A cápsula do tempo falhou: {e}"
