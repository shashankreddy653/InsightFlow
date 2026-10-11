"""Transparent priority scoring for issue groups.

Score = w_freq * frequency_norm + w_neg * negative_ratio + w_sev * severity
        [+ w_trend * trend_norm when real timestamps exist]

Weights are configurable at runtime (Settings page / API). When a factor's
input data does not exist (e.g. no timestamps for trend), its weight is
renormalized across the remaining factors and the UI states which factors were
used - nothing is silently invented.
"""
import math
from dataclasses import dataclass, field

DEFAULT_WEIGHTS = {"frequency": 0.35, "negative": 0.25, "severity": 0.25, "trend": 0.15}

PRIORITY_THRESHOLDS = {"Critical": 0.75, "High": 0.55, "Medium": 0.30}
# Critical additionally requires this severity level so frequent but mild
# complaints are not auto-labelled Critical.
CRITICAL_MIN_SEVERITY = 0.7

# Base severity by topic (0..1). Reflects potential business harm of the
# complaint type, documented and editable in code rather than hidden in a model.
TOPIC_SEVERITY = {
    "Fraud & Scam Reports": 1.0,
    "Website & Checkout Experience": 0.5,
    "Delivery Delays": 0.75,
    "Order & Packaging Problems": 0.7,
    "Product Defects & Quality Problems": 0.85,
    "Customer Service Complaints": 0.7,
    "Refunds & Compensation": 0.65,
    "Transaction Safety (No Issues Reported)": 0.05,
    "On-Time Delivery & Packaging": 0.05,
    "Customer Service Praise": 0.05,
    "Product Quality Praise": 0.05,
    "General Feedback": 0.3,
}


@dataclass
class IssueInput:
    cluster_id: int
    topic: str
    record_count: int  # total records (volume)
    unique_count: int  # unique texts in group
    negative_ratio: float  # 0..1
    avg_sentiment_magnitude: float  # 0..1 mean |compound| of members
    monthly_negative_counts: list[int] = field(default_factory=list)  # for trend, optional


@dataclass
class ScoreResult:
    score: float
    priority: str
    breakdown: dict
    factors_used: list[str]
    factors_unavailable: list[str]


def priority_label(score: float, severity: float) -> str:
    if score >= PRIORITY_THRESHOLDS["Critical"] and severity >= CRITICAL_MIN_SEVERITY:
        return "Critical"
    if score >= PRIORITY_THRESHOLDS["High"]:
        return "High"
    if score >= PRIORITY_THRESHOLDS["Medium"]:
        return "Medium"
    return "Low"


def _trend_factor(monthly_counts: list[int]) -> float | None:
    """Simple normalized recent-vs-earlier growth; None when data is insufficient."""
    if len(monthly_counts) < 2:
        return None
    half = len(monthly_counts) // 2
    earlier = sum(monthly_counts[:half])
    recent = sum(monthly_counts[half:])
    if earlier == 0 and recent == 0:
        return 0.0
    if earlier == 0:
        return 1.0
    growth = (recent - earlier) / earlier
    return max(0.0, min(1.0, (growth + 1) / 2))  # map [-1, +1] growth to [0, 1]


def score_issue(issue: IssueInput, weights: dict[str, float] | None = None) -> ScoreResult:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in DEFAULT_WEIGHTS})

    severity = min(
        1.0,
        TOPIC_SEVERITY.get(issue.topic, 0.3) * 0.7
        + issue.avg_sentiment_magnitude * 0.3,
    )

    factors: dict[str, float] = {}
    unavailable: list[str] = []

    # Frequency: log-scaled so one huge group does not dominate everything.
    if issue.record_count > 0:
        factors["frequency"] = min(1.0, math.log10(issue.record_count + 1) / math.log10(5001))
    else:
        factors["frequency"] = 0.0

    factors["negative"] = max(0.0, min(1.0, issue.negative_ratio))
    factors["severity"] = severity

    trend = _trend_factor(issue.monthly_negative_counts)
    if trend is None:
        unavailable.append("trend")
    else:
        factors["trend"] = trend

    # Renormalize weights over available factors.
    active_weights = {k: v for k, v in w.items() if k in factors}
    total_w = sum(active_weights.values())
    if total_w == 0:
        total_w = 1.0
        active_weights = {"frequency": 1.0}

    score = sum(factors[k] * (active_weights[k] / total_w) for k in active_weights)
    score = round(max(0.0, min(1.0, score)), 4)

    breakdown = {
        "components": {k: round(v, 4) for k, v in factors.items()},
        "weights_used": {k: round(active_weights[k] / total_w, 4) for k in active_weights},
        "configured_weights": w,
        "severity_base": TOPIC_SEVERITY.get(issue.topic, 0.3),
    }
    return ScoreResult(
        score=score,
        priority=priority_label(score, severity),
        breakdown=breakdown,
        factors_used=sorted(factors.keys()),
        factors_unavailable=unavailable,
    )
