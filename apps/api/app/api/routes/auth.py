from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.core.security import create_access_token, verify_password
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DbSession) -> TokenResponse:
    query = (
        select(User)
        .join(Tenant)
        .where(Tenant.slug == credentials.tenant_slug, User.email == credentials.email.lower())
    )
    user = db.scalar(query)
    if (
        user is None
        or not user.is_active
        or not verify_password(credentials.password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id), role=user.role.value
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user
