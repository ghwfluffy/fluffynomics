import os
import unittest

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

os.environ.setdefault("DATABASE_URL", "sqlite://")

from mp.db.core import engine_url  # noqa: E402


class DatabaseDriverTests(unittest.TestCase):
    def test_postgresql_uses_installed_driver(self) -> None:
        url = engine_url("postgresql://user:password@localhost/example")
        engine = create_engine(url)
        try:
            self.assertEqual(engine.dialect.driver, "psycopg2")
        finally:
            engine.dispose()

    def test_explicit_drivers_and_sqlite_are_preserved(self) -> None:
        for value in (
            "postgresql+psycopg2://localhost/example",
            "postgresql+psycopg://localhost/example",
            "sqlite://",
        ):
            with self.subTest(value=value):
                self.assertEqual(engine_url(value), make_url(value))

    def test_credentials_and_options_are_preserved(self) -> None:
        value = "postgresql://user:p%40ss%2Fword@localhost:5433/db?sslmode=require"
        expected = make_url(value).set(drivername="postgresql+psycopg2")
        self.assertEqual(engine_url(value), expected)
        self.assertEqual(engine_url(value).password, "p@ss/word")
