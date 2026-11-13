"""What running more than one copy of the backend, behind health checks, relies on."""
import threading

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db import Base, create_schema, engine, get_session
from app.main import app


def test_copies_starting_together_take_turns_creating_tables():
    # Three copies start at the same moment against an empty database, as two or
    # three pods do in Kubernetes. Before the advisory lock in create_schema, most
    # of them failed with "duplicate key value violates unique constraint".
    for _ in range(5):
        Base.metadata.drop_all(engine)
        errors: list[Exception] = []
        barrier = threading.Barrier(3)

        def start() -> None:
            barrier.wait()
            try:
                create_schema()
            except Exception as error:  # noqa: BLE001 - collected for the assert
                errors.append(error)

        threads = [threading.Thread(target=start) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    tables = set(inspect(engine).get_table_names())
    assert {"service_requests", "audit_events"} <= tables
    with engine.connect() as connection:
        triggers = connection.scalar(
            text("SELECT count(*) FROM pg_trigger WHERE tgname = 'audit_events_append_only'")
        )
    assert triggers == 1


def test_ready_when_the_database_answers(client):
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def _unreachable_session():
    # Port 1 on this machine: nothing listens there, so connecting fails fast.
    broken = create_engine("postgresql+psycopg://postgres@127.0.0.1:1/nowhere", connect_args={"connect_timeout": 2})
    with sessionmaker(broken)() as session:
        yield session
    broken.dispose()


def test_not_ready_without_the_database_but_still_healthy(client):
    app.dependency_overrides[get_session] = _unreachable_session
    try:
        ready = client.get("/api/ready")
        health = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()
    # Not ready: Kubernetes stops sending it traffic.
    assert ready.status_code == 503
    assert ready.json() == {"detail": "Can't reach the database"}
    # Still healthy: Kubernetes doesn't restart it for something a restart can't fix.
    assert health.status_code == 200
