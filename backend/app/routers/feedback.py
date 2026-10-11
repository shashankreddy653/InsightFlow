"""Feedback endpoints: listing, search, filters, manual submission, CSV import."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Feedback, FeedbackAnalysis, ImportBatch, Issue, IssueFeedbackLink
from ..services.analyzer import start_analysis
from ..services.importer import CsvValidationError, hash_text, import_csv_file

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _feedback_dict(fb: Feedback, an: FeedbackAnalysis | None) -> dict:
    priority = None
    issue_id = None
    for link in fb.issue_links:
        if link.issue:
            priority = link.issue.priority
            issue_id = link.issue.id
            break
    return {
        "id": fb.id,
        "review_text": fb.review_text,
        "original_category": fb.original_category,
        "sentiment": an.sentiment if an else None,
        "sentiment_score": an.sentiment_score if an else None,
        "sentiment_confidence": an.sentiment_confidence if an else None,
        "topic": an.topic if an else None,
        "refined_category": an.refined_category if an else None,
        "evidence": an.evidence if an else None,
        "analysis_method": an.analysis_method if an else None,
        "analysis_status": fb.analysis_status,
        "is_duplicate_text": fb.is_duplicate_text,
        "source": fb.source,
        "has_timestamp": fb.original_timestamp is not None,
        "issue_id": issue_id,
        "priority": priority,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }


@router.get("")
def list_feedback(
    q: str | None = None,
    category: str | None = None,
    sentiment: str | None = None,
    topic: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Paginated, searchable, filterable feedback list."""
    query = select(Feedback).options(
        joinedload(Feedback.analysis),
        joinedload(Feedback.issue_links).joinedload(IssueFeedbackLink.issue),
    )
    count_query = select(func.count(Feedback.id))

    if q:
        pattern = f"%{q.strip()}%"
        cond = or_(
            Feedback.review_text.ilike(pattern),
            Feedback.original_category.ilike(pattern),
        )
        query = query.where(cond)
        count_query = count_query.where(cond)
    if category:
        query = query.where(Feedback.original_category == category)
        count_query = count_query.where(Feedback.original_category == category)
    if status:
        query = query.where(Feedback.analysis_status == status)
        count_query = count_query.where(Feedback.analysis_status == status)

    if sentiment or topic or priority:
        query = query.join(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
        count_query = count_query.join(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
        if sentiment:
            query = query.where(FeedbackAnalysis.sentiment == sentiment)
            count_query = count_query.where(FeedbackAnalysis.sentiment == sentiment)
        if topic:
            query = query.where(FeedbackAnalysis.topic == topic)
            count_query = count_query.where(FeedbackAnalysis.topic == topic)
        if priority:
            query = query.join(IssueFeedbackLink, IssueFeedbackLink.feedback_id == Feedback.id).join(
                Issue, Issue.id == IssueFeedbackLink.issue_id
            ).where(Issue.priority == priority)
            count_query = count_query.join(
                IssueFeedbackLink, IssueFeedbackLink.feedback_id == Feedback.id
            ).join(Issue, Issue.id == IssueFeedbackLink.issue_id).where(Issue.priority == priority)

    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Feedback.id).offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return {
        "items": [_feedback_dict(fb, fb.analysis) for fb in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/facets")
def feedback_facets(db: Session = Depends(get_db)):
    """Available filter values, derived from actual data."""

    def facet(col):
        return [r for r in db.scalars(select(col).distinct().order_by(col)).all() if r]

    from ..models import Issue as IssueModel

    priorities = facet(IssueModel.priority)
    return {
        "categories": facet(Feedback.original_category),
        "sentiments": facet(FeedbackAnalysis.sentiment),
        "topics": facet(FeedbackAnalysis.topic),
        "priorities": priorities,
        "statuses": ["pending", "running", "done", "failed"],
    }


class ManualFeedback(BaseModel):
    review_text: str = Field(min_length=3, max_length=10000)
    original_category: str | None = None
    source_metadata: str | None = None


@router.post("", status_code=201)
def submit_feedback(payload: ManualFeedback, db: Session = Depends(get_db)):
    """Manual submission: saves feedback and queues it for analysis."""
    text = payload.review_text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Review text cannot be empty.")
    h = hash_text(text)
    existing = db.scalar(select(Feedback).where(Feedback.text_hash == h))
    fb = Feedback(
        review_text=text,
        original_category=(payload.original_category or "").strip() or None,
        source="manual",
        source_metadata=payload.source_metadata,
        text_hash=h,
        is_duplicate_text=existing is not None,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    start_analysis(db)
    return {"id": fb.id, "is_duplicate_text": fb.is_duplicate_text, "message": "Feedback saved and queued for analysis."}


@router.post("/import", status_code=201)
async def import_csv(
    file: UploadFile = File(...),
    mode: str = Form("append"),
    db: Session = Depends(get_db),
):
    """CSV import. mode: 'append' adds to current data, 'replace' clears first."""
    if mode not in ("append", "replace"):
        raise HTTPException(status_code=422, detail="mode must be 'append' or 'replace'.")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Please upload a .csv file.")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 25 MB upload limit.")
    try:
        result = import_csv_file(db, raw, file.filename or "upload.csv", mode=mode)
    except CsvValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.imported_rows == 0 and result.invalid_rows > 0 and result.total_rows <= result.invalid_rows:
        raise HTTPException(
            status_code=422,
            detail="No valid rows found. " + " ".join(result.errors[:3]),
        )
    start_analysis(db)
    return {
        "batch_id": result.batch_id,
        "total_rows": result.total_rows,
        "imported_rows": result.imported_rows,
        "duplicate_records_preserved": result.skipped_duplicates_in_file,
        "invalid_rows": result.invalid_rows,
        "errors": result.errors[:10],
        "has_timestamps": result.has_timestamps,
        "message": (
            f"Imported {result.imported_rows} records "
            f"({result.skipped_duplicates_in_file} are duplicate texts, preserved and "
            f"flagged for duplicate-aware analytics); analysis queued."
        ),
    }


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    batches = db.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(20)).all()
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "mode": b.mode,
            "total_rows": b.total_rows,
            "imported_rows": b.imported_rows,
            "skipped_duplicates": b.skipped_duplicates,
            "invalid_rows": b.invalid_rows,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


@router.get("/{feedback_id}")
def get_feedback(feedback_id: int, db: Session = Depends(get_db)):
    fb = db.scalar(
        select(Feedback)
        .options(joinedload(Feedback.analysis), joinedload(Feedback.issue_links))
        .where(Feedback.id == feedback_id)
    )
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    data = _feedback_dict(fb, fb.analysis)
    data["issues"] = [
        {"id": l.issue.id, "title": l.issue.title, "priority": l.issue.priority}
        for l in fb.issue_links
        if l.issue
    ]
    return data
