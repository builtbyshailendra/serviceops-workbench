"""Database connection. PostgreSQL only: the audit log relies on a PostgreSQL trigger."""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Matches scripts/dev-postgres.sh. Override with the DATABASE_URL environment variable.
DEFAULT_URL = "postgresql+psycopg://postgres@127.0.0.1:5433/serviceops"

# Any fixed number works. It only has to be the same in every copy of the backend.
SCHEMA_LOCK = 72001


class Base(DeclarativeBase):
    pass


# connect_timeout: if the database can't be reached, fail in seconds instead of
# hanging, so the readiness check answers before Kubernetes gives up on it.
engine = create_engine(
    os.environ.get("DATABASE_URL", DEFAULT_URL),
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    # Imported so the models register their tables on Base.metadata first.
    from app import models  # noqa: F401

    # Several copies of the backend can start at the same moment, such as two pods
    # in Kubernetes. Without a lock they all see no tables, all try to create them,
    # and all but one fail. The advisory lock makes them take turns. PostgreSQL
    # releases it when the transaction ends.
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCHEMA_LOCK})
        Base.metadata.create_all(connection)
