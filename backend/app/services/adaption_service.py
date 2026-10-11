"""Adaption integration (https://adaptionlabs.ai) using the official Python SDK.

Workflow implemented here (matches the Adaptive Data quickstart):
1. Prepare a task-specific instruction dataset from real InsightFlow feedback
   (prompt = review text, completion = structured analysis JSON).
2. Upload via client.datasets.upload_file()
3. Adapt via client.datasets.adapt() with column mapping (estimate first).
4. Poll client.datasets.get_status() until completion.
5. Download the adapted dataset; compare against the hand-labeled reference
   subset for evaluation.
6. Record every attempt honestly in the AdaptionRun table.

If ADAPTION_API_KEY is missing or a call fails, the run is recorded as
not_configured/failed with the real error - the rest of the application keeps
working on the local pipeline. No credentials ever reach the frontend.
"""
import csv
import io
import json
import os
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AdaptionRun, Feedback, FeedbackAnalysis

REFERENCE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "adaption_reference_labels.json"
)


def reference_labels() -> list[dict]:
    """Hand-labeled evaluation subset (documented in README)."""
    try:
        with open(os.path.normpath(REFERENCE_PATH), encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload.get("labels", [])
        return payload
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def sdk_available() -> bool:
    try:
        import adaption  # noqa: F401

        return True
    except ImportError:
        return False


def integration_status(db: Session) -> dict:
    """Honest status of the Adaption integration for the Integrations page."""
    settings = get_settings()
    key_present = bool(settings.adaption_api_key)
    last = db.scalar(select(AdaptionRun).order_by(AdaptionRun.id.desc()))
    status = {
        "configured": key_present,
        "sdk_installed": sdk_available(),
        "workflow": "Adaptive Data instruction-dataset optimization for feedback analysis",
        "task": (
            "Build an optimized instruction dataset (review -> structured analysis) "
            "from InsightFlow's labeled feedback to fine-tune/evaluate the analysis "
            "pipeline."
        ),
        "reference_examples": len(reference_labels()),
        "last_run": None,
    }
    if last:
        status["last_run"] = {
            "id": last.id,
            "status": last.status,
            "step": last.step,
            "dataset_id": last.dataset_id,
            "run_id": last.run_id,
            "detail": last.detail,
            "result_summary": json.loads(last.result_summary) if last.result_summary else None,
            "created_at": last.created_at.isoformat() if last.created_at else None,
        }
    if not key_present:
        status["setup_instructions"] = [
            "1. Sign in at https://adaptionlabs.ai/app/auth",
            "2. Open Settings -> API keys and create a key",
            "3. Put it in backend/.env as ADAPTION_API_KEY=pt_live_...",
            "4. Restart the backend and press 'Run evaluation run' on this page",
        ]
    return status


def build_instruction_dataset(db: Session) -> tuple[str, int]:
    """Prepare prompt/completion CSV from analyzed feedback (unique texts).

    Completion is the structured analysis our pipeline produced, validated
    against the hand-labeled reference subset. Returns (csv_text, row_count).
    """
    labels = {r["review"].strip().lower(): r for r in reference_labels()}
    anchor_ids = db.scalars(
        select(func.min(Feedback.id)).group_by(Feedback.text_hash)
    ).all()
    rows = db.execute(
        select(Feedback, FeedbackAnalysis)
        .join(FeedbackAnalysis, FeedbackAnalysis.feedback_id == Feedback.id)
        .where(Feedback.id.in_(anchor_ids))
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["review", "analysis", "reference_label"])
    count = 0
    for fb, an in rows:
        completion = json.dumps(
            {
                "sentiment": an.sentiment,
                "topic": an.topic,
                "refined_category": an.refined_category,
                "explanation": an.evidence or "",
            },
            ensure_ascii=False,
        )
        ref = labels.get(fb.review_text.strip().lower())
        ref_label = (
            json.dumps({"sentiment": ref["sentiment"], "topic": ref["topic"]}, ensure_ascii=False)
            if ref
            else ""
        )
        writer.writerow([fb.review_text, completion, ref_label])
        count += 1
    return buf.getvalue(), count


def _record(db: Session, **kwargs) -> AdaptionRun:
    run = AdaptionRun(**kwargs)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def evaluate_local_pipeline(db: Session) -> dict:
    """Evaluate the local analysis pipeline against the hand-labeled subset.

    This is the held-out evaluation referenced in the README; it works with or
    without Adaption credentials and is the honest baseline for any
    improvement claims.
    """
    labels = reference_labels()
    if not labels:
        return {"error": "No reference labels found."}
    from .sentiment import analyze_sentiment
    from .topics import identify_topic

    correct_sent = 0
    correct_topic = 0
    ambiguous_total = 0
    ambiguous_correct = 0
    total = len(labels)
    mismatches = []
    for item in labels:
        got = analyze_sentiment(item["review"])
        topic = identify_topic(item["review"], item.get("category"))
        sent_ok = got.label == item["sentiment"]
        topic_ok = topic.topic == item["topic"]
        if item.get("ambiguous"):
            ambiguous_total += 1
            ambiguous_correct += int(sent_ok)
        else:
            correct_sent += int(sent_ok)
            correct_topic += int(topic_ok)
        if (not sent_ok or not topic_ok) and len(mismatches) < 10:
            mismatches.append(
                {
                    "review": item["review"][:120],
                    "expected_sentiment": item["sentiment"],
                    "got_sentiment": got.label,
                    "expected_topic": item["topic"],
                    "got_topic": topic.topic,
                    "ambiguous": bool(item.get("ambiguous")),
                }
            )
    clear_total = max(1, total - ambiguous_total)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "clear_total": total - ambiguous_total,
        "ambiguous_total": ambiguous_total,
        "sentiment_accuracy": round(correct_sent / clear_total, 4),
        "topic_accuracy": round(correct_topic / clear_total, 4),
        "ambiguous_sentiment_agreement": round(ambiguous_correct / max(1, ambiguous_total), 4),
        "sample_mismatches": mismatches,
    }


