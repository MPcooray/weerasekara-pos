from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from app.api.dependencies import CurrentUser, DbSession
from app.models.customer import Customer
from app.models.examination import Examination, ExaminationStatus
from app.models.user import EXAMINATION_FULL_READ_ROLES, EXAMINATION_WRITE_ROLES, User, UserRole
from app.models.visit import Visit
from app.schemas.examination import (
    MEASUREMENT_FIELDS,
    ComparisonChange,
    ExaminationComparison,
    ExaminationCreate,
    ExaminationFields,
    ExaminationFinalize,
    ExaminationResponse,
    ExaminationUpdate,
)
from app.services.audit import record_audit

router = APIRouter(tags=["examinations"])


def require_write(user: User) -> None:
    if user.role not in EXAMINATION_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Clinical edit permission required"
        )


def examination_query(user: User):
    query = select(Examination).where(Examination.tenant_id == user.tenant_id)
    if user.role == UserRole.CASHIER:
        query = query.where(Examination.status == ExaminationStatus.FINALIZED)
    elif user.role not in EXAMINATION_FULL_READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Clinical record access denied"
        )
    return query


def get_examination(db: DbSession, user: User, examination_id: UUID) -> Examination:
    examination = db.scalar(
        examination_query(user)
        .where(Examination.id == examination_id)
        .options(joinedload(Examination.customer), joinedload(Examination.examiner))
    )
    if examination is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found")
    return examination


def to_response(examination: Examination) -> ExaminationResponse:
    data = {
        column.name: getattr(examination, column.name) for column in Examination.__table__.columns
    }
    data["customer_name"] = examination.customer.full_name
    data["examiner_name"] = examination.examiner.full_name
    return ExaminationResponse.model_validate(data)


def validate_finalizable(examination: Examination) -> None:
    if examination.prescription_type is None:
        raise HTTPException(
            status_code=422, detail="Prescription type is required before finalization"
        )
    if not any(getattr(examination, field) is not None for field in MEASUREMENT_FIELDS):
        raise HTTPException(
            status_code=422, detail="At least one measurement is required before finalization"
        )


@router.get("/customers/{customer_id}/examinations", response_model=list[ExaminationResponse])
def list_examinations(
    customer_id: UUID,
    user: CurrentUser,
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[ExaminationResponse]:
    conditions = [Examination.customer_id == customer_id]
    if date_from:
        conditions.append(
            Examination.examined_at >= datetime.combine(date_from, datetime.min.time(), UTC)
        )
    if date_to:
        conditions.append(
            Examination.examined_at <= datetime.combine(date_to, datetime.max.time(), UTC)
        )
    records = db.scalars(
        examination_query(user)
        .where(*conditions)
        .options(joinedload(Examination.customer), joinedload(Examination.examiner))
        .order_by(Examination.examined_at.desc())
    ).all()
    return [to_response(item) for item in records]


@router.post(
    "/customers/{customer_id}/examinations", response_model=ExaminationResponse, status_code=201
)
def create_examination(
    customer_id: UUID, data: ExaminationCreate, user: CurrentUser, db: DbSession
) -> ExaminationResponse:
    require_write(user)
    customer = db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
    )
    visit = db.scalar(
        select(Visit).where(
            Visit.id == data.visit_id,
            Visit.customer_id == customer_id,
            Visit.tenant_id == user.tenant_id,
        )
    )
    if customer is None or visit is None:
        raise HTTPException(status_code=404, detail="Customer or visit not found")
    examination = Examination(
        **data.model_dump(),
        tenant_id=user.tenant_id,
        customer_id=customer_id,
        examiner_id=user.id,
        examination_number=f"EXM-{uuid4().hex[:8].upper()}",
        status=ExaminationStatus.DRAFT,
    )
    db.add(examination)
    db.flush()
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="examination.created",
        entity_type="examination",
        entity_id=examination.id,
    )
    db.commit()
    return to_response(get_examination(db, user, examination.id))


@router.get("/examinations/{examination_id}", response_model=ExaminationResponse)
def examination_detail(
    examination_id: UUID, user: CurrentUser, db: DbSession
) -> ExaminationResponse:
    examination = get_examination(db, user, examination_id)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="examination.viewed",
        entity_type="examination",
        entity_id=examination.id,
    )
    db.commit()
    return to_response(examination)


