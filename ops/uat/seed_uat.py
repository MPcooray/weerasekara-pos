"""Seed a disposable PostgreSQL database with deterministic fictional optical-shop UAT data."""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.customer import Customer
from app.models.finance import Invoice, Payment
from app.models.tenant import Tenant
from app.models.user import User, UserRole

TENANT_SLUG = "weerasekara-uat-fictional"
PASSWORD = "FictionalUAT123!"
ROLE_EMAILS = {
    UserRole.OWNER: "owner@uat.example.com",
    UserRole.MANAGER: "manager@uat.example.com",
    UserRole.CASHIER: "cashier@uat.example.com",
    UserRole.OPTOMETRIST: "optometrist@uat.example.com",
}


def ensure_disposable_database() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    parsed = urlparse(settings.database_url.replace("postgresql+psycopg", "postgresql"))
    database = parsed.path.removeprefix("/")
    if not settings.database_url.startswith("postgresql") or not database.startswith(
        "tetrova_uat_"
    ):
        raise SystemExit("Refusing to seed: database name must start with tetrova_uat_")


def require(response, expected=(200, 201)):
    if response.status_code not in expected:
        raise RuntimeError(
            f"{response.request.url}: {response.status_code} {response.text}"
        )
    return response.json() if response.content else None


def login(client: TestClient, role: UserRole) -> dict[str, str]:
    result = require(
        client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": TENANT_SLUG,
                "email": ROLE_EMAILS[role],
                "password": PASSWORD,
            },
        )
    )
    return {"Authorization": f"Bearer {result['access_token']}"}


def post(
    client: TestClient,
    path: str,
    role: dict[str, str],
    data: dict,
    key: str | None = None,
):
    headers = dict(role)
    if key:
        headers["Idempotency-Key"] = key
    return require(client.post(path, json=data, headers=headers))


ensure_disposable_database()

with SessionLocal.begin() as db:
    if db.scalar(select(Tenant).where(Tenant.slug == TENANT_SLUG)):
        raise SystemExit("Refusing to seed: fictional UAT tenant already exists")
    tenant = Tenant(name="Weerasekara Optics — FICTIONAL UAT", slug=TENANT_SLUG)
    db.add(tenant)
    db.flush()
    employees = {}
    for role, email in ROLE_EMAILS.items():
        employee = User(
            tenant_id=tenant.id,
            email=email,
            full_name=f"Fictional UAT {role.value.title()}",
            password_hash=hash_password(PASSWORD),
            role=role,
        )
        db.add(employee)
        employees[role] = employee
    db.flush()
    created_base = datetime.now(UTC) - timedelta(days=42)
    customers = []
    first_names = ("Nimal", "Kumari", "Saman", "Tharushi", "Isuru", "Nadeesha")
    last_names = ("Perera", "Silva", "Fernando", "Jayasinghe", "De Alwis")
    for index in range(1, 121):
        customer = Customer(
            tenant_id=tenant.id,
            customer_number=f"UAT-CUST-{index:04d}",
            full_name=f"{first_names[index % len(first_names)]} {last_names[index % len(last_names)]} UAT {index}",
            mobile_number=f"077{index:07d}",
            email=f"fictional.customer{index}@example.com" if index % 4 == 0 else None,
            address=f"Fictional address {index}, Colombo" if index % 3 == 0 else None,
            notes="FICTIONAL UAT RECORD — NOT A REAL CUSTOMER",
            created_by_id=employees[UserRole.CASHIER].id,
            created_at=created_base + timedelta(hours=index * 7),
            updated_at=created_base + timedelta(hours=index * 7),
        )
        db.add(customer)
        customers.append(customer)
    db.flush()
    customer_ids = [str(item.id) for item in customers]

