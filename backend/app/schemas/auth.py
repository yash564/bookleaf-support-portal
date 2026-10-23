import uuid

from pydantic import EmailStr, Field

from app.models.enums import Role
from app.schemas.common import ApiModel


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ApiModel):
    id: uuid.UUID
    email: str
    name: str
    role: Role
    author_id: str | None = None


class LoginResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
