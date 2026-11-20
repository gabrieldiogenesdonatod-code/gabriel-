"""
Controle do PC — plugin do J.A.R.V.I.S BR.

APPS      abrir (com apelidos e busca aproximada), abrir como administrador
          (com confirmação), fechar, reiniciar, focar, procurar, listar os que
          estão abertos, atualizar a lista de apps, criar apelido.
JANELAS   listar, focar, minimizar, maximizar, restaurar, fechar, mover para
          outro monitor, lado a lado, sempre no topo, minimizar tudo.
ENERGIA   desligar, reiniciar, suspender, hibernar, sair, agendar
          ("desliga em 30 minutos") e cancelar — tudo com confirmação.
          Bloquear a tela é imediato (é seguro e às vezes urgente).
ENTRADA   digitar texto (com acentos), atalhos, cliques, rolagem, mover mouse.

Fechar apps usa o caminho educado do core/appidentity.py (pede para a janela
fechar, como o X faria), respeitando a lista de proteção.
"""

from __future__ import annotations

import threading
import time

from plugins import _indice_apps as apps
from plugins import _janelas as jan
from plugins._comum import (LINUX, MAC, NAO_DISPONIVEL, WIN, confirmar, desfazer,
                            mostrar, num, powershell, registrar, rodar, sim)
from plugins._protecao import motivo_protecao

PLUGIN = {
    "name": "controle_pc",
    "brief": "Open/close/focus apps (nicknames ok), windows, power (with confirmation), typing, hotkeys, mouse.",
    "description": (
        "Control the computer. APPS: action='abrir' (alvo=app name or nickname, "
        "admin=sim to run as administrator), 'fechar', 'reiniciar_app', 'focar', "
        "'procurar_app', 'apps_abertos', 'atualizar_apps', 'apelido' (alvo=nickname, "
        "nome=real app). WINDOWS: 'janelas' (list), 'minimizar', 'maximizar', "
        "'restaurar', 'fechar_janela', 'mover_monitor' (monitor=number or 'proximo'), "
        "'lado_a_lado' (alvo and alvo2), 'sempre_no_topo' (ligar=sim/nao), "
        "'minimizar_tudo', 'mostrar_tudo' — alvo is a window title word or app; "
        "empty means the active window. POWER: 'desligar', 'reiniciar', 'suspender', "
        "'hibernar', 'bloquear', 'sair', 'agendar' (operacao=desligar|reiniciar, "
        "minutos), 'cancelar_agendamento'. INPUT: 'digitar' (texto), 'atalho' "
        "(teclas like 'ctrl+shift+esc'), 'clicar' (x, y, botao), 'rolar' "
        "(direcao=cima|baixo, quantidade), 'mover_mouse' (x, y). "
        "Prefer this tool for opening apps when the user uses a nickname or a "
        "game name; open_app also works for plain names."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "See description for the list"},
            "alvo": {"type": "STRING", "description": "App, window or nickname"},
            "alvo2": {"type": "STRING", "description": "Second window for lado_a_lado"},
            "nome": {"type": "STRING", "description": "apelido: the real app name"},
            "admin": {"type": "STRING", "description": "abrir: 'sim' to run as administrator"},
            "monitor": {"type": "STRING", "description": "mover_monitor: number or 'proximo'"},
            "ligar": {"type": "STRING", "description": "sempre_no_topo: sim | nao"},
            "operacao": {"type": "STRING", "description": "agendar: desligar | reiniciar"},
            "minutos": {"type": "NUMBER", "description": "agendar: minutes from now"},
            "texto": {"type": "STRING", "description": "digitar: text to type"},
            "teclas": {"type": "STRING", "description": "atalho: e.g. 'ctrl+c', 'win+d'"},
            "x": {"type": "NUMBER"}, "y": {"type": "NUMBER"},
            "botao": {"type": "STRING", "description": "clicar: esquerdo | direito | duplo"},
            "direcao": {"type": "STRING", "description": "rolar: cima | baixo"},
            "quantidade": {"type": "NUMBER", "description": "rolar: how many steps"},
        },
        "required": ["action"],
    },
}

_agendamento: dict = {}          # {"operacao", "quando", "timer"} fora do Windows


