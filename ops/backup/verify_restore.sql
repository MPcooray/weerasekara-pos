\set ON_ERROR_STOP on

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM alembic_version) THEN
    RAISE EXCEPTION 'missing Alembic revision';
  END IF;
  IF EXISTS (
    SELECT 1 FROM invoices
    WHERE paid_minor - refunded_minor + outstanding_minor + credited_minor <> total_minor
  ) THEN
    RAISE EXCEPTION 'invoice balance reconciliation failed';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM inventory_balances balance
    LEFT JOIN (
      SELECT tenant_id, product_id, location_id, SUM(quantity_delta) AS quantity
      FROM stock_movements GROUP BY tenant_id, product_id, location_id
    ) ledger USING (tenant_id, product_id, location_id)
    WHERE balance.quantity <> COALESCE(ledger.quantity, 0)
  ) THEN
    RAISE EXCEPTION 'inventory ledger reconciliation failed';
  END IF;
  IF EXISTS (
    SELECT 1 FROM users employee
    LEFT JOIN tenants tenant ON tenant.id = employee.tenant_id
    WHERE tenant.id IS NULL
  ) THEN
    RAISE EXCEPTION 'employee tenant integrity failed';
  END IF;
  IF EXISTS (
    SELECT 1 FROM examinations exam
    LEFT JOIN customers customer
      ON customer.id = exam.customer_id AND customer.tenant_id = exam.tenant_id
    WHERE customer.id IS NULL
  ) THEN
    RAISE EXCEPTION 'clinical tenant integrity failed';
  END IF;
  IF EXISTS (
    SELECT 1 FROM optical_orders optical_order
    LEFT JOIN customers customer
      ON customer.id = optical_order.customer_id
      AND customer.tenant_id = optical_order.tenant_id
    WHERE customer.id IS NULL
  ) THEN
    RAISE EXCEPTION 'optical order tenant integrity failed';
  END IF;
END $$;

SELECT version_num AS alembic_version FROM alembic_version;
SELECT COUNT(*) AS tenants FROM tenants;
SELECT COUNT(*) AS employees FROM users;
SELECT COUNT(*) AS customers FROM customers;
SELECT COUNT(*) AS examinations FROM examinations;
SELECT COUNT(*) AS invoices FROM invoices;
SELECT COALESCE(SUM(total_minor), 0) AS invoice_total_minor FROM invoices;
SELECT COALESCE(SUM(amount_minor), 0) AS payment_total_minor FROM payments;
SELECT COALESCE(SUM(outstanding_minor), 0) AS outstanding_total_minor FROM invoices;
SELECT COALESCE(SUM(quantity), 0) AS inventory_units FROM inventory_balances;
SELECT COALESCE(SUM(quantity_delta), 0) AS movement_units FROM stock_movements;
SELECT COUNT(*) AS optical_orders FROM optical_orders;
