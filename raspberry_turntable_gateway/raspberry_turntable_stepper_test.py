#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raspberry_turntable_stepper_test.py

Prueba AISLADA del motor NEMA 17 + driver A4988 (sin limits, sin ciclo).

Gira un número FIJO y pequeño de pasos en una dirección y luego en la otra,
para confirmar el cableado STEP=GPIO17 / DIR=GPIO27 y el sentido de giro.
Empieza con pocos pasos y sube STEPS gradualmente para calibrar STEPS_180.

Uso (en la Raspberry):
    python raspberry_turntable_stepper_test.py            # 200 pasos ida y vuelta
    STEPS=400 STEP_DELAY=0.004 python raspberry_turntable_stepper_test.py

ADVERTENCIA: este script SÍ mueve el motor.  Asegúrate de que la mesa pueda
girar libremente y de tener a mano el paro.  NO se ejecuta al importar.
"""

import os
import time

STEP_PIN = int(os.environ.get("STEP_PIN", "17"))
DIR_PIN = int(os.environ.get("DIR_PIN", "27"))
STEPS = int(os.environ.get("STEPS", "200"))
STEP_DELAY = float(os.environ.get("STEP_DELAY", "0.005"))

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except Exception:
    HAS_GPIO = False


def _spin(direction_high, steps):
    GPIO.output(DIR_PIN, GPIO.HIGH if direction_high else GPIO.LOW)
    for _ in range(steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(STEP_DELAY / 2.0)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(STEP_DELAY / 2.0)


def main():
    if not HAS_GPIO:
        print("RPi.GPIO no disponible — este test requiere la Raspberry con GPIO.")
        return

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)

    print(f"STEP=GPIO{STEP_PIN}  DIR=GPIO{DIR_PIN}  STEPS={STEPS}  STEP_DELAY={STEP_DELAY}")
    try:
        print("Girando hacia WORK…")
        _spin(True, STEPS)
        time.sleep(0.5)
        print("Girando hacia HOME…")
        _spin(False, STEPS)
        print("OK — si la mesa volvió a su lugar, el cableado y el sentido son correctos.")
    finally:
        GPIO.output(STEP_PIN, GPIO.LOW)
        GPIO.cleanup()


if __name__ == "__main__":
    main()
