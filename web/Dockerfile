FROM node:22-slim AS web-build

WORKDIR /workspace/web/vue

ARG VITE_APP_BASE_PATH=/
ARG VITE_PUBLIC_URL=
ARG VITE_AUTH_MODE=local
ARG VITE_AUTH_BASE_URL=/auth
ARG VITE_GOALS_BASE_URL=
ARG VITE_MONEY_PLANNER_BASE_URL=
ARG VITE_AGENT_BASE_URL=
ARG VITE_APARTMENT_GATE_BASE_URL=
ARG VITE_FILE_SHARE_BASE_URL=

ENV VITE_APP_BASE_PATH=${VITE_APP_BASE_PATH}
ENV VITE_PUBLIC_URL=${VITE_PUBLIC_URL}
ENV VITE_AUTH_MODE=${VITE_AUTH_MODE}
ENV VITE_AUTH_BASE_URL=${VITE_AUTH_BASE_URL}
ENV VITE_GOALS_BASE_URL=${VITE_GOALS_BASE_URL}
ENV VITE_MONEY_PLANNER_BASE_URL=${VITE_MONEY_PLANNER_BASE_URL}
ENV VITE_AGENT_BASE_URL=${VITE_AGENT_BASE_URL}
ENV VITE_APARTMENT_GATE_BASE_URL=${VITE_APARTMENT_GATE_BASE_URL}
ENV VITE_FILE_SHARE_BASE_URL=${VITE_FILE_SHARE_BASE_URL}

COPY ./vendor/federated-banner/ /workspace/vendor/federated-banner/
COPY ./web/vue/package*.json ./
RUN npm ci

COPY ./web/vue/ ./
RUN npm run build

FROM nginx:1.27-alpine

# Serve the built Vue app
COPY --from=web-build /workspace/web/vue/dist/ /usr/share/nginx/html/

# Runtime-rendered reverse-proxy config and base-path support
COPY ./web/docker-entrypoint.d/ /docker-entrypoint.d/

# Fallback snakeoil certs; replace with real certs by mounting ./web/pki
COPY ./web/pki/ /etc/nginx/pki/

EXPOSE 80 443