# ── apps ───────────────────────────────────────────────────────────────────────
def _abrir(p: dict, player) -> str:
    alvo = str(p.get("alvo") or "").strip()
    if not alvo:
        return "Qual aplicativo?"
    if sim(p.get("admin")):
        achados = apps.procurar(alvo, 1)
        if not achados:
            return f"Não encontrei {alvo} na lista de apps."
        e = achados[0]
        if not WIN:
            return "Abrir como administrador só existe no Windows."
        return confirmar(f"admin-{e['nome']}", f"Abrir {e['nome']} como administrador",
                         "O Windows vai mostrar o aviso de controle de conta (UAC).",
                         lambda: "Pedido enviado." if apps.lancar(e, admin=True) else "O UAC foi recusado.")
    try:
        # O open_app já usa os apelidos e o índice de apps, abre sem console
        # e confere em segundo plano se o app apareceu mesmo.
        from actions.open_app import open_app
        return open_app({"app_name": alvo}, player=player) or f"Abrindo {alvo}."
    except Exception:
        ok, e = apps.abrir(alvo)
        if ok:
            return f"Abrindo {e['nome']}."
        return f"Não encontrei {alvo}."


def _matches(alvo: str):
    from core import appidentity
    return appidentity.running(apps.resolver_apelido(alvo))


def _fechar_app(alvo: str) -> str:
    if not alvo:
        return "Qual aplicativo devo fechar?"
    from core import appidentity
    achados = _matches(alvo)
    if not achados:
        return f"{alvo} não está aberto."
    fechados, recusados = [], []
    for m in achados[:6]:
        motivo = motivo_protecao(m.name, m.pid)
        if motivo:
            recusados.append(motivo)
            continue
        ok, _info = appidentity.request_close(m)
        if ok:
            fechados.append(m.label)
            break                       # um app é várias instâncias: fechar a principal basta
    if fechados:
        return f"Fechei {fechados[0]}."
    if recusados:
        return f"Não posso fechar {alvo}: {recusados[0]}."
    return (f"Pedi para {alvo} fechar, mas ele não fechou (talvez esteja perguntando "
            "se quer salvar).")


def _reiniciar_app(alvo: str, player) -> str:
    msg = _fechar_app(alvo)
    if not msg.startswith("Fechei"):
        return msg
    time.sleep(1.5)
    return msg + " " + _abrir({"alvo": alvo}, player)


def _focar(alvo: str) -> str:
    j = jan.achar(alvo)
    if j:
        return f"{j['titulo'][:60]} na frente." if jan.focar(j) else \
            f"Achei {j['titulo'][:60]}, mas o Windows não deixou trazer para a frente."
    from core import appidentity
    for m in _matches(alvo)[:6]:
        if appidentity.focus(m):
            return f"{m.label} na frente."
    return f"Não achei nenhuma janela de {alvo}."


def _procurar_app(alvo: str, player) -> str:
    achados = apps.procurar(alvo, 8)
    if not achados:
        return f"Nada parecido com {alvo} na lista de apps."
    mostrar(player, f"APPS PARECIDOS COM '{alvo}'",
            "\n".join(f"{e['pontos']:>3}  {e['nome']}   ({e['tipo']}, {e['fonte']})" for e in achados))
    return "Encontrei: " + ", ".join(e["nome"] for e in achados[:5]) + "."


def _apps_abertos(player) -> str:
    js = jan.listar()
    if not js:
        return "Não consegui listar as janelas abertas neste sistema."
    nomes = sorted({j["processo"].rsplit(".", 1)[0] for j in js})
    mostrar(player, "JANELAS ABERTAS", "\n".join(
        f"{j['processo'][:22]:<22} {j['titulo'][:70]}"
        f"{'  [min]' if j['minimizada'] else ''}{'  [topo]' if j['no_topo'] else ''}" for j in js))
    return f"{len(js)} janelas abertas: " + ", ".join(nomes[:12]) + "."


def _atualizar_apps(player) -> str:
    registrar(player, "Atualizando a lista de apps (Menu Iniciar, Store, Steam, Epic)…")
    entradas = apps.indice(forcar=True)
    return f"Lista de apps atualizada: {len(entradas)} itens encontrados."


# ── janelas ────────────────────────────────────────────────────────────────────
def _janela_ou_erro(alvo: str):
    j = jan.achar(alvo)
    return j, (None if j else (f"Não achei nenhuma janela de {alvo}." if alvo else
                                "Não identifiquei a janela ativa."))


