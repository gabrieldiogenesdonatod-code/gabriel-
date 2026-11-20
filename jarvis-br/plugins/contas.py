"""
Contas a vencer (fork PT-BR 2.5).

    "Jarvis, lê esse boleto"                 (o PDF mais novo da pasta de contas/Downloads, ou um arquivo)
    "Jarvis, anota essa conta: 34191.79001 01043…"   (a linha digitável, falada ou colada)
    "Jarvis, olha a conta na foto"           (foto do boleto em papel — com a chave do Gemini)
    "Jarvis, quais contas vencem essa semana?"
    "Jarvis, paguei a conta de luz"          "Jarvis, copia o código da conta de luz"

Ele avisa sozinho 3 dias antes ("A conta de luz vence sexta, R$ 142."), no dia
e se passar do dia. De onde as contas vêm:
  • PDFs que caírem na pasta Documentos\\JARVIS\\Contas ou em Downloads (só os que
    têm um código de boleto válido);
  • o seu e-mail, se você ligar em ⚙ → Contas a vencer (IMAP com SENHA DE APP:
    no Gmail, myaccount.google.com → Segurança → Senhas de app). Ele só lê
    e-mails com anexo PDF e só guarda as contas;
  • o que você ditar ou mandar foto.
Tudo fica em memory/contas.json, só no seu PC. Nada é pago por ele.
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from plugins import _boleto as B
from plugins._comum import MEMORIA, cfg, gravar_json, ler_json, mostrar, pasta_usuario, registrar

PLUGIN = {
    "name": "contas",
    "brief": "Bills to pay: reads boletos (PDF, typed line, photo, e-mail) and warns 3 days before they are due.",
    "description": (
        "Bills/boletos. action='ler' reads a boleto: arquivo (PDF/photo path; empty = newest PDF in the bills folder "
        "or Downloads) or linha (the digit line); optional descricao ('conta de luz'). 'adicionar' with descricao, "
        "valor and vencimento (dd/mm). 'listar' shows unpaid bills (optional dias). 'pagar' with descricao or id "
        "marks as paid. 'copiar' with descricao copies the digit line to the clipboard. 'email' checks the e-mail "
        "now. 'apagar' with id. JARVIS warns by itself 3 days before, on the day and if overdue. It never pays."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ler | adicionar | listar | pagar | copiar | email | apagar"},
            "arquivo": {"type": "STRING"}, "linha": {"type": "STRING"}, "descricao": {"type": "STRING"},
            "valor": {"type": "NUMBER"}, "vencimento": {"type": "STRING"}, "id": {"type": "INTEGER"},
            "dias": {"type": "INTEGER"},
        },
        "required": [],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "contas",
    "title": "Contas a vencer",
    "fields": [
        {"key": "dias_antes", "label": "Avisar quantos dias antes", "type": "text", "default": "3"},
        {"key": "pasta", "label": "Pasta dos boletos (vazio = Documentos\\JARVIS\\Contas)", "type": "text", "default": ""},
        {"key": "olhar_downloads", "label": "Procurar boletos novos na pasta Downloads", "type": "toggle", "default": True},
        {"key": "email", "label": "E-mail para ler as contas (vazio = não ler e-mail)", "type": "text", "default": ""},
        {"key": "senha_app", "label": "Senha de APP do e-mail (não é a sua senha normal)", "type": "password",
         "default": ""},
        {"key": "imap", "label": "Servidor IMAP", "type": "text", "default": "imap.gmail.com"},
    ],
}

ARQ = MEMORIA / "contas.json"
_lock = threading.Lock()
_iniciou = threading.Event()


def _c() -> dict:
    return cfg("contas", PLUGIN_SETTINGS)


def dados() -> dict:
    d = ler_json(ARQ, {}) or {}
    d.setdefault("contas", [])
    d.setdefault("vistos", [])           # PDFs/e-mails já lidos (hash), para não ler de novo
    return d


def _gravar(d: dict) -> None:
    d["vistos"] = d["vistos"][-500:]
    gravar_json(ARQ, d)


def pasta() -> Path:
    p = str(_c().get("pasta") or "").strip()
    return Path(p).expanduser() if p else pasta_usuario("Documents") / "JARVIS" / "Contas"


# ── regras (puras) ─────────────────────────────────────────────────────────────
def data_falada(texto: str, hoje: date | None = None) -> date | None:
    """'14/11', '14/11/2026', '2026-11-14' → date (o ano que vem se o dia já passou)."""
    import re
    hoje = hoje or date.today()
    t = str(texto or "").strip()
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?", t)
    if not m:
        return None
    d, mes = int(m.group(1)), int(m.group(2))
    a = int(m.group(3)) if m.group(3) else hoje.year
    a += 2000 if a < 100 else 0
    try:
        v = date(a, mes, d)
    except ValueError:
        return None
    if not m.group(3) and v < hoje - timedelta(days=15):
        v = date(a + 1, mes, d)
    return v


def avisos_devidos(contas: list[dict], hoje: date, dias_antes: int = 3) -> list[tuple[dict, str]]:
    """Quais avisos dar agora: (conta, 'antes' | 'hoje' | 'atrasada'), um de cada por conta (pura)."""
    saida = []
    for c in contas:
        if c.get("pago") or not c.get("vencimento"):
            continue
        n = (date.fromisoformat(c["vencimento"]) - hoje).days
        feitos = c.get("avisos", {})
        if n == 0 and "hoje" not in feitos:
            saida.append((c, "hoje"))
        elif 0 < n <= dias_antes and "antes" not in feitos:
            saida.append((c, "antes"))
        elif -3 <= n < 0 and "atrasada" not in feitos:
            saida.append((c, "atrasada"))
    return saida


def achar(contas: list[dict], termo: str) -> list[dict]:
    t = B._dobrar(termo)
    abertas = [c for c in contas if not c.get("pago")]
    return [c for c in abertas if t and (t in B._dobrar(c.get("descricao", "")) or t in B._dobrar(c.get("tipo", ""))
                                         or t in B._dobrar(c.get("beneficiario", "")))]


# ── guardar ────────────────────────────────────────────────────────────────────
def adicionar(info: dict, origem: str, descricao: str = "", arquivo: str = "") -> tuple[dict, bool]:
    """Guarda a conta. (conta, nova?) — a mesma linha digitável não entra duas vezes."""
    venc = info.get("vencimento")
    with _lock:
        d = dados()
        chave = info.get("barras") or info.get("linha") or ""
        igual = next((c for c in d["contas"] if chave and c.get("barras") == chave), None)
        if igual:
            return igual, False
        c = {"id": max([x["id"] for x in d["contas"]], default=0) + 1,
             "descricao": descricao or (f"conta de {info['tipo']}" if info.get("tipo") else
                                        (info.get("beneficiario") or "conta")),
             "tipo": info.get("tipo", ""), "beneficiario": info.get("beneficiario", ""), "valor": info.get("valor"),
             "vencimento": venc.isoformat() if isinstance(venc, date) else venc, "linha": info.get("linha") or "",
             "barras": info.get("barras") or "", "origem": origem, "arquivo": arquivo, "pago": False,
             "criada": time.time(), "avisos": {}}
        d["contas"].append(c)
        _gravar(d)
        return c, True


def _descrever(c: dict) -> str:
    venc = f"vence {date.fromisoformat(c['vencimento']).strftime('%d/%m')}" if c.get("vencimento") else "sem vencimento"
    return f"#{c['id']} {c['descricao']} — {B.reais(c.get('valor'))}, {venc}{' (paga)' if c.get('pago') else ''}"


def ler_arquivo(caminho: Path, descricao: str = "") -> str:
    if caminho.suffix.lower() == ".pdf":
        info = B.ler_texto(B.texto_do_pdf(caminho))
    else:
        info = _ler_foto(caminho.read_bytes())
    if not info:
        return f"Não achei um código de boleto válido em {caminho.name}."
    c, nova = adicionar(info, "arquivo", descricao, str(caminho))
    if not nova:
        return f"Essa conta eu já tinha: {_descrever(c)}."
    falta = "" if c.get("vencimento") else " Não achei o vencimento: me diga a data."
    return f"Anotei: {_descrever(c)}.{falta}"


def _ler_foto(imagem: bytes) -> dict | None:
    from plugins import _ia
    j = _ia.ver_imagem_json(
        "Isto é a foto de um boleto/conta brasileiro. Devolva {\"linha\": \"os números da linha digitável ou do "
        "código de barras, só dígitos\", \"vencimento\": \"dd/mm/aaaa\", \"valor\": número, \"empresa\": \"quem "
        "cobra\"}. Use null no que não der para ler.", imagem, inteligente=True)
    if not isinstance(j, dict):
        return None
    info = B.ler_codigo(str(j.get("linha") or "")) or {}
    if not info:
        return None
    if not info.get("vencimento") and j.get("vencimento"):
        info["vencimento"] = data_falada(str(j["vencimento"]))
    if not info.get("valor") and isinstance(j.get("valor"), (int, float)):
        info["valor"] = float(j["valor"])
    info["beneficiario"] = str(j.get("empresa") or "")
    info["tipo"] = B.tipo_da_conta(info["beneficiario"], info.get("segmento", ""))
    return info


def procurar_pdfs(pastas: list[Path], dias: int = 5) -> list[str]:
    """Lê os PDFs novos (dos últimos dias) que ainda não vi. Devolve as frases do que anotou."""
    novos = []
    limite = time.time() - dias * 86400
    for p in pastas:
        if not p.is_dir():
            continue
        for arq in sorted(p.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True)[:40]:
            try:
                if arq.stat().st_mtime < limite:
                    continue
                marca = hashlib.sha1(f"{arq.name}|{arq.stat().st_size}".encode()).hexdigest()
                with _lock:
                    d = dados()
                    if marca in d["vistos"]:
                        continue
                    d["vistos"].append(marca)
                    _gravar(d)
                info = B.ler_texto(B.texto_do_pdf(arq))
                if info:
                    c, nova = adicionar(info, "pdf", "", str(arq))
                    if nova:
                        novos.append(_descrever(c))
            except Exception as e:
                print(f"[Contas] {arq.name}: {e}")
    return novos


def ler_email(dias: int = 15) -> list[str]:
    """IMAP com senha de app: lê os PDFs anexados dos últimos dias."""
    import email
    import imaplib
    c = _c()
    conta, senha = str(c.get("email") or "").strip(), str(c.get("senha_app") or "").strip()
    if not (conta and senha):
        raise RuntimeError("configure o e-mail e a senha de app em ⚙ → Contas a vencer")
    novos = []
    desde = (date.today() - timedelta(days=dias)).strftime("%d-%b-%Y")
    with imaplib.IMAP4_SSL(str(c.get("imap") or "imap.gmail.com")) as m:
        m.login(conta, senha)
        m.select("INBOX", readonly=True)
        _ok, ids = m.search(None, f'(SINCE "{desde}")')
        for num in (ids[0].split() if ids and ids[0] else [])[-80:]:
            _ok, partes = m.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(partes[0][1])
            marca = hashlib.sha1((msg.get("Message-ID") or num.decode()).encode()).hexdigest()
            with _lock:
                d = dados()
                if marca in d["vistos"]:
                    continue
                d["vistos"].append(marca)
                _gravar(d)
            assunto = str(email.header.make_header(email.header.decode_header(msg.get("Subject") or "")))
            for parte in msg.walk():
                nome = parte.get_filename() or ""
                if parte.get_content_type() == "application/pdf" or nome.lower().endswith(".pdf"):
                    destino = pasta() / (nome or f"email_{num.decode()}.pdf")
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_bytes(parte.get_payload(decode=True) or b"")
                    info = B.ler_texto(B.texto_do_pdf(destino))
                    if info:
                        if not info.get("tipo"):
                            info["tipo"] = B.tipo_da_conta(assunto)
                        cc, nova = adicionar(info, "email", "", str(destino))
                        if nova:
                            novos.append(_descrever(cc))
    return novos


# ── avisos sozinho ─────────────────────────────────────────────────────────────
def _avisar(texto: str, urgente: bool = False) -> None:
    try:
        from plugins._notificar import notificar
        notificar(None, texto, titulo="Contas", etiqueta="CONTAS", prioridade="high" if urgente else "default")
    except Exception as e:
        print(f"[Contas] {e}")


def verificar(hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    try:
        dias_antes = max(1, int(str(_c().get("dias_antes") or 3)))
    except ValueError:
        dias_antes = 3
    falas = []
    with _lock:
        d = dados()
        for conta, tipo in avisos_devidos(d["contas"], hoje, dias_antes):
            frase = B.frase_aviso(conta, hoje)
            if tipo == "atrasada":
                frase += " Se já pagou, diga 'paguei'."
            conta.setdefault("avisos", {})[tipo] = time.time()
            falas.append((frase, tipo != "antes"))
        if falas:
            _gravar(d)
    for frase, urgente in falas:
        _avisar(frase, urgente)
    return [f for f, _u in falas]


def _laco() -> None:
    time.sleep(60)
    ultimo_email = 0.0
    while True:
        try:
            c = _c()
            pastas = [pasta()] + ([pasta_usuario("Downloads")] if c.get("olhar_downloads", True) else [])
            for frase in procurar_pdfs(pastas):
                registrar(None, f"Contas: anotei {frase}")
            if c.get("email") and c.get("senha_app") and time.time() - ultimo_email > 6 * 3600:
                ultimo_email = time.time()
                for frase in ler_email():
                    registrar(None, f"Contas (e-mail): anotei {frase}")
            if 8 <= datetime.now().hour < 22:
                verificar()
        except Exception as e:
            print(f"[Contas] {e}")
        time.sleep(1800)


def on_session_start(player) -> None:
    if _iniciou.is_set():
        return
    _iniciou.set()
    threading.Thread(target=_laco, daemon=True, name="contas").start()


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    acao = str(p.get("action") or "listar").lower()
    try:
        if acao == "ler":
            if p.get("linha"):
                info = B.ler_codigo(str(p["linha"]))
                if not info:
                    return "Esse código não confere (algum número trocado?). Pode repetir ou mandar o PDF?"
                if p.get("vencimento") and not info.get("vencimento"):
                    info["vencimento"] = data_falada(str(p["vencimento"]))
                c, nova = adicionar(info, "ditado", str(p.get("descricao") or ""))
                return ("Anotei: " if nova else "Essa eu já tinha: ") + _descrever(c) + "." + \
                    ("" if c.get("vencimento") else " Qual é o vencimento?")
            arq = str(p.get("arquivo") or "").strip()
            if arq:
                caminho = Path(arq).expanduser()
                if not caminho.exists():
                    return f"Não achei o arquivo {arq}."
                return ler_arquivo(caminho, str(p.get("descricao") or ""))
            novos = procurar_pdfs([pasta(), pasta_usuario("Downloads")], dias=30)
            return ("Anotei: " + "; ".join(novos) + ".") if novos else \
                f"Não achei boleto novo em {pasta()} nem em Downloads. Pode me passar o arquivo ou ditar o código."
        if acao == "adicionar":
            venc = data_falada(str(p.get("vencimento") or ""))
            if not venc:
                return "Qual é o vencimento? (dia/mês)"
            info = {"vencimento": venc, "valor": float(p["valor"]) if p.get("valor") else None,
                    "tipo": B.tipo_da_conta(str(p.get("descricao") or ""))}
            c, _n = adicionar(info, "manual", str(p.get("descricao") or "conta"))
            return f"Anotei: {_descrever(c)}."
        if acao in ("pagar", "copiar", "apagar"):
            with _lock:
                d = dados()
                if p.get("id"):
                    alvo = [c for c in d["contas"] if c["id"] == int(p["id"])]
                else:
                    alvo = achar(d["contas"], str(p.get("descricao") or ""))
                if not alvo:
                    return "Não achei essa conta entre as que estão em aberto."
                if len(alvo) > 1:
                    return "Achei mais de uma: " + "; ".join(_descrever(c) for c in alvo[:4]) + ". Qual delas (o número)?"
                c = alvo[0]
                if acao == "pagar":
                    c["pago"], c["pago_em"] = True, time.time()
                    _gravar(d)
                    return f"Marquei como paga: {c['descricao']}."
                if acao == "apagar":
                    d["contas"] = [x for x in d["contas"] if x["id"] != c["id"]]
                    _gravar(d)
                    return f"Tirei {c['descricao']} da lista."
            if not c.get("linha"):
                return "Essa conta não tem código (foi anotada à mão)."
            try:
                import pyperclip
                pyperclip.copy(c["linha"])
                return f"Copiei o código de {c['descricao']}. É só colar no app do banco."
            except Exception:
                mostrar(player, "CÓDIGO DO BOLETO", c["linha"])
                return "Coloquei o código na tela."
        if acao == "email":
            novos = ler_email(30)
            return ("Anotei do e-mail: " + "; ".join(novos) + ".") if novos else "Nenhuma conta nova no e-mail."
        dias = int(p.get("dias") or 31)
        hoje = date.today()
        abertas = sorted((c for c in dados()["contas"] if not c.get("pago") and
                          (not c.get("vencimento") or (date.fromisoformat(c["vencimento"]) - hoje).days <= dias)),
                         key=lambda c: c.get("vencimento") or "9999")
        if not abertas:
            return "Nenhuma conta em aberto."
        texto = "\n".join(_descrever(c) for c in abertas)
        mostrar(player, "CONTAS A VENCER", texto)
        total = sum(c.get("valor") or 0 for c in abertas)
        return f"{len(abertas)} conta(s) em aberto, {B.reais(total)} no total:\n{texto}"
    except Exception as e:
        return f"As contas falharam: {e}"
