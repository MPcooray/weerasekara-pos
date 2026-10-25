# Phase 6 integration audit

Audit baseline: commit `082cfe2`, 25 October 2026. The repository was inspected before Phase 6 fixes.

## Modules reviewed

Authentication/JWT and role policies; customers, visits, examinations and prescription revisions; catalog, suppliers, stock balances and ledger; checkout, invoices, payments and balances; quotations and conversion; returns, credit notes and refunds; dashboard, reporting and CSV; browser printing; optical orders, lens suppliers, quality checks and collection; Docker, migrations and frontend navigation/responsiveness.

## Findings before fixes

### High

- The frontend API treated network failures and timeouts as the browser string `Failed to fetch`, which is not actionable for shop staff and did not distinguish an uncertain financial-mutation outcome.
- Authentication expiry did not consistently clear the local session or provide a clear sign-in recovery path after an authenticated API returned 401.

### Medium

- Quotation expiry and optical-order overdue calculations used the server's local date instead of an explicit Asia/Colombo business date.
- The owner dashboard counted already-expired issued quotations as pending.
- The desktop/mobile header used a hard-coded tenant name even after authorized branding changes.
- Mobile navigation omitted quotations for owners/managers and could not expose every implemented module without crowding.
- Optical-order directory requests lacked a loading state and request-failure recovery UI.
- Order creation fetched independent option lists together but did not surface option-loading failures.

### Low

- Several mature screens use compact single-file components. They remain functional but should be split if their workflows grow further.
- Search uses indexed identifiers plus case-insensitive partial matching. Leading-wildcard name searches will become less efficient at much larger tenant sizes, but are acceptable for the planned single-shop VPS.
- Rate limiting, reverse-proxy request limits, TLS, backup automation and centralized monitoring are deployment concerns and are not present in the application repository.

## Integrity review

- Financial values consistently use integer minor units and server calculations.
- Finalized invoices, issued quotations, credit notes, payments, refunds and order snapshots are protected from normal mutation.
- Checkout, payments, quotation conversion, returns, refunds and order transitions retain persistent idempotency and PostgreSQL locking.
- Checkout is the only sale path that deducts stock. Invoice-linked optical orders do not make inventory movements.
- Return credits reduce outstanding balances before creating refundable liability. Refunds are capped by both credit allocation and net paid eligibility.
- Tenant identifiers are derived from JWT-authenticated users; record lookups combine tenant and record identifiers.

## Phase 6 fix plan

1. Add consistent client network, timeout and expired-session handling without automatic financial retries.
2. Use Asia/Colombo dates for expiry/overdue/pending calculations.
3. Load tenant branding into the application header.
4. Make mobile navigation horizontally accessible and expose all modules.
5. Add order loading/error/retry states and safer async option loading.
6. Add complete cross-module integration and reconciliation tests, including realistic scenarios A–E.
7. Record exact automated/manual verification and remaining production issues in the Phase 6 documents.

## Implemented stabilization

- Client requests now time out with actionable language, distinguish network uncertainty, never automatically retry financial writes, and clear expired authenticated sessions on 401.
- Business-date decisions for quotation expiry, dashboard pending quotations, order overdue status and clinical date validation now use Asia/Colombo explicitly.
- The dashboard excludes expired issued quotations from pending work.
- The application header reads tenant branding instead of displaying a fixed shop name.
- Mobile navigation exposes customers, stock, POS, quotations, orders and authorized reports through a touch-friendly horizontally scrollable bar.
- Optical-order directory loading, request failure and retry states are visible; order option failures are surfaced instead of silently leaving empty selectors.
- A cross-module integration test now exercises registration through final collection, including a finalized prescription, stocked frame, made-to-order lens, partial/mixed payment, supplier tracking, quality control and verification that order creation does not deduct stock twice.

No database schema change was required by these corrections.
