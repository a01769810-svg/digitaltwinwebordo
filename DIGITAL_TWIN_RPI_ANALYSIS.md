# DIGITAL_TWIN_RPI_ANALYSIS.md

**Análisis de integración — Mesa rotatoria física (Raspberry Pi 4) → Digital Twin web**
Fecha: 2026-05-27 · Alcance de esta etapa: **SOLO la mesa rotatoria (turntable)**
Estado: **análisis, sin implementar, sin commits, sin tocar lógica.**

Se clonaron y revisaron los dos repos:
- `Quique2/RaspberryPiGIT` (Raspberry)
- `Quique2/SchneiderProjectWeb_DigitalTwin` (web / digital twin)

> Buena noticia de entrada: **gran parte de la arquitectura que propones ya existe.**
> El repo Raspberry ya tiene un backend FastAPI con WebSocket + REST + modo demo,
> y la web ya tiene un cliente WebSocket completo y una mesa 3D rotable por un
> único valor de ángulo. La integración de la mesa es, en su mayoría, **replicar
> patrones que ya están probados con el cobot**, no inventar desde cero.

---

## 1. Qué encontré en el repo `RaspberryPiGIT`

Archivos (todos en la raíz, sin estructura de paquetes/carpetas):

| Archivo | Qué es |
|---|---|
| `backend.py` | **Servidor FastAPI ya funcional** para el cobot. Expone `WS /ws/cobot` (stream 100 ms), `GET /api/cobot/state`, `GET /health`. Tiene modo demo, CORS abierto, loop de polling en background y broadcaster multi-suscriptor. **Es la plantilla exacta para la mesa.** |
| `cobot_reader.py` | Lector Modbus TCP del cobot (no relevante para la mesa, pero define el estilo del JSON). |
| `Prueba_con_motor.py` | Control real del NEMA con `RPi.GPIO`. **STEP=GPIO17, DIR=GPIO27**, `STEPS_180 = 185`, `STEP_DELAY = 0.005`. Loop infinito a nivel de módulo, bloqueante. |
| `prueba_stepper_led.py` | Variante con `gpiozero` (STEP/DIR como `LED`), también STEP=17/DIR=27, loop infinito. |
| `LED blink.py` | Prueba básica de GPIO. |
| `modbus_check.py`, `network_scanner.py`, `network_scanner_arp.py` | Utilidades de red/Modbus, no relevantes para la mesa. |
| `start_gateway.sh` | Arranca `uvicorn backend:app` en `:8000` **+ túnel ngrok con dominio estático** `unmoral-shrink-cavalry.ngrok-free.dev`. Verifica `/health` antes de abrir el túnel. |
| `CONTEXT_DIGITAL_TWIN.md` | Documento de contexto (red, Modbus, arquitectura objetivo, dependencias). |
| `INSTALACION_RASP_DIGITAL_TWIN.md` | Guía de instalación; **lista todas las dependencias ya instaladas** y un pinout (ver §12, conflicto). |
| `package.json` | Solo `node-opcua` (legado OPC-UA, irrelevante para la mesa). |
| `.gitignore` | Ignora `*.json` (excepto `package.json`), `*.pem`, `*.log`, `__pycache__/`, `schneider-rpi-control/`. |

**Respuestas directas:**
- ¿Ya hay servidor? **Sí**, FastAPI (`backend.py`).
- ¿Ya hay WebSocket/API? **Sí**, `/ws/cobot` + REST, con modo demo y CORS.
- ¿Ya hay control GPIO? **Sí**, pero como *scripts de prueba sueltos* (no como módulo seguro): `RPi.GPIO` y `gpiozero`, ambos con loop infinito que **mueve el motor al ejecutar el archivo**.
- ¿Hay `.env`? **No.** No existe `.env`, `.env.example` ni archivo de config. Todo está hardcodeado.

---

## 2. Qué encontré en el repo `SchneiderProjectWeb_DigitalTwin`

App **Expo / React Native Web** que se exporta a web estática.

