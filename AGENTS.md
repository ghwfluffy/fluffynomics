# Money Planner Agent Notes

This file is the entry point for future dev agents working in this repo.

## Read First

1. `docs/architecture/api.md`
2. `docs/architecture/web.md`
3. `docs/architecture/database.md`

## Working Rules

- Treat `docker-compose.yml` as the source of truth for local orchestration.
- Keep API/web pathing consistent with NGINX (`/api/...` externally).
- Keep schema and DB evolution explicit through SQL migrations + ORM model updates.
- Maintain example-data parity: when adding schema/features, update `python/mp/sample_data.py` so `example_data=true` users get representative sample records.
- Prefer consistent reusable UI primitives over one-off components (example: shared dropdown behavior in `web/vue/src/components/UnifiedDropdown.vue`).
- Preserve existing UX patterns unless explicitly changing product direction.
- For media-like assets (icons/logos), prefer hash-deduplicated storage with reusable references rather than duplicating blobs per account.
- For default organization icons, prefer brand-appropriate color versions (avoid defaulting to black variants unless color is genuinely unavailable or inappropriate).

## Documentation Rule (Important)

- When you add or change behavior that future agents will need to follow consistently, document it in:
  - `docs/architecture/api.md` for API/backend behavior,
  - `docs/architecture/web.md` for frontend UX/component conventions,
  - `docs/architecture/database.md` for schema/migration/data model rules.
- Do not leave important behavior as “tribal knowledge.”
