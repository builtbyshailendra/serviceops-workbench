"""The audit trail: every change writes one event, and events can't be changed."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine
from conftest import as_


def new_request(client, person="asha", title="Access to the finance dashboard") -> int:
    return client.post("/api/requests", json={"title": title, "category": "access"}, headers=as_(person)).json()["id"]


def act(client, request_id, action, person, **body):
    return client.post(f"/api/requests/{request_id}/{action}", json=body, headers=as_(person))


def happy_path(client) -> int:
    rid = new_request(client)
    act(client, rid, "triage", "ravi", priority="high", note="Finance asked for it")
    act(client, rid, "approve", "meera", note="Fine for one quarter")
    act(client, rid, "complete", "ravi", note="Granted read-only access")
    return rid


def test_every_step_writes_one_event_in_order(client):
    rid = happy_path(client)
    events = client.get(f"/api/requests/{rid}/events").json()
    assert [(e["action"], e["actor"], e["from_status"], e["to_status"]) for e in events] == [
        ("created", "asha", None, "new"),
        ("triaged", "ravi", "new", "triaged"),
        ("approved", "meera", "triaged", "approved"),
        ("completed", "ravi", "approved", "done"),
    ]
    assert events[1]["note"] == "Priority high. Finance asked for it"
    assert events[3]["note"] == "Granted read-only access"
    assert all(e["request_title"] == "Access to the finance dashboard" for e in events)


def test_approval_event_matches_the_request(client):
    rid = happy_path(client)
    request = client.get(f"/api/requests/{rid}").json()
    approval = next(e for e in client.get(f"/api/requests/{rid}/events").json() if e["action"] == "approved")
    assert approval["actor"] == request["decided_by"]
    # Same transaction, same clock: now() is fixed at the start of a PostgreSQL transaction.
    assert approval["at"] == request["decided_at"]


def test_a_refused_step_writes_no_event(client):
    rid = new_request(client)
    assert act(client, rid, "approve", "meera").status_code == 409
    assert act(client, rid, "triage", "asha", priority="low").status_code == 403
    assert [e["action"] for e in client.get(f"/api/requests/{rid}/events").json()] == ["created"]


def test_audit_log_is_newest_first_across_requests(client):
    first = new_request(client, title="New laptop")
    second = new_request(client, person="meera", title="Licence for a diagram tool")
    act(client, first, "triage", "ravi", priority="low")
    log = client.get("/api/audit").json()
    assert [(e["request_id"], e["action"]) for e in log] == [(first, "triaged"), (second, "created"), (first, "created")]
    assert log[1]["request_title"] == "Licence for a diagram tool"
    assert len(client.get("/api/audit?limit=1").json()) == 1
    assert client.get("/api/audit?limit=0").status_code == 422


def test_events_for_a_missing_request(client):
    assert client.get("/api/requests/99/events").status_code == 404


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_events SET actor = 'tom' WHERE action = 'approved'",
        "DELETE FROM audit_events WHERE action = 'approved'",
    ],
)
def test_database_refuses_to_change_history(client, sql):
    happy_path(client)
    with pytest.raises(DBAPIError, match="audit_events is append-only"):
        with engine.begin() as connection:
            connection.execute(text(sql))
    assert len(client.get("/api/audit").json()) == 4


def test_a_request_with_history_cant_be_deleted(client):
    rid = new_request(client)
    with pytest.raises(DBAPIError, match="audit_events"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM service_requests WHERE id = :id"), {"id": rid})
