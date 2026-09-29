from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.user import (
    User,
    Organization,
    OrganizationMember,
    UserRole,
)

import bcrypt


def hash_password(password: str) -> str:
    if isinstance(password, str):
        password = password.encode("utf-8")
    return bcrypt.hashpw(password, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if isinstance(plain, str):
        plain = plain.encode("utf-8")
    if isinstance(hashed, str):
        hashed = hashed.encode("utf-8")
    try:
        return bcrypt.checkpw(plain, hashed)
    except (ValueError, TypeError):
        return False


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, email: str, password: str, name: str = None) -> User:
        user = User(
            email=email,
            password_hash=hash_password(password),
            name=name,
            last_login=datetime.utcnow(),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_email(self, email: str) -> User:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User:
        return await self.session.get(User, user_id)

    async def update_last_login(self, user_id: str):
        user = await self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            await self.session.commit()

    async def create_organization(
        self, name: str, slug: str, owner_id: str
    ) -> Organization:
        org = Organization(name=name, slug=slug)
        self.session.add(org)
        await self.session.flush()
        member = OrganizationMember(
            organization_id=org.id,
            user_id=owner_id,
            role=UserRole.owner,
        )
        self.session.add(member)
        await self.session.commit()
        await self.session.refresh(org)
        return org

    async def get_membership(
        self, organization_id: str, user_id: str
    ) -> OrganizationMember:
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