def _estado_janela(alvo: str, acao: str) -> str:
    j, erro = _janela_ou_erro(alvo)
    if erro:
        return erro
    if acao == "fechar":
        motivo = motivo_protecao(j["processo"], j["pid"])
        if motivo:
            return f"Não vou fechar essa janela: {motivo}."
    falha = jan.estado(j, acao)
    if falha:
        return falha
    if acao in ("minimizar", "maximizar") and WIN:
        desfazer(f"{acao} {j['titulo'][:40]}", lambda jj=j: (jan.estado(jj, "restaurar"), "Janela restaurada.")[1])
    verbo = {"minimizar": "minimizada", "maximizar": "maximizada", "restaurar": "restaurada",
             "fechar": "fechada"}[acao]
    return f"Janela {j['titulo'][:50]} {verbo}."


def _mover_monitor(alvo: str, monitor) -> str:
    j, erro = _janela_ou_erro(alvo)
    if erro:
        return erro
    falha = jan.mover_para_monitor(j, monitor or "proximo")
    return falha or f"{j['titulo'][:50]} foi para o outro monitor."


def _lado_a_lado(alvo: str, alvo2: str) -> str:
    a = jan.achar(alvo)
    if not a:
        return f"Não achei a janela {alvo}."
    b = jan.achar(alvo2) if alvo2 else None
    if alvo2 and not b:
        return f"Não achei a janela {alvo2}."
    falha = jan.lado_a_lado(a, b)
    return falha or ("Lado a lado: " + a["titulo"][:30] + (f" e {b['titulo'][:30]}" if b else "") + ".")


def _topo(alvo: str, ligar) -> str:
    j, erro = _janela_ou_erro(alvo)
    if erro:
        return erro
    ligado = True if ligar in (None, "") else sim(ligar)
    falha = jan.sempre_no_topo(j, ligado)
    if falha:
        return falha
    desfazer(f"sempre no topo {j['titulo'][:30]}",
             lambda jj=j, l=ligado: (jan.sempre_no_topo(jj, not l), "Desfeito.")[1])
    return f"{j['titulo'][:50]} {'sempre no topo' if ligado else 'voltou ao normal'}."


# ── energia ────────────────────────────────────────────────────────────────────
def _cmd_energia(op: str):
    """Função que executa a operação de energia agora. None se não existir."""
    if WIN:
        tabela = {
            "desligar": lambda: rodar(["shutdown", "/s", "/t", "15"]),
            "reiniciar": lambda: rodar(["shutdown", "/r", "/t", "15"]),
            "hibernar": lambda: rodar(["shutdown", "/h"]),
            "sair": lambda: rodar(["shutdown", "/l"]),
            # SetSuspendState pelo Forms respeita "suspender" mesmo com a
            # hibernação ligada (o rundll32 hibernaria nesse caso).
            "suspender": lambda: powershell("Add-Type -AssemblyName System.Windows.Forms;"
                                            "[System.Windows.Forms.Application]::SetSuspendState("
                                            "'Suspend', $false, $false)"),
        }
    elif MAC:
        tabela = {
            "desligar": lambda: rodar(["osascript", "-e", 'tell app "System Events" to shut down']),
            "reiniciar": lambda: rodar(["osascript", "-e", 'tell app "System Events" to restart']),
            "suspender": lambda: rodar(["pmset", "sleepnow"]),
            "sair": lambda: rodar(["osascript", "-e", 'tell app "System Events" to log out']),
        }
    else:
        tabela = {
            "desligar": lambda: rodar(["systemctl", "poweroff"]),
            "reiniciar": lambda: rodar(["systemctl", "reboot"]),
            "suspender": lambda: rodar(["systemctl", "suspend"]),
            "hibernar": lambda: rodar(["systemctl", "hibernate"]),
            "sair": lambda: rodar(["loginctl", "terminate-user", __import__("getpass").getuser()]),
        }
    return tabela.get(op)


def bloquear_tela() -> str:
    if WIN:
        import ctypes
        return "Tela bloqueada." if ctypes.windll.user32.LockWorkStation() else "Não consegui bloquear."
    if MAC:
        rodar(["osascript", "-e", 'tell application "System Events" to keystroke "q" using '
                                  '{control down, command down}'])
        return "Tela bloqueada."
    for args in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"],
                 ["gnome-screensaver-command", "-l"]):
        if rodar(args, timeout=5)[0] == 0:
            return "Tela bloqueada."
    return "Não consegui bloquear a tela neste sistema."


_NOMES_ENERGIA = {"desligar": "Desligar o computador", "reiniciar": "Reiniciar o computador",
                  "suspender": "Suspender o computador", "hibernar": "Hibernar o computador",
                  "sair": "Sair da conta (logoff)"}