| Área | Qué hay |
|---|---|
| `App.tsx` | Shell con 4 pestañas: **Inicio, Cableado, Celda 3D, Cobot en Vivo**. |
| `components/CellViewer3D.tsx` | **Escena 3D principal de la celda (V53/V60)**, ~3170 líneas. Contiene la mesa rotatoria, el cobot, CAFI, fixtures, conveyor, etc. Carga URDFs y reproduce el ciclo completo con un `SequencePlayer`. |
| `components/CobotLiveView.tsx` | **Vista "en vivo" del cobot**: cliente WebSocket + fallback a polling HTTP, auto-conexión, fallback a demo. **Es la plantilla exacta del lado web para la mesa.** |
| `components/` (otros) | `HeroSection`, `ArchitectureDiagram`, `SpecsGrid`, `WiringDiagram`, `Footer`. Presentación. |
| `public/urdf/turntable_rivet_cell.urdf` | URDF de la mesa. Joint relevante (ver §4). |
| `public/meshes/v53/turntable/*` | Mallas STL del disco, fixtures, NEMA, rodamientos. |
| `dist/` | Build ya commiteado (Expo export + meshes). |
| `Dockerfile`, `Caddyfile`, `railway.toml` | **Despliegue: Railway** sirve `dist/` con **Caddy** sobre HTTPS (`:{$PORT}`, CORS abierto). |
| `app.json`, `babel.config.js`, `metro.config.js`, `tsconfig.json` | Config Expo/Metro/TS. |

**Respuestas directas:**
- ¿Escena 3D clara para la mesa? **Sí**, en `CellViewer3D.tsx`.
- ¿Three.js o React Three Fiber? **Ambos**: React Three Fiber (`@react-three/fiber` + `@react-three/drei`) sobre `three`, y `urdf-loader` para los URDF.
- ¿Cliente WebSocket? **Sí**, en `CobotLiveView.tsx` (no en `CellViewer3D.tsx` todavía).
- ¿Modo mock? **Sí**, `CobotLiveView` cae a un snapshot DEMO si no hay endpoint; `CellViewer3D` corre una animación pre-programada (no datos en vivo).

---

## 3. Framework de la web

- **Expo `~52.0.46`** + **React Native Web `~0.19.13`** + **React 18.3.1** (TypeScript 5.3).
- **3D:** `@react-three/fiber ^8.17`, `@react-three/drei ^9.117`, `three ^0.170`, `urdf-loader ^0.12`.
- Salida: **web estática** (`expo export --platform web` → `dist/`), servida por **Caddy** en **Railway** (HTTPS).
- No es Next.js ni Vite: es el bundler **Metro** de Expo.

**Implicación crítica de despliegue:** la web en producción corre en **HTTPS**. Un navegador en una página HTTPS **no puede abrir `ws://` ni `http://` planos** hacia una IP LAN (mixed-content bloqueado). Por eso el cobot ya usa **`wss://` vía el túnel ngrok estático**. La mesa **debe** salir por el mismo camino seguro (ver §7).

---

## 4. Cómo está representada la mesa rotatoria y cómo se actualiza el ángulo

En `CellViewer3D.tsx`:

- El componente `Turntable` (≈ línea 776) carga `/urdf/turntable_rivet_cell.urdf` y, en cada frame:
  ```ts
  robot.setJointValue('table_rotation_joint', angleRef.current);
  ```
- El ángulo vive en **un solo ref**: `const discAngleRef = useRef(0);` (≈ línea 2727), **en radianes**.
- Se pasa al componente: `<Turntable angleRef={discAngleRef} ... />` (≈ línea 3081).
- El **`SequencePlayer`** (≈ línea 708) anima ese ref durante el ciclo demo: `{ kind: 'disc', target: Math.PI, duration: 2.5 }` (gira 180° para remachar) y luego `target: 0.0` (regresa).
- El **HMI** muestra el ángulo en grados: `(discAngleRef.current * 180 / Math.PI).toFixed(1)°` (≈ línea 2512) y tiene `setDiscAngle(a)` (≈ línea 2954).

URDF (`turntable_rivet_cell.urdf`, línea 146):
```xml
<joint name="table_rotation_joint" type="revolute">
  <axis xyz="0 0 1"/>
  <limit lower="-3.141593" upper="3.141593" effort="30" velocity="0.60"/>
</joint>
```
→ **Eje +Z, rango [-180°, +180°].** `position A = 0°` y `position B = 180°` (= `Math.PI`, justo en el límite superior). Encaja perfecto con tu contrato.

