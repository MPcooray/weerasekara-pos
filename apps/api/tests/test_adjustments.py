from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal, engine
from app.models.finance import Invoice, Refund
from app.models.inventory import StockMovement
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.adjustments import RefundCreate, ReturnCreate, ReturnLineInput
from app.services.adjustments import (
    approve_return,
    convert_quotation,
    record_refund,
    request_return,
)


def product(client, sku=None, *, price=100000, track=True, made=False, tax=0):
    response = client.post(
        "/api/v1/products",
        json={
            "name": f"Item {uuid4().hex[:5]}",
            "sku": sku or f"ITEM-{uuid4().hex[:8]}",
            "category": "prescription_lens" if made else "spectacle_frame",
            "cost_price_minor": 10000,
            "selling_price_minor": price,
            "track_stock": track,
            "made_to_order": made,
            "tax_rate": tax,
            "tax_inclusive": False,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def stock(client, item, quantity=5):
    response = client.post(
        f"/api/v1/products/{item['id']}/movements",
        json={
            "quantity_delta": quantity,
            "movement_type": "opening_stock",
            "expected_version": item["stock_version"],
            "reason": "Opening",
        },
    )
    assert response.status_code == 201, response.text


def invoice(client, item, quantity=2):
    response = client.post(
        "/api/v1/checkout/confirm",
        json={"lines": [{"product_id": item["id"], "quantity": quantity}]},
        headers={"Idempotency-Key": f"sale-{uuid4()}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def request_and_approve(client, invoice_data, *, quantity=1, restock=True):
    line = invoice_data["lines"][0]
    requested = client.post(
        f"/api/v1/invoices/{invoice_data['id']}/returns",
        json={
            "reason": "Customer changed preference",
            "lines": [
                {
                    "invoice_line_id": line.get("id", line["product_id"]),
                    "quantity": quantity,
                    "restock": restock,
                }
            ],
        },
        headers={"Idempotency-Key": f"return-{uuid4()}"},
    )
    return requested


def test_quotation_draft_edit_issue_and_convert_with_stock(authenticated_client):
    item = product(authenticated_client, price=100000, tax=1800)
    stock(authenticated_client, item, 3)
    created = authenticated_client.post(
        "/api/v1/quotations",
        json={
            "expires_on": "2026-12-31",
            "invoice_discount_minor": 5000,
            "lines": [{"product_id": item["id"], "quantity": 1, "line_discount_minor": 1000}],
        },
    )
    assert created.status_code == 201, created.text
    quote = created.json()
    assert quote["status"] == "draft" and quote["total_minor"] == 110920
    edited = authenticated_client.put(
        f"/api/v1/quotations/{quote['id']}",
        json={"expires_on": "2026-12-31", "lines": [{"product_id": item["id"], "quantity": 2}]},
    )
    assert edited.status_code == 200 and edited.json()["total_minor"] == 236000
    issued = authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/issue",
        headers={"Idempotency-Key": "issue-quotation-1"},
    )
    assert issued.status_code == 200 and issued.json()["status"] == "issued"
    assert (
        authenticated_client.put(
            f"/api/v1/quotations/{quote['id']}",
            json={"lines": [{"product_id": item["id"], "quantity": 1}]},
        ).status_code
        == 409
    )
    converted = authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/convert",
        json={"approve_changes": False},
        headers={"Idempotency-Key": "convert-quotation-1"},
    )
    assert converted.status_code == 201, converted.text
    repeated = authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/convert",
        json={"approve_changes": False},
        headers={"Idempotency-Key": "convert-quotation-1"},
    )
    assert repeated.status_code == 201 and repeated.json()["id"] == converted.json()["id"]
    assert authenticated_client.get(f"/api/v1/products/{item['id']}").json()["quantity"] == 1


def test_changed_price_requires_explicit_conversion_approval(authenticated_client):
    item = product(authenticated_client, price=100000)
    stock(authenticated_client, item, 2)
    quote = authenticated_client.post(
        "/api/v1/quotations", json={"lines": [{"product_id": item["id"], "quantity": 1}]}
    ).json()
    authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/issue",
        headers={"Idempotency-Key": "issue-price-change"},
    )
    authenticated_client.patch(
        f"/api/v1/products/{item['id']}", json={"selling_price_minor": 125000}
    )
    rejected = authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/convert",
        json={"approve_changes": False},
        headers={"Idempotency-Key": "convert-price-change-a"},
    )
    assert rejected.status_code == 409 and rejected.json()["detail"]["differences"]
    approved = authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/convert",
        json={"approve_changes": True},
        headers={"Idempotency-Key": "convert-price-change-b"},
    )
    assert approved.status_code == 201 and approved.json()["total_minor"] == 125000


