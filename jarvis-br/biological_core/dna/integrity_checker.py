"""
Verificador de integridade e banco de células-tronco.

    verificar()  compara os arquivos de agora com o genoma: modificados, novos e ausentes, cada um
                 com a sua classe (vital, núcleo, plugin…). Instalou uma versão nova por cima?
                 Vira UM aviso ("versão nova instalada"), não centenas.

O banco de células-tronco (memory/biological/celulas_tronco.zip) é uma cópia confiável de todo o
código, feita junto com o genoma. É de lá que a regeneração restaura um arquivo quebrado — sempre
com autorização, conferindo o SHA-256 contra o genoma e guardando o arquivo atual como
"nome.mutante-DATA" (nada é apagado).
"""

from __future__ import annotations

import hashlib
import os
import time
import zipfile
from pathlib import Path

from biological_core.dna.digital_dna import DNA, classe_de, listar_arquivos

GRAVIDADE = {("modificado", "vital"): "critica", ("modificado", "nucleo"): "media", ("modificado", "plugin"): "baixa",
             ("ausente", "vital"): "critica", ("ausente", "nucleo"): "alta", ("ausente", "plugin"): "media",
             ("ausente", "celular"): "baixa", ("novo", "plugin"): "baixa"}
ORDEM = ("info", "baixa", "media", "alta", "critica")


class VerificadorIntegridade:
    def __init__(self, dna: DNA):
        self.dna = dna
        self.ultimo: dict = {}

    def verificar(self) -> dict:
        g = self.dna.genoma or {}
        arquivos = g.get("arquivos", {})
        modificados, ausentes = [], []
        for rel, info in arquivos.items():
            h = self.dna.impressao_atual(rel)
            if h is None:
                ausentes.append(rel)
            elif h != info.get("sha256"):
                modificados.append(rel)
        novos = [r for r in listar_arquivos(self.dna.raiz) if r not in arquivos] if arquivos else []
        total = max(1, len(arquivos))
        r = {"ts": time.time(), "situacao_genoma": self.dna.situacao, "total": len(arquivos),
             "modificados": modificados, "ausentes": ausentes, "novos": novos,
             "integridade": round(100.0 * (1 - (len(modificados) + len(ausentes)) / total), 1) if arquivos else 0.0,
             "versao_nova": bool(arquivos) and g.get("app_versao") not in (None, "?", self.dna.versao_app())}
        self.ultimo = r
        return r

    def sintomas(self, r: dict | None = None) -> list[dict]:
        """O relatório virando sintomas para o sistema imune (agrupados por tipo e classe)."""
        r = r or self.verificar()
        if r["situacao_genoma"] in ("adulterado", "corrompido"):
            return [{"categoria": "integridade", "gravidade": "critica", "modulo": "dna", "acao": r["situacao_genoma"],
                     "mensagem": f"o próprio genoma está {r['situacao_genoma']}: alguém ou algo mexeu no DNA do JARVIS",
                     "arquivos": [], "ameaca": True}]
        if r.get("versao_nova") and len(r["modificados"]) + len(r["novos"]) > 20:
            return [{"categoria": "integridade", "gravidade": "info", "modulo": "dna", "acao": "versao_nova",
                     "mensagem": f"versão nova instalada ({(self.dna.genoma or {}).get('app_versao')} → {self.dna.versao_app()}): "
                                 f"{len(r['modificados'])} arquivo(s) mudaram e {len(r['novos'])} chegaram. "
                                 "Diga 'Jarvis, reconhece a versão nova' para atualizar o DNA.",
                     "arquivos": [], "ameaca": False}]
        grupos: dict[tuple[str, str], list[str]] = {}
        for tipo in ("modificado", "ausente", "novo"):
            for rel in r[{"modificado": "modificados", "ausente": "ausentes", "novo": "novos"}[tipo]]:
                grupos.setdefault((tipo, classe_de(rel)), []).append(rel)
        out = []
        for (tipo, classe), rels in sorted(grupos.items()):
            grav = GRAVIDADE.get((tipo, classe), "info")
            nome = {"vital": "vital(is) do organismo", "nucleo": "do núcleo", "plugin": "de plugin",
                    "celular": "do celular", "teste": "de teste", "outro": "outro(s)"}[classe]
            verbo = {"modificado": "mudaram desde o DNA", "ausente": "SUMIRAM", "novo": "são novos (não estão no DNA)"}[tipo]
            exemplos = ", ".join(rels[:4]) + ("…" if len(rels) > 4 else "")
            out.append({"categoria": "integridade", "gravidade": grav, "modulo": "dna", "acao": f"{tipo}_{classe}",
                        "mensagem": f"{len(rels)} arquivo(s) {nome} {verbo}: {exemplos}", "arquivos": rels,
                        "ameaca": classe == "vital" and tipo != "novo"})
        return out


class BancoCelulasTronco:
    def __init__(self, arquivo_zip: Path, raiz: Path):
        self.arquivo = Path(arquivo_zip)
        self.raiz = Path(raiz)

    def criar(self, rels: list[str] | None = None) -> dict:
        rels = rels if rels is not None else listar_arquivos(self.raiz)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.arquivo.with_name(self.arquivo.name + ".tmp")
        n = 0
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for rel in rels:
                p = self.raiz / rel
                if p.is_file():
                    z.write(p, rel)
                    n += 1
        os.replace(tmp, self.arquivo)
        return {"arquivos": n, "bytes": self.arquivo.stat().st_size}

    def existe(self) -> bool:
        return self.arquivo.is_file()

    def ler(self, rel: str) -> bytes | None:
        try:
            with zipfile.ZipFile(self.arquivo) as z:
                return z.read(rel)
        except (KeyError, OSError, zipfile.BadZipFile):
            return None

    def restaurar(self, rel: str, ficha: str | None, autorizacoes, genoma: dict | None) -> tuple[bool, str]:
        """Volta 'rel' para a cópia confiável. Exige a ficha 'restaurar_codigo:rel'. Nunca apaga o atual."""
        if not autorizacoes.validar(ficha, f"restaurar_codigo:{rel}"):
            return False, "Recusado: restaurar código precisa da sua autorização."
        dados = self.ler(rel)
        if dados is None:
            return False, f"Não há cópia confiável de {rel} no banco de células-tronco."
        esperado = ((genoma or {}).get("arquivos", {}).get(rel) or {}).get("sha256")
        if esperado and hashlib.sha256(dados).hexdigest() != esperado:
            return False, f"A cópia de {rel} não bate com o DNA; não restaurei."
        alvo = self.raiz / rel
        guardado = ""
        if alvo.exists():
            guardado = f"{alvo.name}.mutante-{time.strftime('%Y%m%d-%H%M%S')}"
            os.replace(alvo, alvo.with_name(guardado))
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
        return True, f"{rel} voltou para a cópia confiável" + (f" (o arquivo que estava lá ficou como {guardado})." if guardado else ".")