**Cómo actualizaría `angle_deg` visualmente:** escribir en un ref (en radianes) que el componente `Turntable` lea cada frame. Es exactamente lo que ya hace el `SequencePlayer`; el cliente WebSocket simplemente sería **otra fuente** que escribe ese ref:
```ts
angleRef.current = telemetry.turntable.angle_deg * Math.PI / 180;
```
Para que se vea suave (no a saltos), conviene *easing* hacia un `targetRef`, igual que `CobotLiveView` suaviza los joints del cobot con `liveRef += (target - live) * k`.

---

## 5. Archivos importantes (mapa para la fase de implementación)

**Raspberry (`RaspberryPiGIT/`):**
- `backend.py` ← plantilla del servidor (copiar patrón WS/REST/demo/broadcaster).
- `Prueba_con_motor.py` ← lógica física de referencia (pines, STEP/DIR, conversión grados↔pasos).
- `start_gateway.sh` ← cómo se publica todo (uvicorn + ngrok). **La mesa debe pasar por aquí.**

**Web (`SchneiderProjectWeb_DigitalTwin/`):**
- `components/CobotLiveView.tsx` ← plantilla del cliente WebSocket (auto-connect, fallback demo, polling, manejo de mixed-content).
- `components/CellViewer3D.tsx` ← dónde vive `discAngleRef` y el componente `Turntable` (el punto donde inyectar el ángulo en vivo).
- `App.tsx` ← dónde se registran las pestañas (si se quisiera una vista "Mesa en Vivo" dedicada).

---

## 6. Dónde debería vivir el código de control de la mesa en Raspberry

**Propuesta:** un módulo nuevo y aislado, p. ej. `turntable_controller.py`, que:
- Encapsule STEP/DIR y la conversión grados↔pasos en una clase (`TurntableController`).
- **NO mueva el motor al importarse** (nada de `while True` a nivel de módulo; el código actual de prueba sí lo hace y eso hay que evitarlo).
- Lea pines y parámetros desde **`.env`** (`STEP_PIN`, `DIR_PIN`, `STEPS_180`, `STEP_DELAY`).
- Haga `GPIO.cleanup()` (o equivalente `gpiozero`) en un cierre ordenado.
- Tenga **modo mock** (sin GPIO) para correr en una laptop sin hardware.
- Exponga métodos no bloqueantes/ejecutables en hilo: `index(direction)`, `state()`, y un callback de progreso para emitir frames `MOVING`.

Los scripts `Prueba_con_motor.py` / `prueba_stepper_led.py` se quedan como **referencia/manuales**, no se borran ni se "promueven" tal cual (siguen teniendo loop infinito).

---

## 7. Dónde debería vivir el WebSocket/API de la mesa en Raspberry

**Recomendación: extender el MISMO `backend.py` (misma app FastAPI, mismo puerto 8000), no crear un servidor aparte.**

Motivo decisivo: el túnel **ngrok estático ya existente** (`unmoral-shrink-cavalry.ngrok-free.dev`) apunta a `localhost:8000`. Si la mesa vive en la misma app, **queda publicada por `wss://` automáticamente, sin segundo túnel, sin segundo dominio, sin tocar `start_gateway.sh`.** Un servidor separado en otro puerto necesitaría otro túnel (ngrok free solo da un dominio estático) → fricción innecesaria.

Endpoints a añadir a `backend.py`:
```
WS   /ws/turntable          → stream del estado de la mesa
GET  /api/turntable/state   → snapshot REST (fallback / debug)
POST /api/turntable/index   → girar 180° (A↔B)        [fase 5]
POST /api/turntable/home    → ir a posición A (0°)     [fase 5, si aplica]
```
`/health` ya existe y puede ampliarse para reportar también el estado de la mesa.

**Diferencia clave de modelo vs. el cobot:** el cobot es *poll-driven* (lee Modbus cada 100 ms en un loop). La mesa es **command-driven** (se mueve cuando se le pide). Por eso necesita:
- un `TurntableState` + broadcaster (igual patrón que `CobotState`), y
- ejecutar el movimiento del stepper en un **hilo worker** (`asyncio.to_thread` / `run_in_executor`) para **no bloquear el event loop** mientras dura el giro (~0.8–1.9 s), publicando frames `MOVING` desde el hilo vía `loop.call_soon_threadsafe`.

---

## 8. Dónde debería conectarse la web al WebSocket

Dos opciones (recomiendo la A para empezar):

