from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import FinancialDocumentSequence

PREFIXES = {"quotation": "QTN", "return": "RTN", "credit_note": "CRN", "optical_order": "ORD"}


def next_document_number(db: Session, tenant_id: UUID, document_type: str, year: int) -> str:
    sequence = db.scalar(
        select(FinancialDocumentSequence)
        .where(
            FinancialDocumentSequence.tenant_id == tenant_id,
            FinancialDocumentSequence.document_type == document_type,
            FinancialDocumentSequence.year == year,
        )
        .with_for_update()
    )
    if sequence is None:
        try:
            with db.begin_nested():
                sequence = FinancialDocumentSequence(
                    tenant_id=tenant_id, document_type=document_type, year=year, next_number=2
                )
                db.add(sequence)
                db.flush()
            number = 1
        except IntegrityError:
            sequence = db.scalar(
                select(FinancialDocumentSequence)
                .where(
                    FinancialDocumentSequence.tenant_id == tenant_id,
                    FinancialDocumentSequence.document_type == document_type,
                    FinancialDocumentSequence.year == year,
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
    return f"{PREFIXES[document_type]}-{year}-{number:06d}"
