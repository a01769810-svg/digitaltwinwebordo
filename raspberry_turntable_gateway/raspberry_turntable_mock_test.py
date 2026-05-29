#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raspberry_turntable_mock_test.py

Corre un ciclo COMPLETO de la mesa en modo MOCK (sin hardware) e imprime el
contrato JSON en cada transición.  Sirve para validar la lógica y el contrato
en una laptop, y para verificar lo que la web recibirá por /ws/turntable.

Uso:
    TURNTABLE_MOCK=1 python raspberry_turntable_mock_test.py
    (en Windows PowerShell:  $env:TURNTABLE_MOCK=1; python raspberry_turntable_mock_test.py)
"""

import json
import os
import threading
import time

os.environ.setdefault("TURNTABLE_MOCK", "1")
# Remachado corto para que el test sea rápido.
os.environ.setdefault("RIVET_SECONDS", "2")

from raspberry_turntable_gpio_controller import TurntableController  # noqa: E402


def main():
    ctl = TurntableController()
    print(">> Modo:", "MOCK" if ctl.mock else "GPIO real")
    print(">> Estado inicial:")
    print(json.dumps(ctl.get_turntable_state(), indent=2, ensure_ascii=False))

    # Lanzar el ciclo en un hilo y muestrear el estado mientras corre.
    th = threading.Thread(target=ctl.run_riveting_cycle, daemon=True)
    th.start()

    last = None
    while th.is_alive():
        st = ctl.get_turntable_state()
        if st["position"] != last:
            last = st["position"]
            print(f"\n>> Transición -> {st['position']}  ({st['message']})")
            print(json.dumps(st, indent=2, ensure_ascii=False))
        time.sleep(0.1)

    print("\n>> Estado final:")
    print(json.dumps(ctl.get_turntable_state(), indent=2, ensure_ascii=False))
    ctl.cleanup()
    print("\n>> OK — ciclo mock completado.")


if __name__ == "__main__":
    main()
