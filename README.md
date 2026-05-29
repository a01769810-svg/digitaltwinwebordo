# Schneider Riveting Cell Digital Twin

Web del gemelo digital de la celda Schneider Riveting Cell. Este repo es una
adaptacion del proyecto `Quique2/SchneiderProjectWeb_DigitalTwin` con ideas/HMI
integradas desde `Quique2/SchneiderProjectWeb_Simulation`.

El objetivo actual del repo es mostrar la celda en web, simular la mesa
rotatoria, mostrar una HMI de operador y permitir una vista live conectada al
gateway de Raspberry Pi cuando el hardware este disponible.

## Stack

- Expo / React Native Web.
- React 18 + TypeScript.
- Three.js con `@react-three/fiber`, `@react-three/drei` y `urdf-loader`.
- Assets 3D en `public/` y copia generada en `dist/`.
- Gateway Raspberry en Python/FastAPI dentro de `raspberry_turntable_gateway/`.
- Deploy Railway con `Dockerfile`, `Caddyfile` y `railway.toml`.

## Estructura principal

| Ruta | Uso |
|---|---|
| `App.tsx` | Shell principal y tabs: Inicio, Cableado, Celda 3D, Cobot en Vivo. |
| `components/CellViewer3D.tsx` | Escena 3D principal, cobot, mesa rotatoria visual, HMI embebida y controles de simulacion. |
| `components/OperatorHMI.tsx` | HMI de operador integrada desde V62. |
| `components/turntableSim.ts` | Maquina de estados mock de la mesa rotatoria y contrato JSON compartido. |
| `components/useTurntableSim.ts` | Hook React que corre la simulacion mock y alimenta la Celda 3D. |
| `components/useLiveTurntable.ts` | Cliente live WebSocket/REST para la mesa real via Raspberry. |
| `components/CobotLiveView.tsx` | Vista Cobot en Vivo, incluyendo panel de mesa rotatoria live. |
| `public/` | Assets fuente servidos por Expo: URDF, STL, diagramas. |
| `dist/` | Build web exportado. No borrar si Railway depende de esta carpeta. |
| `raspberry_turntable_gateway/` | Gateway FastAPI, controlador GPIO y pruebas de Raspberry. |
| `Dockerfile`, `Caddyfile`, `railway.toml` | Deploy en Railway. |

Ver tambien `FILES_MAP.md` para una tabla mas directa de "area -> archivo".

## Correr local

```bash
npm install
npm start
```

Expo abrira la app web. Si no abre automaticamente, usa la URL local que imprima
la terminal.

## Build web

```bash
npx tsc --noEmit
npm run build
```

`npm run build` ejecuta `expo export --platform web` y luego
`scripts/patch-dist.js`. El patch copia assets de `public/` hacia `dist/` y
ajusta metadata basica de `dist/index.html`.

## Modo mock

Hay dos mocks distintos:

1. **Mock web de Celda 3D**: la tab `Celda 3D` usa `useTurntableSim.ts` y
   `turntableSim.ts`. No necesita hardware.
2. **Mock del gateway Raspberry**: corre el gateway Python sin GPIO real:

```bash
cd raspberry_turntable_gateway
pip install -r requirements.txt
TURNTABLE_MOCK=1 uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

En Windows PowerShell:

```powershell
cd raspberry_turntable_gateway
pip install -r requirements.txt
$env:TURNTABLE_MOCK=1
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

La URL live para la web seria:

```text
ws://localhost:8000/ws/turntable
```

## Gateway Raspberry

La carpeta `raspberry_turntable_gateway/` contiene el gateway FastAPI, el
controlador GPIO y pruebas. Lee
`raspberry_turntable_gateway/README_RASPBERRY_TURNTABLE.md` antes de mover
hardware.

Resumen rapido:

```bash
cd raspberry_turntable_gateway
cp raspberry_turntable_env_example.env .env
pip install -r requirements.txt
python raspberry_turntable_limit_switch_test.py
python raspberry_turntable_stepper_test.py
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

Pines BCM esperados:

- `STEP`: GPIO17.
- `DIR`: GPIO27.
- `LIMIT_HOME`: GPIO22.
- `LIMIT_WORK`: GPIO23.

Los limits usan pull-up interno: sin presionar = HIGH, presionado = LOW.

## Deploy Railway

Railway debe apuntar al repo:

```text
https://github.com/a01769810-svg/digitaltwinwebordo
```

Branch esperada: `main`.

El deploy usa Docker:

- `Dockerfile` parte de `caddy:2-alpine`.
- Copia `dist/` a `/srv/`.
- `Caddyfile` sirve `/srv` usando el `$PORT` que inyecta Railway.
- `railway.toml` arranca Caddy con ese Caddyfile.

Antes de mergear a `main`, corre:

```bash
npm install
npx tsc --noEmit
npm run build
```

Si Railway se ve viejo, revisa `RAILWAY_DEPLOYMENT.md`.

## Branch y flujo de cambios

Para cambios normales usa una rama feature desde `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/nombre-claro
```

Para este trabajo de documentacion la rama esperada es:

```text
feature/repo-docs-for-claude
```

Ver `DEVELOPMENT_WORKFLOW.md` para el flujo completo de commit, push y PR.

## Validaciones antes de push

Corre siempre:

```bash
npx tsc --noEmit
npm run build
git status
git log --oneline -5
```

Si cambias el gateway Raspberry, valida tambien desde
`raspberry_turntable_gateway/`:

```bash
python raspberry_turntable_mock_test.py
python raspberry_turntable_limit_switch_test.py
```

`raspberry_turntable_stepper_test.py` mueve el motor; usalo solo con hardware
seguro y supervisado.

## Cosas que NO se deben tocar sin confirmar

- No borrar `dist/` si Railway depende de los assets generados.
- No borrar `raspberry_turntable_gateway/`.
- No cambiar pines GPIO sin confirmar con hardware.
- No cambiar el contrato JSON de `turntableSim.ts` / gateway sin confirmar.
- No redisenar la UI ni reescribir la escena 3D para cambios de documentacion.
- No mover STL/URDF grandes sin una razon clara.
- No agregar dependencias nuevas salvo que sean estrictamente necesarias.
