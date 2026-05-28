# Mesa rotatoria — gateway Raspberry Pi

Backend que controla la mesa rotatoria (NEMA stepper) y la publica al digital
twin web por WebSocket. La web (pestaña **Cobot en Vivo**) tiene un botón
**ACTIVAR / DESACTIVAR MESA** que arranca/detiene el movimiento.

## Archivos

| Archivo | Qué hace |
|---|---|
| `turntable_controller.py` | Controlador seguro del NEMA. No mueve al importar, lee `.env`, modo mock, cleanup, movimiento interrumpible. STEP=17, DIR=27, 185 pasos/180°. |
| `turntable_backend.py` | FastAPI: `WS /ws/turntable` (estado + comandos start/stop), REST `/api/turntable/*`, `/health`, heartbeat, hilo worker. |
| `.env.example` | Configuración (copiar a `.env`). |
| `requirements.txt` | Dependencias. |

## Cómo correr

### En una laptop (modo MOCK, sin hardware) — para probar la web en vivo
```bash
cd raspberry
pip install fastapi "uvicorn[standard]" websockets python-dotenv
cp .env.example .env
python turntable_backend.py
```
Arranca en `:8000` en modo mock (simula el ángulo). La web puede conectarse y
ver la mesa girar "en vivo".

### En la Raspberry Pi 4 (control real del motor)
```bash
cd raspberry
pip install -r requirements.txt --break-system-packages
cp .env.example .env       # confirma STEP=17, DIR=27, STEPS_180=185
python3 turntable_backend.py
```

## Cómo lo consume la web

La web se conecta por defecto a:
```
wss://unmoral-shrink-cavalry.ngrok-free.dev/ws/turntable
```
- Al pulsar **ACTIVAR MESA** envía `{"command":"start"}` y sigue el ángulo real
  que reporta el backend.
- Al pulsar **DESACTIVAR MESA** envía `{"command":"stop"}`.
- Si el gateway no responde, la web **simula localmente** el ciclo 0°↔180°, así
  el botón funciona en el navegador aunque la RPi no esté corriendo.

## Exponer por el túnel ngrok existente

El túnel estático actual (`unmoral-shrink-cavalry.ngrok-free.dev`) apunta a
`localhost:8000`. Opciones:

1. **Rápido (dev):** corre solo este backend en `:8000` y abre el túnel hacia 8000
   (igual que `start_gateway.sh` del repo de la Raspberry).
2. **Recomendado (producción):** fusiona la ruta `/ws/turntable` y el controlador
   dentro del `backend.py` del cobot para que cobot + mesa compartan el mismo
   puerto 8000 y el mismo túnel. El controlador (`turntable_controller.py`) es un
   módulo independiente y reutilizable justo para esto.

## Contrato JSON (lo que emite el WS)

```json
{
  "timestamp": "2026-05-28T00:00:00Z",
  "ok": true,
  "_demo": false,
  "turntable": {
    "angle_deg": 180,
    "position": "B",
    "moving": false,
    "last_direction": "CW",
    "steps_180": 185
  }
}
```
`position`: `"A"` (0°), `"B"` (180°) o `"MOVING"`. `_demo: true` cuando corre en
mock (sin GPIO). El ángulo es **estimado** (el stepper es open-loop, sin encoder).
