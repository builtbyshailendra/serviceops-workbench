"""HTTP API for service requests."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import workflow
from app.db import create_schema, get_session
from app.models import STATUSES, AuditEvent, ServiceRequest
from app.people import PEOPLE, Person, acting_as
from app.schemas import ActionIn, EventOut, RequestIn, RequestOut


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(title="serviceops-workbench", lifespan=lifespan)


@app.exception_handler(workflow.WorkflowError)
def workflow_error(_, error: workflow.WorkflowError) -> JSONResponse:
    return JSONResponse({"detail": error.message}, status_code=error.status_code)


def _out(request: ServiceRequest, person: Person | None = None) -> RequestOut:
    out = RequestOut.model_validate(request)
    if person is not None:
        out.allowed_actions = workflow.allowed(request.status, request.requested_by, person)
    return out


def _find(session: Session, request_id: int, lock: bool = False) -> ServiceRequest:
    # with_for_update locks the row until the transaction ends, so two people
    # acting on the same request at once are handled one after the other.
    request = session.get(ServiceRequest, request_id, with_for_update=lock)
    if request is None:
        raise HTTPException(404, f"Request {request_id} doesn't exist")
    return request


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/people")
def people() -> list[dict]:
    return [p.to_dict() for p in PEOPLE.values()]


@app.post("/api/requests", status_code=201, response_model=RequestOut)
def create_request(
    body: RequestIn,
    person: Person = Depends(acting_as),
    session: Session = Depends(get_session),
) -> RequestOut:
    request = ServiceRequest(
        title=body.title,
        description=body.description,
        category=body.category,
        requested_by=person.id,
        status="new",
    )
    session.add(request)
    session.flush()  # gives the request its id for the event below
    session.add(AuditEvent(request_id=request.id, action="created", actor=person.id, to_status="new"))
    session.commit()
    session.refresh(request)
    return _out(request, person)


@app.get("/api/requests", response_model=list[RequestOut])
def list_requests(status: str | None = None, session: Session = Depends(get_session)) -> list[RequestOut]:
    query = select(ServiceRequest).order_by(ServiceRequest.id.desc())
    if status is not None:
        if status not in STATUSES:
            raise HTTPException(422, f"Unknown status '{status}'. Use one of: {', '.join(STATUSES)}")
        query = query.where(ServiceRequest.status == status)
    return [_out(r) for r in session.scalars(query)]


@app.get("/api/requests/{request_id}", response_model=RequestOut)
def get_request(
    request_id: int,
    x_acting_as: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> RequestOut:
    person = acting_as(x_acting_as) if x_acting_as else None
    return _out(_find(session, request_id), person)


@app.post("/api/requests/{request_id}/{action}", response_model=RequestOut)
def take_action(
    request_id: int,
    action: str,
    body: ActionIn,
    person: Person = Depends(acting_as),
    session: Session = Depends(get_session),
) -> RequestOut:
    request = _find(session, request_id, lock=True)
    step = workflow.check(action, request.status, request.requested_by, person, body.note, body.priority)

    note = body.note
    if action == "triage":
        request.priority = body.priority
        note = f"Priority {body.priority}. {note}".strip()
    if step.decision:
        request.decided_by = person.id
        request.decided_at = func.now()
    session.add(
        AuditEvent(
            request_id=request.id,
            action=step.past,
            actor=person.id,
            from_status=request.status,
            to_status=step.to_status,
            note=note,
        )
    )
    request.status = step.to_status
    # The change and its audit event commit together, or not at all.
    session.commit()
    session.refresh(request)
    return _out(request, person)


def _event_out(event: AuditEvent) -> EventOut:
    return EventOut.model_validate({**event.__dict__, "request_title": event.request.title})


@app.get("/api/requests/{request_id}/events", response_model=list[EventOut])
def request_events(request_id: int, session: Session = Depends(get_session)) -> list[EventOut]:
    _find(session, request_id)
    query = select(AuditEvent).where(AuditEvent.request_id == request_id).order_by(AuditEvent.id)
    query = query.options(joinedload(AuditEvent.request))
    return [_event_out(e) for e in session.scalars(query)]


@app.get("/api/audit", response_model=list[EventOut])
def audit_log(limit: int = 100, session: Session = Depends(get_session)) -> list[EventOut]:
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit must be between 1 and 500")
    # joinedload fetches each event's request in the same query, not one query per event.
    query = select(AuditEvent).options(joinedload(AuditEvent.request)).order_by(AuditEvent.id.desc()).limit(limit)
    return [_event_out(e) for e in session.scalars(query)]