def test_expired_quotation_and_failed_conversion_preserve_stock(authenticated_client):
    expired_item = product(authenticated_client)
    expired = authenticated_client.post(
        "/api/v1/quotations",
        json={
            "expires_on": "2020-01-01",
            "lines": [{"product_id": expired_item["id"], "quantity": 1}],
        },
    ).json()
    authenticated_client.post(
        f"/api/v1/quotations/{expired['id']}/issue",
        headers={"Idempotency-Key": "issue-expired-quotation"},
    )
    rejected = authenticated_client.post(
        f"/api/v1/quotations/{expired['id']}/convert",
        json={"approve_changes": False},
        headers={"Idempotency-Key": "convert-expired-quotation"},
    )
    assert rejected.status_code == 409

    scarce_item = product(authenticated_client)
    stock(authenticated_client, scarce_item, 1)
    quote = authenticated_client.post(
        "/api/v1/quotations",
        json={"lines": [{"product_id": scarce_item["id"], "quantity": 2}]},
    ).json()
    authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/issue",
        headers={"Idempotency-Key": "issue-insufficient-stock"},
    )
    invoice_count = authenticated_client.get("/api/v1/invoices").json()["total"]
    failed = authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/convert",
        json={"approve_changes": False},
        headers={"Idempotency-Key": "convert-insufficient-stock"},
    )
    assert failed.status_code == 409
    assert authenticated_client.get(f"/api/v1/products/{scarce_item['id']}").json()["quantity"] == 1
    assert authenticated_client.get("/api/v1/invoices").json()["total"] == invoice_count
    assert (
        authenticated_client.get(f"/api/v1/quotations/{quote['id']}").json()["status"] == "issued"
    )


def test_partial_return_credit_restock_and_excess_rejection(authenticated_client):
    item = product(authenticated_client, price=100000)
    stock(authenticated_client, item, 5)
    sold = invoice(authenticated_client, item, 2)
    invoice_line_id = sold["lines"][0].get("id")
    if invoice_line_id is None:
        with SessionLocal() as db:
            invoice_line_id = str(db.get(Invoice, UUID(sold["id"])).lines[0].id)
    requested = authenticated_client.post(
        f"/api/v1/invoices/{sold['id']}/returns",
        json={
            "reason": "Frame unsuitable",
            "lines": [{"invoice_line_id": invoice_line_id, "quantity": 1, "restock": True}],
        },
        headers={"Idempotency-Key": "return-partial-1"},
    )
    assert requested.status_code == 201, requested.text
    approved = authenticated_client.post(
        f"/api/v1/returns/{requested.json()['id']}/approve",
        headers={"Idempotency-Key": "approve-return-1"},
    )
    assert approved.status_code == 200 and approved.json()["credit_note_id"]
    detail = authenticated_client.get(f"/api/v1/invoices/{sold['id']}").json()
    assert detail["credited_minor"] == 100000 and detail["outstanding_minor"] == 100000
    assert authenticated_client.get(f"/api/v1/products/{item['id']}").json()["quantity"] == 4
    excess = authenticated_client.post(
        f"/api/v1/invoices/{sold['id']}/returns",
        json={
            "reason": "Too many",
            "lines": [{"invoice_line_id": invoice_line_id, "quantity": 2, "restock": True}],
        },
        headers={"Idempotency-Key": "return-excess-1"},
    )
    assert excess.status_code == 409


