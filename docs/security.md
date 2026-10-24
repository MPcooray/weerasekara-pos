# Security baseline

- Passwords are hashed with Argon2 and are never logged.
- JWTs contain a user ID, tenant ID, role, issued-at time, expiry, and unique token ID.
- Tenant identity is derived from the verified token.
- CORS is an explicit allow-list.
- API schemas do not return password hashes.
- Customer and visit lookups require both the record ID and authenticated tenant ID.
- Customer deletion is implemented as owner/manager-only archival; visit history remains intact.
- Customer and visit mutations create metadata-only audit records without copying sensitive fields.
- Production startup rejects placeholder or undersized signing secrets.
- Configuration comes from environment variables; `.env` is ignored.

Before production: add refresh-token rotation, rate limiting, audit logs, encrypted backups, MFA for owners, dependency scanning, CSP/security headers, and key rotation procedures.

## Tracked security limitations

- **SEC-001 — session revocation:** access tokens are short-lived but cannot yet be revoked server-side.
- **SEC-002 — refresh tokens:** refresh-token rotation and reuse detection are not implemented. Staff must sign in again after access-token expiry.

These items must be resolved before broad production rollout. Phase 2 adds metadata-only audit events for clinical record creation, access, updates, finalization, and superseding revisions. Full prescription values are intentionally excluded from general logs and audit rows.

## Development credentials

`.env`, SQLite databases, virtual environments, and build outputs are excluded from Git and Docker build contexts. The sample development administrator is not copied into container images. Production startup does not bootstrap an administrator unless `ALLOW_INITIAL_ADMIN_BOOTSTRAP=true` is deliberately supplied with non-sample credentials.

## Catalog and inventory permissions

- Owners and managers can create and edit products and suppliers and record stock movements.
- Optometrists and cashiers have read-only access to the catalog and availability.
- Every product, supplier, location, balance and movement query is tenant-scoped.
- Price changes and all inventory mutations create audit records.
- Archived products reject movements until an authorized owner or manager reactivates them.
- Stock writes use optimistic concurrency and reject stale balance versions and negative stock.

## Checkout permissions and isolation

- Owners, managers, and cashiers may confirm checkout; optometrists may only view invoices.
- Product, location, customer, prescription, invoice, idempotency, and stock queries are scoped to
  the authenticated tenant rather than accepting tenant identity from the client.
- Confirmation rejects stale client prices, archived products, insufficient stock, draft or
  mismatched prescriptions, and reused idempotency keys with a different payload.
- Invoice snapshots and stock deductions commit atomically. PostgreSQL row locks and unique
  constraints protect concurrent finalization; SQLite remains a local compatibility target, not
  the claimed concurrency authority.

