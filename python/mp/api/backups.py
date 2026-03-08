import gzip
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url

from mp.api.auth import get_current_user
from mp.db.core import DATABASE_URL
from mp.db import get_db
from mp.schema.user import User

router = APIRouter(prefix="/backups", tags=["backups"])

BACKUP_TRIGGER_FILE = Path("/app/backups/.trigger-now")
BACKUP_FILE_PREFIX = "pgdump"
BACKUP_PROCESS_TIMEOUT_SECONDS = 300
UNSUPPORTED_SET_PATTERNS = [
    re.compile(
        rb"^\s*SET\s+transaction_timeout\s*=\s*[^;]+;\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
]


def _require_admin(current_user: User) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def _db_cli_env() -> dict[str, str]:
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL is not configured")
    url = make_url(DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        raise HTTPException(status_code=500, detail="Unsupported database driver")
    if not url.database:
        raise HTTPException(status_code=500, detail="Database name is missing")
    env = os.environ.copy()
    env["PGHOST"] = url.host or "database"
    env["PGPORT"] = str(url.port or 5432)
    env["PGUSER"] = url.username or ""
    env["PGPASSWORD"] = url.password or ""
    env["PGDATABASE"] = url.database
    return env


def _backup_filename(database_name: str) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{BACKUP_FILE_PREFIX}-{database_name}-{ts}.sql.gz"


def _sanitize_sql_for_restore(sql_payload: bytes) -> bytes:
    sanitized = sql_payload
    for pattern in UNSUPPORTED_SET_PATTERNS:
        sanitized = pattern.sub(b"", sanitized)
    return sanitized


def _release_request_db_session(db: Session) -> None:
    # Restore operations drop/recreate objects. Keep no ORM transaction open
    # from this request, otherwise PostgreSQL lock waits can stall restore.
    try:
        db.rollback()
    except Exception:
        pass
    try:
        db.close()
    except Exception:
        pass


@router.post("/run-now")
def run_backup_now(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    _require_admin(current_user)
    try:
        BACKUP_TRIGGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        BACKUP_TRIGGER_FILE.write_text(
            datetime.now(tz=timezone.utc).isoformat(), encoding="utf-8"
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Unable to schedule backup trigger",
        ) from exc
    return {
        "status": "scheduled",
        "trigger_file": str(BACKUP_TRIGGER_FILE),
    }


@router.post("/site/export")
def export_site_backup(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    _require_admin(current_user)
    _release_request_db_session(db)
    env = _db_cli_env()
    try:
        dump_proc = subprocess.run(
            [
                "pg_dump",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                env["PGDATABASE"],
            ],
            env=env,
            check=False,
            capture_output=True,
            timeout=BACKUP_PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="pg_dump timed out") from exc
    if dump_proc.returncode != 0:
        detail = dump_proc.stderr.decode("utf-8", errors="replace").strip()
        raise HTTPException(
            status_code=500,
            detail=f"pg_dump failed: {detail or 'unknown error'}",
        )
    try:
        gzip_proc = subprocess.run(
            ["gzip", "-9", "-c"],
            input=dump_proc.stdout,
            check=False,
            capture_output=True,
            timeout=BACKUP_PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504, detail="gzip compression timed out"
        ) from exc
    if gzip_proc.returncode != 0:
        detail = gzip_proc.stderr.decode("utf-8", errors="replace").strip()
        raise HTTPException(
            status_code=500,
            detail=f"gzip failed: {detail or 'unknown error'}",
        )

    filename = _backup_filename(env["PGDATABASE"])
    return Response(
        content=gzip_proc.stdout,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/site/restore")
async def restore_site_backup(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _require_admin(current_user)
    _release_request_db_session(db)
    env = _db_cli_env()
    suffix = ".backup"
    fd, temp_path = tempfile.mkstemp(prefix="site-restore-", suffix=suffix)
    os.close(fd)
    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Backup file is empty")
        with open(temp_path, "wb") as out:
            out.write(raw)
        is_gzip = len(raw) >= 2 and raw[0] == 0x1F and raw[1] == 0x8B
        if is_gzip:
            try:
                sql_payload = gzip.decompress(raw)
            except OSError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid gzip backup payload: {str(exc) or 'decompress failed'}",
                ) from exc
            sql_payload = _sanitize_sql_for_restore(sql_payload)
            try:
                psql_proc = subprocess.run(
                    ["psql", "--set", "ON_ERROR_STOP=1", "--dbname", env["PGDATABASE"]],
                    env=env,
                    input=sql_payload,
                    capture_output=True,
                    check=False,
                    timeout=BACKUP_PROCESS_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(
                    status_code=504,
                    detail="Restore timed out while applying gzip backup",
                ) from exc
            if psql_proc.returncode != 0:
                detail = psql_proc.stderr.decode("utf-8", errors="replace").strip()
                raise HTTPException(
                    status_code=500,
                    detail=f"psql restore failed: {detail or 'unknown error'}",
                )
        else:
            sql_payload = _sanitize_sql_for_restore(raw)
            try:
                psql_proc = subprocess.run(
                    ["psql", "--set", "ON_ERROR_STOP=1", "--dbname", env["PGDATABASE"]],
                    env=env,
                    input=sql_payload,
                    capture_output=True,
                    check=False,
                    timeout=BACKUP_PROCESS_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                raise HTTPException(
                    status_code=504,
                    detail="Restore timed out while applying plain SQL backup",
                ) from exc
            if psql_proc.returncode != 0:
                detail = psql_proc.stderr.decode("utf-8", errors="replace").strip()
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Restore payload is neither valid gzip SQL nor valid plain SQL: "
                        f"{detail or 'unknown error'}"
                    ),
                )
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
    return {"status": "restored"}
