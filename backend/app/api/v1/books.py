from fastapi import APIRouter

from app.core.deps import CurrentAuthor, DbSession
from app.repositories.books import BookRepository
from app.schemas.books import BookOut, BooksResponse, BooksSummary
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/books", tags=["author"])


@router.get("", response_model=BooksResponse, responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}})
async def list_my_books(ctx: CurrentAuthor, db: DbSession) -> BooksResponse:
    """The signed-in author's books with a royalty roll-up. Scoped by the token, never by a query param."""
    books = await BookRepository(db).list_for_author(ctx.author_id)  # type: ignore[arg-type]
    return BooksResponse(items=[BookOut.from_model(b) for b in books], summary=BooksSummary.from_books(books))
