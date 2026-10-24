from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal, engine
from app.models.finance import Invoice, InvoiceStatus, Payment
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.checkout import PaymentCreate
from app.services.payments import record_payment


def create_invoice(client, *, price=2500000):
    product = client.post(
        "/api/v1/products",
        json={
            "name": f"Service {uuid4().hex[:6]}",
            "sku": f"SVC-{uuid4().hex[:8]}",
            "category": "optical_service",
            "cost_price_minor": 0,
            "selling_price_minor": price,
            "track_stock": False,
            "tax_rate": 0,
        },
    ).json()
    response = client.post(
        "/api/v1/checkout/confirm",
        json={"lines": [{"product_id": product["id"], "quantity": 1}]},
        headers={"Idempotency-Key": f"invoice-{uuid4()}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def pay(client, invoice_id, amount, method="cash", key=None, reference=None):
    return client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        json={"amount_minor": amount, "method": method, "reference": reference},
        headers={"Idempotency-Key": key or f"payment-{uuid4()}"},
    )


def role_token(role: UserRole, *, tenant_id=None):
    with SessionLocal() as db:
        tenant = db.get(Tenant, tenant_id) if tenant_id else db.scalar(select(Tenant))
        user = User(
            tenant_id=tenant.id,
            email=f"{role.value}-{uuid4().hex[:8]}@example.com",
            full_name=f"Test {role.value}",
            password_hash=hash_password("SafePassword123!"),
            role=role,
        )
        db.add(user)
        db.commit()
        return create_access_token(
            user_id=str(user.id), tenant_id=str(user.tenant_id), role=user.role.value
        )


def test_partial_deposit_then_mixed_methods_settles_invoice(authenticated_client):
    invoice = create_invoice(authenticated_client)
    deposit = pay(authenticated_client, invoice["id"], 1000000, "cash", reference="DEP-1")
    assert deposit.status_code == 201
    assert deposit.json()["invoice"]["status"] == "partially_paid"
    assert deposit.json()["invoice"]["outstanding_minor"] == 1500000
    second = pay(authenticated_client, invoice["id"], 500000, "card", reference="TERM-42")
    assert second.status_code == 201
    settled = pay(authenticated_client, invoice["id"], 1000000, "bank_transfer", reference="BANK-9")
    assert settled.status_code == 201
    assert settled.json()["invoice"]["status"] == "paid"
    assert settled.json()["invoice"]["paid_minor"] == 2500000
    assert settled.json()["invoice"]["outstanding_minor"] == 0
    detail = authenticated_client.get(f"/api/v1/invoices/{invoice['id']}").json()
    assert [item["method"] for item in detail["payments"]] == [
        "cash",
        "card",
        "bank_transfer",
    ]
    assert sum(item["amount_minor"] for item in detail["payments"]) == detail["total_minor"]


def test_full_payment_idempotency_and_conflict(authenticated_client):
    invoice = create_invoice(authenticated_client, price=100000)
    first = pay(authenticated_client, invoice["id"], 100000, key="payment-repeat-key")
    repeated = pay(authenticated_client, invoice["id"], 100000, key="payment-repeat-key")
    assert first.status_code == repeated.status_code == 201
    assert first.json()["payment"]["id"] == repeated.json()["payment"]["id"]
    assert (
        pay(authenticated_client, invoice["id"], 50000, key="payment-repeat-key").status_code == 409
    )
    assert len(authenticated_client.get(f"/api/v1/invoices/{invoice['id']}/payments").json()) == 1


def test_invalid_amounts_overpayment_and_paid_invoice_rejected(authenticated_client):
    invoice = create_invoice(authenticated_client, price=100000)
    assert pay(authenticated_client, invoice["id"], 0).status_code == 422
    assert pay(authenticated_client, invoice["id"], -1).status_code == 422
    assert pay(authenticated_client, invoice["id"], 100001).status_code == 409
    assert pay(authenticated_client, invoice["id"], 100000).status_code == 201
    assert pay(authenticated_client, invoice["id"], 1).status_code == 409


def test_recorded_payment_is_immutable(authenticated_client):
    invoice = create_invoice(authenticated_client, price=100000)
    payment_id = pay(authenticated_client, invoice["id"], 50000).json()["payment"]["id"]
    with SessionLocal() as db:
        payment = db.get(Payment, UUID(payment_id))
        payment.amount_minor = 1
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        payment = db.get(Payment, UUID(payment_id))
        db.delete(payment)
        with pytest.raises(ValueError, match="cannot be deleted"):
            db.commit()


def test_payment_tenant_isolation_and_optometrist_read_only(authenticated_client, client):
    invoice = create_invoice(authenticated_client)
    optometrist = role_token(UserRole.OPTOMETRIST)
    response = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount_minor": 1, "method": "cash"},
        headers={
            "Authorization": f"Bearer {optometrist}",
            "Idempotency-Key": "optometrist-payment",
        },
    )
    assert response.status_code == 403
    with SessionLocal() as db:
        tenant = Tenant(name="Other payment tenant", slug=f"payment-{uuid4().hex[:8]}")
        db.add(tenant)
        db.commit()
        other_tenant_id = tenant.id
    other = role_token(UserRole.OWNER, tenant_id=other_tenant_id)
    headers = {"Authorization": f"Bearer {other}", "Idempotency-Key": "other-payment-key"}
    assert (
        client.post(
            f"/api/v1/invoices/{invoice['id']}/payments",
            json={"amount_minor": 1, "method": "cash"},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/invoices/{invoice['id']}/payments",
            headers={"Authorization": f"Bearer {other}"},
        ).status_code
        == 404
    )


