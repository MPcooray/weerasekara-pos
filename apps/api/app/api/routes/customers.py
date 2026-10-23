import math
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.dependencies import CurrentUser, DbSession
from app.models.customer import Customer
from app.models.user import CUSTOMER_ARCHIVE_ROLES, CUSTOMER_WRITE_ROLES, User
from app.models.visit import Visit
from app.schemas.customer import (
    CustomerCreate,
    CustomerCreateResponse,
    CustomerDetail,
    CustomerPage,
    CustomerResponse,
    CustomerUpdate,
    VisitCreate,
    VisitResponse,
    VisitUpdate,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/customers", tags=["customers"])


def require_write(user: User) -> None:
    if user.role not in CUSTOMER_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


def get_customer(db: DbSession, user: User, customer_id: UUID, *, visits: bool = False) -> Customer:
    query = select(Customer).where(
        Customer.id == customer_id,
        Customer.tenant_id == user.tenant_id,
        Customer.is_archived.is_(False),
    )
    if visits:
        query = query.options(selectinload(Customer.visits))
    customer = db.scalar(query)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def duplicate_warnings(
    db: DbSession, user: User, data: CustomerCreate, exclude_id: UUID | None = None
) -> list[str]:
    filters = [Customer.mobile_number == data.mobile_number]
    if data.email:
        filters.append(func.lower(Customer.email) == data.email.lower())
    query = select(Customer).where(Customer.tenant_id == user.tenant_id, or_(*filters))
    if exclude_id:
        query = query.where(Customer.id != exclude_id)
    matches = db.scalars(query.limit(3)).all()
    return [f"Possible duplicate: {item.customer_number} — {item.full_name}" for item in matches]


@router.get("", response_model=CustomerPage)
def list_customers(
    user: CurrentUser,
    db: DbSession,
    search: str = Query(default="", max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> CustomerPage:
    conditions = [Customer.tenant_id == user.tenant_id, Customer.is_archived.is_(False)]
    if search.strip():
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                Customer.full_name.ilike(term),
                Customer.mobile_number.ilike(term),
                Customer.customer_number.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(Customer).where(*conditions)) or 0
    customers = db.scalars(
        select(Customer)
        .where(*conditions)
        .order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CustomerPage(
        items=[CustomerResponse.model_validate(item) for item in customers],
        page=page,
        page_size=page_size,
        total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post("", response_model=CustomerCreateResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    data: CustomerCreate, user: CurrentUser, db: DbSession
) -> CustomerCreateResponse:
    require_write(user)
    warnings = duplicate_warnings(db, user, data)
    customer = Customer(
        **data.model_dump(),
        tenant_id=user.tenant_id,
        customer_number=f"CUS-{uuid4().hex[:8].upper()}",
        created_by_id=user.id,
    )
    try:
        db.add(customer)
        db.flush()
        record_audit(
            db,
            tenant_id=user.tenant_id,
            actor_id=user.id,
            action="customer.created",
            entity_type="customer",
            entity_id=customer.id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer identifier conflict; please retry",
        ) from exc
    db.refresh(customer)
    return CustomerCreateResponse(
        customer=CustomerResponse.model_validate(customer), duplicate_warnings=warnings
    )


@router.get("/{customer_id}", response_model=CustomerDetail)
def customer_detail(customer_id: UUID, user: CurrentUser, db: DbSession) -> Customer:
    return get_customer(db, user, customer_id, visits=True)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: UUID, data: CustomerUpdate, user: CurrentUser, db: DbSession
) -> Customer:
    require_write(user)
    customer = get_customer(db, user, customer_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    customer.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="customer.updated",
        entity_type="customer",
        entity_id=customer.id,
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_customer(customer_id: UUID, user: CurrentUser, db: DbSession) -> None:
    if user.role not in CUSTOMER_ARCHIVE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    customer = get_customer(db, user, customer_id)
    customer.is_archived = True
    customer.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="customer.archived",
        entity_type="customer",
        entity_id=customer.id,
    )
    db.commit()


@router.get("/{customer_id}/visits", response_model=list[VisitResponse])
def list_visits(customer_id: UUID, user: CurrentUser, db: DbSession) -> list[Visit]:
    get_customer(db, user, customer_id)
    return list(
        db.scalars(
            select(Visit)
            .where(Visit.customer_id == customer_id, Visit.tenant_id == user.tenant_id)
            .order_by(Visit.visit_at.desc())
        ).all()
    )


@router.post(
    "/{customer_id}/visits", response_model=VisitResponse, status_code=status.HTTP_201_CREATED
)
def create_visit(customer_id: UUID, data: VisitCreate, user: CurrentUser, db: DbSession) -> Visit:
    require_write(user)
    get_customer(db, user, customer_id)
    if data.assigned_staff_id:
        staff = db.scalar(
            select(User).where(
                User.id == data.assigned_staff_id,
                User.tenant_id == user.tenant_id,
                User.is_active.is_(True),
            )
        )
        if staff is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assigned staff member is invalid",
            )
    visit = Visit(**data.model_dump(), tenant_id=user.tenant_id, customer_id=customer_id)
    db.add(visit)
    db.flush()
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="visit.created",
        entity_type="visit",
        entity_id=visit.id,
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.patch("/{customer_id}/visits/{visit_id}", response_model=VisitResponse)
def update_visit(
    customer_id: UUID, visit_id: UUID, data: VisitUpdate, user: CurrentUser, db: DbSession
) -> Visit:
    require_write(user)
    get_customer(db, user, customer_id)
    visit = db.scalar(
        select(Visit).where(
            Visit.id == visit_id,
            Visit.customer_id == customer_id,
            Visit.tenant_id == user.tenant_id,
        )
    )
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(visit, key, value)
    visit.version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="visit.updated",
        entity_type="visit",
        entity_id=visit.id,
    )
    db.commit()
    db.refresh(visit)
    return visit
