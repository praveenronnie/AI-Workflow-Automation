import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ConflictError
from backend.database.base import get_db
from backend.database.models.user import RefreshToken, User
from backend.database.repositories.user_repository import (
    UserRepository,
    verify_password,
)
from backend.features.auth.rate_limit import (
    LOGIN_WINDOW,
    check_login_allowed,
)
from backend.features.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _rate_limit_login(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not check_login_allowed(ip):
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many login attempts. Please try again later "
                f"(limit resets after {LOGIN_WINDOW}s)."
            ),
        )


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = None


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    repo = UserRepository(db)
    existing = await repo.get_by_email(request.email)
    if existing:
        raise ConflictError("Email already registered")
    user = await repo.create_user(request.email, request.password, request.name)
    logger.info("Registered user %s", user.id)
    return RegisterResponse(user_id=user.id, email=user.email, name=user.name)


@router.post("/token", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    _rate_limit_login(request)
    repo = UserRepository(db)
    user = await repo.get_by_email(form.username)
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    await repo.update_last_login(user.id)
    logger.info("User logged in %s", user.id)
    refresh_token, refresh_jti = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            jti=refresh_jti,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=settings_jwt_refresh_days()),
        )
    )
    await db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


def settings_jwt_refresh_days() -> int:
    from backend.core.config import get_settings

    return get_settings().jwt_refresh_token_expire_days


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    # Token is sent in the JSON body — never in the query string, which would
    # leak it into access/proxy logs.
    decoded = decode_token(payload.refresh_token, "refresh")
    if decoded is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    jti = decoded.get("jti")
    user = await UserRepository(db).get_by_id(decoded.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Revocation check: the jti must exist and not be revoked.
    row = (
        (
            await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        ).scalar_one_or_none()
        if jti
        else None
    )
    if row is None or row.revoked or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

    # Rotation: revoke the presented token, issue a new pair.
    await db.execute(
        update(RefreshToken).where(RefreshToken.jti == jti).values(revoked=True)
    )
    new_refresh, new_jti = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            jti=new_jti,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=settings_jwt_refresh_days()),
        )
    )
    await db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=new_refresh,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Revoke every refresh token for the calling user."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await db.commit()
    logger.info("User logged out (refresh tokens revoked) %s", current_user.id)
    return {"status": "logged_out"}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
    }
