"""The status flow, as plain Python with no database, so every rule is easy to test.

    new ──triage──▶ triaged ──approve──▶ approved ──complete──▶ done
                       │
                       └────reject────▶ rejected

Each step says who may take it. Approving and rejecting are the human decision:
they record who decided and when, and nobody may decide their own request.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.people import APPROVER, SERVICE_DESK, Person


@dataclass(frozen=True)
class Step:
    from_status: str
    to_status: str
    role: str
    past: str                   # how the audit log names it
    decision: bool = False      # records who decided and when
    note_needed: str = ""       # if set, the step needs a note, and this says why


STEPS = {
    "triage": Step("new", "triaged", SERVICE_DESK, "triaged"),
    "approve": Step("triaged", "approved", APPROVER, "approved", decision=True),
    "reject": Step("triaged", "rejected", APPROVER, "rejected", decision=True, note_needed="Say why it's rejected"),
    "complete": Step("approved", "done", SERVICE_DESK, "completed", note_needed="Say what was done"),
}

ROLE_WORDS = {
    "requester": "a requester",
    SERVICE_DESK: "on the service desk",
    APPROVER: "an approver",
}
WHO_CAN = {SERVICE_DESK: "Someone on the service desk", APPROVER: "An approver"}
NEXT_HINT = {
    "new": "It has to be triaged first.",
    "triaged": "It has to be approved first.",
    "approved": "It's already approved.",
    "rejected": "It was rejected, so it's closed.",
    "done": "It's already done.",
}


class WorkflowError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def check(action: str, status: str, requested_by: str, person: Person, note: str = "", priority: str | None = None) -> Step:
    """Return the step if this person may take this action now, or raise WorkflowError saying why not."""
    step = STEPS.get(action)
    if step is None:
        raise WorkflowError(404, f"There's no '{action}' step. Use one of: {', '.join(STEPS)}")
    if person.role != step.role:
        raise WorkflowError(
            403,
            f"{person.name} is {ROLE_WORDS[person.role]} and can't {action} requests. "
            f"{WHO_CAN[step.role]} has to do it.",
        )
    if step.decision and person.id == requested_by:
        raise WorkflowError(403, f"{person.name} raised this request, so someone else has to {action} it.")
    if status != step.from_status:
        raise WorkflowError(409, f"Can't {action} a request that is {status}. {NEXT_HINT[status]}")
    if step.note_needed and not note.strip():
        raise WorkflowError(422, step.note_needed)
    if action == "triage" and priority is None:
        raise WorkflowError(422, "Pick a priority to triage it")
    return step


def allowed(status: str, requested_by: str, person: Person) -> list[str]:
    """The actions this person could take on this request right now (ignoring notes and priority)."""
    out = []
    for action, step in STEPS.items():
        if step.from_status == status and step.role == person.role:
            if not (step.decision and person.id == requested_by):
                out.append(action)
    return out
