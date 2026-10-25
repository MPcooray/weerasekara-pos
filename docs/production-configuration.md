# Production configuration

Use `compose.production.yaml` with a private `.env.production` copied from `.env.production.example`. Never copy example values unchanged.

## Required secrets and identities

- Generate `SECRET_KEY` with at least 48 random characters, for example `openssl rand -base64 48`.
- Generate independent random passwords for `POSTGRES_PASSWORD`, `POSTGRES_APP_PASSWORD` and `BACKUP_ENCRYPTION_PASSPHRASE`.
- URL-encode database passwords when placing them in SQLAlchemy URLs.
- `MIGRATION_DATABASE_URL` uses the PostgreSQL owner only in the one-shot migration container.
- `DATABASE_URL` uses the restricted application role. PostgreSQL initialization grants CRUD/sequence access and default privileges but not schema ownership.
- Keep `.env.production` readable only by the deployment administrator (`chmod 600`). Do not put secrets in shell history, tickets or logs.

## Network and containers

Only Caddy exposes host ports. PostgreSQL has no host port. API/web are addressable only on Docker networks. Caddy obtains/renews certificates after `DOMAIN` resolves to the VPS and ports 80/443 are reachable.

The initial memory limits total approximately 1.75 GB at peak including backup/migration jobs. The scheduled backup profile adds up to 256 MB while running. Do not run backup and migration concurrently on a memory-constrained host.

## Runtime safeguards

- Production refuses development bootstrap credentials, wildcard hosts, insecure CORS and SQLite.
- Access tokens expire after 30 minutes by default and are revoked at logout.
- Five failed known-account attempts lock login for 15 minutes by default.
- API pool defaults to five persistent connections plus five overflow connections.
- JSON container logs rotate at 10 MB with five files per service.
- Never enable `ALLOW_INITIAL_ADMIN_BOOTSTRAP` in production. Create the first owner using an audited, one-time administrative procedure, then remove the mechanism/credentials.
- For an existing PostgreSQL volume, initialization scripts do not run again. Create/grant the application role under a reviewed maintenance procedure before switching `DATABASE_URL`; do not delete the volume to force initialization.

## Monitoring checklist

- Poll `https://DOMAIN/api/v1/health` and `/readiness` every minute from outside the VPS.
- Alert on container unhealthy/restart loops, HTTP failure, disk >75%, memory pressure, certificate expiry and missing successful backup within 26 hours.
- Use `docker stats --no-stream`, `df -h`, `docker compose ... ps`, and `tail`/log shipping appropriate to the budget.
- Configure the backup destination's object retention/versioning and an independent alert based on object age.
- A lightweight external uptime monitor plus systemd timers/scripts is sufficient initially; no paid metrics stack is required.
