#!/usr/bin/env python3
"""
Digital Twin — Backend de la mesa rotatoria (Raspberry Pi 4).

Expone el estado de la mesa y recibe comandos de la web:
  - WebSocket  ws://RPi_IP:8000/ws/turntable
        · emite el estado de la mesa (snapshot al conectar + en cada cambio)
        · acepta comandos del cliente:  {"command": "start"}  /  {"command": "stop"}
  - REST GET   /api/turntable/state      → snapshot actual
  - REST GET   /health                   → salud + estado de la mesa
  - REST POST  /api/turntable/activate    → arranca el ciclo de movimiento A↔B
  - REST POST  /api/turntable/deactivate  → detiene el movimiento
  - REST POST  /api/turntable/index        → un solo giro 180° (A↔B)

El movimiento del stepper corre en un HILO WORKER (no bloquea el event loop),
y el estado se publica al loop con loop.call_soon_threadsafe.  En una laptop
sin GPIO arranca en modo MOCK (simula el ángulo) → _demo: true.

Run:
    python3 turntable_backend.py
    uvicorn turntable_backend:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from turntable_controller import TurntableController, load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("turntable")

HEARTBEAT_S = 1.0  # republica el estado cada 1 s para que la web siga "en vivo"

cfg = load_config()
controller = TurntableController(cfg)


def envelope(tt_state: dict) -> dict:
    """Envuelve el estado de la mesa en el contrato JSON que espera la web."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ok": True,
        "_demo": controller.mock,
        "turntable": tt_state,
    }


# ── Estado compartido + broadcaster (1 productor, N suscriptores WS) ──────────
class TurntableHub:
    def __init__(self):
        self.latest: dict = envelope(controller.state())
        self.subscribers: list[asyncio.Queue] = []
        self.loop: asyncio.AbstractEventLoop | None = None

        # Control del hilo de movimiento.
        self._running = threading.Event()   # True mientras la mesa debe oscilar
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()       # serializa start/stop

    # Llamado desde el event loop.
    def broadcast(self, data: dict) -> None:
        self.latest = data
        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    # Callback que el controlador (hilo worker) usa para publicar estado.
    # Reprograma el broadcast en el event loop de forma segura entre hilos.
    def push_from_thread(self, tt_state: dict) -> None:
        if self.loop is None:
            return
        self.loop.call_soon_threadsafe(self.broadcast, envelope(tt_state))

    # ── Arranque / paro del ciclo de movimiento ───────────────────────────────
    def start(self) -> None:
        with self._lock:
            if self._running.is_set():
                return  # ya está corriendo (no duplicar hilo)
            self._running.set()
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()
            log.info("Mesa: ciclo de movimiento ARRANCADO (mock=%s)", controller.mock)

    def stop(self) -> None:
        with self._lock:
            self._running.clear()
        log.info("Mesa: ciclo de movimiento DETENIDO")

    def index_once(self) -> None:
        """Un solo giro 180° (A↔B) en un hilo, sin entrar en oscilación."""
        with self._lock:
            if self._running.is_set() or (self._worker and self._worker.is_alive()):
                return
            def _one():
                nxt = "B" if controller.position != "B" else "A"
                controller.move_to(nxt, on_update=self.push_from_thread)
            self._worker = threading.Thread(target=_one, daemon=True)
            self._worker.start()

    def _run(self) -> None:
        controller.run_cycle(
            should_continue=self._running.is_set,
            on_update=self.push_from_thread,
        )

    @property
    def active(self) -> bool:
        return self._running.is_set()


hub = TurntableHub()


# ── Heartbeat: republica el estado actual periódicamente ──────────────────────
async def heartbeat_loop() -> None:
    while True:
        hub.broadcast(envelope(controller.state()))
        await asyncio.sleep(HEARTBEAT_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.loop = asyncio.get_running_loop()
    task = asyncio.create_task(heartbeat_loop())
    try:
        yield
    finally:
        task.cancel()
        hub.stop()
        controller.cleanup()


app = FastAPI(title="Digital Twin — Turntable Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── REST ──────────────────────────────────────────────────────────────────────
@app.get("/api/turntable/state")
async def get_state() -> dict:
    return hub.latest


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "mock": controller.mock,
        "active": hub.active,
        "subscribers": len(hub.subscribers),
        "turntable": controller.state(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/turntable/activate")
async def activate() -> dict:
    hub.start()
    return {"ok": True, "active": hub.active}


@app.post("/api/turntable/deactivate")
async def deactivate() -> dict:
    hub.stop()
    return {"ok": True, "active": hub.active}


@app.post("/api/turntable/index")
async def index() -> dict:
    hub.index_once()
    return {"ok": True}


# ── WebSocket ───────────────────────────────────────────────────────────────
def _handle_command(text: str) -> None:
    try:
        msg = json.loads(text)
    except Exception:
        return
    cmd = (msg or {}).get("command")
    if cmd == "start":
        hub.start()
    elif cmd == "stop":
        hub.stop()
    elif cmd == "index":
        hub.index_once()


@app.websocket("/ws/turntable")
async def ws_turntable(websocket: WebSocket) -> None:
    await websocket.accept()
    q = hub.subscribe()
    log.info("WS mesa conectado. Total: %d", len(hub.subscribers))

    async def reader():
        # Lee comandos del cliente ({"command":"start"|"stop"|"index"}).
        try:
            while True:
                text = await websocket.receive_text()
                _handle_command(text)
        except Exception:
            pass

    rtask = asyncio.create_task(reader())
    try:
        await websocket.send_text(json.dumps(hub.latest))  # snapshot inmediato
        while True:
            data = await q.get()
            await websocket.send_text(json.dumps(data))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.warning("WS mesa error: %s", exc)
    finally:
        rtask.cancel()
        hub.unsubscribe(q)
        log.info("WS mesa desconectado. Total: %d", len(hub.subscribers))


if __name__ == "__main__":
    import os
    import socket
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = host
    print("\n  Digital Twin — Turntable Backend")
    print("  ─────────────────────────────────────────")
    print(f"  WebSocket : ws://{local_ip}:{port}/ws/turntable")
    print(f"  REST      : http://{local_ip}:{port}/api/turntable/state")
    print(f"  Health    : http://{local_ip}:{port}/health")
    print(f"  MOCK      : {controller.mock}   (pines STEP={cfg.step_pin} DIR={cfg.dir_pin})")
    print("  ─────────────────────────────────────────\n")
    uvicorn.run("turntable_backend:app", host=host, port=port, log_level="info")
