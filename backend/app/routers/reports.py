"""Report generation, history, and export endpoints."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Feedback, FeedbackAnalysis, Issue, Report
from ..services.reporting import (
    build_report_snapshot,
    feedback_rows_to_csv,
    issues_to_csv,
    snapshot_to_csv,
    snapshot_to_pdf,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _collect_snapshot(db: Session, filters: dict | None = None) -> dict:
    total = db.scalar(select(func.count(Feedback.id))) or 0
    unique = db.scalar(select(func.count(func.distinct(Feedback.text_hash)))) or 0
    sent = dict(db.execute(select(FeedbackAnalysis.sentiment, func.count()).group_by(FeedbackAnalysis.sentiment)).all())
    cats = {
        (c or "Uncategorized"): n
        for c, n in db.execute(
            select(Feedback.original_category, func.count()).group_by(Feedback.original_category)
        ).all()
    }
    topics = {
        (t or "General Feedback"): n
        for t, n in db.execute(
            select(FeedbackAnalysis.topic, func.count())
            .join(Feedback, FeedbackAnalysis.feedback_id == Feedback.id)
            .group_by(FeedbackAnalysis.topic)
        ).all()
    }
    priorities = dict(db.execute(select(Issue.priority, func.count()).group_by(Issue.priority)).all())
    top_issues = []
    for issue in db.scalars(select(Issue).order_by(Issue.priority_score.desc()).limit(10)).all():
        metrics = json.loads(issue.supporting_metrics) if issue.supporting_metrics else {}
        top_issues.append(
            {
                "id": issue.id,
                "title": issue.title,
                "priority": issue.priority,
                "priority_score": issue.priority_score,
                "record_count": metrics.get("record_count", 0),
                "negative_ratio": metrics.get("negative_ratio", 0.0),
                "recommendation": issue.recommendation,
                "success_metric": issue.success_metric,
            }
        )
    limitations = [
        "The current dataset contains no customer identifiers or timestamps; "
        "no individual-level or time-based conclusions can be drawn from it.",
        "Topics and priorities are model/rule-derived from review text; they indicate "
        "correlations and recurring complaints, not proven root causes.",
        "Duplicate review texts are counted once for topic discovery and fully for volume.",
    ]
    has_ts = db.scalar(select(func.count(Feedback.id)).where(Feedback.original_timestamp.isnot(None))) or 0
    if not has_ts:
        limitations.insert(0, "No timestamps available: trend analysis is disabled by design.")
    return build_report_snapshot(
        total_records=total,
        unique_texts=unique,
        duplicate_records=total - unique,
        sentiment_counts=sent,
        category_counts=cats,
        topic_counts=topics,
        priority_counts=priorities,
        top_issues=top_issues,
        limitations=limitations,
        filters=filters,
    )


@router.post("/generate")
def generate_report(
    payload: dict | None = None,
    db: Session = Depends(get_db),
):
    """Generate an insight report snapshot and store its metadata in history."""
    filters = payload or {}
    snapshot = _collect_snapshot(db, filters if filters else None)
    report = Report(
        title=snapshot["title"],
        report_type="filtered" if filters else "insight",
        filter_metadata=json.dumps(filters) if filters else None,
        summary_json=json.dumps(snapshot),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "snapshot": snapshot}


@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).order_by(Report.id.desc()).limit(50)).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "report_type": r.report_type,
            "filters": json.loads(r.filter_metadata) if r.filter_metadata else {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return {"id": report.id, "snapshot": json.loads(report.summary_json) if report.summary_json else {}}


@router.get("/{report_id}/export/{fmt}")
def export_report(report_id: int, fmt: str, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    snapshot = json.loads(report.summary_json) if report.summary_json else {}
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if fmt == "csv":
        return Response(
            content=snapshot_to_csv(snapshot),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="insightflow-report-{ts}.csv"'},
        )
    if fmt == "pdf":
        return Response(
            content=snapshot_to_pdf(snapshot),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="insightflow-report-{ts}.pdf"'},
        )
    raise HTTPException(status_code=422, detail="Format must be csv or pdf.")


@router.get("/export/feedback.csv")
def export_feedback(
    sentiment: str | None = None,
    category: str | None = None,
    topic: str | None = None,
    db: Session = Depends(get_db),
):
    """Export feedback rows (with analysis) honoring active filters."""
    query = (
        select(Feedback, FeedbackAnalysis)
        .outerjoin(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
        .options(joinedload(Feedback.issue_links))
    )
    if sentiment:
        query = query.where(FeedbackAnalysis.sentiment == sentiment)
    if category:
        query = query.where(Feedback.original_category == category)
    if topic:
        query = query.where(FeedbackAnalysis.topic == topic)
    rows = db.execute(query.order_by(Feedback.id)).unique().all()
    csv_text = feedback_rows_to_csv([(fb, an) for fb, an in rows])
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="insightflow-feedback-{ts}.csv"'},
    )


@router.get("/export/issues.csv")
def export_issues(db: Session = Depends(get_db)):
    issues = db.scalars(select(Issue).order_by(Issue.priority_score.desc())).all()
    csv_text = issues_to_csv(issues)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="insightflow-issues-{ts}.csv"'},
    )
