from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session, *, tenant_id: UUID, actor_id: UUID, action: str, entity_type: str, entity_id: UUID
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )
