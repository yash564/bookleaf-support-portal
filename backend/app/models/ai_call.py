import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import AiCallStatus, AiPurpose


class AiCall(Base):
    """One row per model invocation. This is the cost ledger behind /admin/ai/usage."""

    __tablename__ = "ai_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
    purpose: Mapped[AiPurpose] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[AiCallStatus] = mapped_column(String(16), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
