"""MINER AI pela linha de comando (funciona sem o JARVIS):

    python -m miner_ai calcular                          o cérebro: compensa? (simulação)
    python -m miner_ai configurar carteira_btc=bc1q... tarifa=0,98 economico=sim horarios=22:00-07:00
    python -m miner_ai minerar btc                       minera de verdade (pede para digitar SIM)
    python -m miner_ai painel                            só o dashboard
"""
from __future__ import annotations

import sys
import time
import webbrowser

from miner_ai import cerebro, config, painel
from miner_ai.controlador import controlador


def _calcular(ctl) -> None:
    print("Consultando preço e dificuldade…")
    ctl.atualizar_mercado()
    for k, s in ctl.simulacoes().items():
        print(f"\n[SIMULAÇÃO] {s['veredito']}")
        print(f"   hashrate {'medido' if s['medido'] else 'estimado'}: {s['hashrate']:,.0f} H/s · {s['watts']:.1f} W estimados")
    print("\nOutras moedas: " + " ".join(cerebro.SO_ASIC.values()))
    print("\nO cérebro recomenda:")
    for d in cerebro.recomendar(config.carregar(), config.ler_json("historico.json", []) or [], ctl.simulacoes()):
        print(" •", d)


def main(argv: list[str]) -> int:
    ctl = controlador(avisar=lambda t: print("[MINER AI]", t))
    cmd = argv[0] if argv else "calcular"
    if cmd == "calcular":
        _calcular(ctl)
    elif cmd == "configurar":
        mud = dict(a.split("=", 1) for a in argv[1:] if "=" in a)
        cfg, erros = config.alterar(mud)
        for e in erros:
            print("ERRO:", e)
        print({k: v for k, v in cfg.items() if k in mud})
    elif cmd in ("minerar", "painel"):
        url = painel.iniciar(ctl)
        print("Painel:", url)
        if cmd == "minerar":
            moeda = (argv[1] if len(argv) > 1 else "btc").lower()
            ctl.atualizar_mercado()
            sim = ctl.simulacoes().get(moeda)
            if sim:
                print("\n[SIMULAÇÃO]", sim["veredito"])
            if input("\nMinerar de verdade no SEU PC, com a sua luz? Digite SIM: ").strip().upper() != "SIM":
                print("Nada foi ligado.")
                return 0
            ok, msg = ctl.iniciar(moeda)
            print(msg)
            if not ok:
                return 1
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            while True:
                time.sleep(10)
                e = ctl.estado()
                if e["rodando"]:
                    d = e["desempenho"]
                    print(f"{d['hashrate']:,.0f} H/s · {d['watts']:.1f} W · shares {e['real']['shares_aceitos']} · "
                          f"luz {cerebro._r(e['custos']['reais'])}" + (f" · PAUSADO: {d['motivo_pausa']}" if d["pausado"] else ""))
        except KeyboardInterrupt:
            print("\n" + ctl.parar("Ctrl+C"))
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
