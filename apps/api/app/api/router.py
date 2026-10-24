from fastapi import APIRouter

from app.api.routes import auth, checkout, customers, examinations, health, inventory

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(examinations.router)
api_router.include_router(inventory.router)
api_router.include_router(checkout.router)
