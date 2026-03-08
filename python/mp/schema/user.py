from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mp.schema.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    example_data: Mapped[bool] = mapped_column(default=False, nullable=False)
    avatar_icon_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("icon_assets.id"), nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_password_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    password_lockout_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserSchema(BaseModel):
    id: UUID
    username: str
    example_data: bool
    is_admin: bool
    avatar_icon_id: Optional[UUID] = None
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreateSchema(BaseModel):
    username: str
    password: str
    add_example_data: bool = False
    registration_code: str | None = None


class LoginSchema(BaseModel):
    username: str
    password: str
    session_seconds: int | None = None


class LoginResponseSchema(BaseModel):
    user: UserSchema
    session_token: str


class ProfileUpdateSchema(BaseModel):
    avatar_icon_id: Optional[UUID] = None
    current_password: str | None = None
    new_password: str | None = None
