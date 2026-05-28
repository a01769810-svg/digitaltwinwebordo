#!/usr/bin/env python3
"""
Controlador seguro de la mesa rotatoria (NEMA stepper) — Raspberry Pi 4.

Reglas de seguridad respetadas:
  - NO mueve el motor al importar este módulo (no hay bucle a nivel de módulo).
  - Pines y parámetros vienen de .env (no hardcodeados en lógica).
  - Modo MOCK automático si no hay GPIO (corre en laptop sin hardware).
  - cleanup() ordenado de GPIO.
  - El movimiento es interrumpible (should_stop) para parar de forma limpia.

Pinout (BCM), por defecto:  STEP=GPIO17, DIR=GPIO27   (confirmado por el equipo)
Conversión:                 180° ≈ 185 pasos          STEP_DELAY=0.005 s

Uso típico (desde el backend, en un hilo worker):
    cfg = load_config()
    tt = TurntableController(cfg)
    tt.run_cycle(should_continue=lambda: running.is_set(), on_update=push)
    ...
    tt.cleanup()
"""

import os
import time
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # python-dotenv es opcional; si falta, se usan defaults / variables del entorno

# Import de GPIO tolerante: en una laptop (sin RPi) falla → modo MOCK automático.
try:
    import RPi.GPIO as GPIO  # en Pi 4/5 lo provee rpi-lgpio
    _HAS_GPIO = True
except Exception:
    GPIO = None
    _HAS_GPIO = False


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class TurntableConfig:
    step_pin: int = 17
    dir_pin: int = 27
    steps_180: int = 185
    step_delay: float = 0.005
    dwell_s: float = 1.0
    mock: bool = False


def load_config() -> TurntableConfig:
    """Lee la configuración desde el entorno/.env, con defaults seguros."""
    return TurntableConfig(
        step_pin=int(os.getenv("STEP_PIN", "17")),
        dir_pin=int(os.getenv("DIR_PIN", "27")),
        steps_180=int(os.getenv("STEPS_180", "185")),
        step_delay=float(os.getenv("STEP_DELAY", "0.005")),
        dwell_s=float(os.getenv("DWELL_S", "1.0")),
        # MOCK explícito, o automático si no hay librería GPIO.
        mock=_env_bool("MOCK", not _HAS_GPIO),
    )


class TurntableController:
    """
    Encapsula STEP/DIR y la conversión grados↔pasos.  El constructor configura
    los pines como salida en LOW (estado seguro) pero NO mueve el motor.
    """

    def __init__(self, cfg: TurntableConfig):
        self.cfg = cfg
        self.mock = cfg.mock or not _HAS_GPIO

        # Estado lógico (estimado: el stepper es open-loop, no hay encoder).
        self.angle_deg: float = 0.0
        self.position: str = "A"          # "A" (0°), "B" (180°) o "MOVING"
        self.moving: bool = False
        self.last_direction: str = "CW"   # "CW" subiendo a B, "CCW" bajando a A

        if not self.mock:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.cfg.step_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.cfg.dir_pin, GPIO.OUT, initial=GPIO.LOW)

    # ── Lectura de estado ────────────────────────────────────────────────────
    def state(self) -> dict:
        return {
            "angle_deg": round(self.angle_deg, 1),
            "position": self.position,
            "moving": self.moving,
            "last_direction": self.last_direction,
            "steps_180": self.cfg.steps_180,
        }

    # ── Movimiento de 180° hacia una posición destino ─────────────────────────
    def move_to(self, to_position: str, on_update=None, should_stop=None) -> None:
        """
        Gira 180° hasta 'A' (0°) o 'B' (180°).  Bloqueante: debe llamarse desde
        un hilo worker, NUNCA desde el event loop del servidor.  Llama a
        on_update(state) periódicamente y respeta should_stop() para abortar.
        """
        target_deg = 180.0 if to_position == "B" else 0.0
        start_deg = self.angle_deg
        going_to_b = to_position == "B"
        self.last_direction = "CW" if going_to_b else "CCW"
        self.moving = True
        self.position = "MOVING"

        if not self.mock:
            # GPIO HIGH = girar hacia B (+180), LOW = hacia A (−180).
            GPIO.output(self.cfg.dir_pin, GPIO.HIGH if going_to_b else GPIO.LOW)
            time.sleep(0.01)  # estabilizar DIR antes de pulsar STEP

        steps = max(1, self.cfg.steps_180)
        for i in range(steps):
            if should_stop and should_stop():
                break
            if not self.mock:
                GPIO.output(self.cfg.step_pin, GPIO.HIGH)
                time.sleep(self.cfg.step_delay)
                GPIO.output(self.cfg.step_pin, GPIO.LOW)
                time.sleep(self.cfg.step_delay)
            else:
                time.sleep(self.cfg.step_delay * 2)  # mismo timing en mock

            frac = (i + 1) / steps
            self.angle_deg = start_deg + (target_deg - start_deg) * frac
            if on_update and (i % 5 == 0):
                on_update(self.state())

        aborted = bool(should_stop and should_stop())
        if not aborted:
            self.angle_deg = target_deg
        self.moving = False
        if abs(self.angle_deg) < 1.0:
            self.position = "A"
        elif abs(self.angle_deg - 180.0) < 1.0:
            self.position = "B"
        else:
            self.position = "MOVING"  # quedó a medio camino (abortado)
        if on_update:
            on_update(self.state())

    # ── Ciclo de oscilación A↔B (lo que activa el botón de la web) ─────────────
    def run_cycle(self, should_continue, on_update=None) -> None:
        """
        Oscila A↔B mientras should_continue() sea True.  Imita el script físico:
        gira 180°, espera DWELL_S, gira de vuelta, repite.  Bloqueante → hilo.
        """
        while should_continue():
            nxt = "B" if self.position != "B" else "A"
            self.move_to(nxt, on_update=on_update, should_stop=lambda: not should_continue())
            if not should_continue():
                break
            # Pausa en el extremo (interrumpible).
            waited = 0.0
            while waited < self.cfg.dwell_s and should_continue():
                time.sleep(0.05)
                waited += 0.05
        self.moving = False
        if on_update:
            on_update(self.state())

    # ── Cierre ordenado ───────────────────────────────────────────────────────
    def cleanup(self) -> None:
        if not self.mock and GPIO is not None:
            try:
                GPIO.cleanup()
            except Exception:
                pass


if __name__ == "__main__":
    # Prueba manual local (en mock no toca hardware).  Gira una vez A→B→A.
    cfg = load_config()
    print(f"TurntableController  mock={cfg.mock}  pins STEP={cfg.step_pin} DIR={cfg.dir_pin} "
          f"steps_180={cfg.steps_180} delay={cfg.step_delay}")
    tt = TurntableController(cfg)
    try:
        tt.move_to("B", on_update=lambda s: print(s))
        time.sleep(cfg.dwell_s)
        tt.move_to("A", on_update=lambda s: print(s))
    except KeyboardInterrupt:
        print("Interrumpido")
    finally:
        tt.cleanup()
