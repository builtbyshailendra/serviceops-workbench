"""Tests run against a real PostgreSQL database, because the rules live partly in it.

They drop and recreate every table, so they refuse to run unless the database
name ends in _test.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:5433/serviceops_test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.db import Base, create_schema, engine
from app.main import app

if not (make_url(os.environ["DATABASE_URL"]).database or "").endswith("_test"):
    raise RuntimeError("Tests drop every table. Point DATABASE_URL at a database whose name ends in _test.")


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    create_schema()
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def empty_tables():
    table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client():
    return TestClient(app)


def as_(person: str) -> dict:
    return {"X-Acting-As": person}
