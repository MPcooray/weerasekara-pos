"""Interactively provision the first owner without command-line password exposure."""

import argparse
import getpass

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.models.tenant import Tenant
from app.models.user import User, UserRole


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision the first tenant owner")
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--owner-name", required=True)
    parser.add_argument("--owner-email", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    password = getpass.getpass("Initial owner password (12+ characters): ")
    confirmation = getpass.getpass("Confirm initial owner password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")

    with SessionLocal.begin() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.slug == args.tenant_slug))
        if tenant is None:
            tenant = Tenant(name=args.tenant_name.strip(), slug=args.tenant_slug.strip())
            db.add(tenant)
            db.flush()
        employee_count = db.scalar(
            select(func.count()).select_from(User).where(User.tenant_id == tenant.id)
        )
        if employee_count:
            raise SystemExit("Refusing: this tenant already has employee accounts")
        owner = User(
            tenant_id=tenant.id,
            email=args.owner_email.lower().strip(),
            full_name=args.owner_name.strip(),
            password_hash=hash_password(password),
            role=UserRole.OWNER,
            must_change_password=True,
        )
        db.add(owner)
        db.flush()
        db.add(
            AuditLog(
                tenant_id=tenant.id,
                actor_id=owner.id,
                action="staff.initial_owner_provisioned",
                entity_type="user",
                entity_id=owner.id,
            )
        )
    print("Initial owner created; password replacement is required at first login")


if __name__ == "__main__":
    main()
