"""Evidence-backed recommendation generation.

Default: transparent local template engine grounded in the actual group
statistics and sample reviews. Optional: an LLM refines the wording when
INSIGHTFLOW_LLM_API_KEY is configured - the source is recorded and shown in
the UI so users always know which one they are reading. LLM prompts receive
only structured statistics and a few sample reviews, never the full dataset.
"""
import json
import urllib.request
from dataclasses import dataclass

from ..config import get_settings

# Action playbooks keyed by topic - written for this dataset's real topics.
PLAYBOOKS: dict[str, dict[str, str]] = {
    "Fraud & Scam Reports": {
        "action": (
            "Review seller verification and payment-hold controls for the transactions "
            "referenced in these reports. Sample the supporting reviews to identify "
            "whether requests for extra payment cluster around specific sellers or "
            "product types, then tighten the fraud-detection rules for that pattern."
        ),
        "metric": "Share of Fraud & Scam-topic feedback classified as negative, week over week.",
    },
    "Delivery Delays": {
        "action": (
            "Audit fulfilment processing times for the carriers and warehouses implicated "
            "in these reviews. Check whether delays correlate with specific regions or "
            "order channels, and test proactive delay notifications where lag is "
            "unavoidable."
        ),
        "metric": "Share of delivery-related feedback mentioning delay.",
    },
    "Order & Packaging Problems": {
        "action": (
            "Inspect packing-station quality checks for the fulfilment centres implied by "
            "these reports (wrong items, missing items, damaged packaging). Compare the "
            "affected order batches against warehouse pick/pack logs."
        ),
        "metric": "Count of order-error complaints (wrong/missing/damaged) per month.",
    },
    "Product Defects & Quality Problems": {
        "action": (
            "Cluster the defect reports by product variant and compare against warranty "
            "and return data. Prioritise the variants with the highest complaint "
            "concentration for a quality inspection."
        ),
        "metric": "Count of unique defect complaints per product variant per month.",
    },
    "Customer Service Complaints": {
        "action": (
            "Sample the unresolved-support reviews to find the contact channels and "
            "issue types with the longest resolution times. Review agent staffing and "
            "macros for those queues."
        ),
        "metric": "Share of support-related feedback classified as negative.",
    },
    "Website & Checkout Experience": {
        "action": (
            "Reproduce the checkout flows mentioned in the reviews on the affected "
            "devices/browsers. Check session and error logs for the corresponding "
            "funnel steps before the next release."
        ),
        "metric": "Share of digital-experience feedback classified as negative.",
    },
    "Refunds & Compensation": {
        "action": (
            "Review refund-policy wording and processing times against the expectations "
            "expressed in these reviews; clarify policy copy where confusion repeats."
        ),
        "metric": "Share of refund-mentioning reviews expressing dissatisfaction.",
    },
    "Transaction Safety (No Issues Reported)": {
        "action": (
            "No corrective action required - these reviews report safe transactions. "
            "Consider featuring this reassurance in onboarding copy."
        ),
        "metric": "Maintain low volume of fraud reports relative to safety confirmations.",
    },
    "On-Time Delivery & Packaging": {
        "action": (
            "No corrective action required. Use these reviews to identify the carriers "
            "and packaging practices worth standardising."
        ),
        "metric": "Maintain the current on-time delivery share.",
    },
    "Customer Service Praise": {
        "action": (
            "No corrective action required. Extract the praised behaviours as training "
            "examples for underperforming queues."
        ),
        "metric": "Maintain the current positive-support share.",
    },
    "Product Quality Praise": {
        "action": (
            "No corrective action required. Mine these reviews for the features "
            "customers value most to inform positioning."
        ),
        "metric": "Maintain the current positive-product share.",
    },
    "General Feedback": {
        "action": (
            "Review the sampled reviews manually - the system could not assign a "
            "specific theme, so the evidence is thin."
        ),
        "metric": "Reduction of unclassified feedback share over time.",
    },
}

FALLBACK_PLAYBOOK = PLAYBOOKS["General Feedback"]


@dataclass
class RecommendationResult:
    text: str
    source: str  # template | llm
    success_metric: str


def build_evidence_lines(group_stats: dict, sample_reviews: list[str]) -> list[str]:
    lines = [
        f"{group_stats['record_count']} feedback records reference this issue "
        f"({group_stats['unique_count']} unique review texts).",
        f"{round(group_stats['negative_ratio'] * 100)}% of the associated reviews "
        f"are classified as negative.",
    ]
    cats = group_stats.get("category_breakdown") or {}
    if cats:
        top = sorted(cats.items(), key=lambda kv: -kv[1])[:3]
        lines.append(
            "Original categories involved: "
            + ", ".join(f"{k} ({v})" for k, v in top)
            + "."
        )
    if group_stats.get("trend_note"):
        lines.append(group_stats["trend_note"])
    return lines


def generate_recommendation(
    topic: str,
    group_stats: dict,
    sample_reviews: list[str],
    use_llm: bool = True,
) -> RecommendationResult:
    playbook = PLAYBOOKS.get(topic, FALLBACK_PLAYBOOK)
    evidence = build_evidence_lines(group_stats, sample_reviews)
    evidence_block = "\n".join(f"- {e}" for e in evidence)

    template_text = (
        f"Evidence:\n{evidence_block}\n\n"
        f"Recommended action:\n{playbook['action']}\n\n"
        f"Note: this recommendation is derived from the observed feedback patterns. "
        f"It does not claim a proven root cause and makes no financial projections."
    )

    if use_llm:
        llm_text = _llm_refine(topic, group_stats, sample_reviews)
        if llm_text:
            return RecommendationResult(text=llm_text, source="llm", success_metric=playbook["metric"])

    return RecommendationResult(text=template_text, source="template", success_metric=playbook["metric"])


def _llm_refine(topic: str, group_stats: dict, sample_reviews: list[str]) -> str | None:
    """Best-effort LLM refinement; returns None on any failure (caller falls back)."""
    settings = get_settings()
    if not settings.insightflow_llm_api_key:
        return None
    prompt = (
        "You are a customer-experience analyst. Write a concise, evidence-backed "
        "recommendation for the issue below. Rules: only reference the supplied "
        "statistics and reviews; do not invent root causes, financial figures, or "
        "guarantees; if evidence is limited, say so.\n\n"
        f"Issue topic: {topic}\n"
        f"Statistics: {json.dumps(group_stats, ensure_ascii=False)}\n"
        f"Sample reviews: {json.dumps(sample_reviews[:5], ensure_ascii=False)}"
    )
    body = json.dumps(
        {
            "model": settings.insightflow_llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        settings.insightflow_llm_base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.insightflow_llm_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
