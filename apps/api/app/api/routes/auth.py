from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import delete, select

from app.api.dependencies import AuthenticatedUser, DbSession
from app.core.config import get_settings
from app.core.permissions import permission_names
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.tenant import Tenant
from app.models.user import RevokedAccessToken, User
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    PasswordChangeResponse,
    TokenResponse,
    UserResponse,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DbSession) -> TokenResponse:
    settings = get_settings()
    now = datetime.now(UTC)
    db.execute(delete(RevokedAccessToken).where(RevokedAccessToken.expires_at < now))
    query = (
        select(User)
        .join(Tenant)
        .where(Tenant.slug == credentials.tenant_slug, User.email == credentials.email.lower())
        .with_for_update()
    )
    user = db.scalar(query)
    if user is not None and _aware(user.locked_until) and _aware(user.locked_until) > now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    password_valid = verify_password(
        credentials.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    valid = bool(user is not None and user.is_active and password_valid)
    if not valid:
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_attempts = 0
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role.value,
        session_version=user.session_version,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: AuthenticatedUser) -> UserResponse:
    return UserResponse.model_validate(
        {**user.__dict__, "permissions": permission_names(user.role)}
    )


@router.post("/logout", status_code=204)
def logout(
    user: AuthenticatedUser,
    db: DbSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> None:
    payload = decode_access_token(token)
    expires_at = datetime.fromtimestamp(float(payload["exp"]), UTC)
    jti = str(payload["jti"])
    if db.get(RevokedAccessToken, jti) is None:
        db.add(
            RevokedAccessToken(
                jti=jti,
                user_id=UUID(str(payload["sub"])),
                tenant_id=user.tenant_id,
                expires_at=expires_at,
                revoked_at=datetime.now(UTC),
            )
        )
        db.commit()


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    data: PasswordChange, user: AuthenticatedUser, db: DbSession
) -> PasswordChangeResponse:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=422, detail="New password must be different")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    user.version += 1
    user.session_version += 1
    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="staff.password_changed",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    replacement = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role.value,
        session_version=user.session_version,
    )
    return PasswordChangeResponse(access_token=replacement, user=me(user))
