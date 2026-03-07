# API Architecture

## Stack

- Framework: FastAPI (`python/main.py`)
- ORM: SQLAlchemy 2-style mapped columns (`python/mp/schema/*.py`)
- DB session dependency: `python/mp/db/core.py` (re-exported via `python/mp/db/__init__.py`)

## App Structure

- FastAPI app is created in `python/main.py`.
- Routers are dynamically imported from `mp.api.*`.
- Currently mounted routers: `auth`, `accounts`.

## Current Routes

- `POST /auth/register`
  - accepts `add_example_data` boolean.
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /accounts`
- `GET /accounts/{id}`
- `POST /accounts`
- `PUT /accounts/{id}`
- `DELETE /accounts/{id}`
- `GET /stocks`
- `POST /stocks`
- `PUT /stocks/{id}`
- `DELETE /stocks/{id}`

Defined in `python/mp/api/auth.py` and `python/mp/api/accounts.py`.

## Important Constraints

- Accounts and stocks are scoped by authenticated user (`user_id`) in the backend.
- Session auth is cookie-based via encrypted+signed payload with `user_id` and expiration.
- Login returns `session_token` in JSON and also sets cookie; auth accepts cookie or bearer token.
- Session key is generated at API startup, so sessions are invalidated on API restart.
- CORS is currently very open (`allow_origins=["*"]` etc.) for dev convenience.
- Example data seeding lives in `python/mp/sample_data.py`; keep it updated with new features.

## Runtime / Container Notes

- API container runs `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- DB connection is from `DATABASE_URL` env var.
- In docker-compose, API is reachable by other services as `http://api:8000`.

## Cross-Layer Integration

- Web traffic should hit API via NGINX proxy path `/api/...`.
- If frontend directly calls `http://localhost:8000`, it bypasses NGINX/TLS and may fail in containerized-only flows.
