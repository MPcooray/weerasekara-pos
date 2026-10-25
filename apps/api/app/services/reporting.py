from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.time import COLOMBO, colombo_today
from app.models.finance import (
    CreditNote,
    CreditNoteStatus,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
    Quotation,
    QuotationStatus,
    Refund,
)
from app.models.inventory import InventoryBalance
from app.models.product import Product
from app.models.user import User
from app.schemas.reporting import (
    DashboardResponse,
    FinancialReport,
    NamedAmount,
    RecentTransaction,
    TrendPoint,
)

ACTIVE_INVOICES = [InvoiceStatus.FINALIZED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.PAID]


def utc_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, COLOMBO).astimezone(UTC)
    end = datetime.combine(date_to + timedelta(days=1), time.min, COLOMBO).astimezone(UTC)
    return start, end


def _amount(db: Session, statement) -> int:
    return int(db.scalar(statement) or 0)


def financial_report(db: Session, tenant_id, date_from: date, date_to: date) -> FinancialReport:
    start, end = utc_bounds(date_from, date_to)
    invoice_filter = (
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(ACTIVE_INVOICES),
        Invoice.invoice_at >= start,
        Invoice.invoice_at < end,
    )
    payment_filter = (
        Payment.tenant_id == tenant_id,
        Payment.reversed_by_id.is_(None),
        Payment.paid_at >= start,
        Payment.paid_at < end,
    )
    refund_filter = (
        Refund.tenant_id == tenant_id,
        Refund.refunded_at >= start,
        Refund.refunded_at < end,
    )
    credit_filter = (
        CreditNote.tenant_id == tenant_id,
        CreditNote.status == CreditNoteStatus.ISSUED,
        CreditNote.issued_at >= start,
        CreditNote.issued_at < end,
    )
    invoices = db.scalars(select(Invoice).where(*invoice_filter)).all()
    payments = db.scalars(select(Payment).where(*payment_filter)).all()
    refunds = db.scalars(select(Refund).where(*refund_filter)).all()
    credits = db.scalars(select(CreditNote).where(*credit_filter)).all()

    method_totals: dict[str, int] = defaultdict(int)
    for payment in payments:
        method_totals[payment.method.value] += payment.amount_minor

    product_rows = db.execute(
        select(
            InvoiceLine.product_name,
            func.sum(InvoiceLine.line_total_minor),
            func.sum(InvoiceLine.quantity),
        )
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(*invoice_filter)
        .group_by(InvoiceLine.product_name)
        .order_by(func.sum(InvoiceLine.quantity).desc())
        .limit(10)
    ).all()
    staff_rows = db.execute(
        select(User.full_name, func.sum(Invoice.total_minor), func.count(Invoice.id))
        .join(User, User.id == Invoice.actor_id)
        .where(*invoice_filter)
        .group_by(User.id, User.full_name)
        .order_by(func.sum(Invoice.total_minor).desc())
    ).all()

    invoice_by_day: dict[date, int] = defaultdict(int)
    payment_by_day: dict[date, int] = defaultdict(int)
    for item in invoices:
        invoice_by_day[item.invoice_at.astimezone(COLOMBO).date()] += item.total_minor
    for item in payments:
        payment_by_day[item.paid_at.astimezone(COLOMBO).date()] += item.amount_minor
    days = (date_to - date_from).days + 1
    trend = [
        TrendPoint(
            date=date_from + timedelta(days=offset),
            invoiced_minor=invoice_by_day[date_from + timedelta(days=offset)],
            payments_minor=payment_by_day[date_from + timedelta(days=offset)],
        )
        for offset in range(days)
    ]
    return FinancialReport(
        date_from=date_from,
        date_to=date_to,
        invoiced_sales_minor=sum(x.total_minor for x in invoices),
        payments_received_minor=sum(x.amount_minor for x in payments),
        refunds_minor=sum(x.amount_minor for x in refunds),
        outstanding_minor=sum(x.outstanding_minor for x in invoices),
        credit_notes_minor=sum(x.total_minor for x in credits),
        discounts_minor=sum(x.discount_minor for x in invoices),
        tax_minor=sum(x.tax_minor for x in invoices),
        payment_methods=[
            NamedAmount(name=name, amount_minor=method_totals[name])
            for name in ("cash", "card", "bank_transfer")
        ],
        top_products=[
            NamedAmount(name=name, amount_minor=int(amount), quantity=int(qty))
            for name, amount, qty in product_rows
        ],
        sales_by_staff=[
            NamedAmount(name=name, amount_minor=int(amount), quantity=int(count))
            for name, amount, count in staff_rows
        ],
        trend=trend,
    )


def dashboard(db: Session, tenant_id, today: date | None = None) -> DashboardResponse:
    today = today or colombo_today()
    report = financial_report(db, tenant_id, today, today)
    trend_start = today - timedelta(days=6)
    trend = financial_report(db, tenant_id, trend_start, today).trend
    outstanding = _amount(
        db,
        select(func.sum(Invoice.outstanding_minor)).where(
            Invoice.tenant_id == tenant_id, Invoice.status.in_(ACTIVE_INVOICES)
        ),
    )
    pending = _amount(
        db,
        select(func.count())
        .select_from(Quotation)
        .where(
            Quotation.tenant_id == tenant_id,
            or_(
                Quotation.status == QuotationStatus.DRAFT,
                and_(
                    Quotation.status == QuotationStatus.ISSUED,
                    or_(Quotation.expires_on.is_(None), Quotation.expires_on >= today),
                ),
            ),
        ),
    )
    low_stock = _amount(
        db,
        select(func.count())
        .select_from(InventoryBalance)
        .join(Product, Product.id == InventoryBalance.product_id)
        .where(
            InventoryBalance.tenant_id == tenant_id,
            Product.is_archived.is_(False),
            Product.track_stock.is_(True),
            InventoryBalance.quantity <= Product.reorder_threshold,
        ),
    )
    transactions: list[RecentTransaction] = []
    for item in db.scalars(
        select(Invoice)
        .where(Invoice.tenant_id == tenant_id, Invoice.status.in_(ACTIVE_INVOICES))
        .order_by(Invoice.invoice_at.desc())
        .limit(5)
    ):
        transactions.append(
            RecentTransaction(
                kind="invoice",
                reference=item.invoice_number,
                amount_minor=item.total_minor,
                occurred_at=item.invoice_at,
            )
        )
    for item in db.scalars(
        select(Payment)
        .where(Payment.tenant_id == tenant_id, Payment.reversed_by_id.is_(None))
        .order_by(Payment.paid_at.desc())
        .limit(5)
    ):
        transactions.append(
            RecentTransaction(
                kind="payment",
                reference=item.reference or item.method.value,
                amount_minor=item.amount_minor,
                occurred_at=item.paid_at,
            )
        )
    for item in db.scalars(
        select(Refund)
        .where(Refund.tenant_id == tenant_id)
        .order_by(Refund.refunded_at.desc())
        .limit(5)
    ):
        transactions.append(
            RecentTransaction(
                kind="refund",
                reference=item.reference or item.method.value,
                amount_minor=item.amount_minor,
                occurred_at=item.refunded_at,
            )
        )
    transactions.sort(key=lambda item: item.occurred_at, reverse=True)
    return DashboardResponse(
        today_invoiced_minor=report.invoiced_sales_minor,
        today_payments_minor=report.payments_received_minor,
        outstanding_minor=outstanding,
        today_refunds_minor=report.refunds_minor,
        pending_quotations=pending,
        low_stock_products=low_stock,
        recent_transactions=transactions[:10],
        trend=trend,
    )
