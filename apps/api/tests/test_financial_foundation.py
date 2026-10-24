from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.finance import (
    FinancialIdempotency,
    IdempotencyStatus,
    Invoice,
    InvoiceNumberSequence,
    InvoiceStatus,
)
from app.models.inventory import InventoryLocation
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.financial_calculations import (
    CalculationLine,
    calculate_totals,
    round_ratio_half_up,
)
from app.services.invoice_numbering import next_invoice_number


def test_integer_calculation_discounts_tax_and_partial_payment():
    result = calculate_totals(
        [
            CalculationLine(2, 1250000, 50000, 1800, False, False),
            CalculationLine(1, 800000, 0, 0, True),
        ],
        invoice_discount_minor=100000,
        paid_minor=1000000,
    )
    assert result.subtotal_minor == 3300000
    assert result.discount_minor == 150000
    assert result.total_minor == 3577431
    assert result.outstanding_minor == 2577431
    assert sum(x.invoice_discount_minor for x in result.lines) == 100000


def test_inclusive_tax_and_half_up_rounding_are_deterministic():
    assert round_ratio_half_up(1, 2) == 1
    result = calculate_totals([CalculationLine(1, 11800, tax_rate_bps=1800, tax_inclusive=True)])
    assert (
        result.tax_minor == 1800 and result.total_minor == 11800 and result.taxable_minor == 10000
    )


@pytest.mark.parametrize("kwargs", [{"invoice_discount_minor": 101}, {"paid_minor": 101}])
def test_invalid_discount_or_overpayment_is_rejected(kwargs):
    with pytest.raises(ValueError):
        calculate_totals([CalculationLine(1, 100)], **kwargs)


def test_quantity_precision_uses_only_integers():
    result = calculate_totals(
        [CalculationLine(3, 333, line_discount_minor=1, tax_rate_bps=750, tax_inclusive=False)]
    )
    assert result.subtotal_minor == 999 and result.tax_minor == 75 and result.total_minor == 1073


def test_idempotency_is_unique_per_tenant_but_shared_keys_across_tenants(client):
    with SessionLocal() as db:
        a = Tenant(name="A", slug="finance-a")
        b = Tenant(name="B", slug="finance-b")
        db.add_all([a, b])
        db.flush()

        def item(t):
            return FinancialIdempotency(
                tenant_id=t.id,
                operation="checkout",
                idempotency_key="same",
                request_hash="a" * 64,
                status=IdempotencyStatus.IN_PROGRESS,
            )

        db.add_all([item(a), item(b)])
        db.commit()
        db.add(item(a))
        with pytest.raises(IntegrityError):
            db.commit()


def test_invoice_number_sequence_is_tenant_scoped(client):
    with SessionLocal() as db:
        a = Tenant(name="A", slug="number-a")
        b = Tenant(name="B", slug="number-b")
        db.add_all([a, b])
        db.flush()
        assert next_invoice_number(db, a.id, 2026) == "INV-2026-000001"
        assert next_invoice_number(db, a.id, 2026) == "INV-2026-000002"
        assert next_invoice_number(db, b.id, 2026) == "INV-2026-000001"
        db.commit()
        assert db.query(InvoiceNumberSequence).count() == 2


def test_postgresql_invoice_numbering_serializes_concurrent_requests(client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    with SessionLocal() as db:
        tenant = Tenant(name="Concurrent", slug="number-concurrent")
        db.add(tenant)
        db.commit()
        tenant_id = tenant.id
    barrier = Barrier(2)

    def allocate():
        with SessionLocal() as db:
            barrier.wait()
            value = next_invoice_number(db, tenant_id, 2026)
            db.commit()
            return value

    with ThreadPoolExecutor(max_workers=2) as pool:
        values = sorted(pool.map(lambda _: allocate(), range(2)))
    assert values == ["INV-2026-000001", "INV-2026-000002"]


def test_finalized_invoice_totals_are_immutable_and_balance_is_constrained(client):
    with SessionLocal() as db:
        tenant = Tenant(name="Integrity", slug="financial-integrity")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="owner@integrity.test",
            full_name="Owner",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        location = InventoryLocation(tenant_id=tenant.id, name="Main", code="MAIN", is_default=True)
        db.add_all([user, location])
        db.flush()
        invoice = Invoice(
            tenant_id=tenant.id,
            location_id=location.id,
            invoice_number="INV-2026-000001",
            actor_id=user.id,
            status=InvoiceStatus.FINALIZED,
            subtotal_minor=1000,
            discount_minor=0,
            tax_minor=0,
            total_minor=1000,
            paid_minor=0,
            outstanding_minor=1000,
        )
        db.add(invoice)
        db.commit()
        invoice.total_minor = 900
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        draft = Invoice(
            tenant_id=tenant.id,
            location_id=location.id,
            invoice_number="INV-2026-000002",
            actor_id=user.id,
            status=InvoiceStatus.DRAFT,
            subtotal_minor=1000,
            discount_minor=0,
            tax_minor=0,
            total_minor=1000,
            paid_minor=900,
            outstanding_minor=900,
        )
        db.add(draft)
        with pytest.raises(IntegrityError):
            db.commit()
