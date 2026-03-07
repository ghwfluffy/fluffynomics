# API Architecture

## Stack

- Framework: FastAPI (`python/main.py`)
- ORM: SQLAlchemy 2-style mapped columns (`python/mp/schema/*.py`)
- DB session dependency: `python/mp/db/core.py` (re-exported via `python/mp/db/__init__.py`)

## App Structure

- FastAPI app is created in `python/main.py`.
- Routers are dynamically imported from `mp.api.*`.
- Right now only `accounts` is mounted.

## Current Routes

- `GET /accounts`
- `POST /accounts`

Defined in `python/mp/api/accounts.py`.

## Important Constraints

- There is currently no `PUT /accounts/{id}` or `DELETE /accounts/{id}` route.
- `AccountSchema` includes required `id`, so create requests currently require an `id` in payload.
- `Account` model uses explicit `id` primary key with no autoincrement behavior defined in SQL schema.
- CORS is currently very open (`allow_origins=["*"]` etc.) for dev convenience.

## Runtime / Container Notes

- API container runs `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- DB connection is from `DATABASE_URL` env var.
- In docker-compose, API is reachable by other services as `http://api:8000`.

## Cross-Layer Integration

- Web traffic should hit API via NGINX proxy path `/api/...`.
- If frontend directly calls `http://localhost:8000`, it bypasses NGINX/TLS and may fail in containerized-only flows.