def _energia(op: str) -> str:
    if op == "bloquear":
        return bloquear_tela()
    fn = _cmd_energia(op)
    if fn is None:
        return NAO_DISPONIVEL
    detalhe = ("Programas abertos serão fechados; salve o que estiver fazendo."
               if op in ("desligar", "reiniciar", "sair") else "Você volta de onde parou.")
    if WIN and op in ("desligar", "reiniciar"):
        detalhe += " Ainda dá para cancelar dizendo 'cancela o desligamento' nos 15 s seguintes."
    return confirmar(f"energia-{op}", _NOMES_ENERGIA[op], detalhe,
                     lambda: (fn(), f"{_NOMES_ENERGIA[op]}: comando enviado.")[1])


def _agendar(op: str, minutos) -> str:
    op = (op or "desligar").lower()
    if op not in ("desligar", "reiniciar"):
        return "Só agendo desligar ou reiniciar."
    m = num(minutos, 0)
    if m <= 0 or m > 24 * 60:
        return "Diga em quantos minutos (até 24 horas)."
    quando = time.strftime("%H:%M", time.localtime(time.time() + m * 60))

    def agendar_agora():
        if WIN:
            rodar(["shutdown", "/a"])          # um agendamento por vez
            c, out = rodar(["shutdown", "/s" if op == "desligar" else "/r", "/t", str(int(m * 60))])
            return f"Agendado para {quando}." if c == 0 else f"O Windows recusou: {out[:100]}"
        fn = _cmd_energia(op)
        t = threading.Timer(m * 60, fn)
        t.daemon = True
        if _agendamento.get("timer"):
            _agendamento["timer"].cancel()
        _agendamento.update({"operacao": op, "quando": quando, "timer": t})
        t.start()
        return f"Agendado para {quando} (enquanto o JARVIS estiver aberto)."

    return confirmar(f"agendar-{op}", f"{op.capitalize()} às {quando}",
                     f"Daqui a {int(m)} minutos. Diga 'cancela o desligamento' para desistir.",
                     agendar_agora)


def _cancelar_agendamento() -> str:
    if WIN:
        c, _out = rodar(["shutdown", "/a"])
        return "Desligamento cancelado." if c == 0 else "Não havia desligamento agendado."
    t = _agendamento.pop("timer", None)
    if t:
        t.cancel()
        return "Agendamento cancelado."
    if LINUX:
        rodar(["shutdown", "-c"])
    return "Não havia nada agendado."


# ── teclado e mouse ────────────────────────────────────────────────────────────
def _pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        return pyautogui
    except Exception:
        return None


def digitar(texto: str) -> str:
    pg = _pyautogui()
    if pg is None:
        return "Preciso do pyautogui para digitar: pip install pyautogui"
    if not texto:
        return "O que devo digitar?"
    if texto.isascii():
        pg.write(texto, interval=0.02)
    else:
        # pyautogui não digita acentos: cola pela área de transferência e
        # devolve o que estava lá antes.
        try:
            import pyperclip
            antes = pyperclip.paste()
            pyperclip.copy(texto)
            pg.hotkey("command" if MAC else "ctrl", "v")
            time.sleep(0.3)
            pyperclip.copy(antes)
        except Exception as e:
            return f"Não consegui digitar com acentos: {e}"
    return f"Digitei {len(texto)} caracteres."


_TECLAS = {"ctrl": "ctrl", "control": "ctrl", "controle": "ctrl", "shift": "shift",
           "alt": "alt", "win": "win", "windows": "win", "super": "win", "cmd": "command",
           "command": "command", "enter": "enter", "esc": "esc", "escape": "esc",
           "tab": "tab", "espaco": "space", "espaço": "space", "space": "space",
           "apagar": "backspace", "backspace": "backspace", "delete": "delete", "del": "delete",
           "cima": "up", "baixo": "down", "esquerda": "left", "direita": "right",
           "home": "home", "end": "end", "pgup": "pageup", "pgdn": "pagedown",
           "printscreen": "printscreen", "print": "printscreen"}


def teclas_de(texto: str) -> list[str]:
    """'Ctrl + Shift + Esc' → ['ctrl', 'shift', 'esc']."""
    partes = [p.strip().lower() for p in str(texto or "").replace("-", "+").split("+") if p.strip()]
    return [_TECLAS.get(p, p) for p in partes]


