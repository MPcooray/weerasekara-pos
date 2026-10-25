# Phase 9 verification

## Delivered

- Backend-generated, versioned Excel template with instructions, samples, dropdowns, formats and text-preserved identifiers.
- Hardened `.xlsx` upload with file/row/column/expanded-size limits, formula/external-link rejection and safe error messages.
- Tenant-scoped row validation, preview summaries, duplicate modes, expiring hashed tokens and CSV error report.
- Atomic/idempotent confirmation, current-state revalidation, import history/audit records and existing-ledger opening stock.
- Responsive Inventory → Import interface for authorized owner/manager roles.
- Migration `0016_product_imports` records previews and outcomes without duplicating catalog or stock data.

## Automated coverage

Dedicated tests cover template structure, leading-zero SKU/barcode preservation, preview without mutation, valid import, prices, quantities, categories, suppliers, in-file duplicates, existing-SKU modes, stock reconciliation, malformed/oversized/version/formula files, cashier denial, tenant binding, atomic rollback, idempotent retry and PostgreSQL concurrent imports.

Verification completed on 2026-10-25:

- PostgreSQL: **97 passed**, including concurrent import protection.
- SQLite: **87 passed, 10 skipped**; the skips are PostgreSQL-only locking/concurrency cases.
- Frontend: **15 passed**; TypeScript and production Vite build passed.
- Ruff and diff whitespace checks passed.
- Fresh PostgreSQL and SQLite migration chains reached `0016_product_imports`; Alembic reported no model/schema drift on either.
- Docker Compose validation, API/web image builds, live migration, API health and web HTTP smoke checks passed.

The PostgreSQL concurrency test is intentionally skipped on SQLite because SQLite cannot prove the production locking behavior.

## Known limitations

- `.xlsx` only; `.xls`, CSV, macros and formulas are not supported.
- Maximum 5 MB and 2,000 product rows per workbook.
- Preview tokens expire after 30 minutes and cannot be edited in the browser; correct the workbook and upload again.
- Existing-product quantity is never adjusted by import.
- Suppliers/categories must already exist; there is no silent creation.
- Multi-branch stock, offline imports and background import jobs remain out of scope.
