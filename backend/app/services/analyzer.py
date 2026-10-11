"""Analysis pipeline orchestration.

Flow (duplicate-aware):
1. Collect distinct text hashes with no successful analysis -> batch-analyze.
   Sentiment and topic are computed once per unique text; every record sharing
   the text reuses the cached result.
2. Cluster unique texts (TF-IDF + agglomerative) into issue groups.
3. Score each group with the transparent priority formula.
4. Generate evidence-backed recommendations (template or LLM).
5. Persist/update Issue rows (auto groups) and IssueFeedbackLinks.

Runs in a background thread with an AnalysisJob row tracking progress so the
UI can poll; the app stays responsive during analysis.
"""
import json
import threading
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import (
    AnalysisJob,
    Feedback,
    FeedbackAnalysis,
    Issue,
    IssueFeedbackLink,
)
from .clustering import cluster_label_hints, cluster_texts
from .prioritization import DEFAULT_WEIGHTS, IssueInput, score_issue
from .recommendations import generate_recommendation
from .sentiment import analyze_sentiment
from .topics import identify_topic

ANALYSIS_VERSION = "v1"
ANALYSIS_METHOD = "vader+lexicon+tfidf"

_job_lock = threading.Lock()
_active_job_id: int | None = None


def get_active_job(db: Session) -> AnalysisJob | None:
    return db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.status.in_(["pending", "running"]))
        .order_by(AnalysisJob.id.desc())
    )


def start_analysis(db: Session) -> AnalysisJob:
    global _active_job_id
    with _job_lock:
        existing = get_active_job(db)
        if existing:
            return existing
        job = AnalysisJob(status="pending", message="Queued")
        db.add(job)
        db.commit()
        db.refresh(job)
        _active_job_id = job.id
    thread = threading.Thread(target=_run_job, args=(job.id,), daemon=True)
    thread.start()
    return job


