from pydantic import BaseModel
from typing import Optional
from datetime import datetime

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

from sqlalchemy import Column, Integer, BigInteger, String, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

from schema.base import Base

class Account(Base):
    __tablename__ = 'accounts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    balance: Mapped[int] = mapped_column(BigInteger)
    apr: Mapped[int] = mapped_column(Integer)
    url: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP)
