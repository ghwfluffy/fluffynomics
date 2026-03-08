from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from mp.api.auth import get_current_user
from mp.schema.user import User

router = APIRouter(prefix="/backups", tags=["backups"])

BACKUP_TRIGGER_FILE = Path("/app/backups/.trigger-now")


@router.post("/run-now")
def run_backup_now(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    _ = current_user
    try:
        BACKUP_TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        BACKUP_TRIGGER_FILE.write_text(
            datetime.now(tz=timezone.utc).isoformat(), encoding="utf-8"
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to schedule backup trigger",
        ) from exc
    return {
        "status": "scheduled",
        "trigger_file": str(BACKUP_TRIGGER_FILE),
    }
