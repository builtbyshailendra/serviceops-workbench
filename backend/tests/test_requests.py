import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db import engine
from conftest import as_

ACCESS = {"title": "Access to the finance dashboard", "category": "access", "description": "Read only is fine"}


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_people_have_roles(client):
    roles = {p["id"]: p["role"] for p in client.get("/api/people").json()}
    assert roles == {"asha": "requester", "ravi": "service_desk", "meera": "approver", "tom": "approver"}


def test_create_request_starts_as_new(client):
    response = client.post("/api/requests", json=ACCESS, headers=as_("asha"))
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["status"] == "new"
    assert body["requested_by"] == "asha"
    assert body["priority"] is None
    assert body["decided_by"] is None


def test_title_is_trimmed_and_checked(client):
    response = client.post("/api/requests", json={**ACCESS, "title": "   New laptop   "}, headers=as_("asha"))
    assert response.json()["title"] == "New laptop"
    too_short = client.post("/api/requests", json={**ACCESS, "title": "  x "}, headers=as_("asha"))
    assert too_short.status_code == 422


def test_unknown_category_is_rejected(client):
    response = client.post("/api/requests", json={**ACCESS, "category": "pizza"}, headers=as_("asha"))
    assert response.status_code == 422


@pytest.mark.parametrize("headers, message", [({}, "Say who you're acting as"), (as_("mallory"), "Nobody called")])
def test_creating_needs_a_known_person(client, headers, message):
    response = client.post("/api/requests", json=ACCESS, headers=headers)
    assert response.status_code == 401
    assert message in response.json()["detail"]


def test_list_newest_first_and_filter_by_status(client):
    for title in ("First request", "Second request"):
        client.post("/api/requests", json={**ACCESS, "title": title}, headers=as_("asha"))
    assert [r["title"] for r in client.get("/api/requests").json()] == ["Second request", "First request"]
    assert len(client.get("/api/requests?status=new").json()) == 2
    assert client.get("/api/requests?status=done").json() == []
    assert client.get("/api/requests?status=lost").status_code == 422


def test_get_one_and_missing(client):
    client.post("/api/requests", json=ACCESS, headers=as_("asha"))
    assert client.get("/api/requests/1").json()["title"] == ACCESS["title"]
    missing = client.get("/api/requests/99")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Request 99 doesn't exist"


# The database enforces the important rules too, even if the API had a bug.

def insert(sql: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(sql))


def test_database_refuses_an_approval_without_who_and_when():
    with pytest.raises(IntegrityError, match="decision_has_who_and_when"):
        insert(
            "INSERT INTO service_requests (title, description, category, requested_by, status, priority) "
            "VALUES ('x', '', 'access', 'asha', 'approved', 'high')"
        )


def test_database_refuses_self_approval():
    with pytest.raises(IntegrityError, match="no_self_decision"):
        insert(
            "INSERT INTO service_requests "
            "(title, description, category, requested_by, status, priority, decided_by, decided_at) "
            "VALUES ('x', '', 'access', 'meera', 'approved', 'high', 'meera', now())"
        )


def test_database_refuses_triage_without_priority():
    with pytest.raises(IntegrityError, match="triaged_has_priority"):
        insert(
            "INSERT INTO service_requests (title, description, category, requested_by, status) "
            "VALUES ('x', '', 'access', 'asha', 'triaged')"
        )