@router.patch("/examinations/{examination_id}", response_model=ExaminationResponse)
def update_examination(
    examination_id: UUID, data: ExaminationUpdate, user: CurrentUser, db: DbSession
) -> ExaminationResponse:
    require_write(user)
    examination = get_examination(db, user, examination_id)
    if examination.status == ExaminationStatus.FINALIZED:
        raise HTTPException(
            status_code=409, detail="Finalized examinations are immutable; create a revision"
        )
    values = data.model_dump(exclude_unset=True, exclude={"expected_version"})
    values["version"] = data.expected_version + 1
    result = db.execute(
        update(Examination)
        .where(
            Examination.id == examination_id,
            Examination.tenant_id == user.tenant_id,
            Examination.version == data.expected_version,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This examination was changed by another user; reload before saving",
        )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="examination.updated",
        entity_type="examination",
        entity_id=examination_id,
    )
    db.commit()
    return to_response(get_examination(db, user, examination_id))


@router.post("/examinations/{examination_id}/finalize", response_model=ExaminationResponse)
def finalize_examination(
    examination_id: UUID, data: ExaminationFinalize, user: CurrentUser, db: DbSession
) -> ExaminationResponse:
    require_write(user)
    examination = get_examination(db, user, examination_id)
    if examination.status == ExaminationStatus.FINALIZED:
        return to_response(examination)
    validate_finalizable(examination)
    result = db.execute(
        update(Examination)
        .where(
            Examination.id == examination_id,
            Examination.tenant_id == user.tenant_id,
            Examination.version == data.expected_version,
            Examination.status == ExaminationStatus.DRAFT,
        )
        .values(
            status=ExaminationStatus.FINALIZED,
            finalized_at=datetime.now(UTC),
            version=data.expected_version + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This examination was changed by another user; reload before finalizing",
        )
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="examination.finalized",
        entity_type="examination",
        entity_id=examination_id,
    )
    db.commit()
    return to_response(get_examination(db, user, examination_id))


@router.post(
    "/examinations/{examination_id}/revisions", response_model=ExaminationResponse, status_code=201
)
def create_revision(examination_id: UUID, user: CurrentUser, db: DbSession) -> ExaminationResponse:
    require_write(user)
    source = get_examination(db, user, examination_id)
    if source.status != ExaminationStatus.FINALIZED:
        raise HTTPException(
            status_code=409, detail="Only finalized examinations require a revision"
        )
    values = {field: getattr(source, field) for field in ExaminationFields.model_fields}
    revision = Examination(
        **values,
        tenant_id=user.tenant_id,
        customer_id=source.customer_id,
        visit_id=source.visit_id,
        examiner_id=user.id,
        examination_number=f"EXM-{uuid4().hex[:8].upper()}",
        examined_at=datetime.now(UTC),
        status=ExaminationStatus.DRAFT,
        supersedes_id=source.id,
        revision_number=source.revision_number + 1,
    )
    db.add(revision)
    db.flush()
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="examination.revision_created",
        entity_type="examination",
        entity_id=revision.id,
    )
    db.commit()
    return to_response(get_examination(db, user, revision.id))


@router.get("/examinations/compare/{earlier_id}/{later_id}", response_model=ExaminationComparison)
def compare_examinations(
    earlier_id: UUID, later_id: UUID, user: CurrentUser, db: DbSession
) -> ExaminationComparison:
    earlier = get_examination(db, user, earlier_id)
    later = get_examination(db, user, later_id)
    if earlier.customer_id != later.customer_id:
        raise HTTPException(
            status_code=422, detail="Only examinations for the same customer can be compared"
        )
    changes = []
    for field in (
        "od_sphere",
        "od_cylinder",
        "od_axis",
        "od_add",
        "os_sphere",
        "os_cylinder",
        "os_axis",
        "os_add",
    ):
        before, after = getattr(earlier, field), getattr(later, field)
        if before != after:
            difference = after - before if before is not None and after is not None else None
            changes.append(
                ComparisonChange(field=field, earlier=before, later=after, difference=difference)
            )
    return ExaminationComparison(
        earlier=to_response(earlier), later=to_response(later), changes=changes
    )
