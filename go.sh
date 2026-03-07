#!/bin/bash

set -eux -o pipefail

(
    cd python
    ./lint.sh
)
(
    cd web
    ./build.sh
)

docker compose down -t0
docker compose build
docker compose up -d
docker compose logs -f
