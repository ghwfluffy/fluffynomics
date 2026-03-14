from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mp.schema.base import Base


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    source_account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    general_frequency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_invested_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_investment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_date_is_static: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InvestmentBaseSchema(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount_cents: int = 0
    enabled: bool = True
    general_frequency: Optional[str] = None
    last_invested_date: Optional[date] = None
    next_investment_date: Optional[date] = None
    next_date_is_static: bool = False


class InvestmentCreateSchema(InvestmentBaseSchema):
    pass


class InvestmentUpdateSchema(BaseModel):
    source_account_id: Optional[UUID] = None
    destination_account_id: Optional[UUID] = None
    amount_cents: Optional[int] = None
    enabled: Optional[bool] = None
    general_frequency: Optional[str] = None
    last_invested_date: Optional[date] = None
    next_investment_date: Optional[date] = None
    next_date_is_static: Optional[bool] = None


class InvestmentSchema(InvestmentBaseSchema):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
