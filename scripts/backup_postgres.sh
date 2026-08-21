#!/bin/sh
set -eu
mkdir -p /backups/daily /backups/weekly /backups/monthly
run_backup() {
  stamp="$(date -u +%Y%m%d_%H%M%S)"; daily="/backups/daily/frexo_${stamp}.sql.gz"
  echo "[backup] creating ${daily}"; pg_dump --no-owner --no-privileges | gzip -9 > "$daily"
  dow="$(date -u +%u)"; dom="$(date -u +%d)"
  [ "$dow" = "7" ] && cp "$daily" "/backups/weekly/frexo_${stamp}.sql.gz" || true
  [ "$dom" = "01" ] && cp "$daily" "/backups/monthly/frexo_${stamp}.sql.gz" || true
  find /backups/daily -type f -name '*.sql.gz' -mtime +7 -delete
  find /backups/weekly -type f -name '*.sql.gz' -mtime +35 -delete
  find /backups/monthly -type f -name '*.sql.gz' -mtime +100 -delete
  echo "[backup] completed"
}
if [ "${1:-}" = "--loop" ]; then while true; do run_backup || echo "[backup] FAILED"; sleep "${BACKUP_INTERVAL_SECONDS:-86400}"; done; else run_backup; fi
