#!/bin/sh
set -eu

raw_base="${APP_BASE_PATH:-/}"
base="/${raw_base#/}"
case "$base" in
  */) ;;
  *) base="${base}/" ;;
esac

if [ "$base" = "/" ]; then
  base_no_slash=""
else
  base_no_slash="${base%/}"
fi

api_prefix="${base_no_slash}/api"
escaped_base_no_slash="$(printf '%s' "$base_no_slash" | sed 's/[.[\*^$()+?{}|]/\\&/g')"
escaped_api_prefix="$(printf '%s' "$api_prefix" | sed 's/[.[\*^$()+?{}|]/\\&/g')"

cat >/etc/nginx/conf.d/default.conf <<EOF
limit_req_status 429;
limit_conn_status 429;
server_tokens off;

# Trust internal/container ingress proxies and rate-limit on the forwarded client IP.
set_real_ip_from 127.0.0.1;
set_real_ip_from 10.0.0.0/8;
set_real_ip_from 172.16.0.0/12;
set_real_ip_from 192.168.0.0/16;
set_real_ip_from fc00::/7;
real_ip_header X-Forwarded-For;
real_ip_recursive on;

# Global per-IP zones for edge abuse protection. Normal API pages can fan out
# many read calls on dashboard load, so keep auth stricter and give app reads
# enough room to burst without tripping normal usage.
limit_req_zone \$binary_remote_addr zone=api_per_ip:20m rate=300r/s;
limit_req_zone \$binary_remote_addr zone=auth_per_ip:10m rate=30r/m;
limit_conn_zone \$binary_remote_addr zone=conn_per_ip:10m;

server {
    listen 80;
    listen [::]:80;
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/pki/tls.crt;
    ssl_certificate_key /etc/nginx/pki/tls.key;

    root /usr/share/nginx/html;
    index index.html;
EOF

if [ "$base" != "/" ]; then
  cat >>/etc/nginx/conf.d/default.conf <<EOF

    location = / {
        return 308 ${base};
    }

    location = ${base_no_slash} {
        return 308 ${base};
    }
EOF
fi

cat >>/etc/nginx/conf.d/default.conf <<EOF

    location ^~ ${api_prefix}/auth/ {
        limit_req zone=auth_per_ip burst=10 nodelay;
        limit_conn conn_per_ip 10;

        rewrite ^${escaped_api_prefix}/(.*)\$ /\$1 break;
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${api_prefix};
    }

    location ^~ ${api_prefix}/widgets/ {
        limit_req zone=api_per_ip burst=150 nodelay;
        limit_conn conn_per_ip 40;

        proxy_cache off;
        proxy_no_cache 1;
        proxy_cache_bypass 1;
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0" always;
        add_header Pragma "no-cache" always;
        add_header Expires "0" always;

        rewrite ^${escaped_api_prefix}/(.*)\$ /\$1 break;
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${api_prefix};
    }

    location ^~ ${api_prefix}/icons/ {
        rewrite ^${escaped_api_prefix}/(.*)\$ /\$1 break;
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${api_prefix};
    }

    location = ${api_prefix}/backups/site/restore {
        client_max_body_size 25m;
        limit_req zone=api_per_ip burst=300 nodelay;
        limit_conn conn_per_ip 80;

        rewrite ^${escaped_api_prefix}/(.*)\$ /\$1 break;
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${api_prefix};
    }

    location ^~ ${api_prefix}/ {
        limit_req zone=api_per_ip burst=300 nodelay;
        limit_conn conn_per_ip 80;

        rewrite ^${escaped_api_prefix}/(.*)\$ /\$1 break;
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${api_prefix};
    }
EOF

if [ "$base" = "/" ]; then
  cat >>/etc/nginx/conf.d/default.conf <<'EOF'

    location / {
        try_files $uri $uri/ /index.html;
    }
EOF
else
  cat >>/etc/nginx/conf.d/default.conf <<EOF

    location ^~ ${base} {
        rewrite ^${escaped_base_no_slash}/(.*)\$ /\$1 break;
        try_files \$uri \$uri/ /index.html;
    }
EOF
fi

cat >>/etc/nginx/conf.d/default.conf <<'EOF'
}
EOF
