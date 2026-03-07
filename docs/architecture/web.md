# Web Architecture

## Stack

- Framework: Vue 3 + TypeScript
- Build tool: Vite
- UI: Vuetify
- HTTP client: Axios wrapper in `web/vue/src/lib/api.ts`

## Structure

- Entry: `web/vue/src/main.ts`
- Routes: `web/vue/src/router.ts`
- Landing/login page: `web/vue/src/auth/LandingPage.vue` (`/`)
- Authenticated app shell: `web/vue/src/AppShell.vue` (`/app`)
- Accounts page: `web/vue/src/accounts/AccountsPage.vue` (`/app`)

## Container/Serving Model

- Production-style container is `web/Dockerfile` using NGINX.
- Built assets are copied from `web/vue/dist` into `/usr/share/nginx/html`.
- NGINX config: `web/nginx.conf`
  - Serves SPA with `try_files ... /index.html`
  - Proxies `/api/` to `http://api:8000/`
  - Terminates TLS using cert/key from `/etc/nginx/pki`
- `docker-compose.yml` mounts `./web/pki` into `/etc/nginx/pki:ro`.

## TLS/PKI Notes

- Dev snakeoil certs currently live in `web/pki/tls.crt` and `web/pki/tls.key`.
- Replace these with real material later, keeping same filenames unless nginx config is changed.

## Important Frontend Gaps (Current State)

- Frontend auth is cookie-based and relies on `/auth/me` in router guards.
- Vite dev mode proxies `/api/*` to backend and strips `/api` prefix to match FastAPI routes.

## Build/Run Notes

- Build script: `web/build.sh` runs `npm install` then `npm run build`.
- NGINX image build expects `web/vue/dist` to exist before `docker compose build web`.
