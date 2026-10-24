from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import InvoiceNumberSequence


def next_invoice_number(db: Session, tenant_id: UUID, year: int) -> str:
    sequence = db.scalar(
        select(InvoiceNumberSequence)
        .where(InvoiceNumberSequence.tenant_id == tenant_id, InvoiceNumberSequence.year == year)
        .with_for_update()
    )
    if sequence is None:
        try:
            with db.begin_nested():
                sequence = InvoiceNumberSequence(tenant_id=tenant_id, year=year, next_number=2)
                db.add(sequence)
                db.flush()
            number = 1
        except IntegrityError:
            sequence = db.scalar(
                select(InvoiceNumberSequence)
                .where(
                    InvoiceNumberSequence.tenant_id == tenant_id, InvoiceNumberSequence.year == year
                )
                .with_for_update()
            )
            if sequence is None:
                raise
            number = sequence.next_number
            sequence.next_number += 1
    else:
        number = sequence.next_number
        sequence.next_number += 1
    return f"INV-{year}-{number:06d}"
