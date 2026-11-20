"""Celular Android (2.18): controla o próprio celular pelo Termux:API quando o JARVIS roda no Termux."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from plugins._lote2 import P, norm, numeros, rodar

PLUGIN = P("celular_android", "Phone control when JARVIS runs on Android (Termux:API): battery, flashlight, vibrate, notification, clipboard, open link/app, location, volume, photo, toast.",
           "bateria | lanterna | vibrar | notificar | copiar | colar | abrir | localizacao | volume | foto | aviso | wifi | brilho | falar | "
           "discar | compartilhar | contato",
           "Phone. lanterna: valor on|off. vibrar: valor ms. notificar/aviso: texto. copiar: texto. abrir: texto (URL, "
           "'whatsapp', 'maps', 'spotify'...). volume: valor 0-15 (music stream). foto: camera (0 back, 1 front). brilho: valor 0-100. "
           "falar: texto (phone speaker). discar: texto = number (opens the dialer, does not call). compartilhar: texto (text or file path). "
           "contato: texto = name to look up.",
           "texto valor camera")

APPS = {"whatsapp": "https://wa.me/", "maps": "https://maps.google.com", "spotify": "spotify:", "youtube": "https://youtube.com",
        "instagram": "https://instagram.com", "gmail": "https://mail.google.com", "agenda": "https://calendar.google.com"}


def termux(*args, timeout=20, entrada=None) -> str:
    if not shutil.which(args[0]):
        raise RuntimeError("isso só funciona no celular com Termux e o app Termux:API instalados "
                           "(pkg install termux-api)")
    r = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, input=entrada)
    return (r.stdout or r.stderr or "").strip()


def _go(p, pl):
    a, t = str(p.get("action")).lower(), str(p.get("texto") or "")
    v = numeros(p.get("valor"))
    if a == "bateria":
        b = json.loads(termux("termux-battery-status") or "{}")
        return f"Bateria em {b.get('percentage')}%, {'carregando' if b.get('status') == 'CHARGING' else 'na bateria'}, " \
               f"{b.get('temperature', 0):.0f} °C."
    if a == "lanterna":
        liga = str(p.get("valor") or "on").lower() in ("on", "liga", "ligar", "sim", "1")
        termux("termux-torch", "on" if liga else "off")
        return "Lanterna ligada." if liga else "Lanterna desligada."
    if a == "vibrar":
        termux("termux-vibrate", "-d", str(int(v[0]) if v else 500), "-f")
        return "Vibrei."
    if a == "notificar":
        termux("termux-notification", "--title", "J.A.R.V.I.S", "--content", t or "Aviso", "--priority", "high")
        return "Notificação enviada."
    if a == "aviso":
        termux("termux-toast", t or "J.A.R.V.I.S")
        return "Mostrei na tela."
    if a == "copiar":
        termux("termux-clipboard-set", entrada=t)
        return "Copiado."
    if a == "colar":
        return termux("termux-clipboard-get") or "A área de transferência está vazia."
    if a == "abrir":
        alvo = APPS.get(t.lower().strip(), t)
        if not alvo.startswith(("http", "spotify:", "tel:", "geo:", "mailto:")):
            alvo = "https://www.google.com/search?q=" + alvo.replace(" ", "+")
        termux("termux-open-url", alvo)
        return f"Abrindo {t}."
    if a == "localizacao":
        g = json.loads(termux("termux-location", "-p", "network", "-r", "once", timeout=40) or "{}")
        if "latitude" not in g:
            return "Não consegui a localização (dê a permissão de localização ao Termux:API)."
        return f"Você está em {g['latitude']:.5f}, {g['longitude']:.5f} (±{g.get('accuracy', 0):.0f} m)."
    if a == "volume":
        termux("termux-volume", "music", str(int(v[0]) if v else 8))
        return f"Volume da mídia em {int(v[0]) if v else 8} de 15."
    if a == "wifi":
        w = json.loads(termux("termux-wifi-connectioninfo") or "{}")
        return f"Wi-Fi: {w.get('ssid', '?')}, sinal {w.get('rssi', '?')} dBm, IP {w.get('ip', '?')}."
    if a == "brilho":
        termux("termux-brightness", str(round(max(0, min(100, v[0])) * 2.55)) if v else "auto")
        return f"Brilho em {v[0]:g}%." if v else "Brilho automático."
    if a == "falar":
        termux("termux-tts-speak", t or "Às suas ordens.", timeout=60)
        return "Falei pelo alto-falante do celular."
    if a == "discar":
        numero = re.sub(r"[^\d+*#]", "", t or str(p.get("valor") or ""))
        if not numero:
            return "Qual número?"
        termux("termux-open-url", "tel:" + numero)
        return f"Abri o discador com {numero}. É só tocar em ligar."
    if a == "compartilhar":
        termux("termux-share", "-a", "send", entrada=t) if not t.startswith("/") else termux("termux-share", "-a", "send", t)
        return "Abri o menu de compartilhar."
    if a == "contato":
        cs = json.loads(termux("termux-contact-list", timeout=30) or "[]")
        achou = [c for c in cs if norm(t) and norm(t) in norm(c.get("name"))][:5]
        return "; ".join(f"{c.get('name')}: {c.get('number')}" for c in achou) or "Não achei esse contato (o Termux:API precisa da permissão de contatos)."
    from plugins._comum import pasta_jarvis
    import time
    arq = pasta_jarvis("Fotos") / f"foto_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
    termux("termux-camera-photo", "-c", str(p.get("camera") or 0), str(arq), timeout=30)
    return f"Foto salva em {arq}."


def run(parameters, player=None, session_memory=None):
    a = "bateria lanterna vibrar notificar copiar colar abrir localizacao volume foto aviso wifi brilho falar discar compartilhar contato".split()
    return rodar(parameters, dict.fromkeys(a, _go), player)
