from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book


class BookRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_author(self, author_id: str) -> list[Book]:
        # Published first, then in-production, newest publication first within each group.
        res = await self.db.execute(
            select(Book)
            .where(Book.author_id == author_id)
            .order_by(Book.publication_date.is_(None), Book.publication_date.desc(), Book.title)
        )
        return list(res.scalars())

    async def get_for_author(self, book_id: str, author_id: str) -> Book | None:
        res = await self.db.execute(select(Book).where(Book.id == book_id, Book.author_id == author_id))
        return res.scalar_one_or_none()
