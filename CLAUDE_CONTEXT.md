# Claude Context

Este archivo esta escrito para que Claude u otro agente pueda entrar al repo y
trabajar sin perderse.

## Resumen corto

Este repo es la web del Digital Twin de la celda Schneider Riveting Cell. Usa
Expo / React Native Web y Three.js. La app tiene tabs principales en `App.tsx`,
una escena 3D en `components/CellViewer3D.tsx`, una HMI de operador en
`components/OperatorHMI.tsx`, simulacion mock de mesa rotatoria y una vista
`Cobot en Vivo` que puede conectarse a datos live de Raspberry.

## Estado actual

- La web corre con Expo web.
- La tab `Celda 3D` usa simulacion mock local para la mesa rotatoria.
- La HMI V62 esta integrada en `components/OperatorHMI.tsx`.
- La vista `Cobot en Vivo` esta en `components/CobotLiveView.tsx`.
- El cliente live de mesa esta en `components/useLiveTurntable.ts`.
- El contrato JSON base esta en `components/turntableSim.ts`.
- El gateway Raspberry esta en `raspberry_turntable_gateway/`.
- Railway sirve `dist/` con Caddy.

## Reglas para modificar el repo

- Haz cambios pequenos y enfocados.
- No reescribas el proyecto si solo te piden arreglar una parte.
- No borres `dist/` ni `raspberry_turntable_gateway/`.
- No cambies pines GPIO sin confirmacion.
- No cambies el contrato JSON de la mesa sin confirmacion.
- No cambies la logica funcional durante tareas de documentacion.
- No agregues dependencias nuevas si puedes resolver con lo que ya existe.
- Si tocas UI, valida en web y revisa que no rompa mobile/desktop.
- Si tocas `CellViewer3D.tsx`, ten cuidado: es grande y concentra escena,
  cobot, IK, mesa, HMI panel y controles.

## Mapa de archivos importantes

| Necesitas cambiar... | Archivo |
|---|---|
| Tabs o shell principal | `App.tsx` |
| HMI de operador | `components/OperatorHMI.tsx` |
| Escena 3D principal | `components/CellViewer3D.tsx` |
| Mesa rotatoria simulada | `components/turntableSim.ts` |
| Hook de simulacion en Celda 3D | `components/useTurntableSim.ts` |
| Datos live de mesa Raspberry | `components/useLiveTurntable.ts` |
| Vista Cobot en Vivo | `components/CobotLiveView.tsx` |
| Assets URDF/STL fuente | `public/urdf/`, `public/meshes/` |
| Build exportado | `dist/` |
| Gateway Raspberry | `raspberry_turntable_gateway/` |
| Deploy Railway | `Dockerfile`, `Caddyfile`, `railway.toml` |

## Que ya funciona

- Shell con tabs: Inicio, Cableado, Celda 3D, Cobot en Vivo.
- Escena 3D con URDF/STL.
- Simulacion mock de ciclo de mesa rotatoria.
- HMI conectada al snapshot de simulacion.
- Cliente live con WebSocket y fallback REST para mesa Raspberry.
- Gateway Raspberry con modo mock y endpoints REST/WebSocket.
- Build web hacia `dist/`.
- Configuracion Railway para servir `dist/` con Caddy.

## Pendiente o delicado

- Confirmar URL live definitiva del gateway Raspberry/ngrok.
- Validar hardware real antes de confiar en `STEPS_180`.
- Confirmar si Railway hace build previo o si se espera `dist/` versionado.
- Si se cambia el contrato JSON, actualizar web y gateway juntos.
- Si se agregan assets 3D nuevos, confirmar que `scripts/patch-dist.js` los copia
  correctamente a `dist/`.

## Como validar cambios

Siempre corre:

```bash
npm install
npx tsc --noEmit
npm run build
```

Para ver la app:

```bash
npm start
```

Para gateway Raspberry mock:

```bash
cd raspberry_turntable_gateway
pip install -r requirements.txt
TURNTABLE_MOCK=1 python raspberry_turntable_mock_test.py
TURNTABLE_MOCK=1 uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

En PowerShell:

```powershell
cd raspberry_turntable_gateway
pip install -r requirements.txt
$env:TURNTABLE_MOCK=1
python raspberry_turntable_mock_test.py
uvicorn raspberry_turntable_fastapi_gateway:app --host 0.0.0.0 --port 8000
```

## Como evitar romper deploy

- No elimines `dist/`.
- Si cambias codigo web, corre `npm run build` y revisa que `dist/index.html`
  exista.
- No cambies `Dockerfile`, `Caddyfile` o `railway.toml` salvo que el objetivo sea
  deploy.
- Recuerda que Railway sirve `/srv`, que viene de `dist/`.
- Si Railway muestra una version vieja, revisa `RAILWAY_DEPLOYMENT.md`.

## Como hacer push

Flujo esperado:

```bash
git checkout main
git pull origin main
git checkout -b feature/nombre-claro
npm install
npm start
npx tsc --noEmit
npm run build
git status
git add README.md CLAUDE_CONTEXT.md DEVELOPMENT_WORKFLOW.md RAILWAY_DEPLOYMENT.md FILES_MAP.md raspberry_turntable_gateway/README_RASPBERRY_TURNTABLE.md
git commit -m "docs: add Claude workflow and deployment context"
git push -u origin feature/nombre-claro
```

Despues abre PR hacia `main`. No pushees directo a `main` salvo que el dueno del
repo lo pida explicitamente.