def atalho(texto: str) -> str:
    pg = _pyautogui()
    if pg is None:
        return "Preciso do pyautogui: pip install pyautogui"
    teclas = teclas_de(texto)
    if not teclas:
        return "Qual atalho?"
    invalidas = [t for t in teclas if t not in pg.KEYBOARD_KEYS]
    if invalidas:
        return f"Não conheço a tecla {invalidas[0]}."
    pg.hotkey(*teclas)
    return "Atalho " + "+".join(teclas) + " enviado."


def clicar(x, y, botao: str) -> str:
    pg = _pyautogui()
    if pg is None:
        return "Preciso do pyautogui: pip install pyautogui"
    b = str(botao or "esquerdo").lower()
    kw = {}
    if x not in (None, "") and y not in (None, ""):
        kw = {"x": int(num(x)), "y": int(num(y))}
    if b.startswith("dup"):
        pg.doubleClick(**kw)
    else:
        pg.click(button="right" if b.startswith("dir") else "left", **kw)
    return "Clique feito."


def rolar(direcao: str, quantidade) -> str:
    pg = _pyautogui()
    if pg is None:
        return "Preciso do pyautogui: pip install pyautogui"
    n = int(num(quantidade, 5)) or 5
    pg.scroll(n * 100 if str(direcao or "").lower().startswith(("c", "u")) else -n * 100)
    return "Rolei."


def mover_mouse(x, y) -> str:
    pg = _pyautogui()
    if pg is None:
        return "Preciso do pyautogui: pip install pyautogui"
    pg.moveTo(int(num(x)), int(num(y)), duration=0.2)
    return "Mouse movido."


# ── entrada do plugin ──────────────────────────────────────────────────────────
def on_session_start(player) -> None:
    apps.aquecer()            # índice de apps pronto antes do primeiro "abre…"


def run(parameters: dict, player=None, session_memory=None) -> str:
    p = parameters or {}
    a = str(p.get("action") or "").strip().lower()
    alvo = str(p.get("alvo") or "").strip()
    try:
        if a == "abrir":
            return _abrir(p, player)
        if a == "fechar":
            return _fechar_app(alvo)
        if a == "reiniciar_app":
            return _reiniciar_app(alvo, player)
        if a == "focar":
            return _focar(alvo)
        if a == "procurar_app":
            return _procurar_app(alvo, player)
        if a == "apps_abertos" or a == "janelas":
            return _apps_abertos(player)
        if a == "atualizar_apps":
            return _atualizar_apps(player)
        if a == "apelido":
            nome = str(p.get("nome") or "").strip()
            return apps.definir_apelido(alvo, nome) if alvo and nome else "Diga o apelido e o app."
        if a in ("minimizar", "maximizar", "restaurar"):
            return _estado_janela(alvo, a)
        if a == "fechar_janela":
            return _estado_janela(alvo, "fechar")
        if a == "mover_monitor":
            return _mover_monitor(alvo, p.get("monitor"))
        if a == "lado_a_lado":
            return _lado_a_lado(alvo, str(p.get("alvo2") or ""))
        if a == "sempre_no_topo":
            return _topo(alvo, p.get("ligar"))
        if a == "minimizar_tudo":
            falha = jan.minimizar_tudo()
            if not falha:
                desfazer("minimizar tudo", lambda: (jan.minimizar_tudo(True), "Janelas de volta.")[1])
            return falha or "Tudo minimizado."
        if a == "mostrar_tudo":
            return jan.minimizar_tudo(True) or "Janelas de volta."
        if a in ("desligar", "reiniciar", "suspender", "hibernar", "bloquear", "sair"):
            return _energia(a)
        if a == "agendar":
            return _agendar(str(p.get("operacao") or "desligar"), p.get("minutos"))
        if a == "cancelar_agendamento":
            return _cancelar_agendamento()
        if a == "digitar":
            return digitar(str(p.get("texto") or ""))
        if a == "atalho":
            return atalho(str(p.get("teclas") or alvo))
        if a == "clicar":
            return clicar(p.get("x"), p.get("y"), str(p.get("botao") or ""))
        if a == "rolar":
            return rolar(str(p.get("direcao") or "baixo"), p.get("quantidade"))
        if a == "mover_mouse":
            return mover_mouse(p.get("x"), p.get("y"))
        return "Ação desconhecida para o controle do PC."
    except Exception as e:
        return f"O controle do PC falhou: {e}"