def test_made_to_order_return_never_restocks(authenticated_client):
    item = product(authenticated_client, made=True)
    sold = invoice(authenticated_client, item, 1)
    with SessionLocal() as db:
        line_id = str(db.get(Invoice, UUID(sold["id"])).lines[0].id)
    requested = authenticated_client.post(
        f"/api/v1/invoices/{sold['id']}/returns",
        json={
            "reason": "Custom lens issue",
            "lines": [{"invoice_line_id": line_id, "quantity": 1, "restock": True}],
        },
        headers={"Idempotency-Key": "return-custom-lens"},
    ).json()
    authenticated_client.post(
        f"/api/v1/returns/{requested['id']}/approve",
        headers={"Idempotency-Key": "approve-custom-lens"},
    )
    with SessionLocal() as db:
        assert (
            db.query(StockMovement).filter(StockMovement.return_id == UUID(requested["id"])).count()
            == 0
        )


def test_non_resellable_return_does_not_increase_stock(authenticated_client):
    item = product(authenticated_client)
    stock(authenticated_client, item, 2)
    sold = invoice(authenticated_client, item, 1)
    requested = request_and_approve(authenticated_client, sold, restock=False)
    assert requested.status_code == 201, requested.text
    approved = authenticated_client.post(
        f"/api/v1/returns/{requested.json()['id']}/approve",
        headers={"Idempotency-Key": "approve-non-resellable"},
    )
    assert approved.status_code == 200
    assert authenticated_client.get(f"/api/v1/products/{item['id']}").json()["quantity"] == 1
    with SessionLocal() as db:
        assert (
            db.query(StockMovement)
            .filter(StockMovement.return_id == UUID(requested.json()["id"]))
            .count()
            == 0
        )


def test_credit_applies_to_outstanding_before_refund(authenticated_client):
    item = product(authenticated_client, price=100000)
    stock(authenticated_client, item, 2)
    sold = invoice(authenticated_client, item, 2)
    authenticated_client.post(
        f"/api/v1/invoices/{sold['id']}/payments",
        json={"amount_minor": 150000, "method": "cash"},
        headers={"Idempotency-Key": "payment-before-return"},
    )
    with SessionLocal() as db:
        line_id = str(db.get(Invoice, UUID(sold["id"])).lines[0].id)
    requested = authenticated_client.post(
        f"/api/v1/invoices/{sold['id']}/returns",
        json={
            "reason": "Partial paid return",
            "lines": [{"invoice_line_id": line_id, "quantity": 1}],
        },
        headers={"Idempotency-Key": "return-paid-item"},
    ).json()
    approved = authenticated_client.post(
        f"/api/v1/returns/{requested['id']}/approve",
        headers={"Idempotency-Key": "approve-paid-item"},
    ).json()
    invoice_after = authenticated_client.get(f"/api/v1/invoices/{sold['id']}").json()
    assert invoice_after["outstanding_minor"] == 0 and invoice_after["refundable_minor"] == 50000
    credit_id = approved["credit_note_id"]
    refund = authenticated_client.post(
        f"/api/v1/credit-notes/{credit_id}/refunds",
        json={
            "amount_minor": 30000,
            "method": "card",
            "reason": "Returned to card",
            "reference": "TERM-R1",
        },
        headers={"Idempotency-Key": "refund-partial-1"},
    )
    assert refund.status_code == 201
    assert (
        authenticated_client.post(
            f"/api/v1/credit-notes/{credit_id}/refunds",
            json={"amount_minor": 30000, "method": "cash", "reason": "Excess"},
            headers={"Idempotency-Key": "refund-excess-1"},
        ).status_code
        == 409
    )
    final = authenticated_client.get(f"/api/v1/invoices/{sold['id']}").json()
    assert final["refunded_minor"] == 30000 and final["refundable_minor"] == 20000


