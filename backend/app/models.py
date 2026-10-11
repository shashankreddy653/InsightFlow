"""SQLAlchemy ORM models for InsightFlow."""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportBatch(Base):
    """One CSV import or manual-submission batch."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    mode: Mapped[str] = mapped_column(String(16))  # "replace" | "append"
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    """A single customer feedback record. Original dataset fields are preserved verbatim."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="csv")  # csv | manual
    source_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    text_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    is_duplicate_text: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    analysis_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending | running | done | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["FeedbackAnalysis | None"] = relationship(
        back_populates="feedback", uselist=False, cascade="all, delete-orphan"
    )
    issue_links: Mapped[list["IssueFeedbackLink"]] = relationship(
        back_populates="feedback", cascade="all, delete-orphan"
    )


class FeedbackAnalysis(Base):
    """Model-generated analysis. Stored separately from original data."""

    __tablename__ = "feedback_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id"), unique=True, index=True)
    sentiment: Mapped[str] = mapped_column(String(16), index=True)  # positive | negative | neutral
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # VADER compound
    sentiment_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    refined_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_method: Mapped[str] = mapped_column(String(64), default="vader+lexicon+tfidf")
    analysis_version: Mapped[str] = mapped_column(String(32), default="v1")
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    feedback: Mapped[Feedback] = relationship(back_populates="analysis")


class Issue(Base):
    """An issue group discovered from feedback; can be saved to the tracker."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="Medium", index=True)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    supporting_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # template | llm
    success_metric: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="Open", index=True)
    # Open | In Progress | Resolved | Dismissed
    user_priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    action_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    notes: Mapped[list["IssueNote"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan", order_by="IssueNote.created_at"
    )
    feedback_links: Mapped[list["IssueFeedbackLink"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


class IssueFeedbackLink(Base):
    """Association between an issue and the feedback records that evidence it."""

    __tablename__ = "issue_feedback_links"
    __table_args__ = (UniqueConstraint("issue_id", "feedback_id", name="uq_issue_feedback"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id"), index=True)
    method: Mapped[str] = mapped_column(String(32), default="tfidf_cluster")
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    issue: Mapped[Issue] = relationship(back_populates="feedback_links")
    feedback: Mapped[Feedback] = relationship(back_populates="issue_links")


class IssueNote(Base):
    __tablename__ = "issue_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), index=True)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    issue: Mapped[Issue] = relationship(back_populates="notes")


class Report(Base):
    """Metadata of a generated report (history)."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    report_type: Mapped[str] = mapped_column(String(32))  # insight | filtered
    filter_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisJob(Base):
    """Progress tracking for background analysis runs."""

    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending | running | completed | failed
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppSetting(Base):
    """Key/value application settings (priority weights etc.)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class AdaptionRun(Base):
    """Record of an Adaption workflow attempt, honest about outcomes."""

    __tablename__ = "adaption_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32))  # succeeded | failed | not_configured
    step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
