# Backup and disaster recovery

## Backup design

`ops/backup/backup.sh` creates a PostgreSQL custom-format dump, verifies its catalog, encrypts it with AES-256-CBC/PBKDF2, writes SHA-256 integrity metadata, then optionally uploads both files to any AWS S3-compatible off-server destination. Plaintext is removed on exit and the process uses a restrictive umask.

A backup is production-complete only when `BACKUP_S3_URI` and valid object-storage credentials are configured. Local encrypted cache is operational convenience, not disaster recovery. Enable provider-side versioning/immutability when available and keep encryption credentials outside the VPS.

Start daily scheduling:

```bash
docker compose --env-file .env.production -f compose.production.yaml --profile backup up -d backup
```

Run a manual backup without starting the scheduler:

```bash
docker compose --env-file .env.production -f compose.production.yaml run --rm --entrypoint /opt/backup/backup.sh backup
```

Review `/backups/backup.log` inside the backup volume and verify that a recent encrypted object and checksum exist off-server. Default interval is 86,400 seconds and local retention is 14 days.

## Restore drill — never target production

1. Download an encrypted dump and matching `.sha256` into a temporary directory.
2. Create a new disposable PostgreSQL database name, such as `tetrova_restore_drill_YYYYMMDD`.
3. Mount the temporary directory into the backup container and run:

```bash
docker compose --env-file .env.production -f compose.production.yaml run --rm \
  --entrypoint /opt/backup/restore.sh \
  -e BACKUP_FILE=/restore/tetrova-TIMESTAMP.dump.enc \
  -e RESTORE_DATABASE=tetrova_restore_drill_YYYYMMDD \
  -e PGDATABASE=tetrova_pos \
  -v /absolute/temporary/restore:/restore:ro backup
```

The restore script refuses the configured source database and any existing target database by default, validates database-name syntax, checksum, decryption and dump catalog, restores with stop-on-error, and reports Alembic version plus counts for customers, examinations, invoices, payments, movements and orders. `RESTORE_ALLOW_EXISTING=true` is an explicit destructive override reserved for a verified disposable target.

4. Run the application against the restored database in an isolated environment.
5. Verify representative tenant records, finalized prescriptions, invoice/payment totals, stock balance versus movement ledger, order snapshots/status, refund/credit totals and the financial report for a known date range.
6. Record duration and evidence, then drop only the explicitly named disposable drill database.

## Objectives and limitations

- **RPO:** up to the configured backup interval (24 hours by default). Reduce the interval or add managed/WAL continuous recovery for a smaller RPO.
- **RTO:** restore duration plus validation and DNS/application recovery. Measure with the real dataset; no fixed RTO is promised.
- Custom dumps are logical backups, not point-in-time recovery. They do not include Caddy state, environment secrets or exported documents.
- Perform a restore drill at least quarterly and after PostgreSQL/backup-tool upgrades.
