import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        res = await self.db.execute(select(User).where(User.email == email.lower()))
        return res.scalar_one_or_none()

    async def list_admins(self) -> list[User]:
        res = await self.db.execute(select(User).where(User.role == Role.ADMIN).order_by(User.name))
        return list(res.scalars())
