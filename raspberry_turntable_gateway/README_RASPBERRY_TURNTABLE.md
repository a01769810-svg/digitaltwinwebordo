# README — Raspberry Turntable Gateway

Gateway de la **mesa rotatoria (turntable)** de la celda Schneider para la
**Raspberry Pi 4**. Controla el disco con un **NEMA 17 + A4988** y dos **limit
switches**, simula el **remachado**, y publica el estado por **WebSocket/REST**
para que la web lo mueva en tiempo real en la pestaña **"Cobot en Vivo"**.

El contrato JSON es **idéntico** al de la simulación web (`turntableSim.ts`), así
que la web no distingue mock de hardware: solo cambia la fuente de datos.

---

## Archivos (nombres autoexplicativos)

| Archivo | Para qué sirve |
|---|---|
| `raspberry_turntable_gpio_controller.py` | **Controlador seguro** de la mesa. Clase `TurntableController`: STEP/DIR, limits, `move_to_work()`, `move_to_home()`, `run_riveting_cycle()`, `read_limits()`, `get_turntable_state()`, `stop()`, `cleanup()`. Modo MOCK automático. **No mueve el motor al importar.** |
| `raspberry_turntable_fastapi_gateway.py` | **Servidor FastAPI + WebSocket.** Expone `/health`, `/api/turntable/state`, `/api/turntable/start-cycle`, `/api/turntable/stop`, `/ws/turntable`. El ciclo corre en hilo worker (no bloquea el WS). |
| `raspberry_turntable_mock_test.py` | Corre un **ciclo completo en MOCK** (sin hardware) e imprime el contrato en cada transición. Valida la lógica en laptop. |
| `raspberry_turntable_limit_switch_test.py` | Prueba **aislada de los limit switches** (no mueve el motor). |
| `raspberry_turntable_stepper_test.py` | Prueba **aislada del motor** (gira N pasos ida y vuelta). Para calibrar `STEPS_180`. ⚠ Sí mueve el motor. |
| `raspberry_turntable_env_example.env` | **Plantilla de configuración** (pines, pasos, tiempos). Copiar a `.env`. |
| `requirements.txt` | Dependencias Python. |

---

## Pinout (BCM)

| Señal | GPIO | Notas |
|---|---|---|
| STEP (A4988) | **GPIO17** | configurable `STEP_PIN` |
| DIR (A4988) | **GPIO27** | configurable `DIR_PIN` |
| LIMIT_HOME | **GPIO22** | pull-up interno; presionado = LOW |
| LIMIT_WORK | **GPIO23** | pull-up interno; presionado = LOW |

> `STEPS_180` (pasos para 180°) **debe calibrarse en hardware** con el
> `stepper_test`. El valor de referencia es 185, pero depende del microstepping
> del A4988 y de la reductora/correa.

---

## Cómo correr

### 1. Mock en laptop (sin Raspberry, sin hardware)
```bash
cd raspberry_turntable_gateway
pip install -r requirements.txt          # o solo: pip install fastapi uvicorn[standard] python-dotenv

# Test de lógica (imprime el contrato en cada transición):
TURNTABLE_MOCK=1 python raspberry_turntable_mock_test.py
# Windows PowerShell:  $env:TURNTABLE_MOCK=1; python raspberry_turntable_mock_test.py
```

### 2. Gateway en mock (la web ya se conecta)
```bash
TURNTABLE_MOCK=1 uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
# Pruebas:
#   curl http://localhost:8000/health
#   curl http://localhost:8000/api/turntable/state
#   curl -X POST http://localhost:8000/api/turntable/start-cycle
```

### 3. En la Raspberry Pi (hardware real)
```bash
cp raspberry_turntable_env_example.env .env   # ajusta pines/STEPS_180
# Primero valida cableado SIN ciclo:
python raspberry_turntable_limit_switch_test.py
python raspberry_turntable_stepper_test.py     # ⚠ mueve el motor (pocos pasos)
# Luego el gateway real:
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

---

## Conectar con la web

En la pestaña **"Cobot en Vivo"**, el panel **"Mesa Rotatoria · Raspberry"**:

1. Pega la URL del gateway:
   - LAN: `ws://<IP-de-la-RPi>:8000/ws/turntable`
   - HTTPS (Railway): publica el puerto 8000 por el **mismo túnel ngrok** del
     cobot y usa `wss://<tu-dominio>.ngrok-free.dev/ws/turntable`.
2. **CONECTAR** → la mesa 3D empieza a girar con `angle_deg` real.
3. **START CYCLE** → `POST /api/turntable/start-cycle` arranca el ciclo en la RPi.

> Si no hay gateway, la vista cae a **DEMO** silenciosamente (mesa en HOME).
> La **simulación completa** (sin hardware) vive en la pestaña **"Celda 3D"**.

---

## Contrato JSON (`/ws/turntable` y `/api/turntable/state`)

```json
{
  "timestamp": "2026-05-28T00:00:00.000Z",
  "ok": true,
  "_demo": true,
  "turntable": {
    "angle_deg": 0,
    "position": "HOME",
    "moving": false,
    "target": "WORK",
    "last_direction": "NONE",
    "limit_home": true,
    "limit_work": false,
    "riveting": false,
    "riveting_done": false,
    "fault": false,
    "message": "Esperando inicio"
  }
}
```

`position` recorre: `HOME → MOVING_TO_WORK → WORK → RIVETING → RIVETING_DONE →
MOVING_TO_HOME → CYCLE_DONE → HOME`. `_demo=true` cuando corre sin GPIO (mock).

---

## Seguridad (qué respeta este código)

- ✅ No mueve el motor al importar módulos ni al instanciar la clase.
- ✅ Sin `while True` bloqueante a nivel de módulo.
- ✅ El giro corre en hilo worker → el WebSocket no se congela.
- ✅ Rechaza comandos si ya está en movimiento (serialización + HTTP 409).
- ✅ `stop()` interrumpe; `cleanup()` hace `GPIO.cleanup()` ordenado.
- ✅ Pines/pasos/tiempos en `.env`, no hardcodeados como verdad única.
- ✅ La web manda **intención** (`start-cycle`); la RPi valida y ejecuta.
- ⚠ Open-loop (sin encoder): `angle_deg` es **estimado** por pasos. El límite
  físico es la verdad de posición (HOME/WORK).
