"""Sentiment analysis using VADER (rule-based, no API key needed).

VADER provides a compound score in [-1, 1] plus positive/neutral/negative
component proportions. Confidence is derived from the class proportions the
model actually produces - it is not invented.
"""
from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Domain lexicon augmentation (VADER's documented lexicon.update mechanism).
# Added because evaluation against the hand-labeled reference subset showed
# VADER lacks e-commerce complaint/praise vocabulary ("scammed", "unhelpful",
# "exceeded", "user-friendly", ...). Values are on VADER's [-4, +4] scale.
DOMAIN_LEXICON = {
    # complaint vocabulary
    "scam": -3.1, "scams": -3.1, "scammed": -3.2, "scammer": -3.2,
    "counterfeit": -2.8, "fraud": -3.0, "frauds": -3.0, "fraudulent": -3.0,
    "unhelpful": -2.4, "unresponsive": -2.1, "unresolved": -1.8,
    "glitch": -1.7, "glitches": -1.7, "crashing": -2.0, "crashed": -2.0, "crash": -2.0,
    "delay": -1.4, "delays": -1.4, "delayed": -1.5,
    "defect": -2.0, "defects": -2.0, "defective": -2.4,
    "low-quality": -2.2, "frustrating": -2.6, "frustrated": -2.6,
    "inconvenient": -1.6, "damaged": -2.0, "damage": -1.8,
    "average": -1.2, "overcharged": -2.4, "missing": -1.2,
    # praise vocabulary
    "exceeded": 2.2, "exceeds": 2.2, "outstanding": 2.8, "exceptional": 2.7,
    "user-friendly": 1.8, "hassle-free": 2.2, "smooth": 1.5,
    "reliable": 2.0, "dependable": 2.0, "durable": 1.9, "innovative": 1.9,
    "sleek": 1.6, "responsive": 1.9, "top-notch": 2.6, "game-changer": 2.6,
    "genuine": 2.2, "advertised": 1.5, "excellent": 3.1, "impressive": 2.3,
}
_analyzer.lexicon.update(DOMAIN_LEXICON)

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05

# Factual all-clear phrases: VADER's negation window flips "no fraudulent
# activity" into a positive score, but these are neutral safety confirmations.
import re

_ALL_CLEAR_PATTERN = re.compile(
    r"\bno (signs of |suspected )?(fraudulent|fraud|scam|issues|problems)\b",
    re.IGNORECASE,
)


def _is_all_clear(text: str) -> bool:
    stripped = re.sub(
        r"\b(not|wasn't|weren't|isn't|aren't|didn't|don't|doesn't)\b", "", text, flags=re.I
    )
    return bool(_ALL_CLEAR_PATTERN.search(stripped))


@dataclass
class SentimentResult:
    label: str  # positive | negative | neutral
    compound: float
    confidence: float
    pos: float
    neu: float
    neg: float


def analyze_sentiment(text: str) -> SentimentResult:
    s = _analyzer.polarity_scores(text)
    compound = float(s["compound"])
    if _is_all_clear(text):
        label, class_share = "neutral", float(s["neu"])
    elif compound >= POSITIVE_THRESHOLD:
        label, class_share = "positive", float(s["pos"])
    elif compound <= NEGATIVE_THRESHOLD:
        label, class_share = "negative", float(s["neg"])
    else:
        label, class_share = "neutral", float(s["neu"])
    # Confidence: the model's own share for the winning class, rescaled so that
    # a barely-threshold review is not reported as highly confident.
    confidence = round(min(0.99, 0.5 + class_share / 2), 4)
    return SentimentResult(
        label=label,
        compound=round(compound, 4),
        confidence=confidence,
        pos=round(float(s["pos"]), 4),
        neu=round(float(s["neu"]), 4),
        neg=round(float(s["neg"]), 4),
    )
