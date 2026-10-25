#!/bin/sh
set -eu

interval="${BACKUP_INTERVAL_SECONDS:-86400}"
case "$interval" in *[!0-9]*|'') echo "BACKUP_INTERVAL_SECONDS must be an integer" >&2; exit 1;; esac
if [ "$interval" -lt 300 ]; then
  echo "BACKUP_INTERVAL_SECONDS must be at least 300" >&2
  exit 1
fi
mkdir -p "${BACKUP_DIR:-/backups}"

while true; do
  if ! /opt/backup/backup.sh; then
    printf '%s scheduled_backup_failed\n' "$(date -u +%Y%m%dT%H%M%SZ)" >> "${BACKUP_DIR:-/backups}/backup.log"
  fi
  sleep "$interval"
done
