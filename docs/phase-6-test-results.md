# Phase 6 verification results

Verification date: 25 October 2026. Baseline: `082cfe2`.

## Automated results

| Check | Result |
| --- | --- |
| Ruff lint | Passed, 64 Python files |
| Ruff format check | Passed, 64 Python files |
| SQLite backend suite | Passed: 61; skipped: 9 PostgreSQL-only concurrency tests |
| PostgreSQL backend suite | Passed: 70, including concurrency tests |
| Frontend TypeScript | Passed |
| Frontend Vitest | Passed: 13 tests in 3 files |
| Production frontend build | Passed; 1,956 modules transformed |
| SQLite migrations | Passed from empty database through `0012_optical_orders` |
| PostgreSQL migrations | Passed from empty database through `0012_optical_orders` |
| Alembic heads | Passed: one head, `0012_optical_orders` |
| Schema drift | Passed on SQLite and PostgreSQL: no new upgrade operations detected |
| Docker Compose configuration | Passed |
| Container smoke check | Existing API, web and PostgreSQL containers healthy; API health and web HTTP returned 200 |
| Fresh Docker image build | Not completed: Docker Hub returned repeated TLS handshake timeout/EOF while resolving official Python/Nginx base-image manifests |

The PostgreSQL suite ran against the dedicated local database `tetrova_pos_phase6`, not the development database.

## Workflow and reconciliation coverage

- Scenario A/B: `test_phase6_integration.py` covers customer, visit, finalized examination, frame and made-to-order lenses, checkout, advance payment, optical order, supplier, status workflow, four-part QC, final card payment, collection and customer history. It asserts one checkout stock deduction and a zero final balance.
- Scenario C: quotation draft/edit/issue/conversion, price-change approval, inventory deduction, idempotency and concurrent conversion are covered in `test_adjustments.py`.
- Scenario D: partial returns, resellable/non-resellable stock behavior, credit allocation, refund limits, reports and concurrent refund protection are covered in `test_adjustments.py` and `test_reporting_printing.py`.
- Scenario E: insufficient checkout and quotation-conversion stock tests verify rollback with no partial invoice or stock mutation.
- Reporting tests reconcile invoiced sales, payments, refunds, credit notes, discounts, tax, methods, products and staff. A new test confirms expired issued quotations are excluded from the owner dashboard.
- Existing tests cover tenant isolation and backend role enforcement across customer, clinical, inventory, checkout, finance, reporting, branding and order modules.
- Printing tests cover immutable-source invoice, receipt, payment, quotation, credit-note and refund document payloads. CSS/build validation passed.

## Commands

```bash
DATABASE_URL=sqlite:// PYTHONPATH=apps/api ./.venv/bin/pytest -q apps/api/tests
DATABASE_URL=postgresql+psycopg://tetrova:tetrova@localhost:55432/tetrova_pos_phase6 PYTHONPATH=apps/api ./.venv/bin/pytest -q apps/api/tests
./.venv/bin/ruff check apps/api/app apps/api/tests
./.venv/bin/ruff format --check apps/api/app apps/api/tests
npm run typecheck --workspace apps/web
npm test --workspace apps/web -- --run
npm run build --workspace apps/web
PYTHONPATH=apps/api DATABASE_URL=<database-url> ./.venv/bin/alembic -c apps/api/alembic.ini upgrade head
PYTHONPATH=apps/api DATABASE_URL=<database-url> ./.venv/bin/alembic -c apps/api/alembic.ini check
docker compose config --quiet
docker compose build
docker compose up -d --no-build
curl -fsS http://localhost:8000/api/v1/health
curl -fsSI http://localhost:5173
```

## Manual/device testing still required

- Playwright and browser binaries are not installed, so automated browser journeys and viewport screenshots were not run.
- Test login, checkout, payment, return/refund, order/QC/collection and print preview on physical Android and iPad devices in portrait and landscape.
- Verify A4 and 80 mm output on each intended printer/browser combination. Direct Bluetooth ESC/POS is outside scope.
- Re-run `docker compose build` when Docker Hub connectivity is stable; the failure was external base-image metadata access, not an application compilation failure.