**Opción A — Inyectar en `CellViewer3D.tsx` (mesa de la celda real):**
- Añadir un pequeño hook/cliente WS (copiado de `CobotLiveView`) que, al recibir estado, escriba `discAngleRef.current` (o un `liveAngleRef` con easing).
- Añadir un toggle tipo "◉ Mesa sigue datos en vivo / ◯ Mesa en demo" para no pelear con el `SequencePlayer`.
- URL por defecto: `wss://unmoral-shrink-cavalry.ngrok-free.dev/ws/turntable`.

**Opción B — Nueva pestaña "Mesa en Vivo"** en `App.tsx` (análoga a "Cobot en Vivo"), con su propia escena mínima (solo el URDF de la mesa) + panel de estado A/B/MOVING. Más limpio para demo, pero duplica setup 3D.

En ambos casos el patrón de conexión es el ya probado en `CobotLiveView`: WebSocket primario, fallback a polling HTTP, auto-conexión al montar, fallback silencioso a demo si el gateway no responde, y `ngrok-skip-browser-warning` en las peticiones REST.

---

## 9. Cómo debería verse el JSON de estado (contrato propuesto)

Tu propuesta es buena. La afino para alinearla con el estilo del cobot (envelope con `timestamp`/`ok`/`_demo`) y para respetar el rango del URDF:

```json
{
  "timestamp": "2026-05-27T21:00:00.000Z",
  "ok": true,
  "_demo": false,
  "turntable": {
    "angle_deg": 0,
    "position": "A",
    "moving": false,
    "last_direction": "CW",
    "steps_180": 80,
    "target_deg": 0,
    "progress": 1.0
  }
}
```

Durante el movimiento:
```json
{
  "timestamp": "2026-05-27T21:00:01.250Z",
  "ok": true,
  "_demo": false,
  "turntable": {
    "angle_deg": 90,
    "position": "MOVING",
    "moving": true,
    "last_direction": "CW",
    "steps_180": 80,
    "target_deg": 180,
    "progress": 0.5
  }
}
```

Notas del contrato:
- **`angle_deg` normalizado a [-180, 180]** (el joint URDF no acepta más; `B = 180°` cae justo en el límite). Si más adelante hay multivuelta, lo discutimos aparte.
- `position`: `"A"` (0°), `"B"` (180°) o `"MOVING"`.
- `_demo: true` cuando el backend corre **sin GPIO** (mock) — mismo significado que en el cobot, así la web puede mostrar "GATEWAY OK · motor en mock".
- `progress`, `target_deg`: opcionales pero ayudan a que la web anime suave aunque la mesa real no reporte ángulos intermedios reales (el stepper es open-loop: no hay encoder, el ángulo es **estimado** por pasos).
- **Mensaje propio en `/ws/turntable`** (no mezclar con el JSON del cobot): mantiene ambos streams desacoplados.

---

## 10. Dependencias que harían falta en Raspberry

**Ninguna nueva.** Según `INSTALACION_RASP_DIGITAL_TWIN.md` ya están instaladas en la RPi:
`fastapi`, `uvicorn[standard]`, `websockets`, `pydantic`, **`python-dotenv`** (para `.env`), y para GPIO: `gpiozero`, `lgpio`, `rpi-lgpio`, `pigpio`.

Observación: el script actual importa `RPi.GPIO`. En Raspberry Pi OS reciente (Pi 4, kernel nuevo) ese paquete se resuelve normalmente vía el shim **`rpi-lgpio`** (ya instalado). Para el módulo seguro conviene **`gpiozero` o `lgpio`** directamente (más robusto en Pi 4/5). A confirmar en hardware en fase 5.

---

## 11. Dependencias que harían falta en web

**Ninguna nueva.** Ya están `@react-three/fiber`, `@react-three/drei`, `three`, `urdf-loader`. El cliente WebSocket usa la API nativa `WebSocket` del navegador (sin librería). Reutilizamos el patrón de `CobotLiveView.tsx`.

---

## 12. Riesgos

