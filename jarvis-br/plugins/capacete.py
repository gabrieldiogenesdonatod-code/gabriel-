"""
Modo capacete (ESP32) — o comando de voz (fork PT-BR 1.4).

O capacete (ESP32 + microfone INMP441 + amplificador MAX98357A + botão) vira
mais um terminal do MESMO JARVIS: você aperta o botão, fala, e a resposta
sai no alto-falante do capacete — sem rodar um segundo assistente.

    "Jarvis, configura o capacete"      → chave, IP e porta para o sketch
    "Jarvis, o capacete está conectado?"
    "Jarvis, gera outra chave do capacete"

O código do ESP32 e o esquema de ligação estão em esp32/capacete/.
Precisa do painel remoto ligado (o mesmo do celular: ◉ CONTROLE REMOTO).
"""

from __future__ import annotations

from plugins._comum import BASE, mostrar

PLUGIN = {
    "name": "capacete",
    "brief": "ESP32 helmet terminal: key/IP for the sketch, connection status.",
    "description": (
        "Helmet mode: an ESP32 with microphone and speaker becomes another terminal of this same JARVIS "
        "(audio over WebSocket through the remote dashboard). action='configurar' shows the key, PC IP and "
        "port to paste in the ESP32 sketch; 'status' says whether a helmet is connected; 'nova_chave' "
        "generates a new key (the old one stops working)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {"action": {"type": "STRING", "description": "configurar | status | nova_chave"}},
        "required": [],
    },
}


def _servidor():
    try:
        from core import registro_ferramentas
        return getattr(registro_ferramentas.app(), "_dashboard", None)
    except Exception:
        return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    from plugins import _capacete
    acao = str((parameters or {}).get("action") or "configurar").lower()
    try:
        srv = _servidor()
        if acao == "status":
            if srv is None:
                return "O painel remoto não está rodando, então o capacete não tem onde se conectar."
            n = _capacete.conectados(srv)
            return f"{n} capacete(s) conectado(s)." if n else "Nenhum capacete conectado agora."
        chave = _capacete.obter_chave(nova=(acao == "nova_chave"))
        ip = getattr(srv, "_ip", "") or "IP-DO-PC"
        texto = (f"COLE NO SKETCH (esp32/capacete/capacete.ino):\n\n"
                 f'  const char* PC_IP   = "{ip}";\n  const uint16_t PC_PORTA = 8000;\n  const char* CHAVE   = "{chave}";\n\n'
                 f"Endereço: ws://{ip}:8000/ws/capacete?chave=…\n"
                 f"O ESP32 precisa estar na MESMA rede Wi-Fi do PC (2,4 GHz).\n"
                 f"Ligações e passo a passo: {BASE / 'esp32' / 'capacete' / 'LEIA-ME.md'}\n\n"
                 "Se o painel remoto não estiver ligado, abra ◉ CONTROLE REMOTO uma vez (ele sobe o servidor).")
        mostrar(player, "CAPACETE ESP32", texto)
        if acao == "nova_chave":
            return "Gerei uma chave nova para o capacete; ela está no painel. A antiga parou de funcionar."
        return (f"A configuração do capacete está no painel: IP {ip}, porta 8000 e a chave."
                + ("" if srv is not None else " Atenção: o painel remoto não está rodando agora."))
    except Exception as e:
        return f"O capacete falhou: {e}"
