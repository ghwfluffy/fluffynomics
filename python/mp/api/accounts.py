from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from mp.schema.account import Account, AccountSchema
from mp.db import get_db

router = APIRouter()


@router.get("/accounts", response_model=List[AccountSchema])
def get_accounts(db: Session = Depends(get_db)) -> List[Account]:
    return db.query(Account).all()


@router.post("/accounts", response_model=AccountSchema)
def create_account(account: AccountSchema, db: Session = Depends(get_db)) -> Account:
    db_account = Account(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account
