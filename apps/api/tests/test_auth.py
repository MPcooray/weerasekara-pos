from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def test_login_and_current_user_are_tenant_scoped(client):
    with SessionLocal() as db:
        tenant = Tenant(name="Weerasekara Optics", slug="weerasekara-optics")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email="owner@example.com",
                full_name="Test Owner",
                password_hash=hash_password("SafePassword123!"),
                role=UserRole.OWNER,
            )
        )
        db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "weerasekara-optics",
            "email": "owner@example.com",
            "password": "SafePassword123!",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["role"] == "owner"
    assert "password_hash" not in profile.json()


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "missing-tenant",
            "email": "owner@example.com",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401
