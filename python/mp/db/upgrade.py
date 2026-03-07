import re
from pathlib import Path

from sqlalchemy import text

from mp.db.core import DATABASE_URL, engine

REVISION_FILENAME_RE = re.compile(r"^(?P<revision>\d{4})_.*\.sql$")


def _list_migrations() -> dict[int, Path]:
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    migrations: dict[int, Path] = {}
    for path in migrations_dir.glob("*.sql"):
        match = REVISION_FILENAME_RE.match(path.name)
        if match is None:
            continue
        revision = int(match.group("revision"))
        migrations[revision] = path
    return migrations


def run_database_upgrades() -> None:
    if not DATABASE_URL:
        return

    migrations = _list_migrations()
    if not migrations:
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO app_config (key, value)
            VALUES ('dbversion', '0')
            ON CONFLICT (key) DO NOTHING
            """
        )
        current_revision = int(
            conn.execute(
                text("SELECT value FROM app_config WHERE key = 'dbversion'")
            ).scalar_one()
        )

        for revision in sorted(migrations):
            if revision <= current_revision:
                continue

            migration_path = migrations[revision]
            sql = migration_path.read_text().strip()
            if sql:
                conn.exec_driver_sql(sql)
            conn.execute(
                text("UPDATE app_config SET value = :revision WHERE key = 'dbversion'"),
                {"revision": str(revision)},
            )