def test_invoice_filters_totals_search_and_pagination(authenticated_client):
    first = create_invoice(authenticated_client, price=100000)
    second = create_invoice(authenticated_client, price=200000)
    create_invoice(authenticated_client, price=300000)
    pay(authenticated_client, first["id"], 100000)
    pay(authenticated_client, second["id"], 50000)
    page = authenticated_client.get("/api/v1/invoices?page=1&page_size=2").json()
    assert page["total"] == 3 and page["pages"] == 2 and len(page["items"]) == 2
    outstanding = authenticated_client.get(
        "/api/v1/invoices?payment_status=outstanding&page_size=10"
    ).json()
    assert outstanding["total"] == 2 and outstanding["total_outstanding_minor"] == 450000
    partial = authenticated_client.get("/api/v1/invoices?payment_status=partially_paid").json()
    assert partial["total"] == 1 and partial["items"][0]["id"] == second["id"]
    searched = authenticated_client.get(f"/api/v1/invoices?search={first['invoice_number']}").json()
    assert searched["total"] == 1 and searched["items"][0]["id"] == first["id"]


def test_postgresql_concurrent_payments_cannot_overpay(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    invoice = create_invoice(authenticated_client, price=100000)
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
    barrier = Barrier(2)

    def submit(key):
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait()
            try:
                payment = record_payment(
                    db,
                    user,
                    UUID(invoice["id"]),
                    PaymentCreate(amount_minor=75000, method="cash"),
                    key,
                )
                db.commit()
                return "ok", str(payment.id)
            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ["concurrent-payment-a", "concurrent-payment-b"]))
    assert [x[0] for x in results].count("ok") == 1
    assert [x[0] for x in results].count("error") == 1
    with SessionLocal() as db:
        saved = db.get(Invoice, UUID(invoice["id"]))
        assert saved.paid_minor == 75000 and saved.outstanding_minor == 25000
        assert saved.status == InvoiceStatus.PARTIALLY_PAID
        assert db.query(Payment).count() == 1


def test_postgresql_concurrent_duplicate_payment_is_idempotent(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL idempotency verification")
    invoice = create_invoice(authenticated_client, price=100000)
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
    barrier = Barrier(2)

    def submit(_):
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait()
            payment = record_payment(
                db,
                user,
                UUID(invoice["id"]),
                PaymentCreate(amount_minor=50000, method="card", reference="TERM-1"),
                "same-concurrent-payment",
            )
            db.commit()
            return str(payment.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        saved = db.get(Invoice, UUID(invoice["id"]))
        assert saved.paid_minor == 50000 and db.query(Payment).count() == 1
