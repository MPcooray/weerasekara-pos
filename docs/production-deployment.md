# DigitalOcean Ubuntu deployment procedure

No deployment is performed by this document.

## Prepare the VPS

1. Create a supported Ubuntu LTS VPS with SSH keys only. Start at 2 GB RAM only after reviewing the measured resource section in `phase-7-verification.md`.
2. Create a non-root sudo deployment user. Disable SSH password and root login; apply security updates and automatic security patches.
3. Configure the cloud firewall and UFW: allow SSH only from trusted administrative IPs where practical, and allow public TCP 80/443 plus UDP 443. Do not allow PostgreSQL 5432.
4. Install Docker Engine and the Compose plugin from Docker's official Ubuntu repository. Restrict membership of the Docker group because it is root-equivalent.
5. Point the chosen domain's A/AAAA records to the VPS. Do not continue HTTPS startup until DNS is correct.

## Install and start

```bash
git clone <private-repository-url> /opt/tetrova-pos
cd /opt/tetrova-pos
cp .env.production.example .env.production
chmod 600 .env.production
# Edit every placeholder and set the real domain, HTTPS CORS origin and strong secrets.
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml build
docker compose --env-file .env.production -f compose.production.yaml up -d db migrate api web proxy
docker compose --env-file .env.production -f compose.production.yaml --profile backup up -d backup
```

Verify `docker compose ... ps`, migration completion, `https://DOMAIN/api/v1/health`, readiness, login, a read-only report and backup upload. Do not expose the bootstrap password. Establish the first owner through an audited one-time procedure.

## Updates

1. Confirm a successful off-server backup and tested rollback artifact.
2. Pull the reviewed commit and rebuild images.
3. Run the one-shot migration service, then recreate API/web/proxy.
4. Run health checks and a financial read-only smoke test.
5. Keep the previous images/commit until verification completes.

## Rollback

Application-only rollback: return to the prior commit/images if its schema is forward-compatible. Never run an Alembic downgrade against production without reviewing data loss and taking a verified backup. If an incompatible migration failed, stop writes and restore the verified pre-update backup into a new database; point the prior application at that restored database after validation.

## Operations

- Review disk, memory, container health and backup age daily at launch.
- Apply OS/container security updates on a scheduled maintenance window.
- Rotate JWT/database/backup/object-store credentials after suspected exposure and on policy cadence.
- Restrict `.env.production`, backup passphrases, exports and database dumps to authorized administrators.
- Keep an incident contact list and a tested procedure for disabling access, preserving logs and notifying affected parties after professional review.
