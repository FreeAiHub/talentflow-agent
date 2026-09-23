"""SQLAlchemy tables.

These are the persistence shape, kept separate from the Pydantic domain models
in :mod:`talentflow.models`. The repository layer maps between the two so the
rest of the application never sees a database row.

Raw scraped data (``vacancies``) is deliberately split from derived data
(``scored_vacancies``, ``applications``): re-scoring a vacancy appends a new row
instead of overwriting history, and a scoring bug never corrupts what we
actually collected.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    """Timezone-aware now — naive timestamps are a bug waiting to happen."""
    return datetime.now(UTC)


def start_of_utc_day(now: datetime | None = None) -> datetime:
    """Midnight UTC of the day ``now`` falls in.

    Lives here rather than beside the LLM budget: it is a time utility, and
    putting it in the LLM layer made storage import the LLM layer, which made
    the LLM layer import storage, which is a cycle.
    """
    moment = now or datetime.now(UTC)
    return moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


class UTCDateTime(TypeDecorator[datetime]):
    """A datetime that always reads back as timezone-aware UTC.

    SQLite has no timezone type: it stores whatever it is handed and returns a
    naive datetime, while Postgres preserves the offset. Without normalising,
    the same row reads back differently on the two databases — and comparing a
    naive value with an aware one raises ``TypeError`` at some later, less
    convenient moment.

    Naive input is treated as UTC. That is an assumption, not a fact: Djinni
    sends ``datePosted`` without an offset, so its local time is being read as
    UTC. Ordering is unaffected, since a constant offset cancels out; absolute
    times are off by the site's offset until this is resolved.
    """

    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    """Declarative base for every table."""


class VacancyRow(Base):
    """A vacancy as collected from a source, before any scoring."""

    __tablename__ = "vacancies"

    #: Source-native identifier (Djinni's ``identifier``), not a surrogate key:
    #: it is what deduplication already keys on during collection.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VacancyRow {self.id} {self.title!r}>"


class ScoredVacancyRow(Base):
    """One scoring result. Append-only: history is kept, not overwritten."""

    __tablename__ = "scored_vacancies"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "model", name="uq_scored_vacancy_model"),
        Index("ix_scored_vacancies_score", "score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vacancy_id: Mapped[str] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    #: Human-readable justification from the scorer; JSON rather than a
    #: delimited string so the reasons survive a round trip intact.
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    #: Which model produced this score — scores from different models are not
    #: comparable, so the model is part of the row's identity.
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ScoredVacancyRow {self.vacancy_id} score={self.score}>"


class ApplicationRow(Base):
    """A generated response to a vacancy, pending or decided."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vacancy_id: Mapped[str] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Nothing is sent while this is False — the human-in-the-loop gate.
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    #: Set once the reviewer has been told about this draft. Without it the
    #: notify stage would re-send every pending draft on every run.
    notified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ApplicationRow {self.id} {self.vacancy_id} {self.status}>"


class RunRow(Base):
    """One execution of the pipeline, for observability and daily limits."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    #: What ran: ``parse``, ``score``, ``notify``.
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    items_processed: Mapped[int] = mapped_column(nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<RunRow {self.id} {self.kind} {self.status}>"


class LlmCallRow(Base):
    """One LLM request, successful or not.

    Serves three purposes at once: the daily call budget is counted from here,
    cost per vacancy is summed from here, and a failed run can be explained
    from here. Recording failures matters as much as successes — a provider
    that answers 429 all day should be visible, not inferred.
    """

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    #: Which logical task this call served: ``score``, ``generate``.
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tokens_in: Mapped[int] = mapped_column(nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(nullable=False, default=0)
    #: Cost in USD as reported by the provider; zero for free tiers.
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    called_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LlmCallRow {self.model} ok={self.ok} {self.latency_ms}ms>"


class LlmCacheRow(Base):
    """A cached model response, keyed by model and prompt.

    Scoring the same vacancy twice should cost nothing. The key includes the
    model because two models given the same prompt are not interchangeable.
    """

    __tablename__ = "llm_cache"

    #: SHA-256 of ``model + "\\x00" + prompt``.
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LlmCacheRow {self.model} {self.key[:8]}>"


class TelegramUpdateRow(Base):
    """A webhook update already handled.

    Telegram retries deliveries, so the same press can arrive twice. Without
    this, a retry of an old "approve" could land after a newer "reject" and
    silently reverse it.
    """

    __tablename__ = "telegram_updates"

    update_id: Mapped[int] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TelegramUpdateRow {self.update_id} {self.action}>"
