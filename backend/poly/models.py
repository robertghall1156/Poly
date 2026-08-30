"""All Poly database models in one place (see DATA_MODEL.md).

Conventions:
- string UUID primary keys
- UTC datetimes
- portable JSON columns
- `VectorType` for embeddings (pgvector on Postgres, float32 blob on SQLite)
"""
from __future__ import annotations

import struct
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

EMBEDDING_DIM = 768  # nomic-embed-text / mxbai / hashing fallback all produce 768-d vectors


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class VectorType(TypeDecorator):
    """pgvector on PostgreSQL, packed float32 blob elsewhere."""

    impl = LargeBinary
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(EMBEDDING_DIM))
        return dialect.type_descriptor(LargeBinary())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(map(float, value))
        return struct.pack(f"<{len(value)}f", *[float(v) for v in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return [float(v) for v in value]
        n = len(value) // 4
        return list(struct.unpack(f"<{n}f", value))


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for col in self.__table__.columns:  # type: ignore[attr-defined]
            val = getattr(self, col.name)
            if isinstance(val, datetime):
                val = val.isoformat()
            if col.name == "vector":
                continue
            out[col.name] = val
        return out


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Knowledge system
# ---------------------------------------------------------------------------
class Principle(TimestampMixin, Base):
    __tablename__ = "principles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    current_position: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="provisional", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    revisions: Mapped[list[PrincipleRevision]] = relationship(
        back_populates="principle", cascade="all, delete-orphan", order_by="PrincipleRevision.created_at"
    )
    evidence: Mapped[list[SupportingEvidence]] = relationship(
        back_populates="principle", cascade="all, delete-orphan"
    )
    counterarguments: Mapped[list[Counterargument]] = relationship(
        back_populates="principle", cascade="all, delete-orphan"
    )
    story_links: Mapped[list[StoryPrincipleLink]] = relationship(
        back_populates="principle", cascade="all, delete-orphan"
    )


class PrincipleRevision(Base):
    __tablename__ = "principle_revisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    principle_id: Mapped[str] = mapped_column(ForeignKey("principles.id", ondelete="CASCADE"), index=True)
    old_position: Mapped[str] = mapped_column(Text, default="")
    new_position: Mapped[str] = mapped_column(Text, default="")
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str | None] = mapped_column(String(20))
    reason_for_change: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    principle: Mapped[Principle] = relationship(back_populates="revisions")


class SupportingEvidence(Base):
    __tablename__ = "supporting_evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    principle_id: Mapped[str] = mapped_column(ForeignKey("principles.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(300), default="")
    source_type: Mapped[str] = mapped_column(String(50), default="secondary")
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(2000), default="")
    publication_date: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reliability: Mapped[str] = mapped_column(String(50), default="unknown")
    notes: Mapped[str] = mapped_column(Text, default="")
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    principle: Mapped[Principle] = relationship(back_populates="evidence")


class Counterargument(Base):
    __tablename__ = "counterarguments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    principle_id: Mapped[str] = mapped_column(ForeignKey("principles.id", ondelete="CASCADE"), index=True)
    argument: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(500), default="")
    strength: Mapped[str] = mapped_column(String(20), default="moderate")
    response: Mapped[str] = mapped_column(Text, default="")
    unresolved_questions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    principle: Mapped[Principle] = relationship(back_populates="counterarguments")


class ResearchNote(TimestampMixin, Base):
    __tablename__ = "research_notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(30), default="note")  # note | brief
    tags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)
    principle_id: Mapped[str | None] = mapped_column(ForeignKey("principles.id", ondelete="SET NULL"), index=True)
    content_item_id: Mapped[str | None] = mapped_column(ForeignKey("content_items.id", ondelete="SET NULL"))


