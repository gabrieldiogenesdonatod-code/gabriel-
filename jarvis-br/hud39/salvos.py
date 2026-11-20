"""
★ SALVOS (fork PT-BR 3.9.3) — guarda o que você quiser, para achar depois.

    Na caixa de texto:  salvar: comprar tecido para a Cristal Malhas
                        salva: senha do wi-fi da loja fica na gaveta
    Por voz:            "Jarvis, salva que ..."  /  "o que eu salvei?"  (plugin salvos)
    Nos vídeos:         a ★ de cada resultado do YouTube salva o vídeo
    No painel ★ SALVOS: abrir/usar e apagar cada item

Fica em memory/salvos.json (texto puro, no seu PC). Até 500 itens; os mais novos primeiro.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "memory" / "salvos.json"
LIMITE = 500
_trava = threading.Lock()
_PREFIXO = re.compile(r"^\s*(salvar|salva|salve|guardar|guarda|guarde)\s*:\s*", re.I)


def _ler() -> list:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return [d for d in dados if isinstance(d, dict) and d.get("id")] if isinstance(dados, list) else []
    except Exception:
        return []


def _gravar(itens: list) -> None:
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(ARQUIVO.parent), prefix=".salvos-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(itens, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ARQUIVO)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def listar() -> list:
    with _trava:
        return _ler()


def adicionar(texto: str, tipo: str = "texto", url: str = "", titulo: str = "") -> dict:
    """Salva um item. Repetir o mesmo texto/vídeo não duplica: só sobe para o topo."""
    texto = " ".join(str(texto or "").split())[:1000]
    url = str(url or "").strip()[:500]
    if not texto and not url:
        raise ValueError("nada para salvar")
    item = {"id": uuid.uuid4().hex[:10], "tipo": "video" if tipo == "video" else "texto", "texto": texto,
            "url": url, "titulo": str(titulo or "")[:200], "quando": time.strftime("%d/%m/%Y %H:%M")}
    with _trava:
        itens = [i for i in _ler() if not ((url and i.get("url") == url) or (not url and i.get("texto") == texto))]
        itens.insert(0, item)
        _gravar(itens[:LIMITE])
    return item


def apagar(item_id: str) -> bool:
    with _trava:
        itens = _ler()
        novos = [i for i in itens if i.get("id") != item_id]
        if len(novos) == len(itens):
            return False
        _gravar(novos)
        return True


def procurar(termo: str) -> list:
    t = str(termo or "").lower().strip()
    return [i for i in listar() if not t or t in (i.get("texto", "") + " " + i.get("titulo", "")).lower()]


def pedido_de_salvar(texto: str) -> str | None:
    """'salvar: X' → 'X'. Outro texto → None. Pura."""
    m = _PREFIXO.match(texto or "")
    if not m:
        return None
    return texto[m.end():].strip()
