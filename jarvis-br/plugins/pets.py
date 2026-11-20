"""Pets (2.18): vacinas, vermífugo, banho e ração com próxima data; idade em 'anos humanos'."""
from __future__ import annotations

from datetime import date, timedelta

from plugins._lote2 import Colecao, P, norm, numeros, rodar
from plugins.calculadora_datas import ler_data

PLUGIN = P("pets", "Pet care: register pet, log vaccine/dewormer/bath/food with repeat interval, what's due, age in human years.",
           "cadastrar | anotar | vencendo | ver | idade_humana",
           "cadastrar: nome, especie (cao|gato), data (birth). anotar: nome, cuidado (vacina|vermifugo|banho|racao|...), dias "
           "(repeat interval). vencendo: due in 7 days.",
           "nome especie data cuidado dias")

PETS = Colecao("pets")
INTERVALO = {"vacina": 365, "vermifugo": 90, "banho": 15, "racao": 30, "antipulgas": 30}


def anos_humanos(anos: float, especie: str) -> int:
    if anos <= 1:
        return round(anos * 15)
    if anos <= 2:
        return round(15 + (anos - 1) * 9)
    return round(24 + (anos - 2) * (4 if norm(especie).startswith("gat") else 5))


def _go(p, pl):
    a, nome = str(p.get("action")).lower(), p.get("nome")
    if a == "cadastrar":
        PETS.por(nome, {"especie": p.get("especie") or "cão",
                        "nasc": ler_data(p.get("data")).isoformat() if p.get("data") else None, "cuidados": {}})
        return f"{nome} cadastrado."
    if a == "vencendo":
        out = []
        for pet in PETS.tudo().values():
            for c, (ult, dias) in pet["cuidados"].items():
                prox = date.fromisoformat(ult) + timedelta(dias)
                if (prox - date.today()).days <= 7:
                    out.append(f"{pet['nome']}: {c} em {prox:%d/%m}")
        return "; ".join(out) or "Nada vencendo nos próximos 7 dias."
    pet = PETS.pegar(nome)
    if not pet:
        return "Não achei esse pet."
    if a == "anotar":
        c = norm(p.get("cuidado") or "banho")
        pet["cuidados"][c] = [date.today().isoformat(), int((numeros(p.get("dias")) or [INTERVALO.get(c, 30)])[0])]
        PETS.por(pet["nome"], pet)
        return f"{c} de {pet['nome']} anotado; próximo em {pet['cuidados'][c][1]} dias."
    if a == "idade_humana":
        if not pet.get("nasc"):
            return "Não sei quando ele nasceu."
        anos = (date.today() - date.fromisoformat(pet["nasc"])).days / 365.25
        return f"{pet['nome']} tem {anos:.1f} anos, como um humano de ~{anos_humanos(anos, pet['especie'])}."
    feitos = ", ".join(f"{c} em {u}" for c, (u, _) in pet["cuidados"].items())
    return f"{pet['nome']} ({pet['especie']}): {feitos or 'sem registros'}."


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("cadastrar anotar vencendo ver idade_humana".split(), _go), player)
