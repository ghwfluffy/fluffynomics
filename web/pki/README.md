# TLS material

This directory is bind-mounted into the web container at `/etc/nginx/pki`.

Expected files:
- `tls.crt`
- `tls.key`

The current files are self-signed snakeoil certs for local development.
Replace them with your real cert/key when available.
