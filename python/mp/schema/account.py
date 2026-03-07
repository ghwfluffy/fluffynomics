from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
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
    date_opened: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
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
    date_opened: Optional[date] = None
    last_update: Optional[datetime] = None

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
    date_opened: Optional[date] = None
    last_update: Optional[datetime] = None
    stock_positions: Optional[list[PositionStockSchema]] = None
    crypto_positions: Optional[list[PositionCryptoSchema]] = None
    cash_bills: Optional[list[CashBillSchema]] = None


class AccountSchema(AccountBaseSchema):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
