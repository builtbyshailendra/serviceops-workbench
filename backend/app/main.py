"""HTTP API for service requests."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import create_schema, get_session
from app.models import STATUSES, ServiceRequest
from app.people import PEOPLE, Person, acting_as
from app.schemas import RequestIn, RequestOut


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(title="serviceops-workbench", lifespan=lifespan)


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
) -> ServiceRequest:
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
    return request


@app.get("/api/requests", response_model=list[RequestOut])
def list_requests(status: str | None = None, session: Session = Depends(get_session)) -> list[ServiceRequest]:
    query = select(ServiceRequest).order_by(ServiceRequest.id.desc())
    if status is not None:
        if status not in STATUSES:
            raise HTTPException(422, f"Unknown status '{status}'. Use one of: {', '.join(STATUSES)}")
        query = query.where(ServiceRequest.status == status)
    return list(session.scalars(query))


@app.get("/api/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: int, session: Session = Depends(get_session)) -> ServiceRequest:
    request = session.get(ServiceRequest, request_id)
    if request is None:
        raise HTTPException(404, f"Request {request_id} doesn't exist")
    return request
