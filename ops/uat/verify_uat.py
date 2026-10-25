"""Verify the fictional UAT dataset, role boundaries, reconciliation and API timings."""

from datetime import UTC, datetime, timedelta
from time import perf_counter
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.customer import Customer
from app.models.examination import Examination
from app.models.finance import Invoice, Payment, Quotation, Refund, Return
from app.models.inventory import InventoryBalance, StockMovement
from app.models.order import OpticalOrder, OpticalOrderStatus
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.user import User, UserRole

TENANT_SLUG = "weerasekara-uat-fictional"
PASSWORD = "FictionalUAT123!"


def ensure_disposable_database() -> None:
    parsed = urlparse(
        get_settings().database_url.replace("postgresql+psycopg", "postgresql")
    )
    if not parsed.path.removeprefix("/").startswith("tetrova_uat_"):
        raise SystemExit(
            "Refusing to verify: database name must start with tetrova_uat_"
        )


def timed(client: TestClient, path: str, headers: dict[str, str], label: str):
    started = perf_counter()
    response = client.get(path, headers=headers)
    elapsed_ms = (perf_counter() - started) * 1000
    if response.status_code != 200:
        raise RuntimeError(f"{label}: {response.status_code} {response.text}")
    print(f"timing {label}={elapsed_ms:.2f}ms")
    return response.json()


def login(client: TestClient, role: UserRole) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": TENANT_SLUG,
            "email": f"{role.value}@uat.example.com",
            "password": PASSWORD,
        },
    )
    if response.status_code != 200:
        raise RuntimeError(response.text)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


ensure_disposable_database()
with SessionLocal() as db:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    if tenant is None:
        raise SystemExit("Fictional UAT tenant is missing")
    tenant_id = tenant.id
    counts = {
        "customers": db.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.tenant_id == tenant_id)
        ),
        "employees": db.scalar(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
        ),
        "examinations": db.scalar(
            select(func.count())
            .select_from(Examination)
            .where(Examination.tenant_id == tenant_id)
        ),
        "products": db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.tenant_id == tenant_id)
        ),
        "invoices": db.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.tenant_id == tenant_id)
        ),
        "quotations": db.scalar(
            select(func.count())
            .select_from(Quotation)
            .where(Quotation.tenant_id == tenant_id)
        ),
        "orders": db.scalar(
            select(func.count())
            .select_from(OpticalOrder)
            .where(OpticalOrder.tenant_id == tenant_id)
        ),
        "returns": db.scalar(
            select(func.count())
            .select_from(Return)
            .where(Return.tenant_id == tenant_id)
        ),
        "refunds": db.scalar(
            select(func.count())
            .select_from(Refund)
            .where(Refund.tenant_id == tenant_id)
        ),
    }
    expected = {
        "customers": 120,
        "employees": 4,
        "examinations": 24,
        "products": 12,
        "invoices": 18,
        "quotations": 5,
        "orders": 6,
        "returns": 1,
        "refunds": 1,
    }
    if counts != expected:
        raise RuntimeError(f"Unexpected UAT counts: {counts}")
    roles = set(db.scalars(select(User.role).where(User.tenant_id == tenant_id)).all())
    if roles != set(UserRole):
        raise RuntimeError(f"Missing role fixtures: {roles}")
    invoices = db.scalars(select(Invoice).where(Invoice.tenant_id == tenant_id)).all()
    for invoice in invoices:
        if (
            invoice.paid_minor
            - invoice.refunded_minor
            + invoice.outstanding_minor
            + invoice.credited_minor
            != invoice.total_minor
        ):
            raise RuntimeError(f"Invoice equation failed: {invoice.invoice_number}")
        recorded = db.scalar(
            select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                Payment.tenant_id == tenant_id, Payment.invoice_id == invoice.id
            )
        )
        if recorded != invoice.paid_minor:
            raise RuntimeError(
                f"Payment reconciliation failed: {invoice.invoice_number}"
            )
    balances = db.execute(
        select(
            InventoryBalance.product_id,
            InventoryBalance.location_id,
            InventoryBalance.quantity,
        ).where(InventoryBalance.tenant_id == tenant_id)
    ).all()
    for product_id, location_id, quantity in balances:
        ledger = db.scalar(
            select(func.coalesce(func.sum(StockMovement.quantity_delta), 0)).where(
                StockMovement.tenant_id == tenant_id,
                StockMovement.product_id == product_id,
                StockMovement.location_id == location_id,
            )
        )
        if quantity != ledger or quantity < 0:
            raise RuntimeError(f"Inventory reconciliation failed for {product_id}")
    collected = db.scalar(
        select(func.count())
        .select_from(OpticalOrder)
        .where(
            OpticalOrder.tenant_id == tenant_id,
            OpticalOrder.status == OpticalOrderStatus.COLLECTED,
        )
    )
    if collected != 2:
        raise RuntimeError("Expected two collected fictional UAT orders")
    first_invoice = invoices[0]
    payment_id = db.scalar(
        select(Payment.id).where(Payment.invoice_id == first_invoice.id)
    )
    quote_id = db.scalar(select(Quotation.id).where(Quotation.tenant_id == tenant_id))

with TestClient(app) as client:
    owner = login(client, UserRole.OWNER)
    manager = login(client, UserRole.MANAGER)
    cashier = login(client, UserRole.CASHIER)
    optometrist = login(client, UserRole.OPTOMETRIST)
    assert client.get("/api/v1/dashboard", headers=owner).status_code == 200
    assert client.get("/api/v1/dashboard", headers=manager).status_code == 200
    assert client.get("/api/v1/dashboard", headers=cashier).status_code == 403
    assert client.get("/api/v1/invoices", headers=optometrist).status_code == 403
    assert client.get("/api/v1/staff", headers=manager).status_code == 403
    assert client.get("/api/v1/suppliers", headers=cashier).status_code == 403
    product = timed(
        client, "/api/v1/products?search=UAT-001", cashier, "product_search"
    )
    if product["items"][0]["cost_price_minor"] is not None:
        raise RuntimeError("Cashier product response leaked cost")
    timed(client, "/api/v1/customers?search=UAT-CUST-0100", cashier, "customer_search")
    timed(client, "/api/v1/invoices?page=1&page_size=20", owner, "invoice_history")
    timed(client, "/api/v1/orders?page=1&page_size=20", manager, "order_directory")
    timed(client, "/api/v1/dashboard", owner, "dashboard")
    date_from = (datetime.now(UTC) - timedelta(days=60)).date().isoformat()
    date_to = datetime.now(UTC).date().isoformat()
    timed(
        client,
        f"/api/v1/reports/financial?date_from={date_from}&date_to={date_to}",
        owner,
        "financial_report",
    )
    for document_type, document_id in (
        ("invoice", first_invoice.id),
        ("receipt", first_invoice.id),
        ("payment", payment_id),
        ("quotation", quote_id),
    ):
        result = client.get(
            f"/api/v1/print-documents/{document_type}/{document_id}", headers=owner
        )
        if result.status_code != 200:
            raise RuntimeError(f"Print source failed: {document_type} {result.text}")

print(f"Fictional UAT verification passed: {counts}; collected_orders={collected}")
