FROM nginx:1.27-alpine

# Serve the built Vue app
COPY ./web/vue/dist/ /usr/share/nginx/html/

# Runtime-rendered reverse-proxy config and base-path support
COPY ./web/docker-entrypoint.d/ /docker-entrypoint.d/

# Fallback snakeoil certs; replace with real certs by mounting ./web/pki
COPY ./web/pki/ /etc/nginx/pki/

EXPOSE 80 443
