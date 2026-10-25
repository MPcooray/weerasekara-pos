from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal, engine
from app.models.order import OpticalOrder
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.orders import TransitionRequest
from app.services.orders import transition_order


def setup_data(client, invoice=True):
    customer = client.post(
        "/api/v1/customers", json={"full_name": "Order Customer", "mobile_number": "0771234567"}
    ).json()["customer"]
    visit = client.post(
        f"/api/v1/customers/{customer['id']}/visits", json={"purpose": "Spectacles"}
    ).json()
    exam = client.post(
        f"/api/v1/customers/{customer['id']}/examinations",
        json={
            "visit_id": visit["id"],
            "prescription_type": "distance",
            "od_sphere": "-1.25",
            "os_sphere": "-1.00",
            "pd_binocular": "62.00",
        },
    ).json()
    exam = client.post(
        f"/api/v1/examinations/{exam['id']}/finalize", json={"expected_version": exam["version"]}
    ).json()
    frame = client.post(
        "/api/v1/products",
        json={
            "name": "Order Frame",
            "sku": f"ORD-{uuid4().hex[:8]}",
            "category": "spectacle_frame",
            "cost_price_minor": 50000,
            "selling_price_minor": 100000,
            "track_stock": True,
            "tax_rate": 0,
            "tax_inclusive": False,
        },
    ).json()
    client.post(
        f"/api/v1/products/{frame['id']}/movements",
        json={
            "quantity_delta": 5,
            "movement_type": "opening_stock",
            "expected_version": frame["stock_version"],
        },
    )
    sale = None
    if invoice:
        sale = client.post(
            "/api/v1/checkout/confirm",
            json={
                "customer_id": customer["id"],
                "examination_id": exam["id"],
                "lines": [{"product_id": frame["id"], "quantity": 1}],
            },
            headers={"Idempotency-Key": f"order-sale-{uuid4()}"},
        ).json()
    return customer, visit, exam, frame, sale


def payload(customer, visit, exam, frame, invoice=None):
    return {
        "customer_id": customer["id"],
        "visit_id": visit["id"],
        "examination_id": exam["id"],
        "invoice_id": invoice["id"] if invoice else None,
        "frame_product_id": frame["id"],
        "lens_type": "Progressive",
        "lens_material": "Polycarbonate",
        "refractive_index": "1.60",
        "coatings": ["Anti-reflective", "UV"],
        "right_lens_details": "Digital freeform",
        "left_lens_details": "Digital freeform",
        "expected_collection_date": "2026-11-10",
    }


def create(client, data, key):
    return client.post("/api/v1/orders", json=data, headers={"Idempotency-Key": key})


def move(client, order, status, key, reason="Workflow update"):
    return client.post(
        f"/api/v1/orders/{order['id']}/transitions",
        json={"status": status, "expected_version": order["version"], "reason": reason},
        headers={"Idempotency-Key": key},
    )


def test_creation_snapshot_invoice_idempotency_and_no_double_stock(authenticated_client):
    customer, visit, exam, frame, invoice = setup_data(authenticated_client)
    data = payload(customer, visit, exam, frame, invoice)
    created = create(authenticated_client, data, "create-order-001")
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["invoice_id"] == invoice["id"]
    assert order["prescription_snapshot"]["od_sphere"] == "-1.25"
    assert order["frame_snapshot"]["name"] == "Order Frame"
    assert create(authenticated_client, data, "create-order-001").json()["id"] == order["id"]
    assert authenticated_client.get(f"/api/v1/products/{frame['id']}").json()["quantity"] == 4
    authenticated_client.patch(f"/api/v1/products/{frame['id']}", json={"name": "Renamed Frame"})
    assert (
        authenticated_client.get(f"/api/v1/orders/{order['id']}").json()["frame_snapshot"]["name"]
        == "Order Frame"
    )


