"""Database connection. PostgreSQL only: the audit log relies on a PostgreSQL trigger."""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Matches scripts/dev-postgres.sh. Override with the DATABASE_URL environment variable.
DEFAULT_URL = "postgresql+psycopg://postgres@127.0.0.1:5433/serviceops"


class Base(DeclarativeBase):
    pass


engine = create_engine(os.environ.get("DATABASE_URL", DEFAULT_URL), pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    # Imported so the models register their tables on Base.metadata first.
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
