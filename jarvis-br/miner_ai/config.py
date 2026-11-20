"""Configuração e arquivos do MINER AI. Só endereços PÚBLICOS ficam aqui — nunca chave nem frase de recuperação."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from miner_ai import seguranca

PASTA = Path(os.environ.get("MINER_AI_DADOS") or Path(__file__).resolve().parent.parent / "memory" / "miner_ai")
_lock = threading.Lock()

PADRAO: dict = {
    "carteira_btc": "",                      # endereço PÚBLICO (1…, 3…, bc1…)
    "carteira_xmr": "",                      # endereço PÚBLICO Monero (4… ou 8…)
    "pool_btc": "solo.ckpool.org:3333",      # pool SOLO: se achar um bloco, a recompensa vai para o seu endereço
    "pool_xmr": "pool.supportxmr.com:443",
    "xmrig": "",                             # caminho do xmrig.exe que VOCÊ baixou (github.com/xmrig/xmrig)
    "nome_maquina": "jarvis",
    "threads": 0,                            # 0 = o cérebro escolhe (metade dos núcleos)
    "cpu_max": 50,                           # % de uso de CPU por núcleo usado (o resto do tempo ele descansa)
    "temperatura_max": 80.0,                 # °C: acima disso pausa; 5 °C antes reduz a intensidade
    "tdp_watts": 15.0,                       # potência do processador (notebook U: 15 W). Tem medidor de tomada? use watts_medidos
    "watts_medidos": 0.0,                    # se você mediu na tomada o quanto aumenta ao minerar, ponha aqui (vale mais que a estimativa)
    "tarifa": 0.95,                          # R$ por kWh (veja na conta de luz, com impostos)
    "economico": True,                       # modo econômico: 1 núcleo, CPU 30%, para na bateria, só com o PC parado
    "ocioso_min": 5,                         # no modo econômico, só minera com o PC parado há N minutos (Windows)
    "horarios": [],                          # ex.: ["22:00-07:00"] — vazio = qualquer hora
    "parar_na_bateria": True,
    "horas_max": 8.0,                        # por sessão
}

CAMPOS_ENDERECO = {"carteira_btc": seguranca.btc_valido, "carteira_xmr": seguranca.xmr_valido}


def arquivo(nome: str) -> Path:
    PASTA.mkdir(parents=True, exist_ok=True)
    return PASTA / nome


def ler_json(nome: str, padrao):
    try:
        return json.loads(arquivo(nome).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def gravar_json(nome: str, dados) -> None:
    with _lock:
        a = arquivo(nome)
        tmp = a.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(a)


def carregar() -> dict:
    return {**PADRAO, **(ler_json("config.json", {}) or {})}


def alterar(mudancas: dict) -> tuple[dict, list[str]]:
    """Valida e grava. Devolve (config, erros). Segredo nunca é gravado, nem por engano."""
    cfg, erros = carregar(), []
    for k, v in (mudancas or {}).items():
        if k not in PADRAO:
            erros.append(f"não conheço o ajuste '{k}'")
            continue
        segredo = seguranca.parece_segredo(v) if isinstance(v, str) else None
        if segredo:
            erros.append(f"isso parece {segredo}: NUNCA guardo isso. Use só o endereço público de receber")
            continue
        if k in CAMPOS_ENDERECO and v and not CAMPOS_ENDERECO[k](v):
            erros.append(f"{k}: endereço inválido (confira se copiou inteiro)")
            continue
        padrao = PADRAO[k]
        try:
            if isinstance(padrao, bool):
                v = v if isinstance(v, bool) else str(v).strip().lower() in ("1", "sim", "true", "ligado", "liga", "s")
            elif isinstance(padrao, (int, float)) and not isinstance(padrao, bool):
                v = type(padrao)(float(str(v).replace(",", ".")))
                if v < 0:
                    raise ValueError
            elif isinstance(padrao, list):
                v = [x.strip() for x in (v if isinstance(v, list) else str(v).replace(";", ",").split(",")) if str(x).strip()]
            else:
                v = str(v).strip().strip('"')
        except Exception:
            erros.append(f"{k}: valor inválido")
            continue
        cfg[k] = v
    if not erros or len(erros) < len(mudancas or {}):
        gravar_json("config.json", cfg)
    return cfg, erros
