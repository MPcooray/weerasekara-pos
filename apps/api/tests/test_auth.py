from datetime import UTC, datetime, timedelta

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


def test_repeated_failures_lock_account_and_success_resets_counter(client):
    with SessionLocal() as db:
        tenant = Tenant(name="Secure Optics", slug="secure-optics")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="secure@example.com",
            full_name="Secure Owner",
            password_hash=hash_password("SecurePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(user)
        db.commit()
        user_id = user.id
    credentials = {
        "tenant_slug": "secure-optics",
        "email": "secure@example.com",
        "password": "WrongPassword123!",
    }
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    credentials["password"] = "SecurePassword123!"
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 200
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


def test_logout_revokes_current_access_token(client):
    with SessionLocal() as db:
        tenant = Tenant(name="Logout Optics", slug="logout-optics")
        db.add(tenant)
        db.flush()
        db.add(
            User(
                tenant_id=tenant.id,
                email="logout@example.com",
                full_name="Logout Owner",
                password_hash=hash_password("SecurePassword123!"),
                role=UserRole.OWNER,
            )
        )
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "logout-optics",
            "email": "logout@example.com",
            "password": "SecurePassword123!",
        },
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_security_headers_prevent_api_caching(client):
    response = client.get("/api/v1/health")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
