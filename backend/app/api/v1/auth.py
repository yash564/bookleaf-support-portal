from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.schemas.common import ErrorResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(ctx_user, author_id: str | None) -> UserOut:
    return UserOut(id=ctx_user.id, email=ctx_user.email, name=ctx_user.name, role=ctx_user.role, author_id=author_id)


@router.post(
    "/login", response_model=LoginResponse, responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
)
async def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    """Email + password login. Returns a bearer JWT (7-day expiry) and the user profile."""
    token, user = await AuthService(db).login(payload.email, payload.password)
    return LoginResponse(
        access_token=token, user=_user_out(user, user.author_profile.id if user.author_profile else None)
    )


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorResponse}})
async def me(ctx: CurrentUser) -> UserOut:
    """Who am I? Used by the frontend on boot to restore the session."""
    return _user_out(ctx.user, ctx.author_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(ctx: CurrentUser) -> None:
    """Stateless JWTs: the client discards the token. Endpoint exists for API symmetry/audit logging."""
    return None
