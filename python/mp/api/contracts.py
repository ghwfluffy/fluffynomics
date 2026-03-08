from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.recurring_period import parse_recurring_period
from mp.schema.account import Account, AccountIconType, Organization
from mp.schema.contract import (
    Contract,
    ContractCreateSchema,
    ContractRankUpdateSchema,
    ContractSchema,
    ContractUpdateSchema,
)
from mp.schema.user import User

router = APIRouter()

CONTRACT_TYPES = {"income", "payment", "transfer"}
LEGACY_RECURRING_PERIODS = {"daily", "weekly", "biweekly", "monthly", "yearly"}
DEFAULT_CONTRACT_EXPIRATION = date(2099, 1, 1)


def _validate_contract_type(contract_type: str) -> None:
    if contract_type not in CONTRACT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Unsupported contract type: {contract_type}"
        )


def _validate_last_payment_date(value: date | None) -> None:
    if value is None:
        return
    if value > date.today():
        raise HTTPException(
            status_code=400, detail="last_payment_date cannot be in the future"
        )


def _validate_expiration_date(value: date | None) -> None:
    if value is None:
        return
    if value < date(1900, 1, 1):
        raise HTTPException(status_code=400, detail="expiration_date is invalid")


def _validate_recurring_period(raw: str | None) -> None:
    if raw is None:
        return
    normalized = raw.strip()
    if not normalized:
        return
    if normalized.lower() in LEGACY_RECURRING_PERIODS:
        # Backward compatibility for older seeded/example rows.
        return
    try:
        parse_recurring_period(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _validate_contract_payload(
    payload: ContractCreateSchema,
    linked_account: Account | None,
    source_account: Account | None,
) -> None:
    _validate_contract_type(payload.type)
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if payload.organization is None or not payload.organization.strip():
        raise HTTPException(status_code=400, detail="organization is required")
    if linked_account is None:
        raise HTTPException(status_code=400, detail="linked_account_id is required")
    if payload.amount_cents < 0:
        raise HTTPException(status_code=400, detail="amount_cents must be >= 0")
    _validate_last_payment_date(payload.last_payment_date)
    _validate_expiration_date(payload.expiration_date)
    _validate_recurring_period(payload.payment_period)
    if payload.payment_day is None:
        raise HTTPException(status_code=400, detail="payment_day is required")
    if not (1 <= payload.payment_day <= 31):
        raise HTTPException(
            status_code=400, detail="payment_day must be in range 1..31"
        )
    if payload.billing_day is not None and not (1 <= payload.billing_day <= 31):
        raise HTTPException(
            status_code=400, detail="billing_day must be in range 1..31"
        )
    if payload.type == "transfer":
        if source_account is None:
            raise HTTPException(
                status_code=400, detail="source_account_id is required for transfers"
            )
        if source_account.id == linked_account.id:
            raise HTTPException(
                status_code=400,
                detail="source_account_id must be different from linked_account_id",
            )


def _validate_icon_type(icon_type: str | None) -> None:
    if icon_type is None:
        return
    if icon_type not in {item.value for item in AccountIconType}:
        raise HTTPException(
            status_code=400, detail=f"Unsupported icon_type: {icon_type}"
        )


def _coerce_icon_type(icon_type: str | None) -> Literal["Letters", "Gravatar", "Icon"]:
    if icon_type == AccountIconType.LETTERS.value:
        return AccountIconType.LETTERS.value
    if icon_type == AccountIconType.GRAVATAR.value:
        return AccountIconType.GRAVATAR.value
    return AccountIconType.ICON.value


def _normalize_icon_selection(
    icon_type: str | None,
    icon_id: UUID | None,
    organization: str | None,
    db: Session,
) -> tuple[Literal["Letters", "Gravatar", "Icon"], UUID | None]:
    normalized_type = _coerce_icon_type(icon_type)
    if normalized_type != AccountIconType.ICON.value:
        return normalized_type, None
    if icon_id is not None:
        return normalized_type, icon_id
    if organization:
        org = db.query(Organization).filter_by(name=organization.strip()).first()
        if org is not None:
            return normalized_type, org.icon_id
    return normalized_type, None


def _serialize_contract(contract: Contract) -> ContractSchema:
    return ContractSchema.model_validate(contract)


def _owned_account(
    db: Session, user_id: UUID, account_id: UUID | None
) -> Account | None:
    if account_id is None:
        return None
    return (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == user_id)
        .first()
    )


@router.get("/contracts", response_model=list[ContractSchema])
def get_contracts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ContractSchema]:
    rows = (
        db.query(Contract)
        .filter(Contract.user_id == current_user.id)
        .order_by(
            Contract.category.asc(), Contract.rank.desc(), Contract.created_at.desc()
        )
        .all()
    )
    return [_serialize_contract(row) for row in rows]


