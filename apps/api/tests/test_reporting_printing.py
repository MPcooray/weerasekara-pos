from datetime import UTC, date, datetime
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.reporting import utc_bounds


def create_product(client, price=100000):
    response = client.post(
        "/api/v1/products",
        json={
            "name": "Report Frame",
            "sku": f"REPORT-{uuid4().hex[:8]}",
            "category": "spectacle_frame",
            "cost_price_minor": 50000,
            "selling_price_minor": price,
            "track_stock": True,
            "tax_rate": 0,
            "tax_inclusive": False,
            "reorder_threshold": 1,
        },
    )
    assert response.status_code == 201, response.text
    item = response.json()
    stocked = client.post(
        f"/api/v1/products/{item['id']}/movements",
        json={
            "quantity_delta": 5,
            "movement_type": "opening_stock",
            "expected_version": item["stock_version"],
            "reason": "Report test",
        },
    )
    assert stocked.status_code == 201
    return item


def customer_and_exam(client):
    customer = client.post(
        "/api/v1/customers",
        json={"full_name": "Reporting Customer", "mobile_number": "0772345678"},
    ).json()["customer"]
    visit = client.post(
        f"/api/v1/customers/{customer['id']}/visits",
        json={"purpose": "Optical examination"},
    ).json()
    exam = client.post(
        f"/api/v1/customers/{customer['id']}/examinations",
        json={
            "visit_id": visit["id"],
            "prescription_type": "distance",
            "od_sphere": "-1.00",
        },
    ).json()
    finalized = client.post(
        f"/api/v1/examinations/{exam['id']}/finalize",
        json={"expected_version": exam["version"]},
    )
    assert finalized.status_code == 200
    return customer, finalized.json()


