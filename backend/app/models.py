"""Tables. The CHECK constraints repeat the most important rules in the database itself,
so a bug in the API can't store a request in a state that makes no sense."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

STATUSES = ("new", "triaged", "approved", "rejected", "done")
CATEGORIES = ("access", "hardware", "software", "other")
PRIORITIES = ("low", "medium", "high")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ServiceRequest(Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint(_one_of("status", STATUSES), name="status_is_known"),
        CheckConstraint(_one_of("category", CATEGORIES), name="category_is_known"),
        CheckConstraint(f"priority IS NULL OR {_one_of('priority', PRIORITIES)}", name="priority_is_known"),
        # A request past triage has a priority.
        CheckConstraint("status = 'new' OR priority IS NOT NULL", name="triaged_has_priority"),
        # An approved, rejected or finished request records who decided and when.
        CheckConstraint(
            "status IN ('new', 'triaged') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="decision_has_who_and_when",
        ),
        # Nobody approves or rejects their own request.
        CheckConstraint("decided_by IS NULL OR decided_by <> requested_by", name="no_self_decision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20))
    requested_by: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="new")
    priority: Mapped[str | None] = mapped_column(String(10))
    decided_by: Mapped[str | None] = mapped_column(String(40))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
