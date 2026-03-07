FROM nginx:1.27-alpine

# Serve the built Vue app
COPY ./web/vue/dist/ /usr/share/nginx/html/

# TLS + reverse-proxy config
COPY ./web/nginx.conf /etc/nginx/conf.d/default.conf

# Fallback snakeoil certs; replace with real certs by mounting ./web/pki
COPY ./web/pki/ /etc/nginx/pki/

EXPOSE 443
