from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DbSession
from app.core.permissions import Permission, has_permission
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.staff import CredentialReset, StaffCreate, StaffResponse, StaffUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/staff", tags=["staff"])


def require_manage(user: User) -> None:
    if not has_permission(user, Permission.STAFF_MANAGE):
        raise HTTPException(403, "Employee management permission required")


def get_staff(db: DbSession, user: User, staff_id: UUID, *, lock: bool = False) -> User:
    query = select(User).where(User.id == staff_id, User.tenant_id == user.tenant_id)
    if lock:
        query = query.with_for_update()
    staff = db.scalar(query)
    if staff is None:
        raise HTTPException(404, "Employee not found")
    return staff


def active_owner_count(db: DbSession, tenant_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(User).where(
                User.tenant_id == tenant_id,
                User.role == UserRole.OWNER,
                User.is_active.is_(True),
            )
        )
        or 0
    )


@router.get("", response_model=list[StaffResponse])
def directory(user: CurrentUser, db: DbSession):
    require_manage(user)
    return list(
        db.scalars(
            select(User).where(User.tenant_id == user.tenant_id).order_by(User.full_name)
        ).all()
    )


@router.post("", response_model=StaffResponse, status_code=201)
def create_staff(data: StaffCreate, user: CurrentUser, db: DbSession):
    require_manage(user)
    item = User(
        tenant_id=user.tenant_id,
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.temporary_password),
        role=data.role,
        must_change_password=True,
    )
    db.add(item)
    try:
        db.flush()
        record_audit(
            db,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="staff.created",
            entity_type="user",
            entity_id=item.id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An employee with this email already exists") from exc
    return item


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: UUID, data: StaffUpdate, user: CurrentUser, db: DbSession
) -> User:
    require_manage(user)
    item = get_staff(db, user, staff_id, lock=True)
    values = data.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        raise HTTPException(422, "Employee fields cannot be null")
    if "full_name" in values:
        values["full_name"] = values["full_name"].strip()
    self_privilege_change = (
        values.get("role", user.role) != user.role or values.get("is_active") is False
    )
    if item.id == user.id and self_privilege_change:
        raise HTTPException(409, "You cannot change your own role or deactivate your account")
    removing_owner = item.role == UserRole.OWNER and item.is_active and (
        values.get("role", item.role) != UserRole.OWNER or values.get("is_active") is False
    )
    if removing_owner and active_owner_count(db, user.tenant_id) <= 1:
        raise HTTPException(409, "The last active owner cannot be removed")
    old_role = item.role
    for key, value in values.items():
        setattr(item, key, value)
    item.version += 1
    action = "staff.role_changed" if item.role != old_role else "staff.updated"
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action=action,
        entity_type="user",
        entity_id=item.id,
    )
    db.commit()
    return item


@router.post("/{staff_id}/reset-credentials", response_model=StaffResponse)
def reset_credentials(
    staff_id: UUID, data: CredentialReset, user: CurrentUser, db: DbSession
) -> User:
    require_manage(user)
    item = get_staff(db, user, staff_id, lock=True)
    if item.id == user.id:
        raise HTTPException(409, "Use Change password for your own account")
    item.password_hash = hash_password(data.temporary_password)
    item.must_change_password = True
    item.failed_login_attempts = 0
    item.locked_until = None
    item.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="staff.credentials_reset",
        entity_type="user",
        entity_id=item.id,
    )
    db.commit()
    return item
