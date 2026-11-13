"""What the API accepts and returns."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["access", "hardware", "software", "other"]
Priority = Literal["low", "medium", "high"]


class ActionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    note: str = Field(default="", max_length=2000)
    priority: Priority | None = None


class RequestIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=4000)
    category: Category


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: str
    requested_by: str
    status: str
    priority: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # What the person in X-Acting-As could do next. Empty when no one is named.
    allowed_actions: list[str] = []


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    request_title: str
    action: str
    actor: str
    from_status: str | None
    to_status: str
    note: str
    at: datetime
