"""
Livro-razão (fork PT-BR 3.6) — a PROVA, à prova de adulteração, do que o JARVIS fez.

Quase nenhuma IA consegue provar o que fez. O JARVIS consegue: cada ação vira um bloco numa
corrente — cada bloco guarda o resumo (hash SHA-256) do bloco anterior e é assinado com uma chave
secreta que só existe no seu PC (HMAC-SHA256). Se alguém mudar, apagar ou trocar de lugar UM
registro, a conta deixa de fechar e a verificação aponta o bloco exato.

O que entra no livro:
    • cada ferramenta chamada: nome, parâmetros resumidos, se deu certo e a IMPRESSÃO DIGITAL do resultado
      (o texto do resultado não é guardado: ele pode trazer mensagem, senha ou coisa pessoal);
    • cada pedido que você confirmou, cancelou ou deixou vencer na tela;
    • cada autorização dada ou negada ao organismo, cada incidente e cada reparo;
    • experimentos do cientista (o plano selado ANTES de os dados chegarem, e o resultado);
    • evoluções do cérebro local (proposta, sua aprovação, rebaixamento) e cada ciclo OMEGA.

Selos: "Jarvis, sela o livro" devolve um código curto (bloco + começo do hash). Guardado FORA do
PC (no celular, num papel), ele prova depois que nada antes daquele ponto foi mexido — nem por
alguém que tenha a chave.

Limites honestos: quem tem acesso total ao PC E à chave consegue forjar o que veio DEPOIS do último
selo que você guardou fora. Parâmetro longo não fica inteiro: fica o começo e o hash do resto.

Privacidade: parâmetro com nome de segredo (senha, token, chave, pin, cpf…) vira "***"; das ferramentas
de cofre só entram o nome e a ação; a nota que VOCÊ dita fica inteira (até 600 letras). O livro não tem
como apagar um registro só (é isso que o torna prova): para zerar tudo, apague os dois arquivos abaixo e
a corrente recomeça. No modo anônimo nada é registrado (só fica marcado quando ele ligou e desligou).
Arquivos: memory/livro_razao.db e memory/livro_razao.key.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
from contextlib import closing
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "memory" / "livro_razao.db"
CHAVE = RAIZ / "memory" / "livro_razao.key"
GENESE = "0" * 64
MAX_TEXTO = 160                 # texto de um bloco em geral
MAX_ARG, COMECO_ARG = 60, 40    # parâmetro de ferramenta maior que isso: ficam as 40 primeiras letras + o hash do resto
MAX_NOTA = 600                  # a nota que você dita fica inteira até aqui
SO_ACAO = frozenset({"cofre_senhas", "cofre_condicional", "chave_celular", "senha_vazada"})   # destas: só nome e ação

_lock = threading.RLock()
_aberta: dict = {"caminho": None, "con": None}
_chaves: dict[str, bytes] = {}


# ─────────────────────────────────────────────────────────── puras ───
def canonico(dados) -> str:
    return json.dumps(dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digital(texto) -> str:
    """Impressão digital de um texto (16 letras do SHA-256): prova o conteúdo sem guardá-lo. Pura."""
    return hashlib.sha256(str(texto or "").encode("utf-8", "replace")).hexdigest()[:16]


def enxugar(v, limite: int = MAX_TEXTO, comeco: int | None = None):
    """Texto longo vira começo + hash do texto inteiro (prova o conteúdo sem guardar tudo). Pura."""
    if isinstance(v, str):
        return v if len(v) <= limite else v[:comeco or limite] + "…#" + digital(v)
    if isinstance(v, dict):
        return {str(k)[:60]: enxugar(x, limite, comeco) for k, x in list(v.items())[:40]}
    if isinstance(v, (list, tuple)):
        return [enxugar(x, limite, comeco) for x in list(v)[:40]]
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    return enxugar(str(v), limite, comeco)


_SEGREDO = ("senha", "password", "token", "key", "chave", "secret", "segredo", "pin", "cartao", "cvv", "cpf", "cnpj", "otp",
            "credencial")


def sem_segredos(args):
    """Parâmetro com nome de segredo (senha, token, chave, pin, cpf…) nunca entra no livro, nem dentro de outro. Pura."""
    if isinstance(args, dict):
        return {k: ("***" if any(x in str(k).lower() for x in _SEGREDO) else sem_segredos(v)) for k, v in args.items()}
    if isinstance(args, (list, tuple)):
        return [sem_segredos(x) for x in args]
    return args


def resumo_chamada(nome: str, args: dict | None, resultado, ok: bool) -> dict:
    """O que fica no livro de uma ferramenta chamada. Pura.
    O texto do resultado NÃO entra (pode trazer mensagem de outra pessoa, senha copiada, conteúdo de arquivo):
    ficam o tamanho e a impressão digital, que provam qual foi o resultado sem guardá-lo."""
    a = sem_segredos(dict(args or {}))
    if nome in SO_ACAO:
        a = {k: v for k, v in a.items() if k in ("action", "acao")}
    res = str(resultado or "")
    return {"f": str(nome), "a": enxugar(a, MAX_ARG, COMECO_ARG), "ok": bool(ok), "r": {"letras": len(res), "digital": digital(res)}}


def hash_bloco(anterior: str, ts: float, tipo: str, dados_json: str) -> str:
    return hashlib.sha256(f"{anterior}|{ts:.3f}|{tipo}|{dados_json}".encode("utf-8")).hexdigest()


def codigo_selo(n: int, h: str) -> str:
    return f"{n}-{h[:12]}"


def ler_codigo(codigo: str) -> tuple[int, str] | None:
    partes = str(codigo or "").strip().lower().replace(" ", "").split("-", 1)
    if len(partes) != 2 or not partes[0].isdigit() or not partes[1] or any(c not in "0123456789abcdef" for c in partes[1]):
        return None
    return int(partes[0]), partes[1]


# ─────────────────────────────────────────────────────────── arquivo ───
def _chave(caminho: Path | None = None) -> bytes:
    caminho = Path(caminho or CHAVE)
    k = _chaves.get(str(caminho))
    if k:
        return k
    try:
        k = caminho.read_bytes()
    except OSError:
        k = b""
    if len(k) < 32:
        k = secrets.token_bytes(32)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(k)
    _chaves[str(caminho)] = k
    return k


def _con() -> sqlite3.Connection:
    if _aberta["caminho"] != str(ARQ) or _aberta["con"] is None:
        fechar()
        ARQ.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(ARQ), check_same_thread=False, timeout=5, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("CREATE TABLE IF NOT EXISTS blocos (n INTEGER PRIMARY KEY, ts REAL NOT NULL, tipo TEXT NOT NULL, "
                  "dados TEXT NOT NULL, anterior TEXT NOT NULL, hash TEXT NOT NULL, mac TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS selos (n INTEGER PRIMARY KEY, hash TEXT NOT NULL, ts REAL NOT NULL)")
        _aberta.update(caminho=str(ARQ), con=c)
    return _aberta["con"]


def fechar() -> None:
    with _lock:
        if _aberta["con"] is not None:
            try:
                _aberta["con"].close()
            except Exception:
                pass
        _aberta.update(caminho=None, con=None)


def _anonimo() -> bool:
    try:
        from core import anonimo
        return anonimo.ativo()
    except Exception:
        return False


# ─────────────────────────────────────────────────────────── escrever ───
def registrar(tipo: str, dados: dict | None = None, forcar: bool = False, limite: int = MAX_TEXTO) -> dict | None:
    """Acrescenta um bloco. Nunca levanta exceção (o JARVIS não pode parar por causa do livro)."""
    if not forcar and _anonimo():
        return None
    try:
        dj = canonico(enxugar(dados or {}, limite))
        with _lock:
            c = _con()
            c.execute("BEGIN IMMEDIATE")          # PC e celular são processos diferentes: um espera o outro
            try:
                ult = c.execute("SELECT n, hash FROM blocos ORDER BY n DESC LIMIT 1").fetchone()
                n, anterior = (ult[0] + 1, ult[1]) if ult else (1, GENESE)
                ts = int(time.time() * 1000) / 1000   # para baixo: um bloco nunca fica com hora "no futuro" de quem consulta logo depois
                h = hash_bloco(anterior, ts, str(tipo), dj)
                mac = hmac.new(_chave(), h.encode(), hashlib.sha256).hexdigest()
                c.execute("INSERT INTO blocos VALUES (?,?,?,?,?,?,?)", (n, ts, str(tipo), dj, anterior, h, mac))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
            return {"n": n, "ts": ts, "tipo": str(tipo), "hash": h}
    except Exception as e:
        print(f"[Livro-razão] não registrei {tipo}: {e}")
        return None


def ferramenta(nome: str, args: dict | None, resultado: str) -> None:
    """Uma ferramenta chamada por um pedido (PC e celular)."""
    try:
        from core.registro_uso import parece_falha
        ok = not parece_falha(resultado)
    except Exception:
        ok = True
    registrar("ferramenta", resumo_chamada(nome, args, resultado, ok))


def selar() -> str | None:
    """Fecha um selo: o código para guardar FORA do PC."""
    with _lock:
        b = registrar("selo", {"quando": time.strftime("%Y-%m-%d %H:%M")})
        if not b:
            return None
        try:
            _con().execute("INSERT OR REPLACE INTO selos VALUES (?,?,?)", (b["n"], b["hash"], b["ts"]))
        except Exception as e:
            print(f"[Livro-razão] selo: {e}")
        return codigo_selo(b["n"], b["hash"])


# ─────────────────────────────────────────────────────────── ler e conferir ───
def _ler(caminho: Path | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(str(Path(caminho or ARQ)), timeout=5)
    c.execute("PRAGMA query_only=ON")              # conferir nunca escreve
    return c


def estado() -> dict:
    if not Path(ARQ).is_file():
        return {"blocos": 0, "desde": None, "ultimo": None, "selos": 0, "ultimo_selo": None, "tipos": {}}
    with _lock, closing(_ler()) as c:
        n, t0, t1 = c.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM blocos").fetchone()
        tipos = dict(c.execute("SELECT tipo, COUNT(*) FROM blocos GROUP BY tipo ORDER BY 2 DESC").fetchall())
        try:
            selo = c.execute("SELECT n, hash, ts FROM selos ORDER BY n DESC LIMIT 1").fetchone()
            nselos = c.execute("SELECT COUNT(*) FROM selos").fetchone()[0]
        except sqlite3.Error:
            selo, nselos = None, 0
    return {"blocos": n or 0, "desde": t0, "ultimo": t1, "selos": nselos, "tipos": tipos,
            "ultimo_selo": {"codigo": codigo_selo(selo[0], selo[1]), "ts": selo[2]} if selo else None}


def verificar(caminho: Path | None = None, chave: Path | None = None) -> dict:
    """Confere a corrente inteira. {'ok', 'blocos', 'erro': None | {'n', 'motivo'}, 'topo'}.
    Acha: registro alterado, bloco apagado ou fora de ordem, assinatura falsa e corte depois de um selo."""
    p = Path(caminho or ARQ)
    if not p.is_file():
        return {"ok": True, "blocos": 0, "erro": None, "topo": None}
    k = _chave(chave)
    with _lock, closing(_ler(p)) as c:
        anterior, esperado, topo = GENESE, 1, None
        for n, ts, tipo, dados, ant, h, mac in c.execute("SELECT n, ts, tipo, dados, anterior, hash, mac FROM blocos ORDER BY n"):
            if n != esperado:
                return {"ok": False, "blocos": esperado - 1, "topo": topo,
                        "erro": {"n": esperado, "motivo": f"o bloco {esperado} foi apagado (o seguinte é o {n})"}}
            if ant != anterior:
                return {"ok": False, "blocos": n - 1, "topo": topo,
                        "erro": {"n": n, "motivo": "a ligação com o bloco anterior não fecha (algo antes dele foi trocado)"}}
            if hash_bloco(ant, ts, tipo, dados) != h:
                return {"ok": False, "blocos": n - 1, "topo": topo,
                        "erro": {"n": n, "motivo": "o conteúdo foi alterado depois de escrito"}}
            if not hmac.compare_digest(hmac.new(k, h.encode(), hashlib.sha256).hexdigest(), mac):
                return {"ok": False, "blocos": n - 1, "topo": topo,
                        "erro": {"n": n, "motivo": "a assinatura não é da chave deste JARVIS"}}
            anterior, esperado, topo = h, n + 1, {"n": n, "hash": h}
        try:
            selos = c.execute("SELECT n, hash FROM selos ORDER BY n").fetchall()
        except sqlite3.Error:
            selos = []
        for n, h in selos:
            achado = c.execute("SELECT hash FROM blocos WHERE n = ?", (n,)).fetchone()
            if not achado or achado[0] != h:
                return {"ok": False, "blocos": esperado - 1, "topo": topo,
                        "erro": {"n": n, "motivo": f"o livro foi cortado ou trocado: o bloco {n}, que tinha selo, não está mais como era"}}
    return {"ok": True, "blocos": esperado - 1, "erro": None, "topo": topo}


def conferir_selo(codigo: str) -> dict:
    """O código guardado fora do PC ainda bate? {'ok', 'motivo', 'n', 'ts'}"""
    lido = ler_codigo(codigo)
    if not lido:
        return {"ok": False, "motivo": "esse código não tem o formato de um selo (ex.: 1532-9f3a1c7b22d4)"}
    n, prefixo = lido
    if not Path(ARQ).is_file():
        return {"ok": False, "motivo": "o livro não existe mais neste PC"}
    with _lock, closing(_ler()) as c:
        b = c.execute("SELECT hash, ts FROM blocos WHERE n = ?", (n,)).fetchone()
    if not b:
        return {"ok": False, "n": n, "motivo": f"o bloco {n} não existe mais: o livro foi cortado"}
    if not b[0].startswith(prefixo):
        return {"ok": False, "n": n, "motivo": f"o bloco {n} não bate com esse código (o código está errado ou o bloco foi trocado)"}
    v = verificar()
    if not v["ok"] and v["erro"]["n"] <= n:
        return {"ok": False, "n": n, "motivo": f"antes do selo há um problema no bloco {v['erro']['n']}: {v['erro']['motivo']}"}
    return {"ok": True, "n": n, "ts": b[1], "motivo": "tudo até esse selo está exatamente como era"}


def consultar(inicio: float = 0.0, fim: float | None = None, tipo: str | None = None, limite: int = 200) -> list[dict]:
    if not Path(ARQ).is_file():
        return []
    sql, args = "SELECT n, ts, tipo, dados, hash FROM blocos WHERE ts >= ? AND ts <= ?", [inicio, fim or time.time() + 1]
    if tipo:
        sql += " AND tipo = ?"
        args.append(tipo)
    with _lock, closing(_ler()) as c:
        linhas = c.execute(sql + " ORDER BY n DESC LIMIT ?", args + [int(limite)]).fetchall()
    out = []
    for n, ts, tp, dados, h in reversed(linhas):
        try:
            d = json.loads(dados)
        except ValueError:
            d = {"?": dados[:80]}
        out.append({"n": n, "ts": ts, "tipo": tp, "dados": d, "hash": h})
    return out


def demonstrar_adulteracao() -> dict:
    """Mostra a prova funcionando SEM tocar no livro de verdade: copia o livro, altera um registro NA CÓPIA
    e confere a cópia. {'ok', 'bloco_alterado', 'detectado', 'motivo'}"""
    if not Path(ARQ).is_file():
        return {"ok": False, "motivo": "o livro ainda está vazio"}
    pasta = Path(tempfile.mkdtemp(prefix="livro_demo_"))
    try:
        copia = pasta / "copia.db"
        with _lock:
            with closing(_ler()) as origem, closing(sqlite3.connect(str(copia))) as destino:
                origem.backup(destino)
        with closing(sqlite3.connect(str(copia))) as c:
            total = c.execute("SELECT COUNT(*) FROM blocos").fetchone()[0]
            if total < 1:
                return {"ok": False, "motivo": "o livro ainda está vazio"}
            alvo = max(1, total // 2)
            c.execute("UPDATE blocos SET dados = ? WHERE n = ?", (canonico({"f": "REGISTRO FALSO", "ok": True}), alvo))
            c.commit()
        v = verificar(copia)
        achou = (not v["ok"]) and v["erro"]["n"] == alvo
        return {"ok": True, "bloco_alterado": alvo, "blocos": total, "detectado": achou,
                "motivo": v["erro"]["motivo"] if v["erro"] else "", "original_intacto": verificar()["ok"]}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


def ligar_ao_organismo(org) -> None:
    """Incidentes e reparos do organismo entram no livro."""
    def anotar(ev):
        registrar("organismo." + ev.topico, {k: v for k, v in list((ev.dados or {}).items())[:12]})
    for padrao in ("incidente.*", "reparo.*"):
        org.bus.assinar(padrao, anotar, nome=f"livro_razao:{padrao}")