1. **Conflicto de pinout (importante).** El código real (`Prueba_con_motor.py`, `prueba_stepper_led.py`) y tu referencia usan **STEP=17 / DIR=27**. Pero `INSTALACION_RASP_DIGITAL_TWIN.md` y la skill `stepper-nema-control` documentan **STEP=18 / DIR=23**. **Tomo 17/27 como verdad** (tu instrucción), pero hay docs que dicen otra cosa → reconciliar y dejar el valor real solo en `.env`.
2. **Conflicto de `STEPS_180`.** Tu referencia dice `80`; `Prueba_con_motor.py` dice `185`. El valor real depende de microstepping/reductora y **debe medirse en hardware**. Por eso va en `.env` y la web no debe asumir un valor fijo (lo recibe en el JSON).
3. **Bloqueo del event loop.** El giro del stepper es un loop de `sleep` (~0.8–1.9 s). Si se ejecuta en el hilo de asyncio, **congela el WebSocket** (y todos los clientes). Debe correr en hilo worker.
4. **Mixed-content (HTTPS↔ws).** La web en Railway es HTTPS; no puede abrir `ws://IP-LAN`. Obliga a salir por `wss://` (ngrok) o correr la web local. Ya resuelto para el cobot; la mesa debe reutilizar el mismo túnel.
5. **Open-loop / sin encoder.** El NEMA no reporta posición real. El `angle_deg` es **estimado**. Si se pierden pasos (par insuficiente, choque), web y realidad divergen sin que nadie lo note. A futuro: sensor de home / endstop.
6. **ngrok free.** Un solo dominio estático y límites de sesión; si el túnel se cae, la web cae a demo (ya manejado), pero la mesa real queda incomunicada.
7. **CORS abierto (`*`).** Aceptable para demo; anotarlo como deuda si esto sale del entorno de feria.
8. **Concurrencia de comandos.** Si llegan dos `index` solapados (o durante un `MOVING`), hay que serializar (lock / rechazar) para no mandar STEP/DIR inconsistentes al driver.

---

## 13. Qué NO debemos hacer

- **No mover el motor al importar** un módulo (el patrón actual de `while True` a nivel de archivo es justo lo que hay que evitar en el módulo de producción).
- **No** correr el giro del stepper en el event loop de FastAPI (bloquea el WS).
- **No** dejar que la web controle el GPIO directamente: la web manda *intención* (`/index`), la RPi decide y ejecuta con lógica segura.
- **No** hardcodear pines/pasos en el código de producción → `.env`.
- **No** cambiar los pines 17/27 sin avisar.
- **No** poner safety crítico en la RPi (sigue siendo el PLC; la RPi es controlador auxiliar).
- **No** crear un segundo servidor/segundo túnel para la mesa (usar la misma app + mismo ngrok).
- **No** romper la pestaña "Cobot en Vivo" ni el `SequencePlayer` de la celda (la fuente "en vivo" debe ser opt-in/toggle, no reemplazar el demo).
- **No** commitear, no mover archivos, no instalar nada **todavía**.

---

## 14. Plan de implementación en fases (propuesta, sin ejecutar)

**FASE 1 — Análisis y contrato (ESTE documento).**
- Analizar ambos repos ✓, documentar arquitectura ✓, fijar el contrato JSON de `/ws/turntable` ✓.
- *Entregable:* este `DIGITAL_TWIN_RPI_ANALYSIS.md`. **Esperar tu visto bueno.**

**FASE 2 — Módulo seguro de mesa en Raspberry (sin servidor, sin web).**
- `turntable_controller.py`: clase `TurntableController` con STEP/DIR encapsulados, `.env`, **sin movimiento en import**, cleanup ordenado, **modo mock**, métodos `index()` / `state()` + callback de progreso.
- `.env.example` con `STEP_PIN=17 DIR_PIN=27 STEPS_180=80 STEP_DELAY=0.005`.
- Prueba en aislamiento (mock primero, luego con motor manualmente).

**FASE 3 — WebSocket/API de la mesa en Raspberry (con mock).**
- Extender `backend.py`: `TurntableState` + broadcaster, `WS /ws/turntable`, `GET /api/turntable/state`, ampliar `/health`.
- Movimiento en **hilo worker**; emitir frames `A`/`MOVING`/`B`.
- Correr todo en **mock** (sin tocar el motor) y validar el JSON con un cliente de prueba.

**FASE 4 — Conectar la web (visual, aún con mock en la RPi).**
- En `CellViewer3D.tsx`: cliente WS (patrón `CobotLiveView`) que escribe `discAngleRef` con easing + toggle "en vivo / demo".
- Validar que `A→B→A` se ve suave y que `position` se refleja en el HMI.
- Default URL: `wss://unmoral-shrink-cavalry.ngrok-free.dev/ws/turntable`.

