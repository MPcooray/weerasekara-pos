from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.tenant import Tenant
from app.models.user import User, UserRole

PASSWORD = "SafePassword123!"


def login(client, slug: str, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def add_user(role: UserRole, email: str, *, tenant_slug: str = "weerasekara-optics") -> User:
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=f"Test {role.value.title()}",
            password_hash=hash_password(PASSWORD),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def test_permissions_and_sensitive_inventory_fields(authenticated_client):
    product = authenticated_client.post(
        "/api/v1/products",
        json={
            "name": "Restricted Cost Frame",
            "sku": "RBAC-001",
            "category": "spectacle_frame",
            "cost_price_minor": 100_000,
            "selling_price_minor": 200_000,
            "track_stock": True,
        },
    ).json()
    add_user(UserRole.CASHIER, "cashier-rbac@example.com")
    cashier = login(authenticated_client, "weerasekara-optics", "cashier-rbac@example.com")
    profile = authenticated_client.get("/api/v1/auth/me", headers=cashier).json()
    assert "pos.checkout" in profile["permissions"]
    assert "reports.view" not in profile["permissions"]
    assert authenticated_client.get("/api/v1/dashboard", headers=cashier).status_code == 403
    assert authenticated_client.get("/api/v1/suppliers", headers=cashier).status_code == 403
    assert (
        authenticated_client.get(
            f"/api/v1/products/{product['id']}/movements", headers=cashier
        ).status_code
        == 403
    )
    restricted_product = authenticated_client.get(
        f"/api/v1/products/{product['id']}", headers=cashier
    ).json()
    assert restricted_product["cost_price_minor"] is None
    assert restricted_product["supplier_id"] is None
    summary = authenticated_client.get("/api/v1/inventory/summary", headers=cashier).json()
    assert summary["valuation_minor"] is None


def test_optometrist_cannot_access_financial_or_supplier_data(authenticated_client):
    add_user(UserRole.OPTOMETRIST, "clinical-rbac@example.com")
    headers = login(authenticated_client, "weerasekara-optics", "clinical-rbac@example.com")
    assert authenticated_client.get("/api/v1/invoices", headers=headers).status_code == 403
    assert authenticated_client.get("/api/v1/quotations", headers=headers).status_code == 403
    assert authenticated_client.get("/api/v1/suppliers", headers=headers).status_code == 403
    assert authenticated_client.get("/api/v1/dashboard", headers=headers).status_code == 403


def test_owner_employee_lifecycle_and_forced_password_change(authenticated_client):
    created = authenticated_client.post(
        "/api/v1/staff",
        json={
            "email": "new.cashier@example.com",
            "full_name": "New Cashier",
            "role": "cashier",
            "temporary_password": "Temporary123!",
        },
    )
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True
    employee_id = created.json()["id"]
    temporary = login(
        authenticated_client,
        "weerasekara-optics",
        "new.cashier@example.com",
        "Temporary123!",
    )
    assert authenticated_client.get("/api/v1/customers", headers=temporary).status_code == 403
    changed = authenticated_client.post(
        "/api/v1/auth/change-password",
        headers=temporary,
        json={"current_password": "Temporary123!", "new_password": "Permanent456!"},
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert authenticated_client.get("/api/v1/customers", headers=temporary).status_code == 200

    disabled = authenticated_client.patch(
        f"/api/v1/staff/{employee_id}", json={"is_active": False}
    )
    assert disabled.status_code == 200
    assert authenticated_client.get("/api/v1/auth/me", headers=temporary).status_code == 401
    with SessionLocal() as db:
        actions = set(db.scalars(select(AuditLog.action)).all())
        assert {"staff.created", "staff.updated", "staff.password_changed"} <= actions


def test_staff_management_guards_and_tenant_isolation(authenticated_client):
    manager = add_user(UserRole.MANAGER, "manager-rbac@example.com")
    manager_headers = login(authenticated_client, "weerasekara-optics", manager.email)
    assert authenticated_client.get("/api/v1/staff", headers=manager_headers).status_code == 403

    owner_profile = authenticated_client.get("/api/v1/auth/me").json()
    assert (
        authenticated_client.patch(
            f"/api/v1/staff/{owner_profile['id']}", json={"role": "manager"}
        ).status_code
        == 409
    )
    with SessionLocal() as db:
        other = Tenant(name="Other Optics", slug="other-rbac")
        db.add(other)
        db.flush()
        outsider = User(
            tenant_id=other.id,
            email="other@example.com",
            full_name="Other Employee",
            password_hash=hash_password(PASSWORD),
            role=UserRole.CASHIER,
        )
        db.add(outsider)
        db.commit()
        outsider_id = outsider.id
    assert (
        authenticated_client.patch(
            f"/api/v1/staff/{outsider_id}", json={"is_active": False}
        ).status_code
        == 404
    )


def test_credential_reset_forces_change_and_is_audited(authenticated_client):
    employee = add_user(UserRole.CASHIER, "reset-rbac@example.com")
    response = authenticated_client.post(
        f"/api/v1/staff/{employee.id}/reset-credentials",
        json={"temporary_password": "Replacement789!"},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True
    with SessionLocal() as db:
        assert db.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == employee.id,
                AuditLog.action == "staff.credentials_reset",
            )
        )
