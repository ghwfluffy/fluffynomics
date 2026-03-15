from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from mp.schema.audit_log import AuditLogEvent, AuditLogTriggerType


def format_cents(value_cents: int, *, signed: bool = False) -> str:
    value = int(value_cents or 0)
    absolute = abs(value) / 100
    if signed:
        if value > 0:
            return f"+${absolute:,.2f}"
        if value < 0:
            return f"-${absolute:,.2f}"
    prefix = "-" if value < 0 else ""
    return f"{prefix}${absolute:,.2f}"


def record_audit_log(
    db: Session,
    user_id: UUID,
    *,
    trigger_type: AuditLogTriggerType,
    event_type: str,
    message: str,
    details: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> None:
    event = AuditLogEvent(
        user_id=user_id,
        trigger_type=trigger_type,
        event_type=event_type,
        message=message,
        details_json=details or {},
    )
    if occurred_at is not None:
        event.occurred_at = occurred_at
    db.add(event)
