#!/bin/bash

set -eux -o pipefail

docker compose down -t0
./lint.sh
docker compose build
docker compose up -d
docker compose logs -f
