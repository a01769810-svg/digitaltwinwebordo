# IMPLEMENTATION — Digital Twin: Mesa Rotatoria + HMI V62

Integración final de la **mesa rotatoria (turntable)** y la **HMI de operador
V62** en la web del Digital Twin de la celda Schneider.

- **Repo destino:** https://github.com/a01769810-svg/digitaltwinwebordo
- **Branch:** `feature/raspberry-turntable-hmi`
- **Fecha:** 2026-05-28

---

## 1. Qué repos se usaron

| Repo | Rol |
|---|---|
| `Quique2/SchneiderProjectWeb_DigitalTwin` | **Base web** (ya clonada en el destino en sesión previa). |
| `Quique2/SchneiderProjectWeb_Simulation` | **Fuente de la HMI V62** (`src/schneider_hmi/src/hmi_node.py`). |
| `Quique2/RaspberryPiGIT` | **Referencia Raspberry** (backend FastAPI del cobot, scripts de motor). |
| `a01769810-svg/digitaltwinwebordo` | **Destino** — aquí queda todo. |

## 2. Qué se copió / clonó

La base web (Expo + React Native Web + React Three Fiber) ya estaba clonada en
el repo destino. Esta fase **no re-clona**: parte de esa base y agrega encima la
mesa rotatoria, la HMI V62 y el gateway Raspberry. El build (`dist/`) se
regeneró para que el deploy incluya todo lo nuevo.

## 3. Qué se integró de la V62

La HMI de la simulación ROS (`hmi_node.py`, estable desde V55 y vigente en
V61/V62 — las V61/V62 solo recalcularon poses del cobot, no la HMI) se **portó a
React** (`components/OperatorHMI.tsx`):

- 4 botones de operador con su matriz de habilitación: **START** (IDLE) ·
  **Colocar CAFI** (RUNNING + spawn) · **STOP** (RUNNING) · **RESET**
  (PAUSED/FAULT).
- Estado de **celda** + **etapa de ciclo** + **veredicto de cámara** (PASS/FAIL).
- Indicadores **SPAWN ALLOWED/BLOCKED** y **fault**.
- **4 lámparas Digital Input**: Conveyor · Remachado · Visión · Cobot ready.
- **8 lámparas Digital Output**: Conv Motor · Disco · Remachado · Cámara ·
  Grip Open · Grip Close · Sol Left · Reservado.

## 4. Qué HMI se agregó y dónde

`OperatorHMI.tsx` se integró en la pestaña **"Celda 3D"**, reemplazando el
**placeholder** que decía *"Pending: DI/DO lamps, cycle state, verdict…"* en el
panel lateral derecho. Convive con la escena 3D (la mesa gira mientras se opera
la HMI). Se agregó además una sección **"Mesa Rotatoria (turntable)"** con la
lectura del contrato nuevo (posición, ángulo, target, dirección, limits HOME/WORK,
remachado).

## 5. Qué apartado Debug se eliminó

El panel lateral de "Celda 3D" tenía una pestaña **DEBUG** (secuenciador, pose
library, jogging, IK, etc.). Ahora **no se muestra al usuario final**: se ocultó
detrás de la constante `SHOW_DEBUG = false` en `CellViewer3D.tsx`. El código
debug se conserva como herramienta interna (ponlo en `true` para depurar), pero
la pestaña arranca directamente en la **HMI de operador**.

## 6. Qué lógica de mesa se agregó

Máquina de estados **completa** del disco (`components/turntableSim.ts`):

```
HOME → MOVING_TO_WORK → WORK → RIVETING → RIVETING_DONE
     → MOVING_TO_HOME → CYCLE_DONE → (HOME)
```

- Ángulo visual: **HOME = 0°**, **WORK = 180°**, interpolación con easing coseno.
- Limit switches lógicos: `limit_home` activo en HOME/CYCLE_DONE, `limit_work`
  activo en WORK/RIVETING/RIVETING_DONE.
