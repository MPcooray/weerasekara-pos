# Optical order management

Optical orders are fulfilment records, separate from invoices and inventory transactions. Creating an order from an invoice never deducts stock again. Cancelling an order does not reverse its invoice; staff must use the established return, credit-note, and refund workflows when a financial correction is required.

Each order stores immutable snapshots of the finalized prescription and selected frame details. Draft specifications may be edited, but confirmation freezes the manufacturing instructions against later prescription or catalog changes.

The enforced lifecycle is draft → confirmed → awaiting lenses/in preparation → quality check → ready for collection → collected. Owners and managers may cancel a non-terminal order. Required prescription, lens, frame, and fitting checks must all pass before readiness.

Owners and managers manage supplier tracking and may authorize collection with an outstanding invoice balance. Cashiers can collect fully paid orders but cannot override a balance. Collection never changes invoice payment state.

Order creation and critical transitions use persistent idempotency keys. PostgreSQL row locks plus optimistic versions serialize status changes. Timeline, quality, and collection history are append-only through the public API.
