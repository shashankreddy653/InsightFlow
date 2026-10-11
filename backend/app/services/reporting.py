"""Report generation: JSON snapshots, CSV export, PDF export."""
import csv
import io
import json
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Feedback, FeedbackAnalysis, Issue


def build_report_snapshot(
    total_records: int,
    unique_texts: int,
    duplicate_records: int,
    sentiment_counts: dict,
    category_counts: dict,
    topic_counts: dict,
    priority_counts: dict,
    top_issues: list[dict],
    limitations: list[str],
    filters: dict | None = None,
    title: str = "InsightFlow Feedback Analysis Report",
) -> dict:
    return {
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": filters or {},
        "dataset_summary": {
            "total_feedback_records": total_records,
            "unique_review_texts": unique_texts,
            "duplicate_records": duplicate_records,
        },
        "sentiment_distribution": sentiment_counts,
        "category_distribution": category_counts,
        "topic_distribution": topic_counts,
        "priority_distribution": priority_counts,
        "top_issues": top_issues,
        "limitations": limitations,
    }


def snapshot_to_csv(snapshot: dict) -> str:
    """Flat CSV representation of a report snapshot (sections as rows)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Section", "Key", "Value"])
    writer.writerow(["Report", "Title", snapshot["title"]])
    writer.writerow(["Report", "Generated At", snapshot["generated_at"]])
    for k, v in snapshot["dataset_summary"].items():
        writer.writerow(["Dataset", k, v])
    for section in (
        "sentiment_distribution",
        "category_distribution",
        "topic_distribution",
        "priority_distribution",
    ):
        for k, v in (snapshot.get(section) or {}).items():
            writer.writerow([section.replace("_", " ").title(), k, v])
    for issue in snapshot.get("top_issues", []):
        writer.writerow(
            [
                "Issue",
                issue.get("title", ""),
                f"priority={issue.get('priority')} score={issue.get('priority_score')} "
                f"records={issue.get('record_count')} negative={issue.get('negative_ratio')}",
            ]
        )
    for lim in snapshot.get("limitations", []):
        writer.writerow(["Limitation", "", lim])
    return buf.getvalue()


def feedback_rows_to_csv(rows: list[tuple[Feedback, FeedbackAnalysis | None]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "review",
            "original_category",
            "sentiment",
            "sentiment_score",
            "sentiment_confidence",
            "topic",
            "refined_category",
            "priority",
            "analysis_status",
            "source",
            "created_at",
        ]
    )
    for fb, an in rows:
        writer.writerow(
            [
                fb.id,
                fb.review_text,
                fb.original_category or "",
                an.sentiment if an else "",
                an.sentiment_score if an else "",
                an.sentiment_confidence if an else "",
                an.topic if an else "",
                an.refined_category if an else "",
                _issue_priority_for(fb),
                fb.analysis_status,
                fb.source,
                fb.created_at.isoformat() if fb.created_at else "",
            ]
        )
    return buf.getvalue()


def _issue_priority_for(fb: Feedback) -> str:
    for link in fb.issue_links:
        if link.issue and link.issue.priority:
            return link.issue.priority
    return ""


def issues_to_csv(issues: list[Issue]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "title",
            "topic",
            "priority",
            "priority_score",
            "status",
            "record_count",
            "negative_ratio",
            "success_metric",
            "recommendation_source",
            "created_at",
            "updated_at",
        ]
    )
    for issue in issues:
        metrics = json.loads(issue.supporting_metrics) if issue.supporting_metrics else {}
        writer.writerow(
            [
                issue.id,
                issue.title,
                issue.topic or "",
                issue.priority,
                issue.priority_score,
                issue.status,
                metrics.get("record_count", ""),
                metrics.get("negative_ratio", ""),
                issue.success_metric or "",
                issue.recommendation_source or "",
                issue.created_at.isoformat() if issue.created_at else "",
                issue.updated_at.isoformat() if issue.updated_at else "",
            ]
        )
    return buf.getvalue()


def snapshot_to_pdf(snapshot: dict) -> bytes:
    """Business-friendly PDF insight report."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        title=snapshot["title"],
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1b", parent=styles["Heading1"], textColor=colors.HexColor("#1e3a8a"))
    h2 = ParagraphStyle("H2b", parent=styles["Heading2"], textColor=colors.HexColor("#1e3a8a"))
    body = styles["BodyText"]
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11)

    story = []
    story.append(Paragraph(snapshot["title"], h1))
    story.append(
        Paragraph(
            f"Generated: {snapshot['generated_at']} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"by InsightFlow",
            small,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    ds = snapshot["dataset_summary"]
    story.append(Paragraph("Dataset summary", h2))
    data = [
        ["Total feedback records", str(ds["total_feedback_records"])],
        ["Unique review texts", str(ds["unique_review_texts"])],
        ["Duplicate records", str(ds["duplicate_records"])],
    ]
    t = Table(data, colWidths=8 * cm, hAlign="LEFT")
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1"))]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))

    def dist_table(title_text: str, dist: dict):
        if not dist:
            return
        story.append(Paragraph(title_text, h2))
        rows = [[Paragraph("<b>Label</b>", small), Paragraph("<b>Count</b>", small)]]
        rows += [[str(k), str(v)] for k, v in sorted(dist.items(), key=lambda kv: -kv[1])]
        tt = Table(rows, colWidths=10 * cm, hAlign="LEFT")
        tt.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ]
            )
        )
        story.append(tt)
        story.append(Spacer(1, 0.3 * cm))

    dist_table("Sentiment distribution", snapshot["sentiment_distribution"])
    dist_table("Category distribution", snapshot["category_distribution"])
    dist_table("Topic distribution", snapshot["topic_distribution"])
    dist_table("Priority distribution", snapshot["priority_distribution"])

    story.append(Paragraph("High-priority issues & recommendations", h2))
    if snapshot["top_issues"]:
        for issue in snapshot["top_issues"][:8]:
            story.append(
                Paragraph(
                    f"<b>{issue['title']}</b> — {issue['priority']} "
                    f"(score {issue['priority_score']}, {issue['record_count']} records, "
                    f"{round(issue['negative_ratio'] * 100)}% negative)",
                    body,
                )
            )
            if issue.get("recommendation"):
                rec = issue["recommendation"].replace("\n", "<br/>")
                story.append(Paragraph(rec, small))
            if issue.get("success_metric"):
                story.append(Paragraph(f"<i>Success metric: {issue['success_metric']}</i>", small))
            story.append(Spacer(1, 0.25 * cm))
    else:
        story.append(Paragraph("No issues identified yet — run the analysis first.", body))

    if snapshot.get("limitations"):
        story.append(Paragraph("Data limitations", h2))
        for lim in snapshot["limitations"]:
            story.append(Paragraph(f"• {lim}", small))

    doc.build(story)
    return buf.getvalue()
