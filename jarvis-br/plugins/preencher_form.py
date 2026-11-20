"""
Preenchedor de formulários por voz (fork PT-BR 2.11).

Guarda os seus dados que você vive digitando em site (nome, e-mail, telefone,
CPF, endereço…) e preenche o campo onde o cursor estiver, por voz.

    "Jarvis, guarda meu e-mail: fulano@gmail.com."      "Jarvis, meu CEP é 74000-000."
    (clica no campo do site)  "Jarvis, preenche o e-mail."   → digita no campo
    "Jarvis, quais dados você tem meus?"     "Jarvis, esquece meu CPF."

Ele digita no campo que estiver em foco (por isso clique no campo certo antes).
Os dados ficam só no seu PC, em memory/meus_dados.json. NÃO guarda senha — isso
é coisa pro gerenciador de senhas do navegador.
"""

from __future__ import annotations

import re
import threading
import unicodedata

from plugins._comum import MEMORIA, WIN, gravar_json, ler_json, mostrar, powershell, registrar

PLUGIN = {
    "name": "preencher_form",
    "brief": "Voice form-filler: stores your common fields (name, email, phone, CPF, address) and types them in.",
    "description": (
        "Stores the user's common form fields and types them into the focused field by voice. action: 'salvar' "
        "(campo + valor, e.g. campo='email'), 'preencher' (campo → types that value into whatever field has focus), "
        "'ver' (list stored fields, CPF/RG masked), 'remover' (campo). Use for 'guarda meu email: ...', 'meu CPF é "
        "...', 'preenche o email/telefone/CPF', 'quais dados você tem', 'esquece meu X'. It types into the focused "
        "field, so the user should click the right field first. Does NOT store passwords."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "salvar | preencher | ver | remover"},
            "campo": {"type": "STRING", "description": "nome | email | telefone | cpf | cep | endereco | cidade ..."},
            "valor": {"type": "STRING", "description": "the value (for 'salvar')"},
        },
    },
}

ARQ = MEMORIA / "meus_dados.json"        # o carregador dos testes troca este caminho
_lock = threading.RLock()

CAMPOS = {
    "nome": ["nome", "nome completo"], "email": ["email", "e-mail", "e mail", "imeio"],
    "telefone": ["telefone", "celular", "fone", "whatsapp", "numero de telefone"],
    "cpf": ["cpf"], "rg": ["rg", "identidade"], "cep": ["cep"],
    "endereco": ["endereco", "endereço", "rua", "logradouro"], "numero": ["numero", "número da casa", "num"],
    "bairro": ["bairro"], "cidade": ["cidade"], "estado": ["estado", "uf"],
    "data_nascimento": ["data de nascimento", "nascimento", "aniversario"], "nome_mae": ["nome da mae", "mae"],
    "profissao": ["profissao", "profissão", "cargo", "ocupacao"], "empresa": ["empresa"],
}
SENSIVEIS = {"cpf", "rg"}
PROIBIDO = ("senha", "password", "cartao de credito", "cartão", "cvv", "codigo de seguranca")


def dobrar(t: str) -> str:
    return unicodedata.normalize("NFKD", str(t or "").lower()).encode("ascii", "ignore").decode()


def campo_canonico(bruto: str) -> str:
    """'e-mail', 'meu celular', 'número de telefone' → a chave padrão (puro). '' se não reconhecer."""
    t = dobrar(bruto).strip().strip(":")
    t = re.sub(r"^(meu|minha|o|a)\s+", "", t)
    for chave, nomes in CAMPOS.items():
        if t == chave or t in [dobrar(n) for n in nomes]:
            return chave
    for chave, nomes in CAMPOS.items():
        if any(dobrar(n) in t or t in dobrar(n) for n in nomes):
            return chave
    return ""


def eh_proibido(campo: str) -> bool:
    t = dobrar(campo)
    return any(p in t for p in PROIBIDO)


def mascarar(campo: str, valor: str) -> str:
    if campo in SENSIVEIS and len(valor) > 4:
        return "•••" + valor[-3:]
    return valor


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    return d if isinstance(d, dict) else {}


