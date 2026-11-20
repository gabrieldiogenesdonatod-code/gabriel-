"""
Memória de tela (fork PT-BR 1.5).

De tempos em tempos (1 min, só quando a tela mudou e você está no PC) o
JARVIS guarda o TEXTO da janela ativa — lido com OCR, aqui no PC — e uma
miniatura. Depois você pergunta:

    "Jarvis, o que eu estava vendo ontem sobre ESP32?"
    "Jarvis, onde eu vi aquele erro de I2S?"
    → "Ontem às 21h14, no Chrome (YouTube: ESP32 I2S MAX98357A) e às 22h no
       VS Code (capacete.ino)."  — e mostra os trechos e as miniaturas.

PRIVACIDADE
    • começa DESLIGADA: "Jarvis, liga a memória de tela";
    • tudo fica neste PC (memory/memoria_tela.db e memory/memoria_tela/);
      nada vai para a internet;
    • nunca guarda janelas de banco, senha, cofre de senhas, navegação anônima
      (lista editável em ⚙);
    • "Jarvis, pausa a memória de tela por 1 hora" / "apaga a memória de tela de hoje";
    • texto fica 30 dias e miniaturas 7 dias (ajustável).

OCR: rapidocr-onnxruntime (recomendado) ou Tesseract. Sem nenhum, guarda só o
título das janelas — a busca ainda funciona pelos títulos.
"""

from __future__ import annotations

import hashlib
import io
import re
import sqlite3
import threading
import time
from datetime import datetime

from plugins._comum import MEMORIA, cfg, mostrar, salvar_cfg

