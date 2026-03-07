from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import BigInteger, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


from mp.schema.base import Base


class AccountSchema(BaseModel):
    id: int
    name: str
    type: str
    balance: int
    apr: int
    url: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    balance: Mapped[int] = mapped_column(BigInteger)
    apr: Mapped[int] = mapped_column(Integer)
    url: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
