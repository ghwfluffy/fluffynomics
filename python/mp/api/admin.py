import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from mp.api.auth import _hash_password, get_current_user
from mp.db import get_db
from mp.schema.account import Account, AccountValueHistory, NetWorthDailySnapshot, Stock
from mp.schema.contract import Contract, ContractPosting
from mp.schema.expense import Expense
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
ADMIN_LOCKOUT_YEARS = 100


def _require_admin(current_user: User) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


class AdminUserSchema(BaseModel):
    id: UUID
    username: str
    is_admin: bool
    last_login_at: datetime | None
    password_changed_at: datetime | None
    created_at: datetime
    password_lockout_until: datetime | None
    model_config = ConfigDict(from_attributes=True)


class AdminUserPasswordUpdateSchema(BaseModel):
    new_password: str


class AdminUserLockUpdateSchema(BaseModel):
    locked: bool


class AdminUserAdminUpdateSchema(BaseModel):
    is_admin: bool


def _get_target_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _admin_count(db: Session) -> int:
    return db.query(User.id).filter(User.is_admin.is_(True)).count()


def _delete_user_owned_data(db: Session, user_id: UUID) -> None:
    db.query(RegistrationCode).filter(
        RegistrationCode.created_by_user_id == user_id
    ).delete(synchronize_session=False)
    db.query(Expense).filter(Expense.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(ContractPosting).filter(ContractPosting.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Contract).filter(Contract.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(AccountValueHistory).filter(AccountValueHistory.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(NetWorthDailySnapshot).filter(
        NetWorthDailySnapshot.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(Account).filter(Account.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Stock).filter(Stock.user_id == user_id).delete(synchronize_session=False)


def _new_registration_code() -> str:
    return "".join(
        secrets.choice(ALPHANUMERIC) for _ in range(REGISTRATION_CODE_LENGTH)
    )


@router.get("/users", response_model=list[AdminUserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AdminUserSchema]:
    _require_admin(current_user)
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [AdminUserSchema.model_validate(user) for user in users]


@router.put("/users/{user_id}/password", status_code=204)
def admin_update_user_password(
    user_id: UUID,
    payload: AdminUserPasswordUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    new_password = payload.new_password.strip()
    if not new_password:
        raise HTTPException(status_code=400, detail="new_password cannot be empty")
    target_user = _get_target_user(db, user_id)
    now = datetime.now(tz=timezone.utc)
    target_user.password_hash = _hash_password(new_password)
    target_user.password_changed_at = now
    target_user.failed_password_attempts = 0
    target_user.password_lockout_until = None
    target_user.updated_at = now
    db.add(target_user)
    db.commit()
    return None


@router.put("/users/{user_id}/lock", status_code=204)
def admin_update_user_lock(
    user_id: UUID,
    payload: AdminUserLockUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    target_user = _get_target_user(db, user_id)
    now = datetime.now(tz=timezone.utc)
    if payload.locked:
        target_user.failed_password_attempts = 10
        target_user.password_lockout_until = now + timedelta(
            days=365 * ADMIN_LOCKOUT_YEARS
        )
    else:
        target_user.failed_password_attempts = 0
        target_user.password_lockout_until = None
    target_user.updated_at = now
    db.add(target_user)
    db.commit()
    return None


@router.put("/users/{user_id}/admin", status_code=204)
def admin_update_user_admin(
    user_id: UUID,
    payload: AdminUserAdminUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    target_user = _get_target_user(db, user_id)
    if target_user.is_admin == payload.is_admin:
        return None
    if not payload.is_admin and target_user.is_admin and _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last admin")
    target_user.is_admin = payload.is_admin
    target_user.updated_at = datetime.now(tz=timezone.utc)
    db.add(target_user)
    db.commit()
    return None


@router.delete("/users/{user_id}", status_code=204)
def admin_delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    _require_admin(current_user)
    if current_user.id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Use Profile > Delete Account to delete your own account",
        )
    target_user = _get_target_user(db, user_id)
    if target_user.is_admin and _admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    _delete_user_owned_data(db, target_user.id)
    db.delete(target_user)
    db.commit()
    return None


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
