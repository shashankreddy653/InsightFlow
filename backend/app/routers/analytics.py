"""Analytics endpoints for the dashboard and AI Insights pages."""
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisJob, Feedback, FeedbackAnalysis, Issue
from ..services.analyzer import start_analysis

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/analyze", status_code=202)
def trigger_analysis(db: Session = Depends(get_db)):
    """Start (or resume) the background analysis pipeline."""
    job = start_analysis(db)
    return {"job_id": job.id, "status": job.status, "message": "Analysis queued."}


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """KPI summary computed from actual records."""
    total = db.scalar(select(func.count(Feedback.id))) or 0
    unique_texts = db.scalar(select(func.count(func.distinct(Feedback.text_hash)))) or 0
    dupes = total - unique_texts
    analyzed = (
        db.scalar(select(func.count(Feedback.id)).where(Feedback.analysis_status == "done")) or 0
    )
    failed = (
        db.scalar(select(func.count(Feedback.id)).where(Feedback.analysis_status == "failed")) or 0
    )
    pending = (
        db.scalar(
            select(func.count(Feedback.id)).where(
                Feedback.analysis_status.in_(["pending", "running"])
            )
        )
        or 0
    )

    sent_rows = db.execute(
        select(FeedbackAnalysis.sentiment, func.count()).group_by(FeedbackAnalysis.sentiment)
    ).all()
    sentiment = {k: v for k, v in sent_rows}

    high_priority = (
        db.scalar(
            select(func.count(Issue.id)).where(Issue.priority.in_(["Critical", "High"]))
        )
        or 0
    )
    distinct_issues = db.scalar(select(func.count(Issue.id))) or 0

    has_timestamps = db.scalar(select(func.count(Feedback.id)).where(Feedback.original_timestamp.isnot(None))) or 0

    return {
        "total_records": total,
        "unique_texts": unique_texts,
        "duplicate_records": dupes,
        "analyzed_records": analyzed,
        "pending_records": pending,
        "failed_records": failed,
        "completion_rate": round(analyzed / total, 4) if total else 0.0,
        "positive": sentiment.get("positive", 0),
        "negative": sentiment.get("negative", 0),
        "neutral": sentiment.get("neutral", 0),
        "high_priority_issues": high_priority,
        "distinct_issues": distinct_issues,
        "records_with_timestamps": has_timestamps,
        "trend_available": has_timestamps > 0 and has_timestamps == total,
    }


@router.get("/charts")
def charts(db: Session = Depends(get_db)):
    """Chart data for the dashboard."""
    category_rows = db.execute(
        select(Feedback.original_category, func.count())
        .group_by(Feedback.original_category)
        .order_by(func.count().desc())
    ).all()
    topic_rows = db.execute(
        select(FeedbackAnalysis.topic, func.count())
        .join(Feedback, FeedbackAnalysis.feedback_id == Feedback.id)
        .group_by(FeedbackAnalysis.topic)
        .order_by(func.count().desc())
        .limit(12)
    ).all()
    priority_rows = db.execute(
        select(Issue.priority, func.count()).group_by(Issue.priority)
    ).all()
    sent_rows = db.execute(
        select(FeedbackAnalysis.sentiment, func.count()).group_by(FeedbackAnalysis.sentiment)
    ).all()
    status_rows = db.execute(
        select(Feedback.analysis_status, func.count()).group_by(Feedback.analysis_status)
    ).all()

    # Trend only when every record carries a real timestamp (never fabricated)
    has_timestamps = db.scalar(
        select(func.count(Feedback.id)).where(Feedback.original_timestamp.isnot(None))
    ) or 0
    total = db.scalar(select(func.count(Feedback.id))) or 0
    trend = None
    if total and has_timestamps == total:
        rows = db.execute(
            select(
                func.strftime("%Y-%m", Feedback.original_timestamp),
                FeedbackAnalysis.sentiment,
                func.count(),
            )
            .join(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
            .group_by(func.strftime("%Y-%m", Feedback.original_timestamp), FeedbackAnalysis.sentiment)
        ).all()
        buckets: dict[str, Counter] = {}
        for month, sent, cnt in rows:
            buckets.setdefault(month or "unknown", Counter())[sent] += cnt
        trend = [
            {"month": m, **{k: v for k, v in c.items()}, "total": sum(c.values())}
            for m, c in sorted(buckets.items())
        ]

    return {
        "sentiment_distribution": dict(sent_rows),
        "category_distribution": [
            {"category": c or "Uncategorized", "count": n} for c, n in category_rows
        ],
        "topic_distribution": [{"topic": t or "General Feedback", "count": n} for t, n in topic_rows],
        "priority_distribution": dict(priority_rows),
        "analysis_status_distribution": dict(status_rows),
        "trend": trend,
        "trend_unavailable_reason": (
            None
            if trend is not None
            else "The current dataset contains no timestamp column, so a time-series chart "
            "would require fabricating dates. Upload a CSV with a 'timestamp' or 'date' "
            "column to enable trend analysis."
        ),
    }


@router.get("/job")
def current_job(db: Session = Depends(get_db)):
    job = db.scalar(
        select(AnalysisJob).order_by(AnalysisJob.id.desc()).limit(1)
    )
    if not job:
        return {"status": "idle"}
    return {
        "id": job.id,
        "status": job.status,
        "total": job.total,
        "processed": job.processed,
        "failed": job.failed,
        "message": job.message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/issues")
def issue_groups(saved_only: bool = False, db: Session = Depends(get_db)):
    """Discovered issue groups with priority explanations."""
    query = select(Issue)
    if saved_only:
        query = query.where(Issue.saved.is_(True))
    issues = db.scalars(query.order_by(Issue.priority_score.desc())).all()
    return [_issue_dict(i) for i in issues]


def _issue_dict(issue: Issue) -> dict:
    import json

    metrics = json.loads(issue.supporting_metrics) if issue.supporting_metrics else {}
    breakdown = json.loads(issue.score_breakdown) if issue.score_breakdown else {}
    return {
        "id": issue.id,
        "title": issue.title,
        "description": issue.description,
        "topic": issue.topic,
        "priority": issue.priority,
        "priority_score": issue.priority_score,
        "score_breakdown": breakdown,
        "metrics": metrics,
        "recommendation": issue.recommendation,
        "recommendation_source": issue.recommendation_source,
        "success_metric": issue.success_metric,
        "saved": issue.saved,
        "status": issue.status,
        "factors_used": metrics.get("factors_used", []),
        "factors_unavailable": metrics.get("factors_unavailable", []),
    }
