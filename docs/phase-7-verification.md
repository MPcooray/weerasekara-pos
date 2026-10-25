# Phase 7 verification

Verification date: 25 October 2026. Baseline: `35f8442`.

## Implemented controls

- JWT issuer/audience/claim validation and persistent logout revocation
- Persistent account lockout with configurable threshold/duration
- Fail-closed production secret, database, CORS, trusted-host and bootstrap validation
- API no-store and browser security headers
- Separate migration-owner and runtime CRUD database identities
- Internal-only PostgreSQL production network
- Caddy HTTPS reverse proxy, resource limits, health checks, restart policy and log rotation
- Encrypted verified backup, optional off-server upload, configurable schedule/retention and guarded restore

## Test results

| Check | Result |
| --- | --- |
| PostgreSQL backend suite | 80 passed, including financial and order concurrency tests |
| SQLite compatibility | 71 passed; 9 PostgreSQL-only concurrency tests skipped |
| Security regressions | Passed: lockout, reset, logout revocation, claims/config rejection and no-store headers |
| Frontend Vitest | 14 passed in 3 files |
| TypeScript and production build | Passed; 1,956 modules transformed |
| Ruff lint/format | Passed; 66 Python files |
| Shell syntax and Compose configuration | Passed |
| SQLite/PostgreSQL migration | Passed from empty database to `0013_auth_hardening` |
| Alembic head/drift | One head; no drift on SQLite or PostgreSQL |
| Fresh image builds | API, web and backup images passed |
| Fresh image smoke | API health/readiness and web HTTP returned 200 |
| Caddy runtime validation | Not completed: repeated Docker Hub EOF/TLS timeout while pulling `caddy:2.10-alpine` |

## Recovery drill

The source and target were separate disposable databases: `tetrova_phase7_source` and `tetrova_phase7_restore`. Fictional data covered one customer, finalized examination, stocked-frame checkout, partial payment and linked optical order.

- Encrypted dump creation and catalog verification: **0.63 seconds**.
- SHA-256 verification, decryption and restore: **0.76 seconds**.
- Both databases reported migration `0013_auth_hardening`.
- Source and restored reconciliation matched exactly: customer `1`, examination `1`, invoice `1`, invoice total `800000`, payment `300000`, outstanding `500000`, inventory balance `2`, movement quantity sum `2`, optical order `1`.
- Off-server upload was not executed because no real object-store credentials were supplied. Production acceptance requires a real upload/download drill.

These timings reflect a tiny test dataset and are not production RTO evidence.

## Resource and latency measurements

- Fresh FastAPI image: **74.89 MiB**
- Fresh Nginx web image: **11.08 MiB**
- PostgreSQL test container: **374.3 MiB**
- Local health latency: **58.5 ms**; database readiness: **44.8 ms**

The measured steady-state core was approximately 460 MiB. Production limits allow 640 MiB PostgreSQL, 384 MiB API, 96 MiB web and 128 MiB proxy; migration/backup jobs are separately capped at 256 MiB. A 2 GB VPS is a reasonable initial target for one shop given these measurements, provided backup and migration do not overlap and memory/disk are monitored. Reassess under realistic concurrent users and production data before promising capacity.

## Limitations

- No public deployment, real DNS, ACME certificate issuance, firewall or SSH change was performed.
- Caddy runtime validation remains blocked by Docker Hub connectivity; Compose and the Caddyfile were statically reviewed.
- No penetration test, browser security scanner or legal compliance assessment was performed.
- Password-reset email, distributed IP throttling, point-in-time recovery and centralized error aggregation remain future enhancements.
