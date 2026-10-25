# Phase 8 user acceptance test plan

## Purpose and safety

Validate the complete shop workflow on PostgreSQL before a controlled pilot. All fixture names, contacts and transactions are fictional. The seed refuses non-PostgreSQL databases and any database whose name does not start with `tetrova_uat_`; it also refuses to overwrite its tenant.

## Reproduce the dataset

Create an empty disposable database, migrate it, then run:

```bash
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/tetrova_uat_phase8 \
INITIAL_ADMIN_PASSWORD= SECRET_KEY=replace-with-test-secret PYTHONPATH=apps/api \
./.venv/bin/python ops/uat/seed_uat.py

DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/tetrova_uat_phase8 \
INITIAL_ADMIN_PASSWORD= SECRET_KEY=replace-with-test-secret PYTHONPATH=apps/api \
./.venv/bin/python ops/uat/verify_uat.py
```

The fixture creates 120 customers, four role accounts, 24 visits and finalized examinations, 3 suppliers, 12 varied products, stock ledgers, 18 invoices, mixed and partial payments, 5 quotations, 6 optical orders, returns, a credit note and a refund across several weeks. Fixture password: `FictionalUAT123!`; use only in the disposable environment.

## Acceptance scenarios

1. Owner: dashboard and reports; tenant branding; employee management; invoice/payment/refund review; CSV and print preview.
2. Manager: products, suppliers and stock; quotations; checkout; returns; order supplier tracking, override collection and reports.
3. Cashier: customer/visit registration, search, checkout, partial payment, receipt, order collection; verify cost and management screens are unavailable.
4. Optometrist: customer history, examination draft/finalize/print, standalone optical order and quality check; verify invoice/payment/report access is unavailable.
5. Full journey: customer → visit → examination → products → checkout → payment → optical order → QC → collection → return → credit → refund.
6. Interruptions: retry identical idempotency keys; reject stale stock/order versions; refresh after a successful financial request before resubmitting.
7. Devices: desktop, iPad/tablet portrait and landscape, and phone; check navigation, form keyboard flow, touch targets, scrolling, print preview and browser PDF.

## Pass rules

No open critical/high defect; exact financial and stock reconciliation; tenant and role isolation; PostgreSQL concurrency suite passes; backup restores into a separate database; key directory/report requests remain comfortably below one second on the fixture. Physical printer and staff sign-off are required during the pilot.