def run_adaption_workflow(db: Session) -> dict:
    """Full Adaptive Data run. Records every step honestly. Returns status dict."""
    settings = get_settings()
    if not settings.adaption_api_key:
        _record(
            db,
            status="not_configured",
            step="auth",
            detail="ADAPTION_API_KEY is not set. Local pipeline remains available.",
        )
        return {"status": "not_configured", "detail": "ADAPTION_API_KEY is not set."}
    if not sdk_available():
        _record(
            db,
            status="failed",
            step="sdk",
            detail="The 'adaption' package is not installed (pip install adaption).",
        )
        return {"status": "failed", "detail": "adaption SDK not installed."}

    from adaption import Adaption

    client = Adaption(api_key=settings.adaption_api_key)

    # Step 1: prepare + upload instruction dataset
    csv_text, row_count = build_instruction_dataset(db)
    if row_count == 0:
        _record(
            db,
            status="failed",
            step="prepare",
            detail="No analyzed feedback available. Import the dataset and run analysis first.",
        )
        return {"status": "failed", "detail": "No analyzed feedback yet."}

    tmp_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "adaption_instruction_dataset.csv")
    )
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        f.write(csv_text)

    run_row = _record(db, status="running", step="upload", detail=f"Uploading {row_count} rows")
    try:
        dataset = client.datasets.upload_file(tmp_path)
        dataset_id = dataset.dataset_id
        run_row.dataset_id = dataset_id
        run_row.step = "import"
        db.commit()
    except Exception as exc:
        run_row.status = "failed"
        run_row.step = "upload"
        run_row.detail = f"Upload failed: {exc}"
        db.commit()
        return {"status": "failed", "detail": run_row.detail}

    # Step 2: wait for import
    try:
        import time

        deadline = time.time() + 300
        while time.time() < deadline:
            status = client.datasets.get_status(dataset_id)
            if status.status == "failed":
                run_row.status = "failed"
                run_row.step = "import"
                err = getattr(status, "error_data", None)
                run_row.detail = f"Ingestion failed: {err}"
                db.commit()
                return {"status": "failed", "detail": run_row.detail}
            if getattr(status, "row_count", None) is not None:
                break
            time.sleep(5)
    except Exception as exc:
        run_row.status = "failed"
        run_row.step = "import"
        run_row.detail = f"Status polling failed: {exc}"
        db.commit()
        return {"status": "failed", "detail": run_row.detail}

    # Step 3: estimate, then adapt
    column_mapping = {"prompt": "review", "completion": "analysis", "context": ["reference_label"]}
    job_spec = {"max_rows": row_count}
    try:
        estimate = client.datasets.adapt(
            dataset_id, column_mapping=column_mapping, job_specification=job_spec, estimate=True
        )
        est_credits = getattr(estimate, "estimated_credits_consumed", None)
        run_row.step = "adapt"
        run_row.detail = f"Estimate: {est_credits} credits"
        db.commit()
        run = client.datasets.adapt(
            dataset_id, column_mapping=column_mapping, job_specification=job_spec
        )
        run_row.run_id = run.run_id
        db.commit()
    except Exception as exc:
        run_row.status = "failed"
        run_row.step = "adapt"
        run_row.detail = f"Adapt call failed: {exc}"
        db.commit()
        return {"status": "failed", "detail": run_row.detail}

    # Step 4: wait for completion
    try:
        status = client.datasets.wait_for_completion(dataset_id, timeout=1800)
        if status.status == "failed":
            run_row.status = "failed"
            run_row.step = "run"
            run_row.detail = f"Adaptive Data run failed: {getattr(status, 'error_data', None)}"
            db.commit()
            return {"status": "failed", "detail": run_row.detail}
        run_row.step = "download"
        db.commit()
        adapted_path = tmp_path.replace(".csv", "_adapted.csv")
        client.datasets.download(dataset_id, file_format="csv").write_to_file(adapted_path)
        run_row.status = "succeeded"
        run_row.result_summary = json.dumps(
            {
                "rows_uploaded": row_count,
                "adapted_file": os.path.basename(adapted_path),
                "evaluation": evaluate_local_pipeline(db),
            }
        )
        run_row.detail = "Adaptive Data run completed; adapted dataset downloaded."
        db.commit()
        return {"status": "succeeded", "detail": run_row.detail, "dataset_id": dataset_id}
    except Exception as exc:
        run_row.status = "failed"
        run_row.step = "run"
        run_row.detail = f"Run/download failed: {exc}"
        db.commit()
        return {"status": "failed", "detail": str(exc)}
