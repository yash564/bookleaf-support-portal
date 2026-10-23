import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import Role


class User(Base, TimestampMixin):
    """Login identity. Authors additionally have an AuthorProfile; admins do not."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    author_profile: Mapped["AuthorProfile | None"] = relationship(back_populates="user", uselist=False, lazy="selectin")


class AuthorProfile(Base):
    """Business-side author record. Keeps the dataset's AUTH001-style ids."""

    __tablename__ = "author_profiles"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. AUTH001
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(80))
    joined_date: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="author_profile", lazy="selectin")
    books: Mapped[list["Book"]] = relationship(back_populates="author", lazy="selectin")


from app.models.book import Book  # noqa: E402  (circular import for type resolution)
