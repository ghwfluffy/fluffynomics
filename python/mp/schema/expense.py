from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mp.schema.base import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    icon_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("icon_assets.id"), nullable=True
    )
    icon_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'Icon'")
    )
    estimated_amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    linked_account_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    general_frequency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_expensed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_expensed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_date_is_static: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExpenseBaseSchema(BaseModel):
    name: str
    category: str
    icon_id: Optional[UUID] = None
    icon_type: Literal["Letters", "Gravatar", "Icon"] = "Icon"
    estimated_amount_cents: int = 0
    linked_account_id: Optional[UUID] = None
    enabled: bool = True
    general_frequency: Optional[str] = None
    last_expensed_date: Optional[date] = None
    next_expensed_date: Optional[date] = None
    next_date_is_static: bool = False


class ExpenseCreateSchema(ExpenseBaseSchema):
    linked_account_id: UUID


class ExpenseUpdateSchema(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    icon_id: Optional[UUID] = None
    icon_type: Optional[Literal["Letters", "Gravatar", "Icon"]] = None
    estimated_amount_cents: Optional[int] = None
    linked_account_id: Optional[UUID] = None
    enabled: Optional[bool] = None
    general_frequency: Optional[str] = None
    last_expensed_date: Optional[date] = None
    next_expensed_date: Optional[date] = None
    next_date_is_static: Optional[bool] = None


class ExpenseSchema(ExpenseBaseSchema):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
