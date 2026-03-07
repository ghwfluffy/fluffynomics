from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mp.db import run_database_upgrades
from mp.api.auth import initialize_session_signing_key
from mp.sample_data import ensure_example_data_for_opted_in_users

# FastAPI
app: FastAPI = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIs
for name in [
    "auth",
    "accounts",
]:
    mod = import_module(f"mp.api.{name}")
    router = getattr(mod, "router")
    app.include_router(router)


@app.on_event("startup")
def startup_event() -> None:
    initialize_session_signing_key()
    run_database_upgrades()
    ensure_example_data_for_opted_in_users()
