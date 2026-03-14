from __future__ import annotations

from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

from mp.contracts.engine import run_contract_simulation
from mp.db.core import SessionLocal
from mp.expenses.engine import run_expense_simulation
from mp.investments.engine import run_investment_simulation
from mp.schema.user import User

_scheduler: BackgroundScheduler | None = None


def _run_once() -> None:
    db = SessionLocal()
    try:
        users = db.query(User.id).all()
        for (user_id,) in users:
            run_contract_simulation(
                db,
                user_id,
                date.today(),
                apply=True,
                lock=True,
            )
            run_expense_simulation(
                db,
                user_id,
                date.today(),
                apply=True,
                lock=True,
            )
            run_investment_simulation(
                db,
                user_id,
                date.today(),
                apply=True,
                lock=True,
            )
        db.commit()
    finally:
        db.close()


def start_contract_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_once,
        trigger="interval",
        minutes=30,
        id="contracts-apply",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    _run_once()


def stop_contract_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
