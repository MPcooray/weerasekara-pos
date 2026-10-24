import csv
import io
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.api.dependencies import CurrentUser, DbSession
from app.models.tenant import Tenant
from app.models.user import BRANDING_WRITE_ROLES, REPORT_READ_ROLES
from app.schemas.reporting import (
    BrandingResponse,
    BrandingUpdate,
    DashboardResponse,
    FinancialReport,
)
from app.services.audit import record_audit
from app.services.reporting import dashboard, financial_report

router = APIRouter(tags=["reporting"])


def branding_response(tenant: Tenant) -> BrandingResponse:
    return BrandingResponse(
        business_display_name=tenant.business_display_name or tenant.name,
        business_address=tenant.business_address,
        business_contact=tenant.business_contact,
        logo_url=tenant.logo_url,
        invoice_footer=tenant.invoice_footer,
        receipt_footer=tenant.receipt_footer,
        business_registration=tenant.business_registration,
        tax_registration=tenant.tax_registration,
        default_currency=tenant.default_currency,
    )


def validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise HTTPException(422, "date_to must be on or after date_from")
    if date_to - date_from > timedelta(days=366):
        raise HTTPException(422, "Reporting range cannot exceed 366 days")


@router.get("/tenant/branding", response_model=BrandingResponse)
def get_branding(user: CurrentUser, db: DbSession):
    return branding_response(db.get(Tenant, user.tenant_id))


@router.patch("/tenant/branding", response_model=BrandingResponse)
def update_branding(data: BrandingUpdate, user: CurrentUser, db: DbSession):
    if user.role not in BRANDING_WRITE_ROLES:
        raise HTTPException(403, "Branding permission required")
    tenant = db.get(Tenant, user.tenant_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(tenant, key, str(value) if key == "logo_url" and value else value)
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="tenant.branding_updated",
        entity_type="tenant",
        entity_id=tenant.id,
    )
    db.commit()
    db.refresh(tenant)
    return branding_response(tenant)


@router.get("/reports/financial", response_model=FinancialReport)
def report(
    user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
):
    if user.role not in REPORT_READ_ROLES:
        raise HTTPException(403, "Financial reporting permission required")
    validate_range(date_from, date_to)
    return financial_report(db, user.tenant_id, date_from, date_to)


@router.get("/reports/financial.csv")
def report_csv(
    user: CurrentUser,
    db: DbSession,
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
):
    if user.role not in REPORT_READ_ROLES:
        raise HTTPException(403, "Financial reporting permission required")
    validate_range(date_from, date_to)
    data = financial_report(db, user.tenant_id, date_from, date_to)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "amount_minor", "quantity"])
    for name, value in (
        ("invoiced_sales", data.invoiced_sales_minor),
        ("payments_received", data.payments_received_minor),
        ("refunds", data.refunds_minor),
        ("outstanding", data.outstanding_minor),
        ("credit_notes", data.credit_notes_minor),
        ("discounts", data.discounts_minor),
        ("tax", data.tax_minor),
    ):
        writer.writerow([name, value, ""])
    for item in data.payment_methods:
        writer.writerow([f"payment:{item.name}", item.amount_minor, item.quantity])
    for item in data.top_products:
        writer.writerow([f"product:{item.name}", item.amount_minor, item.quantity])
    for item in data.sales_by_staff:
        writer.writerow([f"staff:{item.name}", item.amount_minor, item.quantity])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="financial-{date_from}-{date_to}.csv"'
        },
    )


@router.get("/dashboard", response_model=DashboardResponse)
def owner_dashboard(user: CurrentUser, db: DbSession):
    if user.role not in REPORT_READ_ROLES:
        raise HTTPException(403, "Dashboard permission required")
    return dashboard(db, user.tenant_id)
