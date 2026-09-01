import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from inspection_ai.database.base import get_db
from inspection_ai.database.models.user import User
from inspection_ai.database.repositories.user_repository import (
    UserRepository,
    verify_password,
)
from inspection_ai.features.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Lightweight in-memory login rate limiter --------------------------------
# Best-effort brute-force mitigation for the (bcrypt-costed) login endpoint.
# Per-process only; for multi-worker deployments move this to Redis.
_LOGIN_LIMIT = 10          # max attempts per window
_LOGIN_WINDOW = 300        # seconds
_login_attempts: dict = {}  # client ip -> [timestamps]


def _rate_limit_login(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _login_attempts.get(ip, []) if now - t < _LOGIN_WINDOW]
    if len(recent) >= _LOGIN_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )
    recent.append(now)
    _login_attempts[ip] = recent


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = None


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    name: str = None


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
        raise HTTPException(status_code=400, detail="Email already registered")
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
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    # Token is sent in the JSON body — never in the query string, which would
    # leak it into access/proxy logs.
    decoded = decode_token(payload.refresh_token, "refresh")
    if decoded is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await UserRepository(db).get_by_id(decoded.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
    }
