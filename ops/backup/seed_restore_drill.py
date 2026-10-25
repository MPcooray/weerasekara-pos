"""Seed a disposable database for the documented backup/restore drill."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def require(response, expected=(200, 201)):
    if response.status_code not in expected:
        raise RuntimeError(
            f"{response.request.url}: {response.status_code} {response.text}"
        )
    return response.json() if response.content else None


with SessionLocal() as db:
    tenant = Tenant(name="Phase 7 Restore Drill", slug="phase7-restore-drill")
    db.add(tenant)
    db.flush()
    db.add(
        User(
            tenant_id=tenant.id,
            email="restore-drill@example.com",
            full_name="Restore Drill Owner",
            password_hash=hash_password("RestoreDrillPassword123!"),
            role=UserRole.OWNER,
        )
    )
    db.commit()

with TestClient(app) as client:
    token = require(
        client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "phase7-restore-drill",
                "email": "restore-drill@example.com",
                "password": "RestoreDrillPassword123!",
            },
        )
    )["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    customer = require(
        client.post(
            "/api/v1/customers",
            json={"full_name": "Restore Test Customer", "mobile_number": "0772345678"},
        )
    )["customer"]
    visit = require(
        client.post(
            f"/api/v1/customers/{customer['id']}/visits",
            json={"purpose": "Restore drill examination"},
        )
    )
    examination = require(
        client.post(
            f"/api/v1/customers/{customer['id']}/examinations",
            json={
                "visit_id": visit["id"],
                "prescription_type": "distance",
                "od_sphere": "-1.00",
                "os_sphere": "-1.25",
                "pd_binocular": "62.00",
            },
        )
    )
    examination = require(
        client.post(
            f"/api/v1/examinations/{examination['id']}/finalize",
            json={"expected_version": examination["version"]},
        )
    )
    frame = require(
        client.post(
            "/api/v1/products",
            json={
                "name": "Restore Drill Frame",
                "sku": f"DRILL-{uuid4().hex[:8]}",
                "category": "spectacle_frame",
                "cost_price_minor": 400000,
                "selling_price_minor": 800000,
                "track_stock": True,
                "tax_rate": 0,
            },
        )
    )
    require(
        client.post(
            f"/api/v1/products/{frame['id']}/movements",
            json={
                "quantity_delta": 3,
                "movement_type": "opening_stock",
                "expected_version": frame["stock_version"],
            },
        )
    )
    invoice = require(
        client.post(
            "/api/v1/checkout/confirm",
            json={
                "customer_id": customer["id"],
                "examination_id": examination["id"],
                "lines": [{"product_id": frame["id"], "quantity": 1}],
            },
            headers={"Idempotency-Key": "phase7-drill-checkout"},
        )
    )
    require(
        client.post(
            f"/api/v1/invoices/{invoice['id']}/payments",
            json={"amount_minor": 300000, "method": "cash", "reference": "DRILL-PAY"},
            headers={"Idempotency-Key": "phase7-drill-payment"},
        )
    )
    require(
        client.post(
            "/api/v1/orders",
            json={
                "customer_id": customer["id"],
                "visit_id": visit["id"],
                "examination_id": examination["id"],
                "invoice_id": invoice["id"],
                "frame_product_id": frame["id"],
                "lens_type": "Single vision",
                "coatings": ["Anti-reflective"],
            },
            headers={"Idempotency-Key": "phase7-drill-order"},
        )
    )

print("Restore drill seed created successfully")
