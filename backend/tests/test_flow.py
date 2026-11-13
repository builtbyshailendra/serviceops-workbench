"""The status flow through the API, against PostgreSQL."""
import threading
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine
from app.main import app
from conftest import as_


def new_request(client, person="asha") -> int:
    body = {"title": "Access to the finance dashboard", "category": "access"}
    return client.post("/api/requests", json=body, headers=as_(person)).json()["id"]


def act(client, request_id, action, person, **body):
    return client.post(f"/api/requests/{request_id}/{action}", json=body, headers=as_(person))


def test_full_happy_path(client):
    rid = new_request(client)

    triaged = act(client, rid, "triage", "ravi", priority="high")
    assert triaged.status_code == 200
    assert (triaged.json()["status"], triaged.json()["priority"]) == ("triaged", "high")

    approved = act(client, rid, "approve", "meera", note="Fine for one quarter").json()
    assert approved["status"] == "approved"
    assert approved["decided_by"] == "meera"
    decided_at = datetime.fromisoformat(approved["decided_at"])
    assert abs(datetime.now(timezone.utc) - decided_at) < timedelta(minutes=1)

    done = act(client, rid, "complete", "ravi", note="Granted read-only access").json()
    assert done["status"] == "done"
    assert done["decided_by"] == "meera"  # completing doesn't change who approved it


def test_rejection_records_who_and_when(client):
    rid = new_request(client)
    act(client, rid, "triage", "ravi", priority="low")
    rejected = act(client, rid, "reject", "tom", note="Use the shared monthly report").json()
    assert (rejected["status"], rejected["decided_by"]) == ("rejected", "tom")
    assert rejected["decided_at"] is not None


def test_errors_come_back_in_plain_words(client):
    rid = new_request(client)
    early = act(client, rid, "approve", "meera")
    assert early.status_code == 409
    assert early.json()["detail"] == "Can't approve a request that is new. It has to be triaged first."

    act(client, rid, "triage", "ravi", priority="medium")
    wrong_person = act(client, rid, "approve", "ravi")
    assert wrong_person.status_code == 403
    assert act(client, rid, "escalate", "ravi").status_code == 404
    assert act(client, 99, "triage", "ravi", priority="low").status_code == 404
    assert act(client, rid, "triage", "ravi", priority="urgent").status_code == 422


def test_a_failed_step_changes_nothing(client):
    rid = new_request(client, person="meera")
    act(client, rid, "triage", "ravi", priority="high")
    assert act(client, rid, "approve", "meera").status_code == 403
    request = client.get(f"/api/requests/{rid}").json()
    assert (request["status"], request["decided_by"]) == ("triaged", None)


def test_request_shows_what_the_viewer_can_do(client):
    rid = new_request(client)
    assert client.get(f"/api/requests/{rid}", headers=as_("ravi")).json()["allowed_actions"] == ["triage"]
    assert client.get(f"/api/requests/{rid}", headers=as_("meera")).json()["allowed_actions"] == []
    assert client.get(f"/api/requests/{rid}").json()["allowed_actions"] == []
    act(client, rid, "triage", "ravi", priority="low")
    assert client.get(f"/api/requests/{rid}", headers=as_("meera")).json()["allowed_actions"] == [
        "approve",
        "reject",
    ]


def test_second_approver_waits_then_sees_the_first_decision(client):
    """Two approvers click at the same moment. Without the row lock, Tom's approval
    would read "triaged", wait, then overwrite Meera's. With it, Tom waits for
    Meera to finish, reads "approved", and gets a 409."""
    rid = new_request(client)
    act(client, rid, "triage", "ravi", priority="high")
    result = {}

    with engine.connect() as meera:  # Meera's approval, paused halfway through
        transaction = meera.begin()
        meera.execute(text("SELECT id FROM service_requests WHERE id = :id FOR UPDATE"), {"id": rid})

        tom = threading.Thread(target=lambda: result.update(r=act(TestClient(app), rid, "approve", "tom")))
        tom.start()
        tom.join(timeout=1.0)
        assert tom.is_alive(), "Tom's approval should be waiting for Meera's to finish"

        meera.execute(
            text("UPDATE service_requests SET status = 'approved', decided_by = 'meera', decided_at = now() WHERE id = :id"),
            {"id": rid},
        )
        transaction.commit()

    tom.join(timeout=10)
    assert result["r"].status_code == 409
    assert result["r"].json()["detail"] == "Can't approve a request that is approved. It's already approved."
    assert client.get(f"/api/requests/{rid}").json()["decided_by"] == "meera"
