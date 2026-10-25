# Phase 7 verification

Phase 7.2 verification date: 25 October 2026. Baseline: `5e2d08f`.

## Implemented controls

- JWT issuer/audience/claim validation and persistent logout revocation
- Persistent account lockout with configurable threshold/duration
- Database-backed session-generation invalidation for credential, role and activation changes
- Fail-closed production secret, database, CORS, trusted-host and bootstrap validation
- API no-store and browser security headers
- Separate migration-owner and runtime CRUD database identities
- Internal-only PostgreSQL production network
- Caddy HTTPS reverse proxy, resource limits, health checks, restart policy and log rotation
- Encrypted verified backup, optional off-server upload, configurable schedule/retention and guarded restore
- Restore reconciliation SQL, backup status/health reporting and lightweight host monitoring

The Phase 7.2 result table and recovery/resource measurements below must be refreshed from the current verification run before acceptance; older Phase 7 measurements are retained only as a comparison baseline.

## Test results

| Check | Result |
| --- | --- |
| PostgreSQL backend suite | 91 passed, including all financial and order concurrency tests |
| SQLite compatibility | 82 passed; 9 PostgreSQL-only concurrency tests skipped |
| Security regressions | Passed: expiry/signature rejection, logout, session-generation invalidation, lockout, forced replacement, RBAC, sensitive-field masking and production config rejection |
| Frontend Vitest | 15 passed in 3 files |
| TypeScript and production build | Passed; 1,956 modules transformed |
| Ruff lint/format | Passed; 86 Python files |
| Shell syntax and Compose configuration | Passed |
| SQLite/PostgreSQL migration | Passed from empty database to `0015_session_invalidation` |
| Alembic head/drift | One head; no drift on SQLite or PostgreSQL |
| Fresh image builds | API, web and backup images passed; first combined attempt hit a transient Docker Hub TLS timeout, retry passed |
| Fresh image smoke | API health/readiness and web HTTP returned 200 |
| Caddy validation | Pinned `caddy:2.10-alpine` downloaded; `caddy validate` passed after correcting pre-existing one-line block syntax |

## Recovery drill

The source and target were separate disposable databases: `tetrova_phase72_source` and `tetrova_phase72_restore`. Fictional data covered one customer, finalized examination, stocked-frame checkout, partial payment and linked optical order.

- Encrypted dump creation included `pg_restore --list`, AES-256/PBKDF2 encryption and SHA-256 metadata; the restore verified all three layers successfully.
- Both databases reported migration `0015_session_invalidation`.
- Source and restored reconciliation matched exactly: customer `1`, examination `1`, invoice `1`, invoice total `800000`, payment `300000`, outstanding `500000`, inventory balance `2`, movement quantity sum `2`, optical order `1`.
- Restore SQL also passed invoice-equation, inventory-ledger, employee-tenant, examination-tenant and order-tenant integrity checks.
- Off-server upload was not executed because no real object-store credentials were supplied. Production acceptance requires a real upload/download drill.

These timings reflect a tiny test dataset and are not production RTO evidence.

## Resource and latency measurements

- Fresh FastAPI image: **67.25 MiB**
- Fresh Nginx web image: **20.91 MiB**
- Fresh backup image: **149.13 MiB**
- Pinned Caddy image: **20.46 MiB**
- Running API: **77.52 MiB**; Nginx web: **10.98 MiB**; PostgreSQL with several disposable test databases: **366.2 MiB**
- Local response times: API health **8.7 ms**, database readiness **8.6 ms**, web **2.8 ms**

The measured running development core was approximately **455 MiB**, excluding Caddy and an active backup job. Production limits allow 640 MiB PostgreSQL, 384 MiB API, 96 MiB web and 128 MiB proxy; migration/backup jobs are separately capped at 256 MiB. A 2 GB VPS remains a reasonable acceptance-test target for one shop, provided migration and backup jobs do not overlap and swap/memory/disk are monitored. This was a local macOS Docker Desktop test with fictional low-volume data—not a production load test. Reassess with realistic concurrent users and database size before promising capacity.

## Limitations

- No public deployment, real DNS, ACME certificate issuance, firewall or SSH change was performed.
- No public TLS issuance or full proxy-to-application production-domain smoke test was performed.
- No penetration test, browser security scanner or legal compliance assessment was performed.
- Password-reset email, distributed IP throttling, point-in-time recovery and centralized error aggregation remain future enhancements.
