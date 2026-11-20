"""Eletrônica (2.18): cores do resistor, lei de Ohm, resistor do LED, divisor de tensão e pinos seguros do ESP32."""
from __future__ import annotations

from plugins._lote2 import P, norm, numeros, rodar

PLUGIN = P("eletronica", "Electronics helper: resistor color code both ways, Ohm's law, LED resistor, voltage divider, ESP32 pin tips.",
           "cores_resistor | resistor_cores | ohm | led | divisor | esp32",
           "cores_resistor: texto ('marrom preto vermelho'). resistor_cores: valor (ohms). ohm: valor 'V=5 I=0.02' (any two). "
           "led: valor 'fonte led_v corrente_mA' (5 2 20). divisor: valor 'vin r1 r2'. esp32: texto (pin number or topic).",
           "texto valor")

CORES = "preto marrom vermelho laranja amarelo verde azul violeta cinza branco".split()


def cores_para_ohm(t: str) -> float:
    c = [CORES.index(x) for x in norm(t).split() if x in CORES]
    if len(c) < 3:
        raise ValueError("diga pelo menos 3 cores")
    *dig, mult = c[:4] if len(c) >= 4 else c[:3]
    return int("".join(map(str, dig))) * 10 ** mult


def ohm_para_cores(r: float) -> str:
    s = f"{r:.2e}"                      # 4.70e+03
    a, b, exp = int(s[0]), int(s[2]), int(s.split("e")[1]) - 1
    return f"{CORES[a]} {CORES[b]} {CORES[exp] if 0 <= exp < 10 else '?'} (+ dourado 5%)"


def legivel(r: float) -> str:
    return f"{r / 1e6:g} MΩ" if r >= 1e6 else f"{r / 1e3:g} kΩ" if r >= 1e3 else f"{r:g} Ω"


def led(fonte: float, vled: float, ma: float) -> float:
    return (fonte - vled) / (ma / 1000)


def ohm(t: str) -> str:
    import re
    d = {k.upper(): float(v.replace(",", ".")) for k, v in re.findall(r"([VIRvir])\s*=\s*([\d.,]+)", t)}
    if len(d) < 2:
        raise ValueError("diga dois valores, ex.: 'V=5 R=220'")
    if "V" not in d:
        return f"V = {d['I'] * d['R']:g} V"
    if "I" not in d:
        return f"I = {d['V'] / d['R'] * 1000:g} mA"
    return f"R = {legivel(d['V'] / d['I'])}"


ESP32 = {"seguros": "Use livres: 4, 13, 16-19, 21-23, 25-27, 32-33.",
         "boot": "Cuidado no boot: 0, 2, 5, 12, 15 (strapping). 12 em HIGH no boot quebra o flash.",
         "entrada": "34, 35, 36 (VP), 39 (VN) são só ENTRADA e sem pull-up interno.",
         "adc": "ADC2 (0, 2, 4, 12-15, 25-27) não funciona com Wi-Fi ligado; use ADC1 (32-39).",
         "flash": "6 a 11 são do flash: nunca use.", "i2c": "I2C padrão: SDA 21, SCL 22.", "dac": "DAC: 25 e 26.",
         "tensao": "Pinos são 3,3 V: não ligue 5 V direto (use divisor ou conversor de nível)."}


def esp32(t: str) -> str:
    n = numeros(t)
    if n:
        g, notas = int(n[0]), []
        if 6 <= g <= 11:
            return f"GPIO {g}: é do flash interno, nunca use."
        if g in (0, 2, 5, 12, 15):
            notas.append("pino de boot (strapping): cuidado com o nível no boot")
        if g in (34, 35, 36, 39):
            notas.append("só entrada, sem pull-up interno")
        if g in (0, 2, 4, 12, 13, 14, 15, 25, 26, 27):
            notas.append("ADC2: analógico não funciona com Wi-Fi ligado")
        if g in (25, 26):
            notas.append("tem DAC")
        if g in (21, 22):
            notas.append("I2C padrão (21 SDA, 22 SCL)")
        return f"GPIO {g}: " + ("; ".join(notas) if notas else "livre para uso geral") + "."
    k = next((k for k in ESP32 if k in norm(t)), None)
    return ESP32[k] if k else " ".join(ESP32.values())


def _go(p, pl):
    a, t, v = str(p.get("action")).lower(), str(p.get("texto") or ""), numeros(p.get("valor"))
    if a == "cores_resistor":
        return f"{legivel(cores_para_ohm(t))}."
    if a == "resistor_cores":
        return ohm_para_cores(v[0])
    if a == "ohm":
        return ohm(str(p.get("valor") or t))
    if a == "led":
        f, vl, ma = (v + [5, 2, 20][len(v):])[:3]
        r = led(f, vl, ma)
        return f"Resistor de {legivel(r)} (use o valor comercial acima, ex.: {legivel(r * 1.1):s}); potência {(f - vl) * ma / 1000:.3f} W."
    if a == "divisor":
        if len(v) < 3:
            return "Diga 'vin r1 r2', ex.: '5 10000 20000'."
        vin, r1, r2 = v[:3]
        return f"Vout = {vin * r2 / (r1 + r2):.2f} V."
    return esp32(t or str(p.get("valor") or ""))


def run(parameters, player=None, session_memory=None):
    return rodar(parameters, dict.fromkeys("cores_resistor resistor_cores ohm led divisor esp32".split(), _go), player)
