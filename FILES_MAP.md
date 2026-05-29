# Files Map

| Area | Archivo | Funcion |
|---|---|---|
| App shell | `App.tsx` | Tabs principales y layout global. |
| Inicio | `components/HeroSection.tsx` | Hero/portada de la app. |
| Arquitectura | `components/ArchitectureDiagram.tsx` | Seccion visual de arquitectura. |
| Specs | `components/SpecsGrid.tsx` | Tabla/grid de especificaciones. |
| Cableado | `components/WiringDiagram.tsx` | Vista de cableado. |
| Celda 3D | `components/CellViewer3D.tsx` | Escena principal, cobot, mesa, fixtures, HMI panel y controles. |
| HMI | `components/OperatorHMI.tsx` | HMI V62 portada e indicadores DI/DO. |
| Sim mesa | `components/turntableSim.ts` | Maquina de estados y contrato JSON mock de mesa rotatoria. |
| Hook sim | `components/useTurntableSim.ts` | Estado mock en Celda 3D y escritura de angulo del disco. |
| Live mesa | `components/useLiveTurntable.ts` | Cliente WebSocket/REST live para Raspberry. |
| Cobot vivo | `components/CobotLiveView.tsx` | Vista live del cobot y panel live de mesa. |
| Assets fuente | `public/meshes/`, `public/urdf/` | STL/URDF usados por la app. |
| Assets build | `dist/meshes/`, `dist/urdf/` | Copia exportada para deploy. |
| Script build | `scripts/patch-dist.js` | Ajusta `dist/index.html` y copia assets publicos a `dist/`. |
| Raspberry gateway | `raspberry_turntable_gateway/raspberry_turntable_fastapi_gateway.py` | API FastAPI + WebSocket para mesa real/mock. |
| Raspberry GPIO | `raspberry_turntable_gateway/raspberry_turntable_gpio_controller.py` | Control GPIO STEP/DIR, limits y ciclo. |
| Raspberry limits | `raspberry_turntable_gateway/raspberry_turntable_limit_switch_test.py` | Prueba limit switches sin mover motor. |
| Raspberry stepper | `raspberry_turntable_gateway/raspberry_turntable_stepper_test.py` | Prueba motor paso a paso; mueve hardware. |
| Raspberry mock | `raspberry_turntable_gateway/raspberry_turntable_mock_test.py` | Prueba ciclo completo en mock. |
| Raspberry config | `raspberry_turntable_gateway/raspberry_turntable_env_example.env` | Ejemplo de `.env` con pines y tiempos. |
| Deploy | `Dockerfile` | Imagen Caddy que copia `dist/` a `/srv/`. |
| Deploy | `Caddyfile` | Servidor estatico con fallback a `index.html`. |
| Deploy | `railway.toml` | Configuracion de Railway. |