def _gravar(d: dict) -> None:
    with _lock:
        gravar_json(ARQ, d)


# ── digitar no campo em foco ─────────────────────────────────────────────────
def digitar(valor: str) -> bool:
    """Põe o valor no campo em foco. Tenta colar (aguenta acento); senão digita tecla a tecla."""
    valor = str(valor or "")
    if WIN:
        try:
            if powershell(f"Set-Clipboard -Value {_ps_aspas(valor)}")[0] == 0:
                import pyautogui
                pyautogui.hotkey("ctrl", "v")
                return True
        except Exception as e:
            print(f"[Form] colar: {e}")
    try:
        import pyautogui
        pyautogui.typewrite(valor, interval=0.02)
        return True
    except Exception as e:
        print(f"[Form] digitar: {e}")
        return False


def _ps_aspas(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


# ── ações ──────────────────────────────────────────────────────────────────────
def salvar(campo: str, valor: str) -> str:
    if eh_proibido(campo):
        return "Senha e cartão eu não guardo — isso fica no gerenciador de senhas do navegador, que é mais seguro."
    chave = campo_canonico(campo) or dobrar(campo).strip().replace(" ", "_")[:24]
    valor = " ".join(str(valor or "").split()).strip()
    if not chave:
        return "Qual dado é esse? (ex.: email, telefone, CPF, CEP...)"
    if not valor:
        return f"Qual é o seu {chave.replace('_', ' ')}?"
    with _lock:
        d = dados()
        d[chave] = valor
        _gravar(d)
    return f"Guardei o seu {chave.replace('_', ' ')}. Clique no campo do site e diga 'preenche o {chave}'."


def preencher(campo: str) -> str:
    chave = campo_canonico(campo)
    with _lock:
        d = dados()
    if not chave or chave not in d:
        tem = ", ".join(k.replace("_", " ") for k in d) or "nenhum ainda"
        return (f"Não tenho o seu {campo}. Dados que eu tenho: {tem}. "
                f"Guarde com 'meu {campo} é ...'." if campo else "Qual campo? " + (f"Tenho: {tem}." if d else ""))
    ok = digitar(d[chave])
    if not ok:
        return (f"Não consegui digitar (o pyautogui pode não estar instalado). O seu {chave.replace('_', ' ')} é: "
                f"{d[chave]} — dá pra copiar daí.")
    return f"Preenchi o {chave.replace('_', ' ')} no campo em foco. Se foi no lugar errado, desfaz com Ctrl+Z."


def ver(player=None) -> str:
    with _lock:
        d = dados()
    if not d:
        return "Não tenho nenhum dado seu guardado. Diga, por exemplo, 'guarda meu email: ...'."
    linhas = [f"{k.replace('_', ' ')}: {mascarar(k, v)}" for k, v in d.items()]
    mostrar(player, "MEUS DADOS", "\n".join(linhas))
    return f"Tenho {len(d)} dado(s) seu(s): {', '.join(k.replace('_', ' ') for k in d)}. (CPF/RG aparecem mascarados.)"


def remover(campo: str) -> str:
    chave = campo_canonico(campo) or dobrar(campo).strip().replace(" ", "_")
    with _lock:
        d = dados()
        if chave not in d:
            return f"Não tinha o seu {campo} guardado."
        del d[chave]
        _gravar(d)
    registrar(None, f"🧾 Esqueci o dado: {chave}")
    return f"Esqueci o seu {chave.replace('_', ' ')}."


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = dobrar(p.get("action") or "ver").strip()
    campo = str(p.get("campo") or "")
    try:
        if acao in ("salvar", "guardar", "salva"):
            return salvar(campo, str(p.get("valor") or ""))
        if acao in ("preencher", "preenche", "digitar", "colar"):
            return preencher(campo)
        if acao in ("ver", "listar", "quais", "meus_dados"):
            return ver(player)
        if acao in ("remover", "esquecer", "apagar", "esquece"):
            return remover(campo)
        return ver(player)
    except Exception as e:
        return f"O preenchedor falhou: {e}"
