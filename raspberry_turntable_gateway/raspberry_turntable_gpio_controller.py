#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raspberry_turntable_gpio_controller.py

Controlador SEGURO de la mesa rotatoria (turntable) de la celda Schneider.

Hardware objetivo (Raspberry Pi 4, numeración BCM):
    - Motor NEMA 17 vía driver A4988
        STEP -> GPIO17   (configurable por .env: STEP_PIN)
        DIR  -> GPIO27   (configurable por .env: DIR_PIN)
    - Limit switches (pull-up interno; sin presionar = HIGH, presionado = LOW):
        LIMIT_HOME -> GPIO22  (LIMIT_HOME_PIN)
        LIMIT_WORK -> GPIO23  (LIMIT_WORK_PIN)
    - Remachado: por ahora SIMULADO (dwell). Futuro actuador.

Reglas de seguridad respetadas (ver README_RASPBERRY_TURNTABLE.md):
    * NO mueve el motor al importar el módulo ni al instanciar la clase.
    * NO usa `while True` bloqueante a nivel de módulo.
    * El ciclo corre en un hilo worker (no bloquea el event loop del gateway).
    * Rechaza comandos nuevos si ya está en movimiento (serialización).
    * Es interrumpible (stop()) y hace cleanup() ordenado.
    * Pines y tiempos vienen de .env, NO hardcodeados como verdad única.
    * Modo MOCK automático: corre en una laptop sin GPIO (para la web sin HW).