**FASE 5 — Control real del NEMA.**
- Quitar el flag mock; `TurntableController` mueve el motor físico.
- Calibrar `STEPS_180` real en hardware. Verificar pines 17/27 y lógica 3.3 V del driver.
- Serializar comandos (lock), validar A/B reales.

**FASE 6 — Estados futuros (fuera del alcance actual).**
- Ampliar el contrato con: fixture A/B ocupado, CAFI presente, remachado en curso, visión, aceptado/rechazado — reaprovechando los sensores/links que ya existen en el URDF y los estados que ya modela el `SequencePlayer`.

---

## Respuestas a tus 10 preguntas

1. **¿El repo Raspberry ya tiene estructura para API/WebSocket?**
   Sí — `backend.py` ya es un FastAPI con WS + REST + demo + CORS + broadcaster. Se extiende, no se crea de cero.

2. **¿El repo web ya tiene una escena 3D clara para la mesa?**
   Sí — `CellViewer3D.tsx`, componente `Turntable` con el URDF `turntable_rivet_cell.urdf`.

3. **¿La web usa Three.js o React Three Fiber?**
   Ambos: React Three Fiber + drei sobre three, con urdf-loader. Dentro de Expo / React Native Web.

4. **¿Dónde está el componente de mesa rotatoria?**
   `components/CellViewer3D.tsx`: `function Turntable(...)` (≈ L776), instanciado en ≈ L3081. El ángulo está en `discAngleRef` (≈ L2727).

5. **¿Cómo actualizarías `angle_deg` visualmente?**
   Escribiendo `angleRef.current = angle_deg * π/180` (con easing hacia un target), que el `Turntable` aplica a `table_rotation_joint` cada frame. Misma mecánica que ya usa el `SequencePlayer`.

6. **¿Conviene WebSocket o HTTP polling?**
   **WebSocket primario** (la mesa empuja `MOVING`/`A`/`B` en cuanto cambian — push, baja latencia), con **HTTP polling como fallback** (igual que el cobot). No es "uno u otro": el patrón actual ya hace ambos.

7. **¿Cómo evitar que el loop del stepper bloquee el servidor?**
   Ejecutar el giro en un **hilo worker** (`asyncio.to_thread`/executor); el event loop sigue libre para el WS. El hilo reporta progreso al estado vía `loop.call_soon_threadsafe`.

8. **¿Cómo harías mock mode?**
   Flag `MOCK` (o autodetección: si falla el import de GPIO → mock, igual que `backend.py` cae a demo si falta `pymodbus`). En mock, `index()` solo simula la rampa de ángulo y marca `_demo: true`. Permite desarrollar en laptop sin hardware.

9. **¿Qué cambiarías primero?**
   El **módulo seguro `turntable_controller.py`** (Fase 2): es lo que desbloquea todo lo demás y es 100% testeable sin web ni motor.

10. **¿Qué NO tocaría todavía?**
    El control real del motor, los scripts de prueba existentes, `start_gateway.sh`, el `SequencePlayer`/pestaña "Cobot en Vivo", los pines, y la simulación ROS (V71, congelada). Nada de commits ni instalaciones.

---

## Reglas de seguridad (checklist que respetará la implementación)

- [x] No mover motor al importar módulos.
- [x] No bucle infinito por default.
- [x] `GPIO.cleanup()` / cierre ordenado siempre.
- [x] Pines y pasos en `.env`, no hardcodeados.
- [x] La RPi **no** controla safety crítico (eso es del PLC).
- [x] El servidor web **no** se bloquea mientras mueve el motor (hilo worker).
- [x] La web manda *intención*; la RPi valida y ejecuta (la web no toca GPIO).

---

## Próximos pasos

1. **Tú revisas este reporte.**
2. Si lo apruebas, arranco **Fase 2** (módulo `turntable_controller.py` seguro, con `.env` y mock) — **solo eso**, sin servidor ni web, sin commits, para que lo valides antes de seguir.
3. Antes de Fase 2 necesito que confirmes 2 cosas: **(a)** pines definitivos `STEP=17 / DIR=27` (hay docs que dicen 18/23), y **(b)** si `STEPS_180` arranca en `80` (tu referencia) o `185` (el otro script) — de todos modos irá a `.env` y se calibrará en hardware.
