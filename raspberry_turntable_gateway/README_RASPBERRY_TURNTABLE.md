# Raspberry Turntable Gateway

Gateway de la mesa rotatoria de la celda Schneider para Raspberry Pi 4. Controla
un NEMA 17 con driver A4988, lee dos limit switches, simula el tiempo de
remachado y publica el estado por REST/WebSocket para la web.

El contrato JSON debe mantenerse alineado con `components/turntableSim.ts`. La
web no deberia distinguir entre mock y hardware real: solo cambia la fuente de
datos.

## Archivos

| Archivo | Funcion |
|---|---|
| `raspberry_turntable_fastapi_gateway.py` | Corre el gateway FastAPI + WebSocket. Expone `/health`, `/api/turntable/state`, `/api/turntable/start-cycle`, `/api/turntable/stop` y `/ws/turntable`. |
| `raspberry_turntable_gpio_controller.py` | Controlador GPIO seguro. Maneja STEP/DIR, limits, movimiento HOME/WORK, ciclo de remachado, `stop()` y `cleanup()`. No debe mover motor al importar. |
| `raspberry_turntable_limit_switch_test.py` | Prueba limits sin mover el motor. Usar primero para validar cableado. |
| `raspberry_turntable_stepper_test.py` | Prueba el stepper. Mueve el motor; usar solo con hardware libre y supervisado. |
| `raspberry_turntable_mock_test.py` | Corre ciclo completo en mock sin GPIO. Sirve para laptop o debug sin hardware. |
| `raspberry_turntable_env_example.env` | Plantilla de `.env` con pines, pasos y tiempos. |
| `requirements.txt` | Dependencias Python. |

## Pines GPIO esperados

Numeracion BCM:

| Senal | GPIO | Notas |
|---|---|---|
| STEP | GPIO17 | Pulso STEP al A4988. |
| DIR | GPIO27 | Direccion del A4988. |
| LIMIT_HOME | GPIO22 | Pull-up interno. |
| LIMIT_WORK | GPIO23 | Pull-up interno. |

Limits con pull-up interno:

- Sin presionar: HIGH.
- Presionado: LOW.

No cambies estos pines sin confirmar el cableado fisico.

## Instalacion

```bash
cd raspberry_turntable_gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp raspberry_turntable_env_example.env .env
```

En Windows PowerShell para pruebas mock:

```powershell
cd raspberry_turntable_gateway
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item raspberry_turntable_env_example.env .env
```

## Correr gateway

Mock sin hardware:

```bash
TURNTABLE_MOCK=1 uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

PowerShell:

```powershell
$env:TURNTABLE_MOCK=1
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

Hardware real:

```bash
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

Endpoints:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/turntable/state
curl -X POST http://localhost:8000/api/turntable/start-cycle
```

WebSocket:

```text
ws://<IP-de-la-RPi>:8000/ws/turntable
```

## Pruebas recomendadas

Primero mock:

```bash
TURNTABLE_MOCK=1 python raspberry_turntable_mock_test.py
```

Luego limits, sin mover motor:

```bash
python raspberry_turntable_limit_switch_test.py
```

Despues stepper, solo con hardware seguro:

```bash
python raspberry_turntable_stepper_test.py
```

Finalmente gateway real:

```bash
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

## Conectar con la web

En la tab `Cobot en Vivo`, panel de mesa rotatoria:

1. Usa `ws://<IP-de-la-RPi>:8000/ws/turntable` en LAN.
2. Si usas tunel publico, usa `wss://<dominio>/ws/turntable`.
3. Presiona conectar.
4. `START CYCLE` llama `POST /api/turntable/start-cycle`.

Si no hay gateway, la web cae a modo demo.

## Contrato JSON

Ejemplo:

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

Estados esperados:

```text
HOME -> MOVING_TO_WORK -> WORK -> RIVETING -> RIVETING_DONE -> MOVING_TO_HOME -> CYCLE_DONE -> HOME
```

No cambies nombres de campos ni valores sin actualizar tambien la web.

## Seguridad

- No energices el motor sin revisar driver, fuente, corriente limite y masa
  comun con Raspberry.
- Haz primero `raspberry_turntable_limit_switch_test.py`.
- Usa `raspberry_turntable_stepper_test.py` solo con la mesa libre de manos,
  herramientas y piezas sueltas.
- Ten forma fisica de cortar energia al motor.
- Verifica que `STEPS_180` este calibrado antes de ciclos completos.
- El sistema es open-loop: `angle_deg` es estimado por pasos. Los limit switches
  son la referencia fisica.
- `stop()` y `cleanup()` existen, pero no sustituyen un paro fisico de seguridad.
- No corras pruebas de motor por SSH sin alguien supervisando el hardware.