PLUGIN = {
    "name": "memoria_tela",
    "brief": "Local screen memory: OCR text of the active window over time; search what you saw.",
    "description": (
        "Screen memory (opt-in, local only): periodically stores the OCR text and a thumbnail of the active window, "
        "skipping banking/password/private windows. action='buscar' with termo and optional periodo ('what was I "
        "looking at yesterday about ESP32?'), 'ligar', 'desligar', 'pausar' with minutos, 'apagar' with periodo "
        "(hoje|tudo), 'status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "buscar | ligar | desligar | pausar | apagar | status"},
            "termo": {"type": "STRING"}, "periodo": {"type": "STRING"}, "minutos": {"type": "INTEGER"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "memoria_tela",
    "title": "Memória de tela",
    "fields": [
        {"key": "ligado", "label": "Guardar o texto da tela (local)", "type": "toggle", "default": False},
        {"key": "intervalo", "label": "Intervalo (segundos)", "type": "text", "default": "60"},
        {"key": "imagens", "label": "Guardar miniaturas", "type": "toggle", "default": True},
        {"key": "dias_texto", "label": "Dias para guardar o texto", "type": "text", "default": "30"},
        {"key": "dias_imagens", "label": "Dias para guardar as miniaturas", "type": "text", "default": "7"},
        {"key": "excluir", "label": "Nunca guardar janelas com (separe por vírgula)", "type": "text",
         "default": "senha, password, banco, bank, nubank, itaú, itau, bradesco, santander, caixa econômica, "
                    "inter, pix, 1password, bitwarden, keepass, lastpass, inprivate, incognito, anônima, privada, "
                    "privativa, private browsing"},
    ],
}

ARQ = MEMORIA / "memoria_tela.db"
PASTA_IMG = MEMORIA / "memoria_tela"
_estado = {"pausado_ate": 0.0, "ultimo_hash": {}, "capturas": 0}
_lock = threading.Lock()
_con: dict = {"c": None, "fts": False, "arq": None}
_iniciado = threading.Event()


def _sim(v) -> bool:
    return str(v).strip().lower() not in ("false", "0", "nao", "não", "off")


def _c() -> sqlite3.Connection:
    if _con["c"] is None or _con["arq"] != ARQ:
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(ARQ), check_same_thread=False, timeout=5)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("CREATE TABLE IF NOT EXISTS capturas (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, app TEXT, "
                  "titulo TEXT, texto TEXT, imagem TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_cap_ts ON capturas(ts)")
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS busca USING fts5(titulo, texto, content='capturas', "
                      "content_rowid='id', tokenize='unicode61 remove_diacritics 2')")
            _con["fts"] = True
        except sqlite3.OperationalError:
            _con["fts"] = False                                # sem FTS5: busca por LIKE
        c.commit()
        _con.update(c=c, arq=ARQ)
    return _con["c"]


def excluida(app: str, titulo: str, lista: str) -> bool:
    """A janela fala de algo da lista? Palavra inteira (aceita plural): 'pix' pega "Pix" mas
    não "pixel"; 'inter' pega "Banco Inter" mas não "Internet" (pura)."""
    texto = f"{app} {titulo}".lower()
    for termo in (lista or "").split(","):
        termo = termo.strip().lower()
        if termo and re.search(r"(?<!\w)" + re.escape(termo) + r"s?(?!\w)", texto):
            return True
    return False


def guardar(app: str, titulo: str, texto: str, imagem: str = "", ts: float | None = None) -> int:
    with _lock:
        c = _c()
        cur = c.execute("INSERT INTO capturas (ts, app, titulo, texto, imagem) VALUES (?,?,?,?,?)",
                        (ts or time.time(), app, titulo, texto, imagem))
        if _con["fts"]:
            c.execute("INSERT INTO busca(rowid, titulo, texto) VALUES (?,?,?)", (cur.lastrowid, titulo, texto))
        c.commit()
        return cur.lastrowid


def _consulta_fts(termo: str) -> str:
    palavras = [w for w in re.findall(r"\w+", termo.lower()) if len(w) > 1]
    return " AND ".join(f'"{w}"*' for w in palavras)


def buscar(termo: str, desde: float = 0, ate: float | None = None, limite: int = 30) -> list[dict]:
    ate = ate or time.time() + 60
    with _lock:
        c = _c()
        c.row_factory = sqlite3.Row
        try:
            if _con["fts"] and _consulta_fts(termo):
                linhas = c.execute(
                    "SELECT capturas.*, snippet(busca, 1, '[', ']', '…', 12) AS trecho FROM busca "
                    "JOIN capturas ON capturas.id = busca.rowid WHERE busca MATCH ? AND capturas.ts BETWEEN ? AND ? "
                    "ORDER BY capturas.ts DESC LIMIT ?", (_consulta_fts(termo), desde, ate, limite)).fetchall()
            else:
                like = f"%{termo.lower()}%"
                linhas = c.execute("SELECT *, substr(texto, 1, 160) AS trecho FROM capturas WHERE ts BETWEEN ? AND ? "
                                   "AND (lower(texto) LIKE ? OR lower(titulo) LIKE ?) ORDER BY ts DESC LIMIT ?",
                                   (desde, ate, like, like, limite)).fetchall()
            return [dict(x) for x in linhas]
        finally:
            c.row_factory = None


def limpar_antigos(dias_texto: float, dias_img: float) -> int:
    limite_txt = time.time() - dias_texto * 86400
    limite_img = time.time() - dias_img * 86400
    with _lock:
        c = _c()
        for (img,) in c.execute("SELECT imagem FROM capturas WHERE ts < ? AND imagem != ''", (limite_img,)).fetchall():
            try:
                (PASTA_IMG / img).unlink(missing_ok=True)
            except OSError:
                pass
        c.execute("UPDATE capturas SET imagem = '' WHERE ts < ?", (limite_img,))
        ids = [r[0] for r in c.execute("SELECT id FROM capturas WHERE ts < ?", (limite_txt,)).fetchall()]
        if ids and _con["fts"]:
            c.executemany("INSERT INTO busca(busca, rowid, titulo, texto) SELECT 'delete', id, titulo, texto FROM "
                          "capturas WHERE id = ?", [(i,) for i in ids])
        c.execute("DELETE FROM capturas WHERE ts < ?", (limite_txt,))
        c.commit()
        return len(ids)


def apagar(desde: float) -> int:
    with _lock:
        c = _c()
        linhas = c.execute("SELECT id, imagem FROM capturas WHERE ts >= ?", (desde,)).fetchall()
        for _id, img in linhas:
            if img:
                (PASTA_IMG / img).unlink(missing_ok=True)
        if _con["fts"]:
            c.executemany("INSERT INTO busca(busca, rowid, titulo, texto) SELECT 'delete', id, titulo, texto FROM "
                          "capturas WHERE id = ?", [(i,) for i, _ in linhas])
        c.execute("DELETE FROM capturas WHERE ts >= ?", (desde,))
        c.commit()
        return len(linhas)


def _miniatura(jpeg: bytes) -> tuple[bytes, str]:
    """(miniatura jpeg, impressão para saber se a tela mudou)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        pequena = im.copy()
        pequena.thumbnail((960, 960))
        buf = io.BytesIO()
        pequena.save(buf, "JPEG", quality=60)
        cinza = im.convert("L").resize((32, 24))
        bits = bytes(1 if px > sum(cinza.getdata()) / (32 * 24) else 0 for px in cinza.getdata())
        return buf.getvalue(), hashlib.sha1(bits).hexdigest()
    except Exception:
        return jpeg, hashlib.sha1(jpeg[::101]).hexdigest()


def capturar_agora() -> str:
    """Uma captura da janela ativa (se não estiver excluída e tiver mudado)."""
    from plugins import olha_isso
    c = cfg("memoria_tela", PLUGIN_SETTINGS)
    j = olha_isso.janela_alvo()
    if not j:
        return "sem janela"
    if excluida(j.get("processo", ""), j.get("titulo", ""), str(c.get("excluir") or "")):
        return "excluída"
    img = olha_isso.capturar(j, 1600)
    texto, nome_img = "", ""
    if img:
        mini, impressao = _miniatura(img[0])
        chave = f"{j.get('processo')}|{j.get('titulo')}"
        if _estado["ultimo_hash"].get(chave) == impressao:
            return "igual"
        _estado["ultimo_hash"][chave] = impressao
        texto = olha_isso._ler_tela(img[0], inicio=0)
        if _sim(c.get("imagens", True)):
            dia = datetime.now().strftime("%Y%m%d")
            (PASTA_IMG / dia).mkdir(parents=True, exist_ok=True)
            nome_img = f"{dia}/{datetime.now():%H%M%S}.jpg"
            (PASTA_IMG / nome_img).write_bytes(mini)
    guardar(j.get("processo", ""), j.get("titulo", ""), re.sub(r"\s+", " ", texto).strip()[:20000], nome_img)
    _estado["capturas"] += 1
    return "guardada"


def _laco(player) -> None:
    time.sleep(90)
    ultima_limpeza = 0.0
    while True:
        c = cfg("memoria_tela", PLUGIN_SETTINGS)
        try:
            intervalo = max(20.0, float(str(c.get("intervalo") or 60)))
        except ValueError:
            intervalo = 60.0
        try:
            if _sim(c.get("ligado", False)) and time.time() >= _estado["pausado_ate"]:
                from core import verificacao
                from plugins.linha_do_tempo import ocioso_segundos
                if ocioso_segundos() < 120 and not verificacao.windows_travado():
                    capturar_agora()
            if time.time() - ultima_limpeza > 6 * 3600:
                ultima_limpeza = time.time()
                limpar_antigos(float(str(c.get("dias_texto") or 30)), float(str(c.get("dias_imagens") or 7)))
        except Exception as e:
            print(f"[MemóriaTela] {e}")
        time.sleep(intervalo)


def on_session_start(player) -> None:
    if not _iniciado.is_set():
        _iniciado.set()
        threading.Thread(target=_laco, args=(player,), daemon=True, name="memoria_tela").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "buscar").lower()
    try:
        if acao == "ligar":
            salvar_cfg("memoria_tela", {"ligado": True})
            from plugins import olha_isso
            ocr = "com leitura de texto" if olha_isso.ocr_disponivel() else \
                "só com os títulos das janelas (instale o rapidocr-onnxruntime para ler o texto)"
            return f"Memória de tela ligada, {ocr}. Tudo fica neste PC; janelas de banco e senha são puladas."
        if acao == "desligar":
            salvar_cfg("memoria_tela", {"ligado": False})
            return "Memória de tela desligada. O que já foi guardado continua até expirar."
        if acao == "pausar":
            minutos = int(p.get("minutos") or 60)
            _estado["pausado_ate"] = time.time() + minutos * 60
            return f"Pausei a memória de tela por {minutos} minutos."
        if acao == "apagar":
            from plugins.reconstrucao import periodo
            per = str(p.get("periodo") or "hoje").lower()
            desde = 0.0 if "tudo" in per else periodo(per)[0].timestamp()
            n = apagar(desde)
            return f"Apaguei {n} captura(s) da memória de tela."
        if acao == "status":
            with _lock:
                total = _c().execute("SELECT COUNT(*) FROM capturas").fetchone()[0]
            ligado = _sim(cfg("memoria_tela", PLUGIN_SETTINGS).get("ligado", False))
            return f"Memória de tela {'ligada' if ligado else 'desligada'}; {total} captura(s) guardadas."
        termo = str(p.get("termo") or "").strip()
        if not termo:
            return "O que você quer achar na memória de tela?"
        desde, ate, rotulo = 0.0, None, "nos últimos 30 dias"
        if p.get("periodo"):
            from plugins.reconstrucao import periodo
            ini, fim, rotulo = periodo(str(p["periodo"]))
            desde, ate = ini.timestamp(), fim.timestamp()
        achados = buscar(termo, desde, ate)
        if not achados:
            return f"Não achei '{termo}' na memória de tela {rotulo}."
        mostrar(player, f"MEMÓRIA DE TELA — {termo}", "\n\n".join(
            f"{datetime.fromtimestamp(a['ts']):%d/%m %H:%M}  {a['app']} — {a['titulo'][:80]}\n  {a.get('trecho') or ''}"
            + (f"\n  imagem: {PASTA_IMG / a['imagem']}" if a.get("imagem") else "") for a in achados[:15]))
        primeiros = "; ".join(f"{datetime.fromtimestamp(a['ts']):%d/%m às %H:%M} no {a['app'].replace('.exe', '')} "
                              f"({a['titulo'][:50]})" for a in achados[:3])
        return f"Achei {len(achados)} momento(s) {rotulo}: {primeiros}. Os trechos estão no painel."
    except Exception as e:
        return f"A memória de tela falhou: {e}"
