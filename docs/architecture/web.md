# Web Architecture

## Stack

- Framework: Vue 3 + TypeScript
- Build tool: Vite
- UI: Vuetify
- HTTP client: Axios wrapper in `web/vue/src/lib/api.ts`

## Structure

- Entry: `web/vue/src/main.ts`
- Routes: `web/vue/src/router.ts`
- Current page: `web/vue/src/accounts/AccountsPage.vue` (`/`)

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

- `request.get()` returns response data directly, but `AccountsPage.vue` uses `res.data`.
- `deleteAccount()` references `API_URL` which is not defined.
- Form calls update endpoint (`PUT /accounts/{id}`) not currently implemented by API.
- Axios base URL is hardcoded to `http://localhost:8000`; this conflicts with the NGINX `/api` pattern and HTTPS flow.

## Build/Run Notes

- Build script: `web/build.sh` runs `npm install` then `npm run build`.
- NGINX image build expects `web/vue/dist` to exist before `docker compose build web`.
