from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models.enums import Role
from app.models.user import User
from app.repositories.users import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession):
        self.users = UserRepository(db)

    async def login(self, email: str, password: str) -> tuple[str, User]:
        user = await self.users.get_by_email(email)
        # Same error for unknown email and wrong password: don't leak which emails exist.
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Incorrect email or password.", code="INVALID_CREDENTIALS")
        token = create_access_token(
            user_id=user.id, role=Role(user.role), author_id=user.author_profile.id if user.author_profile else None
        )
        return token, user
