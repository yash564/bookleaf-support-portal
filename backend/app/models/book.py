from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Book(Base, TimestampMixin):
    """One row per title. Nullable money/date columns model books still in production."""

    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. BK001
    author_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("author_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(32))
    genre: Mapped[str | None] = mapped_column(String(120))
    publication_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    royalty_per_copy: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    copies_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    royalty_earned: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    royalty_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    royalty_pending: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    last_payout_date: Mapped[date | None] = mapped_column(Date)
    print_partner: Mapped[str | None] = mapped_column(String(80))
    # JSON (not Postgres ARRAY) so the same model runs on SQLite in tests.
    available_on: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    author: Mapped["AuthorProfile"] = relationship(back_populates="books")

    @property
    def is_published(self) -> bool:
        return self.status == "Published & Live"


from app.models.user import AuthorProfile  # noqa: E402