# ---------------------------------------------------------------------------
# News intelligence
# ---------------------------------------------------------------------------
class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="other")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    ideology: Mapped[str | None] = mapped_column(String(50))
    reliability_notes: Mapped[str] = mapped_column(Text, default="")


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="rss")
    query: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(60), default="general")
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    last_fetched_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(Text)
    fetch_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("url", "query", name="uq_feed_url_query"),)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(600), nullable=False)
    title_simhash: Mapped[str] = mapped_column(String(32), index=True, default="")
    author: Mapped[str | None] = mapped_column(String(300))
    publication: Mapped[str] = mapped_column(String(200), default="")
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    feed_id: Mapped[str | None] = mapped_column(ForeignKey("feeds.id", ondelete="SET NULL"))
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    topics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    duplicate_of_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    story: Mapped[Story | None] = relationship(back_populates="articles", foreign_keys=[story_id])
    source: Mapped[Source | None] = relationship()


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(600), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), index=True, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    last_updated: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    topics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    arguments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    primary_sources: Mapped[list[Any]] = mapped_column(JSON, default=list)
    unresolved_questions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    competing_interpretations: Mapped[list[Any]] = mapped_column(JSON, default=list)
    content_potential: Mapped[list[Any]] = mapped_column(JSON, default=list)
    recommended_format: Mapped[str] = mapped_column(String(40), default="")
    dashboard_action: Mapped[str] = mapped_column(String(30), default="none", index=True)
    analysis_version: Mapped[int] = mapped_column(Integer, default=0)
    analysis_source: Mapped[str] = mapped_column(String(40), default="none")  # none | heuristic | llm:<model>
    analyzed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    keywords: Mapped[list[Any]] = mapped_column(JSON, default=list)

    articles: Mapped[list[Article]] = relationship(back_populates="story", foreign_keys=[Article.story_id])
    events: Mapped[list[StoryEvent]] = relationship(
        back_populates="story", cascade="all, delete-orphan", order_by="StoryEvent.occurred_at"
    )
    claims: Mapped[list[Claim]] = relationship(back_populates="story", cascade="all, delete-orphan")
    principle_links: Mapped[list[StoryPrincipleLink]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )


class StoryEvent(Base):
    __tablename__ = "story_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    story_id: Mapped[str] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    kind: Mapped[str] = mapped_column(String(30), default="article")  # article | analysis | user
    description: Mapped[str] = mapped_column(Text, default="")

    story: Mapped[Story] = relationship(back_populates="events")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    story_id: Mapped[str] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(20), default="FACT")
    supporting_passage: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    publication: Mapped[str] = mapped_column(String(200), default="")
    is_primary_source: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_source_url: Mapped[str] = mapped_column(String(2000), default="")
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    story: Mapped[Story] = relationship(back_populates="claims")


