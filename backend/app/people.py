"""The demo team. There is no login: the UI lets you pick who you're acting as,
and the API reads that from the X-Acting-As header. All names are made up."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from fastapi import Header, HTTPException

REQUESTER = "requester"
SERVICE_DESK = "service_desk"
APPROVER = "approver"


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    role: str

    def to_dict(self) -> dict:
        return asdict(self)


PEOPLE = {
    p.id: p
    for p in (
        Person("asha", "Asha", REQUESTER),
        Person("ravi", "Ravi", SERVICE_DESK),
        Person("meera", "Meera", APPROVER),
        Person("tom", "Tom", APPROVER),
    )
}


def acting_as(x_acting_as: str | None = Header(default=None)) -> Person:
    """FastAPI dependency: the person making this request."""
    if not x_acting_as:
        raise HTTPException(401, "Say who you're acting as with the X-Acting-As header")
    person = PEOPLE.get(x_acting_as.strip().lower())
    if person is None:
        raise HTTPException(401, f"Nobody called '{x_acting_as}' works here")
    return person
