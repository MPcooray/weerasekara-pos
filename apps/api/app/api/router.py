from fastapi import APIRouter

from app.api.routes import (
    adjustments,
    auth,
    checkout,
    customers,
    examinations,
    health,
    inventory,
    orders,
    printing,
    reporting,
    staff,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(examinations.router)
api_router.include_router(inventory.router)
api_router.include_router(checkout.router)
api_router.include_router(adjustments.router)
api_router.include_router(reporting.router)
api_router.include_router(printing.router)
api_router.include_router(orders.router)
api_router.include_router(staff.router)
