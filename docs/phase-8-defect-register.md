# Phase 8 defect register

| ID | Severity | Finding | Resolution | Status |
|---|---|---|---|---|
| UAT-001 | High | Payment print rendering accepted `payment`, but the permission gate listed `payment-receipt`; a user without invoice access could reach the payment branch. | Unified the route on `payment` and added an optometrist denial regression test. | Closed |
| UAT-002 | Medium | Optometrist order creation displayed an empty invoice selector even though that role correctly cannot load invoices. | Hide the invoice control for optometrists; standalone prescription-linked order remains available. | Closed |
| UAT-003 | Medium | Shared dialogs did not focus an actionable control, restore focus, or close with Escape. | Added initial close-button focus, Escape handling, focus restoration and strong global focus-visible styling. | Closed |
| UAT-004 | Medium | No Playwright/browser automation dependency exists. | API/component automation retained; physical responsive and browser-print checks moved to pilot checklist. | Open—pilot validation |
| UAT-005 | Medium | Direct Bluetooth/ESC-POS support is outside current architecture. | Use OS/browser print service or PDF; validate the shop's exact printer during pilot. | Accepted limitation |
| UAT-006 | Medium | Off-server object storage credentials and alerts cannot be proven in local UAT. | Require a successful production-target backup/upload and alert test before live data. | Open—deployment |

There are no open critical or high defects after verification.