def test_lifecycle_supplier_quality_and_outstanding_collection(authenticated_client):
    customer, visit, exam, frame, invoice = setup_data(authenticated_client)
    order = create(
        authenticated_client, payload(customer, visit, exam, frame, invoice), "workflow-create"
    ).json()
    assert (
        move(authenticated_client, order, "ready_for_collection", "invalid-jump").status_code == 409
    )
    for status in ("confirmed", "awaiting_lenses", "in_preparation", "quality_check"):
        response = move(authenticated_client, order, status, f"move-{status}")
        assert response.status_code == 200, response.text
        order = response.json()
    supplier = authenticated_client.post(
        "/api/v1/suppliers", json={"business_name": "Lens Laboratory"}
    ).json()
    tracking = authenticated_client.put(
        f"/api/v1/orders/{order['id']}/supplier",
        json={
            "supplier_id": supplier["id"],
            "supplier_reference": "LAB-100",
            "ordered_on": "2026-10-25",
            "expected_delivery": "2026-10-30",
            "status": "ordered",
        },
    )
    assert tracking.status_code == 200
    incomplete = authenticated_client.post(
        f"/api/v1/orders/{order['id']}/quality-check",
        json={
            "prescription_verified": True,
            "lenses_inspected": True,
            "frame_inspected": False,
            "fitting_confirmed": True,
        },
    )
    assert incomplete.status_code == 422
    checked = authenticated_client.post(
        f"/api/v1/orders/{order['id']}/quality-check",
        json={
            "prescription_verified": True,
            "lenses_inspected": True,
            "frame_inspected": True,
            "fitting_confirmed": True,
            "remarks": "Passed",
        },
    )
    assert checked.status_code == 201
    order = authenticated_client.get(f"/api/v1/orders/{order['id']}").json()
    order = move(authenticated_client, order, "ready_for_collection", "ready-order").json()
    denied = authenticated_client.post(
        f"/api/v1/orders/{order['id']}/collect",
        json={"expected_version": order["version"], "allow_outstanding_balance": False},
        headers={"Idempotency-Key": "collect-denied"},
    )
    assert denied.status_code == 409
    collected = authenticated_client.post(
        f"/api/v1/orders/{order['id']}/collect",
        json={
            "expected_version": order["version"],
            "allow_outstanding_balance": True,
            "notes": "Owner approved",
        },
        headers={"Idempotency-Key": "collect-approved"},
    )
    assert collected.status_code == 200
    result = collected.json()
    assert result["status"] == "collected" and result["collection"]["outstanding_override"]
    assert result["outstanding_minor"] == invoice["total_minor"]
    assert (
        authenticated_client.get(f"/api/v1/invoices/{invoice['id']}").json()["outstanding_minor"]
        == invoice["total_minor"]
    )


def test_cancellation_search_isolation_and_permissions(authenticated_client, client):
    customer, visit, exam, frame, _ = setup_data(authenticated_client, False)
    order = create(
        authenticated_client, payload(customer, visit, exam, frame), "cancel-create"
    ).json()
    cancelled = move(authenticated_client, order, "cancelled", "cancel-order", "Customer request")
    assert cancelled.status_code == 200 and len(cancelled.json()["events"]) == 2
    assert (
        authenticated_client.get(f"/api/v1/orders?search={order['order_number']}").json()["total"]
        == 1
    )
    with SessionLocal() as db:
        primary = db.scalar(select(Tenant).where(Tenant.slug == "weerasekara-optics"))
        cashier = User(
            tenant_id=primary.id,
            email="order-cashier@example.com",
            full_name="Cashier",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.CASHIER,
        )
        optometrist = User(
            tenant_id=primary.id,
            email="order-optometrist@example.com",
            full_name="Optometrist",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OPTOMETRIST,
        )
        other = Tenant(name="Other Orders", slug="other-orders")
        db.add_all([cashier, optometrist, other])
        db.flush()
        owner = User(
            tenant_id=other.id,
            email="order-owner@other.example",
            full_name="Other",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(owner)
        db.commit()
        cashier_token = create_access_token(
            user_id=str(cashier.id), tenant_id=str(primary.id), role=cashier.role.value
        )
        other_token = create_access_token(
            user_id=str(owner.id), tenant_id=str(other.id), role=owner.role.value
        )
        optometrist_token = create_access_token(
            user_id=str(optometrist.id),
            tenant_id=str(primary.id),
            role=optometrist.role.value,
        )
    assert (
        client.put(
            f"/api/v1/orders/{order['id']}/supplier",
            json={"supplier_id": str(uuid4()), "status": "ordered"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/api/v1/orders/{order['id']}", headers={"Authorization": f"Bearer {other_token}"}
        ).status_code
        == 404
    )
    clinical_order = client.get(
        f"/api/v1/orders/{order['id']}",
        headers={"Authorization": f"Bearer {optometrist_token}"},
    )
    assert clinical_order.status_code == 200
    assert clinical_order.json()["outstanding_minor"] is None
    assert clinical_order.json()["supplier_order"] is None


def test_postgresql_concurrent_transition(authenticated_client):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock verification")
    customer, visit, exam, frame, _ = setup_data(authenticated_client, False)
    order = create(
        authenticated_client, payload(customer, visit, exam, frame), "concurrent-create"
    ).json()
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "staff@example.com"))
    barrier = Barrier(2)

    def submit(key):
        with SessionLocal() as db:
            barrier.wait()
            try:
                result = transition_order(
                    db,
                    db.get(User, user_id),
                    UUID(order["id"]),
                    TransitionRequest(status="confirmed", expected_version=order["version"]),
                    key,
                )
                db.commit()
                return "ok", result.status.value
            except HTTPException as exc:
                db.rollback()
                return "error", exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ["concurrent-a", "concurrent-b"]))
    assert [x[0] for x in results].count("ok") == 1
    with SessionLocal() as db:
        assert db.get(OpticalOrder, UUID(order["id"])).version == 2
