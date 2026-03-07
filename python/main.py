from importlib import import_module

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    "accounts",
]:
    mod = import_module(f"mp.api.{name}")
    router = getattr(mod, "router")
    app.include_router(router)
