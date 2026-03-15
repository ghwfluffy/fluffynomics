from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mp.schema.base import Base


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    automatic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    organization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("icon_assets.id"), nullable=True
    )
    icon_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'Icon'")
    )
    rank: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    linked_account_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_account_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_wallet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_period: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expiration_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("'2099-01-01'")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    billing_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContractPosting(Base):
    __tablename__ = "contract_postings"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    delta_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContractBaseSchema(BaseModel):
    name: str
    type: str
    automatic: bool = True
    amount_cents: int
    organization: Optional[str] = None
    icon_id: Optional[UUID] = None
    icon_type: Literal["Letters", "Gravatar", "Icon"] = "Icon"
    rank: Optional[float] = None
    linked_account_id: Optional[UUID] = None
    linked_wallet: Optional[Literal["paypal", "google_pay"]] = None
    source_account_id: Optional[UUID] = None
    last_payment_date: Optional[date] = None
    next_payment_date: Optional[date] = None
    payment_period: Optional[str] = None
    payment_day: Optional[int] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    account_number: Optional[str] = None
    billing_day: Optional[int] = None


class ContractCreateSchema(ContractBaseSchema):
    linked_account_id: Optional[UUID] = None


class ContractUpdateSchema(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    automatic: Optional[bool] = None
    amount_cents: Optional[int] = None
    organization: Optional[str] = None
    icon_id: Optional[UUID] = None
    icon_type: Optional[Literal["Letters", "Gravatar", "Icon"]] = None
    rank: Optional[float] = None
    linked_account_id: Optional[UUID] = None
    linked_wallet: Optional[Literal["paypal", "google_pay"]] = None
    source_account_id: Optional[UUID] = None
    last_payment_date: Optional[date] = None
    next_payment_date: Optional[date] = None
    payment_period: Optional[str] = None
    payment_day: Optional[int] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    account_number: Optional[str] = None
    billing_day: Optional[int] = None


class ContractSchema(ContractBaseSchema):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractRankUpdateSchema(BaseModel):
    rank: float
