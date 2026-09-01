from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from inspection_ai.config import get_settings
from inspection_ai.database.base import get_db
from inspection_ai.database.models.user import User
from inspection_ai.database.repositories.user_repository import UserRepository

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str, expected_type: str = None) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        if expected_type and payload.get("type") != expected_type:
            return None
        return payload
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token, "access")
    if payload is None:
        raise credentials_exception
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user
