#!/bin/sh
set -eu

umask 077
: "${BACKUP_FILE:?BACKUP_FILE is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}"
: "${PGHOST:?PGHOST is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${RESTORE_DATABASE:?RESTORE_DATABASE is required}"
case "$RESTORE_DATABASE" in *[!a-zA-Z0-9_]*) echo "Invalid RESTORE_DATABASE" >&2; exit 1;; esac

if [ "${PGDATABASE:-}" = "$RESTORE_DATABASE" ]; then
  echo "Refusing to restore over the configured source database" >&2
  exit 1
fi
if [ ! -f "$BACKUP_FILE" ] || [ ! -f "${BACKUP_FILE}.sha256" ]; then
  echo "Encrypted backup and checksum file are required" >&2
  exit 1
fi

backup_dir="$(dirname "$BACKUP_FILE")"
(cd "$backup_dir" && sha256sum -c "$(basename "$BACKUP_FILE").sha256")
plain="$(mktemp /tmp/tetrova-restore.XXXXXX)"
cleanup() { rm -f "$plain"; }
trap cleanup EXIT INT TERM
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE -in "$BACKUP_FILE" -out "$plain"
pg_restore --list "$plain" >/dev/null

exists="$(psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$RESTORE_DATABASE'")"
if [ "$exists" != "1" ]; then
  createdb "$RESTORE_DATABASE"
elif [ "${RESTORE_ALLOW_EXISTING:-false}" != "true" ]; then
  echo "Refusing to overwrite an existing restore database" >&2
  exit 1
fi
pg_restore --exit-on-error --no-owner --no-privileges --clean --if-exists \
  --dbname="$RESTORE_DATABASE" "$plain"
psql --dbname="$RESTORE_DATABASE" -v ON_ERROR_STOP=1 -c \
  "SELECT version_num AS alembic_version FROM alembic_version; SELECT COUNT(*) AS customers FROM customers; SELECT COUNT(*) AS examinations FROM examinations; SELECT COUNT(*) AS invoices FROM invoices; SELECT COUNT(*) AS payments FROM payments; SELECT COUNT(*) AS stock_movements FROM stock_movements; SELECT COUNT(*) AS optical_orders FROM optical_orders;"
