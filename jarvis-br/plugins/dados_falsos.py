"""Dados falsos para teste (2.18): pessoas brasileiras fictícias em JSON/CSV para popular banco de dados de projeto."""
from __future__ import annotations

import json
import random

from plugins._lote2 import P, rodar
from plugins.validador_documentos import gerar_cpf

PLUGIN = P("dados_falsos", "Fake Brazilian test data for dev projects: people (name, email, phone, CPF, city), products, as JSON or CSV saved to Documents/JARVIS.",
           "pessoas | produtos",
           "pessoas/produtos: quantidade (default 10, max 1000), formato (json|csv).", "quantidade formato")

NOMES = "Ana Bruno Carla Diego Eduarda Felipe Gabriela Heitor Isabela João Larissa Lucas Mariana Miguel Paula Rafael Sofia Thiago Vitória Yuri".split()
SOBRE = "Silva Souza Oliveira Santos Lima Pereira Costa Rodrigues Almeida Nascimento Ferreira Araújo Barbosa Rocha".split()
CIDADES = ["Goiânia/GO", "Anápolis/GO", "Brasília/DF", "São Paulo/SP", "Belo Horizonte/MG", "Salvador/BA", "Curitiba/PR",
           "Recife/PE", "Fortaleza/CE", "Porto Alegre/RS"]
PRODUTOS = "Body Conjunto Vestido Short Camiseta Pijama Macacão Jaqueta Calça Saia Moletom Meia".split()
CORES = "azul rosa branco preto amarelo verde lilás vermelho".split()


def pessoa(rng=random) -> dict:
    n, s = rng.choice(NOMES), rng.choice(SOBRE)
    return {"nome": f"{n} {s}", "email": f"{n.lower()}.{s.lower()}{rng.randint(1, 99)}@exemplo.com".replace("ã", "a")
            .replace("ú", "u").replace("ó", "o").replace("í", "i"),
            "telefone": f"(62) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}", "cpf": gerar_cpf(rng),
            "cidade": rng.choice(CIDADES), "idade": rng.randint(18, 80)}


def produto(rng=random) -> dict:
    return {"sku": f"CM{rng.randint(10000, 99999)}", "nome": f"{rng.choice(PRODUTOS)} {rng.choice(CORES)}",
            "tamanho": rng.choice(["RN", "P", "M", "G", "1", "2", "4", "6", "8"]), "preco": round(rng.uniform(19, 199), 2),
            "estoque": rng.randint(0, 40)}


def _go(p, pl):
    from plugins._comum import pasta_jarvis
    from plugins.conversor_dados import lista_para_csv
    a = str(p.get("action")).lower()
    q = max(1, min(1000, int(p.get("quantidade") or 10)))
    d = [(pessoa if a == "pessoas" else produto)() for _ in range(q)]
    fmt = "csv" if str(p.get("formato")).lower() == "csv" else "json"
    arq = pasta_jarvis("DadosTeste") / f"{a}_{q}.{fmt}"
    arq.write_text(lista_para_csv(d) if fmt == "csv" else json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"{q} {a} fictícios salvos em {arq}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, {"pessoas": _go, "produtos": _go}, player)
