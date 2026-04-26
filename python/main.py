from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mp.config import external_api_root_path, public_url_origin
from mp.db import run_database_upgrades
from mp.api.auth import initialize_session_signing_key
from mp.contracts.scheduler import start_contract_scheduler, stop_contract_scheduler
from mp.organization_defaults import ensure_default_organizations_loaded
from mp.db.sample_data import ensure_example_data_for_opted_in_users

# FastAPI
configured_public_origin = public_url_origin()
cors_origins = [configured_public_origin] if configured_public_origin else ["*"]
app: FastAPI = FastAPI(root_path=external_api_root_path())
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIs
for name in [
    "auth",
    "admin",
    "accounts",
    "widgets",
    "contracts",
    "expenses",
    "investments",
    "logs",
    "data_portability",
    "backups",
]:
    mod = import_module(f"mp.api.{name}")
    router = getattr(mod, "router")
    app.include_router(router)


@app.on_event("startup")
def startup_event() -> None:
    initialize_session_signing_key()
    run_database_upgrades()
    ensure_default_organizations_loaded()
    ensure_example_data_for_opted_in_users()
    start_contract_scheduler()


@app.on_event("shutdown")
def shutdown_event() -> None:
    stop_contract_scheduler()
