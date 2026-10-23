"""FastAPI dependencies for authentication and role-based access control.

- `get_current_user`     -> any authenticated user (401 otherwise)
- `require_author`       -> AUTHOR role with a linked AuthorProfile (403 otherwise)
- `require_admin`        -> ADMIN role (403 otherwise)

Author-scoped routes never accept an author_id from the client; they read it from the token via
`CurrentAuthor`, so an author structurally cannot query another author's data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.repositories.users import UserRepository

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    role: Role
    author_id: str | None  # populated for authors only

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN


async def _resolve_token(request: Request, creds: HTTPAuthorizationCredentials | None, token_qs: str | None) -> str:
    # Standard clients send `Authorization: Bearer <jwt>`. The browser's EventSource API cannot set
    # headers, so SSE endpoints additionally accept `?token=` (documented in the OpenAPI description).
    if creds and creds.scheme.lower() == "bearer" and creds.credentials:
        return creds.credentials
    if token_qs:
        return token_qs
    raise UnauthorizedError("Authentication required.")


async def get_current_user(
    request: Request,
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    token: Annotated[str | None, Query(include_in_schema=False)] = None,
) -> AuthContext:
    raw = await _resolve_token(request, creds, token)
    try:
        payload = decode_access_token(raw)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise UnauthorizedError("Invalid or expired token.") from None

    user = await UserRepository(db).get(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    role = Role(user.role)
    author_id = user.author_profile.id if user.author_profile else None
    return AuthContext(user=user, role=role, author_id=author_id)


CurrentUser = Annotated[AuthContext, Depends(get_current_user)]


async def require_author(ctx: CurrentUser) -> AuthContext:
    if ctx.role != Role.AUTHOR or ctx.author_id is None:
        raise ForbiddenError("This endpoint is for authors only.")
    return ctx


async def require_admin(ctx: CurrentUser) -> AuthContext:
    if ctx.role != Role.ADMIN:
        raise ForbiddenError("This endpoint is for BookLeaf staff only.")
    return ctx


CurrentAuthor = Annotated[AuthContext, Depends(require_author)]
CurrentAdmin = Annotated[AuthContext, Depends(require_admin)]
