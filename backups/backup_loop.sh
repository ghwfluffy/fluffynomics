#!/bin/sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION="${BACKUP_RETENTION:-100}"
BACKUP_UID="${BACKUP_UID:-1000}"
BACKUP_GID="${BACKUP_GID:-1000}"
BACKUP_HOUR_UTC="${BACKUP_HOUR_UTC:-02}"
BACKUP_MINUTE_UTC="${BACKUP_MINUTE_UTC:-00}"
TRIGGER_FILE="${BACKUP_TRIGGER_FILE:-${BACKUP_DIR}/.trigger-now}"
STATE_FILE="${BACKUP_DIR}/.last-nightly-run"

mkdir -p "${BACKUP_DIR}"

run_backup() {
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  filename="pgdump-${PGDATABASE}-${ts}.sql.gz"
  filepath="${BACKUP_DIR}/${filename}"
  tmpfile="${filepath}.tmp"

  pg_dump --clean --if-exists --no-owner --no-privileges "${PGDATABASE}" | gzip -9 > "${tmpfile}"
  mv "${tmpfile}" "${filepath}"
  chown "${BACKUP_UID}:${BACKUP_GID}" "${filepath}" || true

  # Retain only the newest N backups.
  list="$(ls -1t "${BACKUP_DIR}"/pgdump-*.sql.gz 2>/dev/null || true)"
  i=0
  echo "${list}" | while IFS= read -r file; do
    [ -n "${file}" ] || continue
    i=$((i + 1))
    if [ "${i}" -gt "${RETENTION}" ]; then
      rm -f "${file}"
    fi
  done
}

while true; do
  now_day="$(date -u +%Y-%m-%d)"
  now_hour="$(date -u +%H)"
  now_minute="$(date -u +%M)"
  last_day="$(cat "${STATE_FILE}" 2>/dev/null || true)"

  if [ -f "${TRIGGER_FILE}" ]; then
    rm -f "${TRIGGER_FILE}"
    run_backup
  fi

  if [ "${now_hour}" = "${BACKUP_HOUR_UTC}" ] && [ "${now_minute}" = "${BACKUP_MINUTE_UTC}" ] && [ "${last_day}" != "${now_day}" ]; then
    run_backup
    echo "${now_day}" > "${STATE_FILE}"
  fi

  sleep 30
done
