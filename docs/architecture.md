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

## Inventory consistency

Phase 3 stores money as integer LKR minor units. Stock changes pass through a single
transactional inventory service which atomically performs an optimistic version check,
updates the product/location balance, appends an immutable stock-movement record, and
writes an audit event. Negative balances are rejected by default. The balance is a fast
projection that can be reconciled against the sum of the movement ledger.

Inventory is location-scoped from its first release. Every tenant receives a default
`MAIN` location; later phases can add branches and transfer workflows without changing
the ledger shape.

## Financial foundation

All financial values are integer minor currency units. Draft invoices and quotations may
be edited; finalized invoice totals and line snapshots are protected from mutation and
financial corrections will be represented by payments, returns, and credit notes.

Invoice discounts are allocated across line net amounts using a deterministic
largest-remainder algorithm. Taxes are then rounded half-up per line using integer ratios.
Invoice numbering uses a tenant/year sequence row locked with `SELECT FOR UPDATE` on
PostgreSQL, while financial idempotency keys are unique per tenant and operation.

## Checkout consistency

Checkout previews are advisory; confirmation always reloads products, validates tenant-owned
customer/location/finalized-prescription references, and recalculates totals on the server.
Confirmation claims a tenant-scoped idempotency key, locks stock-bearing products and inventory
balances in UUID order, allocates the invoice number, stores immutable invoice snapshots, deducts
stock, appends invoice-linked stock movements, and records an audit event in one transaction.
Services and made-to-order products deliberately bypass stock deduction. A finalized sale begins
with zero paid and the full total outstanding; payment capture remains a later workflow.

## Payment consistency

Payments are immutable records of funds confirmed externally by staff; the application never
stores card or bank credentials. Payment submission claims a tenant-scoped idempotency key and
locks the invoice row on PostgreSQL before recalculating the integer-minor-unit balance. The
payment row, invoice paid/outstanding amounts, derived payment status, and audit metadata commit
in one transaction. Full, partial, mixed-method, and advance-deposit payments all use this path.

## Financial adjustments

Issued quotations, finalized returns, credit notes, refunds, and stock-return movements are
immutable historical records. Quotation conversion reuses checkout validation, calculation,
locking, invoice numbering, and stock deduction; changed current values require explicit approval.
Credits reduce outstanding debt first. Any excess becomes refundable, and refunds reduce that
liability without creating negative payments. The invoice invariant explicitly reconciles gross
payments, refunds, outstanding debt, issued credit, and remaining refundable liability.

