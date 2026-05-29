# Development Workflow

Flujo recomendado para que Claude o cualquier colaborador trabaje sin romper
`main`.

## 1. Crear rama desde main

```bash
git checkout main
git pull origin main
git checkout -b feature/nombre-claro
```

Usa nombres claros, por ejemplo:

```bash
git checkout -b feature/fix-live-turntable-url
git checkout -b feature/operator-hmi-status
git checkout -b docs/raspberry-gateway-notes
```

Para este paquete de documentacion:

```bash
git checkout -b feature/repo-docs-for-claude
```

## 2. Instalar y correr local

```bash
npm install
npm start
```

Revisa en navegador las tabs afectadas:

- `Inicio` si cambias shell o contenido general.
- `Cableado` si cambias wiring.
- `Celda 3D` si cambias escena, HMI o simulacion mock.
- `Cobot en Vivo` si cambias live data, cobot live o Raspberry.

## 3. Validar TypeScript y build

```bash
npx tsc --noEmit
npm run build
```

`npm run build` actualiza `dist/` con `expo export --platform web` y
`scripts/patch-dist.js`.

## 4. Revisar cambios antes de commit

```bash
git status
git diff
```

Si el repo tiene cambios no relacionados, no uses `git add -A` a ciegas. Agrega
solo los archivos del trabajo actual.

Ejemplo para documentacion:

```bash
git add README.md CLAUDE_CONTEXT.md DEVELOPMENT_WORKFLOW.md RAILWAY_DEPLOYMENT.md FILES_MAP.md raspberry_turntable_gateway/README_RASPBERRY_TURNTABLE.md
```

Ejemplo para un cambio de HMI:

```bash
git add components/OperatorHMI.tsx
```

## 5. Commit

```bash
git commit -m "docs: add Claude workflow and deployment context"
```

Usa mensajes cortos y especificos:

- `fix: correct live turntable fallback`
- `feat: add operator HMI status row`
- `docs: update Raspberry gateway notes`
- `build: refresh web dist`

## 6. Push de rama

```bash
git push -u origin feature/nombre-claro
```

Para este trabajo:

```bash
git push -u origin feature/repo-docs-for-claude
```

## 7. Abrir PR hacia main

Opcion GitHub CLI:

```bash
gh pr create --base main --head feature/nombre-claro --title "docs: add Claude workflow and deployment context" --body "Adds repo documentation, Claude context, development workflow, Railway deployment notes, and file map."
```

Opcion web:

1. Abre el repo en GitHub.
2. Crea Pull Request desde `feature/nombre-claro` hacia `main`.
3. Pega resumen de cambios y validaciones.
4. Espera review o mergea si tienes permiso.

## 8. Merge a main

Merge recomendado via PR. Despues de mergear:

```bash
git checkout main
git pull origin main
git branch -d feature/nombre-claro
```

Si el deploy Railway no se actualiza, revisa `RAILWAY_DEPLOYMENT.md`.

## Checklist antes de push

- `npm install` termino sin errores.
- `npx tsc --noEmit` pasa.
- `npm run build` pasa.
- `git status` solo contiene archivos esperados.
- No se cambio contrato JSON sin confirmacion.
- No se cambiaron pines GPIO sin confirmacion.
- No se borro `dist/`.
- No se agregaron dependencias innecesarias.
