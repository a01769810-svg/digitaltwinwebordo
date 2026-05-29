#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raspberry_turntable_fastapi_gateway.py

Gateway FastAPI + WebSocket de la mesa rotatoria, para la Raspberry Pi 4.

Publica el contrato JSON (HOME/WORK/RIVETING…) que la web mueve en tiempo real
en la pestaña "Cobot en Vivo".  Reutiliza el patrón del backend del cobot:
CORS abierto, modo demo (_demo), broadcaster multi-suscriptor por WebSocket.

Endpoints:
    GET   /health                     -> salud del gateway + modo (mock/real)
    GET   /api/turntable/state        -> snapshot REST del contrato
    POST  /api/turntable/start-cycle  -> arranca un ciclo (hilo worker)
    POST  /api/turntable/stop         -> interrumpe el ciclo
    WS    /ws/turntable               -> stream del contrato (~10 Hz)

Seguridad:
    * El ciclo del stepper corre en un HILO worker (run_in_executor / Thread),
      NO en el event loop -> el WebSocket nunca se congela durante el giro.
    * start-cycle se rechaza si la mesa ya está en movimiento (HTTP 409).
    * Apagado ordenado: cleanup() del controlador en el shutdown.

Arranque:
    uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000

Para publicarlo por HTTPS/WSS (y que la web en Railway lo alcance sin
mixed-content), exponerlo por el MISMO túnel ngrok del cobot.
"""

import asyncio
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from raspberry_turntable_gpio_controller import TurntableController

app = FastAPI(title="Schneider Turntable Gateway", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

controller = TurntableController()
_cycle_thread = None


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _envelope():
    """Sobre completo del contrato: timestamp + ok + _demo + turntable."""
    return {
        "timestamp": _now_iso(),
        "ok": not controller.fault,
        "_demo": controller.mock,
        "turntable": controller.get_turntable_state(),
    }


def _start_cycle_thread():
    """Lanza el ciclo en un hilo worker si no hay otro en curso."""
    global _cycle_thread
    if _cycle_thread is not None and _cycle_thread.is_alive():
        return False
    _cycle_thread = threading.Thread(
        target=controller.run_riveting_cycle, name="turntable-cycle", daemon=True)
    _cycle_thread.start()
    return True


# ── REST ─────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "turntable",
        "mock": controller.mock,
        "moving": controller.moving,
        "position": controller.position,
    }


@app.get("/api/turntable/state")
def state():
    return _envelope()


@app.post("/api/turntable/start-cycle")
def start_cycle():
    if controller.moving:
        return JSONResponse(status_code=409, content={"ok": False, "error": "mesa en movimiento"})
    started = _start_cycle_thread()
    if not started:
        return JSONResponse(status_code=409, content={"ok": False, "error": "ciclo ya en curso"})
    return {"ok": True, "message": "ciclo iniciado"}


@app.post("/api/turntable/stop")
def stop_cycle():
    controller.stop()
    return {"ok": True, "message": "stop solicitado"}


# ── WebSocket: stream del contrato (~10 Hz) ───────────────────────────────────
@app.websocket("/ws/turntable")
async def ws_turntable(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(_envelope())
            await asyncio.sleep(0.1)  # 10 Hz; el giro corre en hilo aparte
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.on_event("shutdown")
def _shutdown():
    controller.cleanup()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