with TestClient(app) as client:
    owner = login(client, UserRole.OWNER)
    manager = login(client, UserRole.MANAGER)
    cashier = login(client, UserRole.CASHIER)
    optometrist = login(client, UserRole.OPTOMETRIST)

    suppliers = [
        require(
            client.post(
                "/api/v1/suppliers",
                headers=manager,
                json={
                    "business_name": name,
                    "telephone": f"01120000{index:02d}",
                    "notes": "FICTIONAL UAT SUPPLIER",
                },
            )
        )
        for index, name in enumerate(
            (
                "Colombo Vision Lab UAT",
                "Lanka Frames UAT",
                "Coastal Contact Lenses UAT",
            ),
            1,
        )
    ]
    catalog = [
        ("Classic Acetate Frame", "spectacle_frame", 350_000, 750_000, True),
        ("Titanium Office Frame", "spectacle_frame", 600_000, 1_250_000, True),
        ("Children's Flexible Frame", "spectacle_frame", 280_000, 590_000, True),
        ("Premium Rimless Frame", "spectacle_frame", 800_000, 1_650_000, True),
        ("Polarized Aviator", "sunglasses", 450_000, 990_000, True),
        ("UV Sports Sunglasses", "sunglasses", 300_000, 690_000, True),
        ("Single Vision 1.56 Pair", "prescription_lens", 180_000, 450_000, False),
        ("Progressive 1.60 Pair", "prescription_lens", 500_000, 1_200_000, False),
        ("Monthly Contact Lens Pack", "contact_lens", 220_000, 480_000, True),
        ("Lens Cleaning Kit", "accessory", 35_000, 90_000, True),
        ("Hard Spectacle Case", "accessory", 30_000, 75_000, True),
        ("Comprehensive Eye Examination", "optical_service", 0, 150_000, False),
    ]
    products = []
    for index, (name, category, cost, price, tracked) in enumerate(catalog, 1):
        product = require(
            client.post(
                "/api/v1/products",
                headers=manager,
                json={
                    "name": f"{name} — UAT",
                    "sku": f"UAT-{index:03d}",
                    "category": category,
                    "supplier_id": suppliers[index % len(suppliers)]["id"],
                    "cost_price_minor": cost,
                    "selling_price_minor": price,
                    "track_stock": tracked,
                    "made_to_order": category == "prescription_lens",
                    "reorder_threshold": 5 if tracked else 0,
                    "tax_rate": 0,
                },
            )
        )
        products.append(product)
        if tracked:
            post(
                client,
                f"/api/v1/products/{product['id']}/movements",
                manager,
                {
                    "quantity_delta": 8 + index,
                    "movement_type": "opening_stock",
                    "reference": f"UAT-OPEN-{index:03d}",
                    "reason": "Fictional UAT opening stock",
                    "expected_version": product["stock_version"],
                },
            )

    examinations = []
    visits = []
    for index in range(24):
        when = datetime.now(UTC) - timedelta(days=35 - index)
        visit = post(
            client,
            f"/api/v1/customers/{customer_ids[index]}/visits",
            cashier,
            {
                "visit_at": when.isoformat(),
                "purpose": "Fictional UAT eye examination",
                "status": "completed",
            },
        )
        exam = post(
            client,
            f"/api/v1/customers/{customer_ids[index]}/examinations",
            optometrist,
            {
                "visit_id": visit["id"],
                "examined_at": when.isoformat(),
                "prescription_type": "progressive" if index % 5 == 0 else "distance",
                "od_sphere": f"-{1 + index % 4}.00",
                "od_cylinder": "-0.50",
                "od_axis": 90,
                "os_sphere": f"-{1 + (index + 1) % 4}.00",
                "os_cylinder": "-0.75",
                "os_axis": 85,
                "pd_binocular": "62.00",
                "notes": "FICTIONAL UAT CLINICAL RECORD",
            },
        )
        exam = post(
            client,
            f"/api/v1/examinations/{exam['id']}/finalize",
            optometrist,
            {"expected_version": exam["version"]},
        )
        visits.append(visit)
        examinations.append(exam)

    invoices = []
    for index in range(18):
        lines = [
            {
                "product_id": products[index % 6]["id"],
                "quantity": 1,
                "line_discount_minor": 25_000 if index % 4 == 0 else 0,
            },
            {"product_id": products[6 + index % 2]["id"], "quantity": 1},
        ]
        invoice = post(
            client,
            "/api/v1/checkout/confirm",
            cashier,
            {
                "customer_id": customer_ids[index],
                "examination_id": examinations[index]["id"],
                "invoice_discount_minor": 50_000 if index % 6 == 0 else 0,
                "lines": lines,
                "notes": "FICTIONAL UAT SALE",
            },
            f"uat-checkout-{index:03d}",
        )
        first_amount = (
            invoice["total_minor"] if index % 3 else invoice["total_minor"] // 2
        )
        post(
            client,
            f"/api/v1/invoices/{invoice['id']}/payments",
            cashier,
            {
                "amount_minor": first_amount,
                "method": ("cash", "card", "bank_transfer")[index % 3],
                "reference": f"UAT-PAY-{index:03d}",
            },
            f"uat-payment-{index:03d}-a",
        )
        if index in {3, 9, 15}:
            outstanding = invoice["total_minor"] - first_amount
            if outstanding:
                post(
                    client,
                    f"/api/v1/invoices/{invoice['id']}/payments",
                    cashier,
                    {
                        "amount_minor": outstanding,
                        "method": "card",
                        "reference": "UAT-MIXED",
                    },
                    f"uat-payment-{index:03d}-b",
                )
        invoices.append(invoice)

    quotations = []
    for index in range(5):
        quotation = post(
            client,
            "/api/v1/quotations",
            cashier,
            {
                "customer_id": customer_ids[30 + index],
                "expires_on": (datetime.now(UTC) + timedelta(days=14))
                .date()
                .isoformat(),
                "lines": [{"product_id": products[index]["id"], "quantity": 1}],
                "notes": "FICTIONAL UAT QUOTATION",
            },
        )
        quotation = post(
            client,
            f"/api/v1/quotations/{quotation['id']}/issue",
            cashier,
            {},
            f"uat-quote-issue-{index}",
        )
        quotations.append(quotation)

    orders = []
    for index in range(6):
        order = post(
            client,
            "/api/v1/orders",
            cashier,
            {
                "customer_id": customer_ids[index],
                "visit_id": visits[index]["id"],
                "examination_id": examinations[index]["id"],
                "invoice_id": invoices[index]["id"],
                "frame_product_id": products[index % 4]["id"],
                "lens_type": "Progressive" if index % 2 else "Single vision",
                "lens_material": "CR-39",
                "coatings": ["Anti-reflective", "UV"],
                "expected_collection_date": (datetime.now(UTC) + timedelta(days=7))
                .date()
                .isoformat(),
                "internal_notes": "FICTIONAL UAT ORDER",
            },
            f"uat-order-{index}",
        )
        require(
            client.put(
                f"/api/v1/orders/{order['id']}/supplier",
                headers=manager,
                json={
                    "supplier_id": suppliers[0]["id"],
                    "supplier_reference": f"UAT-LAB-{index:03d}",
                    "status": "ordered",
                },
            )
        )
        for status in (
            "confirmed",
            "awaiting_lenses",
            "in_preparation",
            "quality_check",
        ):
            order = post(
                client,
                f"/api/v1/orders/{order['id']}/transitions",
                manager,
                {"status": status, "expected_version": order["version"]},
                f"uat-order-{index}-{status}",
            )
        require(
            client.post(
                f"/api/v1/orders/{order['id']}/quality-check",
                headers=optometrist,
                json={
                    "prescription_verified": True,
                    "lenses_inspected": True,
                    "frame_inspected": True,
                    "fitting_confirmed": True,
                    "remarks": "Fictional UAT quality check",
                },
            )
        )
        order = post(
            client,
            f"/api/v1/orders/{order['id']}/transitions",
            manager,
            {"status": "ready_for_collection", "expected_version": order["version"]},
            f"uat-order-{index}-ready",
        )
        if index in {1, 2}:
            order = post(
                client,
                f"/api/v1/orders/{order['id']}/collect",
                cashier,
                {
                    "expected_version": order["version"],
                    "allow_outstanding_balance": False,
                },
                f"uat-order-{index}-collect",
            )
        orders.append(order)

    returned_invoice = require(
        client.get(f"/api/v1/invoices/{invoices[1]['id']}", headers=owner)
    )
    requested_return = post(
        client,
        f"/api/v1/invoices/{returned_invoice['id']}/returns",
        cashier,
        {
            "reason": "Fictional UAT customer return",
            "lines": [
                {
                    "invoice_line_id": returned_invoice["lines"][0]["id"],
                    "quantity": 1,
                    "restock": True,
                }
            ],
        },
        "uat-return-001",
    )
    approved_return = post(
        client,
        f"/api/v1/returns/{requested_return['id']}/approve",
        manager,
        {},
        "uat-return-approve-001",
    )
    credit = require(
        client.get(
            f"/api/v1/credit-notes/{approved_return['credit_note_id']}", headers=owner
        )
    )
    post(
        client,
        f"/api/v1/credit-notes/{credit['id']}/refunds",
        owner,
        {
            "amount_minor": min(credit["total_minor"], returned_invoice["paid_minor"]),
            "method": "cash",
            "reason": "Fictional UAT approved refund",
        },
        "uat-refund-001",
    )

with SessionLocal.begin() as db:
    for index, invoice in enumerate(invoices):
        occurred = datetime.now(UTC) - timedelta(days=28 - index)
        db.execute(
            update(Invoice)
            .where(Invoice.id == invoice["id"])
            .values(invoice_at=occurred)
        )
        db.execute(
            update(Payment)
            .where(Payment.invoice_id == invoice["id"])
            .values(paid_at=occurred)
        )

print(
    "Fictional UAT seed complete: customers=120 examinations=24 products=12 "
    "invoices=18 quotations=5 optical_orders=6 returns=1 refunds=1 employees=4"
)
