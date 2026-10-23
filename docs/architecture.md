# Phase 0 architecture

## Decisions

1. **Modular monolith:** one deployable API, separated internally by domain. Later phases add `customers`, `examinations`, `inventory`, `sales`, `orders`, and `sync` modules without premature network boundaries.
2. **Shared interface:** React, TypeScript, and responsive CSS provide the UI reused by browsers, the PWA, and a future Tauri desktop wrapper.
3. **Tenant boundary:** every business-owned row carries `tenant_id`. Authenticated requests obtain tenant context from the signed access token, never from a client-selected header.
4. **Database portability:** SQLAlchemy 2 and Alembic target PostgreSQL while tests and local development can use SQLite. PostgreSQL remains the server source of truth.
5. **Money:** LKR is the tenant default. Transaction amounts will use integer minor units and immutable ledger-style payment records.
6. **Offline later:** sync is deliberately deferred until billing invariants exist. Domain records will use UUIDs, timestamps, and version counters suitable for an eventual outbox protocol.
7. **Clinical history:** finalized examinations are immutable. Corrections create draft records linked through `supersedes_id`; optimistic version checks prevent silent concurrent overwrites.

## Module dependency rule

HTTP routes depend on services; services depend on repositories/models. Domain modules may use shared core utilities but must not import HTTP concerns. Cross-domain writes will share one database transaction.

## Authentication

Phase 0 provides password login, Argon2 hashing, short-lived signed access tokens, roles, disabled-user checks, and tenant isolation. Refresh-token rotation, password reset, MFA, session revocation, and audit events are scheduled before production release.

## Environments

- Development: local Node/Python or Docker Compose
- Test: isolated SQLite database per test session
- Production: containerized API and static web assets, managed PostgreSQL, reverse proxy/TLS, secrets supplied by the deployment platform

