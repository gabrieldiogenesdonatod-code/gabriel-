"""
Missões em segundo plano (fork PT-BR 2.4).

Tarefas longas que rodam por horas e CONTINUAM depois de fechar o JARVIS ou
reiniciar o PC: cada missão guarda onde parou (memory/missoes.json) e volta
dali quando o JARVIS abre. Todas aparecem no painel MISSÕES (página /missoes)
com progresso, pausar, continuar e cancelar.

Tipos:
    organizar_fotos   separa as fotos de uma pasta em Ano/Mês (pela data da
                      foto). Por padrão COPIA (o original fica onde está);
                      "mover" pede confirmação e dá para desfazer.
    monitorar_preco   consulta o preço de um produto (ou link) de tempos em
                      tempos por N dias e avisa no menor preço / no preço alvo.
    converter_videos  converte todos os vídeos de uma pasta para MP4 (H.264),
                      numa pasta "convertidos" ao lado — os originais ficam.

No máximo 3 missões rodando ao mesmo tempo; as outras esperam na fila.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from plugins._comum import CNW, MEMORIA, gravar_json, ler_json

ARQ = MEMORIA / "missoes.json"
PASTA_LISTAS = MEMORIA / "missoes"
MAX_JUNTAS = 3
FOTOS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".dng", ".cr2", ".nef", ".arw"}
VIDEOS = {".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".mts", ".m2ts", ".mpg", ".mpeg", ".mp4"}
MESES = ("01 - Janeiro", "02 - Fevereiro", "03 - Março", "04 - Abril", "05 - Maio", "06 - Junho", "07 - Julho",
         "08 - Agosto", "09 - Setembro", "10 - Outubro", "11 - Novembro", "12 - Dezembro")
NOMES_TIPO = {"organizar_fotos": "Organizar fotos", "monitorar_preco": "Monitorar preço",
              "converter_videos": "Converter vídeos"}

_lock = threading.RLock()
_threads: dict[int, threading.Thread] = {}
_paradas: dict[int, threading.Event] = {}
_avisar = {"fn": None}                     # nos testes: captura os avisos


# ── arquivo ──────────────────────────────────────────────────────────────────
def _todas() -> list[dict]:
    d = ler_json(ARQ, []) or []
    return d if isinstance(d, list) else []


def _gravar(lista: list[dict]) -> None:
    gravar_json(ARQ, lista)


def obter(mid: int) -> dict | None:
    with _lock:
        return next((dict(m) for m in _todas() if m["id"] == mid), None)


def _atualizar(mid: int, **campos) -> dict | None:
    with _lock:
        lista = _todas()
        m = next((x for x in lista if x["id"] == mid), None)
        if m is None:
            return None
        log = campos.pop("log", None)
        m.update(campos, atualizada=time.time())
        if log:
            m["log"] = (m.get("log", []) + [f"{time.strftime('%d/%m %H:%M')} {log}"])[-20:]
        _gravar(lista)
        return dict(m)


def listar() -> list[dict]:
    with _lock:
        return [{k: v for k, v in m.items() if k != "checkpoint"} for m in _todas()]


# ── regras (puras, nos testes) ───────────────────────────────────────────────
def destino_foto(raiz: Path, data: datetime, nome: str) -> Path:
    return raiz / str(data.year) / MESES[data.month - 1] / nome


def sem_conflito(p: Path) -> Path:
    if not p.exists():
        return p
    for i in range(2, 10_000):
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
    return p.with_name(f"{p.stem}_{int(time.time())}{p.suffix}")


def data_da_foto(arq: Path) -> datetime:
    """Data em que a foto foi tirada (EXIF), senão a data do nome (IMG_20240131…), senão a do arquivo."""
    try:
        from PIL import Image
        with Image.open(arq) as im:
            exif = im.getexif()
            bruto = exif.get(36867) or exif.get_ifd(0x8769).get(36867) or exif.get(306)
            if bruto:
                return datetime.strptime(str(bruto)[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    m = re.search(r"(20\d{2}|19\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])", arq.name)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return datetime.fromtimestamp(arq.stat().st_mtime)


def arquivos(pasta: Path, extensoes: set[str], ignorar: Path | None = None) -> list[str]:
    saida = []
    for p in sorted(pasta.rglob("*")):
        if p.is_file() and p.suffix.lower() in extensoes:
            if ignorar is not None and ignorar in p.parents:
                continue
            saida.append(str(p))
    return saida


def args_ffmpeg(ffmpeg: str, origem: str, destino: str, crf: int = 23) -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", origem, "-c:v", "libx264", "-preset", "veryfast",
            "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", destino]


def proxima_consulta(ultima: float, intervalo_h: float) -> float:
    return ultima + intervalo_h * 3600


# ── criar e controlar ────────────────────────────────────────────────────────
def criar(tipo: str, params: dict, titulo: str = "") -> dict:
    if tipo not in NOMES_TIPO:
        raise ValueError(f"tipo desconhecido: {tipo}")
    with _lock:
        lista = _todas()
        mid = max([m["id"] for m in lista], default=0) + 1
        m = {"id": mid, "tipo": tipo, "titulo": titulo or NOMES_TIPO[tipo], "params": params, "estado": "rodando",
             "progresso": 0.0, "feito": 0, "total": 0, "etapa": "começando", "checkpoint": {}, "criada": time.time(),
             "atualizada": time.time(), "log": [], "resultado": ""}
        lista.append(m)
        _gravar(lista)
    _iniciar(mid)
    return m


def comando(acao: str, mid: int) -> dict:
    m = obter(mid)
    if m is None:
        return {"ok": False, "erro": f"Não existe a missão {mid}."}
    if acao == "pausar" and m["estado"] == "rodando":
        _atualizar(mid, estado="pausada", log="pausada")
        _parar_thread(mid)
    elif acao == "continuar" and m["estado"] in ("pausada", "erro", "fila"):
        _atualizar(mid, estado="rodando", log="continuando")
        _iniciar(mid)
    elif acao == "cancelar" and m["estado"] not in ("concluida", "cancelada"):
        _atualizar(mid, estado="cancelada", log="cancelada")
        _parar_thread(mid)
    elif acao == "apagar" and m["estado"] in ("concluida", "cancelada", "erro"):
        with _lock:
            _gravar([x for x in _todas() if x["id"] != mid])
        return {"ok": True}
    else:
        return {"ok": False, "erro": f"A missão {mid} está {m['estado']}."}
    return {"ok": True, "missao": obter(mid)}


def _parar_thread(mid: int) -> None:
    ev = _paradas.get(mid)
    if ev is not None:
        ev.set()


def retomar() -> int:
    """Na abertura do JARVIS: volta as missões que estavam rodando (de onde pararam)."""
    n = 0
    for m in listar():
        if m["estado"] in ("rodando", "fila"):
            _iniciar(m["id"])
            n += 1
    return n


def _iniciar(mid: int) -> None:
    with _lock:
        t = _threads.get(mid)
        if t is not None and t.is_alive():
            return
        rodando = sum(1 for x in _threads.values() if x.is_alive())
        if rodando >= MAX_JUNTAS:
            _atualizar(mid, estado="fila", etapa="na fila (já há 3 rodando)")
            return
        _atualizar(mid, estado="rodando")
        ev = threading.Event()
        _paradas[mid] = ev
        t = threading.Thread(target=_rodar, args=(mid, ev), daemon=True, name=f"missao_{mid}")
        _threads[mid] = t
        t.start()


def _proxima_da_fila() -> None:
    for m in listar():
        if m["estado"] == "fila":
            _iniciar(m["id"])
            return


def _notificar(texto: str, prioridade: str = "default") -> None:
    if _avisar["fn"] is not None:
        _avisar["fn"](texto)
        return
    try:
        from plugins._notificar import notificar
        notificar(None, texto, titulo="MISSÕES", etiqueta="MISSÃO", prioridade=prioridade)
    except Exception as e:
        print(f"[Missões] {e}")


def _rodar(mid: int, parar: threading.Event) -> None:
    try:
        m = obter(mid)
        fn = {"organizar_fotos": _organizar_fotos, "monitorar_preco": _monitorar_preco,
              "converter_videos": _converter_videos}[m["tipo"]]
        terminou = fn(mid, parar)
        if terminou:
            m = _atualizar(mid, estado="concluida", progresso=1.0, etapa="concluída", log="concluída")
            _notificar(f"Missão {mid} concluída: {m['titulo']}. {m.get('resultado', '')}".strip())
    except Exception as e:
        _atualizar(mid, estado="erro", etapa=f"erro: {e}", log=f"erro: {e}")
        _notificar(f"A missão {mid} parou com erro: {e}")
    finally:
        with _lock:
            _threads.pop(mid, None)
            _paradas.pop(mid, None)
        _proxima_da_fila()


def _lista_salva(mid: int, gerar) -> list[str]:
    """A lista de arquivos é feita uma vez e salva (a ordem não muda depois de reiniciar)."""
    PASTA_LISTAS.mkdir(parents=True, exist_ok=True)
    arq = PASTA_LISTAS / f"{mid}_lista.json"
    lista = ler_json(arq, None)
    if lista is None:
        lista = gerar()
        gravar_json(arq, lista)
    return lista


# ── os tipos ─────────────────────────────────────────────────────────────────
def _organizar_fotos(mid: int, parar: threading.Event) -> bool:
    m = obter(mid)
    p = m["params"]
    pasta = Path(p["pasta"])
    raiz = Path(p.get("destino") or pasta / "Organizadas")
    mover = p.get("modo") == "mover"
    if not pasta.is_dir():
        raise RuntimeError(f"a pasta {pasta} não existe")
    lista = _lista_salva(mid, lambda: arquivos(pasta, FOTOS, ignorar=raiz))
    i = int(m["checkpoint"].get("i", 0))
    feitos = m["checkpoint"].get("movidos", []) if mover else []
    _atualizar(mid, total=len(lista), etapa="organizando por ano e mês")
    ultimo_save = time.time()
    while i < len(lista):
        if parar.is_set():
            _atualizar(mid, checkpoint={"i": i, "movidos": feitos}, feito=i)
            return False
        origem = Path(lista[i])
        if origem.exists():
            alvo = sem_conflito(destino_foto(raiz, data_da_foto(origem), origem.name))
            alvo.parent.mkdir(parents=True, exist_ok=True)
            if mover:
                shutil.move(str(origem), str(alvo))
                feitos.append([str(origem), str(alvo)])
            else:
                shutil.copy2(str(origem), str(alvo))
        i += 1
        if time.time() - ultimo_save > 1.5 or i == len(lista):
            _atualizar(mid, checkpoint={"i": i, "movidos": feitos}, feito=i, progresso=i / max(1, len(lista)),
                       etapa=f"{i} de {len(lista)} fotos")
            ultimo_save = time.time()
    _atualizar(mid, resultado=f"{len(lista)} fotos {'movidas' if mover else 'copiadas'} para {raiz}.")
    return True


def desfazer_fotos(mid: int) -> str:
    m = obter(mid)
    if m is None or m["tipo"] != "organizar_fotos":
        return "Essa missão não é de organizar fotos."
    movidos = m["checkpoint"].get("movidos") or []
    if not movidos:
        return "Nada para desfazer (as fotos foram copiadas; os originais estão no lugar)."
    voltaram = 0
    for orig, novo in reversed(movidos):
        if Path(novo).exists() and not Path(orig).exists():
            Path(orig).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(novo, orig)
            voltaram += 1
    raiz = Path(m["params"].get("destino") or Path(m["params"]["pasta"]) / "Organizadas")
    for d in sorted((x for x in raiz.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)) + [raiz]:
        try:
            d.rmdir()                                          # só apaga pasta que ficou vazia
        except OSError:
            pass
    _atualizar(mid, checkpoint={**m["checkpoint"], "movidos": []}, log=f"desfeita: {voltaram} fotos voltaram")
    return f"Voltei {voltaram} foto(s) para onde estavam."


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _converter_videos(mid: int, parar: threading.Event) -> bool:
    m = obter(mid)
    p = m["params"]
    pasta = Path(p["pasta"])
    saida = Path(p.get("destino") or pasta / "convertidos")
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("falta o ffmpeg (python -m pip install imageio-ffmpeg)")
    if not pasta.is_dir():
        raise RuntimeError(f"a pasta {pasta} não existe")
    lista = _lista_salva(mid, lambda: arquivos(pasta, VIDEOS, ignorar=saida))
    i = int(m["checkpoint"].get("i", 0))
    erros = int(m["checkpoint"].get("erros", 0))
    _atualizar(mid, total=len(lista), etapa="convertendo")
    saida.mkdir(parents=True, exist_ok=True)
    while i < len(lista):
        if parar.is_set():
            _atualizar(mid, checkpoint={"i": i, "erros": erros}, feito=i)
            return False
        origem = Path(lista[i])
        destino = sem_conflito(saida / (origem.stem + ".mp4"))
        temp = destino.with_name(destino.stem + ".parcial.mp4")
        _atualizar(mid, etapa=f"{i + 1} de {len(lista)}: {origem.name}")
        proc = subprocess.Popen(args_ffmpeg(ff, str(origem), str(temp), int(p.get("crf") or 23)),
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **CNW)
        while proc.poll() is None:
            if parar.wait(0.5):
                proc.kill()
                proc.wait()
                temp.unlink(missing_ok=True)
                _atualizar(mid, checkpoint={"i": i, "erros": erros}, feito=i)
                return False
        if proc.returncode == 0 and temp.exists():
            temp.replace(destino)
        else:
            erros += 1
            temp.unlink(missing_ok=True)
            _atualizar(mid, log=f"não converti {origem.name}")
        i += 1
        _atualizar(mid, checkpoint={"i": i, "erros": erros}, feito=i, progresso=i / max(1, len(lista)))
    _atualizar(mid, resultado=f"{len(lista) - erros} vídeo(s) em {saida}" + (f"; {erros} com erro." if erros else "."))
    return True


def _consultar_preco(params: dict) -> float | None:
    from plugins import vigia_preco
    v = {"produto": params.get("produto", ""), "url": params.get("url", "")}
    r = vigia_preco.consultar(v)
    return float(r["preco"]) if r and r.get("preco") else None


def _monitorar_preco(mid: int, parar: threading.Event) -> bool:
    m = obter(mid)
    p = m["params"]
    dias = float(p.get("dias") or 7)
    intervalo = float(p.get("intervalo_h") or 3)
    inicio = m["checkpoint"].get("inicio") or m["criada"]
    fim = inicio + dias * 86400
    hist = m["checkpoint"].get("historico", [])
    ultima = m["checkpoint"].get("ultima", 0)
    alvo = float(p.get("alvo") or 0)
    while time.time() < fim:
        if time.time() >= proxima_consulta(ultima, intervalo):
            preco = _consultar_preco(p)
            ultima = time.time()
            if preco:
                menor = min([h[1] for h in hist], default=None)
                hist.append([ultima, preco])
                _atualizar(mid, log=f"R$ {preco:.2f}")
                if alvo and preco <= alvo:
                    _notificar(f"{p.get('produto') or 'O produto'} chegou a R$ {preco:.2f} (seu alvo: R$ {alvo:.2f}).",
                               "high")
                elif menor is not None and preco < menor * 0.97:
                    _notificar(f"{p.get('produto') or 'O produto'} caiu para R$ {preco:.2f} (antes R$ {menor:.2f}).")
            _atualizar(mid, checkpoint={"inicio": inicio, "historico": hist[-200:], "ultima": ultima},
                       feito=len(hist), etapa=(f"último: R$ {hist[-1][1]:.2f} · menor: R$ {min(h[1] for h in hist):.2f}"
                                               if hist else "sem preço ainda"))
        _atualizar(mid, progresso=min(1.0, (time.time() - inicio) / (fim - inicio)))
        if parar.wait(min(300.0, max(1.0, proxima_consulta(ultima, intervalo) - time.time()))):
            _atualizar(mid, checkpoint={"inicio": inicio, "historico": hist, "ultima": ultima})
            return False
    menor = min((h[1] for h in hist), default=None)
    _atualizar(mid, resultado=(f"Menor preço em {dias:g} dias: R$ {menor:.2f}." if menor else "Não achei o preço."))
    return True


def descrever(m: dict) -> str:
    estado = {"rodando": "rodando", "pausada": "pausada", "concluida": "concluída", "cancelada": "cancelada",
              "erro": "com erro", "fila": "na fila"}.get(m["estado"], m["estado"])
    return f"#{m['id']} {m['titulo']} — {estado}, {round(100 * m.get('progresso', 0))}% ({m.get('etapa', '')})"
