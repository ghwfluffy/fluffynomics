from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    Boolean,
    LargeBinary,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mp.schema.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    account_number: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    organization: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    balance_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fee_amount_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fee_period: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    routing_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apy_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    compound_period: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apr_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    billing_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cvc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usd_balance_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retirement_account_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_amount_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    icon_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("icon_assets.id"), nullable=True
    )
    icon_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'Icon'")
    )
    rank: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    last_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IconAsset(Base):
    __tablename__ = "icon_assets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    png_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    icon_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("icon_assets.id"), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DefaultIcon(Base):
    __tablename__ = "default_icons"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    icon_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("icon_assets.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccountStockPosition(Base):
    __tablename__ = "account_stock_positions"

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stock_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)


class AccountCryptoPosition(Base):
    __tablename__ = "account_crypto_positions"

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)


class AccountCashDenomination(Base):
    __tablename__ = "account_cash_denominations"

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    denomination_cents: Mapped[int] = mapped_column(Integer, primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class PositionStockSchema(BaseModel):
    stock_id: UUID
    quantity: Decimal


class PositionCryptoSchema(BaseModel):
    ticker: str
    quantity: Decimal


class CashBillSchema(BaseModel):
    denomination_cents: int
    quantity: int


class AccountBaseSchema(BaseModel):
    account_number: str
    name: str
    type: str
    organization: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None

    balance_cents: Optional[int] = None
    fee_amount_cents: Optional[int] = None
    fee_period: Optional[str] = None
    routing_number: Optional[str] = None
    apy_bps: Optional[int] = None
    compound_period: Optional[str] = None
    apr_bps: Optional[int] = None
    billing_day: Optional[int] = None
    payment_day: Optional[int] = None
    expiration_date: Optional[date] = None
    cvc: Optional[str] = None
    usd_balance_cents: Optional[int] = None
    retirement_account_type: Optional[str] = None
    payment_amount_cents: Optional[int] = None
    icon_id: Optional[UUID] = None
    icon_type: Literal["Letters", "Gravatar", "Icon"] = "Icon"

    stock_positions: list[PositionStockSchema] = []
    crypto_positions: list[PositionCryptoSchema] = []
    cash_bills: list[CashBillSchema] = []


class AccountCreateSchema(AccountBaseSchema):
    pass


class AccountUpdateSchema(BaseModel):
    account_number: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    organization: Optional[str] = None
    url: Optional[str] = None
    notes: Optional[str] = None
    balance_cents: Optional[int] = None
    fee_amount_cents: Optional[int] = None
    fee_period: Optional[str] = None
    routing_number: Optional[str] = None
    apy_bps: Optional[int] = None
    compound_period: Optional[str] = None
    apr_bps: Optional[int] = None
    billing_day: Optional[int] = None
    payment_day: Optional[int] = None
    expiration_date: Optional[date] = None
    cvc: Optional[str] = None
    usd_balance_cents: Optional[int] = None
    retirement_account_type: Optional[str] = None
    payment_amount_cents: Optional[int] = None
    icon_id: Optional[UUID] = None
    icon_type: Optional[Literal["Letters", "Gravatar", "Icon"]] = None
    stock_positions: Optional[list[PositionStockSchema]] = None
    crypto_positions: Optional[list[PositionCryptoSchema]] = None
    cash_bills: Optional[list[CashBillSchema]] = None


class AccountValueUpdateSchema(BaseModel):
    balance_cents: Optional[int] = None
    usd_balance_cents: Optional[int] = None
    stock_positions: Optional[list[PositionStockSchema]] = None
    crypto_positions: Optional[list[PositionCryptoSchema]] = None


class AccountRankUpdateSchema(BaseModel):
    rank: float


class IconUploadResponseSchema(BaseModel):
    id: UUID
    hash: str


class IconListItemSchema(BaseModel):
    id: UUID
    hash: str
    is_default: bool
    created_by_me: bool


class OrganizationSuggestionSchema(BaseModel):
    name: str
    icon_id: Optional[UUID] = None
    is_default: bool = False


class DefaultIconSchema(BaseModel):
    key: str
    label: str
    icon_id: UUID


class AccountSchema(AccountBaseSchema):
    id: UUID
    user_id: UUID
    rank: float
    created_at: datetime
    last_update: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AccountIconType(str, Enum):
    LETTERS = "Letters"
    GRAVATAR = "Gravatar"
    ICON = "Icon"


class StockBaseSchema(BaseModel):
    name: str
    ticker: str
    exchange: Optional[str] = None


class StockCreateSchema(StockBaseSchema):
    pass


class StockUpdateSchema(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    exchange: Optional[str] = None


class StockSchema(StockBaseSchema):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
