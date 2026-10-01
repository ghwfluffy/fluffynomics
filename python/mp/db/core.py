import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")


def engine_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg2")
    return url


engine = create_engine(engine_url(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
