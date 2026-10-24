# Printing and financial reporting

## Supported printing

The POS provides browser print previews for A4 invoices, 80 mm receipts, payment receipts, quotations, credit notes, and refund confirmations. The browser print dialog provides printer selection and Save as PDF when the browser/platform supports it. Printed values come from immutable financial snapshots; current catalog prices are never used to rebuild historical totals.

Modern desktop browsers, Android tablets, iPads, and smartphones are the supported path. Android printing depends on the browser, Android Print Service, and a printer manufacturer's compatible print-service app. Direct Bluetooth ESC/POS commands are not implemented, and universal Bluetooth thermal-printer compatibility is not claimed. If a browser does not expose printing, staff can read the preview but must use another supported browser/device to print or save PDF.

Owners and managers can configure display name, address, contact details, an HTTPS logo URL, invoice and receipt footers, and optional business/tax registration text. The application never invents registration details.

## Report definitions

- Invoiced sales: finalized invoice totals created inside the selected Asia/Colombo date range.
- Payments received: immutable payment records received in the range. Deposits reduce balances but do not increase invoiced sales.
- Refunds: funds recorded as returned during the range.
- Outstanding: current outstanding balance of invoices issued in the selected range.
- Credit adjustments: issued credit-note totals in the range.
- Discounts and tax: finalized invoice snapshot amounts, not current catalog settings.
- Top-selling products: gross finalized invoice quantity and line value in the range. Returns are reported separately as credits.
- Sales by staff: finalized invoice totals grouped by the staff member who completed checkout.

CSV values use integer minor currency units. Reports are tenant-scoped, owner/manager-only, and limited to 366 days for the planned 2 GB VPS.

## Operations, backups, and limitations

Reports are not a substitute for backups. Use automated encrypted PostgreSQL backups, retain multiple recovery points, and test restoration. Browser-generated PDFs are exports, not authoritative database backups.

There is no payment gateway, fiscal-device signing, direct ESC/POS transport, or jurisdiction-specific tax filing export. Print output can vary by browser and printer driver. Before offline Android operation, the project needs an encrypted local store, durable synchronization queue, conflict policy, device authorization, replay-safe financial mutations, printer capability discovery, and recovery testing. Those concerns are intentionally excluded from this phase.
