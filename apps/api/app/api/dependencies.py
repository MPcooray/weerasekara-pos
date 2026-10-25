from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import RevokedAccessToken, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DbSession = Annotated[Session, Depends(get_db)]


def get_authenticated_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = UUID(str(payload["sub"]))
        tenant_id = UUID(str(payload["tenant_id"]))
        jti = str(payload["jti"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise error from exc
    user = db.get(User, user_id)
    if (
        user is None
        or not user.is_active
        or user.tenant_id != tenant_id
        or db.get(RevokedAccessToken, jti) is not None
    ):
        raise error
    return user


def get_current_user(user: Annotated[User, Depends(get_authenticated_user)]) -> User:
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="Password change required")
    return user


AuthenticatedUser = Annotated[User, Depends(get_authenticated_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]