def test_tenant_isolation_and_role_permissions(authenticated_client, client):
    item = product(authenticated_client)
    quote = authenticated_client.post(
        "/api/v1/quotations", json={"lines": [{"product_id": item["id"], "quantity": 1}]}
    ).json()
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "weerasekara-optics"))
        optometrist = User(
            tenant_id=tenant.id,
            email="adjustment-optometrist@example.com",
            full_name="Optometrist",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OPTOMETRIST,
        )
        other = Tenant(name="Other adjustments", slug="other-adjustments")
        db.add_all([optometrist, other])
        db.flush()
        other_owner = User(
            tenant_id=other.id,
            email="adjustment-owner@example.com",
            full_name="Other Owner",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(other_owner)
        db.commit()
        opt_token = create_access_token(
            user_id=str(optometrist.id), tenant_id=str(tenant.id), role=optometrist.role.value
        )
        other_token = create_access_token(
            user_id=str(other_owner.id), tenant_id=str(other.id), role=other_owner.role.value
        )
    assert (
        client.post(
            "/api/v1/quotations",
            json={"lines": [{"product_id": item["id"], "quantity": 1}]},
            headers={"Authorization": f"Bearer {opt_token}"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/quotations/{quote['id']}", headers={"Authorization": f"Bearer {other_token}"}
        ).status_code
        == 404
    )


def test_postgresql_concurrent_returns_cannot_exceed_sold(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    item = product(authenticated_client)
    stock(authenticated_client, item, 1)
    sold = invoice(authenticated_client, item, 1)
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
        line_id = db.get(Invoice, UUID(sold["id"])).lines[0].id
    barrier = Barrier(2)

    def submit(key):
        with SessionLocal() as db:
            barrier.wait()
            try:
                result = request_return(
                    db,
                    db.get(User, user_id),
                    UUID(sold["id"]),
                    ReturnCreate(
                        reason="Concurrent return",
                        lines=[ReturnLineInput(invoice_line_id=line_id, quantity=1)],
                    ),
                    key,
                )
                db.commit()
                return "ok", str(result.id)
            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ["concurrent-return-a", "concurrent-return-b"]))
    assert [x[0] for x in results].count("ok") == 1


def test_postgresql_concurrent_refunds_cannot_exceed_credit(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    item = product(authenticated_client)
    stock(authenticated_client, item, 1)
    sold = invoice(authenticated_client, item, 1)
    authenticated_client.post(
        f"/api/v1/invoices/{sold['id']}/payments",
        json={"amount_minor": 100000, "method": "cash"},
        headers={"Idempotency-Key": "pay-concurrent-refund"},
    )
    with SessionLocal() as db:
        line_id = db.get(Invoice, UUID(sold["id"])).lines[0].id
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
        ret = request_return(
            db,
            db.get(User, user_id),
            UUID(sold["id"]),
            ReturnCreate(
                reason="Concurrent refund",
                lines=[ReturnLineInput(invoice_line_id=line_id, quantity=1)],
            ),
            "return-concurrent-refund",
        )
        db.commit()
        return_id = ret.id
    with SessionLocal() as db:
        ret, credit = approve_return(
            db, db.get(User, user_id), return_id, "approve-concurrent-refund"
        )
        db.commit()
        credit_id = credit.id
    barrier = Barrier(2)

    def submit(key):
        with SessionLocal() as db:
            barrier.wait()
            try:
                result = record_refund(
                    db,
                    db.get(User, user_id),
                    credit_id,
                    RefundCreate(amount_minor=75000, method="cash", reason="Concurrent"),
                    key,
                )
                db.commit()
                return "ok", str(result.id)
            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ["concurrent-refund-a", "concurrent-refund-b"]))
    assert [x[0] for x in results].count("ok") == 1
    with SessionLocal() as db:
        assert db.query(Refund).count() == 1


def test_postgresql_concurrent_quotation_conversion_creates_one_invoice(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    item = product(authenticated_client)
    stock(authenticated_client, item, 1)
    quote = authenticated_client.post(
        "/api/v1/quotations", json={"lines": [{"product_id": item["id"], "quantity": 1}]}
    ).json()
    authenticated_client.post(
        f"/api/v1/quotations/{quote['id']}/issue",
        headers={"Idempotency-Key": "issue-concurrent-conversion"},
    )
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
    barrier = Barrier(2)

    def submit(key):
        with SessionLocal() as db:
            barrier.wait()
            result = convert_quotation(db, db.get(User, user_id), UUID(quote["id"]), False, key)
            db.commit()
            return str(result.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, ["convert-concurrent-a", "convert-concurrent-b"]))
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert db.query(Invoice).count() == 1