El estado expuesto por get_turntable_state() es EXACTAMENTE el contrato JSON
que consume la web (HOME/WORK/RIVETING…), idéntico a turntableSim.ts.
"""

import os
import threading
import time

try:
    from dotenv import load_dotenv  # opcional
    load_dotenv(os.path.join(os.path.dirname(__file__), "raspberry_turntable_env_example.env"))
    load_dotenv()  # también un .env real si existe
except Exception:
    pass


# ── Detección de GPIO real vs MOCK ───────────────────────────────────────────
def _env(name, default):
    return os.environ.get(name, str(default))


def _env_int(name, default):
    try:
        return int(_env(name, default))
    except ValueError:
        return default


def _env_float(name, default):
    try:
        return float(_env(name, default))
    except ValueError:
        return default


FORCE_MOCK = _env("TURNTABLE_MOCK", "0").lower() in ("1", "true", "yes")

GPIO = None
HAS_GPIO = False
if not FORCE_MOCK:
    try:
        import RPi.GPIO as GPIO  # resuelto vía rpi-lgpio en Pi 4/5 reciente
        HAS_GPIO = True
    except Exception:
        HAS_GPIO = False


# ── Parámetros configurables ─────────────────────────────────────────────────
STEP_PIN = _env_int("STEP_PIN", 17)
DIR_PIN = _env_int("DIR_PIN", 27)
LIMIT_HOME_PIN = _env_int("LIMIT_HOME_PIN", 22)
LIMIT_WORK_PIN = _env_int("LIMIT_WORK_PIN", 23)

STEPS_180 = _env_int("STEPS_180", 185)        # pasos para girar 180° (calibrar en HW)
STEP_DELAY = _env_float("STEP_DELAY", 0.005)  # s entre flancos (velocidad)
RIVET_SECONDS = _env_float("RIVET_SECONDS", 10.0)  # dwell de remachado físico
MAX_MOVE_STEPS = _env_int("MAX_MOVE_STEPS", 4000)  # tope de seguridad open-loop

# Posiciones lógicas
HOME, WORK = "HOME", "WORK"


class TurntableController:
    """Controla la mesa. Instanciar NO mueve el motor (solo configura GPIO)."""

    def __init__(self):
        self.mock = not HAS_GPIO
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()

        # Estado lógico (contrato)
        self.position = HOME
        self.angle_deg = 0.0
        self.moving = False
        self.target = WORK
        self.last_direction = "NONE"   # TO_WORK | TO_HOME | NONE
        self.riveting = False
        self.riveting_done = False
        self.fault = False
        self.message = "Esperando inicio"

        if not self.mock:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(STEP_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(DIR_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(LIMIT_HOME_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(LIMIT_WORK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # ── Lectura de limits ────────────────────────────────────────────────────
    def read_limits(self):
        """Devuelve (limit_home, limit_work). Presionado=LOW -> True (activo)."""
        if self.mock:
            # En mock derivamos los limits del estado lógico.
            return (self.position in (HOME, "CYCLE_DONE"),
                    self.position in (WORK, "RIVETING", "RIVETING_DONE"))
        home = (GPIO.input(LIMIT_HOME_PIN) == GPIO.LOW)
        work = (GPIO.input(LIMIT_WORK_PIN) == GPIO.LOW)
        return home, work

    # ── Movimiento de bajo nivel ──────────────────────────────────────────────
    def _pulse_step(self):
        if self.mock:
            time.sleep(STEP_DELAY)
            return
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(STEP_DELAY / 2.0)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(STEP_DELAY / 2.0)

    def _move_until_limit(self, direction, limit_check, to_position):
        """Gira en `direction` hasta que se active el limit, con tope de seguridad.

        direction: 'TO_WORK' o 'TO_HOME'.
        limit_check: callable() -> bool (limit activo).
        """
        self.last_direction = direction
        if not self.mock:
            GPIO.output(DIR_PIN, GPIO.HIGH if direction == "TO_WORK" else GPIO.LOW)

        steps = 0
        # En mock no hay limit físico: usamos STEPS_180 como recorrido nominal.
        target_steps = STEPS_180
        while not self._stop_flag.is_set():
            # Hardware: parar cuando el limit se active.
            if not self.mock:
                _, work_lim = self.read_limits()
                home_lim, _ = self.read_limits()
                if (direction == "TO_WORK" and work_lim) or \
                   (direction == "TO_HOME" and home_lim):
                    break
            else:
                if steps >= target_steps:
                    break

            self._pulse_step()
            steps += 1
            # Ángulo estimado (open-loop): 0..180 proporcional a pasos.
            frac = min(1.0, steps / float(STEPS_180))
            self.angle_deg = 180.0 * frac if direction == "TO_WORK" else 180.0 * (1.0 - frac)

            if steps > MAX_MOVE_STEPS:
                self.fault = True
                self.message = "FAULT: no se alcanzó el limit (¿pasos perdidos?)"
                return False

        self.angle_deg = 180.0 if to_position == WORK else 0.0
        self.position = to_position
        return True

    # ── Acciones de alto nivel (contrato) ─────────────────────────────────────
    def move_to_work(self):
        self.moving = True
        self.target = WORK
        self.position = "MOVING_TO_WORK"
        self.message = "Moviendo hacia zona de remachado"
        ok = self._move_until_limit("TO_WORK", None, WORK)
        self.moving = False
        if ok:
            self.message = "En posición de remachado"
        return ok

    def move_to_home(self):
        self.moving = True
        self.target = HOME
        self.position = "MOVING_TO_HOME"
        self.message = "Regresando a HOME"
        ok = self._move_until_limit("TO_HOME", None, HOME)
        self.moving = False
        if ok:
            self.position = "CYCLE_DONE"
            self.message = "REMACHADO ACABADO"
        return ok

    def run_riveting_cycle(self):
        """Ciclo completo HOME->WORK->RIVETING->HOME. Pensado para correr en hilo.

        Rechaza el arranque si ya hay un movimiento en curso (serialización).
        """
        if not self._lock.acquire(blocking=False):
            return False  # ya hay un ciclo activo
        try:
            self._stop_flag.clear()
            self.fault = False
            self.riveting_done = False

            if not self.move_to_work():
                return False
            if self._stop_flag.is_set():
                return False

            # Remachado simulado (dwell). Futuro: disparar actuador real aquí.
            self.target = HOME  # el siguiente movimiento será de regreso
            self.position = "RIVETING"
            self.riveting = True
            self.message = "Remachando"
            t0 = time.time()
            while time.time() - t0 < RIVET_SECONDS and not self._stop_flag.is_set():
                time.sleep(0.05)
            self.riveting = False
            self.riveting_done = True
            self.position = "RIVETING_DONE"
            self.message = "Remachado terminado"

            if self._stop_flag.is_set():
                return False

            self.move_to_home()
            return True
        finally:
            self._lock.release()

    def stop(self):
        """Interrumpe el ciclo en curso de forma segura."""
        self._stop_flag.set()
        self.moving = False
        self.riveting = False

    # ── Estado / contrato ──────────────────────────────────────────────────────
    def get_turntable_state(self):
        home_lim, work_lim = self.read_limits()
        return {
            "angle_deg": round(self.angle_deg, 1),
            "position": self.position,
            "moving": self.moving,
            "target": self.target,
            "last_direction": self.last_direction,
            "limit_home": home_lim,
            "limit_work": work_lim,
            "riveting": self.riveting,
            "riveting_done": self.riveting_done,
            "fault": self.fault,
            "message": self.message,
        }

    def cleanup(self):
        """Cierre ordenado del GPIO. Llamar siempre al terminar."""
        self.stop()
        if not self.mock and GPIO is not None:
            try:
                GPIO.output(STEP_PIN, GPIO.LOW)
                GPIO.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    # Smoke test manual (mock por defecto si no hay GPIO). NO se ejecuta al importar.
    ctl = TurntableController()
    print("Modo:", "MOCK" if ctl.mock else "GPIO real")
    print("Estado inicial:", ctl.get_turntable_state())
    print("Corriendo un ciclo de remachado…")
    ctl.run_riveting_cycle()
    print("Estado final:", ctl.get_turntable_state())
    ctl.cleanup()
