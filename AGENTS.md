# Money Planner Agent Notes

This file is the entry point for future dev agents working in this repo.

## Read First

1. `docs/architecture/api.md`
2. `docs/architecture/web.md`
3. `docs/architecture/database.md`

## Working Rules

- Treat `docker-compose.yml` as the source of truth for local orchestration.
- Keep API/web pathing consistent with NGINX (`/api/...` externally).
- Do not assume CRUD is fully implemented; verify endpoints before wiring UI calls.
- Keep schema and DB evolution explicit (new tables/columns should be reflected in both SQL and ORM models).
