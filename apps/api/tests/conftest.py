import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "")

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole


@pytest.fixture
def client():
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


@pytest.fixture
def authenticated_client(client):
    with SessionLocal() as db:
        tenant = Tenant(name="Weerasekara Optics", slug="weerasekara-optics")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="staff@example.com",
            full_name="Staff User",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(user)
        db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": "weerasekara-optics",
            "email": "staff@example.com",
            "password": "SafePassword123!",
        },
    )
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return client
