from uuid import UUID, uuid4

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.models.examination import Examination, ExaminationStatus
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def setup_customer_visit(client):
    customer = client.post(
        "/api/v1/customers",
        json={"full_name": "Optical Patient", "mobile_number": "0772345678"},
    ).json()["customer"]
    visit = client.post(
        f"/api/v1/customers/{customer['id']}/visits",
        json={"purpose": "Optical examination"},
    ).json()
    return customer, visit


def create_exam(client, customer_id, visit_id, **fields):
    return client.post(
        f"/api/v1/customers/{customer_id}/examinations",
        json={"visit_id": visit_id, **fields},
    )


def add_role_user(role: UserRole) -> tuple[User, str]:
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter_by(slug="weerasekara-optics").one()
        user = User(
            tenant_id=tenant.id,
            email=f"{role.value}-{uuid4().hex[:6]}@example.com",
            full_name=f"Test {role.value}",
            password_hash=hash_password("SafePassword123!"),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(
            user_id=str(user.id), tenant_id=str(user.tenant_id), role=user.role.value
        )
        return user, token


def test_draft_creation_and_incomplete_draft_saving(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    created = create_exam(authenticated_client, customer["id"], visit["id"])
    assert created.status_code == 201
    exam = created.json()
    assert exam["status"] == "draft"
    updated = authenticated_client.patch(
        f"/api/v1/examinations/{exam['id']}",
        json={"expected_version": exam["version"], "notes": "Incomplete draft"},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Incomplete draft"


def test_validation_and_finalization(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    invalid = create_exam(
        authenticated_client,
        customer["id"],
        visit["id"],
        od_sphere="1.13",
        od_axis=181,
    )
    assert invalid.status_code == 422
    exam = create_exam(
        authenticated_client,
        customer["id"],
        visit["id"],
        prescription_type="distance",
        od_sphere="-1.25",
        od_cylinder="-0.50",
        od_axis=90,
        pd_binocular="62.00",
    ).json()
    finalized = authenticated_client.post(
        f"/api/v1/examinations/{exam['id']}/finalize",
        json={"expected_version": exam["version"]},
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "finalized"
    immutable = authenticated_client.patch(
        f"/api/v1/examinations/{exam['id']}",
        json={"expected_version": finalized.json()["version"], "od_sphere": "-2.00"},
    )
    assert immutable.status_code == 409


def test_revision_preserves_finalized_history(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    exam = create_exam(
        authenticated_client,
        customer["id"],
        visit["id"],
        prescription_type="distance",
        od_sphere="-1.00",
    ).json()
    finalized = authenticated_client.post(
        f"/api/v1/examinations/{exam['id']}/finalize",
        json={"expected_version": exam["version"]},
    ).json()
    revision = authenticated_client.post(f"/api/v1/examinations/{exam['id']}/revisions").json()
    assert revision["status"] == "draft"
    assert revision["supersedes_id"] == exam["id"]
    assert revision["revision_number"] == 2
    with SessionLocal() as db:
        original = db.get(Examination, UUID(exam["id"]))
        assert original.status == ExaminationStatus.FINALIZED
        assert str(original.od_sphere) == "-1.00"
    assert finalized["status"] == "finalized"


def test_concurrent_update_is_rejected(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    exam = create_exam(authenticated_client, customer["id"], visit["id"]).json()
    first = authenticated_client.patch(
        f"/api/v1/examinations/{exam['id']}",
        json={"expected_version": exam["version"], "od_sphere": "-1.00"},
    )
    stale = authenticated_client.patch(
        f"/api/v1/examinations/{exam['id']}",
        json={"expected_version": exam["version"], "od_sphere": "-2.00"},
    )
    assert first.status_code == 200
    assert stale.status_code == 409


def test_comparison_reports_numerical_change(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    first = create_exam(
        authenticated_client,
        customer["id"],
        visit["id"],
        prescription_type="distance",
        od_sphere="-1.00",
    ).json()
    second = create_exam(
        authenticated_client,
        customer["id"],
        visit["id"],
        prescription_type="distance",
        od_sphere="-1.50",
    ).json()
    comparison = authenticated_client.get(
        f"/api/v1/examinations/compare/{first['id']}/{second['id']}"
    )
    assert comparison.status_code == 200
    assert comparison.json()["changes"][0]["difference"] == "-0.50"
    assert "not clinical diagnoses" in comparison.json()["notice"]


def test_role_permissions_and_cashier_finalized_only(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    draft = create_exam(authenticated_client, customer["id"], visit["id"]).json()
    ready = create_exam(
        authenticated_client,
        customer["id"],
        visit["id"],
        prescription_type="distance",
        od_sphere="-0.50",
    ).json()
    finalized = authenticated_client.post(
        f"/api/v1/examinations/{ready['id']}/finalize",
        json={"expected_version": ready["version"]},
    ).json()
    manager, manager_token = add_role_user(UserRole.MANAGER)
    cashier, cashier_token = add_role_user(UserRole.CASHIER)
    manager_headers = {"Authorization": f"Bearer {manager_token}"}
    cashier_headers = {"Authorization": f"Bearer {cashier_token}"}
    assert (
        authenticated_client.get(
            f"/api/v1/examinations/{draft['id']}", headers=manager_headers
        ).status_code
        == 200
    )
    assert (
        authenticated_client.patch(
            f"/api/v1/examinations/{draft['id']}",
            headers=manager_headers,
            json={"expected_version": draft["version"], "notes": "Not allowed"},
        ).status_code
        == 403
    )
    assert (
        authenticated_client.get(
            f"/api/v1/examinations/{draft['id']}", headers=cashier_headers
        ).status_code
        == 404
    )
    assert (
        authenticated_client.get(
            f"/api/v1/examinations/{finalized['id']}", headers=cashier_headers
        ).status_code
        == 200
    )
    assert manager.role == UserRole.MANAGER and cashier.role == UserRole.CASHIER


def test_tenant_isolation_for_examinations(authenticated_client):
    customer, visit = setup_customer_visit(authenticated_client)
    exam = create_exam(authenticated_client, customer["id"], visit["id"]).json()
    with SessionLocal() as db:
        tenant = Tenant(name="Other", slug=f"other-{uuid4().hex[:6]}")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email="other@example.com",
            full_name="Other Owner",
            password_hash=hash_password("SafePassword123!"),
            role=UserRole.OWNER,
        )
        db.add(user)
        db.commit()
        token = create_access_token(user_id=str(user.id), tenant_id=str(tenant.id), role="owner")
    assert (
        authenticated_client.get(
            f"/api/v1/examinations/{exam['id']}",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 404
    )