class StoryPrincipleLink(Base):
    __tablename__ = "story_principle_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    story_id: Mapped[str] = mapped_column(ForeignKey("stories.id", ondelete="CASCADE"), index=True)
    principle_id: Mapped[str] = mapped_column(ForeignKey("principles.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(20), default="relates")
    strength: Mapped[float] = mapped_column(Float, default=0.5)
    note: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("story_id", "principle_id", name="uq_story_principle"),)

    story: Mapped[Story] = relationship(back_populates="principle_links")
    principle: Mapped[Principle] = relationship(back_populates="story_links")


# ---------------------------------------------------------------------------
# Thinking
# ---------------------------------------------------------------------------
class ThinkSession(TimestampMixin, Base):
    __tablename__ = "think_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)
    principle_id: Mapped[str | None] = mapped_column(ForeignKey("principles.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    messages: Mapped[list[Any]] = mapped_column(JSON, default=list)
    principle_ids_considered: Mapped[list[Any]] = mapped_column(JSON, default=list)
    model_used: Mapped[str] = mapped_column(String(120), default="")

    briefs: Mapped[list[PositionBrief]] = relationship(back_populates="session")


class PositionBrief(Base):
    __tablename__ = "position_briefs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    think_session_id: Mapped[str | None] = mapped_column(ForeignKey("think_sessions.id", ondelete="SET NULL"))
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)
    issue: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    governing_principle_id: Mapped[str | None] = mapped_column(ForeignKey("principles.id", ondelete="SET NULL"))
    governing_principle_text: Mapped[str] = mapped_column(Text, default="")
    strongest_for: Mapped[str] = mapped_column(Text, default="")
    strongest_against: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    factual_assumptions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    unresolved_questions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    policy_mechanisms: Mapped[list[Any]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    approved_principle_id: Mapped[str | None] = mapped_column(ForeignKey("principles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    session: Mapped[ThinkSession | None] = relationship(back_populates="briefs")


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
CONTENT_STATUSES = [
    "IDEA", "RESEARCHING", "POSITION_DEVELOPED", "SCRIPTING", "RECORDED", "EDITING", "READY", "PUBLISHED",
]
CONTENT_FORMATS = [
    "podcast", "youtube", "youtube_short", "tiktok", "instagram_reel", "x_post", "x_thread", "facebook_post",
    "instagram_post", "linkedin_post", "newsletter", "article", "book_note", "meme", "infographic",
    "talking_points", "research_brief",
]


class ContentItem(TimestampMixin, Base):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    format: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="IDEA", index=True)
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"), index=True)
    principle_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    position_brief_id: Mapped[str | None] = mapped_column(ForeignKey("position_briefs.id", ondelete="SET NULL"))
    script: Mapped[str] = mapped_column(Text, default="")
    package: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"))
    clip_id: Mapped[str | None] = mapped_column(ForeignKey("clips.id", ondelete="SET NULL"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("content_items.id", ondelete="SET NULL"), index=True)
    platform: Mapped[str] = mapped_column(String(40), default="")
    publish_date: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    url: Mapped[str] = mapped_column(String(2000), default="")
    fact_check_status: Mapped[str] = mapped_column(String(30), default="not_run")
    fact_check_override_reason: Mapped[str] = mapped_column(Text, default="")
    substantive_value: Mapped[float | None] = mapped_column(Float)
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    generation_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    children: Mapped[list[ContentItem]] = relationship(
        back_populates="parent", foreign_keys=[parent_id], cascade="all"
    )
    parent: Mapped[ContentItem | None] = relationship(
        back_populates="children", remote_side=[id], foreign_keys=[parent_id]
    )
    fact_check_claims: Mapped[list[FactCheckClaim]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )
    metrics: Mapped[list[ContentMetric]] = relationship(back_populates="content_item", cascade="all, delete-orphan")


class FactCheckClaim(Base):
    __tablename__ = "fact_check_claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")
    sources: Mapped[list[Any]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    content_item: Mapped[ContentItem] = relationship(back_populates="fact_check_claims")


class ContentMetric(Base):
    __tablename__ = "content_metrics"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(40), default="")
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    views: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    retention_pct: Mapped[float | None] = mapped_column(Float)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_gained: Mapped[int] = mapped_column(Integer, default=0)
    completion_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="manual")

    content_item: Mapped[ContentItem] = relationship(back_populates="metrics")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(60), default="deterministic")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    path: Mapped[str] = mapped_column(String(2000), default="")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str] = mapped_column(String(30), default="chart")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    content_item_id: Mapped[str | None] = mapped_column(ForeignKey("content_items.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


# ---------------------------------------------------------------------------
# Book
# ---------------------------------------------------------------------------
class BookProject(TimestampMixin, Base):
    __tablename__ = "book_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    working_titles: Mapped[list[Any]] = mapped_column(JSON, default=list)
    premise: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="concept")

    chapters: Mapped[list[BookChapter]] = relationship(
        back_populates="book", cascade="all, delete-orphan", order_by="BookChapter.order"
    )
    notes: Mapped[list[BookNote]] = relationship(back_populates="book", cascade="all, delete-orphan")


class BookChapter(TimestampMixin, Base):
    __tablename__ = "book_chapters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    book_id: Mapped[str] = mapped_column(ForeignKey("book_projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="idea")

    book: Mapped[BookProject] = relationship(back_populates="chapters")
    notes: Mapped[list[BookNote]] = relationship(back_populates="chapter")


class BookNote(TimestampMixin, Base):
    __tablename__ = "book_notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    book_id: Mapped[str | None] = mapped_column(ForeignKey("book_projects.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey("book_chapters.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="note")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"))
    principle_id: Mapped[str | None] = mapped_column(ForeignKey("principles.id", ondelete="SET NULL"))
    content_item_id: Mapped[str | None] = mapped_column(ForeignKey("content_items.id", ondelete="SET NULL"))
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="SET NULL"))
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id", ondelete="SET NULL"))

    book: Mapped[BookProject | None] = relationship(back_populates="notes")
    chapter: Mapped[BookChapter | None] = relationship(back_populates="notes")


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------
class VideoFolder(Base):
    __tablename__ = "video_folders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    path: Mapped[str] = mapped_column(String(2000), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    recursive: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    videos: Mapped[list[Video]] = relationship(back_populates="folder", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    folder_id: Mapped[str] = mapped_column(ForeignKey("video_folders.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(2000), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    codec: Mapped[str] = mapped_column(String(50), default="")
    has_audio: Mapped[bool] = mapped_column(Boolean, default=True)
    file_created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    file_modified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    indexed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    transcript_status: Mapped[str] = mapped_column(String(20), default="none", index=True)
    transcript_provider: Mapped[str] = mapped_column(String(60), default="")
    transcript_language: Mapped[str] = mapped_column(String(10), default="")
    transcript_error: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    topics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    people: Mapped[list[Any]] = mapped_column(JSON, default=list)
    key_moments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    fingerprint: Mapped[str] = mapped_column(String(64), default="")
    missing: Mapped[bool] = mapped_column(Boolean, default=False)

    folder: Mapped[VideoFolder] = relationship(back_populates="videos")
    segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="TranscriptSegment.idx"
    )
    clips: Mapped[list[Clip]] = relationship(back_populates="video", cascade="all, delete-orphan")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer, default=0)
    start: Mapped[float] = mapped_column(Float, nullable=False)
    end: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    words: Mapped[list[Any]] = mapped_column(JSON, default=list)

    video: Mapped[Video] = relationship(back_populates="segments")


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    start: Mapped[float] = mapped_column(Float, nullable=False)
    end: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    why_it_works: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    platform: Mapped[str] = mapped_column(String(40), default="youtube_short")
    status: Mapped[str] = mapped_column(String(20), default="suggested", index=True)
    render_path: Mapped[str] = mapped_column(String(2000), default="")
    render_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    render_error: Mapped[str | None] = mapped_column(Text)
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    story_id: Mapped[str | None] = mapped_column(ForeignKey("stories.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    video: Mapped[Video] = relationship(back_populates="clips")


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


TASK_CATEGORIES = ["FAST", "REASONING", "WRITING", "EMBEDDING", "VISION", "TRANSCRIPTION", "IMAGE"]


class LocalModel(Base):
    __tablename__ = "local_models"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), default="")
    context_window: Mapped[int | None] = mapped_column(Integer)
    tasks: Mapped[list[Any]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    fallback_model_id: Mapped[str | None] = mapped_column(ForeignKey("local_models.id", ondelete="SET NULL"))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_ok_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_latency_ms: Mapped[float | None] = mapped_column(Float)
    last_error: Mapped[str | None] = mapped_column(Text)
    detected: Mapped[bool] = mapped_column(Boolean, default=True)
    locality: Mapped[str] = mapped_column(String(10), default="local")  # local | cloud
    __table_args__ = (UniqueConstraint("name", "runtime", "endpoint", name="uq_local_model"),)


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    vector: Mapped[list[float] | None] = mapped_column(VectorType)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "chunk_index", name="uq_embedding_chunk"),
        Index("ix_embeddings_entity", "entity_type", "entity_id"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retryable: Mapped[bool] = mapped_column(Boolean, default=True)
    cloud_override_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

# ---------------------------------------------------------------------------
# Faceless Content Studio
# ---------------------------------------------------------------------------
FACELESS_FORMATS = [
    "question", "text_explainer", "news_explainer", "did_you_know", "system_explainer",
    "data_story", "argument", "my_take", "custom",
]
SCENE_VISUAL_TYPES = ["text", "title", "question", "chart", "comparison", "counter", "timeline", "list", "image", "quote", "icon"]


class VideoProject(TimestampMixin, Base):
    """A scripted (faceless) video or carousel. Scenes follow the VideoScene JSON schema:

    {order, duration, narration, on_screen_text, subtext, visual_type, visual, animation,
     transition, background, emphasis, source}
    """

    __tablename__ = "video_projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="faceless_video")  # faceless_video | carousel
    format: Mapped[str] = mapped_column(String(30), default="question")
    target_seconds: Mapped[int] = mapped_column(Integer, default=30)
    platform: Mapped[str] = mapped_column(String(30), default="youtube_short")
    voice_mode: Mapped[str] = mapped_column(String(10), default="none")  # none | tts
    tts_voice: Mapped[str] = mapped_column(String(80), default="")
    music_path: Mapped[str] = mapped_column(String(2000), default="")
    music_recommendation: Mapped[str] = mapped_column(String(300), default="")
    scenes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    previous_scenes: Mapped[list[Any]] = mapped_column(JSON, default=list)  # last version, for undo
    sources: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [{label, url}]
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list[Any]] = mapped_column(JSON, default=list)
    brand_overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    render_status: Mapped[str] = mapped_column(String(20), default="none")  # none|queued|rendering|done|failed
    render_path: Mapped[str] = mapped_column(String(2000), default="")
    render_error: Mapped[str | None] = mapped_column(Text)
    generation_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    content_item: Mapped[ContentItem] = relationship()
