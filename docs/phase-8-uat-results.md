# Phase 8 UAT results

Run date: 2026-10-25. Environment: local macOS/Docker, PostgreSQL 17, fictional data only.

## Automated acceptance result

- Fixture: 120 customers, 4 employees/roles, 24 examinations, 12 products, 18 invoices, 5 quotations, 6 orders, 1 return and 1 refund; 2 orders collected.
- Finance: invoice equations and recorded-payment sums reconciled; invoiced LKR 323,350.00, payments LKR 306,350.00 and outstanding LKR 17,000.00.
- Inventory: balance total 106 units exactly matched immutable movement total and no negative balance existed.
- Access: role denials, cashier cost masking and tenant isolation passed. A payment-receipt authorization mismatch found during UAT was fixed and regression-tested.
- Printing data: invoice, thermal receipt, payment receipt and quotation sources passed. Existing tests cover credit notes/refunds and immutable historical prices.
- Performance samples: product search 10.32 ms; customer search 10.40 ms; invoice history 7.01 ms; order directory 49.15 ms; dashboard 17.34 ms; financial report 8.84 ms.
- Recovery: encrypted backup, checksum, decryption, catalog validation and isolated restore passed. Restored totals matched all values above; 21 payments and 28 stock movements were restored.

## Test gates

- PostgreSQL: 91 passed.
- SQLite compatibility: 82 passed, 9 PostgreSQL-only locking/concurrency cases skipped as designed.
- Frontend: TypeScript passed; 15 tests passed; Vite production build passed.
- Ruff passed; migrations reached `0015_session_invalidation` from empty PostgreSQL and SQLite databases.
- Docker Compose validation, API/web image builds and container HTTP smoke tests passed (`/api/v1/health`, web HTTP 200).

## Manual/device status

Playwright was not installed, so automated browser viewport tests were not executed. Physical iPad, Android tablet, smartphone, A4 printer and 80 mm printer acceptance remains a pilot task. Browser print/PDF is implemented; direct Bluetooth/ESC-POS printing is not supported.
