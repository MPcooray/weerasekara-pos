from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.inventory import StockMovement
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def product_payload(**overrides):
    data = {
        "name": "Classic Acetate Frame",
        "sku": "FRM-001",
        "barcode": "4791234567890",
        "category": "spectacle_frame",
        "brand": "Tetrova",
        "cost_price_minor": 450000,
        "selling_price_minor": 790000,
        "track_stock": True,
        "reorder_threshold": 2,
    }
    data.update(overrides)
    return data


def create_product(client, **overrides):
    return client.post("/api/v1/products", json=product_payload(**overrides))


def test_product_supplier_stock_and_reporting(authenticated_client):
    supplier = authenticated_client.post(
        "/api/v1/suppliers",
        json={"business_name": "Vision Imports", "telephone": "0112345678"},
    )
    assert supplier.status_code == 201
    product = create_product(authenticated_client, supplier_id=supplier.json()["id"])
    assert product.status_code == 201
    assert product.json()["cost_price_minor"] == 450000
    product_id = product.json()["id"]

    received = authenticated_client.post(
        f"/api/v1/products/{product_id}/movements",
        json={
            "quantity_delta": 8,
            "movement_type": "stock_received",
            "reference": "GRN-1001",
            "reason": "Supplier delivery",
            "expected_version": 1,
        },
    )
    assert received.status_code == 201
    assert received.json()["balance_after"] == 8
    detail = authenticated_client.get(f"/api/v1/products/{product_id}").json()
    assert detail["quantity"] == 8
    assert detail["stock_version"] == 2
    summary = authenticated_client.get("/api/v1/inventory/summary").json()
    assert summary["total_units"] == 8
    assert summary["valuation_minor"] == 3_600_000


def test_sku_barcode_uniqueness_search_and_update(authenticated_client):
    first = create_product(authenticated_client)
    assert first.status_code == 201
    assert create_product(authenticated_client, name="Duplicate").status_code == 409
    assert create_product(authenticated_client, sku="FRM-002").status_code == 409
    found = authenticated_client.get("/api/v1/products?search=4791234567890").json()
    assert found["total"] == 1
    updated = authenticated_client.patch(
        f"/api/v1/products/{first.json()['id']}", json={"selling_price_minor": 850000}
    )
    assert updated.status_code == 200
    assert updated.json()["selling_price_minor"] == 850000


def test_negative_stock_concurrency_and_archived_restrictions(authenticated_client):
    product = create_product(authenticated_client).json()
    path = f"/api/v1/products/{product['id']}/movements"
    negative = authenticated_client.post(
        path,
        json={"quantity_delta": -1, "movement_type": "damaged_stock", "expected_version": 1},
    )
    assert negative.status_code == 409
    assert (
        authenticated_client.post(
            path,
            json={"quantity_delta": 4, "movement_type": "opening_stock", "expected_version": 1},
        ).status_code
        == 201
    )
    stale = authenticated_client.post(
        path,
        json={"quantity_delta": 1, "movement_type": "stock_received", "expected_version": 1},
    )
    assert stale.status_code == 409
    assert (
        authenticated_client.patch(
            f"/api/v1/products/{product['id']}", json={"is_archived": True}
        ).status_code
        == 200
    )
    blocked = authenticated_client.post(
        path,
        json={"quantity_delta": 1, "movement_type": "stock_received", "expected_version": 2},
    )
    assert blocked.status_code == 409
    with SessionLocal() as db:
        movement = db.query(StockMovement).one()
        movement.quantity_delta = 999
        db.rollback()
        assert db.query(StockMovement).one().quantity_delta == 4


def test_tenant_isolation_and_cashier_read_only(authenticated_client, client):
    product = create_product(authenticated_client).json()
    with SessionLocal() as db:
        tenant = Tenant(name="Other Optics", slug="other-optics")
        db.add(tenant)
        db.flush()
        cashier = User(
            tenant_id=tenant.id,
            email="cashier@example.com",
            full_name="Cashier",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.CASHIER,
        )
        db.add(cashier)
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "other-optics",
            "email": "cashier@example.com",
            "password": "SafePassword123!",
        },
    )
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    assert client.get(f"/api/v1/products/{product['id']}").status_code == 404
    assert create_product(client, sku="FRM-001", barcode="4791234567890").status_code == 403
    assert client.get("/api/v1/products").json()["total"] == 0
