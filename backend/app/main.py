"""HTTP API for service requests."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import workflow
from app.db import create_schema, get_session
from app.models import STATUSES, ServiceRequest
from app.people import PEOPLE, Person, acting_as
from app.schemas import ActionIn, RequestIn, RequestOut


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

    request.status = step.to_status
    if action == "triage":
        request.priority = body.priority
    if step.decision:
        request.decided_by = person.id
        request.decided_at = func.now()
    session.commit()
    session.refresh(request)
    return _out(request, person)
