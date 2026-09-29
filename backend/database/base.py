from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from backend.core.config import get_settings

settings = get_settings()

DB_NAME = settings.db_name
USER = settings.db_username
PASWORD = settings.db_password
HOST = settings.db_host
PORT = settings.db_port

DATABASE_URL = f"postgresql+asyncpg://{USER}:{PASWORD}@{HOST}:{PORT}/{DB_NAME}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Use NullPool so every session opens a connection bound to the *current*
    # event loop and closes it on exit.  The Celery tasks run each pipeline via
    # ``asyncio.run`` (a fresh loop per invocation); a persistent pool would
    # otherwise hand down an asyncpg connection whose protocol is pinned to a
    # previously-closed loop, raising "Future ... attached to a different loop".
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
