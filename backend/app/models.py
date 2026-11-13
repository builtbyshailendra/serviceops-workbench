"""Tables. The CHECK constraints repeat the most important rules in the database itself,
so a bug in the API can't store a request in a state that makes no sense."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DDL, BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class AuditEvent(Base):
    """One row per change, written in the same transaction as the change itself.

    A PostgreSQL trigger (below) refuses UPDATE and DELETE, so the history can
    only grow. Requests can't be deleted either while they have events, because
    of the foreign key.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("service_requests.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped[ServiceRequest] = relationship()


# SQLAlchemy passes DDL strings through Python "%" formatting, so this SQL avoids "%" entirely.
APPEND_ONLY = DDL(
    """
    CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
    BEGIN
      RAISE EXCEPTION USING MESSAGE = 'audit_events is append-only: ' || TG_OP || ' is not allowed';
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER audit_events_append_only
      BEFORE UPDATE OR DELETE ON audit_events
      FOR EACH ROW EXECUTE FUNCTION audit_events_append_only();
    """
)
event.listen(AuditEvent.__table__, "after_create", APPEND_ONLY)
