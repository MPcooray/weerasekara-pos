#!/bin/sh
set -eu

: "${PUBLIC_BASE_URL:?PUBLIC_BASE_URL is required, for example https://pos.example.com}"
disk_limit="${DISK_USAGE_ALERT_PERCENT:-75}"
backup_status="${BACKUP_STATUS_FILE:-}"
failed=0

check_url() {
  label="$1"
  url="$2"
  if curl --fail --silent --show-error --max-time 10 "$url" >/dev/null; then
    printf '%s status=ok check=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$label"
  else
    printf '%s status=failed check=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$label" >&2
    failed=1
  fi
}

check_url api_health "${PUBLIC_BASE_URL%/}/api/v1/health"
check_url api_readiness "${PUBLIC_BASE_URL%/}/api/v1/readiness"
check_url web "${PUBLIC_BASE_URL%/}/"

disk_used="$(df -P / | awk 'NR==2 {gsub(/%/, "", $5); print $5}')"
if [ "$disk_used" -ge "$disk_limit" ]; then
  printf '%s status=failed check=disk used_percent=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$disk_used" >&2
  failed=1
else
  printf '%s status=ok check=disk used_percent=%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$disk_used"
fi

if [ -n "$backup_status" ]; then
  if [ ! -r "$backup_status" ] || ! grep -q '^status=succeeded$' "$backup_status"; then
    printf '%s status=failed check=backup\n' "$(date -u +%Y%m%dT%H%M%SZ)" >&2
    failed=1
  else
    printf '%s status=ok check=backup\n' "$(date -u +%Y%m%dT%H%M%SZ)"
  fi
fi

exit "$failed"
