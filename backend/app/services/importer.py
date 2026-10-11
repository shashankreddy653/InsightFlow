"""CSV import: validation, duplicate awareness, graceful error handling.

Uses pandas for parsing (quoting, embedded commas/newlines) and never
overwrites the original review text or category. Analysis fields are written
to separate tables by the analysis pipeline.
"""
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Feedback, FeedbackAnalysis, ImportBatch, IssueFeedbackLink

REQUIRED_COLUMNS = {"review", "category"}
OPTIONAL_TIMESTAMP_COLUMNS = ["timestamp", "created_at", "date", "review_date", "datetime"]


class CsvValidationError(Exception):
    """Raised when a file cannot be imported at all (bad structure)."""


@dataclass
class ImportResult:
    batch_id: int
    filename: str
    mode: str
    total_rows: int = 0
    imported_rows: int = 0
    skipped_duplicates_in_file: int = 0
    skipped_existing: int = 0
    invalid_rows: int = 0
    errors: list[str] = field(default_factory=list)
    has_timestamps: bool = False


def hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def validate_and_parse(raw: bytes, filename: str) -> tuple[pd.DataFrame, list[str]]:
    """Parse CSV bytes into a DataFrame; raise CsvValidationError on fatal problems."""
    if not raw:
        raise CsvValidationError("The uploaded file is empty.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise CsvValidationError(f"File encoding is not supported: {exc}") from exc

    if not text.strip():
        raise CsvValidationError("The uploaded file contains no data rows.")

    try:
        df = pd.read_csv(io.StringIO(text))
    except pd.errors.EmptyDataError as exc:
        raise CsvValidationError("The uploaded file has no parseable columns.") from exc
    except pd.errors.ParserError as exc:
        raise CsvValidationError(f"CSV parsing failed: {exc}") from exc

    if df.empty and len(df.columns) == 0:
        raise CsvValidationError("The uploaded file has no columns.")

    df = _normalize_columns(df)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise CsvValidationError(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Expected at least: review, category."
        )
    warnings: list[str] = []
    extra = set(df.columns) - REQUIRED_COLUMNS
    if extra:
        warnings.append(f"Additional columns ignored: {', '.join(sorted(extra))}.")
    return df, warnings


def import_dataframe(
    db: Session,
    df: pd.DataFrame,
    filename: str,
    mode: str = "append",
) -> ImportResult:
    """Insert valid rows. mode='replace' clears existing feedback first (caller confirms)."""
    result = ImportResult(batch_id=0, filename=filename, mode=mode)

    timestamp_col = next((c for c in OPTIONAL_TIMESTAMP_COLUMNS if c in df.columns), None)
    result.has_timestamps = timestamp_col is not None

    if mode == "replace":
        # Delete related rows explicitly: a bulk .delete() bypasses the ORM
        # cascade, which would orphan analysis rows and skew summary counts.
        db.query(FeedbackAnalysis).delete(synchronize_session=False)
        db.query(IssueFeedbackLink).delete(synchronize_session=False)
        db.query(Feedback).delete(synchronize_session=False)
        db.commit()

    existing_hashes = set(
        db.scalars(select(Feedback.text_hash)).all()
    )
    seen_in_file: set[str] = set()
    hash_occurrences: dict[str, int] = {}

    batch = ImportBatch(filename=filename, mode=mode)
    db.add(batch)
    db.flush()

    records: list[Feedback] = []
    result.total_rows = len(df)

    for idx, row in df.iterrows():
        if result.total_rows > 200_000:
            raise CsvValidationError("File exceeds the maximum supported row count (200,000).")
        review = row.get("review")
        category = row.get("category")
        if pd.isna(review) or not str(review).strip():
            result.invalid_rows += 1
            if result.invalid_rows <= 5:
                result.errors.append(f"Row {idx + 2}: empty or missing review text.")
            continue
        review_text = str(review).strip()
        if len(review_text) > 10_000:
            result.invalid_rows += 1
            if result.invalid_rows <= 5:
                result.errors.append(f"Row {idx + 2}: review text too long (max 10,000 chars).")
            continue

        h = hash_text(review_text)
        category_val = None if pd.isna(category) else str(category).strip() or None

        ts = None
        if timestamp_col and not pd.isna(row.get(timestamp_col)):
            try:
                ts = pd.to_datetime(row[timestamp_col], errors="raise").to_pydatetime()
            except (ValueError, TypeError):
                ts = None

        hash_occurrences[h] = hash_occurrences.get(h, 0) + 1
        already_seen = h in seen_in_file or h in existing_hashes
        seen_in_file.add(h)
        # Duplicate records are preserved (spec: never silently discard), flagged for
        # duplicate-aware analytics.
        records.append(
            Feedback(
                review_text=review_text,
                original_category=category_val,
                source="csv",
                original_timestamp=ts,
                import_batch_id=batch.id,
                text_hash=h,
                is_duplicate_text=already_seen,
            )
        )
        if already_seen:
            result.skipped_duplicates_in_file += 1

    db.add_all(records)
    result.imported_rows = len(records)
    result.skipped_existing = 0

    # Flag every record whose text appears more than once in the table
    dup_hashes = {
        h
        for h, n in db.execute(
            select(Feedback.text_hash, func.count()).group_by(Feedback.text_hash)
        ).all()
        if n > 1
    }
    if dup_hashes:
        for fb in db.scalars(select(Feedback).where(Feedback.text_hash.in_(dup_hashes))):
            fb.is_duplicate_text = True
    db.commit()

    batch.total_rows = result.total_rows
    batch.imported_rows = result.imported_rows
    batch.skipped_duplicates = result.skipped_duplicates_in_file
    batch.invalid_rows = result.invalid_rows
    batch.error_summary = "; ".join(result.errors[:5]) or None
    db.commit()

    result.batch_id = batch.id
    return result


def import_csv_file(db: Session, raw: bytes, filename: str, mode: str = "append") -> ImportResult:
    df, warnings = validate_and_parse(raw, filename)
    result = import_dataframe(db, df, filename, mode=mode)
    result.errors.extend(warnings)
    return result
