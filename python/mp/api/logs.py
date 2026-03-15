from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.schema.audit_log import AuditLogEvent, AuditLogEventSchema
from mp.schema.user import User

router = APIRouter()


@router.get("/logs", response_model=list[AuditLogEventSchema])
def get_logs(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogEventSchema]:
    rows = (
        db.query(AuditLogEvent)
        .filter(AuditLogEvent.user_id == current_user.id)
        .order_by(AuditLogEvent.occurred_at.desc(), AuditLogEvent.id.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditLogEventSchema(
            id=row.id,
            user_id=row.user_id,
            trigger_type=row.trigger_type,  # type: ignore[arg-type]
            event_type=row.event_type,
            message=row.message,
            details=row.details_json or {},
            occurred_at=row.occurred_at,
        )
        for row in rows
    ]
