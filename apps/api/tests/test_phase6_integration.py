from datetime import timedelta
from uuid import uuid4

from app.core.time import colombo_today


def _post(client, path, *, json, key=None):
    headers = {"Idempotency-Key": key or f"phase6-{uuid4()}"}
    response = client.post(path, json=json, headers=headers)
    assert response.status_code in {200, 201}, response.text
    return response.json()


def test_customer_to_collected_order_reconciles_finance_and_stock(authenticated_client):
    customer = authenticated_client.post(
        "/api/v1/customers",
        json={"full_name": "Nadeesha Perera", "mobile_number": "0772345678"},
    ).json()["customer"]
    visit = authenticated_client.post(
        f"/api/v1/customers/{customer['id']}/visits",
        json={"purpose": "Eye test and new spectacles"},
    ).json()
    exam = authenticated_client.post(
        f"/api/v1/customers/{customer['id']}/examinations",
        json={
            "visit_id": visit["id"],
            "prescription_type": "distance",
            "od_sphere": "-1.50",
            "os_sphere": "-1.25",
            "pd_binocular": "62.00",
        },
    ).json()
    exam = authenticated_client.post(
        f"/api/v1/examinations/{exam['id']}/finalize",
        json={"expected_version": exam["version"]},
    ).json()

    frame = authenticated_client.post(
        "/api/v1/products",
        json={
            "name": "Phase 6 Acetate Frame",
            "sku": f"P6-FRM-{uuid4().hex[:8]}",
            "category": "spectacle_frame",
            "cost_price_minor": 450000,
            "selling_price_minor": 800000,
            "track_stock": True,
            "tax_rate": 0,
        },
    ).json()
    authenticated_client.post(
        f"/api/v1/products/{frame['id']}/movements",
        json={
            "quantity_delta": 2,
            "movement_type": "opening_stock",
            "expected_version": frame["stock_version"],
        },
    )
    lenses = authenticated_client.post(
        "/api/v1/products",
        json={
            "name": "Made-to-order 1.60 lenses",
            "sku": f"P6-LNS-{uuid4().hex[:8]}",
            "category": "prescription_lens",
            "cost_price_minor": 300000,
            "selling_price_minor": 600000,
            "track_stock": False,
            "made_to_order": True,
            "tax_rate": 0,
        },
    ).json()
    invoice = _post(
        authenticated_client,
        "/api/v1/checkout/confirm",
        json={
            "customer_id": customer["id"],
            "examination_id": exam["id"],
            "lines": [
                {"product_id": frame["id"], "quantity": 1},
                {"product_id": lenses["id"], "quantity": 1},
            ],
        },
    )
    assert invoice["total_minor"] == 1_400_000
    assert authenticated_client.get(f"/api/v1/products/{frame['id']}").json()["quantity"] == 1

    first_payment = _post(
        authenticated_client,
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount_minor": 400000, "method": "cash", "reference": "ADV-P6"},
    )
    assert first_payment["invoice"]["outstanding_minor"] == 1_000_000

    order = _post(
        authenticated_client,
        "/api/v1/orders",
        json={
            "customer_id": customer["id"],
            "visit_id": visit["id"],
            "examination_id": exam["id"],
            "invoice_id": invoice["id"],
            "frame_product_id": frame["id"],
            "lens_type": "Single vision",
            "lens_material": "Polycarbonate",
            "refractive_index": "1.60",
            "coatings": ["Anti-reflective", "UV"],
            "expected_collection_date": "2026-11-10",
        },
    )
    assert authenticated_client.get(f"/api/v1/products/{frame['id']}").json()["quantity"] == 1

    supplier = authenticated_client.post(
        "/api/v1/suppliers", json={"business_name": "Colombo Lens Laboratory"}
    ).json()
    tracked = authenticated_client.put(
        f"/api/v1/orders/{order['id']}/supplier",
        json={"supplier_id": supplier["id"], "status": "ordered", "ordered_on": "2026-10-25"},
    )
    assert tracked.status_code == 200, tracked.text
    for status in ("confirmed", "awaiting_lenses", "in_preparation", "quality_check"):
        order = _post(
            authenticated_client,
            f"/api/v1/orders/{order['id']}/transitions",
            json={"status": status, "expected_version": order["version"]},
        )
    checked = authenticated_client.post(
        f"/api/v1/orders/{order['id']}/quality-check",
        json={
            "prescription_verified": True,
            "lenses_inspected": True,
            "frame_inspected": True,
            "fitting_confirmed": True,
        },
    )
    assert checked.status_code == 201, checked.text
    order = _post(
        authenticated_client,
        f"/api/v1/orders/{order['id']}/transitions",
        json={"status": "ready_for_collection", "expected_version": order["version"]},
    )
    remaining = _post(
        authenticated_client,
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount_minor": 1_000_000, "method": "card", "reference": "TERM-P6"},
    )
    assert remaining["invoice"]["status"] == "paid"
    collected = _post(
        authenticated_client,
        f"/api/v1/orders/{order['id']}/collect",
        json={"expected_version": order["version"], "allow_outstanding_balance": False},
    )
    assert collected["status"] == "collected"
    assert collected["outstanding_minor"] == 0
    examinations = authenticated_client.get(
        f"/api/v1/customers/{customer['id']}/examinations"
    ).json()
    profile = authenticated_client.get(f"/api/v1/customers/{customer['id']}").json()
    assert len(examinations) == 1
    assert profile["visits"][0]["id"] == visit["id"]


def test_dashboard_excludes_expired_issued_quotations(authenticated_client):
    product = authenticated_client.post(
        "/api/v1/products",
        json={
            "name": "Quotation eye test",
            "sku": f"P6-Q-{uuid4().hex[:8]}",
            "category": "optical_service",
            "cost_price_minor": 0,
            "selling_price_minor": 100000,
            "track_stock": False,
            "tax_rate": 0,
        },
    ).json()
    authenticated_client.post(
        "/api/v1/quotations", json={"lines": [{"product_id": product["id"], "quantity": 1}]}
    )
    expired = authenticated_client.post(
        "/api/v1/quotations",
        json={
            "expires_on": str(colombo_today() - timedelta(days=1)),
            "lines": [{"product_id": product["id"], "quantity": 1}],
        },
    ).json()
    issued = authenticated_client.post(
        f"/api/v1/quotations/{expired['id']}/issue",
        headers={"Idempotency-Key": "phase6-expired-issue"},
    )
    assert issued.status_code == 200
    assert authenticated_client.get("/api/v1/dashboard").json()["pending_quotations"] == 1
