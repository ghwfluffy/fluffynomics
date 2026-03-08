import secrets
import string
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.schema.registration_code import (
    RegistrationCode,
    RegistrationCodeCreateSchema,
    RegistrationCodeSchema,
    RegistrationCodeUpdateSchema,
)
from mp.schema.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

ALPHANUMERIC = string.ascii_uppercase + string.digits
REGISTRATION_CODE_LENGTH = 32


def _require_admin(current_user: User) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _new_registration_code() -> str:
    return "".join(
        secrets.choice(ALPHANUMERIC) for _ in range(REGISTRATION_CODE_LENGTH)
    )


@router.get("/registration-codes", response_model=list[RegistrationCodeSchema])
def list_registration_codes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RegistrationCodeSchema]:
    _require_admin(current_user)
    rows = db.query(RegistrationCode).order_by(RegistrationCode.created_at.desc()).all()
    return [RegistrationCodeSchema.model_validate(item) for item in rows]


@router.post("/registration-codes", response_model=RegistrationCodeSchema)
def create_registration_code(
    payload: RegistrationCodeCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegistrationCodeSchema:
    _require_admin(current_user)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    generated = ""
    for _ in range(8):
        candidate = _new_registration_code()
        exists = (
            db.query(RegistrationCode.id)
            .filter(RegistrationCode.code == candidate)
            .first()
        )
        if exists is None:
            generated = candidate
            break
    if not generated:
        raise HTTPException(
            status_code=500, detail="Unable to generate unique registration code"
        )

    now = datetime.now(tz=timezone.utc)
    record = RegistrationCode(
        code=generated,
        name=name,
        expires_at=payload.expires_at,
        created_by_user_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return RegistrationCodeSchema.model_validate(record)


@router.put("/registration-codes/{code_id}", response_model=RegistrationCodeSchema)
def update_registration_code(
    code_id: UUID,
    payload: RegistrationCodeUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RegistrationCodeSchema:
    _require_admin(current_user)
    record = db.get(RegistrationCode, code_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registration code not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return RegistrationCodeSchema.model_validate(record)
    if "name" in data:
        name = (payload.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        record.name = name
    if "expires_at" in data:
        record.expires_at = payload.expires_at
    record.updated_at = datetime.now(tz=timezone.utc)
    db.add(record)
    db.commit()
    db.refresh(record)
    return RegistrationCodeSchema.model_validate(record)


@router.delete("/registration-codes/{code_id}", status_code=204)
def delete_registration_code(
    code_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    record = db.get(RegistrationCode, code_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registration code not found")
    db.delete(record)
    db.commit()
    return None
