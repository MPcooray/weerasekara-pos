# Phase 6 operational workflows

## Complete spectacle sale

1. Register or search for the customer, then create a visit.
2. Record the examination and finalize the prescription. Finalization makes the clinical snapshot immutable; corrections use a revision.
3. In POS, select the customer/prescription and products. Preview totals, confirm stock and complete checkout once.
4. If the browser reports an uncertain network failure, search invoices before trying checkout again. Reusing the same request is protected by idempotency, but staff should still verify the result.
5. Record the deposit or full payment against the invoice. Payments do not create additional sales revenue.
6. Create the optical order from the invoice. This captures frame/prescription snapshots and does not deduct stock a second time.
7. Assign the lens supplier and move the order through confirmed, awaiting lenses, preparation and quality check.
8. Complete all four quality checks, move the order to ready, settle any remaining invoice balance, and confirm collection.

## Quotation to sale

Create and review a draft, issue it, then use conversion preview. If current prices differ, an authorized user must explicitly accept the changes. Conversion creates one invoice and performs the normal checkout stock checks/deduction. Expired quotations cannot be converted.

## Return, credit and refund

Request return quantities from the original invoice. Choose restock only for resellable goods. Approval creates the immutable credit note and any eligible stock movement. Credit first reduces outstanding invoice debt; only the remaining paid-value liability can be refunded. Never pay a refund outside the recorded credit-note workflow.

## Daily reconciliation

Use the Asia/Colombo date range in Dashboard & Reports. Treat invoiced sales, payments received, refunds, credit adjustments and outstanding balances as separate measures. Compare cash/card/bank totals with the relevant till, terminal and bank records. Export CSV before period close if an external working paper is required.

## Printing

Open an invoice, payment, quotation, credit note or refund record and use its print preview. Choose A4 or 80 mm where offered, then use the browser's Print / Save as PDF. Browser printing works on supported Android/iPad browsers, but direct Bluetooth ESC/POS control is not implemented and printer-driver capabilities vary.

## Recovery rules

- A 401 response clears the local session and returns the operator to sign-in.
- Network/timeout errors are not automatically retried for financial mutations because the server may already have committed them.
- After an interrupted checkout, payment, conversion, return or refund, search the relevant ledger before submitting again.
- Do not edit database rows to correct finalized records. Use the supported revision, return, credit and refund paths.
