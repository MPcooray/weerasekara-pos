# Phase 7 security audit

Audit baseline: commit `35f8442`. Scope: application and deployment configuration, not a legal compliance certification or external penetration test.

## Findings and disposition

### Critical

No critical application defect was identified. Existing tenant filters, server-side role checks, immutable financial ledgers, idempotency keys and PostgreSQL row locking remain intact.

### High — fixed

- **Tokens remained usable after logout.** Access tokens now contain required issuer, audience and JWT ID claims. Logout stores the JWT ID until expiry, and every authenticated request rejects revoked tokens.
- **No repeated-login protection.** Known accounts now use persistent, generic-response lockout after configurable failures. Lock state survives API restarts and is tenant/account scoped.
- **Production could start with weak configuration.** Startup now rejects short/example secrets, SQLite, HTTP/wildcard CORS, wildcard trusted hosts, bootstrap enablement and any production bootstrap password.
- **PostgreSQL was published by the development Compose file.** The production Compose file publishes only ports 80/443; PostgreSQL is on an internal network.
- **Backups and tested recovery were absent.** Encrypted, verified PostgreSQL backup/restore tools and an optional scheduled off-server uploader are included.

### Medium — mitigated or documented

- The browser keeps the short-lived access token in `sessionStorage`; this limits persistence but does not eliminate token theft if same-origin script execution occurs. Caddy now supplies a restrictive CSP and other browser headers. Moving to HttpOnly cookie sessions would be a future authentication redesign.
- Account lockout does not provide distributed source-IP throttling. The single-instance deployment is protected by account lockout; add edge rate limiting if exposed to sustained hostile traffic. Avoid lockout thresholds that enable easy denial of service.
- Revoked-token rows require periodic cleanup after expiry. Their bounded 30-minute default lifetime makes growth modest, but a maintenance cleanup should be scheduled.
- Password recovery is deliberately not implemented. Production recovery is an owner-authorized administrative operation with identity verification and forced password replacement; email reset requires a future trusted mail service and policy.
- Refresh tokens are deliberately not issued. Operators re-authenticate after the short access-token lifetime, avoiding a second long-lived credential and rotation store at this scale.
- The migration role remains the database owner, while the API uses a separate CRUD role. Credentials must be independently generated and protected.

### Low / operational

- Caddy and application logs intentionally omit request bodies, but operators must still restrict log access and retention.
- Exported CSV/PDF and printed records leave application access control once downloaded or printed. Store and destroy them under shop policy.
- No automatic customer/clinical deletion is provided because invoices, audit records and clinical history may require retention. Define retention and lawful deletion rules with Sri Lankan legal/privacy professionals.

## Control review

- Passwords use pwdlib's recommended Argon2 hashing and are never returned.
- SQLAlchemy parameterization is used; no user input is interpolated into application SQL.
- Pydantic validates API inputs; financial amounts use server calculations and integer minor units.
- Tenant IDs come from validated JWT/user state, and direct-ID isolation tests cover all major modules.
- Roles are enforced by backend endpoints; frontend visibility is not treated as authorization.
- CORS and trusted hosts are explicit in production. Caddy terminates TLS and adds HSTS, CSP, frame, MIME, referrer and permissions policies.
- Audit records cover business mutations. Login responses remain generic and do not reveal tenant/account existence.
- Customer, prescription, payment-reference and report responses are `Cache-Control: no-store` at the API boundary.

## Professional review required

Obtain legal advice for Sri Lankan privacy, health-record retention, employee access, breach response, customer consent and tax/accounting retention. This implementation does not claim automatic regulatory compliance.
