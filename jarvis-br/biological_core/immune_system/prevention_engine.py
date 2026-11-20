"""
Camada 7 — PREVENÇÃO: evitar o problema antes que ele aconteça.

    • pontos de restauração dos seus DADOS (memory/**/*.json e config/*.json): cada versão de arquivo
      é guardada uma vez só, pelo conteúdo (memory/biological/pontos/blobs), e cada ponto é uma lista
      de "arquivo → versão". Dez pontos custam quase o mesmo espaço que um. Um ponto igual ao anterior
      nem é criado. config/api_keys.json fica de fora de propósito (tem as suas chaves);
    • checagem dos dados: abre cada JSON que mudou desde a última vez; quebrado vira sintoma (com a
      última versão boa já localizada para o reparo) — e os bancos SQLite passam por "quick_check";
    • verificação antes de executar: o plugin ainda compila? bate com o DNA?
    • avaliação de risco de um reparo antes de deixar fazer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

from biological_core.config import gravar_json, ler_json

TAMANHO_MAXIMO = 5_000_000
NAO_COPIAR = {"api_keys.json"}


class Prevencao:
    def __init__(self, raiz: Path, pasta: Path, manter: int = 10):
        self.raiz = Path(raiz)
        self.pasta = Path(pasta) / "pontos"
        self.blobs = self.pasta / "blobs"
        self.manter = manter
        self.estado_arq = Path(pasta) / "prevencao.json"
        self.estado = ler_json(self.estado_arq, {}) or {}

    # ── quais arquivos são dados ──────────────────────────────────────────────
    def arquivos_de_dados(self) -> list[Path]:
        out = []
        mem, conf = self.raiz / "memory", self.raiz / "config"
        bio = self.pasta.parent.resolve()
        if mem.is_dir():
            for p in mem.rglob("*.json"):
                try:
                    if bio in p.resolve().parents or p.stat().st_size > TAMANHO_MAXIMO:
                        continue
                except OSError:
                    continue
                out.append(p)
        if conf.is_dir():
            out += [p for p in conf.glob("*.json") if p.name not in NAO_COPIAR and p.stat().st_size <= TAMANHO_MAXIMO]
        return sorted(out)

    def _rel(self, p: Path) -> str:
        return Path(p).resolve().relative_to(self.raiz.resolve()).as_posix()

    # ── pontos de restauração ─────────────────────────────────────────────────
    def criar_ponto(self, motivo: str = "rotina") -> str | None:
        """Guarda a versão atual de cada arquivo de dados. None se nada mudou desde o último ponto."""
        mapa = {}
        for p in self.arquivos_de_dados():
            try:
                dados = p.read_bytes()
            except OSError:
                continue
            h = hashlib.sha256(dados).hexdigest()
            blob = self.blobs / f"{h}.json"
            if not blob.exists():
                blob.parent.mkdir(parents=True, exist_ok=True)
                tmp = blob.with_suffix(".tmp")
                tmp.write_bytes(dados)
                os.replace(tmp, blob)
            mapa[self._rel(p)] = h
        pontos = self.pontos()
        if pontos and pontos[-1].get("arquivos") == mapa:
            return None
        pid = time.strftime("%Y%m%d-%H%M%S")
        while (self.pasta / f"{pid}.json").exists():
            pid += "b"
        gravar_json(self.pasta / f"{pid}.json", {"id": pid, "ts": time.time(), "motivo": motivo, "arquivos": mapa})
        self.podar()
        return pid

    def pontos(self) -> list[dict]:
        """Os pontos, do mais velho ao mais novo (lidos de novo só quando a pasta muda)."""
        if not self.pasta.is_dir():
            return []
        chave = self.pasta.stat().st_mtime_ns
        cache = getattr(self, "_cache_pontos", None)
        if cache and cache[0] == chave:
            return list(cache[1])
        lista = [d for d in (ler_json(p, None) for p in sorted(self.pasta.glob("*.json"))) if isinstance(d, dict)]
        self._cache_pontos = (chave, lista)
        return list(lista)

    def podar(self) -> int:
        pontos = self.pontos()
        sobra = pontos[-self.manter:]
        for p in pontos[:-self.manter]:
            try:
                (self.pasta / f"{p['id']}.json").unlink()
            except OSError:
                pass
        usados = {h for p in sobra for h in p.get("arquivos", {}).values()}
        n = 0
        if self.blobs.is_dir():
            for b in self.blobs.glob("*.json"):
                if b.stem not in usados:
                    try:
                        b.unlink()
                        n += 1
                    except OSError:
                        pass
        return n

    def ultima_versao_boa(self, caminho: Path | str) -> tuple[str, Path] | None:
        """(id do ponto, blob) da versão mais nova de 'caminho' que abre como JSON."""
        rel = self._rel(self.raiz / caminho) if not Path(caminho).is_absolute() else self._rel(Path(caminho))
        atual = None
        try:
            atual = hashlib.sha256((self.raiz / rel).read_bytes()).hexdigest()
        except OSError:
            pass
        for p in reversed(self.pontos()):
            h = p.get("arquivos", {}).get(rel)
            if not h or h == atual:
                continue
            blob = self.blobs / f"{h}.json"
            try:
                json.loads(blob.read_text(encoding="utf-8"))
                return p["id"], blob
            except (OSError, ValueError):
                continue
        return None

    def restaurar_arquivo(self, rel: str, blob: Path) -> str:
        """Põe a versão boa no lugar e guarda a quebrada como 'nome.corrompido-DATA' (nada é apagado)."""
        alvo = self.raiz / rel
        guardado = ""
        if alvo.exists():
            guardado = f"{alvo.name}.corrompido-{time.strftime('%Y%m%d-%H%M%S')}"
            os.replace(alvo, alvo.with_name(guardado))
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(blob, alvo)
        return guardado

    # ── checagens ─────────────────────────────────────────────────────────────
    def checar_dados(self, so_mudados: bool = True) -> list[dict]:
        """Arquivos de dados que não abrem mais (JSON quebrado). Devolve [{arquivo, erro, versao_boa}]."""
        vistos = self.estado.setdefault("mtimes", {})
        ruins = []
        for p in self.arquivos_de_dados():
            rel = self._rel(p)
            try:
                mt = p.stat().st_mtime_ns
            except OSError:
                continue
            if so_mudados and vistos.get(rel) == mt:
                continue
            try:
                txt = p.read_text(encoding="utf-8")
                if txt.strip():
                    json.loads(txt)
                vistos[rel] = mt
            except (ValueError, UnicodeDecodeError) as e:
                boa = self.ultima_versao_boa(rel)
                ruins.append({"arquivo": rel, "erro": f"{type(e).__name__}: {e}"[:200], "versao_boa": boa[0] if boa else None})
            except OSError:
                continue
        self._gravar()
        return ruins

    def checar_bancos(self) -> list[dict]:
        ruins = []
        mem = self.raiz / "memory"
        for db in (mem.glob("*.db") if mem.is_dir() else []):
            try:
                c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
                ok = c.execute("PRAGMA quick_check").fetchone()[0]
                c.close()
                if ok != "ok":
                    ruins.append({"arquivo": self._rel(db), "erro": str(ok)[:200]})
            except sqlite3.DatabaseError as e:
                ruins.append({"arquivo": self._rel(db), "erro": str(e)[:200]})
        return ruins

    def verificar_codigo(self, caminho: Path) -> tuple[bool, str]:
        """O arquivo de código ainda compila? (verificação antes de executar/recarregar)"""
        try:
            compile(Path(caminho).read_text(encoding="utf-8"), str(caminho), "exec")
            return True, "compila"
        except SyntaxError as e:
            return False, f"erro de sintaxe na linha {e.lineno}: {e.msg}"
        except (OSError, UnicodeDecodeError) as e:
            return False, str(e)

    def avaliar_risco(self, tratamento: str, alvo: str = "", gravidade: str = "media") -> float:
        """0 (nenhum) a 1 (alto). Quanto pode dar errado se este reparo for feito agora."""
        base = {"observar": 0.0, "isolar_temporario": 0.05, "esperar_rede": 0.05, "aumentar_limite": 0.1,
                "reflexo_memoria": 0.05, "recarregar_modulo": 0.3, "recriar_pasta": 0.2, "restaurar_json": 0.5,
                "restaurar_codigo": 0.6}.get(tratamento, 0.1)
        if alvo.startswith(("biological_core/", "core/", "main.py", "ui.py")):
            base += 0.3
        if gravidade == "critica":
            base += 0.1
        return round(min(1.0, base), 2)

    def _gravar(self) -> None:
        try:
            gravar_json(self.estado_arq, self.estado)
        except Exception:
            pass