@router.post("/contracts", response_model=ContractSchema)
def create_contract(
    payload: ContractCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractSchema:
    linked_account = _owned_account(db, current_user.id, payload.linked_account_id)
    source_account = _owned_account(db, current_user.id, payload.source_account_id)
    _validate_contract_payload(payload, linked_account, source_account)
    _validate_icon_type(payload.icon_type)

    now = datetime.utcnow()
    max_rank = (
        db.query(func.max(Contract.rank))
        .filter(
            Contract.user_id == current_user.id,
            Contract.category == payload.category,
        )
        .scalar()
    )
    icon_type, icon_id = _normalize_icon_selection(
        payload.icon_type,
        payload.icon_id,
        payload.organization,
        db,
    )
    contract = Contract(
        user_id=current_user.id,
        name=payload.name.strip(),
        type=payload.type,
        automatic=payload.automatic,
        amount_cents=payload.amount_cents,
        organization=payload.organization.strip() if payload.organization else None,
        icon_id=icon_id,
        icon_type=icon_type,
        rank=payload.rank if payload.rank is not None else (max_rank or 0) + 1,
        linked_account_id=payload.linked_account_id,
        source_account_id=payload.source_account_id
        if payload.type == "transfer"
        else None,
        last_payment_date=payload.last_payment_date,
        payment_period=payload.payment_period,
        payment_day=payload.payment_day,
        expiration_date=payload.expiration_date or DEFAULT_CONTRACT_EXPIRATION,
        notes=payload.notes,
        category=(payload.category or "Financial"),
        url=payload.url,
        account_number=payload.account_number,
        billing_day=payload.billing_day,
        created_at=now,
        updated_at=now,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.put("/contracts/{contract_id}", response_model=ContractSchema)
def update_contract(
    contract_id: UUID,
    payload: ContractUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractSchema:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _serialize_contract(contract)
    if "type" in data and data["type"] != contract.type:
        raise HTTPException(
            status_code=400,
            detail="contract type is immutable; create a new contract to change type",
        )
    if "icon_type" in data:
        _validate_icon_type(data["icon_type"])

    merged = ContractCreateSchema(
        name=data.get("name", contract.name),
        type=data.get("type", contract.type),
        automatic=data.get("automatic", contract.automatic),
        amount_cents=data.get("amount_cents", contract.amount_cents),
        organization=data.get("organization", contract.organization),
        icon_id=data.get("icon_id", contract.icon_id),
        icon_type=data.get("icon_type", contract.icon_type),
        rank=data.get("rank", contract.rank),
        linked_account_id=data.get("linked_account_id", contract.linked_account_id),
        source_account_id=data.get("source_account_id", contract.source_account_id),
        last_payment_date=data.get("last_payment_date", contract.last_payment_date),
        payment_period=data.get("payment_period", contract.payment_period),
        payment_day=data.get("payment_day", contract.payment_day),
        expiration_date=data.get("expiration_date", contract.expiration_date),
        notes=data.get("notes", contract.notes),
        category=data.get("category", contract.category),
        url=data.get("url", contract.url),
        account_number=data.get("account_number", contract.account_number),
        billing_day=data.get("billing_day", contract.billing_day),
    )
    linked_account = _owned_account(db, current_user.id, merged.linked_account_id)
    source_account = _owned_account(db, current_user.id, merged.source_account_id)
    _validate_contract_payload(merged, linked_account, source_account)
    normalized_icon_type, normalized_icon_id = _normalize_icon_selection(
        merged.icon_type,
        merged.icon_id,
        merged.organization,
        db,
    )

    contract.name = merged.name.strip()
    contract.type = merged.type
    contract.automatic = merged.automatic
    contract.amount_cents = merged.amount_cents
    contract.organization = merged.organization.strip() if merged.organization else None
    contract.icon_id = normalized_icon_id
    contract.icon_type = normalized_icon_type
    contract.rank = merged.rank if merged.rank is not None else contract.rank
    contract.linked_account_id = merged.linked_account_id
    contract.source_account_id = (
        merged.source_account_id if merged.type == "transfer" else None
    )
    contract.last_payment_date = merged.last_payment_date
    contract.payment_period = merged.payment_period
    contract.payment_day = merged.payment_day
    contract.expiration_date = merged.expiration_date or DEFAULT_CONTRACT_EXPIRATION
    contract.notes = merged.notes
    contract.category = merged.category or "Financial"
    contract.url = merged.url
    contract.account_number = merged.account_number
    contract.billing_day = merged.billing_day
    contract.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.put("/contracts/{contract_id}/rank", response_model=ContractSchema)
def set_contract_rank(
    contract_id: UUID,
    payload: ContractRankUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractSchema:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    contract.rank = payload.rank
    contract.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contract)
    return _serialize_contract(contract)


@router.delete("/contracts/{contract_id}", status_code=204)
def delete_contract(
    contract_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.user_id == current_user.id)
        .first()
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    db.delete(contract)
    db.commit()
