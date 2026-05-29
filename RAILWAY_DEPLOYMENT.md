# Railway Deployment

Este repo despliega la web estatica del Digital Twin en Railway usando Docker y
Caddy.

## Repo y branch esperados

Railway debe apuntar a:

```text
https://github.com/a01769810-svg/digitaltwinwebordo
```

Branch esperada:

```text
main
```

## Build esperado

Antes de que `main` tenga cambios web nuevos, genera build local:

```bash
npm install
npx tsc --noEmit
npm run build
```

`npm run build` hace:

```bash
expo export --platform web
node scripts/patch-dist.js
```

El resultado importante es `dist/`.

## Como sirve la app

Archivos relevantes:

- `Dockerfile`
- `Caddyfile`
- `railway.toml`

Flujo:

1. `Dockerfile` usa `caddy:2-alpine`.
2. Copia `dist/` a `/srv/`.
3. Copia `Caddyfile` a `/etc/caddy/Caddyfile`.
4. Railway inyecta `$PORT`.
5. `Caddyfile` sirve `/srv` y hace fallback de rutas a `/index.html`.

Esto significa que Railway sirve lo que exista en `dist/` dentro del commit que
esta desplegando.

## Si Railway se ve viejo

Revisa en este orden:

1. Confirma que Railway esta conectado al repo correcto:
   `a01769810-svg/digitaltwinwebordo`.
2. Confirma que Railway despliega branch `main`.
3. Confirma que el commit esperado ya esta en `main`.
4. Confirma que `dist/` fue actualizado en el commit si el deploy depende de
   assets versionados.
5. En Railway, usa `Redeploy latest commit`.
6. Si Railway no detecta cambios, fuerza un commit vacio:

```bash
git checkout main
git pull origin main
git commit --allow-empty -m "chore: trigger Railway redeploy"
git push origin main
```

## Diagnostico rapido

Comandos utiles:

```bash
git log --oneline -5
git status
npm run build
```

Revisa que exista:

```text
dist/index.html
```

Si Railway arranca pero muestra 404 o pantalla vieja:

- Verifica que `Dockerfile` copie `dist/`.
- Verifica que `Caddyfile` tenga `root * /srv`.
- Verifica que el deploy use el ultimo commit de `main`.
- Verifica que no estes viendo una cache vieja del navegador.

## Limpiar cache del navegador

Opciones:

- Hard refresh: `Ctrl+Shift+R` en Windows/Linux o `Cmd+Shift+R` en macOS.
- Abrir en ventana incognito.
- Agregar query temporal a la URL, por ejemplo `?v=latest`.
- En DevTools, pestaña Network, activar `Disable cache` y recargar.

## Que no cambiar sin razon

- No cambies `Dockerfile` si solo cambias UI o docs.
- No cambies `Caddyfile` si solo necesitas refrescar deploy.
- No borres `dist/` si Railway esta sirviendo assets versionados desde el repo.
- No cambies branch de Railway sin confirmar con el dueno del repo.