- Estados de remachado: `riveting` (durante el dwell) y `riveting_done`.
- El hook `useTurntableSim()` corre la simulación en un loop
  `requestAnimationFrame` y **escribe el ángulo en el `discAngleRef`** de la
  escena, así el disco URDF gira en tiempo real siguiendo la simulación.

### Ciclo COMPLETO de la celda en Celda 3D (tipo ROS)

La pestaña **Celda 3D** ejecuta el ciclo completo de la celda (el mismo
`SequencePlayer` de la simulación), ahora disparado desde la HMI:

- Botón **START** → corre una **flota de 5 CAFIs** (5 entran, 5 salen). Cada CAFI:
  1. **entra al conveyor y viaja por la banda** hasta el punto de pick (paso
     `cafiConveyor`, el CAFI se ve desplazarse),
  2. el **cobot** lo recoge del conveyor, lo levanta y lo coloca en el fixture,
  3. el **disco indexa 180°**, **remacha** (30 s, spec real) e indexa de regreso,
  4. el cobot recoge la pieza remachada y la lleva a **visión**,
  5. la **cámara** da veredicto **PASS/FAIL**, y el cobot la deja en el bin
     **aceptado/rechazado** y vuelve a HOME,
  6. al terminar, arranca el siguiente CAFI hasta completar los 5.
- Botón **CAFI** → corre 1 CAFI suelto. **STOP** pausa. **RESET** reinicia la flota.
- La HMI V62 muestra en vivo el contador **CAFI IN: x/5 · CAFI OUT: x/5**, el
  estado de mesa, limits, remachado, DI/DO y el veredicto — es un **espejo** del
  ciclo real (igual que la HMI ROS, que solo refleja estado).
- Velocidad de demo opcional: `window.__CELL_SPEED = 30` acelera el ciclo
  (default 1 = timing real). Útil para revisar los 5 CAFIs rápido.

**Verificado headless (Chrome):** START → los 5 CAFIs recorren
`conveyor → in_gripper → on_fixture → at_vision → bin`, el cobot se mueve en
todas las poses, CAFI IN 5/5 y OUT 5/5, **cero errores de consola**.

### Reparto Celda 3D vs Cobot en Vivo

- **Celda 3D** = **simulación 100% mock** desde la web (sin hardware): se opera
  con la HMI (START → Colocar CAFI → ciclo) y se ve el disco girar, los limits,
  el remachado, las lámparas DI/DO y el veredicto. No depende de la Raspberry.
- **Cobot en Vivo** = **datos reales** de la Raspberry. Se agregó el panel
  **"Mesa Rotatoria · Raspberry"** y el disco 3D de la mesa, alimentados por el
  WebSocket `/ws/turntable` (con fallback a REST y a DEMO). El cobot existente
  **no se tocó**. El contrato es el nuevo (HOME/WORK/RIVETING…), no A/B/MOVING.

## 7. Qué contrato JSON se usó

Sobre + bloque `turntable` (idéntico en web mock y en la Raspberry):

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

`position ∈ {HOME, MOVING_TO_WORK, WORK, RIVETING, RIVETING_DONE,
MOVING_TO_HOME, CYCLE_DONE, ERROR}`. `_demo=true` cuando corre sin GPIO (mock).

## 8. Archivos Raspberry (carpeta `raspberry_turntable_gateway/`)

| Archivo | Para qué sirve |
|---|---|
| `raspberry_turntable_gpio_controller.py` | Controlador seguro `TurntableController` (STEP=17, DIR=27, LIMIT_HOME=22, LIMIT_WORK=23; `.env`; mock automático; sin movimiento en import; serialización; `stop()`/`cleanup()`). Métodos: `move_to_work`, `move_to_home`, `run_riveting_cycle`, `read_limits`, `get_turntable_state`. |
| `raspberry_turntable_fastapi_gateway.py` | Gateway FastAPI + WebSocket. `/health`, `/api/turntable/state`, `/api/turntable/start-cycle`, `/api/turntable/stop`, `/ws/turntable`. El ciclo corre en hilo worker (no bloquea el WS). |
| `raspberry_turntable_mock_test.py` | Ciclo completo en MOCK que imprime el contrato en cada transición (valida lógica en laptop). |
| `raspberry_turntable_limit_switch_test.py` | Prueba aislada de los limit switches (no mueve el motor). |
| `raspberry_turntable_stepper_test.py` | Prueba aislada del motor (gira N pasos ida y vuelta; para calibrar `STEPS_180`). |
| `raspberry_turntable_env_example.env` | Plantilla de configuración (pines, pasos, tiempos). Copiar a `.env`. |
| `requirements.txt` | Dependencias Python del gateway. |
| `README_RASPBERRY_TURNTABLE.md` | Guía completa de uso. |