def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(AnalysisJob, job_id)
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.message = "Collecting feedback pending analysis"
        db.commit()

        pending_hashes = list(
            db.scalars(
                select(Feedback.text_hash)
                .outerjoin(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
                .where(FeedbackAnalysis.id.is_(None))
                .distinct()
            ).all()
        )
        total_records = (
            db.scalar(
                select(func.count(Feedback.id)).where(Feedback.text_hash.in_(pending_hashes))
            )
            if pending_hashes
            else 0
        )
        job.total = total_records
        job.message = f"Analyzing {len(pending_hashes)} unique review texts"
        db.commit()

        # Representative (text, category) per hash for topic context
        reps: dict[str, str] = {}
        for fb in db.scalars(select(Feedback).where(Feedback.text_hash.in_(pending_hashes))):
            reps.setdefault(fb.text_hash, fb.review_text)

        batch = 200
        done = 0
        failed = 0
        for i in range(0, len(pending_hashes), batch):
            chunk = pending_hashes[i : i + batch]
            for h in chunk:
                try:
                    sent = analyze_sentiment(reps[h])
                    topic = identify_topic(reps[h])
                    # analysis rows attach to one record per hash; duplicates copy below
                    anchor = db.scalar(
                        select(Feedback).where(Feedback.text_hash == h).order_by(Feedback.id)
                    )
                    if anchor is None:
                        continue
                    if anchor.analysis is None:
                        db.add(
                            FeedbackAnalysis(
                                feedback_id=anchor.id,
                                sentiment=sent.label,
                                sentiment_score=sent.compound,
                                sentiment_confidence=sent.confidence,
                                topic=topic.topic,
                                refined_category=topic.refined_category,
                                evidence=topic.evidence,
                                analysis_method=ANALYSIS_METHOD,
                                analysis_version=ANALYSIS_VERSION,
                            )
                        )
                    anchor.analysis_status = "done"
                    done += 1
                except Exception:
                    failed += 1
                    anchor_err = db.scalar(
                        select(Feedback).where(Feedback.text_hash == h).order_by(Feedback.id)
                    )
                    if anchor_err:
                        anchor_err.analysis_status = "failed"
            db.commit()
            job.processed = (
                db.scalar(
                    select(func.count(Feedback.id)).where(
                        Feedback.text_hash.in_(pending_hashes[: i + batch]),
                        Feedback.analysis_status == "done",
                    )
                )
                or 0
            )
            job.failed = failed
            db.commit()

        # Duplicate propagation: every record shares its anchor's analysis
        job.message = "Propagating cached results to duplicate records"
        db.commit()
        anchors = {
            row[0].feedback.text_hash: row[0]
            for row in db.execute(
                select(FeedbackAnalysis)
                .join(Feedback, FeedbackAnalysis.feedback_id == Feedback.id)
            ).all()
        }
        all_fb = db.scalars(
            select(Feedback).where(Feedback.analysis_status != "done")
        ).all()
        # Idempotency guard: a concurrent import can surface rows whose analysis
        # row was already created, so skip any feedback_id already analyzed.
        already_analyzed = set(
            db.scalars(select(FeedbackAnalysis.feedback_id)).all()
        )
        for fb in all_fb:
            src = anchors.get(fb.text_hash)
            if src is None or fb.id in already_analyzed:
                continue
            already_analyzed.add(fb.id)
            db.add(
                FeedbackAnalysis(
                    feedback_id=fb.id,
                    sentiment=src.sentiment,
                    sentiment_score=src.sentiment_score,
                    sentiment_confidence=src.sentiment_confidence,
                    topic=src.topic,
                    refined_category=src.refined_category,
                    evidence=src.evidence,
                    analysis_method=ANALYSIS_METHOD,
                    analysis_version=ANALYSIS_VERSION,
                )
            )
            fb.analysis_status = "done"
        db.commit()

        job.message = "Grouping similar feedback into issue clusters"
        db.commit()
        _rebuild_issue_groups(db)

        job.status = "completed"
        job.finished_at = datetime.now(timezone.utc)
        job.message = f"Analysis complete: {done} texts analyzed, {failed} failed"
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if job:
            job.status = "failed"
            job.message = f"Analysis failed: {exc}"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
        traceback.print_exc()
    finally:
        global _active_job_id
        with _job_lock:
            _active_job_id = None
        db.close()


def _rebuild_issue_groups(db: Session, weights: dict | None = None) -> None:
    """(Re)build issue groups from analyzed unique texts."""
    # Unique texts with analysis (anchor record per hash = lowest id)
    anchor_ids = db.scalars(
        select(func.min(Feedback.id)).group_by(Feedback.text_hash)
    ).all()
    rows = db.execute(
        select(Feedback, FeedbackAnalysis)
        .join(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
        .where(Feedback.id.in_(anchor_ids))
    ).all()
    if not rows:
        return

    texts = [fb.review_text for fb, _ in rows]
    assignments = cluster_texts(texts)

    # record counts and sentiment per cluster over ALL records
    cluster_by_hash: dict[str, int] = {}
    for (fb, _an), a in zip(rows, assignments):
        cluster_by_hash[fb.text_hash] = a.cluster_id

    all_rows = db.execute(
        select(Feedback.text_hash, FeedbackAnalysis.sentiment, FeedbackAnalysis.sentiment_score)
        .join(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
    ).all()
    cluster_records: Counter = Counter()
    cluster_unique: dict[int, set] = defaultdict(set)
    cluster_sent: dict[int, Counter] = defaultdict(Counter)
    cluster_mag: dict[int, list[float]] = defaultdict(list)
    cluster_topics: dict[int, Counter] = defaultdict(Counter)
    cluster_categories: dict[int, Counter] = defaultdict(Counter)

    topic_by_hash = {
        fb.text_hash: an.topic
        for fb, an in rows
    }
    cat_by_hash = {
        fb.text_hash: fb.original_category
        for fb, _ in rows
    }

    for h, sentiment, score in all_rows:
        cid = cluster_by_hash.get(h)
        if cid is None:
            continue
        cluster_records[cid] += 1
        cluster_unique[cid].add(h)
        cluster_sent[cid][sentiment] += 1
        cluster_mag[cid].append(abs(score or 0.0))
        cluster_topics[cid][topic_by_hash.get(h) or "General Feedback"] += 1
        if cat_by_hash.get(h):
            cluster_categories[cid][cat_by_hash[h]] += 1

    rep_text_by_cluster: dict[int, str] = {}
    for (fb, _an), a in zip(rows, assignments):
        if a.representative:
            rep_text_by_cluster[a.cluster_id] = fb.review_text
    hints = cluster_label_hints(rep_text_by_cluster)

    # Remove previous auto-generated (non-saved) issues to rebuild cleanly
    old = db.scalars(select(Issue).where(Issue.saved.is_(False))).all()
    for issue in old:
        db.query(IssueFeedbackLink).filter(IssueFeedbackLink.issue_id == issue.id).delete()
        db.delete(issue)
    db.commit()

    saved_issues = db.scalars(select(Issue).where(Issue.saved.is_(True))).all()
    saved_by_cluster = {
        issue.cluster_id: issue for issue in saved_issues if issue.cluster_id is not None
    }
    used_titles: set[str] = {issue.title for issue in saved_issues}

    for cid in sorted(cluster_records.keys()):
        total = cluster_records[cid]
        neg = cluster_sent[cid].get("negative", 0)
        neg_ratio = neg / total if total else 0.0
        mags = cluster_mag[cid] or [0.0]
        topic = cluster_topics[cid].most_common(1)[0][0]
        base_title = _title_for(topic, hints.get(cid, []), rep_text_by_cluster.get(cid, ""))
        title = base_title
        suffix_n = 2
        while title in used_titles:
            hint = ", ".join(hints.get(cid, [])[:2])
            title = f"{base_title} ({hint})" if hint else f"{base_title} #{suffix_n}"
            suffix_n += 1
            if suffix_n > 20:
                title = f"{base_title} #{cid}"
                break
        used_titles.add(title)

        issue_input = IssueInput(
            cluster_id=cid,
            topic=topic,
            record_count=total,
            unique_count=len(cluster_unique[cid]),
            negative_ratio=neg_ratio,
            avg_sentiment_magnitude=sum(mags) / len(mags),
        )
        result = score_issue(issue_input, weights)

        group_stats = {
            "record_count": total,
            "unique_count": len(cluster_unique[cid]),
            "negative_ratio": round(neg_ratio, 4),
            "category_breakdown": dict(cluster_categories[cid]),
            "sentiment_breakdown": dict(cluster_sent[cid]),
        }
        sample_reviews = list(cluster_unique[cid])[:5]
        sample_texts = [
            fb.review_text
            for fb, _ in rows
            if fb.text_hash in cluster_unique[cid]
        ][:5]
        rec = generate_recommendation(topic, group_stats, sample_texts or sample_reviews)

        metrics = {
            "record_count": total,
            "unique_count": len(cluster_unique[cid]),
            "sentiment_breakdown": dict(cluster_sent[cid]),
            "negative_ratio": round(neg_ratio, 4),
            "category_breakdown": dict(cluster_categories[cid]),
            "avg_sentiment_magnitude": round(sum(mags) / len(mags), 4),
            "factors_used": result.factors_used,
            "factors_unavailable": result.factors_unavailable,
            "representative_text": rep_text_by_cluster.get(cid, ""),
        }

        existing = saved_by_cluster.get(cid)
        if existing:
            # refresh stats on saved issue without clobbering user fields
            existing.priority_score = result.score
            existing.priority = result.priority
            existing.score_breakdown = json.dumps(result.breakdown)
            existing.supporting_metrics = json.dumps(metrics)
            existing.recommendation = rec.text
            existing.recommendation_source = rec.source
            existing.success_metric = rec.success_metric
            issue = existing
        else:
            issue = Issue(
                title=title,
                description=_description_for(topic, metrics),
                topic=topic,
                cluster_id=cid,
                priority=result.priority,
                priority_score=result.score,
                score_breakdown=json.dumps(result.breakdown),
                supporting_metrics=json.dumps(metrics),
                recommendation=rec.text,
                recommendation_source=rec.source,
                success_metric=rec.success_metric,
                saved=False,
                status="Open",
            )
            db.add(issue)
            db.flush()

        # Links: attach every record of the cluster
        hash_set = cluster_unique[cid]
        fb_ids = db.scalars(
            select(Feedback.id).where(Feedback.text_hash.in_(hash_set))
        ).all()
        existing_links = {
            l.feedback_id
            for l in db.scalars(
                select(IssueFeedbackLink).where(IssueFeedbackLink.issue_id == issue.id)
            ).all()
        }
        db.add_all(
            IssueFeedbackLink(issue_id=issue.id, feedback_id=fid, method="tfidf_cluster")
            for fid in fb_ids
            if fid not in existing_links
        )
    db.commit()


def _title_for(topic: str, hint_terms: list[str], rep_text: str) -> str:
    if topic == "Delivery Delays":
        return "Repeated Delivery Delays"
    if topic == "Order & Packaging Problems":
        return "Order Fulfilment & Packaging Errors"
    if topic == "Fraud & Scam Reports":
        return "Reported Seller Fraud & Scams"
    if topic == "Product Defects & Quality Problems":
        return "Product Defect & Quality Complaints"
    if topic == "Customer Service Complaints":
        return "Unresolved Customer Service Issues"
    if topic == "Website & Checkout Experience":
        return "Website & Checkout Failures"
    if topic == "Refunds & Compensation":
        return "Refund & Compensation Disputes"
    if topic == "Transaction Safety (No Issues Reported)":
        return "Confirmed Safe Transactions"
    if topic == "On-Time Delivery & Packaging":
        return "On-Time Delivery & Packaging Praise"
    if topic == "Customer Service Praise":
        return "Customer Service Praise"
    if topic == "Product Quality Praise":
        return "Product Quality Praise"
    if hint_terms:
        return "Feedback cluster: " + ", ".join(hint_terms[:3])
    return "General Feedback Group"


def _description_for(topic: str, metrics: dict) -> str:
    total = metrics["record_count"]
    uniq = metrics["unique_count"]
    neg_pct = round(metrics["negative_ratio"] * 100)
    return (
        f"{total} feedback records ({uniq} unique texts) grouped by lexical similarity "
        f"and identified as '{topic}'. {neg_pct}% of the associated reviews carry "
        f"negative sentiment."
    )
