from inspection_ai.database.base import Base, engine, AsyncSessionLocal, get_db
from inspection_ai.database import models

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
