import csv
import io
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.permissions import Permission, has_permission
from app.models.product_import import ProductImport, ProductImportMode
from app.services.product_imports import (
    MAX_FILE_BYTES,
    confirm_import,
    parse_preview,
    response,
    template_bytes,
)

router = APIRouter(prefix="/product-imports", tags=["product imports"])


def csv_safe(value: object) -> str:
    text = str(value or "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def require_import_permission(user: CurrentUser) -> None:
    if not (
        has_permission(user, Permission.PRODUCTS_MANAGE)
        and has_permission(user, Permission.INVENTORY_RECEIVE)
        and has_permission(user, Permission.SUPPLIER_COSTS_VIEW)
    ):
        raise HTTPException(403, "Product import permission required")


class ConfirmRequest(BaseModel):
    preview_token: str = Field(min_length=20, max_length=200)


@router.get("/template")
def download_template(user: CurrentUser):
    require_import_permission(user)
    return Response(
        template_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tetrova-product-import-v1.xlsx"'},
    )


@router.post("/preview")
async def preview_import(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    mode: Annotated[ProductImportMode, Form()],
):
    require_import_permission(user)
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise HTTPException(415, "Only .xlsx files are accepted")
    content = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    return parse_preview(db, user, content, mode)


@router.post("/confirm")
def confirm(
    data: ConfirmRequest,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
):
    require_import_permission(user)
    return confirm_import(db, user, data.preview_token, idempotency_key)


@router.get("")
def history(user: CurrentUser, db: DbSession):
    require_import_permission(user)
    items = db.scalars(
        select(ProductImport)
        .where(ProductImport.tenant_id == user.tenant_id)
        .order_by(ProductImport.created_at.desc())
        .limit(50)
    ).all()
    return [response(item) for item in items]


@router.get("/{import_id}/errors.csv")
def error_report(import_id: UUID, user: CurrentUser, db: DbSession):
    require_import_permission(user)
    item = db.scalar(
        select(ProductImport).where(
            ProductImport.id == import_id, ProductImport.tenant_id == user.tenant_id
        )
    )
    if item is None:
        raise HTTPException(404, "Product import not found")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Row", "SKU", "Product Name", "Errors", "Warnings"])
    for row in item.rows_payload:
        if row["errors"] or row["warnings"]:
            writer.writerow(
                [
                    row["row"],
                    csv_safe(row["data"]["sku"]),
                    csv_safe(row["data"]["name"]),
                    csv_safe("; ".join(row["errors"])),
                    csv_safe("; ".join(row["warnings"])),
                ]
            )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="product-import-{item.id}-errors.csv"'
        },
    )
