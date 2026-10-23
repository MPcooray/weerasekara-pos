from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def bootstrap_initial_tenant(db: Session, settings: Settings) -> None:
    if settings.app_env == "production" and not settings.allow_initial_admin_bootstrap:
        return
    if not settings.initial_admin_password:
        return
    if db.scalar(select(Tenant).where(Tenant.slug == settings.initial_tenant_slug)):
        return
    tenant = Tenant(name=settings.initial_tenant_name, slug=settings.initial_tenant_slug)
    db.add(tenant)
    db.flush()
    db.add(
        User(
            tenant_id=tenant.id,
            email=settings.initial_admin_email.lower(),
            full_name="Store Owner",
            password_hash=hash_password(settings.initial_admin_password),
            role=UserRole.OWNER,
        )
    )
    db.commit()
