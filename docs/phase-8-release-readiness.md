# Phase 8 release readiness

## Decision

**Conditionally ready for a controlled single-shop pilot.** It is not declared ready for unrestricted production rollout.

The transactional workflow, tenant/role controls, PostgreSQL concurrency checks, reconciliation, migrations, production builds, container smoke tests and encrypted recovery drill passed. The realistic fixture is reproducible and contains no real customer data.

## Conditions before pilot

- Configure real tenant branding and authorized employees; replace all example secrets and passwords.
- Deploy behind HTTPS, restrict PostgreSQL from the public internet, configure off-server encrypted backups and prove upload/alerting.
- Take a verified pre-pilot backup and name the person authorized to approve refunds, stock corrections and outstanding-balance collection.
- Test the exact Android/iPad/phone models and A4/80 mm printers used by the shop. Browser printing/PDF only; no promise of Bluetooth ESC/POS compatibility.
- Train one staff member per role using the role guides and record signed acceptance of the core journey.

## Pilot controls

Run with a small trained group and a defined support contact. Reconcile cash/card/bank totals, invoice balances and stock daily. Keep existing manual records in parallel during the agreed pilot window. Stop financial entry, preserve logs and contact the owner/support if totals do not reconcile; do not “fix” ledgers directly.

## Go/no-go after pilot

Go only if physical-device/printing checks pass, no critical/high defect remains, daily reconciliations match, backup age is healthy and a restore is still demonstrable. Offline operation, payment gateways, native mobile packaging and direct thermal integration remain out of scope.
