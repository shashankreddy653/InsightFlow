"""Settings, Adaption integration, and health endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppSetting
from ..services import adaption_service
from ..services.prioritization import DEFAULT_WEIGHTS

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"
    return {"status": "ok", "database": db_status}


@router.get("/settings")
def get_app_settings(db: Session = Depends(get_db)):
    stored = {s.key: s.value for s in db.scalars(select(AppSetting)).all()}
    weights = dict(DEFAULT_WEIGHTS)
    for k in DEFAULT_WEIGHTS:
        if f"weight_{k}" in stored:
            try:
                weights[k] = float(stored[f"weight_{k}"])
            except ValueError:
                pass
    return {
        "priority_weights": weights,
        "llm_configured": bool(stored.get("llm_enabled", "0") == "1"),
        "adaption_configured": adaption_service.integration_status(db)["configured"],
    }


class SettingsPayload(BaseModel):
    weight_frequency: float | None = Field(default=None, ge=0, le=1)
    weight_negative: float | None = Field(default=None, ge=0, le=1)
    weight_severity: float | None = Field(default=None, ge=0, le=1)
    weight_trend: float | None = Field(default=None, ge=0, le=1)


@router.post("/settings")
def update_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    for field, value in payload.model_dump(exclude_none=True).items():
        db.merge(AppSetting(key=field, value=str(value)))
    db.commit()
    return get_app_settings(db)


@router.post("/settings/rescore")
def rescore_issues(db: Session = Depends(get_db)):
    """Re-run grouping/scoring with current weights."""
    from ..services.analyzer import _rebuild_issue_groups

    stored = {s.key: s.value for s in db.scalars(select(AppSetting)).all()}
    weights = {}
    for k in DEFAULT_WEIGHTS:
        if f"weight_{k}" in stored:
            try:
                weights[k] = float(stored[f"weight_{k}"])
            except ValueError:
                pass
    _rebuild_issue_groups(db, weights or None)
    return {"status": "ok", "weights_applied": weights or DEFAULT_WEIGHTS}


@router.get("/integrations/adaption")
def adaption_status(db: Session = Depends(get_db)):
    return adaption_service.integration_status(db)


@router.post("/integrations/adaption/run")
def adaption_run(db: Session = Depends(get_db)):
    """Launch the Adaptive Data workflow (requires ADAPTION_API_KEY)."""
    return adaption_service.run_adaption_workflow(db)


@router.post("/integrations/adaption/evaluate")
def adaption_evaluate(db: Session = Depends(get_db)):
    """Evaluate the local pipeline against the hand-labeled reference subset."""
    return adaption_service.evaluate_local_pipeline(db)


@router.get("/integrations/adaption/dataset")
def adaption_dataset_preview(db: Session = Depends(get_db)):
    """Preview the instruction dataset that would be sent to Adaption."""
    csv_text, count = adaption_service.build_instruction_dataset(db)
    return {"row_count": count, "preview": csv_text.splitlines()[:6]}
