"""
Instalar e atualizar programas pelo winget (fork PT-BR 2.17, Windows).

    "Jarvis, tem atualização de programa?"         (winget upgrade)
    "Jarvis, atualiza o Chrome"                    → com confirmação
    "Jarvis, atualiza tudo"                        → com confirmação (lista antes)
    "Jarvis, instala o OBS"                        → procura, mostra o nome oficial e pede confirmação

Usa o winget, que já vem no Windows 10/11. Sempre com confirmação na tela.
"""

from __future__ import annotations

import re
import subprocess

from plugins._comum import confirmar, mostrar

PLUGIN = {
    "name": "apps_winget",
    "brief": "Windows apps via winget: list updates, update one/all, search and install (all confirmed).",
    "description": (
        "winget. action='atualizacoes' lists available updates. action='atualizar' with app (or 'tudo'). "
        "action='instalar' with app searches and installs after confirmation. action='procurar' with app."
    ),
    "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "app": {"type": "STRING"}},
                   "required": ["action"]},
}

_BASE = ["winget", "--disable-interactivity"]


def _rodar(args: list[str], timeout: float = 120) -> str:
    r = subprocess.run(["winget", *args, "--accept-source-agreements"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.stdout


def tabela(saida: str) -> list[dict]:
    """Tabela do winget (Nome  Id  Versão  Disponível…) → linhas (pura)."""
    linhas = [l.rstrip() for l in saida.splitlines() if l.strip()]
    cab = next((i for i, l in enumerate(linhas) if re.search(r"\b(Id|ID)\b", l) and re.search(r"Vers|Version", l)), None)
    if cab is None:
        return []
    h = linhas[cab]
    cols = [(m.start(), m.group(0)) for m in re.finditer(r"\S+", h)]
    itens = []
    for l in linhas[cab + 1:]:
        if set(l) <= set("-─ ") or re.match(r"^\d+ (atualiza|upgrade)", l, re.I):
            continue
        partes = [l[c[0]: (cols[i + 1][0] if i + 1 < len(cols) else None)].strip() for i, c in enumerate(cols)]
        if len(partes) >= 3 and partes[1]:
            itens.append({"nome": partes[0], "id": partes[1], "versao": partes[2],
                          "nova": partes[3] if len(partes) > 3 else ""})
    return itens


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "atualizacoes").lower()
    app = str(p.get("app") or "").strip()
    try:
        if a == "atualizacoes":
            itens = tabela(_rodar(["upgrade"]))
            if not itens:
                return "Tudo atualizado."
            mostrar(player, "ATUALIZAÇÕES", "\n".join(f"{i['nome']:<35} {i['versao']} → {i['nova']}" for i in itens))
            return f"{len(itens)} programa(s) com atualização: " + ", ".join(i["nome"] for i in itens[:6]) + "."
        if a == "atualizar":
            if app.lower() in ("tudo", "todos", ""):
                itens = tabela(_rodar(["upgrade"]))
                if not itens:
                    return "Tudo atualizado."
                return confirmar("winget_tudo", f"Atualizar {len(itens)} programa(s)?", ", ".join(i["nome"] for i in itens),
                                 lambda: _rodar(["upgrade", "--all", "--silent", "--accept-package-agreements"], 3600)[-300:]
                                 or "Atualização terminada.")
            alvo = next((i for i in tabela(_rodar(["upgrade"])) if app.lower() in i["nome"].lower()), None)
            if not alvo:
                return f"{app} já está atualizado (ou não achei)."
            return confirmar(f"winget_{alvo['id']}", f"Atualizar {alvo['nome']}?", f"{alvo['versao']} → {alvo['nova']}",
                             lambda: _rodar(["upgrade", "--id", alvo["id"], "-e", "--silent",
                                             "--accept-package-agreements"], 1800)[-300:] or "Atualizado.")
        achados = tabela(_rodar(["search", app], 60))
        if not achados:
            return f"Não achei '{app}' no winget."
        if a == "procurar":
            return "Achei: " + "; ".join(f"{i['nome']} ({i['id']})" for i in achados[:5]) + "."
        alvo = achados[0]
        return confirmar(f"winget_inst_{alvo['id']}", f"Instalar {alvo['nome']}?", f"Id: {alvo['id']} · versão {alvo['versao']}",
                         lambda: _rodar(["install", "--id", alvo["id"], "-e", "--silent", "--accept-package-agreements"],
                                        1800)[-300:] or "Instalado.")
    except FileNotFoundError:
        return "O winget não está disponível neste PC (instale o 'Instalador de Aplicativo' na Microsoft Store)."
    except Exception as e:
        return f"O winget falhou: {e}"