## 9. Cómo correr la web

```bash
cd SchneiderProjectWeb_DigitalTwin_Sandbox   # (el repo destino)
npm install
npm start          # dev server (expo start --web)  → abre en el navegador
# o build de producción:
npm run build      # genera dist/ (lo que sirve Caddy/Railway)
```

Abre la pestaña **"Celda 3D"** y opera la HMI: **START → Colocar CAFI** y verás
el ciclo completo (disco a WORK, remachado, regreso a HOME) reflejado en la
escena, las lámparas y el contrato.

## 10. Cómo correr el mock (sin hardware)

```bash
cd raspberry_turntable_gateway
TURNTABLE_MOCK=1 python raspberry_turntable_mock_test.py     # lógica en consola
# o el gateway entero en mock:
TURNTABLE_MOCK=1 uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```
(En Windows PowerShell: `$env:TURNTABLE_MOCK=1; python …`)

## 11. Cómo correr el Raspberry gateway (hardware real)

```bash
cd raspberry_turntable_gateway
pip install -r requirements.txt
cp raspberry_turntable_env_example.env .env     # ajusta pines / STEPS_180
python raspberry_turntable_limit_switch_test.py # valida switches (no mueve motor)
python raspberry_turntable_stepper_test.py      # valida motor (pocos pasos)
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

## 12. Cómo conectar web ↔ Raspberry

1. Pestaña **"Cobot en Vivo"** → panel **"Mesa Rotatoria · Raspberry"**.
2. URL del gateway:
   - LAN: `ws://<IP-RPi>:8000/ws/turntable`
   - HTTPS/Railway: publica el puerto 8000 por el **mismo túnel ngrok** del
     cobot → `wss://<dominio>.ngrok-free.dev/ws/turntable`.
3. **CONECTAR** → el disco 3D gira con `angle_deg` real.
4. **START CYCLE** → `POST /api/turntable/start-cycle` arranca el ciclo en la RPi.

> La web en HTTPS (Railway) no puede abrir `ws://` a una IP LAN
> (mixed-content): para producción usa `wss://` por ngrok, igual que el cobot.

## 13. Qué queda pendiente

- **Calibrar `STEPS_180`** en hardware (referencia 185; depende de
  microstepping/reductora) con `raspberry_turntable_stepper_test.py`.
- **Actuador de remachado real** (hoy es un dwell simulado).
- **Sin encoder (open-loop):** `angle_deg` es estimado; el límite físico es la
  verdad de posición. A futuro, sensor de home/endstop redundante.
- **Unificar Cobot en Vivo** (fase siguiente): si se desea, mover toda la
  experiencia o compartir más estado entre cobot y mesa.
- **Publicar el gateway por el túnel ngrok** existente para demo remota.

## 14. Comandos de push usados

```bash
cd SchneiderProjectWeb_DigitalTwin_Sandbox
git checkout -b feature/raspberry-turntable-hmi
git add -A
git commit -m "feat(turntable+hmi): HMI V62 + simulación de mesa en Celda 3D, mesa en vivo en Cobot en Vivo, gateway Raspberry"
git push -u origin feature/raspberry-turntable-hmi
```

> Si el push falla por credenciales/entorno, ejecuta los mismos comandos desde
> tu máquina (la branch y el commit ya quedan locales en el repo destino).
