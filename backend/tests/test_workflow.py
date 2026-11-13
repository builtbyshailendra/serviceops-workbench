"""The rules on their own, without the database or HTTP."""
import pytest

from app.people import PEOPLE
from app.workflow import WorkflowError, allowed, check

ASHA, RAVI, MEERA, TOM = (PEOPLE[p] for p in ("asha", "ravi", "meera", "tom"))


def error(action, status, person, requested_by="asha", **kwargs) -> WorkflowError:
    with pytest.raises(WorkflowError) as caught:
        check(action, status, requested_by, person, **kwargs)
    return caught.value


def test_happy_path_steps():
    assert check("triage", "new", "asha", RAVI, priority="high").to_status == "triaged"
    assert check("approve", "triaged", "asha", MEERA).to_status == "approved"
    assert check("complete", "approved", "asha", RAVI, note="Granted read access").to_status == "done"
    assert check("reject", "triaged", "asha", TOM, note="Use the shared report").to_status == "rejected"


def test_only_approvers_approve():
    e = error("approve", "triaged", RAVI)
    assert e.status_code == 403
    assert e.message == "Ravi is on the service desk and can't approve requests. An approver has to do it."


def test_requesters_cant_triage():
    e = error("triage", "new", ASHA, priority="low")
    assert e.message == "Asha is a requester and can't triage requests. Someone on the service desk has to do it."


def test_nobody_approves_their_own_request():
    e = error("approve", "triaged", MEERA, requested_by="meera")
    assert e.status_code == 403
    assert e.message == "Meera raised this request, so someone else has to approve it."
    # Another approver can.
    assert check("approve", "triaged", "meera", TOM).to_status == "approved"


@pytest.mark.parametrize(
    "action, status, person, hint",
    [
        ("approve", "new", MEERA, "It has to be triaged first."),
        ("complete", "triaged", RAVI, "It has to be approved first."),
        ("approve", "approved", TOM, "It's already approved."),
        ("complete", "rejected", RAVI, "It was rejected, so it's closed."),
        ("triage", "done", RAVI, "It's already done."),
    ],
)
def test_steps_happen_in_order(action, status, person, hint):
    e = error(action, status, person, note="x", priority="low")
    assert e.status_code == 409
    assert e.message == f"Can't {action} a request that is {status}. {hint}"


@pytest.mark.parametrize(
    "action, status, person, message",
    [
        ("reject", "triaged", MEERA, "Say why it's rejected"),
        ("complete", "approved", RAVI, "Say what was done"),
        ("triage", "new", RAVI, "Pick a priority to triage it"),
    ],
)
def test_some_steps_need_more_input(action, status, person, message):
    e = error(action, status, person, note="   ")
    assert (e.status_code, e.message) == (422, message)


def test_unknown_step():
    assert error("escalate", "new", RAVI).status_code == 404


def test_allowed_actions_per_person():
    assert allowed("new", "asha", RAVI) == ["triage"]
    assert allowed("new", "asha", MEERA) == []
    assert allowed("triaged", "asha", MEERA) == ["approve", "reject"]
    assert allowed("triaged", "meera", MEERA) == []          # her own request
    assert allowed("approved", "asha", RAVI) == ["complete"]
    assert allowed("done", "asha", RAVI) == []
