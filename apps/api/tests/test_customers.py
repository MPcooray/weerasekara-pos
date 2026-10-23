from datetime import date
from uuid import UUID

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def customer_payload(name="Nimal Perera", mobile="0771234567"):
    return {"full_name": name, "mobile_number": mobile, "email": "nimal@example.com"}


def test_register_customer_and_audit(authenticated_client):
    response = authenticated_client.post("/api/v1/customers", json=customer_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["customer"]["customer_number"].startswith("CUS-")
    assert body["customer"]["mobile_number"] == "+94771234567"
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="customer.created").count() == 1


def test_duplicate_registration_warns_without_merging(authenticated_client):
    first = authenticated_client.post("/api/v1/customers", json=customer_payload())
    second = authenticated_client.post("/api/v1/customers", json=customer_payload("Nimal P."))
    assert first.status_code == second.status_code == 201
    assert second.json()["duplicate_warnings"]
    assert first.json()["customer"]["id"] != second.json()["customer"]["id"]


def test_search_and_pagination(authenticated_client):
    for index in range(14):
        response = authenticated_client.post(
            "/api/v1/customers", json=customer_payload(f"Customer {index}", f"+1415555{index:04d}")
        )
        assert response.status_code == 201
    page = authenticated_client.get("/api/v1/customers?page=2&page_size=5").json()
    assert page["total"] == 14
    assert page["pages"] == 3
    assert len(page["items"]) == 5
    result = authenticated_client.get("/api/v1/customers?search=Customer%2013").json()
    assert result["total"] == 1


def test_update_customer(authenticated_client):
    customer = authenticated_client.post("/api/v1/customers", json=customer_payload()).json()[
        "customer"
    ]
    response = authenticated_client.patch(
        f"/api/v1/customers/{customer['id']}",
        json={"full_name": "Nimal Silva", "notes": "Prefers SMS"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Nimal Silva"


def test_create_visit_and_preserve_history(authenticated_client):
    customer = authenticated_client.post("/api/v1/customers", json=customer_payload()).json()[
        "customer"
    ]
    response = authenticated_client.post(
        f"/api/v1/customers/{customer['id']}/visits",
        json={"purpose": "Eye examination", "status": "in_progress"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "in_progress"
    profile = authenticated_client.get(f"/api/v1/customers/{customer['id']}").json()
    assert len(profile["visits"]) == 1


def test_tenant_isolation_returns_not_found(authenticated_client):
    with SessionLocal() as db:
        other_tenant = Tenant(name="Other Optics", slug="other-optics")
        db.add(other_tenant)
        db.flush()
        other_user = User(
            tenant_id=other_tenant.id,
            email="owner@other.test",
            full_name="Other Owner",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(other_user)
        db.flush()
        customer = Customer(
            tenant_id=other_tenant.id,
            customer_number="CUS-OTHER001",
            full_name="Private Customer",
            mobile_number="0712345678",
            created_by_id=other_user.id,
        )
        db.add(customer)
        db.commit()
        customer_id = customer.id
    assert authenticated_client.get(f"/api/v1/customers/{customer_id}").status_code == 404
    assert (
        authenticated_client.patch(
            f"/api/v1/customers/{customer_id}", json={"full_name": "Stolen"}
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/v1/customers/{customer_id}/visits", json={"purpose": "Invalid"}
        ).status_code
        == 404
    )


def test_unauthorized_access(client):
    assert client.get("/api/v1/customers").status_code == 401
    assert client.post("/api/v1/customers", json=customer_payload()).status_code == 401


def test_validation_rejects_invalid_phone_and_future_birth_date(authenticated_client):
    invalid_phone = authenticated_client.post(
        "/api/v1/customers", json=customer_payload(mobile="123")
    )
    future_birth = authenticated_client.post(
        "/api/v1/customers",
        json={
            **customer_payload(),
            "date_of_birth": str(date.today().replace(year=date.today().year + 1)),
        },
    )
    assert invalid_phone.status_code == 422
    assert future_birth.status_code == 422


def test_archive_is_soft_delete(authenticated_client):
    customer = authenticated_client.post("/api/v1/customers", json=customer_payload()).json()[
        "customer"
    ]
    assert authenticated_client.delete(f"/api/v1/customers/{customer['id']}").status_code == 204
    assert authenticated_client.get(f"/api/v1/customers/{customer['id']}").status_code == 404
    with SessionLocal() as db:
        assert db.get(Customer, UUID(customer["id"])).is_archived is True
