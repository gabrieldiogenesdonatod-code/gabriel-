"""Eletrônica avançada (2.19): autonomia da bateria, código de capacitor, filtro RC, 555, fonte para fita de LED, leitura do ADC e PWM do ESP32."""
from __future__ import annotations

import math

from plugins._lote2 import P, numeros, rodar

PLUGIN = P("eletronica_pro", "Maker electronics math: battery life, capacitor code (104 = 100 nF), RC filter, 555 astable, LED strip power supply, ADC raw to volts, ESP32 PWM limits.",
           "bateria | capacitor | rc | ne555 | fita_led | adc | pwm",
           "valor = numbers in order. bateria: 'mAh mA'. capacitor: code '104'. rc: 'ohms uF'. ne555: 'R1 R2 uF'. "
           "fita_led: 'leds brilho%' (WS2812, 5 V). adc: 'raw bits vref'. pwm: 'bits'.",
           "valor")


def capacitor(codigo: str) -> float:
    """'104' → 100000 pF. Pura."""
    c = str(codigo).strip()
    return float(c) if len(c) < 3 else int(c[:2]) * 10 ** int(c[2])


def farad(pf: float) -> str:
    return f"{pf / 1e6:g} µF" if pf >= 1e6 else f"{pf / 1e3:g} nF" if pf >= 1e3 else f"{pf:g} pF"


def ne555(r1, r2, uf) -> tuple[float, float]:
    f = 1.44 / ((r1 + 2 * r2) * uf * 1e-6)
    return f, (r1 + r2) / (r1 + 2 * r2) * 100


def fita_led(leds, brilho=100, ma_por_led=60) -> float:
    return leds * ma_por_led * brilho / 100 / 1000


def _go(p, pl):
    a, n = p["action"], numeros(p.get("valor"))
    if not n:
        return "Me diga os valores."
    if a == "bateria":
        h = n[0] / n[1] * 0.8
        return f"{n[0]:g} mAh a {n[1]:g} mA duram cerca de {h:.1f} horas ({h / 24:.1f} dias), já descontando 20% de perdas."
    if a == "capacitor":
        return f"Capacitor {p.get('valor')}: {farad(capacitor(str(int(n[0]))))}."
    if a == "rc":
        tau = n[0] * n[1] * 1e-6
        return f"Constante de tempo {tau * 1000:.3g} ms; carrega 99% em {tau * 5000:.3g} ms; frequência de corte {1 / (2 * math.pi * tau):.4g} Hz."
    if a == "ne555":
        f, duty = ne555(*n[:3])
        return f"555 astável: {f:.4g} Hz, ciclo de trabalho {duty:.1f}%."
    if a == "fita_led":
        amp = fita_led(n[0], n[1] if len(n) > 1 else 100)
        return (f"{n[0]:g} LEDs WS2812 em {n[1] if len(n) > 1 else 100:g}% de brilho: até {amp:.1f} A ({amp * 5:.0f} W em 5 V). "
                f"Use fonte de {math.ceil(amp * 1.2)} A ou mais e injete energia a cada ~100 LEDs.")
    if a == "adc":
        bits, vref = (int(n[1]) if len(n) > 1 else 12), (n[2] if len(n) > 2 else 3.3)
        return f"Leitura {n[0]:g} de {2 ** bits - 1} = {n[0] / (2 ** bits - 1) * vref:.3f} V (referência {vref:g} V)."
    bits = int(n[0])
    return f"PWM de {bits} bits no ESP32: {2 ** bits} níveis, frequência máxima perto de {80e6 / 2 ** bits:,.0f} Hz.".replace(",", ".")


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("bateria capacitor rc ne555 fita_led adc pwm".split(), _go), player)
