#!/bin/sh
set -eu

umask 077
: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}"

backup_dir="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
name="tetrova-${timestamp}.dump"
plain="${backup_dir}/${name}"
encrypted="${plain}.enc"
log="${backup_dir}/backup.log"
status_file="${backup_dir}/last-backup-status"
completed=false

mkdir -p "$backup_dir"
cleanup() {
  result=$?
  rm -f "$plain"
  if [ "$completed" != "true" ]; then
    failed_at="$(date -u +%Y%m%dT%H%M%SZ)"
    printf '%s backup_failed exit_code=%s\n' "$failed_at" "$result" >> "$log"
    printf 'status=failed\ntimestamp=%s\n' "$failed_at" > "$status_file"
  fi
}
trap cleanup EXIT INT TERM

printf '%s backup_started database=%s\n' "$timestamp" "$PGDATABASE" >> "$log"
pg_dump --format=custom --no-owner --no-privileges --file="$plain"
pg_restore --list "$plain" >/dev/null
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE -in "$plain" -out "$encrypted"
(cd "$backup_dir" && sha256sum "$(basename "$encrypted")" > "$(basename "$encrypted").sha256")

if [ -n "${BACKUP_S3_URI:-}" ]; then
  command -v aws >/dev/null 2>&1 || { printf '%s backup_failed reason=aws_cli_missing\n' "$timestamp" >> "$log"; exit 1; }
  aws s3 cp "$encrypted" "${BACKUP_S3_URI%/}/$(basename "$encrypted")" --only-show-errors
  aws s3 cp "${encrypted}.sha256" "${BACKUP_S3_URI%/}/$(basename "$encrypted").sha256" --only-show-errors
  destination="encrypted_off_server"
else
  destination="local_only_warning"
fi

find "$backup_dir" -type f \( -name 'tetrova-*.dump.enc' -o -name 'tetrova-*.dump.enc.sha256' \) \
  -mtime "+$retention_days" -delete
printf '%s backup_succeeded file=%s destination=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$(basename "$encrypted")" "$destination" >> "$log"
printf 'status=succeeded\ntimestamp=%s\nfile=%s\ndestination=%s\n' \
  "$(date -u +%Y%m%dT%H%M%SZ)" "$(basename "$encrypted")" "$destination" > "$status_file"
completed=true
printf '%s\n' "$encrypted"
