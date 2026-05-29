#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raspberry_turntable_limit_switch_test.py

Prueba AISLADA de los dos limit switches (sin mover el motor).

Lee LIMIT_HOME (GPIO22) y LIMIT_WORK (GPIO23) con pull-up interno e imprime su
estado ~5 veces/seg.  Presiona cada switch a mano para confirmar el cableado:
    sin presionar = HIGH = inactivo
    presionado    = LOW  = activo (True)

Uso (en la Raspberry):
    python raspberry_turntable_limit_switch_test.py

NO mueve el motor.  Pulsa Ctrl+C para salir (hace cleanup ordenado).
"""

import os
import time

LIMIT_HOME_PIN = int(os.environ.get("LIMIT_HOME_PIN", "22"))
LIMIT_WORK_PIN = int(os.environ.get("LIMIT_WORK_PIN", "23"))

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except Exception:
    HAS_GPIO = False


def main():
    if not HAS_GPIO:
        print("RPi.GPIO no disponible — este test requiere la Raspberry con GPIO.")
        print("(En laptop usa raspberry_turntable_mock_test.py para validar la lógica.)")
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LIMIT_HOME_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(LIMIT_WORK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print(f"Leyendo LIMIT_HOME=GPIO{LIMIT_HOME_PIN}  LIMIT_WORK=GPIO{LIMIT_WORK_PIN}")
    print("Presiona cada switch para verificar (Ctrl+C para salir)…\n")
    try:
        while True:
            home = (GPIO.input(LIMIT_HOME_PIN) == GPIO.LOW)
            work = (GPIO.input(LIMIT_WORK_PIN) == GPIO.LOW)
            print(f"\rHOME={'ACTIVO' if home else '  --  '}   "
                  f"WORK={'ACTIVO' if work else '  --  '}   ", end="", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nSaliendo…")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
