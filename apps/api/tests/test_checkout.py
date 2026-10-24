from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.finance import Invoice
from app.models.inventory import StockMovement
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.checkout import CheckoutRequest
from app.services.checkout import confirm_checkout


def product(
    client,
    *,
    sku="FRAME-1",
    name="Frame A",
    price=1250000,
    category="spectacle_frame",
    track=True,
    made=False,
):
    response = client.post(
        "/api/v1/products",
        json={
            "name": name,
            "sku": sku,
            "category": category,
            "cost_price_minor": 500000,
            "selling_price_minor": price,
            "track_stock": track,
            "made_to_order": made,
            "reorder_threshold": 1,
            "tax_rate": 1800,
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


def payload(item, **overrides):
    data = {
        "lines": [
            {
                "product_id": item["id"],
                "quantity": 2,
                "line_discount_minor": 50000,
                "expected_unit_price_minor": item["selling_price_minor"],
            }
        ],
        "invoice_discount_minor": 100000,
    }
    data.update(overrides)
    return data


def test_preview_confirmation_snapshots_stock_and_idempotency(authenticated_client):
    item = product(authenticated_client)
    stock(authenticated_client, item)
    preview = authenticated_client.post("/api/v1/checkout/preview", json=payload(item))
    assert preview.status_code == 200 and preview.json()["total_minor"] == 2773000
    headers = {"Idempotency-Key": "checkout-test-001"}
    confirmed = authenticated_client.post(
        "/api/v1/checkout/confirm", json=payload(item), headers=headers
    )
    assert confirmed.status_code == 201, confirmed.text
    invoice = confirmed.json()
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["paid_minor"] == 0 and invoice["outstanding_minor"] == invoice["total_minor"]
    assert invoice["lines"][0]["product_name"] == "Frame A"
    repeated = authenticated_client.post(
        "/api/v1/checkout/confirm", json=payload(item), headers=headers
    )
    assert repeated.status_code == 201 and repeated.json()["id"] == invoice["id"]
    assert authenticated_client.get(f"/api/v1/products/{item['id']}").json()["quantity"] == 3
    movements = authenticated_client.get(f"/api/v1/products/{item['id']}/movements").json()
    assert len([m for m in movements if m["movement_type"] == "sale_deduction"]) == 1
    assert (
        authenticated_client.post(
            "/api/v1/checkout/confirm",
            json=payload(item, invoice_discount_minor=0),
            headers=headers,
        ).status_code
        == 409
    )


def test_nonstock_service_and_made_to_order_do_not_deduct(authenticated_client):
    service = product(
        authenticated_client,
        sku="SVC-1",
        name="Fitting",
        price=200000,
        category="optical_service",
        track=False,
    )
    lens = product(
        authenticated_client,
        sku="LENS-MTO",
        name="Custom lens",
        price=800000,
        category="prescription_lens",
        track=True,
        made=True,
    )
    data = {
        "lines": [
            {"product_id": service["id"], "quantity": 1},
            {"product_id": lens["id"], "quantity": 2},
        ]
    }
    response = authenticated_client.post(
        "/api/v1/checkout/confirm", json=data, headers={"Idempotency-Key": "checkout-nonstock"}
    )
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        assert (
            db.query(StockMovement)
            .filter(StockMovement.invoice_id == UUID(response.json()["id"]))
            .count()
            == 0
        )


def test_insufficient_stock_rolls_back_everything(authenticated_client):
    first = product(authenticated_client)
    stock(authenticated_client, first, 1)
    second = product(authenticated_client, sku="FRAME-2", name="Frame B")
    stock(authenticated_client, second, 1)
    data = {
        "lines": [
            {"product_id": first["id"], "quantity": 1},
            {"product_id": second["id"], "quantity": 2},
        ]
    }
    response = authenticated_client.post(
        "/api/v1/checkout/confirm", json=data, headers={"Idempotency-Key": "checkout-rollback"}
    )
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.query(Invoice).count() == 0
    assert authenticated_client.get(f"/api/v1/products/{first['id']}").json()["quantity"] == 1


def test_changed_price_and_archived_product_are_rejected(authenticated_client):
    item = product(authenticated_client)
    stock(authenticated_client, item)
    changed = payload(item)
    changed["lines"][0]["expected_unit_price_minor"] -= 1
    assert (
        authenticated_client.post(
            "/api/v1/checkout/confirm",
            json=changed,
            headers={"Idempotency-Key": "checkout-price-change"},
        ).status_code
        == 409
    )
    authenticated_client.patch(f"/api/v1/products/{item['id']}", json={"is_archived": True})
    assert (
        authenticated_client.post("/api/v1/checkout/preview", json=payload(item)).status_code == 409
    )


def test_only_finalized_prescription_for_selected_customer_can_be_linked(authenticated_client):
    item = product(authenticated_client)
    stock(authenticated_client, item)
    customer = authenticated_client.post(
        "/api/v1/customers",
        json={"full_name": "Prescription Customer", "mobile_number": "0772345678"},
    ).json()["customer"]
    visit = authenticated_client.post(
        f"/api/v1/customers/{customer['id']}/visits",
        json={"purpose": "Optical examination"},
    ).json()
    exam = authenticated_client.post(
        f"/api/v1/customers/{customer['id']}/examinations",
        json={
            "visit_id": visit["id"],
            "prescription_type": "distance",
            "od_sphere": "-1.00",
        },
    ).json()
    draft = authenticated_client.post(
        "/api/v1/checkout/preview",
        json=payload(item, customer_id=customer["id"], examination_id=exam["id"]),
    )
    assert draft.status_code == 422
    finalized = authenticated_client.post(
        f"/api/v1/examinations/{exam['id']}/finalize",
        json={"expected_version": exam["version"]},
    ).json()
    confirmed = authenticated_client.post(
        "/api/v1/checkout/confirm",
        json=payload(
            item,
            customer_id=customer["id"],
            examination_id=finalized["id"],
        ),
        headers={"Idempotency-Key": "checkout-prescription"},
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["examination_id"] == finalized["id"]


def test_invoice_tenant_isolation_and_optometrist_cannot_checkout(authenticated_client, client):
    item = product(authenticated_client)
    stock(authenticated_client, item)
    invoice = authenticated_client.post(
        "/api/v1/checkout/confirm",
        json=payload(item),
        headers={"Idempotency-Key": "checkout-isolation"},
    ).json()
    with SessionLocal() as db:
        tenant = Tenant(name="Other", slug="checkout-other")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="optometrist@example.com",
            full_name="Optometrist",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OPTOMETRIST,
        )
        db.add(user)
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "checkout-other",
            "email": "optometrist@example.com",
            "password": "SafePassword123!",
        },
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    assert client.get(f"/api/v1/invoices/{invoice['id']}").status_code == 404
    assert (
        client.post(
            "/api/v1/checkout/confirm",
            json=payload(item),
            headers={"Idempotency-Key": "checkout-forbidden"},
        ).status_code
        == 403
    )


def test_postgresql_concurrent_sales_cannot_oversell(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    item = product(authenticated_client)
    stock(authenticated_client, item, 1)
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
    barrier = Barrier(2)
    data = CheckoutRequest.model_validate({"lines": [{"product_id": item["id"], "quantity": 1}]})

    def sale(key):
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait()
            try:
                invoice = confirm_checkout(db, user, data, key)
                db.commit()
                return ("ok", str(invoice.id))
            except HTTPException as exc:
                db.rollback()
                return ("error", exc.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(sale, ["concurrent-sale-a", "concurrent-sale-b"]))
    assert [x[0] for x in results].count("ok") == 1 and [x[0] for x in results].count("error") == 1
    with SessionLocal() as db:
        assert (
            db.query(Invoice).count() == 1
            and db.query(StockMovement).filter(StockMovement.invoice_id.is_not(None)).count() == 1
        )


def test_postgresql_concurrent_duplicate_key_returns_one_invoice(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL idempotency verification")
    item = product(authenticated_client)
    stock(authenticated_client, item, 2)
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
    barrier = Barrier(2)
    data = CheckoutRequest.model_validate({"lines": [{"product_id": item["id"], "quantity": 1}]})

    def sale(_):
        with SessionLocal() as db:
            user = db.get(User, user_id)
            barrier.wait()
            invoice = confirm_checkout(db, user, data, "same-concurrent-key")
            db.commit()
            return str(invoice.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(sale, range(2)))
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert (
            db.query(Invoice).count() == 1
            and db.query(StockMovement).filter(StockMovement.invoice_id.is_not(None)).count() == 1
        )
