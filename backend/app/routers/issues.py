"""Issue tracker endpoints: save, update status/priority, notes, evidence."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Feedback, FeedbackAnalysis, Issue, IssueFeedbackLink, IssueNote

router = APIRouter(prefix="/api/issues", tags=["issues"])


def _dict(issue: Issue, detail: bool = False) -> dict:
    metrics = json.loads(issue.supporting_metrics) if issue.supporting_metrics else {}
    breakdown = json.loads(issue.score_breakdown) if issue.score_breakdown else {}
    data = {
        "id": issue.id,
        "title": issue.title,
        "description": issue.description,
        "topic": issue.topic,
        "priority": issue.user_priority or issue.priority,
        "system_priority": issue.priority,
        "priority_score": issue.priority_score,
        "score_breakdown": breakdown,
        "metrics": metrics,
        "recommendation": issue.recommendation,
        "recommendation_source": issue.recommendation_source,
        "success_metric": issue.success_metric,
        "saved": issue.saved,
        "status": issue.status,
        "action_plan": issue.action_plan,
        "resolution_notes": issue.resolution_notes,
        "notes": [
            {"id": n.id, "note_text": n.note_text, "created_at": n.created_at.isoformat() if n.created_at else None}
            for n in issue.notes
        ]
        if detail
        else None,
        "feedback_count": metrics.get("record_count", 0),
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
    }
    return data


@router.get("")
def list_issues(
    q: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    saved_only: bool | None = None,
    db: Session = Depends(get_db),
):
    query = select(Issue).options(joinedload(Issue.notes))
    count_query = select(func.count(Issue.id))
    if q:
        pattern = f"%{q.strip()}%"
        cond = or_(Issue.title.ilike(pattern), Issue.description.ilike(pattern), Issue.topic.ilike(pattern))
        query = query.where(cond)
        count_query = count_query.where(cond)
    if status:
        query = query.where(Issue.status == status)
        count_query = count_query.where(Issue.status == status)
    if priority:
        query = query.where(Issue.priority == priority)
        count_query = count_query.where(Issue.priority == priority)
    if saved_only is True:
        query = query.where(Issue.saved.is_(True))
        count_query = count_query.where(Issue.saved.is_(True))
    total = db.scalar(count_query) or 0
    # .unique() is required because joinedload(Issue.notes) eager-loads a
    # one-to-many collection, which produces duplicate parent rows.
    issues = db.scalars(query.order_by(Issue.priority_score.desc())).unique().all()
    return {"items": [_dict(i) for i in issues], "total": total}


@router.post("/{issue_id}/save", status_code=201)
def save_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    issue.saved = True
    db.commit()
    return _dict(issue)


class IssueUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(Open|In Progress|Resolved|Dismissed)$")
    priority: str | None = Field(default=None, pattern="^(Critical|High|Medium|Low)$")
    action_plan: str | None = None
    resolution_notes: str | None = None


@router.patch("/{issue_id}")
def update_issue(issue_id: int, payload: IssueUpdate, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if payload.status:
        issue.status = payload.status
    if payload.priority:
        issue.user_priority = payload.priority
    if payload.action_plan is not None:
        issue.action_plan = payload.action_plan
    if payload.resolution_notes is not None:
        issue.resolution_notes = payload.resolution_notes
    db.commit()
    db.refresh(issue)
    return _dict(issue)


class NotePayload(BaseModel):
    note_text: str = Field(min_length=1, max_length=5000)


@router.post("/{issue_id}/notes", status_code=201)
def add_note(issue_id: int, payload: NotePayload, db: Session = Depends(get_db)):
    issue = db.get(Issue, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    note = IssueNote(issue_id=issue.id, note_text=payload.note_text.strip())
    db.add(note)
    db.commit()
    return {"id": note.id, "note_text": note.note_text, "created_at": note.created_at.isoformat()}


@router.get("/{issue_id}")
def get_issue(issue_id: int, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    issue = db.scalar(
        select(Issue).options(joinedload(Issue.notes)).where(Issue.id == issue_id)
    )
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    data = _dict(issue, detail=True)
    links = db.scalars(
        select(IssueFeedbackLink)
        .where(IssueFeedbackLink.issue_id == issue.id)
        .limit(limit)
    ).all()
    fb_ids = [l.feedback_id for l in links]
    fbs = {
        fb.id: fb
        for fb in db.scalars(
            select(Feedback).options(joinedload(Feedback.analysis)).where(Feedback.id.in_(fb_ids))
        ).unique().all()
    } if fb_ids else {}
    data["evidence"] = [
        {
            "feedback_id": fid,
            "review_text": fbs[fid].review_text,
            "original_category": fbs[fid].original_category,
            "sentiment": fbs[fid].analysis.sentiment if fbs[fid].analysis else None,
            "sentiment_score": fbs[fid].analysis.sentiment_score if fbs[fid].analysis else None,
            "topic": fbs[fid].analysis.topic if fbs[fid].analysis else None,
        }
        for fid in fb_ids
        if fid in fbs
    ]
    return data