def test_full_workflow_report_reconciliation_and_snapshot_printing(authenticated_client):
    customer, exam = customer_and_exam(authenticated_client)
    item = create_product(authenticated_client)
    sale = authenticated_client.post(
        "/api/v1/checkout/confirm",
        json={
            "customer_id": customer["id"],
            "examination_id": exam["id"],
            "invoice_discount_minor": 10000,
            "lines": [{"product_id": item["id"], "quantity": 2}],
        },
        headers={"Idempotency-Key": "report-workflow-sale"},
    )
    assert sale.status_code == 201, sale.text
    invoice = sale.json()
    payment = authenticated_client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        json={"amount_minor": 150000, "method": "cash"},
        headers={"Idempotency-Key": "report-workflow-payment"},
    )
    assert payment.status_code == 201
    returned = authenticated_client.post(
        f"/api/v1/invoices/{invoice['id']}/returns",
        json={
            "reason": "Reporting return",
            "lines": [
                {
                    "invoice_line_id": invoice["lines"][0]["id"],
                    "quantity": 1,
                    "restock": True,
                }
            ],
        },
        headers={"Idempotency-Key": "report-workflow-return"},
    )
    approved = authenticated_client.post(
        f"/api/v1/returns/{returned.json()['id']}/approve",
        headers={"Idempotency-Key": "report-workflow-credit"},
    )
    assert approved.status_code == 200
    credit_id = approved.json()["credit_note_id"]
    refunded = authenticated_client.post(
        f"/api/v1/credit-notes/{credit_id}/refunds",
        json={"amount_minor": 30000, "method": "cash", "reason": "Cash returned"},
        headers={"Idempotency-Key": "report-workflow-refund"},
    )
    assert refunded.status_code == 201

    today = date.today().isoformat()
    report = authenticated_client.get(
        f"/api/v1/reports/financial?date_from={today}&date_to={today}"
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["invoiced_sales_minor"] == 190000
    assert data["payments_received_minor"] == 150000
    assert data["refunds_minor"] == 30000
    assert data["credit_notes_minor"] == 95000
    assert data["discounts_minor"] == 10000
    assert data["outstanding_minor"] == 0
    assert {x["name"]: x["amount_minor"] for x in data["payment_methods"]}["cash"] == 150000

    printed = authenticated_client.get(f"/api/v1/print-documents/invoice/{invoice['id']}")
    assert printed.status_code == 200
    assert printed.json()["customer_name"] == "Reporting Customer"
    assert printed.json()["total_minor"] == 190000
    authenticated_client.patch(
        f"/api/v1/products/{item['id']}", json={"selling_price_minor": 999999}
    )
    snapshot = authenticated_client.get(f"/api/v1/print-documents/receipt/{invoice['id']}")
    assert snapshot.json()["total_minor"] == 190000
    assert snapshot.json()["lines"][0]["unit_price_minor"] == 100000
    assert (
        authenticated_client.get(
            f"/api/v1/print-documents/payment/{payment.json()['payment']['id']}"
        ).status_code
        == 200
    )
    assert (
        authenticated_client.get(f"/api/v1/print-documents/credit-note/{credit_id}").status_code
        == 200
    )
    assert (
        authenticated_client.get(
            f"/api/v1/print-documents/refund/{refunded.json()['id']}"
        ).status_code
        == 200
    )


def test_colombo_boundaries_branding_csv_and_dashboard(authenticated_client):
    start, end = utc_bounds(date(2026, 1, 1), date(2026, 1, 1))
    assert start == datetime(2025, 12, 31, 18, 30, tzinfo=UTC)
    assert end == datetime(2026, 1, 1, 18, 30, tzinfo=UTC)
    branding = authenticated_client.patch(
        "/api/v1/tenant/branding",
        json={
            "business_display_name": "Weerasekara Optics",
            "business_address": "Colombo, Sri Lanka",
            "invoice_footer": "Thank you for your business.",
        },
    )
    assert branding.status_code == 200
    assert (
        authenticated_client.get("/api/v1/tenant/branding").json()["business_address"]
        == "Colombo, Sri Lanka"
    )
    today = date.today().isoformat()
    csv_response = authenticated_client.get(
        f"/api/v1/reports/financial.csv?date_from={today}&date_to={today}"
    )
    assert csv_response.status_code == 200
    assert "invoiced_sales" in csv_response.text
    dashboard = authenticated_client.get("/api/v1/dashboard")
    assert dashboard.status_code == 200
    assert len(dashboard.json()["trend"]) == 7


def test_reporting_permissions_and_tenant_isolation(authenticated_client, client):
    item = create_product(authenticated_client)
    invoice = authenticated_client.post(
        "/api/v1/checkout/confirm",
        json={"lines": [{"product_id": item["id"], "quantity": 1}]},
        headers={"Idempotency-Key": "report-isolation-sale"},
    ).json()
    with SessionLocal() as db:
        primary = db.query(Tenant).filter_by(slug="weerasekara-optics").one()
        cashier = User(
            tenant_id=primary.id,
            email="report-cashier@example.com",
            full_name="Report Cashier",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.CASHIER,
        )
        other = Tenant(name="Other Reporter", slug="other-reporter")
        db.add_all([cashier, other])
        db.flush()
        other_owner = User(
            tenant_id=other.id,
            email="owner@other-reporter.example",
            full_name="Other Owner",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(other_owner)
        db.commit()
        cashier_token = create_access_token(
            user_id=str(cashier.id), tenant_id=str(primary.id), role=cashier.role.value
        )
        other_token = create_access_token(
            user_id=str(other_owner.id), tenant_id=str(other.id), role=other_owner.role.value
        )
    today = date.today().isoformat()
    assert (
        client.get(
            f"/api/v1/reports/financial?date_from={today}&date_to={today}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/tenant/branding",
            json={"business_display_name": "Not allowed"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        ).status_code
        == 403
    )
    other_report = client.get(
        f"/api/v1/reports/financial?date_from={today}&date_to={today}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_report.status_code == 200
    assert other_report.json()["invoiced_sales_minor"] == 0
    assert (
        client.get(
            f"/api/v1/print-documents/invoice/{invoice['id']}",
            headers={"Authorization": f"Bearer {other_token}"},
        ).status_code
        == 404
    )
